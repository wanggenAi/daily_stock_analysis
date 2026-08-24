from src.strategies.genge_opportunity_discovery.selection_framework_v31 import (
    assess_v31,
    exit_action_from_valuation,
)


def _base_row(*, current_price: float, neutral_value: float, entry_price: float) -> dict:
    return {
        "code": "600118",
        "entry_price": entry_price,
        "v31_current_price": current_price,
        "v31_predictability_status": "PASS",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
        "v31_financial_safety_status": "PASS",
        "v31_earnings_authenticity_status": "PASS",
        "v31_pessimistic_value": neutral_value * 0.8,
        "v31_neutral_value": neutral_value,
        "v31_optimistic_value": neutral_value * 1.2,
        "v31_extreme_stress_value": neutral_value * 0.6,
    }


def test_exit_action_is_independent_of_entry_cost():
    cheap_entry = assess_v31(_base_row(current_price=18.0, neutral_value=15.0, entry_price=10.0))
    expensive_entry = assess_v31(_base_row(current_price=18.0, neutral_value=15.0, entry_price=30.0))

    assert cheap_entry.exit_action == "REDUCE_25"
    assert expensive_entry.exit_action == "REDUCE_25"
    assert cheap_entry.exit_reason == expensive_entry.exit_reason
    assert cheap_entry.target_position_fraction == expensive_entry.target_position_fraction == 0.75


def test_refreshed_neutral_value_can_cancel_profit_taking_despite_large_gain():
    old_value = exit_action_from_valuation(current_price=18.0, neutral_value=15.0)
    refreshed_value = exit_action_from_valuation(current_price=18.0, neutral_value=25.0)

    assert old_value[0] == "REDUCE_25"
    assert refreshed_value[0] == "HOLD"
    assert refreshed_value[2] == 1.0


def test_falling_intrinsic_value_can_require_reduction_without_profit():
    # Purchase cost is deliberately irrelevant: current price is below an imagined
    # cost of 20, but valuation still requires de-risking when refreshed value is 10.
    row = _base_row(current_price=14.0, neutral_value=10.0, entry_price=20.0)
    result = assess_v31(row)

    assert result.exit_action == "REDUCE_50"
    assert result.target_position_fraction == 0.50


def test_broken_hard_logic_forces_exit_regardless_of_valuation_or_cost():
    row = _base_row(current_price=8.0, neutral_value=15.0, entry_price=20.0)
    row["v31_long_term_demand_status"] = "FAIL"
    result = assess_v31(row)

    assert result.exit_action == "EXIT"
    assert result.target_position_fraction == 0.0
    assert "long_term_demand" in result.exit_reason


def test_missing_valuation_never_falls_back_to_cost_basis_profit_taking():
    action, reason, target = exit_action_from_valuation(
        current_price=18.0,
        neutral_value=None,
    )

    assert action == "HOLD_REVIEW"
    assert reason == "valuation_incomplete"
    assert target is None
