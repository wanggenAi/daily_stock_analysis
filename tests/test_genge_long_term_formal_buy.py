from src.strategies.genge_opportunity_discovery.long_term_formal_buy import (
    evaluate_long_term_candidate,
)


def _second_pass(code="603369"):
    return {
        "code": code,
        "stock_name": "Sample",
        "industry": "Consumer",
        "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
        "real_reward_risk_ratio": "3.2",
    }


def _plan():
    return {
        "code": "603369",
        "stock_name": "Sample",
        "industry": "Consumer",
        "market_regime_status": "GREEN",
        "event_risk_level": "LOW",
        "real_reward_risk_ratio": "3.2",
        "hard_blockers": "",
        "preferred_plan": "pullback",
        "raw_latest_close": "40",
        "pullback_entry_low": "39",
        "pullback_entry_high": "41",
        "pullback_stop_price": "36",
        "pullback_target_1": "50",
        "pullback_target_2": "56",
        "pullback_status": "READY",
    }


def _v31():
    return {
        "v31_predictability_status": "PASS",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
        "v31_financial_safety_status": "PASS",
        "v31_earnings_authenticity_status": "PASS",
        "v31_candidate_class": "A2",
        "v31_score_long_term_demand": 9,
        "v31_score_moat_direction": 18,
        "v31_score_earnings_quality": 8,
        "v31_score_roic_incremental_roic": 8,
        "v31_score_capital_allocation": 7,
        "v31_score_growth_runway": 8,
        "v31_score_normalized_earnings_certainty": 6,
        "v31_score_expectation_gap": 7,
        "v31_score_valuation_margin_of_safety": 10,
        "v31_score_market_position": 4,
        "v31_normalized_profit": 100,
        "v31_normalized_profit_method": "five_year_normalized_profit",
        "v31_pessimistic_value": 38,
        "v31_neutral_value": 60,
        "v31_optimistic_value": 80,
        "v31_extreme_stress_value": 32,
        "v31_current_price": 40,
        "v31_market_implied_profit_cagr": 0.06,
        "v31_realistic_profit_cagr": 0.14,
        "v31_expectation_gap_pct": 0.08,
        "v31_expectation_gap_thesis": "market underestimates durable earnings growth",
        "v31_risk_adjusted_3y_cagr": 0.17,
        "v31_potential_max_fundamental_loss_pct": 0.20,
        "v31_why_can_buy": "stable moat, cash earnings and valuation margin",
        "v31_strongest_bear_case": "growth runway or incremental ROIC may disappoint",
        "v31_falsification_status": "PASS",
        "v31_margin_of_safety_status": "PASS",
        "v31_cagr_attractiveness_status": "PASS",
        "v31_pessimistic_loss_status": "PASS",
        "v31_portfolio_exposure_status": "PASS",
        "v31_market_position_status": "PASS",
    }


def _valuation(required_growth="0.10", quality="75", execution="GENERIC_REVERSE_DIAGNOSTIC_READY"):
    return {
        "code": "603369",
        "valuation_model_execution_state": execution,
        "valuation_primary_strategy_id": "general_reverse_earnings",
        "valuation_routing_confidence": "0.8",
        "valuation_diagnostic_status": "OK",
        "required_profit_growth_vs_reference": required_growth,
        "earnings_quality_score": quality,
        "earnings_quality_confidence": "HIGH",
        "financial_review_status": "OK",
        "normalized_core_operating_profit": "100",
        # V3.1.1 Round-8/9 confidence evidence.  BUY fixtures must prove the
        # promoted gate rather than relying on pre-V3.1.1 implicit defaults.
        "normalized_earnings_observation_count": "4",
        "deduct_profit_quality_factor": "0.90",
        "cash_conversion_ratio": "0.90",
        "realistic_growth_four_report_range": "0.08",
        "implied_growth_status": "OK",
        **_v31(),
    }


