from src.strategies.genge_opportunity_discovery.near_buy_evidence_recovery import (
    build_priority_payload,
    build_review_packets,
    evidence_tasks,
    normalize_recovery_rows,
)
from src.strategies.genge_opportunity_discovery.research_priority_router import build_queue


def _recovery_row(code="603369", tier="A", missing="hard_gate:predictability;hard_gate:moat"):
    return {
        "code": code,
        "stock_name": "今世缘",
        "industry": "白酒",
        "research_opportunity_state": "EVIDENCE_RECOVERY_PRIORITY",
        "evidence_recovery_priority_tier": tier,
        "missing_evidence_items": missing,
        "v31_hard_gate_failures": "",
        "confirmed_negative_items": "",
        "conflicted_evidence_items": "",
        "evidence_recovery_starter_allowed": "False",
        "terminal_decision": "REJECT",
        "terminal_reason_class": "EVIDENCE_INSUFFICIENT",
        "master_research_rank": "12",
    }


def test_recovery_workset_is_missing_only_and_deterministic():
    rows = [
        _recovery_row("600916", "C", "hard_gate:long_term_demand"),
        _recovery_row("603369", "A"),
        _recovery_row("603883", "B", "hard_gate:financial_safety"),
    ]
    workset = normalize_recovery_rows(rows)
    assert [row["code"] for row in workset] == ["603369", "603883", "600916"]
    assert [row["evidence_recovery_priority_tier"] for row in workset] == ["A", "B", "C"]
    assert all(row["source_row_immutable"] is True for row in workset)


def test_full_near_buy_overlay_is_valid_recovery_input():
    rows = [
        {"code": "000001", "research_opportunity_state": "REJECT"},
        {"code": "000002", "research_opportunity_state": "NEAR_BUY"},
        _recovery_row("603369", "A"),
    ]
    workset = normalize_recovery_rows(rows)
    assert [row["code"] for row in workset] == ["603369"]
    assert workset[0]["evidence_recovery_priority_tier"] == "A"


def test_empty_recovery_is_healthy_research_only_noop():
    workset = normalize_recovery_rows([])
    assert workset == []
    priority = build_priority_payload(workset, source_run_id="123", workset_digest="empty")
    assert priority["queue_count"] == 0
    assert priority["queue"] == []
    assert priority["priority_changes_order_only"] is True
    assert priority["threshold_changes_allowed"] is False
    assert priority["automatic_gate_inference_allowed"] is False
    assert priority["formal_action_eligible"] is False
    assert priority["formal_action_recomputed"] is False
    assert priority["automatic_promotion_allowed"] is False
    assert priority["starter_position_allowed"] is False
    assert priority["no_auto_trade"] is True

    routed = build_queue({"rows": []}, {"candidates": {}}, {"securities": []}, priority)
    assert routed["near_buy_recovery_integrated"] is False
    assert routed["near_buy_recovery_count"] == 0
    assert routed["near_buy_recovery_changes_order_only"] is True
    assert routed["near_buy_recovery_changes_thresholds"] is False
    assert routed["formal_action_recomputed"] is False
    assert routed["formal_action_eligible"] is False
    assert routed["no_auto_trade"] is True


def test_recovery_rejects_negative_conflict_and_starter_authority():
    negative = _recovery_row()
    negative["confirmed_negative_items"] = "hard_gate:moat"
    try:
        normalize_recovery_rows([negative])
        assert False, "confirmed negative must fail closed"
    except AssertionError:
        pass

    conflicted = _recovery_row()
    conflicted["conflicted_evidence_items"] = "source_conflict"
    try:
        normalize_recovery_rows([conflicted])
        assert False, "conflicted evidence must fail closed"
    except AssertionError:
        pass

    starter = _recovery_row()
    starter["evidence_recovery_starter_allowed"] = "True"
    try:
        normalize_recovery_rows([starter])
        assert False, "recovery cannot carry starter authority"
    except AssertionError:
        pass


def test_missing_items_map_to_tasks_not_gate_outcomes():
    tasks = evidence_tasks([
        "hard_gate:predictability",
        "hard_gate:long_term_demand",
        "hard_gate:moat",
        "normalized_profit",
        "falsification",
    ])
    assert "COMPANY_ANNUAL_REPORT" in tasks
    assert "PUBLIC_INDUSTRY_DATA" in tasks
    assert "COMPETITION_PEER_MAPPING" in tasks
    assert "EARNINGS_QUALITY_REVIEW" in tasks
    assert "FALSIFICATION_CONDITION_REVIEW" in tasks
    assert not any(task.endswith("PASS") for task in tasks)


