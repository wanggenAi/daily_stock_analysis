from src.strategies.genge_opportunity_discovery.selection_framework_v31 import (
    assess_v31,
    margin_reference_band,
)


def complete_v31(**overrides):
    row = {
        "v31_predictability_status": "PASS",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
        "v31_financial_safety_status": "PASS",
        "v31_earnings_authenticity_status": "PASS",
        "v31_candidate_class": "A1",
        "v31_score_long_term_demand": 9,
        "v31_score_moat_direction": 18,
        "v31_score_earnings_quality": 9,
        "v31_score_roic_incremental_roic": 9,
        "v31_score_capital_allocation": 7,
        "v31_score_growth_runway": 9,
        "v31_score_normalized_earnings_certainty": 6,
        "v31_score_expectation_gap": 7,
        "v31_score_valuation_margin_of_safety": 11,
        "v31_score_market_position": 4,
        "v31_normalized_profit": 100,
        "v31_normalized_profit_method": "five_year_midcycle_and_next_cycle_blend",
        "v31_pessimistic_value": 80,
        "v31_neutral_value": 120,
        "v31_optimistic_value": 160,
        "v31_extreme_stress_value": 60,
        "v31_current_price": 75,
        "v31_market_implied_profit_cagr": 0.05,
        "v31_realistic_profit_cagr": 0.15,
        "v31_expectation_gap_pct": 0.10,
        "v31_expectation_gap_thesis": "market underestimates durable share gains",
        "v31_risk_adjusted_3y_cagr": 0.18,
        "v31_potential_max_fundamental_loss_pct": 0.20,
        "v31_why_can_buy": "durable moat plus normalized earnings upside",
        "v31_strongest_bear_case": "incremental ROIC could deteriorate after expansion",
        "v31_falsification_status": "PASS",
        "v31_margin_of_safety_status": "PASS",
        "v31_cagr_attractiveness_status": "PASS",
        "v31_pessimistic_loss_status": "PASS",
        "v31_portfolio_exposure_status": "PASS",
        "v31_market_position_status": "PASS",
    }
    row.update(overrides)
    return row


def test_complete_frozen_framework_can_be_buy_ready():
    result = assess_v31(complete_v31())
    assert result.hard_gates_passed is True
    assert result.a_eligible is True
    assert result.score_complete is True
    assert result.score_total == 89.0
    assert result.buy_ready is True


def test_cheap_price_cannot_rescue_structural_demand_failure():
    result = assess_v31(
        complete_v31(
            v31_long_term_demand_status="STRUCTURAL_DECLINE",
            v31_current_price=20,
            v31_neutral_value=120,
        )
    )
    assert result.margin_reference_band == "EXTREME_MARGIN"
    assert result.hard_gates_passed is False
    assert result.a_eligible is False
    assert result.buy_ready is False
    assert "hard_gate_failed:long_term_demand" in result.blockers


def test_unknown_moat_cannot_be_silently_promoted_to_a():
    result = assess_v31(complete_v31(v31_moat_status=""))
    assert result.hard_gates_passed is False
    assert result.a_eligible is False
    assert "moat" in result.hard_gate_unknowns


def test_total_score_cannot_compensate_for_gate_failure():
    row = complete_v31(v31_financial_safety_status="FAIL")
    result = assess_v31(row)
    assert result.score_total == 89.0
    assert result.buy_ready is False
    assert "hard_gate_failed:financial_safety" in result.blockers


def test_reference_margin_bands_match_frozen_document():
    assert margin_reference_band(64, 100) == "EXTREME_MARGIN"
    assert margin_reference_band(70, 100) == "A_LEVEL_REFERENCE"
    assert margin_reference_band(80, 100) == "STAGED_BUY_REFERENCE"
    assert margin_reference_band(95, 100) == "WAIT_REFERENCE"
    assert margin_reference_band(110, 100) == "OVERVALUED_REFERENCE"
    assert margin_reference_band(125, 100) == "SEVERELY_PRICED_IN_REFERENCE"
