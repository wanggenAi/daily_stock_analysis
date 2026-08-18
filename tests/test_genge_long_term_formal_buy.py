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
    }


def test_buy_ready_when_non_exit_gates_and_completed_valuation_are_strong():
    row = evaluate_long_term_candidate(_second_pass(), _plan(), _valuation())
    assert row["long_term_formal_buy_eligible"] is True
    assert row["long_term_classification"] == "LONG_TERM_BUY_READY"
    assert row["legacy_exit_profile_is_long_term_veto"] is False
    assert row["entry_low"] == 39.0
    assert row["entry_high"] == 41.0
    assert row["risk_invalidation_price"] == 36.0
    assert row["current_action"] == "ENTRY_CONDITION_PRESENT_REVIEW_NOW"
    assert row["formal_signal_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["no_auto_trade"] is True


def test_try_position_for_acceptable_but_not_buy_ready_valuation():
    row = evaluate_long_term_candidate(
        _second_pass(), _plan(), _valuation(required_growth="0.25", quality="58")
    )
    assert row["long_term_formal_buy_eligible"] is True
    assert row["long_term_classification"] == "LONG_TERM_TRY_POSITION"
    assert row["long_term_blockers"] == ""


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
