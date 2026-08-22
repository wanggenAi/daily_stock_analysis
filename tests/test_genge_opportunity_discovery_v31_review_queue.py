from src.strategies.genge_opportunity_discovery.v31_review_queue import build_review_rows


def test_queue_prefills_only_semantically_safe_machine_fields():
    valuation = [{
        "code": "600001",
        "stock_name": "样本",
        "industry": "高端制造",
        "valuation_research_rank": "1",
        "quant_score": "91",
        "normalized_core_operating_profit": "123.4",
        "earnings_normalization_method": "REPORTED_RECURRING_PROFIT",
        "earnings_quality_score": "88",
        "earnings_quality_confidence": "HIGH",
        "required_profit_growth_vs_reference": "0.08",
        "valuation_diagnostic_status": "OK",
        "financial_review_status": "OK",
    }]
    plans = {"600001": {"raw_latest_close": "50.0"}}

    row = build_review_rows(valuation, plan_map=plans, limit=10)[0]

    assert row["v31_current_price"] == "50.0"
    assert row["v31_normalized_profit"] == "123.4"
    assert row["v31_normalized_profit_method"] == "REPORTED_RECURRING_PROFIT"
    assert row["v31_predictability_status"] == ""
    assert row["v31_long_term_demand_status"] == ""
    assert row["v31_moat_status"] == ""
    assert row["v31_financial_safety_status"] == ""
    assert row["v31_earnings_authenticity_status"] == ""
    assert row["v31_hard_gates_passed"] is False
    assert row["v31_a_eligible"] is False
    assert row["v31_buy_ready"] is False
    assert set(row["v31_hard_gate_unknowns"].split(";")) == {
        "predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity"
    }


def test_high_legacy_scores_never_manufacture_v31_pass():
    valuation = [{
        "code": "600002",
        "stock_name": "高分样本",
        "industry": "材料",
        "valuation_research_rank": "1",
        "quant_score": "99.9",
        "earnings_quality_score": "100",
        "normalized_core_operating_profit": "500",
        "earnings_normalization_method": "MIDCYCLE",
        "required_profit_growth_vs_reference": "-0.20",
    }]

    row = build_review_rows(valuation, plan_map={"600002": {"raw_latest_close": "10"}})[0]

    assert row["v31_review_status"] == "RESEARCH_REQUIRED"
    assert row["v31_score_complete"] is False
    assert row["v31_a_eligible"] is False
    assert row["v31_buy_ready"] is False
    assert row["formal_signal_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
