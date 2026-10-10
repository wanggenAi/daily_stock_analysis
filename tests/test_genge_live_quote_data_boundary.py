from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from scripts.genge_apply_live_quote_snapshot import apply_snapshot
from scripts.genge_live_quote_snapshot import build_snapshot
from src.strategies.genge_opportunity_discovery.hourly_deep_overlay import Quote


def _dashboard() -> dict:
    return {
        "canonical_snapshot_id": "canon-1",
        "canonical_source_run_id": "run-1",
        "stock_portfolio": {
            "rows": [
                {
                    "code": "600406",
                    "formal_action": "HOLD",
                    "current_price": 22.0,
                    "canonical_price": 22.0,
                    "average_cost": 23.0,
                }
            ]
        },
        "terminal_opportunities": {"buy_now": [], "wait_price": []},
        "capital_deployment": {
            "available_cash_cny": 50000,
            "planned_immediate_cash_cny": 0,
            "operations": [],
        },
    }


def test_live_quote_producer_is_data_only_and_does_not_mutate_dashboard():
    dashboard = _dashboard()
    before = deepcopy(dashboard)
    now = datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc)  # 10:00 Beijing, active session

    def provider(codes):
        assert list(codes) == ["600406"]
        return {
            "600406": Quote(
                code="600406",
                name="国电南瑞",
                price=22.5,
                previous_close=22.0,
                change_pct=2.27,
                observed_at="2026-10-09T02:00:00+00:00",
                provider="TEST",
                status="OK",
            )
        }

    snapshot = build_snapshot(dashboard, now=now, provider=provider)
    assert dashboard == before
    assert snapshot["producer_role"] == "DATA_ACQUISITION_ONLY"
    assert snapshot["formal_action_authority"] == "NONE"
    assert snapshot["formal_action_recomputed"] is False
    assert snapshot["automatic_execution_allowed"] is False
    assert snapshot["ok_quote_count"] == 1


def test_off_session_producer_never_calls_network_provider():
    dashboard = _dashboard()
    now = datetime(2026, 10, 10, 2, 0, tzinfo=timezone.utc)  # Saturday

    def forbidden_provider(_codes):
        raise AssertionError("off-session producer must not fetch quotes")

    snapshot = build_snapshot(dashboard, now=now, provider=forbidden_provider)
    assert snapshot["market_session_active"] is False
    assert snapshot["ok_quote_count"] == 0
    assert snapshot["formal_action_authority"] == "NONE"


def test_quote_consumer_fails_closed_on_canonical_lineage_mismatch():
    dashboard = _dashboard()
    snapshot = {
        "contract": "GEN_GE_LIVE_EXECUTION_QUOTE_SNAPSHOT_V1",
        "formal_action_authority": "NONE",
        "formal_action_recomputed": False,
        "canonical_snapshot_id": "different-canonical",
        "canonical_source_run_id": "run-2",
        "market_session_active": True,
        "rows": [],
    }
    with pytest.raises(ValueError, match="lineage mismatch"):
        apply_snapshot(dashboard, snapshot)
