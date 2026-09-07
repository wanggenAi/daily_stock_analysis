"""Targeted evidence recovery for Near-BUY missing-evidence candidates.

This module is deliberately research-only. It turns the observer-only Near-BUY
Evidence Recovery A/B/C queue into a bounded public-evidence workset, invokes
existing evidence collectors, and emits an auditable review packet plus a
research-priority overlay. It never infers qualitative V3.1 hard-gate PASS,
never recomputes Formal actions, and never creates trade authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CONTRACT_VERSION = "GEN_GE_NEAR_BUY_EVIDENCE_RECOVERY_V1"
RESEARCH_AUTHORITY = "RESEARCH_ONLY_EVIDENCE_RECOVERY"
RECOVERY_STATE = "EVIDENCE_RECOVERY_PRIORITY"
RECOVERY_TIERS = ("A", "B", "C")
TIER_PRIORITY_BOOST = {"A": 45, "B": 30, "C": 20}


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


def _tokens(value: Any) -> list[str]:
    return [token.strip() for token in _text(value).replace(",", ";").split(";") if token.strip()]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        if not fields:
            stream.write("")
            return
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _stable_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    canonical = [
        {
            "code": _code(row.get("code")),
            "tier": _text(row.get("evidence_recovery_priority_tier")).upper(),
            "missing": sorted(_tokens(row.get("missing_evidence_items"))),
        }
        for row in rows
    ]
    canonical.sort(key=lambda item: (item["tier"], item["code"], item["missing"]))
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_recovery_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and deterministically order the missing-only Recovery workset."""
    tier_rank = {tier: index for index, tier in enumerate(RECOVERY_TIERS)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        row = dict(raw)
        if _text(row.get("research_opportunity_state")).upper() != RECOVERY_STATE:
            continue
        code = _code(row.get("code"))
        tier = _text(row.get("evidence_recovery_priority_tier")).upper()
        missing = _tokens(row.get("missing_evidence_items"))
        if not code or tier not in RECOVERY_TIERS or not missing:
            continue
        if code in seen:
            continue
        if _tokens(row.get("v31_hard_gate_failures")):
            raise AssertionError(f"recovery workset contains hard-gate failure: {code}")
        if _tokens(row.get("confirmed_negative_items")):
            raise AssertionError(f"recovery workset contains confirmed negative: {code}")
        if _tokens(row.get("conflicted_evidence_items")):
            raise AssertionError(f"recovery workset contains conflicted evidence: {code}")
        if _text(row.get("evidence_recovery_starter_allowed")).lower() not in {"", "false", "0", "no"}:
            raise AssertionError(f"recovery workset contains starter authority: {code}")
        row["code"] = code
        row["evidence_recovery_priority_tier"] = tier
        row["normalized_industry"] = _text(row.get("normalized_industry") or row.get("industry"))
        row["source_row_immutable"] = True
        result.append(row)
        seen.add(code)
    result.sort(
        key=lambda row: (
            tier_rank[_text(row.get("evidence_recovery_priority_tier")).upper()],
            float(row.get("master_research_rank") or 10**9),
            row["code"],
        )
    )
    return result


_TASK_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("predictability",), ("COMPANY_ANNUAL_REPORT", "BUSINESS_MODEL_HISTORY_REVIEW")),
    (("long_term_demand", "demand"), ("PUBLIC_INDUSTRY_DATA", "COMPANY_ANNUAL_REPORT")),
    (("moat",), ("COMPANY_ANNUAL_REPORT", "COMPETITION_PEER_MAPPING")),
    (("financial_safety",), ("COMPANY_ANNUAL_REPORT", "BALANCE_SHEET_CASHFLOW_REVIEW")),
    (("earnings_authenticity", "normalized_profit"), ("COMPANY_ANNUAL_REPORT", "EARNINGS_QUALITY_REVIEW")),
    (("score",), ("QUALITATIVE_SCORE_REVIEW",)),
    (("scenario_valuation",), ("SCENARIO_VALUATION_REVIEW",)),
    (("implied_expectation",), ("MARKET_IMPLIED_EXPECTATION_REVIEW",)),
    (("expectation_gap",), ("EXPECTATION_GAP_REVIEW",)),
    (("risk_adjusted_cagr",), ("RISK_ADJUSTED_CAGR_REVIEW",)),
    (("downside",), ("DOWNSIDE_STRESS_REVIEW",)),
    (("falsification",), ("FALSIFICATION_CONDITION_REVIEW",)),
)


