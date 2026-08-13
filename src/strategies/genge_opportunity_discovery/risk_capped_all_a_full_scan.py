"""Risk-capped production entry policy for the unified all-A scan.

The strict research path is intentionally kept intact as a control.  This
module changes only one production decision: an exit profile that is missing
because the historical sample is insufficient is treated as uncertainty that
reduces position size, not as proof that the entry is unsafe.

Hard market, event, trend, execution, valuation, evidence, price-plan and
price-mapping gates still have to pass.  An explicitly FAILED exit profile is
never relaxed.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core


# Only these strict gates are allowed to be uncertain on a risk-capped formal
# entry.  Every non-exit strict gate must still pass.
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

# Missing history is uncertainty, not negative evidence.  Degraded history is
# allowed only when the profile explicitly says its negative-veto checks are
# clear, and therefore receives a smaller cap.
RISK_CAPPED_PROFILE_MULTIPLIERS = {
    "NOT_AVAILABLE": 0.25,
    "DEGRADED": 0.15,
}

_ORIGINAL_CLASSIFY_CANDIDATE = core.classify_candidate
_ORIGINAL_APPLY_POSITION_BUDGET = core._apply_position_budget


def failed_strict_gates(
    row: Mapping[str, Any],
    plan: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    board_rule: core.BoardRule,
) -> set[str]:
    checks = core.strict_candidate_checks(row, plan, profile, board_rule=board_rule)
    return {name for name, passed in checks.items() if not passed}


def risk_capped_profile_multiplier(profile: Mapping[str, Any]) -> float:
    """Return the maximum profile multiplier allowed by the fallback policy."""

    status = str(profile.get("exit_profile_status") or "NOT_AVAILABLE").upper()
    multiplier = RISK_CAPPED_PROFILE_MULTIPLIERS.get(status, 0.0)
    if multiplier <= 0:
        return 0.0

    # A historical hard veto is negative evidence and must never be converted
    # into a smaller position.  FAILED is also excluded by the lookup above.
    hard_veto_count = int(core._safe_float(profile.get("stock_hard_veto_outcome_count")) or 0)
    if hard_veto_count > 0:
        return 0.0

    if status == "DEGRADED" and not bool(profile.get("stock_negative_veto_clear")):
        return 0.0

    return multiplier


def risk_capped_eligible(
    row: Mapping[str, Any],
    plan: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    board_rule: core.BoardRule,
) -> bool:
    """Allow a formal entry only when *all* failures are exit-history uncertainty."""

    failed = failed_strict_gates(row, plan, profile, board_rule=board_rule)
    if not failed or not failed.issubset(RELAXABLE_EXIT_GATES):
        return False

    status = str(profile.get("exit_profile_status") or "NOT_AVAILABLE").upper()
    if status == "FAILED":
        return False

    return risk_capped_profile_multiplier(profile) > 0.0


def classify_candidate(
    row: Mapping[str, Any],
    plan: Mapping[str, Any],
    profile: Mapping[str, Any],
    evidence_urls: list[str],
    *,
    board_rule: core.BoardRule,
) -> tuple[str, list[str]]:
    """Promote exit-history-only misses to formal review with a capped position."""

    checks = core.strict_candidate_checks(row, plan, profile, board_rule=board_rule)
    if all(checks.values()):
        return "STRICT_REVIEW_READY", []

    if risk_capped_eligible(row, plan, profile, board_rule=board_rule):
        missing = sorted(name for name, passed in checks.items() if not passed)
        return "STRICT_REVIEW_READY", missing

    return _ORIGINAL_CLASSIFY_CANDIDATE(
        row, plan, profile, evidence_urls, board_rule=board_rule,
    )


def _row_is_risk_capped(row: Mapping[str, Any]) -> bool:
    failed = {
        name for name in str(row.get("strict_gate_failed") or "").split(";") if name
    }
    if not failed or not failed.issubset(RELAXABLE_EXIT_GATES):
        return False
    status = str(row.get("exit_profile_status") or "NOT_AVAILABLE").upper()
    profile_like = {
        "exit_profile_status": status,
        "stock_hard_veto_outcome_count": row.get("stock_hard_veto_outcome_count"),
        "stock_negative_veto_clear": row.get("stock_negative_veto_clear"),
    }
    return risk_capped_profile_multiplier(profile_like) > 0.0


def apply_position_budget(
    row: dict[str, Any], plan: Mapping[str, Any], level: str,
) -> None:
    """Reuse the validated sizing engine after applying the fallback cap."""

    if level == "STRICT_REVIEW_READY" and _row_is_risk_capped(row):
        status = str(row.get("exit_profile_status") or "NOT_AVAILABLE").upper()
        fallback_multiplier = risk_capped_profile_multiplier({
            "exit_profile_status": status,
            "stock_hard_veto_outcome_count": row.get("stock_hard_veto_outcome_count"),
            "stock_negative_veto_clear": row.get("stock_negative_veto_clear"),
        })
        existing = core._safe_float(row.get("profile_position_multiplier"))
        effective = fallback_multiplier if existing is None or existing <= 0 else min(existing, fallback_multiplier)
        row["profile_position_multiplier"] = effective
        row["profile_validation_scope"] = f"RISK_CAPPED_{status}_EXIT_HISTORY"
        blocker = str(row.get("exit_profile_blocker_detail") or "")
        row["exit_profile_blocker_detail"] = (
            f"risk_capped_multiplier={effective};" + blocker
        )

    _ORIGINAL_APPLY_POSITION_BUDGET(row, plan, level)


def install_policy() -> None:
    """Install the production policy into the already-tested all-A engine."""

    core.classify_candidate = classify_candidate
    core._apply_position_budget = apply_position_budget


def main(argv: list[str] | None = None) -> int:
    install_policy()
    return core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
