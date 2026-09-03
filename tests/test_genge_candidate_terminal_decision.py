from src.strategies.genge_opportunity_discovery.candidate_terminal_decision import (
    build_terminal_rows,
    terminalize_candidate,
)


def _complete_v31(code="603369"):
    return {
        "code": code,
        "stock_name": "Sample",
        "industry": "Consumer",
        "master_research_rank": "1",
        "valuation_research_rank": "1",
        "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
        "financial_review_status": "OK",
        "valuation_diagnostic_status": "OK",
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


def test_buy_can_only_mirror_already_authorized_formal_buy():
    row = _complete_v31()
    row.update(
        {
            "long_term_formal_buy_eligible": True,
            "v31_buy_ready": True,
            "production_action": "BUY",
        }
    )
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "BUY"
    assert result["terminal_reason_class"] == "FORMAL_BUY_READY"
    assert result["terminal_formal_buy_authorized"] is True
    assert result["decision_authority"] == "RESEARCH_TERMINAL_VIEW"
    assert result["formal_signal_eligible"] is False
    assert result["automatic_promotion_allowed"] is False
    assert result["no_auto_trade"] is True


def test_complete_candidate_with_only_margin_failure_becomes_wait_price():
    row = _complete_v31()
    row["v31_margin_of_safety_status"] = "FAIL"
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "WAIT_PRICE"
    assert result["terminal_reason_class"] == "PRICE_OR_RETURN_NOT_ATTRACTIVE"
    assert result["terminal_evidence_complete"] is True
    assert result["wait_price_reference"] == 51.0
    assert result["wait_price_reference_source"] == "v31_staged_buy_reference_band_diagnostic"
    assert result["research_reference_ceiling_semantics"] == "diagnostic_only_not_formal_buy_gate"
    assert result["terminal_formal_buy_authorized"] is False


def test_existing_entry_high_is_preferred_as_wait_reference():
    row = _complete_v31()
    row["v31_market_position_status"] = "FAIL"
    row["entry_high"] = "44.5"
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "WAIT_PRICE"
    assert result["wait_price_reference"] == 44.5
    assert result["wait_price_reference_source"] == "existing_entry_high"


def test_unknown_hard_gate_is_reject_evidence_insufficient_not_wait_price():
    row = _complete_v31()
    row.pop("v31_moat_status")
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "REJECT"
    assert result["terminal_reason_class"] == "EVIDENCE_INSUFFICIENT"
    assert "hard_gate_unknown:moat" in result["terminal_reason_codes"]
    assert result["terminal_retryable_next_cycle"] is True


def test_failed_hard_gate_is_reject_and_not_retryable_price_wait():
    row = _complete_v31()
    row["v31_long_term_demand_status"] = "STRUCTURAL_DECLINE"
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "REJECT"
    assert result["terminal_reason_class"] == "HARD_GATE_FAILED"
    assert "hard_gate_failed:long_term_demand" in result["terminal_reason_codes"]
    assert result["terminal_retryable_next_cycle"] is False


def test_non_price_buy_condition_failure_never_becomes_wait_price():
    row = _complete_v31()
    row["v31_portfolio_exposure_status"] = "FAIL"
    result = terminalize_candidate(row)
    assert result["terminal_decision"] == "REJECT"
    assert result["terminal_reason_class"] == "NON_PRICE_BUY_CONDITION_FAILED"
    assert "buy_condition_failed:portfolio_exposure_acceptable" in result["terminal_reason_codes"]


def test_buy_ready_research_cannot_self_promote_without_formal_authority():
    result = terminalize_candidate(_complete_v31())
    assert result["v31_buy_ready"] is True
    assert result["terminal_decision"] == "REJECT"
    assert result["terminal_reason_class"] == "FORMAL_BUY_NOT_AUTHORIZED"
    assert result["terminal_formal_buy_authorized"] is False


def test_all_master_rows_end_in_exactly_one_terminal_state():
    buy = _complete_v31("603369")
    buy.update(
        {
            "long_term_formal_buy_eligible": "True",
            "v31_buy_ready": "True",
            "production_action": "BUY",
            "master_research_rank": "2",
        }
    )
    wait = _complete_v31("000001")
    wait["v31_cagr_attractiveness_status"] = "FAIL"
    wait["master_research_rank"] = "1"
    reject = _complete_v31("600000")
    reject.pop("v31_predictability_status")
    reject["master_research_rank"] = "3"

    rows = build_terminal_rows([reject, buy, wait, dict(wait)])
    assert len(rows) == 3
    assert {row["terminal_decision"] for row in rows} == {"BUY", "WAIT_PRICE", "REJECT"}
    assert [row["terminal_decision"] for row in rows] == ["BUY", "WAIT_PRICE", "REJECT"]
    assert all(row["no_auto_trade"] is True for row in rows)
    assert all(row["decision_authority"] == "RESEARCH_TERMINAL_VIEW" for row in rows)
