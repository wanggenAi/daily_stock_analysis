from src.strategies.genge_opportunity_discovery.research_priority_router import build_queue


def test_holding_and_reunderwrite_rank_high_without_formal_recompute():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "600406", "formal_action": "HOLD", "deep_review_priority": "RAISE", "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD", "thesis_status": "REUNDERWRITE_REQUIRED"}]}
    lifecycle = {"candidates": {"600406": {"stock_name": "国电南瑞", "research_tier": "A1 / WAIT_PRICE"}}}
    coverage = {"securities": [{"code": "600406", "name": "国电南瑞", "scopes": ["HOLDING"], "industry_mapped": True, "commodity_monitoring_state": "NOT_APPLICABLE", "peer_monitoring_state": "MAPPED"}]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert row["priority"] == "P0"
    assert "CURRENT_HOLDING" in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" in row["reason_codes"]
    assert row["formal_action"] == "HOLD"
    assert row["formal_action_recomputed"] is False
    assert payload["formal_action_eligible"] is False


def test_mapping_gap_is_visible_not_guessed():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"600309": {"stock_name": "万华化学", "research_tier": "A1-QUALITY / WAIT_PRICE"}}}
    coverage = {"securities": [{"code": "600309", "name": "万华化学", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "APPLICABLE_UNMAPPED", "peer_monitoring_state": "APPLICABLE_UNMAPPED"}]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert set(row["mapping_gaps"]) == {"COMMODITY", "PEER"}
    assert "MAPPING_GAP" in row["reason_codes"]
    assert row["formal_action_eligible"] is False
