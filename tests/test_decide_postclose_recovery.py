"""Regression checks for post-close producer watchdog; never authorizes trades."""
from datetime import datetime, timezone
from pathlib import Path

from scripts.decide_postclose_recovery import decide_recovery


NOW = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)  # 21:00 Beijing
DAY = "2026-09-28"


def _run(run_id=1, at="2026-09-28T10:32:00Z", status="completed", event="schedule"):
    return {"id": run_id, "event": event, "status": status, "created_at": at}


def _dashboard(day=DAY, fresh=True, market=DAY):
    return {
        "latest_trade_date": day,
        "freshness_contract": {
            "fresh": fresh,
            "canonical_latest_trade_date": day,
            "market_as_of": market,
        },
    }


def _decide(dashboard=None, upstream=(), downstream=(), now=NOW):
    return decide_recovery(
        dashboard, list(upstream), list(downstream), evaluated_at=now
    )


def test_missing_scheduled_source_dispatches_existing_full_scan():
    result = _decide(_dashboard(day="2026-09-24", fresh=False, market="2026-09-24"))
    assert result["action"] == "DISPATCH"
    assert result["expected_trade_date"] == DAY
    assert result["postclose_attempts"] == 0


def test_fully_fresh_dashboard_never_dispatches():
    assert _decide(_dashboard())["action"] == "SATISFIED"


def test_new_report_timestamp_cannot_stand_in_for_old_canonical_or_market_date():
    for stale in (
        _dashboard(day=DAY, fresh=True, market="2026-09-24"),
        _dashboard(day="2026-09-24", fresh=True),
        _dashboard(day=DAY, fresh=False),
        {"latest_trade_date": DAY, "freshness_contract": {"fresh": True}},
    ):
        assert _decide(stale)["action"] == "DISPATCH"


def test_in_progress_full_scan_is_not_dispatched_twice():
    result = _decide(None, upstream=[_run(status="in_progress")])
    assert (result["action"], result["postclose_attempts"]) == ("DEFER", 1)


def test_active_industry_or_finalizer_pipeline_prevents_duplicate_source_work():
    result = _decide(None, upstream=[_run()], downstream=[_run(5, status="queued")])
    assert result["action"] == "DEFER"


def test_busy_push_fixture_cannot_block_full_market_recovery():
    fixture = _run(99, status="in_progress", event="push")
    fixture["name"] = "GenGe Opportunity Discovery"
    assert _decide(None, downstream=[fixture])["action"] == "DISPATCH"


def test_only_real_postclose_production_events_count_as_attempts():
    prior_premarket = _run(1, at="2026-09-28T00:22:45Z", event="workflow_dispatch")
    non_producer = _run(2, at="2026-09-28T11:30:00Z", event="push")
    result = _decide(None, upstream=[prior_premarket, non_producer])
    assert result["action"] == "DISPATCH"
    assert result["postclose_attempts"] == 0


def test_one_completed_stale_source_allows_only_one_extra_recovery():
    assert _decide(None, upstream=[_run()])["action"] == "DISPATCH"


def test_two_completed_postclose_scans_fail_explicitly_if_still_stale():
    runs = [_run(1), _run(2, at="2026-09-28T12:35:00Z", event="workflow_dispatch")]
    result = _decide(_dashboard(day="2026-09-24", fresh=False), upstream=runs)
    assert result["action"] == "EXHAUSTED"
    assert result["postclose_attempts"] == 2


def test_next_morning_still_recovers_previous_completed_session():
    tuesday_0100 = datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc)
    result = _decide(_dashboard(day="2026-09-24", fresh=False, market="2026-09-24"), now=tuesday_0100)
    assert result["expected_trade_date"] == "2026-09-28"
    assert result["action"] == "DISPATCH"


def test_holiday_saturday_early_morning_does_not_invent_friday_session():
    # 2026-10-02 is inside the official mainland National Day closure. At
    # Saturday 01:00 Beijing the latest completed exchange session is Sep30,
    # not a nonexistent Oct2 Friday session.
    saturday_0100 = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    result = _decide(now=saturday_0100)
    assert result["expected_trade_date"] == "2026-09-30"
    assert result["action"] == "DISPATCH"


def test_not_weekday_postclose_defers_instead_of_guessing_session():
    morning = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
    saturday = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)
    assert _decide(now=morning)["action"] == "DEFER"
    assert _decide(now=saturday)["action"] == "DEFER"


def test_workflow_has_independent_bounded_recovery_triggers_and_real_producer():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/genge-postclose-source-recovery.yml"
    ).read_text(encoding="utf-8")
    assert 'cron: "30 12 * * 1-5"' in workflow
    assert 'cron: "0 17 * * 1-5"' in workflow
    assert "scripts/decide_postclose_recovery.py" in workflow
    assert "gh workflow run genge-v311-all-a.yml" in workflow
    assert "POSTCLOSE_SCAN_LIMIT_REACHED_STILL_STALE" in workflow
