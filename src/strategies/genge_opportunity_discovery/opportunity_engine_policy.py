"""Multi-engine opportunity admission policy for the risk-capped A-share scan.

The legacy scan historically treated a five-year price percentile <= 35% as a
universal strict gate. That is appropriate for a valley-repair setup, but it
silently excludes strong-trend pullbacks and genuine earnings inflections.

This module changes only that opportunity-shape gate. Every safety, financial,
valuation, evidence, market, event, price-volume, execution, reward/risk, plan,
price-mapping and exit-history rule remains owned by the existing strict checker
and is preserved unchanged.

No engine creates a quota and no engine can turn a failed hard gate into a pass.
Factor evidence is engine-specific: negative momentum evidence must not veto a
separate valley setup, and vice versa. Missing factor history remains UNKNOWN.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core


LEGACY_UNIVERSAL_PRICE_GATE = "price_percentile_le_35"
ENGINE_GATE = "opportunity_engine_eligible"

FACTOR_IC_MIN_ABS_EFFECT = 0.02
FACTOR_IC_MIN_SAMPLES = 20
EARNINGS_INFLECTION_MIN_ACCELERATION_PCT = 10.0

_ORIGINAL_STRICT_CANDIDATE_CHECKS = core.strict_candidate_checks

_ENGINE_FACTOR_PREFIX = {
    "VALLEY_REPAIR": "valley",
    "STRONG_TREND_PULLBACK": "trend",
    "EARNINGS_INFLECTION": "earnings",
}
_FACTOR_STATUS_ALIASES = {
    "PASSED": "VALID",
    "VALID": "VALID",
    "POSITIVE": "VALID",
    "NEUTRAL": "NEUTRAL",
    "WEAK": "NEUTRAL",
    "FAILED": "INVALID",
    "INVALID": "INVALID",
    "NEGATIVE": "INVALID",
    "UNKNOWN": "UNKNOWN",
    "NOT_AVAILABLE": "UNKNOWN",
}


@dataclass(frozen=True)
class EngineEvaluation:
    eligible: bool
    engine: str
    reason: str
    factor_validity_status: str
    earnings_inflection_confirmed: bool


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip().lower() in {"", "nan", "none"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {
        "1", "true", "yes", "y", "passed", "confirmed",
    }


def _normalize_factor_status(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return _FACTOR_STATUS_ALIASES.get(text)


def factor_validity_status(row: Mapping[str, Any]) -> str:
    """Return generic VALID/NEUTRAL/INVALID/UNKNOWN without inventing evidence.

    This compatibility path consumes an explicit generic status or measured IC.
    The production multi-engine path prefers ``factor_validity_for_engine`` so a
    factor that is adverse to one setup does not veto unrelated opportunity
    shapes.
    """

    explicit = _normalize_factor_status(
        row.get("factor_validity_status")
        or row.get("factor_effectiveness_status")
    )
    if explicit is not None:
        return explicit

    ic = _safe_float(row.get("factor_ic"))
    samples = int(_safe_float(row.get("factor_ic_sample_count")) or 0)
    if ic is None or samples < FACTOR_IC_MIN_SAMPLES:
        return "UNKNOWN"
    if ic >= FACTOR_IC_MIN_ABS_EFFECT:
        return "VALID"
    if ic <= -FACTOR_IC_MIN_ABS_EFFECT:
        return "INVALID"
    return "NEUTRAL"


def factor_validity_for_engine(row: Mapping[str, Any], engine: str) -> str:
    """Return factor evidence only for the requested opportunity engine."""

    prefix = _ENGINE_FACTOR_PREFIX.get(str(engine).upper())
    if prefix:
        explicit = _normalize_factor_status(
            row.get(f"{prefix}_factor_validity_status")
        )
        if explicit is not None:
            return explicit
        ic = _safe_float(row.get(f"{prefix}_factor_ic"))
        samples = int(
            _safe_float(row.get(f"{prefix}_factor_ic_sample_count")) or 0
        )
        if ic is not None and samples >= FACTOR_IC_MIN_SAMPLES:
            if ic >= FACTOR_IC_MIN_ABS_EFFECT:
                return "VALID"
            if ic <= -FACTOR_IC_MIN_ABS_EFFECT:
                return "INVALID"
            return "NEUTRAL"
    return factor_validity_status(row)


def _factor_metrics_for_engine(
    row: Mapping[str, Any], engine: str,
) -> tuple[float | None, int]:
    prefix = _ENGINE_FACTOR_PREFIX.get(str(engine).upper())
    if prefix:
        ic = _safe_float(row.get(f"{prefix}_factor_ic"))
        samples = int(
            _safe_float(row.get(f"{prefix}_factor_ic_sample_count")) or 0
        )
        if ic is not None or samples:
            return ic, samples
    return (
        _safe_float(row.get("factor_ic")),
        int(_safe_float(row.get("factor_ic_sample_count")) or 0),
    )


def earnings_inflection_confirmed(row: Mapping[str, Any]) -> bool:
    """Require explicit evidence or real profit-growth fields for an inflection."""

    explicit = row.get("earnings_inflection_confirmed")
    if explicit not in {None, ""}:
        return _bool_value(explicit)

    current = next(
        (
            value for value in (
                _safe_float(row.get("net_profit_yoy")),
                _safe_float(row.get("net_profit_growth_yoy")),
                _safe_float(row.get("profit_yoy_pct")),
            )
            if value is not None
        ),
        None,
    )
    previous = next(
        (
            value for value in (
                _safe_float(row.get("previous_net_profit_yoy")),
                _safe_float(row.get("net_profit_yoy_prev")),
                _safe_float(row.get("previous_net_profit_growth_yoy")),
            )
            if value is not None
        ),
        None,
    )
    if current is None or previous is None:
        return False
    return bool(
        current > 0.0
        and previous <= 0.0
        and current - previous >= EARNINGS_INFLECTION_MIN_ACCELERATION_PCT
    )


def _shape_flags(
    row: Mapping[str, Any], plan: Mapping[str, Any],
) -> tuple[bool, bool, bool, bool]:
    percentile = _safe_float(row.get("price_percentile_5y"))
    trend = str(row.get("trend_confirmation_level") or "NONE").upper()
    industry_regime = str(
        row.get("industry_regime_status") or "UNKNOWN"
    ).upper()
    preferred_plan = str(
        plan.get("preferred_plan") or row.get("preferred_plan") or ""
    ).lower()
    earnings = earnings_inflection_confirmed(row)
    valley = percentile is not None and percentile <= 0.35
    trend_pullback = bool(
        trend == "STRONG"
        and industry_regime == "STRONG"
        and preferred_plan == "pullback"
        and str(plan.get("pullback_status") or "").upper() == "READY"
    )
    earnings_shape = bool(
        earnings and industry_regime in {"STRONG", "NEUTRAL"}
    )
    return valley, trend_pullback, earnings_shape, earnings


def evaluate_engine(row: Mapping[str, Any], plan: Mapping[str, Any]) -> EngineEvaluation:
    valley, trend_pullback, earnings_shape, earnings = _shape_flags(row, plan)
    rejected_by_factor: list[str] = []

    if valley:
        factor = factor_validity_for_engine(row, "VALLEY_REPAIR")
        if factor != "INVALID":
            return EngineEvaluation(
                True,
                "VALLEY_REPAIR",
                "five_year_price_percentile_at_or_below_35pct",
                factor,
                earnings,
            )
        rejected_by_factor.append("valley_factor_evidence_adverse")

    if trend_pullback:
        factor = factor_validity_for_engine(row, "STRONG_TREND_PULLBACK")
        if factor != "INVALID":
            return EngineEvaluation(
                True,
                "STRONG_TREND_PULLBACK",
                "strong_stock_trend_strong_industry_ready_pullback",
                factor,
                earnings,
            )
        rejected_by_factor.append("trend_factor_evidence_adverse")

    if earnings_shape:
        factor = factor_validity_for_engine(row, "EARNINGS_INFLECTION")
        if factor != "INVALID":
            return EngineEvaluation(
                True,
                "EARNINGS_INFLECTION",
                "verified_profit_growth_inflection",
                factor,
                earnings,
            )
        rejected_by_factor.append("earnings_factor_evidence_adverse")

    missing: list[str] = []
    if not valley:
        missing.append("not_valley_repair")
    if not trend_pullback:
        missing.append("not_strong_trend_pullback")
    if not earnings_shape:
        missing.append("no_verified_earnings_inflection")
    missing.extend(rejected_by_factor)
    factor = "INVALID" if rejected_by_factor else factor_validity_status(row)
    return EngineEvaluation(False, "NONE", ";".join(missing), factor, earnings)


def strict_candidate_checks(
    row: Mapping[str, Any],
    plan: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    board_rule: core.BoardRule,
) -> dict[str, bool]:
    """Replace only the universal low-percentile gate with engine admission."""

    checks = dict(
        _ORIGINAL_STRICT_CANDIDATE_CHECKS(
            row, plan, profile, board_rule=board_rule,
        )
    )
    evaluation = evaluate_engine(row, plan)
    checks.pop(LEGACY_UNIVERSAL_PRICE_GATE, None)
    checks[ENGINE_GATE] = evaluation.eligible

    if isinstance(row, MutableMapping):
        row["opportunity_engine"] = evaluation.engine
        row["opportunity_engine_eligible"] = evaluation.eligible
        row["opportunity_engine_reason"] = evaluation.reason
        row["factor_validity_status"] = evaluation.factor_validity_status
        row["earnings_inflection_confirmed"] = evaluation.earnings_inflection_confirmed
        ic, samples = _factor_metrics_for_engine(row, evaluation.engine)
        row["factor_ic"] = ic
        row["factor_ic_sample_count"] = samples
    return checks


def install() -> None:
    """Install the opportunity-shape policy; safe to call repeatedly."""

    if core.strict_candidate_checks is strict_candidate_checks:
        return
    core.strict_candidate_checks = strict_candidate_checks
