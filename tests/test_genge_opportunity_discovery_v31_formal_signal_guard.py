from src.strategies.genge_opportunity_discovery import v31_formal_signal_guard as guard


def _strict_original(row, plan, profile, evidence_urls, *, board_rule):
    return "STRICT_REVIEW_READY", []


def _v31_ready():
    return {
        "code": "600000",
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
        "v31_normalized_profit_method": "midcycle",
        "v31_pessimistic_value": 80,
        "v31_neutral_value": 120,
        "v31_optimistic_value": 160,
        "v31_extreme_stress_value": 60,
        "v31_current_price": 75,
        "v31_market_implied_profit_cagr": 0.05,
        "v31_realistic_profit_cagr": 0.15,
        "v31_expectation_gap_pct": 0.10,
        "v31_expectation_gap_thesis": "market underestimates growth",
        "v31_risk_adjusted_3y_cagr": 0.18,
        "v31_potential_max_fundamental_loss_pct": 0.20,
        "v31_why_can_buy": "hard logic and valuation margin",
        "v31_strongest_bear_case": "incremental ROIC may fall",
        "v31_falsification_status": "PASS",
        "v31_margin_of_safety_status": "PASS",
        "v31_cagr_attractiveness_status": "PASS",
        "v31_pessimistic_loss_status": "PASS",
        "v31_portfolio_exposure_status": "PASS",
        "v31_market_position_status": "PASS",
    }


def test_would_be_formal_buy_is_demoted_when_v31_is_missing():
    classify = guard._guarded_classifier(_strict_original)
    row = {}
    level, missing = classify(row, {}, {}, [], board_rule=None)
    assert level == "CONDITION_WATCH"
    assert guard.V31_FORMAL_GATE in missing
    assert row["v31_buy_ready"] is False


def test_complete_v31_can_leave_strict_review_ready_intact():
    classify = guard._guarded_classifier(_strict_original)
    row = _v31_ready()
    level, missing = classify(row, {}, {}, [], board_rule=None)
    assert level == "STRICT_REVIEW_READY"
    assert missing == []
    assert row["v31_buy_ready"] is True


def test_failed_long_term_demand_overrides_legacy_strict_buy():
    classify = guard._guarded_classifier(_strict_original)
    row = _v31_ready()
    row["v31_long_term_demand_status"] = "STRUCTURAL_DECLINE"
    row["v31_current_price"] = 10
    level, missing = classify(row, {}, {}, [], board_rule=None)
    assert level == "CONDITION_WATCH"
    assert any("hard_gate_failed:long_term_demand" in item for item in missing)
