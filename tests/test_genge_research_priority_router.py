from src.strategies.genge_opportunity_discovery.research_priority_router import build_queue


def test_holding_and_reunderwrite_rank_high_without_formal_recompute():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "600406", "scope": "HOLDING", "formal_action": "HOLD", "deep_review_priority": "RAISE", "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD", "thesis_status": "REUNDERWRITE_REQUIRED"}]}
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


def test_holding_hold_review_without_value_anchor_routes_reunderwrite():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "601318", "name": "中国平安", "scope": "HOLDING", "formal_action": "HOLD_REVIEW", "deep_review_priority": "KEEP", "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED", "thesis_status": "NO_NEW_MATERIAL_EVIDENCE", "price_evidence_status": "VALUE_ANCHOR_UNAVAILABLE", "validated_value_anchor": None}]}
    coverage = {"securities": [{"code": "601318", "name": "中国平安", "scopes": ["HOLDING"], "industry_mapped": False, "commodity_monitoring_state": "NOT_APPLICABLE", "peer_monitoring_state": "MAPPED"}]}
    row = build_queue(hourly, {"candidates": {}}, coverage)["queue"][0]
    assert row["priority"] == "P0"
    assert "CURRENT_HOLDING" in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" in row["reason_codes"]
    assert "VALUE_ANCHOR_REUNDERWRITE_REQUIRED" in row["reason_codes"]


def test_nonholding_missing_value_anchor_does_not_invent_reunderwrite():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "601318", "scope": "DEEP_REVIEW_FOCUS", "formal_action": "HOLD_REVIEW", "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED", "thesis_status": "NO_NEW_MATERIAL_EVIDENCE", "price_evidence_status": "VALUE_ANCHOR_UNAVAILABLE", "validated_value_anchor": None}]}
    coverage = {"securities": [{"code": "601318", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "NOT_APPLICABLE", "peer_monitoring_state": "MAPPED"}]}
    row = build_queue(hourly, {"candidates": {}}, coverage)["queue"][0]
    assert "CURRENT_HOLDING" not in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" not in row["reason_codes"]
    assert "VALUE_ANCHOR_REUNDERWRITE_REQUIRED" not in row["reason_codes"]


def test_stale_mapping_holding_scope_cannot_resurrect_closed_position():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "603369", "name": "今世缘", "scope": "DEEP_REVIEW_FOCUS", "formal_action": "", "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED", "thesis_status": "NO_NEW_MATERIAL_EVIDENCE"}]}
    coverage = {"securities": [{"code": "603369", "name": "今世缘", "scopes": ["HOLDING"], "industry_mapped": True, "commodity_monitoring_state": "NOT_APPLICABLE", "peer_monitoring_state": "MAPPED"}]}
    row = build_queue(hourly, {"candidates": {}}, coverage)["queue"][0]
    assert "CURRENT_HOLDING" not in row["reason_codes"]
    assert row["priority_score"] < 50


def test_holding_with_usable_value_anchor_does_not_invent_reunderwrite():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{"code": "601318", "scope": "HOLDING", "formal_action": "HOLD_REVIEW", "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED", "thesis_status": "NO_NEW_MATERIAL_EVIDENCE", "price_evidence_status": "PRICE_GATE_NOT_MET", "validated_value_anchor": 62.0}]}
    coverage = {"securities": [{"code": "601318", "scopes": ["HOLDING"], "industry_mapped": True, "commodity_monitoring_state": "NOT_APPLICABLE", "peer_monitoring_state": "MAPPED"}]}
    row = build_queue(hourly, {"candidates": {}}, coverage)["queue"][0]
    assert "CURRENT_HOLDING" in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" not in row["reason_codes"]


def test_mapping_gap_is_visible_not_guessed():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"600309": {"stock_name": "万华化学", "research_tier": "A1-QUALITY / WAIT_PRICE"}}}
    coverage = {"securities": [{"code": "600309", "name": "万华化学", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "APPLICABLE_UNMAPPED", "peer_monitoring_state": "APPLICABLE_UNMAPPED"}]}
    row = build_queue(hourly, lifecycle, coverage)["queue"][0]
    assert set(row["mapping_gaps"]) == {"COMMODITY", "PEER"}
    assert "MAPPING_GAP" in row["reason_codes"]


def test_partial_mapping_remains_visible_without_losing_connected_status():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"601020": {"stock_name": "华钰矿业", "research_tier": "PENDING"}}}
    coverage = {"securities": [{"code": "601020", "name": "华钰矿业", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "PARTIAL_MAPPED", "peer_monitoring_state": "APPLICABLE_UNMAPPED"}]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert set(row["mapping_gaps"]) == {"COMMODITY_PARTIAL", "PEER"}
    assert payload["partial_mapping_gap_count"] == 1
