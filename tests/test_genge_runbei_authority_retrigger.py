from copy import deepcopy

from src.strategies.genge_opportunity_discovery.event_driven_deep_review_trigger import build_decision


def _priority() -> dict:
    return {
        "canonical_snapshot_id": "snap-1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "queue": [
            {
                "code": "000526",
                "name": "学大教育",
                "priority": "P1",
                "priority_score": 90,
                "research_tier": "TIER_1",
                "formal_action": "",
                "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
                "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
                "reason_codes": ["SUCCESS_ARCHETYPE_RECALL"],
                "success_archetype_id": "RUNBEI_001316_V1",
                "success_archetype_similarity_score": 85.9134,
                "success_archetype_evidence_coverage": 1.0,
                "success_archetype_source_quant_status": "PRIORITY_RESEARCH",
                "near_buy_evidence_recovery_tier": "B",
                "mapping_gaps": ["INDUSTRY"],
                "near_buy_missing_evidence_items": ["hard_gate_1", "hard_gate_2", "scenario_valuation"],
            }
        ],
    }


def _hourly() -> dict:
    return {
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "rows": [
            {
                "code": "000526",
                "name": "学大教育",
                "price_evidence_status": "PRICE_GATE_NOT_MET",
                "latest_price_observed_at": "2026-09-08T10:00:00+08:00",
                "latest_change_pct": 0.2,
                "latest_evidence": [],
            }
        ],
    }


def test_high_confidence_runbei_recall_requests_authority_rereview_only() -> None:
    decision = build_decision(_priority(), _hourly())
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["000526"]
    assert decision["formal_action_eligible"] is False
    assert decision["direct_formal_action_change_allowed"] is False
    assert decision["no_auto_trade"] is True
    trigger = decision["triggers"][0]
    assert "SUCCESS_ARCHETYPE_RECALL_REUNDERWRITE_REQUIRED" in trigger["trigger_reasons"]
    assert trigger["success_archetype_signal_state"]["missing_evidence"] == [
        "hard_gate_1",
        "hard_gate_2",
        "scenario_valuation",
    ]


def test_runbei_recall_fails_closed_below_research_thresholds() -> None:
    for key, value in (
        ("success_archetype_similarity_score", 69.999),
        ("success_archetype_evidence_coverage", 0.999),
        ("success_archetype_source_quant_status", "HARD_REJECT"),
    ):
        priority = _priority()
        priority["queue"][0][key] = value
        decision = build_decision(priority, _hourly())
        assert decision["dispatch_required"] is False


def test_runbei_recall_requires_explicit_archetype_reason() -> None:
    priority = _priority()
    priority["queue"][0]["reason_codes"] = []
    assert build_decision(priority, _hourly())["dispatch_required"] is False


def test_digest_ignores_harmless_similarity_wiggle_and_gap_order() -> None:
    first = build_decision(_priority(), _hourly())
    changed = _priority()
    changed["queue"][0]["success_archetype_similarity_score"] = 86.7
    changed["queue"][0]["near_buy_missing_evidence_items"] = [
        "scenario_valuation",
        "hard_gate_2",
        "hard_gate_1",
    ]
    second = build_decision(changed, _hourly())
    assert first["signal_digest"] == second["signal_digest"]


def test_digest_changes_when_real_near_buy_evidence_gap_recovers() -> None:
    first = build_decision(_priority(), _hourly())
    recovered = deepcopy(_priority())
    recovered["queue"][0]["near_buy_missing_evidence_items"] = ["hard_gate_2", "scenario_valuation"]
    second = build_decision(recovered, _hourly())
    assert first["signal_digest"] != second["signal_digest"]


def test_legacy_missing_evidence_and_near_buy_items_are_combined_semantically() -> None:
    priority = _priority()
    priority["queue"][0]["missing_evidence"] = ["scenario_valuation", "legacy_gate"]
    state = build_decision(priority, _hourly())["triggers"][0]["success_archetype_signal_state"]
    assert state["missing_evidence"] == ["hard_gate_1", "hard_gate_2", "legacy_gate", "scenario_valuation"]
