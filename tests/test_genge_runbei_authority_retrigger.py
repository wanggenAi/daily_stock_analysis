from __future__ import annotations

import copy

import pytest

from src.strategies.genge_opportunity_discovery.event_driven_deep_review_trigger import build_decision


def _priority() -> dict:
    return {
        "canonical_snapshot_id": "snap-runbei",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "queue": [
            {
                "code": "000526",
                "name": "学大教育",
                "priority": "P1",
                "priority_score": 55,
                "research_tier": "PENDING",
                "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
                "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
                "reason_codes": [
                    "HOURLY_PRIORITY_RAISE",
                    "MAPPING_GAP",
                    "NEAR_BUY_EVIDENCE_RECOVERY_B",
                    "SUCCESS_ARCHETYPE_RECALL",
                    "ARCHETYPE:RUNBEI_001316_20260826_V1",
                ],
                "formal_action": "",
                "success_archetype_evidence_coverage": 1.0,
                "success_archetype_id": "RUNBEI_001316_20260826_V1",
                "success_archetype_similarity_score": 85.9134,
                "success_archetype_source_quant_status": "PRIORITY_RESEARCH",
                "near_buy_evidence_recovery_tier": "B",
                "mapping_gaps": ["INDUSTRY"],
                "missing_evidence": [
                    "hard_gate_1",
                    "hard_gate_2",
                    "scenario_valuation",
                ],
            }
        ],
    }


def _hourly() -> dict:
    return {
        "canonical_snapshot_id": "snap-runbei",
        "canonical_source_run_id": "34073932682",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "rows": [
            {
                "code": "000526",
                "name": "学大教育",
                "hourly_research_conclusion": "FORMAL_ACTION_UNCHANGED",
                "thesis_status": "NO_NEW_MATERIAL_EVIDENCE",
                "price_evidence_status": "UNKNOWN",
                "latest_change_pct": 0.5,
                "latest_price_observed_at": "2026-09-07T10:20:00+08:00",
                "high_materiality_evidence_count_72h": 0,
                "material_weakening_evidence_count_72h": 0,
                "material_strengthening_evidence_count_72h": 0,
                "latest_evidence": [],
            }
        ],
    }


def test_high_confidence_runbei_recall_triggers_authority_rereview_without_promotion() -> None:
    decision = build_decision(_priority(), _hourly())

    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["000526"]
    assert decision["holding_trigger_count"] == 0
    assert decision["external_trigger_count"] == 1
    assert "HIGH_CONFIDENCE_SUCCESS_ARCHETYPE_RECALL" in decision["triggers"][0]["trigger_reasons"]
    assert decision["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert decision["formal_action_recomputed"] is False
    assert decision["formal_action_eligible"] is False
    assert decision["direct_formal_action_change_allowed"] is False
    assert decision["no_auto_trade"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("success_archetype_similarity_score", 69.999),
        ("success_archetype_evidence_coverage", 0.999),
        ("success_archetype_source_quant_status", "HARD_REJECT"),
    ],
)
def test_runbei_recall_fails_closed_below_research_trigger_contract(field: str, value: object) -> None:
    priority = _priority()
    priority["queue"][0][field] = value

    decision = build_decision(priority, _hourly())

    assert decision["dispatch_required"] is False
    assert decision["external_trigger_count"] == 0


def test_runbei_recall_requires_explicit_recall_reason() -> None:
    priority = _priority()
    priority["queue"][0]["reason_codes"] = ["MAPPING_GAP", "NEAR_BUY_EVIDENCE_RECOVERY_B"]

    decision = build_decision(priority, _hourly())

    assert decision["dispatch_required"] is False


def test_runbei_digest_is_stable_for_same_evidence_state() -> None:
    first = build_decision(_priority(), _hourly())
    priority2 = copy.deepcopy(_priority())
    priority2["queue"][0]["success_archetype_similarity_score"] = 86.7
    priority2["queue"][0]["missing_evidence"] = list(reversed(priority2["queue"][0]["missing_evidence"]))

    second = build_decision(priority2, _hourly())

    assert first["signal_digest"] == second["signal_digest"]


def test_runbei_digest_changes_when_evidence_gap_state_changes() -> None:
    first = build_decision(_priority(), _hourly())
    priority2 = copy.deepcopy(_priority())
    priority2["queue"][0]["missing_evidence"].remove("hard_gate_2")

    second = build_decision(priority2, _hourly())

    assert first["signal_digest"] != second["signal_digest"]
