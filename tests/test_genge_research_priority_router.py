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
    hourly = {
        "canonical_snapshot_id": "s1",
        "rows": [{
            "code": "601318",
            "name": "中国平安",
            "scope": "HOLDING",
            "formal_action": "HOLD_REVIEW",
            "deep_review_priority": "KEEP",
            "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
            "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
            "price_evidence_status": "VALUE_ANCHOR_UNAVAILABLE",
            "validated_value_anchor": None,
        }],
    }
    lifecycle = {"candidates": {}}
    coverage = {"securities": [{
        "code": "601318",
        "name": "中国平安",
        "scopes": ["HOLDING"],
        "industry_mapped": False,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert row["priority"] == "P0"
    assert row["formal_action"] == "HOLD_REVIEW"
    assert "CURRENT_HOLDING" in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" in row["reason_codes"]
    assert "VALUE_ANCHOR_REUNDERWRITE_REQUIRED" in row["reason_codes"]
    assert row["formal_action_recomputed"] is False
    assert row["formal_action_eligible"] is False
    assert payload["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert payload["no_auto_trade"] is True


def test_nonholding_missing_value_anchor_does_not_invent_reunderwrite():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{
        "code": "601318",
        "scope": "DEEP_REVIEW_FOCUS",
        "formal_action": "HOLD_REVIEW",
        "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
        "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
        "price_evidence_status": "VALUE_ANCHOR_UNAVAILABLE",
        "validated_value_anchor": None,
    }]}
    payload = build_queue(hourly, {"candidates": {}}, {"securities": [{
        "code": "601318",
        "scopes": ["ACTIVE_CANDIDATE"],
        "industry_mapped": True,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]})
    row = payload["queue"][0]
    assert "CURRENT_HOLDING" not in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" not in row["reason_codes"]
    assert "VALUE_ANCHOR_REUNDERWRITE_REQUIRED" not in row["reason_codes"]


def test_stale_mapping_holding_scope_cannot_resurrect_closed_position():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{
        "code": "603369",
        "name": "今世缘",
        "scope": "DEEP_REVIEW_FOCUS",
        "formal_action": "",
        "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
        "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
    }]}
    payload = build_queue(hourly, {"candidates": {}}, {"securities": [{
        "code": "603369",
        "name": "今世缘",
        "scopes": ["HOLDING"],
        "industry_mapped": True,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]})
    row = payload["queue"][0]
    assert "CURRENT_HOLDING" not in row["reason_codes"]
    assert row["priority_score"] < 50
    assert row["formal_action_recomputed"] is False
    assert row["formal_action_eligible"] is False


def test_holding_with_usable_value_anchor_does_not_invent_reunderwrite():
    hourly = {"canonical_snapshot_id": "s1", "rows": [{
        "code": "601318",
        "scope": "HOLDING",
        "formal_action": "HOLD_REVIEW",
        "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
        "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
        "price_evidence_status": "PRICE_GATE_NOT_MET",
        "validated_value_anchor": 62.0,
    }]}
    payload = build_queue(hourly, {"candidates": {}}, {"securities": [{
        "code": "601318",
        "scopes": ["HOLDING"],
        "industry_mapped": True,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]})
    row = payload["queue"][0]
    assert "CURRENT_HOLDING" in row["reason_codes"]
    assert "REUNDERWRITE_REQUIRED" not in row["reason_codes"]
    assert "VALUE_ANCHOR_REUNDERWRITE_REQUIRED" not in row["reason_codes"]


def test_mapping_gap_is_visible_not_guessed():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"600309": {"stock_name": "万华化学", "research_tier": "A1-QUALITY / WAIT_PRICE"}}}
    coverage = {"securities": [{"code": "600309", "name": "万华化学", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "APPLICABLE_UNMAPPED", "peer_monitoring_state": "APPLICABLE_UNMAPPED"}]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert set(row["mapping_gaps"]) == {"COMMODITY", "PEER"}
    assert "MAPPING_GAP" in row["reason_codes"]
    assert row["formal_action_eligible"] is False


def test_partial_mapping_remains_visible_without_losing_connected_status():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"601020": {"stock_name": "华钰矿业", "research_tier": "PENDING"}}}
    coverage = {"securities": [{"code": "601020", "name": "华钰矿业", "scopes": ["ACTIVE_CANDIDATE"], "industry_mapped": True, "commodity_monitoring_state": "PARTIAL_MAPPED", "peer_monitoring_state": "APPLICABLE_UNMAPPED"}]}
    payload = build_queue(hourly, lifecycle, coverage)
    row = payload["queue"][0]
    assert set(row["mapping_gaps"]) == {"COMMODITY_PARTIAL", "PEER"}
    assert payload["partial_mapping_gap_count"] == 1
    assert row["formal_action_eligible"] is False


