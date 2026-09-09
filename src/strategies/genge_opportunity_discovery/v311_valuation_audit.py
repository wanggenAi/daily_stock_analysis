"""Auditable semantics for the V3.1.1 strict-PIT valuation anchor.

The Round-6 strict-PIT extractor produces a single ten-year earning-power value
from normalized clean EPS and a bounded growth estimate.  Historically that
single point was transported through the legacy ``v31_neutral_value`` field and
therefore inherited the semantic authority of a calibrated Base/Neutral value.

This module makes the distinction explicit.  It does not change the frozen
Round-6 arithmetic or the V3.1 sell ladder.  Instead it exposes the complete
chain and fail-closes *valuation-driven* BUY/SELL authority when a fresh
strict-PIT single point has not been explicitly validated as a Base value.
Hard-logic EXIT remains independent of this guard.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

ROUND6_POLICY_SOURCE = "round6_expectation_gap_10y_strict_pit_frozen"
STRICT_EPS_METHOD = "STRICT_PIT_NORMALIZED_CLEAN_EPS_ROUND6"
ROUND6_DISCOUNT_RATE = 0.10
ROUND6_TERMINAL_GROWTH = 0.03
ROUND6_HORIZON_YEARS = 10
ROUND6_REVENUE_GROWTH_ALLOWANCE = 0.05
ROUND6_REALISTIC_GROWTH_CAP = 0.30
ROUND6_TERMINAL_MULTIPLE = 1.0 / (ROUND6_DISCOUNT_RATE - ROUND6_TERMINAL_GROWTH)

VALIDATED_BASE = "VALIDATED_BASE"
UNCALIBRATED_SINGLE_POINT = "UNCALIBRATED_SINGLE_POINT"
LEGACY_UNSPECIFIED = "LEGACY_UNSPECIFIED"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def neutral_value_semantic_status(data: Mapping[str, Any]) -> str:
    """Classify whether ``neutral_value`` is a validated Base or a model point.

    An explicit status is authoritative.  Otherwise fresh Round-6 strict-PIT
    inputs are classified as an uncalibrated single point because that extractor
    does not construct Bear/Base/Bull scenarios.  Legacy rows remain visible but
    are not retroactively reinterpreted.
    """
    explicit = _text(data.get("v311_neutral_value_semantic_status")).upper()
    if explicit:
        return explicit
    policy = _text(data.get("v311_expectation_policy_source"))
    method = _text(data.get("v31_normalized_profit_method")).upper()
    if policy == ROUND6_POLICY_SOURCE or method == STRICT_EPS_METHOD:
        return UNCALIBRATED_SINGLE_POINT
    return LEGACY_UNSPECIFIED


def growth_binding_constraint(data: Mapping[str, Any]) -> str:
    """Explain which Round-6 growth input binds the realistic-growth estimate."""
    eps_growth = _finite(data.get("eps_growth_3y_round6"))
    revenue_growth = _finite(data.get("revenue_growth_3y_round6"))
    if eps_growth is None or revenue_growth is None:
        return "INPUT_INCOMPLETE"
    revenue_supported = revenue_growth + ROUND6_REVENUE_GROWTH_ALLOWANCE
    supportable = min(eps_growth, revenue_supported)
    if supportable <= 0.0:
        return "LOWER_BOUND_0"
    if supportable >= ROUND6_REALISTIC_GROWTH_CAP:
        return "UPPER_CAP_30"
    if eps_growth <= revenue_supported:
        return "EPS_CAGR"
    return "REVENUE_CAGR_PLUS_5PP"


def mechanical_valuation_action(price_to_neutral: float | None) -> str:
    """Mirror the frozen V3.1 valuation ladder for audit only."""
    ratio = _finite(price_to_neutral)
    if ratio is None or ratio <= 0.0:
        return "HOLD_REVIEW"
    if ratio >= 1.70:
        return "CORE_ONLY"
    if ratio >= 1.40:
        return "REDUCE_50"
    if ratio >= 1.20:
        return "REDUCE_25"
    if ratio >= 1.00:
        return "HOLD_NO_ADD"
    return "HOLD"


def build_valuation_audit(
    data: Mapping[str, Any],
    *,
    current_price: float | None,
    neutral_value: float | None,
    normalized_earnings: float | None,
    realistic_growth: float | None,
    price_to_neutral: float | None,
) -> dict[str, Any]:
    """Return production-persistable lineage for the valuation decision chain."""
    semantic_status = neutral_value_semantic_status(data)
    fresh_status = _text(data.get("v311_expectation_input_status")).upper()
    strict_round6 = bool(
        _text(data.get("v311_expectation_policy_source")) == ROUND6_POLICY_SOURCE
        or _text(data.get("v31_normalized_profit_method")).upper() == STRICT_EPS_METHOD
    )
    # Only fresh strict-PIT rows acquire the new semantic guard.  Historical
    # rows without fresh-input provenance keep legacy behaviour for replay
    # compatibility; they are labelled rather than silently reclassified.
    guard_required = bool(
        fresh_status == "READY"
        and strict_round6
        and semantic_status != VALIDATED_BASE
    )

    normalized = _finite(normalized_earnings)
    neutral = _finite(neutral_value)
    effective_pe = (
        neutral / normalized
        if neutral is not None and neutral > 0.0 and normalized is not None and normalized > 0.0
        else None
    )
    role = {
        VALIDATED_BASE: "VALIDATED_BASE_VALUE",
        UNCALIBRATED_SINGLE_POINT: "ROUND6_EARNING_POWER_SINGLE_POINT",
    }.get(semantic_status, "LEGACY_UNSPECIFIED_VALUE")

    eps_growth = _finite(data.get("eps_growth_3y_round6"))
    revenue_growth = _finite(data.get("revenue_growth_3y_round6"))
    mechanical_action = mechanical_valuation_action(price_to_neutral)

    return {
        "v311_valuation_audit_version": "GEN_GE_V311_VALUATION_SEMANTICS_AUDIT_V1",
        "v311_normalized_earnings_semantics": (
            "EPS_PER_SHARE" if strict_round6 else "LEGACY_UNSPECIFIED"
        ),
        "v311_normalized_eps": normalized if strict_round6 else None,
        "v311_normalized_profit_legacy_alias": strict_round6,
        "v311_eps_growth_3y": eps_growth,
        "v311_revenue_growth_3y": revenue_growth,
        "v311_growth_binding_constraint": growth_binding_constraint(data),
        "v311_growth_rule": "clip(min(EPS_CAGR,REVENUE_CAGR_PLUS_5PP),0,30%)",
        "v311_realistic_growth_used": _finite(realistic_growth),
        "v311_discount_rate": ROUND6_DISCOUNT_RATE if strict_round6 else None,
        "v311_terminal_growth": ROUND6_TERMINAL_GROWTH if strict_round6 else None,
        "v311_horizon_years": ROUND6_HORIZON_YEARS if strict_round6 else None,
        "v311_terminal_multiple": ROUND6_TERMINAL_MULTIPLE if strict_round6 else None,
        "v311_raw_earning_power_value": neutral if strict_round6 else None,
        "v311_effective_pe": effective_pe if strict_round6 else None,
        "v311_fair_pe_is_explicit_input": False if strict_round6 else None,
        "v311_neutral_value_semantic_status": semantic_status,
        "v311_neutral_value_role": role,
        "v311_neutral_value_scenario_calibrated": semantic_status == VALIDATED_BASE,
        "v311_neutral_value_semantic_guard_required": guard_required,
        "v311_current_price_audit": _finite(current_price),
        "v311_price_to_model_point": _finite(price_to_neutral),
        "v311_mechanical_valuation_action": mechanical_action,
        "v311_formal_valuation_action_authorized": not guard_required,
        "v311_formal_valuation_authority_reason": (
            "VALIDATED_BASE_SEMANTICS"
            if semantic_status == VALIDATED_BASE
            else (
                "ROUND6_SINGLE_POINT_NOT_VALIDATED_AS_BASE"
                if guard_required
                else "LEGACY_COMPATIBILITY_NO_FRESH_SEMANTIC_GUARD"
            )
        ),
    }
