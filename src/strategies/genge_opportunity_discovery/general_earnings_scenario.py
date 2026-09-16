"""Evidence-derived GENERAL_EARNINGS scenario valuation for GenGe V3.1.

This module closes the numeric scenario gap without weakening the frozen V3.1
selection policy.  It consumes only strict-PIT Round-6 numeric evidence that is
already emitted by :mod:`v311_current_expectation_inputs`.

Policy contract
---------------
* route must be explicitly ``general_reverse_earnings``;
* normalized EPS, ~3Y EPS CAGR, ~3Y revenue CAGR and the frozen realistic
  growth must all be present;
* bear growth removes the Round-6 +5pp revenue allowance and uses the lower of
  observed normalized-EPS and revenue CAGR, clipped to the frozen 0%-30% band;
* base growth is the frozen Round-6 realistic growth and must reconcile to the
  supplied neutral value;
* bull growth is the evidence-backed revenue-support ceiling
  ``revenue CAGR + 5pp``, clipped to the same frozen 0%-30% band;
* extreme stress is the frozen model's explicit 0% starting-growth boundary;
* all scenario values are CURRENT PRESENT VALUES from ``value_expectation_10y``.
  They are never re-labelled as 3Y terminal values.

The builder deliberately does not create terminal multiples, 3Y terminal
values, scenario probabilities, risk-adjusted CAGR, qualitative gate PASSes or
Formal authority.  If those inputs are absent they remain absent/UNKNOWN.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from .v311_current_expectation_inputs import (
    POLICY_SOURCE as ROUND6_POLICY_SOURCE,
    REALISTIC_GROWTH_CAP,
    REVENUE_GROWTH_ALLOWANCE,
    value_expectation_10y,
)


POLICY_SOURCE = "v31_general_earnings_round6_strict_pit_scenarios_v1"
GENERAL_STRATEGY_ID = "general_reverse_earnings"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clip_growth(value: float) -> float:
    return min(max(float(value), 0.0), REALISTIC_GROWTH_CAP)


def _route_is_general(row: Mapping[str, Any]) -> bool:
    return str(row.get("valuation_primary_strategy_id") or "").strip() == GENERAL_STRATEGY_ID


def build_general_earnings_scenario(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return auditable scenario fields, failing closed on any missing lineage."""
    result: dict[str, Any] = {
        "v31_general_scenario_policy_source": POLICY_SOURCE,
        "v31_general_scenario_value_semantics": "CURRENT_PRESENT_VALUE",
        "v31_general_scenario_3y_cagr_status": "TERMINAL_VALUE_EVIDENCE_REQUIRED",
        "v31_general_scenario_risk_adjusted_cagr_status": "SCENARIO_PROBABILITIES_AND_TERMINAL_VALUES_REQUIRED",
        "v31_general_scenario_status": "NOT_READY",
        "v31_general_scenario_error": "",
    }

    if not _route_is_general(row):
        result["v31_general_scenario_error"] = "GENERAL_EARNINGS_ROUTE_UNPROVEN"
        return result

    source = str(row.get("v311_expectation_policy_source") or "").strip()
    if source != ROUND6_POLICY_SOURCE:
        result["v31_general_scenario_error"] = "STRICT_PIT_ROUND6_LINEAGE_UNPROVEN"
        return result

    normalized = _finite(row.get("v31_normalized_profit"))
    eps_growth = _finite(row.get("eps_growth_3y_round6"))
    revenue_growth = _finite(row.get("revenue_growth_3y_round6"))
    realistic = _finite(row.get("v31_realistic_profit_cagr"))
    neutral = _finite(row.get("v31_neutral_value"))
    price = _finite(row.get("v31_current_price"))
    if any(value is None for value in (normalized, eps_growth, revenue_growth, realistic, neutral)):
        result["v31_general_scenario_error"] = "SCENARIO_EVIDENCE_INCOMPLETE"
        return result
    assert normalized is not None and eps_growth is not None and revenue_growth is not None
    assert realistic is not None and neutral is not None
    if normalized <= 0.0 or neutral <= 0.0:
        result["v31_general_scenario_error"] = "SCENARIO_EVIDENCE_NONPOSITIVE"
        return result

    expected_base_growth = _clip_growth(min(eps_growth, revenue_growth + REVENUE_GROWTH_ALLOWANCE))
    if not math.isclose(realistic, expected_base_growth, rel_tol=1e-9, abs_tol=1e-12):
        result["v31_general_scenario_error"] = "ROUND6_REALISTIC_GROWTH_LINEAGE_MISMATCH"
        return result

    bear_growth = _clip_growth(min(eps_growth, revenue_growth))
    bull_growth = _clip_growth(revenue_growth + REVENUE_GROWTH_ALLOWANCE)
    stress_growth = 0.0
    if not (stress_growth <= bear_growth <= realistic <= bull_growth):
        result["v31_general_scenario_error"] = "SCENARIO_GROWTH_ORDER_INVALID"
        return result

    stress_value = value_expectation_10y(normalized, stress_growth)
    bear_value = value_expectation_10y(normalized, bear_growth)
    base_value = value_expectation_10y(normalized, realistic)
    bull_value = value_expectation_10y(normalized, bull_growth)
    values = (stress_value, bear_value, base_value, bull_value)
    if not all(math.isfinite(value) and value > 0.0 for value in values):
        result["v31_general_scenario_error"] = "SCENARIO_VALUE_CALCULATION_FAILED"
        return result
    if not math.isclose(base_value, neutral, rel_tol=1e-9, abs_tol=1e-9):
        result["v31_general_scenario_error"] = "NEUTRAL_VALUE_LINEAGE_MISMATCH"
        return result
    if not (stress_value <= bear_value <= base_value <= bull_value):
        result["v31_general_scenario_error"] = "SCENARIO_VALUE_ORDER_INVALID"
        return result

    result.update(
        {
            "v31_general_scenario_status": "READY",
            "v31_general_scenario_error": "",
            "v31_bear_growth_assumption": bear_growth,
            "v31_base_growth_assumption": realistic,
            "v31_bull_growth_assumption": bull_growth,
            "v31_stress_growth_assumption": stress_growth,
            "v31_bear_growth_source": "min(strict_pit_eps_cagr,strict_pit_revenue_cagr);clip_0_30",
            "v31_base_growth_source": "frozen_round6_realistic_growth",
            "v31_bull_growth_source": "strict_pit_revenue_cagr_plus_frozen_5pp_allowance;clip_0_30",
            "v31_stress_growth_source": "frozen_round6_zero_growth_lower_boundary",
            "v31_pessimistic_value": bear_value,
            "v31_neutral_value": base_value,
            "v31_optimistic_value": bull_value,
            "v31_extreme_stress_value": stress_value,
            "v31_scenario_valuation_ready": True,
        }
    )
    if price is not None and price > 0.0:
        # Signed downside follows the V3.1 research convention requested by the
        # policy: value/current_price - 1.  Positive means the bear value is
        # still above price; negative means fundamental downside.
        result["v31_bear_downside_pct"] = bear_value / price - 1.0
        result["v31_extreme_stress_downside_pct"] = stress_value / price - 1.0
        result["v31_potential_max_fundamental_loss_pct"] = bear_value / price - 1.0
        result["v31_general_scenario_downside_status"] = "READY"
    else:
        result["v31_general_scenario_downside_status"] = "PRICE_EVIDENCE_REQUIRED"
    return result


def enrich_general_earnings_scenarios(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Overlay only evidence-derived numeric scenario fields on production rows."""
    enriched: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        row.update(build_general_earnings_scenario(row))
        enriched.append(row)
    return enriched