def test_current_deep_all_pass_candidate_is_promoted_for_research_order_only():
    hourly = {"rows": []}
    lifecycle = {"candidates": {"603596": {"stock_name": "伯特利", "research_tier": "PENDING"}}}
    coverage = {"securities": [{
        "code": "603596",
        "name": "伯特利",
        "industry_mapped": True,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]}
    deep_profiles = {
        "lambda_run_id": "deep-1",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "profiles": {
            "603596": {
                "name": "伯特利",
                "industry": "C36汽车制造业",
                "gates": {
                    "earnings_authenticity": {"status": "PASS"},
                    "financial_safety": {"status": "PASS"},
                    "long_term_demand": {"status": "PASS"},
                    "moat": {"status": "PASS"},
                    "predictability": {"status": "PASS"},
                },
            }
        },
    }
    deep_status = {"lambda_run_id": "deep-1", "execution_status": "SUCCESS"}

    payload = build_queue(
        hourly,
        lifecycle,
        coverage,
        deep_profiles=deep_profiles,
        deep_status=deep_status,
    )
    row = payload["queue"][0]

    assert row["code"] == "603596"
    assert row["priority"] == "P1"
    assert row["deep_hard_gate_complete"] is True
    assert row["deep_hard_gate_pass_count"] == 5
    assert "DEEP_HARD_GATES_COMPLETE_RESEARCH_FOLLOWUP" in row["reason_codes"]
    assert row["formal_action_eligible"] is False
    assert row["formal_action_recomputed"] is False
    assert payload["deep_qualified_profile_count"] == 1
    assert payload["deep_qualified_profile_changes_order_only"] is True
    assert payload["deep_qualified_profile_changes_thresholds"] is False
    assert payload["no_auto_trade"] is True


def test_deep_profile_unknown_or_stale_lineage_cannot_receive_qualification_boost():
    lifecycle = {
        "candidates": {
            "603596": {"stock_name": "伯特利", "research_tier": "PENDING"},
            "600000": {"stock_name": "未知样例", "research_tier": "PENDING"},
        }
    }
    coverage = {"securities": []}
    profiles = {
        "lambda_run_id": "old-run",
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "profiles": {
            "603596": {
                "gates": {
                    "earnings_authenticity": {"status": "PASS"},
                    "financial_safety": {"status": "PASS"},
                    "long_term_demand": {"status": "PASS"},
                    "moat": {"status": "PASS"},
                    "predictability": {"status": "PASS"},
                }
            },
            "600000": {
                "gates": {
                    "earnings_authenticity": {"status": "PASS"},
                    "financial_safety": {"status": "PASS"},
                    "long_term_demand": {"status": "PASS"},
                    "moat": {"status": "PASS"},
                    "predictability": {"status": "UNKNOWN"},
                }
            },
        },
    }

    stale = build_queue(
        {"rows": []},
        lifecycle,
        coverage,
        deep_profiles=profiles,
        deep_status={"lambda_run_id": "new-run", "execution_status": "SUCCESS"},
    )
    assert stale["deep_qualified_profile_count"] == 0
    assert all(row["deep_hard_gate_complete"] is False for row in stale["queue"])

    current = build_queue(
        {"rows": []},
        lifecycle,
        coverage,
        deep_profiles=profiles,
        deep_status={"lambda_run_id": "old-run", "execution_status": "SUCCESS"},
    )
    by_code = {row["code"]: row for row in current["queue"]}
    assert by_code["603596"]["deep_hard_gate_complete"] is True
    assert by_code["600000"]["deep_hard_gate_complete"] is False
    assert "DEEP_HARD_GATES_COMPLETE_RESEARCH_FOLLOWUP" not in by_code["600000"]["reason_codes"]
