from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_opportunity_discovery.drawdown_overlay_backtest import (
    RiskOverlayPolicy,
    apply_risk_overlay_to_trade,
    equal_weight_portfolio,
    equity_curve_from_trades,
    risk_exit_reason,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    HistoricalCompanyData,
)


def _policy() -> RiskOverlayPolicy:
    return RiskOverlayPolicy(
        name="test",
        initial_stop_pct=15.0,
        breakeven_activation_pct=25.0,
        breakeven_floor_pct=2.0,
        trailing_activation_pct=40.0,
        trailing_drawdown_pct=20.0,
    )


def _data(closes: list[float]) -> HistoricalCompanyData:
    start = date(2025, 1, 2)
    rows = []
    for i, close in enumerate(closes):
        rows.append(
            {
                "date": start + timedelta(days=i),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000,
                "amount": 10_000_000,
            }
        )
    return HistoricalCompanyData(
        code="600001",
        stock_name="测试",
        price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(),
        financial_df=pd.DataFrame(),
        warnings=[],
    )


def test_initial_loss_limit_triggers_before_catastrophic_drawdown():
    assert risk_exit_reason(
        entry_price=100.0,
        peak_close=100.0,
        close=84.0,
        policy=_policy(),
    ) == "SELL_RISK_INITIAL_LOSS_LIMIT"


def test_trailing_profit_protection_activates_only_after_large_runup():
    policy = _policy()
    assert risk_exit_reason(
        entry_price=100.0,
        peak_close=130.0,
        close=103.0,
        policy=policy,
    ) is None
    assert risk_exit_reason(
        entry_price=100.0,
        peak_close=150.0,
        close=119.0,
        policy=policy,
    ) == "SELL_RISK_TRAILING_PROFIT_PROTECTION"


def test_overlay_keeps_entry_frozen_and_exits_next_open_after_risk_trigger():
    data = _data([100, 110, 150, 145, 118, 117, 116])
    start = date(2025, 1, 2)
    baseline = {
        "code": "600001",
        "stock_name": "测试",
        "entry_date": start,
        "entry_price": 100.0,
        "exit_date": start + timedelta(days=6),
        "exit_price": 116.0,
        "exit_reason": "END_OF_TEST_MARK_TO_MARKET",
        "net_return_pct": 16.0,
        "gross_return_pct": 16.0,
    }

    overlay = apply_risk_overlay_to_trade(data, baseline, _policy(), cost_bps_per_side=0.0)

    assert overlay["entry_date"] == baseline["entry_date"]
    assert overlay["entry_price"] == baseline["entry_price"]
    assert overlay["risk_overlay_exit"] is True
    assert overlay["exit_reason"] == "SELL_RISK_TRAILING_PROFIT_PROTECTION"
    assert overlay["exit_date"] == start + timedelta(days=5)
    assert overlay["exit_price"] == 117.0


def test_equity_curve_holds_cash_after_early_exit():
    data = _data([100, 90, 80, 70, 60])
    start = date(2025, 1, 2)
    trade = {
        "entry_date": start,
        "entry_price": 100.0,
        "exit_date": start + timedelta(days=2),
        "exit_price": 80.0,
        "exit_reason": "SELL_RISK_INITIAL_LOSS_LIMIT",
    }
    curve = equity_curve_from_trades(
        data,
        [trade],
        start_date=start,
        end_date=start + timedelta(days=4),
    )
    assert round(float(curve.iloc[-1]), 6) == 0.8
    assert round(float(curve.iloc[-2]), 6) == 0.8


def test_equal_weight_portfolio_dilutes_single_name_drawdown():
    index = pd.Index([date(2025, 1, 2), date(2025, 1, 3)], name="date")
    a = pd.Series([1.0, 0.8], index=index)
    b = pd.Series([1.0, 1.0], index=index)
    portfolio = equal_weight_portfolio([a, b])
    assert round(float(portfolio.iloc[-1]), 6) == 0.9