def test_buy_ready_requires_both_production_safety_and_frozen_v31():
    row = evaluate_long_term_candidate(_second_pass(), _plan(), _valuation())
    assert row["long_term_formal_buy_eligible"] is True
    assert row["long_term_classification"] == "LONG_TERM_BUY_READY"
    assert row["v31_buy_ready"] is True
    assert row["v31_hard_gates_passed"] is True
    assert row["production_model_version"] == "GEN_GE_V3_1_1_PRODUCTION"
    assert row["production_action"] == "BUY"
    assert row["valuation_confidence"] == "HIGH"
    assert row["legacy_exit_profile_is_long_term_veto"] is False
    assert row["entry_low"] == 39.0
    assert row["entry_high"] == 41.0
    assert row["risk_invalidation_price"] == 36.0
    assert row["current_action"] == "ENTRY_CONDITION_PRESENT_REVIEW_NOW"
    assert row["formal_signal_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["no_auto_trade"] is True


def test_old_try_position_no_longer_exists_as_formal_bypass():
    row = evaluate_long_term_candidate(
        _second_pass(), _plan(), _valuation(required_growth="0.25", quality="58")
    )
    assert row["long_term_formal_buy_eligible"] is True
    assert row["long_term_classification"] == "LONG_TERM_BUY_READY"
    assert "TRY_POSITION" not in row["long_term_classification"]


def test_missing_v31_gate_blocks_even_when_legacy_inputs_are_strong():
    valuation = _valuation()
    valuation.pop("v31_moat_status")
    row = evaluate_long_term_candidate(_second_pass(), _plan(), valuation)
    assert row["long_term_formal_buy_eligible"] is False
    assert row["long_term_classification"] == "LONG_TERM_REVIEW_BLOCKED"
    assert "v31:hard_gate_unknown:moat" in row["long_term_blockers"]


def test_structural_demand_decline_cannot_be_rescued_by_cheap_valuation():
    valuation = _valuation()
    valuation["v31_long_term_demand_status"] = "STRUCTURAL_DECLINE"
    valuation["v31_current_price"] = 10
    valuation["v31_neutral_value"] = 60
    row = evaluate_long_term_candidate(_second_pass(), _plan(), valuation)
    assert row["v31_margin_reference_band"] == "EXTREME_MARGIN"
    assert row["long_term_formal_buy_eligible"] is False
    assert "v31:hard_gate_failed:long_term_demand" in row["long_term_blockers"]


def test_specialized_route_is_not_treated_as_executed_valuation():
    row = evaluate_long_term_candidate(
        _second_pass(),
        _plan(),
        _valuation(execution="SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"),
    )
    assert row["long_term_formal_buy_eligible"] is False
    assert row["long_term_classification"] == "LONG_TERM_REVIEW_BLOCKED"
    assert "valuation_model_not_executed" in row["long_term_blockers"]


def test_expensive_reverse_expectation_blocks_long_term_formal_buy():
    row = evaluate_long_term_candidate(
        _second_pass(), _plan(), _valuation(required_growth="0.60")
    )
    assert row["long_term_formal_buy_eligible"] is False
    assert "valuation_expectation_too_high" in row["long_term_blockers"]


def test_defensive_market_can_legitimately_leave_zero_formal_buy():
    plan = _plan()
    plan["market_regime_status"] = "RED"
    row = evaluate_long_term_candidate(_second_pass(), plan, _valuation())
    assert row["long_term_formal_buy_eligible"] is False
    assert "defensive_market" in row["long_term_blockers"]


def test_missing_financial_review_never_promotes_candidate():
    valuation = _valuation()
    valuation["financial_review_status"] = "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW"
    row = evaluate_long_term_candidate(_second_pass(), _plan(), valuation)
    assert row["long_term_formal_buy_eligible"] is False
    assert "financial_review_not_ready" in row["long_term_blockers"]


def test_low_valuation_confidence_blocks_formal_buy():
    valuation = _valuation()
    valuation["cash_conversion_ratio"] = -0.1
    row = evaluate_long_term_candidate(_second_pass(), _plan(), valuation)
    assert row["production_action"] == "HOLD_REVIEW"
    assert row["long_term_formal_buy_eligible"] is False
    assert "production_action_not_buy:HOLD_REVIEW" in row["long_term_blockers"]
