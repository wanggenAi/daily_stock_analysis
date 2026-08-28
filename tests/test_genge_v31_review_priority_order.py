from src.strategies.genge_opportunity_discovery.v31_review_queue import build_review_rows


def test_priority_reorders_deep_review_without_promotion_or_trade():
    valuation_rows = [
        {"code": "600001", "stock_name": "A", "valuation_research_rank": "1"},
        {"code": "600002", "stock_name": "B", "valuation_research_rank": "2"},
    ]
    priority = {
        "600002": {"priority": "P0", "priority_score": 100, "reason_codes": ["CURRENT_HOLDING"], "mapping_gaps": []}
    }
    rows = build_review_rows(valuation_rows, plan_map={}, priority_map=priority, limit=2)
    assert rows[0]["code"] == "600002"
    assert rows[0]["research_priority"] == "P0"
    assert rows[0]["research_priority_is_ordering_only"] is True
    assert rows[0]["formal_signal_eligible"] is False
    assert rows[0]["automatic_promotion_allowed"] is False
    assert rows[0]["no_auto_trade"] is True
    assert rows[0]["v31_review_status"] == "RESEARCH_REQUIRED"


def test_no_priority_falls_back_to_valuation_rank():
    valuation_rows = [
        {"code": "600002", "stock_name": "B", "valuation_research_rank": "2"},
        {"code": "600001", "stock_name": "A", "valuation_research_rank": "1"},
    ]
    rows = build_review_rows(valuation_rows, plan_map={}, priority_map={}, limit=2)
    assert [r["code"] for r in rows] == ["600001", "600002"]
