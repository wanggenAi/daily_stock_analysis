"""Regression tests for concurrent investor brief replays after a newer session."""
import pytest

from scripts.guard_investor_report_epoch import assert_no_regressive_epoch


def test_older_replayed_canonical_cannot_replace_newer_published_market_epoch():
    with pytest.raises(ValueError, match="regressive_market_epoch"):
        assert_no_regressive_epoch(
            {"latest_trade_date": "2026-09-24", "canonical_snapshot_id": "newer"},
            {"latest_trade_date": "2026-09-21", "canonical_snapshot_id": "older"},
        )


def test_later_genuine_market_session_may_replace_previous_report():
    assert_no_regressive_epoch(
        {"latest_trade_date": "2026-09-24"},
        {"latest_trade_date": "2026-09-28"},
    )


def test_same_session_overlay_may_rerender_without_new_authority():
    assert_no_regressive_epoch(
        {"latest_trade_date": "2026-09-24"},
        {"latest_trade_date": "2026-09-24"},
    )


@pytest.mark.parametrize("invalid", ["", "UNKNOWN", "2026-09-28T15:00", None])
def test_unknown_candidate_date_fails_closed(invalid):
    with pytest.raises(ValueError, match="candidate"):
        assert_no_regressive_epoch(
            {"latest_trade_date": "2026-09-24"},
            {"latest_trade_date": invalid},
        )


def test_invalid_prior_report_cannot_be_silently_overwritten():
    with pytest.raises(ValueError, match="previous"):
        assert_no_regressive_epoch(
            {"latest_trade_date": ""},
            {"latest_trade_date": "2026-09-28"},
        )


def test_fresh_first_publication_requires_candidate_market_date():
    assert_no_regressive_epoch(None, {"latest_trade_date": "2026-09-28"})