def evidence_tasks(missing_items: Sequence[str]) -> list[str]:
    """Map evidence debt to collection/review tasks without inferring outcomes."""
    tasks: list[str] = []
    for raw in missing_items:
        token = _text(raw).lower()
        matched = False
        for needles, mapped in _TASK_RULES:
            if any(needle in token for needle in needles):
                tasks.extend(mapped)
                matched = True
        if not matched:
            tasks.append("EXPLICIT_EVIDENCE_REVIEW")
    return list(dict.fromkeys(tasks))


def build_priority_payload(
    rows: Sequence[Mapping[str, Any]], *, source_run_id: str = "", workset_digest: str = ""
) -> dict[str, Any]:
    queue: list[dict[str, Any]] = []
    for row in rows:
        tier = _text(row.get("evidence_recovery_priority_tier")).upper()
        queue.append(
            {
                "code": _code(row.get("code")),
                "name": _text(row.get("stock_name") or row.get("name")),
                "recovery_tier": tier,
                "priority_boost": TIER_PRIORITY_BOOST[tier],
                "reason_codes": [f"NEAR_BUY_EVIDENCE_RECOVERY_{tier}"],
                "missing_evidence_items": _tokens(row.get("missing_evidence_items")),
                "formal_action_eligible": False,
                "formal_action_recomputed": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "authority": RESEARCH_AUTHORITY,
        "source_near_buy_run_id": source_run_id,
        "workset_digest": workset_digest,
        "queue_count": len(queue),
        "queue": queue,
        "priority_changes_order_only": True,
        "threshold_changes_allowed": False,
        "automatic_gate_inference_allowed": False,
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "canonical_authority_unchanged": True,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "no_auto_trade": True,
    }


def _evidence_refs(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for row in rows:
        ref = _text(row.get("original_url") or row.get("source"))
        if ref and ref not in refs:
            refs.append(ref)
    return refs[:12]


def build_review_packets(
    workset: Sequence[Mapping[str, Any]],
    *,
    company_evidence: Sequence[Mapping[str, Any]],
    industry_evidence: Sequence[Mapping[str, Any]],
    audit_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in workset:
        code = _code(row.get("code"))
        industry = _text(row.get("normalized_industry") or row.get("industry"))
        company = [item for item in company_evidence if _code(item.get("code")) == code]
        industry_rows = [item for item in industry_evidence if industry and _text(item.get("industry")) == industry]
        audits = [
            item
            for item in audit_rows
            if _code(item.get("code")) == code
            or (not _code(item.get("code")) and industry and _text(item.get("industry")) == industry)
        ]
        all_evidence = [*company, *industry_rows]
        verified = sum(_text(item.get("evidence_status")).upper() == "VERIFIED" for item in all_evidence)
        partial = sum(_text(item.get("evidence_status")).upper() == "PARTIALLY_VERIFIED" for item in all_evidence)
        failed = sum(_text(item.get("status")).upper() == "FAILED" for item in audits)
        missing_audit = sum(_text(item.get("status")).upper() == "MISSING" for item in audits)
        if verified or partial:
            collection_state = "EVIDENCE_COLLECTED_REQUIRES_EXPLICIT_JUDGEMENT"
        elif failed or missing_audit:
            collection_state = "EVIDENCE_STILL_MISSING_OR_SOURCE_FAILED"
        else:
            collection_state = "EVIDENCE_NOT_OBSERVED"
        missing_items = _tokens(row.get("missing_evidence_items"))
        refs = _evidence_refs(all_evidence)
        packets.append(
            {
                "code": code,
                "stock_name": _text(row.get("stock_name") or row.get("name")),
                "industry": industry,
                "recovery_tier": _text(row.get("evidence_recovery_priority_tier")).upper(),
                "missing_evidence_items": ";".join(missing_items),
                "required_review_tasks": ";".join(evidence_tasks(missing_items)),
                "company_evidence_count": len(company),
                "industry_evidence_count": len(industry_rows),
                "verified_evidence_count": verified,
                "partially_verified_evidence_count": partial,
                "source_failure_count": failed,
                "source_missing_count": missing_audit,
                "evidence_source_refs": ";".join(refs),
                "evidence_collection_state": collection_state,
                "qualitative_judgement_state": "UNRESOLVED",
                "automatic_gate_inference_allowed": False,
                "unknown_evidence_is_pass": False,
                "formal_action_eligible": False,
                "formal_action_recomputed": False,
                "canonical_authority_unchanged": True,
                "automatic_promotion_allowed": False,
                "starter_position_allowed": False,
                "no_auto_trade": True,
                "source_terminal_decision": _text(row.get("terminal_decision")),
                "source_terminal_reason_class": _text(row.get("terminal_reason_class")),
            }
        )
    return packets


def _collect(
    workset: Sequence[Mapping[str, Any]], *, as_of: date, cache_dir: Path, timeout: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from .evidence_collectors import collect_auto_evidence

    return collect_auto_evidence(
        priority_rows=list(workset),
        as_of=as_of,
        cache_dir=cache_dir,
        max_companies=len(workset),
        timeout=timeout,
    )


def run_recovery(
    recovery_csv: Path,
    output_dir: Path,
    *,
    cache_dir: Path,
    as_of: date,
    source_run_id: str = "",
    source_artifact: str = "",
    timeout: int = 12,
) -> tuple[dict[str, Any], bool]:
    workset = normalize_recovery_rows(_read_csv(recovery_csv))
    digest = _stable_digest(workset)
    collector_exception = ""
    try:
        industry_evidence, company_evidence, audit_rows, collector_summary = _collect(
            workset, as_of=as_of, cache_dir=cache_dir, timeout=timeout
        )
    except Exception as exc:  # fail closed, but preserve an audit artifact
        industry_evidence, company_evidence, audit_rows = [], [], []
        collector_summary = {"enabled": True, "executed": False}
        collector_exception = f"{type(exc).__name__}:{exc}"

    packets = build_review_packets(
        workset,
        company_evidence=company_evidence,
        industry_evidence=industry_evidence,
        audit_rows=audit_rows,
    )
    priority_payload = build_priority_payload(workset, source_run_id=source_run_id, workset_digest=digest)
    tier_counts = Counter(_text(row.get("evidence_recovery_priority_tier")).upper() for row in workset)
    collection_counts = Counter(_text(row.get("evidence_collection_state")) for row in packets)
    summary = {
        "contract_version": CONTRACT_VERSION,
        "authority": RESEARCH_AUTHORITY,
        "as_of": as_of.isoformat(),
        "source_near_buy_run_id": source_run_id,
        "source_near_buy_artifact": source_artifact,
        "workset_digest": digest,
        "workset_count": len(workset),
        "tier_counts": {tier: tier_counts.get(tier, 0) for tier in RECOVERY_TIERS},
        "review_packet_count": len(packets),
        "collection_state_counts": dict(sorted(collection_counts.items())),
        "collector_summary": collector_summary,
        "collector_exception": collector_exception,
        "qualitative_judgement_resolved_count": 0,
        "priority_changes_order_only": True,
        "threshold_changes_allowed": False,
        "automatic_gate_inference_allowed": False,
        "unknown_evidence_is_pass": False,
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "canonical_authority_unchanged": True,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "no_auto_trade": True,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "recovery_workset.csv", workset)
    _write_csv(output_dir / "recovered_company_evidence.csv", company_evidence)
    _write_csv(output_dir / "recovered_industry_evidence.csv", industry_evidence)
    _write_csv(output_dir / "recovery_evidence_audit.csv", audit_rows)
    _write_csv(output_dir / "recovery_review_packet.csv", packets)
    (output_dir / "near_buy_research_priority.json").write_text(
        json.dumps(priority_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "recovery_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary, not bool(collector_exception)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--source-artifact", default="")
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args(argv)
    summary, collector_ok = run_recovery(
        args.recovery_csv,
        args.output_dir,
        cache_dir=args.cache_dir,
        as_of=args.as_of,
        source_run_id=args.source_run_id,
        source_artifact=args.source_artifact,
        timeout=args.timeout,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if collector_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
