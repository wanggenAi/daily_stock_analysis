from datetime import datetime, timezone

from src.strategies.genge_opportunity_discovery.generation_freshness import (
    evaluate_generation_freshness,
    expected_latest_trade_date,
)


def _canonical(trade_date="2026-09-30"):
    return {
        "generated_at": "2026-09-30T09:00:00+00:00",
        "latest_trade_date": trade_date,
        "source_run_id": "36826306197",
    }


def test_national_day_closure_keeps_sep30_as_latest_completed_session():
    for day in range(1, 8):
        evaluated = datetime(2026, 10, day, 15, 30, tzinfo=timezone.utc)  # 23:30 Shanghai
        assert expected_latest_trade_date(evaluated).isoformat() == "2026-09-30"
        result = evaluate_generation_freshness(
            _canonical(),
            market_regime={"as_of_date": "2026-09-30"},
            evaluated_at=evaluated,
            strict_missing_metadata=True,
        )
        assert result["status"] == "OK"
        assert result["fresh"] is True
        assert result["expected_min_trade_date"] == "2026-09-30"
        assert result["holiday_calendar_mode"] == "OFFICIAL_SSE_2026"
        assert result["holiday_calendar_source"] == "SSE_2026_NOTICE_2025_45"


def test_oct8_before_settlement_still_accepts_sep30():
    evaluated = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)  # 15:00 Shanghai
    assert expected_latest_trade_date(evaluated).isoformat() == "2026-09-30"


def test_oct8_after_settlement_requires_oct8_and_fails_closed_on_sep30():
    evaluated = datetime(2026, 10, 8, 8, 30, tzinfo=timezone.utc)  # 16:30 Shanghai
    assert expected_latest_trade_date(evaluated).isoformat() == "2026-10-08"
    result = evaluate_generation_freshness(
        _canonical(),
        market_regime={"as_of_date": "2026-09-30"},
        evaluated_at=evaluated,
        strict_missing_metadata=True,
    )
    assert result["status"] == "STALE_UPSTREAM"
    assert result["formal_new_exposure_allowed"] is False
    assert "CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION" in result["reasons"]
    assert "MARKET_CONTEXT_BEHIND_COMPLETED_SESSION" in result["reasons"]
