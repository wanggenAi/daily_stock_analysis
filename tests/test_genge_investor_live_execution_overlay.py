from datetime import datetime, timezone

import pytest

from src.strategies.genge_opportunity_discovery.investor_live_execution_overlay import (
    apply_live_execution_overlay,
    render_live_markdown,
)


def _dashboard():
    return {
        "contract_version": "GEN_GE_INVESTOR_DECISION_DASHBOARD_V2",
        "canonical_snapshot_id": "snap-1",
        "no_auto_trade": True,
        "headline": "old",
        "market": {"status": "YELLOW", "allow_new_buy": True, "position_multiplier": 0.5},
        "stock_portfolio": {
            "rows": [
                {"code": "601318", "name": "中国平安", "quantity": 300, "average_cost": 57.0,
                 "current_price": 56.0, "formal_action": "HOLD_REVIEW", "investor_action": "持有观察"},
                {"code": "600406", "name": "国电南瑞", "quantity": 200, "average_cost": 23.0,
                 "current_price": 22.5, "formal_action": "ADD", "investor_action": "加仓"},
            ]
        },
        "terminal_opportunities": {
            "buy_now": [{"code": "600036", "name": "招商银行", "current_price": 40.0,
                         "formal_buy_authorized": True, "neutral_value": 55.0, "buy_ratio": 0.8}],
            "wait_price": [{"code": "601899", "name": "紫金矿业", "current_price": 34.0,
                            "wait_price_max": 32.0}],
            "reject_count": 1,
        },
        "capital_deployment": {
            "status": "READY", "available_cash_cny": 70000.0, "capital_as_of": "2026-09-03T12:17:00+08:00",
            "planner_config": {"max_deployment_ratio": 0.7, "max_single_name_ratio_of_available_cash": 0.2,
                               "max_names": 5, "first_tranche_ratio": 0.5, "second_tranche_discount_pct": 0.02},
            "planned_immediate_cash_cny": 0,
        },
        "decision_summary": {"planned_immediate_cash_cny": 0},
    }


def _hourly():
    return {
        "canonical_snapshot_id": "snap-1",
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "rows": [
            {"code": "601318", "latest_price": 58.3, "latest_price_status": "OK",
             "latest_price_observed_at": "2026-09-03T11:53:32+08:00", "latest_price_provider": "tencent_quote"},
            {"code": "600406", "latest_price": 23.2, "latest_price_status": "OK",
             "latest_price_observed_at": "2026-09-03T11:53:54+08:00", "latest_price_provider": "tencent_quote"},
            {"code": "600036", "latest_price": 45.0, "latest_price_status": "OK",
             "latest_price_observed_at": "2026-09-03T11:53:40+08:00", "latest_price_provider": "tencent_quote"},
            {"code": "601899", "latest_price": 33.5, "latest_price_status": "OK",
             "latest_price_observed_at": "2026-09-03T11:53:42+08:00", "latest_price_provider": "tencent_quote"},
        ],
    }


def _now():
    return datetime(2026, 9, 3, 4, 20, tzinfo=timezone.utc)


def test_live_quotes_replace_display_prices_but_never_formal_actions():
    payload = apply_live_execution_overlay(_dashboard(), _hourly(), now=_now())
    rows = {x["code"]: x for x in payload["stock_portfolio"]["rows"]}
    assert rows["601318"]["current_price"] == 58.3
    assert rows["601318"]["canonical_price"] == 56.0
    assert rows["601318"]["formal_action"] == "HOLD_REVIEW"
    assert rows["601318"]["price_source"] == "HOURLY_FRESH_EXECUTION_QUOTE"
    assert rows["601318"]["pnl_pct"] == pytest.approx(2.28, abs=0.01)
    assert rows["600406"]["formal_action"] == "ADD"
    assert payload["live_execution_overlay"]["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True


def test_planner_uses_conservative_authorized_limit_when_live_price_rises():
    payload = apply_live_execution_overlay(_dashboard(), _hourly(), now=_now())
    operations = {x["code"]: x for x in payload["capital_deployment"]["operations"]}

    # Holding ADD was authorized at frozen 22.5; fresh 23.2 may be displayed but
    # the execution plan must not chase above the frozen authorized price.
    add = operations["600406"]
    assert add["live_market_price"] == 23.2
    assert add["first_entry_max_price"] == 22.5
    assert add["immediate_execution_eligible"] is False
    assert add["action"] == "ADD_LIMIT"

    # Terminal BUY has an explicit 0.8 * 55 = 44 ceiling.  Live 45 therefore
    # becomes a manual limit-only instruction at no more than 44.
    buy = operations["600036"]
    assert buy["live_market_price"] == 45.0
    assert buy["first_entry_max_price"] == 44.0
    assert buy["immediate_execution_eligible"] is False
    assert buy["action"] == "BUY_LIMIT"
    assert all(x["automatic_order_allowed"] is False for x in operations.values())


def test_wait_price_threshold_is_not_changed_by_live_quote():
    payload = apply_live_execution_overlay(_dashboard(), _hourly(), now=_now())
    wait = payload["terminal_opportunities"]["wait_price"][0]
    assert wait["current_price"] == 33.5
    assert wait["terminal_reference_price"] == 34.0
    assert wait["wait_price_max"] == 32.0
    reservation = payload["capital_deployment"]["wait_price_reservations"][0]
    assert reservation["first_entry_max_price"] == 32.0
    assert reservation["immediate_execution_eligible"] is False


def test_stale_or_mismatched_hourly_data_fails_closed():
    stale = _hourly()
    payload = apply_live_execution_overlay(
        _dashboard(), stale,
        now=datetime(2026, 9, 3, 8, 30, tzinfo=timezone.utc),
        max_age_minutes=120,
    )
    row = payload["stock_portfolio"]["rows"][0]
    assert row["current_price"] == 56.0
    assert row["price_source"] == "CANONICAL_FROZEN_PRICE"
    assert payload["live_execution_overlay"]["applied_code_count"] == 0

    bad = _hourly(); bad["canonical_snapshot_id"] = "other"
    with pytest.raises(ValueError, match="canonical snapshot mismatch"):
        apply_live_execution_overlay(_dashboard(), bad, now=_now())


def test_markdown_calls_out_live_quote_scope_and_keeps_system_last():
    payload = apply_live_execution_overlay(_dashboard(), _hourly(), now=_now())
    text = render_live_markdown(payload)
    assert "盘中执行价覆盖" in text
    assert "正式动作仍来自冻结 Canonical" in text
    assert text.index("## 2. 我的持仓怎么办") < text.index("## 5. 资金怎么花")
