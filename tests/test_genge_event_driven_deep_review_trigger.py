from __future__ import annotations

import copy

import pytest

from src.strategies.genge_opportunity_discovery.event_driven_deep_review_trigger import build_decision


def _material_event(evidence_id: str = "ev-new-1", direction: str = "WEAKENING") -> dict:
    return {
        "evidence_id": evidence_id,
        "materiality": "HIGH",
        "direction": direction,
    }


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
                "thesis_status": "REUNDERWRITE_REQUIRED",
                "price_evidence_status": "PRICE_GATE_NOT_MET",
                "latest_price": 18.5,
                "latest_change_pct": 0.5,
                "latest_price_observed_at": "2026-08-31T09:45:00+08:00",
                "high_materiality_evidence_count_72h": 1,
                "material_weakening_evidence_count_72h": 1,
                "material_strengthening_evidence_count_72h": 0,
                "latest_evidence": [_material_event()],
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
                "thesis_status": "REUNDERWRITE_REQUIRED",
                "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD",
                "reason_codes": ["REUNDERWRITE_REQUIRED", "HOURLY_PRIORITY_RAISE"],
                "formal_action": "",
            }
        ],
    }


def _make_holding(priority: dict, formal_action: str = "HOLD_REVIEW") -> None:
    priority["queue"][0]["reason_codes"].append("CURRENT_HOLDING")
    priority["queue"][0]["formal_action"] = formal_action


def _make_neutral(priority: dict, hourly: dict, *, holding: bool = False) -> None:
    reasons = ["HOURLY_PRIORITY_RAISE"]
    if holding:
        reasons.insert(0, "CURRENT_HOLDING")
    priority["queue"][0].update(
        priority="P0" if holding else "P2",
        priority_score=70 if holding else 25,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        reason_codes=reasons,
    )
    hourly["rows"][0].update(
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        high_materiality_evidence_count_72h=0,
        material_weakening_evidence_count_72h=0,
        material_strengthening_evidence_count_72h=0,
        latest_evidence=[],
    )


def test_external_reunderwrite_triggers_existing_full_v31_deep_review() -> None:
    decision = build_decision(_priority(), _hourly())
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["601020"]
    assert decision["holding_trigger_count"] == 0
    assert decision["external_trigger_count"] == 1
    assert decision["signal_digest"]
    assert decision["downstream_semantics"] == "EXISTING_V31_FULL_DEEP_REVIEW_THEN_PRODUCTION_FINALIZER"
    assert decision["formal_action_eligible"] is False
    assert decision["direct_formal_action_change_allowed"] is False
    assert decision["no_auto_trade"] is True


def test_holding_reunderwrite_signal_triggers_immediate_deep_review() -> None:
    priority = _priority()
    _make_holding(priority)
    decision = build_decision(priority, _hourly())
    assert decision["dispatch_required"] is True
    assert decision["trigger_codes"] == ["601020"]
    assert decision["holding_trigger_count"] == 1
    assert decision["external_trigger_count"] == 0
    assert decision["triggers"][0]["is_current_holding"] is True
    assert decision["triggers"][0]["existing_formal_action"] == "HOLD_REVIEW"


def test_ordinary_holding_p0_raise_does_not_trigger() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="REDUCE_25")
    _make_neutral(priority, hourly, holding=True)
    hourly["rows"][0]["latest_change_pct"] = 2.99
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is False


def test_holding_significant_move_triggers_at_existing_three_pct_raise_threshold() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="REDUCE_25")
    _make_neutral(priority, hourly, holding=True)
    hourly["rows"][0]["latest_change_pct"] = -3.2
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is True
    trigger = decision["triggers"][0]
    assert trigger["holding_move_bucket"] == "DOWN_3_TO_5"
    assert "SIGNIFICANT_HOLDING_PRICE_MOVE" in trigger["trigger_reasons"]


def test_same_holding_move_bucket_same_day_is_digest_stable() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="HOLD_REVIEW")
    _make_neutral(priority, hourly, holding=True)
    hourly["rows"][0]["latest_change_pct"] = 3.2
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_change_pct"] = 4.9
    hourly2["rows"][0]["latest_price_observed_at"] = "2026-08-31T14:30:00+08:00"
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] == second["signal_digest"]


def test_crossing_holding_move_band_retriggers_once() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="HOLD_REVIEW")
    _make_neutral(priority, hourly, holding=True)
    hourly["rows"][0]["latest_change_pct"] = 4.9
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_change_pct"] = 5.1
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] != second["signal_digest"]
    assert second["triggers"][0]["holding_move_bucket"] == "UP_5_TO_8"