def test_review_packet_keeps_qualitative_judgement_unresolved():
    workset = normalize_recovery_rows([_recovery_row()])
    packets = build_review_packets(
        workset,
        company_evidence=[{
            "code": "603369",
            "industry": "白酒",
            "evidence_status": "VERIFIED",
            "original_url": "https://example.invalid/company",
        }],
        industry_evidence=[{
            "code": "",
            "industry": "白酒",
            "evidence_status": "VERIFIED",
            "original_url": "https://example.invalid/industry",
        }],
        audit_rows=[],
    )
    row = packets[0]
    assert row["verified_evidence_count"] == 2
    assert row["evidence_collection_state"] == "EVIDENCE_COLLECTED_REQUIRES_EXPLICIT_JUDGEMENT"
    assert row["qualitative_judgement_state"] == "UNRESOLVED"
    assert row["automatic_gate_inference_allowed"] is False
    assert row["unknown_evidence_is_pass"] is False
    assert row["formal_action_eligible"] is False
    assert row["formal_action_recomputed"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["starter_position_allowed"] is False
    assert row["no_auto_trade"] is True


def test_priority_payload_is_bounded_and_research_only():
    workset = normalize_recovery_rows([
        _recovery_row("603369", "A"),
        _recovery_row("603883", "B", "hard_gate:financial_safety"),
        _recovery_row("600916", "C", "hard_gate:long_term_demand"),
    ])
    payload = build_priority_payload(workset, source_run_id="123", workset_digest="abc")
    assert [row["priority_boost"] for row in payload["queue"]] == [45, 30, 20]
    assert payload["priority_changes_order_only"] is True
    assert payload["threshold_changes_allowed"] is False
    assert payload["automatic_gate_inference_allowed"] is False
    assert payload["formal_action_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["starter_position_allowed"] is False
    assert payload["no_auto_trade"] is True


def test_router_merges_recovery_as_order_signal_only():
    hourly = {
        "canonical_snapshot_id": "s1",
        "rows": [{
            "code": "603369",
            "scope": "DEEP_REVIEW_FOCUS",
            "formal_action": "",
            "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
            "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
        }],
    }
    lifecycle = {"candidates": {"603369": {"stock_name": "今世缘", "research_tier": "PENDING"}}}
    coverage = {"securities": [{
        "code": "603369",
        "name": "今世缘",
        "industry_mapped": True,
        "commodity_monitoring_state": "NOT_APPLICABLE",
        "peer_monitoring_state": "MAPPED",
    }]}
    recovery = build_priority_payload(normalize_recovery_rows([_recovery_row()]))
    payload = build_queue(hourly, lifecycle, coverage, recovery)
    row = payload["queue"][0]
    assert row["near_buy_evidence_recovery_tier"] == "A"
    assert "NEAR_BUY_EVIDENCE_RECOVERY_A" in row["reason_codes"]
    assert row["priority_score"] == 50  # PENDING base=5 + bounded A boost=45
    assert row["priority"] == "P1"
    assert row["formal_action_recomputed"] is False
    assert row["formal_action_eligible"] is False
    assert payload["near_buy_recovery_changes_order_only"] is True
    assert payload["near_buy_recovery_changes_thresholds"] is False
    assert payload["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert payload["no_auto_trade"] is True


def test_router_ignores_untrusted_priority_boost_and_rejects_authority():
    recovery = build_priority_payload(normalize_recovery_rows([_recovery_row()]))
    recovery["queue"][0]["priority_boost"] = 99999
    payload = build_queue({"rows": []}, {"candidates": {}}, {"securities": []}, recovery)
    assert payload["queue"][0]["priority_score"] == 55  # base=5 + missing mapping=5 + fixed A=45

    recovery["formal_action_eligible"] = True
    try:
        build_queue({"rows": []}, {"candidates": {}}, {"securities": []}, recovery)
        assert False, "recovery artifact cannot claim Formal authority"
    except AssertionError:
        pass
