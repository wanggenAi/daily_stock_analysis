"""Multi-engine opportunity admission policy for the risk-capped A-share scan.

The legacy scan historically treated a five-year price percentile <= 35% as a
universal strict gate.  That is appropriate for a valley-repair setup, but it
silently excludes strong-trend pullbacks and genuine earnings inflections.

This module changes only that *opportunity-shape* gate.  Every safety,
financial, valuation, evidence, market, event, price-volume, execution,
reward/risk, plan, price-mapping and exit-history rule remains owned by the
existing strict checker and is preserved unchanged.

No engine creates a quota and no engine can turn a failed hard gate into a
pass.  Explicitly adverse factor evidence blocks engine admission; missing
factor evidence is reported as UNKNOWN rather than fabricated.
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
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "confirmed"}


def factor_validity_status(row: Mapping[str, Any]) -> str:
    """Return VALID/NEUTRAL/INVALID/UNKNOWN without inventing factor evidence.

    An upstream factor-validation job may provide an explicit status.  When it
    instead provides a measured IC and an adequate sample size, a small dead
    band prevents noise around zero from being called a valid/invalid factor.
    With no such evidence we deliberately return UNKNOWN; UNKNOWN never acts as
    positive evidence, but it also does not become a synthetic hard veto.
    """

    explicit = str(
        row.get("factor_validity_status")
        or row.get("factor_effectiveness_status")
        or ""
    ).strip().upper()
    aliases = {
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
    if explicit in aliases:
        return aliases[explicit]

    ic = _safe_float(row.get("factor_ic"))
    samples = int(_safe_float(row.get("factor_ic_sample_count")) or 0)
    if ic is None or samples < FACTOR_IC_MIN_SAMPLES:
        return "UNKNOWN"
    if ic >= FACTOR_IC_MIN_ABS_EFFECT:
        return "VALID"
    if ic <= -FACTOR_IC_MIN_ABS_EFFECT:
        return "INVALID"
    return "NEUTRAL"


def earnings_inflection_confirmed(row: Mapping[str, Any]) -> bool:
    """Require explicit evidence or real profit-growth fields for an inflection.

    ``financial_safety_score`` is intentionally *not* used here.  Debt ratio,
    liquidity and ROE safety are not an earnings inflection.  If normalized
    profit-growth evidence is absent, this engine remains inactive.
    """

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

    # A sign change plus meaningful acceleration is a conservative, auditable
    # definition.  It avoids calling merely "less bad" earnings an inflection.
    return bool(
        current > 0.0
        and previous <= 0.0
        and current - previous >= EARNINGS_INFLECTION_MIN_ACCELERATION_PCT
    )


def evaluate_engine(row: Mapping[str, Any], plan: Mapping[str, Any]) -> EngineEvaluation:
    factor = factor_validity_status(row)
    if factor == "INVALID":
        return EngineEvaluation(False, "NONE", "explicit_factor_evidence_adverse", factor, False)

    percentile = _safe_float(row.get("price_percentile_5y"))
    trend = str(row.get("trend_confirmation_level") or "NONE").upper()
    industry_regime = str(row.get("industry_regime_status") or "UNKNOWN").upper()
    preferred_plan = str(plan.get("preferred_plan") or row.get("preferred_plan") or "").lower()
    earnings = earnings_inflection_confirmed(row)

    # Engine 1: the original low-price logic, now correctly scoped to one setup.
    if percentile is not None and percentile <= 0.35:
        return EngineEvaluation(
            True,
            "VALLEY_REPAIR",
            "five_year_price_percentile_at_or_below_35pct",
            factor,
            earnings,
        )

    # Engine 2: a high-quality trend may be bought on a pullback without also
    # pretending the stock is historically cheap.  Industry STRONG is required
    # because this engine is explicitly regime-dependent.
    if (
        trend == "STRONG"
        and industry_regime == "STRONG"
        and preferred_plan == "pullback"
        and str(plan.get("pullback_status") or "").upper() == "READY"
    ):
        return EngineEvaluation(
            True,
            "STRONG_TREND_PULLBACK",
            "strong_stock_trend_strong_industry_ready_pullback",
            factor,
            earnings,
        )

    # Engine 3: earnings evidence may justify an opportunity above the historic
    # low-price band, but it still has to pass every legacy universal strict gate
    # (including financial safety, trend/MA, evidence, event, RR and execution).
    if earnings and industry_regime in {"STRONG", "NEUTRAL"}:
        return EngineEvaluation(
            True,
            "EARNINGS_INFLECTION",
            "verified_profit_growth_inflection",
            factor,
            earnings,
        )

    missing: list[str] = []
    if percentile is None or percentile > 0.35:
        missing.append("not_valley_repair")
    if not (
        trend == "STRONG"
        and industry_regime == "STRONG"
        and preferred_plan == "pullback"
        and str(plan.get("pullback_status") or "").upper() == "READY"
    ):
        missing.append("not_strong_trend_pullback")
    if not earnings:
        missing.append("no_verified_earnings_inflection")
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

    # The old price gate remains available as raw data in the candidate row, but
    # must no longer participate in the global AND across all strict gates.
    checks.pop(LEGACY_UNIVERSAL_PRICE_GATE, None)
    checks[ENGINE_GATE] = evaluation.eligible

    # Production rows are mutable dicts.  Add diagnostics without making tests or
    # callers that provide read-only Mapping objects depend on mutation.
    if isinstance(row, MutableMapping):
        row["opportunity_engine"] = evaluation.engine
        row["opportunity_engine_eligible"] = evaluation.eligible
        row["opportunity_engine_reason"] = evaluation.reason
        row["factor_validity_status"] = evaluation.factor_validity_status
        row["earnings_inflection_confirmed"] = evaluation.earnings_inflection_confirmed

    return checks


def install() -> None:
    """Install the opportunity-shape policy; safe to call repeatedly."""

    if core.strict_candidate_checks is strict_candidate_checks:
        return
    core.strict_candidate_checks = strict_candidate_checks
