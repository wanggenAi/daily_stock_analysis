from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.strategies.genge_opportunity_discovery.canonical_promotion_window import (
    assert_canonical_promotion_window_open,
    evaluate_canonical_promotion_window,
)


def test_oct8_incident_window_blocks_formal_promotion_before_settlement() -> None:
    # 2026-10-08 14:37 Asia/Shanghai: first A-share session after the
    # National Day closure is still in progress. Sep30 data may be used for
    # research, but must not overwrite the formal canonical for Oct8.
    result = evaluate_canonical_promotion_window(
        evaluated_at=datetime(2026, 10, 8, 6, 37, tzinfo=timezone.utc)
    )
    assert result["status"] == "BLOCKED_PENDING_SESSION"
    assert result["canonical_promotion_allowed"] is False
    assert result["session_day"] is True
    assert result["shanghai_time"] == "14:37:00"
    assert result["reasons"] == ["CURRENT_ASHARE_SESSION_NOT_SETTLED"]

    with pytest.raises(ValueError, match="PRE_SETTLEMENT_CANONICAL_PROMOTION_REFUSED"):
        assert_canonical_promotion_window_open(
            evaluated_at=datetime(2026, 10, 8, 6, 37, tzinfo=timezone.utc)
        )


def test_oct8_postclose_window_allows_promotion_then_freshness_decides_trade_date() -> None:
    # 18:30 Shanghai: promotion window is open. The separate generation
    # freshness contract will then require the canonical to carry Oct8 data.
    result = evaluate_canonical_promotion_window(
        evaluated_at=datetime(2026, 10, 8, 10, 30, tzinfo=timezone.utc)
    )
    assert result["status"] == "OPEN"
    assert result["canonical_promotion_allowed"] is True
    assert result["session_day"] is True
    assert result["shanghai_time"] == "18:30:00"


def test_national_day_holiday_does_not_create_false_pending_session() -> None:
    result = evaluate_canonical_promotion_window(
        evaluated_at=datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
    )
    assert result["status"] == "OPEN"
    assert result["canonical_promotion_allowed"] is True
    assert result["session_day"] is False
    assert result["holiday_calendar_mode"] == "OFFICIAL_SSE_2026"


def test_weekend_does_not_create_false_pending_session() -> None:
    result = evaluate_canonical_promotion_window(
        evaluated_at=datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc)
    )
    assert result["status"] == "OPEN"
    assert result["canonical_promotion_allowed"] is True
    assert result["session_day"] is False


def test_production_cli_calls_promotion_gate_before_finalization(monkeypatch, tmp_path) -> None:
    from src.strategies.genge_opportunity_discovery import canonical_authority

    called = {"gate": False}

    def refuse() -> dict:
        called["gate"] = True
        raise ValueError("PRE_SETTLEMENT_CANONICAL_PROMOTION_REFUSED")

    monkeypatch.setattr(canonical_authority, "assert_canonical_promotion_window_open", refuse)

    with pytest.raises(ValueError, match="PRE_SETTLEMENT_CANONICAL_PROMOTION_REFUSED"):
        canonical_authority.main(
            [
                "--snapshot",
                str(tmp_path / "does-not-need-to-exist.json"),
                "--output-dir",
                str(tmp_path / "out"),
                "--expected-source-run-id",
                "123",
                "--source-workflow",
                "GenGe V3.1.1 Every-Industry Research",
                "--source-head-sha",
                "a" * 40,
                "--finalizer-run-id",
                "456",
                "--finalizer-code-sha",
                "b" * 40,
            ]
        )
    assert called["gate"] is True
