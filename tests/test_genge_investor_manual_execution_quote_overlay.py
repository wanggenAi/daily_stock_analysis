from datetime import datetime, timezone

import pytest

from src.strategies.genge_opportunity_discovery.investor_manual_execution_quote_overlay import (
    MANUAL_PRICE_SOURCE,
    apply_manual_broker_quote_overlay,
)


def _dashboard():
    return {
        "contract_version": "GEN_GE_INVESTOR_DECISION_DASHBOARD_V3",
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_holding_actions_currently_usable": True,
        "holdings_reconciliation": {
            "status": "HOLDINGS_IN_SYNC",
            "in_sync": True,
            "formal_holding_actions_currently_usable": True,
        },
        "no_auto_trade": True,
        "headline": "old",
        "market": {
            "status": "YELLOW",
            "allow_new_buy": True,
            "position_multiplier": 0.5,
        },
        "stock_portfolio": {
            "rows": [
                {
                    "code": "601318",
                    "name": "中国平安",
                    "quantity": 400,
                    "average_cost": 55.9658,
                    "current_price": 56.26,
                    "formal_action": "HOLD",
                    "formal_action_currently_usable": True,
                    "action_authority": "FORMAL",
                    "investor_action": "继续持有",
                    "holding_add_authorized": False,
                },
                {
                    "code": "603993",
                    "name": "洛阳钼业",
                    "quantity": 900,
                    "average_cost": 18.8163,
                    "current_price": 19.09,
                    "formal_action": "HOLD",
                    "formal_action_currently_usable": True,
                    "action_authority": "FORMAL",
                    "investor_action": "继续持有；可分批加仓1手",
                    "holding_add_authorized": True,
                },
            ]
        },
        "terminal_opportunities": {
            "buy_now": [],
            "wait_price": [],
            "reject_count": 0,
        },
        "capital_deployment": {
            "status": "READY",
            "available_cash_cny": 60000.0,
            "capital_as_of": "2026-09-10T10:36:40+08:00",
            "planner_config": {
                "max_deployment_ratio": 0.70,
                "max_single_name_ratio_of_available_cash": 0.20,
                "max_names": 5,
                "first_tranche_ratio": 0.50,
                "second_tranche_discount_pct": 0.02,
            },
            "planned_immediate_cash_cny": 1909.0,
        },
        "decision_summary": {"planned_immediate_cash_cny": 1909.0},
    }


def _manual(price_603993=18.94):
    return {
        "contract": "GEN_GE_USER_CONFIRMED_BROKER_INTRADAY_QUOTES_V1",
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "observed_at": "2026-09-10T11:17:38+08:00",
        "evidence_authority": "USER_CONFIRMED_BROKER_SCREENSHOT",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
        "broker": "CITIC_SECURITIES",
        "quotes": [
            {"code": "601318", "latest_price": 55.40, "status": "OK"},
            {"code": "603993", "latest_price": price_603993, "status": "OK"},
        ],
    }


def _now():
    return datetime(2026, 9, 10, 3, 30, tzinfo=timezone.utc)


def test_user_confirmed_broker_quotes_update_prices_without_changing_authority():
    payload = apply_manual_broker_quote_overlay(_dashboard(), _manual(), now=_now())
    rows = {row["code"]: row for row in payload["stock_portfolio"]["rows"]}

    assert rows["601318"]["current_price"] == 55.40
    assert rows["601318"]["canonical_price"] == 56.26
    assert rows["601318"]["formal_action"] == "HOLD"
    assert rows["601318"]["price_source"] == MANUAL_PRICE_SOURCE
    assert rows["601318"]["pnl_pct"] == pytest.approx(-1.01, abs=0.01)
    assert rows["603993"]["current_price"] == 18.94
    assert rows["603993"]["formal_action"] == "HOLD"
    assert payload["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True

    overlay = payload["live_execution_overlay"]
    assert overlay["source"] == MANUAL_PRICE_SOURCE
    assert overlay["applied_code_count"] == 2
    assert overlay["formal_trading_authority"] is False
    assert overlay["automatic_formal_buy_allowed"] is False
    assert overlay["no_auto_trade"] is True


def test_staged_holding_add_never_chases_above_frozen_canonical_price():
    payload = apply_manual_broker_quote_overlay(
        _dashboard(), _manual(price_603993=19.50), now=_now()
    )
    op = next(
        row
        for row in payload["capital_deployment"]["operations"]
        if row["code"] == "603993"
    )
    assert op["source"] == "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD"
    assert op["live_market_price"] == 19.50
    assert op["first_entry_max_price"] == 19.09
    assert op["immediate_execution_eligible"] is False
    assert op["action"] == "ADD_LIMIT"
    assert op["automatic_order_allowed"] is False
    assert op["no_auto_trade"] is True


def test_stale_or_superseded_manual_snapshot_is_safe_noop():
    stale = _manual()
    original = _dashboard()
    original["live_execution_overlay"] = {"source": "HOURLY", "applied_code_count": 2}
    payload = apply_manual_broker_quote_overlay(
        original,
        stale,
        now=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        max_age_minutes=120,
    )
    assert payload == original

    wrong_lineage = _manual()
    wrong_lineage["canonical_snapshot_id"] = "old-snapshot"
    payload = apply_manual_broker_quote_overlay(
        original, wrong_lineage, now=_now()
    )
    assert payload == original


def test_manual_quote_authority_violation_fails_closed():
    bad = _manual()
    bad["formal_trading_authority"] = True
    with pytest.raises(ValueError, match="Formal trading authority"):
        apply_manual_broker_quote_overlay(_dashboard(), bad, now=_now())

    bad = _manual()
    bad["no_auto_trade"] = False
    with pytest.raises(ValueError, match="no-auto-trade"):
        apply_manual_broker_quote_overlay(_dashboard(), bad, now=_now())