def test_same_holding_move_band_new_trade_day_can_retrigger() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="HOLD_REVIEW")
    _make_neutral(priority, hourly, holding=True)
    hourly["rows"][0]["latest_change_pct"] = -3.5
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_price_observed_at"] = "2026-09-01T09:45:00+08:00"
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] != second["signal_digest"]


def test_external_three_pct_move_alone_does_not_trigger() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_neutral(priority, hourly, holding=False)
    hourly["rows"][0]["latest_change_pct"] = 6.0
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is False


def test_holding_price_attractive_signal_triggers_add_review() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_holding(priority, formal_action="HOLD_NO_ADD")
    priority["queue"][0].update(
        priority="P1",
        priority_score=55,
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        reason_codes=["CURRENT_HOLDING", "PRICE_ATTRACTIVE_RESEARCH_LEAD"],
    )
    hourly["rows"][0].update(
        thesis_status="NO_NEW_MATERIAL_EVIDENCE",
        hourly_research_conclusion="PRICE_ATTRACTIVE_RESEARCH_LEAD",
        price_evidence_status="PRICE_GATE_PASS_RESEARCH_ONLY",
        latest_change_pct=0.5,
        high_materiality_evidence_count_72h=0,
        material_weakening_evidence_count_72h=0,
        material_strengthening_evidence_count_72h=0,
        latest_evidence=[],
    )
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is True
    assert decision["holding_trigger_count"] == 1


def test_price_attractive_external_signal_triggers_even_when_priority_is_not_p0() -> None:
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
        high_materiality_evidence_count_72h=0,
        material_weakening_evidence_count_72h=0,
        material_strengthening_evidence_count_72h=0,
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
        high_materiality_evidence_count_72h=0,
        material_weakening_evidence_count_72h=0,
        material_strengthening_evidence_count_72h=0,
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
        high_materiality_evidence_count_72h=0,
        material_weakening_evidence_count_72h=0,
        material_strengthening_evidence_count_72h=0,
        latest_evidence=[],
    )
    first = build_decision(priority, hourly)
    hourly2 = copy.deepcopy(hourly)
    hourly2["rows"][0]["latest_price_observed_at"] = "2026-09-01T09:45:00+08:00"
    second = build_decision(priority, hourly2)
    assert first["signal_digest"] != second["signal_digest"]


def test_low_neutral_evidence_does_not_retrigger_same_material_signal() -> None:
    first = build_decision(_priority(), _hourly())
    hourly2 = _hourly()
    hourly2["rows"][0]["latest_evidence"].insert(
        0,
        {"evidence_id": "ev-low-neutral", "materiality": "LOW", "direction": "NEUTRAL"},
    )
    second = build_decision(_priority(), hourly2)
    assert first["signal_digest"] == second["signal_digest"]


def test_new_material_evidence_changes_signal_digest() -> None:
    first = build_decision(_priority(), _hourly())
    hourly2 = _hourly()
    hourly2["rows"][0]["latest_evidence"].append(_material_event("ev-new-2"))
    hourly2["rows"][0]["high_materiality_evidence_count_72h"] = 2
    hourly2["rows"][0]["material_weakening_evidence_count_72h"] = 2
    second = build_decision(_priority(), hourly2)
    assert first["signal_digest"] != second["signal_digest"]


def test_neutral_p0_raise_does_not_launch_expensive_deep_review() -> None:
    priority = _priority()
    hourly = _hourly()
    _make_neutral(priority, hourly, holding=False)
    priority["queue"][0]["priority"] = "P0"
    priority["queue"][0]["priority_score"] = 75
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is False


def test_p0_material_evidence_change_triggers_without_reunderwrite_label() -> None:
    priority = _priority()
    hourly = _hourly()
    priority["queue"][0].update(
        priority="P0",
        thesis_status="MIXED_NEW_EVIDENCE",
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        reason_codes=["MATERIAL_EVIDENCE_CHANGE"],
    )
    hourly["rows"][0].update(
        thesis_status="MIXED_NEW_EVIDENCE",
        hourly_research_conclusion="FORMAL_ACTION_UNCHANGED",
        material_strengthening_evidence_count_72h=1,
    )
    decision = build_decision(priority, hourly)
    assert decision["dispatch_required"] is True


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
