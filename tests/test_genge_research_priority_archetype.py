import pytest

from src.strategies.genge_opportunity_discovery.research_priority_router import build_queue


def _base():
    return (
        {"canonical_snapshot_id": "snap", "rows": []},
        {"candidates": {}},
        {"securities": []},
    )


def _archetype(score=72.0, coverage=0.8, **top):
    payload = {
        "archetype_id": "RUNBEI_TEST",
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "canonical_authority_unchanged": True,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "changes_research_order_only": True,
        "changes_thresholds": False,
        "unknown_evidence_is_pass": False,
        "no_auto_trade": True,
        "queue": [{
            "code": "600001",
            "name": "测试股",
            "archetype_id": "RUNBEI_TEST",
            "similarity_score": score,
            "evidence_coverage": coverage,
            "source_quant_status": "HARD_REJECT",
            "formal_action_eligible": False,
            "formal_action_recomputed": False,
            "automatic_promotion_allowed": False,
            "starter_position_allowed": False,
        }],
    }
    payload.update(top)
    return payload


def test_archetype_only_hard_reject_enters_research_queue_without_formal_authority():
    hourly, lifecycle, coverage = _base()
    result = build_queue(hourly, lifecycle, coverage, success_archetype_recall=_archetype())
    row = next(r for r in result["queue"] if r["code"] == "600001")
    assert row["success_archetype_source_quant_status"] == "HARD_REJECT"
    assert row["research_overlay_priority_boost"] == 28
    assert row["formal_action_eligible"] is False
    assert result["success_archetype_recall_integrated"] is True
    assert result["success_archetype_recall_changes_thresholds"] is False


def test_low_coverage_archetype_is_not_integrated():
    hourly, lifecycle, coverage = _base()
    result = build_queue(hourly, lifecycle, coverage, success_archetype_recall=_archetype(coverage=0.4))
    assert result["success_archetype_recall_count"] == 0


def test_near_buy_and_archetype_boost_use_max_not_sum():
    hourly, lifecycle, coverage = _base()
    recovery = {
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "priority_changes_order_only": True,
        "threshold_changes_allowed": False,
        "queue": [{"code": "600001", "recovery_tier": "B", "formal_action_eligible": False, "automatic_promotion_allowed": False}],
    }
    result = build_queue(hourly, lifecycle, coverage, recovery, _archetype(score=72))
    row = next(r for r in result["queue"] if r["code"] == "600001")
    assert row["research_overlay_priority_boost"] == 30
    assert row["research_overlay_boost_combination"] == "MAX_NOT_SUM"


def test_archetype_authority_violation_fails_closed():
    hourly, lifecycle, coverage = _base()
    with pytest.raises(AssertionError):
        build_queue(hourly, lifecycle, coverage, success_archetype_recall=_archetype(formal_action_eligible=True))
