"""Prioritize near-ready research candidates without changing eligibility.

This report is deliberately advisory to the research pipeline only.  It never
changes classification, never creates a formal signal, and never bypasses a
strict gate.  Its purpose is to make recoverable data/setup gaps visible early
so the next production scan can re-evaluate them under the unchanged policy.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Iterable, Mapping


RELAXABLE_EXIT_GATES = frozenset({
    "exit_profile_passed",
    "exit_profile_sample_count",
    "exit_profile_recent_2y_samples",
    "exit_profile_confidence",
    "exit_profile_freshness",
    "exit_profile_rule_version",
    "exit_profile_data_traceable",
    "exit_profile_entry_mode_match",
    "exit_profile_validation_scope",
})

DATA_RECOVERY_GATES = frozenset({"event_risk_known"})

MARKET_SETUP_GATES = frozenset({
    "price_volume_not_distribution",
    "trend_medium",
    "above_ma60",
    "ma60_not_down",
    "ready_plan",
    "real_rr_1_8",
    "market_regime_not_red",
    "industry_regime_available",
    "industry_regime_not_crisis",
    "price_percentile_le_35",
})

RESEARCH_EVIDENCE_GATES = frozenset({
    "industry_evidence",
    "company_evidence",
    "strict_official_evidence",
    "hard_logic_medium",
})

HARD_BLOCK_GATES = frozenset({
    "event_risk_not_high",
    "no_hard_risk",
    "financial_passed",
    "valuation_not_failed",
    "execution_not_high",
    "value_trap_not_high",
    "price_mapping_ok",
    "quant_research_queue",
    "not_falling_knife",
})

RECOVERY_COLUMNS = [
    "recovery_rank",
    "recovery_class",
    "code",
    "stock_name",
    "actionability_score",
    "user_visible_level",
    "non_exit_blocker_count",
    "non_exit_blockers",
    "exit_profile_status",
    "stock_negative_veto_clear",
    "stock_hard_veto_outcome_count",
    "next_research_action",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _failed_gates(row: Mapping[str, Any]) -> set[str]:
    text = str(row.get("failed_gates") or row.get("strict_gate_failed") or "")
    return {item.strip() for item in text.split(";") if item.strip()}


def _profile_is_recoverable(row: Mapping[str, Any]) -> bool:
    status = str(row.get("exit_profile_status") or "NOT_AVAILABLE").upper()
    hard_veto = int(_float_value(row.get("stock_hard_veto_outcome_count")))
    if status == "FAILED" or hard_veto > 0:
        return False
    if status == "DEGRADED" and not _bool_value(row.get("stock_negative_veto_clear")):
        return False
    return status in {"PASSED", "NOT_AVAILABLE", "DEGRADED"}


def _next_action(recovery_class: str, blockers: set[str]) -> str:
    actions: list[str] = []
    if "event_risk_known" in blockers:
        actions.append("complete_official_material_event_scan_then_require_event_scan_OK")
    if blockers & {"price_volume_not_distribution"}:
        actions.append("wait_for_non_distribution_price_volume_state_and_rerun")
    if blockers & {"trend_medium", "above_ma60", "ma60_not_down", "price_percentile_le_35"}:
        actions.append("wait_for_next_daily_bar_to_pass_price_trend_gates")
    if blockers & {"ready_plan", "real_rr_1_8"}:
        actions.append("rebuild_price_plan_then_require_ready_plan_and_real_rr_ge_1_8")
    if blockers & {"market_regime_not_red", "industry_regime_available", "industry_regime_not_crisis"}:
        actions.append("wait_for_market_or_industry_regime_gate_to_recover")
    if blockers & RESEARCH_EVIDENCE_GATES:
        actions.append("complete_official_industry_company_evidence_and_recheck_hard_logic")
    return ";".join(actions) or f"recheck_{recovery_class.lower()}_gates"


def classify_recovery_candidate(row: Mapping[str, Any]) -> tuple[str, set[str]] | None:
    """Return a research-priority class only when every blocker is recoverable.

    Exit-history uncertainty is ignored only for prioritization because the
    production risk-capped policy already owns that decision.  Explicit exit
    negatives and every hard non-exit blocker remain excluded from this report.
    """

    failed = _failed_gates(row)
    non_exit = failed - RELAXABLE_EXIT_GATES

    if not _profile_is_recoverable(row):
        return None
    if non_exit & HARD_BLOCK_GATES:
        return None
    if not non_exit:
        return None
    if non_exit <= DATA_RECOVERY_GATES:
        return "DATA_RECOVERY_NOW", non_exit
    if non_exit <= MARKET_SETUP_GATES:
        return "MARKET_TRIGGER_WATCH", non_exit
    if non_exit <= (DATA_RECOVERY_GATES | MARKET_SETUP_GATES | RESEARCH_EVIDENCE_GATES):
        return "RESEARCH_OR_TRIGGER_WATCH", non_exit
    return None


def build_recovery_rows(
    audit_rows: Iterable[Mapping[str, Any]],
    deep_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deep_by_code = {
        str(row.get("code") or "").zfill(6): dict(row)
        for row in deep_rows
        if str(row.get("code") or "").strip()
    }
    result: list[dict[str, Any]] = []
    class_priority = {
        "DATA_RECOVERY_NOW": 0,
        "MARKET_TRIGGER_WATCH": 1,
        "RESEARCH_OR_TRIGGER_WATCH": 2,
    }

    for audit in audit_rows:
        code = str(audit.get("code") or "").zfill(6)
        source = {**deep_by_code.get(code, {}), **dict(audit), "code": code}
        classified = classify_recovery_candidate(source)
        if classified is None:
            continue
        recovery_class, blockers = classified
        result.append({
            "recovery_rank": 0,
            "recovery_class": recovery_class,
            "code": code,
            "stock_name": source.get("stock_name") or "",
            "actionability_score": source.get("actionability_score") or "",
            "user_visible_level": source.get("user_visible_level") or "",
            "non_exit_blocker_count": len(blockers),
            "non_exit_blockers": ";".join(sorted(blockers)),
            "exit_profile_status": source.get("exit_profile_status") or "",
            "stock_negative_veto_clear": source.get("stock_negative_veto_clear") or "",
            "stock_hard_veto_outcome_count": source.get("stock_hard_veto_outcome_count") or 0,
            "next_research_action": _next_action(recovery_class, blockers),
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "_class_priority": class_priority[recovery_class],
            "_score": _float_value(source.get("actionability_score")),
        })

    result.sort(
        key=lambda row: (
            row["_class_priority"],
            int(row["non_exit_blocker_count"]),
            -float(row["_score"]),
            str(row["code"]),
        )
    )
    for rank, row in enumerate(result, 1):
        row["recovery_rank"] = rank
        row.pop("_class_priority", None)
        row.pop("_score", None)
    return result


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RECOVERY_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in RECOVERY_COLUMNS} for row in rows)


def _write_markdown(path: Path, rows: list[Mapping[str, Any]]) -> None:
    lines = [
        "# Candidate Recovery Report",
        "",
        "This report never grants formal eligibility and never bypasses a strict gate.",
        "Candidates remain non-formal until a later production scan passes every required gate.",
        "",
    ]
    if not rows:
        lines.append("No recoverable near-ready candidates in the current deep-review set.")
    else:
        for row in rows:
            lines.extend([
                f"## {row['recovery_rank']}. {row['code']} {row['stock_name']}",
                f"- class: {row['recovery_class']}",
                f"- blockers: {row['non_exit_blockers']}",
                f"- next action: {row['next_research_action']}",
                "- formal signal eligible: False",
                "- automatic promotion allowed: False",
                "",
            ])
    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_report_dir(path: Path | None) -> Path:
    if path is not None:
        return path
    root = Path("reports/all_a_full_scan")
    candidates = sorted(
        item for item in root.iterdir()
        if item.is_dir() and (item / "strict_gate_audit.csv").exists()
    ) if root.exists() else []
    if not candidates:
        raise RuntimeError("no all-A report with strict_gate_audit.csv found")
    return candidates[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(argv)
    report_dir = resolve_report_dir(args.report_dir)
    audit_rows = _read_csv(report_dir / "strict_gate_audit.csv")
    deep_rows = _read_csv(report_dir / "top30_deep_review.csv")
    rows = build_recovery_rows(audit_rows, deep_rows)
    _write_csv(report_dir / "candidate_recovery_queue.csv", rows)
    _write_markdown(report_dir / "candidate_recovery_queue.md", rows)
    print(f"candidate_recovery_report={report_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
