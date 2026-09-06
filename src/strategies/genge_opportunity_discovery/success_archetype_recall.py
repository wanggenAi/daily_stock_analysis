from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery import valuation_research_report as valuation

CONTRACT_VERSION = "GEN_GE_SUCCESS_ARCHETYPE_RECALL_V1"
AUTHORITY = "RESEARCH_ONLY_SUCCESS_ARCHETYPE_RECALL"
DEFAULT_ARCHETYPE = Path("data/research_archetypes/runbei_v1.json")


def _text(v: Any) -> str:
    return str(v or "").strip()


def _bool(v: Any) -> bool:
    return v is True or _text(v).lower() in {"1", "true", "yes", "pass", "passed"}


def _float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _code(v: Any) -> str:
    s = _text(v).upper()
    if "." in s:
        b, suffix = s.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            s = b
    for p in ("SH", "SZ", "BJ"):
        if s.startswith(p) and s[len(p):].isdigit():
            s = s[len(p):]
    return s.zfill(6) if s.isdigit() else s


def _tokens(v: Any) -> list[str]:
    return [x.strip() for x in _text(v).replace(",", ";").split(";") if x.strip()]


def load_archetype(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("archetype_id") or not payload.get("features"):
        raise ValueError("invalid archetype config")
    weight = sum(float(f["weight"]) for f in payload["features"])
    if not math.isclose(weight, 100.0, abs_tol=1e-6):
        raise ValueError(f"feature weights must sum to 100, got {weight}")
    ref = payload.get("reference") or {}
    if ref.get("post_cutoff_returns_used_as_features") is not False:
        raise ValueError("post-cutoff returns must be forbidden")
    if ref.get("post_cutoff_valuation_used_as_features") is not False:
        raise ValueError("post-cutoff valuation must be forbidden")
    return payload


def _prior_same_period(frame, current: Mapping[str, Any], *, as_of: date) -> Mapping[str, Any]:
    rd = valuation._coerce_date(current.get("report_date"))
    if rd is None or frame is None or frame.empty:
        return {}
    target = date(rd.year - 1, rd.month, rd.day)
    local = frame.copy()
    local["report_date"] = local["report_date"].map(valuation._coerce_date)
    if "disclosure_date" in local.columns:
        local["disclosure_date"] = local["disclosure_date"].map(valuation._coerce_date)
        local = local[(local["disclosure_date"].isna()) | (local["disclosure_date"] <= as_of)]
    rows = local[local["report_date"] == target]
    return {} if rows.empty else rows.iloc[-1].to_dict()


def _yoy(current: Any, prior: Any) -> float | None:
    c, p = _float(current), _float(prior)
    if c is None or p is None or p == 0:
        return None
    return (c / p - 1.0) * 100.0


def enrich_growth(row: Mapping[str, Any], frame, *, as_of: date) -> dict[str, Any]:
    out = dict(row)
    current, method = valuation._financial_pit_row(frame, as_of=as_of)
    prior = _prior_same_period(frame, current, as_of=as_of)
    out["archetype_financial_pit_method"] = method
    out["archetype_financial_report_date"] = current.get("report_date") or ""
    out["archetype_financial_disclosure_date"] = current.get("disclosure_date") or ""
    for src, dst in (
        ("net_profit", "net_profit_yoy_pct"),
        ("recurring_profit", "recurring_profit_yoy_pct"),
        ("operating_cash_flow", "operating_cash_flow_yoy_pct"),
    ):
        out[dst] = _yoy(current.get(src), prior.get(src))
    return out


def _safe(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if _tokens(row.get("v31_hard_gate_failures")):
        blockers.append("confirmed_hard_gate_failure")
    if _tokens(row.get("confirmed_negative_items")):
        blockers.append("confirmed_negative_evidence")
    if _tokens(row.get("conflicted_evidence_items")):
        blockers.append("conflicted_evidence")
    if _text(row.get("terminal_reason_class")).upper() == "HARD_GATE_FAILED":
        blockers.append("terminal_hard_gate_failed")
    eligible = _bool(row.get("v31_execution_universe_eligible")) or _text(row.get("v31_execution_universe_status")).upper() == "EXECUTION_ELIGIBLE"
    if not eligible:
        blockers.append("execution_universe_ineligible")
    if not _bool(row.get("terminal_full_review_attempted")):
        blockers.append("full_review_not_attempted")
    if _text(row.get("financial_review_status")).upper() != "OK":
        blockers.append("financial_review_not_ok")
    return not blockers, blockers


def _points(row: Mapping[str, Any], feature: Mapping[str, Any]) -> tuple[float, bool, str]:
    aliases = feature.get("aliases") or [feature["id"]]
    field = next((a for a in aliases if row.get(a) not in (None, "")), None)
    if field is None:
        return 0.0, False, ""
    value = _float(row.get(field))
    ref = _float(feature.get("reference_value"))
    tol = _float(feature.get("tolerance"))
    if value is None or ref is None or tol is None or tol <= 0:
        return 0.0, False, ""
    similarity = max(0.0, 1.0 - abs(value - ref) / tol)
    return float(feature["weight"]) * similarity, True, field


def score_row(row: Mapping[str, Any], archetype: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    score = 0.0
    available = 0.0
    details: dict[str, float | None] = {}
    sources: dict[str, str] = {}
    missing: list[str] = []
    for feature in archetype["features"]:
        pts, ok, source = _points(row, feature)
        fid = str(feature["id"])
        if ok:
            score += pts
            available += float(feature["weight"])
            details[fid] = round(pts, 4)
            sources[fid] = source
        else:
            details[fid] = None
            missing.append(fid)
    coverage = available / 100.0
    safe, blockers = _safe(row)
    thresholds = archetype.get("thresholds") or {}
    match = (
        safe
        and _text(row.get("terminal_decision")).upper() in {"REJECT", "WAIT_PRICE"}
        and score >= float(thresholds.get("min_similarity_score", 52))
        and coverage >= float(thresholds.get("min_evidence_coverage", 0.60))
    )
    out.update({
        "success_archetype_id": archetype["archetype_id"],
        "success_archetype_similarity_score": round(score, 4),
        "success_archetype_evidence_coverage": round(coverage, 4),
        "success_archetype_state": "ARCHETYPE_MATCH" if match else "NONE",
        "success_archetype_safety_eligible": safe,
        "success_archetype_blockers": ";".join(blockers),
        "success_archetype_missing_features": ";".join(missing),
        "success_archetype_feature_scores_json": json.dumps(details, ensure_ascii=False, sort_keys=True),
        "success_archetype_feature_sources_json": json.dumps(sources, ensure_ascii=False, sort_keys=True),
        "success_archetype_changes_research_order_only": True,
        "success_archetype_changes_thresholds": False,
        "success_archetype_formal_action_eligible": False,
        "success_archetype_formal_action_recomputed": False,
        "success_archetype_automatic_promotion_allowed": False,
        "success_archetype_starter_position_allowed": False,
        "success_archetype_unknown_evidence_is_pass": False,
        "success_archetype_no_auto_trade": True,
    })
    return out


def build_priority_payload(rows: Iterable[Mapping[str, Any]], archetype: Mapping[str, Any]) -> dict[str, Any]:
    ref = _code((archetype.get("reference") or {}).get("code"))
    queue = []
    for row in rows:
        if row.get("success_archetype_state") != "ARCHETYPE_MATCH" or _code(row.get("code")) == ref:
            continue
        queue.append({
            "code": _code(row.get("code")),
            "name": _text(row.get("stock_name") or row.get("name")),
            "archetype_id": archetype["archetype_id"],
            "similarity_score": row["success_archetype_similarity_score"],
            "evidence_coverage": row["success_archetype_evidence_coverage"],
            "source_quant_status": _text(row.get("quant_status")),
            "formal_action_eligible": False,
            "formal_action_recomputed": False,
            "automatic_promotion_allowed": False,
            "starter_position_allowed": False,
            "no_auto_trade": True,
        })
    queue.sort(key=lambda x: (-float(x["similarity_score"]), -float(x["evidence_coverage"]), x["code"]))
    return {
        "contract_version": CONTRACT_VERSION,
        "authority": AUTHORITY,
        "archetype_id": archetype["archetype_id"],
        "reference_code": ref,
        "queue_count": len(queue),
        "queue": queue,
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "canonical_authority_unchanged": True,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "changes_research_order_only": True,
        "changes_thresholds": False,
        "unknown_evidence_is_pass": False,
        "no_auto_trade": True,
    }


def run(rows: list[dict[str, Any]], *, archetype: dict[str, Any], as_of: date, cache_dir: Path, max_workers: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    loader = PublicFundamentalLoader(cache_dir)
    reviewable = [row for row in rows if _text(row.get("financial_review_status")).upper() == "OK"]
    frames: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        jobs = {
            pool.submit(loader.load, _code(row.get("code")), years=3, fetch_valuation=False, fetch_financial=True): _code(row.get("code"))
            for row in reviewable
        }
        for future in as_completed(jobs):
            code = jobs[future]
            try:
                frames[code] = future.result().financial_df
            except Exception:
                frames[code] = None
    scored = []
    for row in rows:
        code = _code(row.get("code"))
        enriched = enrich_growth(row, frames.get(code), as_of=as_of) if code in frames else dict(row)
        scored.append(score_row(enriched, archetype))
    scored.sort(key=lambda row: (row.get("success_archetype_state") != "ARCHETYPE_MATCH", -float(row.get("success_archetype_similarity_score") or 0), _code(row.get("code"))))
    return scored, build_priority_payload(scored, archetype)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-csv", type=Path, required=True)
    parser.add_argument("--archetype", type=Path, default=DEFAULT_ARCHETYPE)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/valuation_research_fundamentals"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    archetype = load_archetype(args.archetype)
    with args.terminal_csv.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    scored, payload = run(rows, archetype=archetype, as_of=as_of, cache_dir=args.cache_dir, max_workers=args.max_workers)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys([*(rows[0].keys() if rows else []), *[key for row in scored for key in row.keys()]]))
    with (args.output_dir / "success_archetype_scored.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in scored)
    (args.output_dir / "success_archetype_priority.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"archetype_id": archetype["archetype_id"], "scored_count": len(scored), "queue_count": payload["queue_count"], "formal_action_eligible": False, "no_auto_trade": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
