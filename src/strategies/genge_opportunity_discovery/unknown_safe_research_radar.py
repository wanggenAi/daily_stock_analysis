"""Build a fail-closed research radar from verified V3.1 deep-review profiles.

The radar exists to preserve research visibility when a candidate still has UNKNOWN
hard gates. It does not relax hard gates, promote UNKNOWN to PASS, or create Formal
trading authority. A candidate with any verified FAIL is excluded. Candidates need
a minimum amount of verified PASS progress before they can enter the radar.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT = "GEN_GE_V31_UNKNOWN_SAFE_RESEARCH_RADAR_V1"
AUTHORITY = "RESEARCH_ONLY"
DEFAULT_MIN_VERIFIED_PASS_GATES = 2
DEFAULT_TOP_N = 10
HARD_GATES = (
    "predictability",
    "long_term_demand",
    "moat",
    "financial_safety",
    "earnings_authenticity",
)
VERIFIED_PASS_SOURCES = frozenset({"EXPLICIT_VERIFIED", "AUTOMATIC_MACHINE"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _float(value: Any, default: float = float("-inf")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = [
            "radar_rank",
            "code",
            "stock_name",
            "radar_tier",
            "verified_pass_gate_count",
            "unknown_gate_count",
            "fail_gate_count",
        ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)


def _load_profiles(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = _text(payload.get("contract"))
    if not contract.startswith("GEN_GE_V31_AUTOMATIC_DEEP_CALC_"):
        raise ValueError(f"unexpected deep-profile contract: {contract!r}")
    if payload.get("authority") != "RESEARCH_ONLY":
        raise ValueError("deep profiles must remain RESEARCH_ONLY")
    if payload.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("deep profiles must not grant automatic Formal BUY")
    if payload.get("unknown_is_pass") is not False:
        raise ValueError("deep profiles must preserve UNKNOWN != PASS")
    if payload.get("no_auto_trade") is not True:
        raise ValueError("deep profiles must preserve no_auto_trade=true")
    if not isinstance(payload.get("profiles"), Mapping):
        raise ValueError("deep profiles payload must contain a profiles object")
    return payload


def _normalized_gate_state(raw: Mapping[str, Any] | None) -> tuple[str, bool]:
    gate = raw if isinstance(raw, Mapping) else {}
    status = _text(gate.get("status")).upper()
    if status == "FAIL":
        return "FAIL", False
    if status != "PASS":
        return "UNKNOWN", False
    source = _text(gate.get("source")).upper()
    evidence = gate.get("evidence")
    verified = source in VERIFIED_PASS_SOURCES and isinstance(evidence, list) and bool(evidence)
    return ("PASS", True) if verified else ("UNKNOWN", False)


def _classify_candidate(
    row: Mapping[str, Any],
    profile: Mapping[str, Any] | None,
    *,
    min_verified_pass_gates: int,
) -> dict[str, Any]:
    code = _code(row.get("code") or row.get("stock_code") or row.get("symbol"))
    profile_obj = profile if isinstance(profile, Mapping) else None
    if profile_obj is None:
        return {
            "code": code,
            "eligible": False,
            "exclusion_reason": "MISSING_VERIFIED_PROFILE",
            "verified_pass_gates": [],
            "unknown_gates": list(HARD_GATES),
            "fail_gates": [],
            "unverified_pass_gates": [],
        }

    gates_raw = profile_obj.get("gates")
    gates = gates_raw if isinstance(gates_raw, Mapping) else {}
    pass_gates: list[str] = []
    unknown_gates: list[str] = []
    fail_gates: list[str] = []
    unverified_pass_gates: list[str] = []
    for gate_name in HARD_GATES:
        raw_gate = gates.get(gate_name)
        normalized, verified = _normalized_gate_state(raw_gate if isinstance(raw_gate, Mapping) else None)
        original_status = _text(raw_gate.get("status") if isinstance(raw_gate, Mapping) else "").upper()
        if original_status == "PASS" and not verified:
            unverified_pass_gates.append(gate_name)
        if normalized == "PASS":
            pass_gates.append(gate_name)
        elif normalized == "FAIL":
            fail_gates.append(gate_name)
        else:
            unknown_gates.append(gate_name)

    if fail_gates:
        eligible = False
        reason = "HARD_GATE_FAIL"
    elif len(pass_gates) < min_verified_pass_gates:
        eligible = False
        reason = "INSUFFICIENT_VERIFIED_PROGRESS"
    else:
        eligible = True
        reason = ""

    return {
        "code": code,
        "eligible": eligible,
        "exclusion_reason": reason,
        "verified_pass_gates": pass_gates,
        "unknown_gates": unknown_gates,
        "fail_gates": fail_gates,
        "unverified_pass_gates": unverified_pass_gates,
    }


def _ranking_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row["verified_pass_gate_count"]),
        -_float(row.get("quant_score")),
        _int(row.get("v31_review_rank")),
        str(row.get("code") or ""),
    )


def build_radar(
    candidate_rows: list[dict[str, Any]],
    profile_payload: Mapping[str, Any],
    *,
    min_verified_pass_gates: int = DEFAULT_MIN_VERIFIED_PASS_GATES,
    top_n: int = DEFAULT_TOP_N,
    source_run_id: str = "",
) -> dict[str, Any]:
    min_verified_pass_gates = max(1, min(int(min_verified_pass_gates), len(HARD_GATES)))
    top_n = max(1, min(int(top_n), 100))
    profiles_raw = profile_payload.get("profiles")
    profiles = profiles_raw if isinstance(profiles_raw, Mapping) else {}

    eligible: list[dict[str, Any]] = []
    hard_fail_excluded_count = 0
    insufficient_verified_progress_count = 0
    missing_profile_count = 0
    unverified_pass_downgraded_count = 0

    for source in candidate_rows:
        row = dict(source)
        code = _code(row.get("code") or row.get("stock_code") or row.get("symbol"))
        if not code:
            continue
        classification = _classify_candidate(
            row,
            profiles.get(code) if isinstance(profiles, Mapping) else None,
            min_verified_pass_gates=min_verified_pass_gates,
        )
        unverified_pass_downgraded_count += len(classification["unverified_pass_gates"])
        if not classification["eligible"]:
            reason = classification["exclusion_reason"]
            if reason == "HARD_GATE_FAIL":
                hard_fail_excluded_count += 1
            elif reason == "MISSING_VERIFIED_PROFILE":
                missing_profile_count += 1
            else:
                insufficient_verified_progress_count += 1
            continue

        unknown_gates = list(classification["unknown_gates"])
        pass_gates = list(classification["verified_pass_gates"])
        radar_tier = "FULL_EVIDENCE" if not unknown_gates else "UNKNOWN_RESEARCH"
        eligible.append(
            {
                "radar_rank": 0,
                "code": code,
                "stock_name": _text(row.get("stock_name") or row.get("name") or (profiles.get(code) or {}).get("name")),
                "industry": _text(row.get("industry") or (profiles.get(code) or {}).get("industry")),
                "radar_tier": radar_tier,
                "verified_pass_gate_count": len(pass_gates),
                "unknown_gate_count": len(unknown_gates),
                "fail_gate_count": 0,
                "verified_pass_gates": ",".join(pass_gates),
                "unknown_gates": ",".join(unknown_gates),
                "quant_score": row.get("quant_score"),
                "v31_review_rank": row.get("v31_review_rank"),
                "research_priority": row.get("research_priority"),
                "followup": "VALUATION_CLOSURE" if radar_tier == "FULL_EVIDENCE" else "EVIDENCE_CLOSURE",
                "authority": AUTHORITY,
                "formal_trading_authority": False,
                "automatic_formal_buy_allowed": False,
                "mutates_authoritative_decision": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
            }
        )

    eligible.sort(key=_ranking_key)
    for rank, row in enumerate(eligible, start=1):
        row["radar_rank"] = rank
    top = eligible[:top_n]

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = {
        "contract": CONTRACT,
        "authority": AUTHORITY,
        "generated_at": now,
        "source_run_id": str(source_run_id or profile_payload.get("source_run_id") or ""),
        "source_deep_profile_contract": _text(profile_payload.get("contract")),
        "candidate_count": len(candidate_rows),
        "radar_eligible_count": len(eligible),
        "hard_fail_excluded_count": hard_fail_excluded_count,
        "insufficient_verified_progress_count": insufficient_verified_progress_count,
        "missing_profile_count": missing_profile_count,
        "unverified_pass_downgraded_count": unverified_pass_downgraded_count,
        "unknown_eligible_count": sum(row["radar_tier"] == "UNKNOWN_RESEARCH" for row in eligible),
        "full_evidence_count": sum(row["radar_tier"] == "FULL_EVIDENCE" for row in eligible),
        "top_count": len(top),
        "requested_top_n": top_n,
        "min_verified_pass_gates": min_verified_pass_gates,
        "ranking_policy": "VERIFIED_PASS_COUNT_DESC_THEN_QUANT_DESC_THEN_V31_REVIEW_RANK_ASC_THEN_CODE_ASC",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "mutates_authoritative_decision": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    return {"summary": summary, "eligible_rows": eligible, "top_rows": top}


def _render_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    top_rows = payload["top_rows"]
    lines = [
        "# GenGe UNKNOWN-Safe Research Radar",
        "",
        "> Research-only visibility layer. UNKNOWN remains UNKNOWN; any hard-gate FAIL is excluded; this artifact cannot create Formal actions or orders.",
        "",
        f"- source run: `{summary.get('source_run_id')}`",
        f"- candidates inspected: **{summary.get('candidate_count')}**",
        f"- radar eligible: **{summary.get('radar_eligible_count')}**",
        f"- hard-gate FAIL excluded: **{summary.get('hard_fail_excluded_count')}**",
        f"- insufficient verified progress: **{summary.get('insufficient_verified_progress_count')}**",
        f"- UNKNOWN-eligible research candidates: **{summary.get('unknown_eligible_count')}**",
        f"- full-evidence candidates: **{summary.get('full_evidence_count')}**",
        f"- Top rows emitted: **{summary.get('top_count')}** / requested {summary.get('requested_top_n')}",
        f"- admission floor: at least **{summary.get('min_verified_pass_gates')} verified PASS** gates and **zero FAIL** gates.",
        "- Formal authority: **none**; automatic Formal BUY: **false**; UNKNOWN != PASS; no_auto_trade=true.",
        "",
        "## Research Top",
        "",
        "| Rank | Code | Name | Tier | PASS | UNKNOWN | Quant | V3.1 rank | Follow-up |",
        "|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in top_rows:
        quant = _text(row.get("quant_score")) or "—"
        review_rank = _text(row.get("v31_review_rank")) or "—"
        lines.append(
            f"| {row['radar_rank']} | {row['code']} | {row['stock_name']} | {row['radar_tier']} | "
            f"{row['verified_pass_gate_count']} | {row['unknown_gate_count']} | {quant} | {review_rank} | {row['followup']} |"
        )
    if not top_rows:
        lines.append("| — | — | No eligible research candidate | — | — | — | — | — | — |")
    lines.extend(["", "This is a research queue, not a buy list or execution instruction.", ""])
    return "\n".join(lines)


def run(
    *,
    candidate_csv: Path,
    deep_profiles_json: Path,
    output_dir: Path,
    min_verified_pass_gates: int = DEFAULT_MIN_VERIFIED_PASS_GATES,
    top_n: int = DEFAULT_TOP_N,
    source_run_id: str = "",
) -> dict[str, Any]:
    candidate_rows = _read_csv(candidate_csv)
    profile_payload = _load_profiles(deep_profiles_json)
    payload = build_radar(
        candidate_rows,
        profile_payload,
        min_verified_pass_gates=min_verified_pass_gates,
        top_n=top_n,
        source_run_id=source_run_id,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "research_radar.csv", payload["eligible_rows"])
    (output_dir / "research_radar.json").write_text(
        json.dumps(
            {"summary": payload["summary"], "top_rows": payload["top_rows"]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    (output_dir / "research_radar.md").write_text(
        _render_markdown(payload), encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--deep-profiles-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-verified-pass-gates", type=int, default=DEFAULT_MIN_VERIFIED_PASS_GATES)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--source-run-id", default="")
    args = parser.parse_args()
    payload = run(
        candidate_csv=args.candidate_csv,
        deep_profiles_json=args.deep_profiles_json,
        output_dir=args.output_dir,
        min_verified_pass_gates=args.min_verified_pass_gates,
        top_n=args.top_n,
        source_run_id=args.source_run_id,
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
