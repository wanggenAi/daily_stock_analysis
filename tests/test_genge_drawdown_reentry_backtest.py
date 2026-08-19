from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_opportunity_discovery.drawdown_reentry_backtest import (
    ReentryRiskPolicy,
    simulate_company_with_reentry,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    HistoricalCompanyData,
)


def _synthetic_data() -> HistoricalCompanyData:
    start = date(2020, 1, 1)
    sessions = 460
    prices = []
    valuations = []
    for i in range(sessions):
        day = start + timedelta(days=i)
        if i < 180:
            close = 20.0
            pe = 20.0
        elif i < 205:
            close = 12.0
            pe = 12.0
        elif i < 220:
            close = 9.0
            pe = 9.0
        elif i < 320:
            close = 12.0
            pe = 12.0
        else:
            close = 24.0
            pe = 30.0
        prices.append(
            {
                "date": day,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000,
                "amount": 20_000_000,
            }
        )
        valuations.append({"date": day, "pe": pe})

    financials = pd.DataFrame(
        [
            {
                "report_date": date(2019, 12, 31),
                "disclosure_date": date(2020, 1, 10),
                "recurring_profit": 100.0,
                "net_profit": 100.0,
                "cash_conversion_ratio": 1.0,
                "operating_cash_flow": 100.0,
                "roe": 15.0,
                "debt_ratio": 30.0,
            },
            {
                "report_date": date(2020, 3, 31),
                "disclosure_date": date(2020, 4, 20),
                "recurring_profit": 30.0,
                "net_profit": 30.0,
                "cash_conversion_ratio": 1.0,
                "operating_cash_flow": 30.0,
                "roe": 15.0,
                "debt_ratio": 30.0,
            },
            {
                "report_date": date(2020, 6, 30),
                "disclosure_date": date(2020, 8, 20),
                "recurring_profit": 65.0,
                "net_profit": 65.0,
                "cash_conversion_ratio": 1.0,
                "operating_cash_flow": 65.0,
                "roe": 15.0,
                "debt_ratio": 30.0,
            },
        ]
    )
    return HistoricalCompanyData(
        code="600001",
        stock_name="测试公司",
        price_df=pd.DataFrame(prices),
        valuation_df=pd.DataFrame(valuations),
        financial_df=financials,
        warnings=[],
    )


def test_risk_exit_can_reenter_only_after_fresh_original_buy_signal():
    data = _synthetic_data()
    policy = ReentryRiskPolicy(
        name="test_reentry",
        initial_stop_pct=18.0,
        breakeven_activation_pct=50.0,
        breakeven_floor_pct=1.0,
        trailing_activation_pct=100.0,
        trailing_drawdown_pct=35.0,
        reentry_cooldown_sessions=10,
    )
    trades, signals, curve, case = simulate_company_with_reentry(
        data,
        start_date=date(2020, 1, 1),
        end_date=date(2021, 4, 4),
        policy=policy,
        evaluation_stride=5,
        cost_bps_per_side=0.0,
    )

    assert case["risk_exit_count"] >= 1
    assert case["signal_confirmed_reentry_count"] >= 1
    assert sum(signal["signal_action"] == "BUY" for signal in signals) >= 2
    assert any(trade["exit_reason"] == "SELL_RISK_INITIAL_LOSS_LIMIT" for trade in trades)
    assert len(curve) > 100


def test_reentry_policy_never_enters_without_original_buy_signal():
    data = _synthetic_data()
    data.valuation_df["pe"] = 50.0
    policy = ReentryRiskPolicy("no_buy", 18.0, 50.0, 1.0, 100.0, 35.0, 10)
    trades, signals, _, case = simulate_company_with_reentry(
        data,
        start_date=date(2020, 1, 1),
        end_date=date(2021, 4, 4),
        policy=policy,
        evaluation_stride=5,
        cost_bps_per_side=0.0,
    )
    assert not trades
    assert not [signal for signal in signals if signal["signal_action"] == "BUY"]
    assert case["entry_count"] == 0
