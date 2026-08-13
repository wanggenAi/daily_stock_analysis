from __future__ import annotations

from src.strategies.genge_opportunity_discovery import candidate_recovery_report as report


def _base(**updates):
    item = {
        "code": "000001",
        "stock_name": "sample",
        "actionability_score": "70",
        "user_visible_level": "CONDITION_WATCH",
        "failed_gates": "event_risk_known;exit_profile_passed;exit_profile_sample_count",
        "exit_profile_status": "NOT_AVAILABLE",
        "stock_negative_veto_clear": "True",
        "stock_hard_veto_outcome_count": "0",
    }
    item.update(updates)
    return item


def test_recoverable_data_gap_is_non_formal():
    source = _base()
    rows = report.build_recovery_rows([source], [source])
    assert len(rows) == 1
    assert rows[0]["recovery_class"] == "DATA_RECOVERY_NOW"
    assert rows[0]["formal_signal_eligible"] is False
    assert rows[0]["automatic_promotion_allowed"] is False


def test_hard_event_blocker_is_excluded():
    source = _base(
        failed_gates="event_risk_not_high;exit_profile_passed;exit_profile_sample_count"
    )
    assert report.build_recovery_rows([source], [source]) == []


def test_negative_exit_profile_is_excluded():
    source = _base(exit_profile_status="DEGRADED", stock_negative_veto_clear="False")
    assert report.build_recovery_rows([source], [source]) == []
