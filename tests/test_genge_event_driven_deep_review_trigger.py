from __future__ import annotations

import copy

import pytest

from src.strategies.genge_opportunity_discovery.event_driven_deep_review_trigger import build_decision


def _hourly() -> dict:
    return {
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "1001",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "rows": [
            {
                "code": "601020",
                "name": "华钰矿业",
                "formal_action": "",
                "deep_review_priority": "RAISE",
                "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD",
                "thesis_status": "WEAKENING_RESEARCH_SIGNAL",
                "price_evidence_status": "PRICE_GATE_NOT_MET",
                "latest_price": 18.5,
                "latest_price_observed_at": "2026-08-31T09:45:00+08:00",
                "latest_evidence": [{"evidence_id": "ev-new-1"}],
            }
        ],
    }


def _priority() -> dict:
    return {
        "canonical_snapshot_id": "snap-1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "queue": [
            {
                "code": "601020",
                "name": "华钰矿业",
                "priority": "P0",
                "priority_score": 75,
                "research_tier": "PENDING",
                "thesis_status": "WEAKENING_RESEARCH_SIGNAL",
                "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD",
                "reason_codes": ["REUNDERWRITE_REQUIRED", "HOURLY_PRIORITY_RAISE"],
                "formal_action": "",
            }
        ],
    }


def test_external_p0_reunderwrite_triggers_full_production_rescan() -> None:
    decision = build_decision(_priority(), _hourly())
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["601020"]
    assert decision["signal_digest"]
    assert decision["downstream_semantics"] == "FULL_PRODUCTION_RESCAN_THEN_EXISTING_CANONICAL_FINALIZER"
    assert decision["formal_action_eligible"] is False
    assert decision["direct_formal_action_change_allowed"] is False
    assert decision["no_auto_trade"] is True


def test_current_holding_is_never_event_dispatch_trigger() -> None:
    priority = _priority()
    priority["queue"][0]["reason_codes"].append("CURRENT_HOLDING")
    priority["queue"][0]["formal_action"] = "HOLD_REVIEW"
    decision = build_decision(priority, _hourly())
    assert decision["dispatch_required"] is False
    assert decision["trigger_codes"] == []


def test_price_attractive_signal_triggers_even_when_priority_is_not_p0() -> None:
    priority = _priority()
    hourly = _hourly()
    priority["queue"][0].update(
        priority="P2",
        priority_score=40,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        reason_codes=["PRICE_ATTRACTIVE_RESEARCH_LEAD"],
    )
    hourly["rows"][0].update(
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        price_evidence_status="PRICE_GATE_PASS_RESEARCH_ONLY",
        latest_evidence=[],
    )
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["601020"]


def test_intraday_price_change_does_not_change_price_signal_digest() -> None:
    priority = _priority()
    hourly = _hourly()
    priority["queue"][0].update(
        priority="P2",
        priority_score=40,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        reason_codes=["PRICE_ATTRACTIVE_RESEARCH_LEAD"],
    )
    hourly["rows"][0].update(
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        price_evidence_status="PRICE_GATE_PASS_RESEARCH_ONLY",
        latest_evidence=[],
    )
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_price"] = 17.9
    hourly2["rows"][0]["latest_price_observed_at"] = "2026-08-31T13:45:00+08:00"
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] == second["signal_digest"]


def test_new_trade_day_changes_price_signal_digest() -> None:
    priority = _priority()
    hourly = _hourly()
    priority["queue"][0].update(
        priority="P2",
        priority_score=40,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        reason_codes=["PRICE_ATTRACTIVE_RESEARCH_LEAD"],
    )
    hourly["rows"][0].update(
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        price_evidence_status="PRICE_GATE_PASS_RESEARCH_ONLY",
        latest_evidence=[],
    )
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_price_observed_at"] = "2026-09-01T09:45:00+08:00"
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] != second["signal_digest"]


def test_new_evidence_id_changes_signal_digest() -> None:
    first = build_decision(_priority(), _hourly())
    hourly2 = _hourly()
    hourly2["rows"][0]["latest_evidence"].append({"evidence_id": "ev-new-2"})
    second = build_decision(_priority(), hourly2)
    assert first["signal_digest"] != second["signal_digest"]


def test_neutral_p2_raise_does_not_launch_expensive_full_scan() -> None:
    priority = _priority()
    hourly = _hourly()
    priority["queue"][0].update(
        priority="P2",
        priority_score=25,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        reason_codes=["HOURLY_PRIORITY_RAISE", "MAPPING_GAP"],
    )
    hourly["rows"][0].update(
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        latest_evidence=[],
    )
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is False


def test_canonical_identity_mismatch_fails_closed() -> None:
    priority = _priority()
    priority["canonical_snapshot_id"] = "different-snapshot"
    with pytest.raises(ValueError, match="one canonical snapshot"):
        build_decision(priority, _hourly())


def test_research_layer_cannot_be_promoted_to_formal_authority() -> None:
    priority = _priority()
    priority["formal_action_eligible"] = True
    with pytest.raises(ValueError, match="cannot be formal-action eligible"):
        build_decision(priority, _hourly())
