from datetime import datetime, timezone
from pathlib import Path

from src.strategies.genge_opportunity_discovery.postclose_recovery_watchdog import (
    evaluate_postclose_recovery,
)


def _dashboard(trade_date: str | None) -> dict:
    payload = {"canonical_source_run_id": "12345"}
    if trade_date is not None:
        payload["latest_trade_date"] = trade_date
    return payload


def test_oct8_postclose_stale_sep30_requests_recovery() -> None:
    result = evaluate_postclose_recovery(
        _dashboard("2026-09-30"),
        evaluated_at=datetime(2026, 10, 8, 11, 0, tzinfo=timezone.utc),
    )
    assert result["needs_recovery"] is True
    assert result["reason"] == "CANONICAL_BEHIND_COMPLETED_SESSION"
    assert result["expected_trade_date"] == "2026-10-08"


def test_oct8_postclose_current_canonical_does_not_recover() -> None:
    result = evaluate_postclose_recovery(
        _dashboard("2026-10-08"),
        evaluated_at=datetime(2026, 10, 8, 11, 0, tzinfo=timezone.utc),
    )
    assert result["needs_recovery"] is False
    assert result["reason"] == "CANONICAL_CURRENT"


def test_oct8_pre_settlement_does_not_dispatch_recovery() -> None:
    result = evaluate_postclose_recovery(
        _dashboard("2026-09-30"),
        evaluated_at=datetime(2026, 10, 8, 7, 30, tzinfo=timezone.utc),
    )
    assert result["needs_recovery"] is False
    assert result["reason"] == "NO_COMPLETED_SESSION_TODAY"
    assert result["expected_trade_date"] == "2026-09-30"


def test_national_day_holiday_does_not_dispatch_recovery() -> None:
    result = evaluate_postclose_recovery(
        _dashboard("2026-09-30"),
        evaluated_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
    )
    assert result["needs_recovery"] is False
    assert result["reason"] == "NO_COMPLETED_SESSION_TODAY"
    assert result["expected_trade_date"] == "2026-09-30"


def test_missing_trade_date_after_completed_session_requests_recovery() -> None:
    result = evaluate_postclose_recovery(
        _dashboard(None),
        evaluated_at=datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc),
    )
    assert result["needs_recovery"] is True
    assert result["reason"] == "CANONICAL_TRADE_DATE_MISSING"


def test_workflow_does_not_let_zero_job_queued_runs_deadlock_recovery() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/genge-postclose-canonical-recovery.yml"
    ).read_text(encoding="utf-8")

    # Fresh queues remain fail-closed, while a run that has spent at least an
    # hour queued and never created a job is explicitly cancelled before the
    # watchdog decides whether a replacement full producer may be dispatched.
    assert 'STALE_QUEUED_MINUTES: "60"' in workflow
    assert '--json databaseId,status,createdAt' in workflow
    assert '/actions/runs/${run_id}/jobs?per_page=1' in workflow
    assert 'jobs_total" -eq 0' in workflow
    assert 'gh run cancel "$run_id"' in workflow
    assert 'STALE_QUEUED_PRODUCTION_RUN' in workflow
