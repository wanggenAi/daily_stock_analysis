from __future__ import annotations

from src.strategies.genge_opportunity_discovery import candidate_recovery_report as report


def row(**updates):
    base = {
        "code": "600196",
        "stock_name": "example",
        "actionability_score": "73.5",
        "user_visible_level": "CONDITION_WATCH",
        "failed_gates": "event_risk_known;exit_profile_passed;exit_profile_sample_count",
        "exit_profile_status": "NOT_AVAILABLE",
        "stock_negative_veto_clear": "True",
        "stock_hard_veto_outcome_count": "0",
    }
    base.update(updates)
    return base


def test_data_gap_is_prioritized_without_becoming_formal():
    rows = report.build_recovery_rows([row()], [row()])
    assert len(rows) == 1
    candidate = rows[0]
    assert candidate["recovery_class"] == "DATA_RECOVERY_NOW"
    assert candidate["non_exit_blockers"] == "event_risk_known"
    assert candidate["formal_signal_eligible"] is False
    assert candidate["automatic_promotion_allowed"] is False


def test_market_setup_gap_is_watch_only():
    source = row(
        code="603369",
        failed_gates=(
            "price_volume_not_distribution;exit_profile_passed;"
            "exit_profile_sample_count;exit_profile_confidence"
        ),
    )
    rows = report.build_recovery_rows([source], [source])
    assert len(rows) == 1
    assert rows[0]["recovery_class"] == "MARKET_TRIGGER_WATCH"
    assert rows[0]["formal_signal_eligible"] is False


def test_high_event_risk_is_excluded():
    source = row(
        code="600199",
        failed_gates="event_risk_not_high;exit_profile_passed;exit_profile_sample_count",
    )
    assert report.build_recovery_rows([source], [source]) == []


def test_failed_or_negative_exit_profile_is_excluded():
    failed = row(exit_profile_status="FAILED")
    degraded = row(exit_profile_status="DEGRADED", stock_negative_veto_clear="False")
    hard_veto = row(stock_hard_veto_outcome_count="1")
    for source in (failed, degraded, hard_veto):
        assert report.build_recovery_rows([source], [source]) == []


def test_financial_or_valuation_failure_is_excluded():
    source = row(
        failed_gates=(
            "financial_passed;valuation_not_failed;"
            "exit_profile_passed;exit_profile_sample_count"
        ),
    )
    assert report.build_recovery_rows([source], [source]) == []


def test_data_recovery_ranks_ahead_of_market_and_research():
    data = row(code="600196", actionability_score="70")
    market = row(
        code="603369",
        actionability_score="90",
        failed_gates="price_volume_not_distribution;exit_profile_passed",
    )
    research = row(
        code="603195",
        actionability_score="95",
        failed_gates="hard_logic_medium;industry_evidence;exit_profile_passed",
    )
    rows = report.build_recovery_rows(
        [research, market, data],
        [research, market, data],
    )
    assert [item["recovery_class"] for item in rows] == [
        "DATA_RECOVERY_NOW",
        "MARKET_TRIGGER_WATCH",
        "RESEARCH_OR_TRIGGER_WATCH",
    ]
