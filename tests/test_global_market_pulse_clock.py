from datetime import datetime, timezone

from tools.run_global_market_pulse import (
    _latest_completed_a_share_trade_date,
    _resolve_a_share_last_trade_date,
)


def test_sunday_20261011_resolves_latest_completed_a_share_session_to_20261009():
    now = datetime(2026, 10, 11, 8, 0, tzinfo=timezone.utc)
    assert _latest_completed_a_share_trade_date(now) == "2026-10-09"
    assert _resolve_a_share_last_trade_date({"latest_trade_date": "2026-10-08"}, now) == "2026-10-09"


def test_open_session_is_not_treated_as_completed_before_close():
    # 2026-10-09 06:00 UTC == 14:00 Asia/Shanghai, before the 15:00 close.
    now = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)
    assert _latest_completed_a_share_trade_date(now) == "2026-10-08"


def test_completed_session_becomes_anchor_after_exchange_close():
    # 2026-10-09 07:01 UTC is just after the 15:00 Asia/Shanghai close.
    now = datetime(2026, 10, 9, 7, 1, tzinfo=timezone.utc)
    assert _latest_completed_a_share_trade_date(now) == "2026-10-09"
