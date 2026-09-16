from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.general_earnings_scenario import (
    POLICY_SOURCE,
    build_general_earnings_scenario,
)
from src.strategies.genge_opportunity_discovery.selection_framework_v31 import assess_v31
from src.strategies.genge_opportunity_discovery.v311_current_expectation_inputs import (
    POLICY_SOURCE as ROUND6_POLICY_SOURCE,
    current_inputs_from_panel,
    value_expectation_10y,
)


def _row(**overrides):
    normalized = 2.0
    realistic = 0.10
    row = {
        "code": "000001",
        "valuation_primary_strategy_id": "general_reverse_earnings",
        "v311_expectation_policy_source": ROUND6_POLICY_SOURCE,
        "v31_normalized_profit": normalized,
        "v31_normalized_profit_method": "STRICT_PIT_NORMALIZED_CLEAN_EPS_ROUND6",
        "eps_growth_3y_round6": 0.10,
        "revenue_growth_3y_round6": 0.08,
        "v31_realistic_profit_cagr": realistic,
        "v31_neutral_value": value_expectation_10y(normalized, realistic),
        "v31_current_price": 20.0,
    }
    row.update(overrides)
    return row


def test_complete_evidence_builds_ordered_current_pv_scenarios():
    result = build_general_earnings_scenario(_row())

    assert result["v31_general_scenario_status"] == "READY"
    assert result["v31_scenario_valuation_ready"] is True
    assert result["v31_general_scenario_policy_source"] == POLICY_SOURCE
    assert result["v31_general_scenario_value_semantics"] == "CURRENT_PRESENT_VALUE"
    assert result["v31_stress_growth_assumption"] == 0.0
    assert result["v31_bear_growth_assumption"] == 0.08
    assert result["v31_base_growth_assumption"] == 0.10
    assert result["v31_bull_growth_assumption"] == 0.13
    assert (
        result["v31_extreme_stress_value"]
        <= result["v31_pessimistic_value"]
        <= result["v31_neutral_value"]
        <= result["v31_optimistic_value"]
    )
    assert result["v31_potential_max_fundamental_loss_pct"] == (
        result["v31_pessimistic_value"] / 20.0 - 1.0
    )


def test_missing_bear_evidence_keeps_scenario_not_ready():
    result = build_general_earnings_scenario(_row(eps_growth_3y_round6=None))
    assert result["v31_general_scenario_status"] == "NOT_READY"
    assert result["v31_general_scenario_error"] == "SCENARIO_EVIDENCE_INCOMPLETE"
    assert "v31_scenario_valuation_ready" not in result


def test_missing_bull_evidence_keeps_scenario_not_ready():
    result = build_general_earnings_scenario(_row(revenue_growth_3y_round6=None))
    assert result["v31_general_scenario_status"] == "NOT_READY"
    assert result["v31_general_scenario_error"] == "SCENARIO_EVIDENCE_INCOMPLETE"
    assert "v31_optimistic_value" not in result


def test_builder_does_not_supply_arbitrary_defaults_or_cross_model_routes():
    result = build_general_earnings_scenario(
        _row(valuation_primary_strategy_id="insurance_embedded_value")
    )
    assert result["v31_general_scenario_error"] == "GENERAL_EARNINGS_ROUTE_UNPROVEN"
    assert "v31_pessimistic_value" not in result
    assert "v31_optimistic_value" not in result


def test_round6_lineage_must_reconcile_exactly():
    result = build_general_earnings_scenario(_row(v31_realistic_profit_cagr=0.20))
    assert result["v31_general_scenario_status"] == "NOT_READY"
    assert result["v31_general_scenario_error"] == "ROUND6_REALISTIC_GROWTH_LINEAGE_MISMATCH"


def test_current_pv_is_not_mislabelled_as_three_year_terminal_value():
    result = build_general_earnings_scenario(_row())
    assert result["v31_general_scenario_value_semantics"] == "CURRENT_PRESENT_VALUE"
    assert result["v31_general_scenario_3y_cagr_status"] == "TERMINAL_VALUE_EVIDENCE_REQUIRED"
    assert result["v31_general_scenario_risk_adjusted_cagr_status"] == (
        "SCENARIO_PROBABILITIES_AND_TERMINAL_VALUES_REQUIRED"
    )
    assert "v31_base_3y_cagr" not in result
    assert "v31_risk_adjusted_3y_cagr" not in result


def test_future_financial_observation_cannot_leak_into_current_inputs():
    as_of = date(2026, 9, 16)
    current_neutral = value_expectation_10y(2.0, 0.10)
    future_neutral = value_expectation_10y(99.0, 0.30)
    panel = pd.DataFrame(
        [
            {
                "report_date": "2026-06-30",
                "available_date": "2026-08-30",
                "normalized_eps_round6": 2.0,
                "realistic_growth_round6": 0.10,
                "neutral_value_round6": current_neutral,
                "normalized_earnings_observation_count": 4,
                "deduct_factor_round6": 0.9,
                "cash_conversion": 1.1,
                "realistic_growth_four_report_range": 0.03,
                "eps_growth_3y_round6": 0.10,
                "revenue_growth_3y_round6": 0.08,
            },
            {
                "report_date": "2026-09-30",
                "available_date": "2026-10-30",
                "normalized_eps_round6": 99.0,
                "realistic_growth_round6": 0.30,
                "neutral_value_round6": future_neutral,
                "normalized_earnings_observation_count": 4,
                "deduct_factor_round6": 1.0,
                "cash_conversion": 2.0,
                "realistic_growth_four_report_range": 0.01,
                "eps_growth_3y_round6": 0.30,
                "revenue_growth_3y_round6": 0.30,
            },
        ]
    )
    result = current_inputs_from_panel(
        "000001",
        panel,
        current_price=20.0,
        as_of=as_of,
        price_source="TEST",
        price_date=as_of,
    )
    assert result["v31_normalized_profit"] == 2.0
    assert result["v31_neutral_value"] == current_neutral
    assert result["financial_report_date"] == "2026-06-30"


def test_scenario_numeric_completion_does_not_create_gate_or_formal_authority():
    row = _row()
    row.update(build_general_earnings_scenario(row))
    assessment = assess_v31(row)

    assert assessment.scenario_valuation_ready is True
    assert assessment.buy_ready is False
    assert any(blocker.startswith("hard_gate_unknown:") for blocker in assessment.blockers)
    assert not any(key.startswith("v31_gate_") for key in build_general_earnings_scenario(_row()))
    assert "formal_signal_eligible" not in build_general_earnings_scenario(_row())
