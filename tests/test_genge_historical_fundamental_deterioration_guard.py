from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_fundamental_deterioration_guard import (
    FundamentalExitPolicy,
    first_fundamental_exit,
)


def _data() -> HistoricalCompanyData:
    start = date(2021, 1, 1)
    end = date(2023, 6, 2)
    price_rows = []
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        # Keep the fixture's long-run price at 100, then model a recent
        # deterioration-driven break to 80 shortly before the 2023-04-20
        # warning. This preserves a meaningful below-MA60 confirmation while
        # also covering the next-open execution date and original exit date.
        close = 100.0 if day < date(2023, 4, 1) else 80.0
        price_rows.append({
            "date": day, "open": close, "high": close * 1.01,
            "low": close * 0.99, "close": close,
            "volume": 1_000_000, "amount": close * 1_000_000,
        })
    financial = pd.DataFrame([
        {
            "report_date": date(2020, 12, 31), "disclosure_date": date(2021, 4, 20),
            "recurring_profit": 100.0, "cash_conversion_ratio": 1.0, "roe": 15.0, "debt_ratio": 30.0,
        },
        {
            "report_date": date(2021, 12, 31), "disclosure_date": date(2022, 4, 20),
            "recurring_profit": 120.0, "cash_conversion_ratio": 1.0, "roe": 15.0, "debt_ratio": 30.0,
        },
        {
            "report_date": date(2022, 12, 31), "disclosure_date": date(2023, 4, 20),
            "recurring_profit": 70.0, "cash_conversion_ratio": 1.0, "roe": 3.0, "debt_ratio": 80.0,
        },
    ])
    return HistoricalCompanyData(
        code="600001", stock_name="fixture", price_df=pd.DataFrame(price_rows),
        valuation_df=pd.DataFrame(), financial_df=financial, warnings=[],
    )


def _event():
    return {
        "event_id": "600001:0:2022-04-21", "code": "600001", "stock_name": "fixture",
        "signal_date": date(2022, 4, 21), "entry_date": date(2022, 4, 22),
        "exit_date": date(2023, 6, 1), "entry_price": 100.0, "exit_price": 80.0,
        "exit_reason": "ORIGINAL",
    }


def test_warning_exit_uses_next_open_and_sell_friction():
    data = _data()
    event = _event()
    policy = FundamentalExitPolicy("rule", "score_drop15_and_yoy_negative")
    result = first_fundamental_exit(data, event, policy=policy, cost_bps_per_side=15.0)

    assert result is not None
    assert result["warning_date"] == date(2023, 4, 20)
    assert result["execution_date"] == date(2023, 4, 21)
    assert result["raw_execution_open"] == 80.0
    assert result["exit_price_after_friction"] == pytest.approx(80.0 * (1 - 0.0015))
    assert result["decision_after_close_for_next_open"] is True


def test_ma60_confirmation_is_evaluated_on_warning_date_only():
    data = _data()
    event = _event()
    policy = FundamentalExitPolicy(
        "rule_ma", "score_drop15_and_yoy_negative", require_below_ma60=True,
    )
    result = first_fundamental_exit(data, event, policy=policy, cost_bps_per_side=0.0)

    assert result is not None
    assert result["warning_date"] == date(2023, 4, 20)
    assert result["price_confirmed_below_ma60"] is True
    assert result["warning_close"] < result["warning_ma60"]


def test_future_deterioration_after_original_exit_cannot_replace_exit():
    data = _data()
    event = _event()
    event["exit_date"] = date(2023, 4, 1)
    policy = FundamentalExitPolicy("rule", "score_drop15_and_yoy_negative")
    result = first_fundamental_exit(data, event, policy=policy, cost_bps_per_side=15.0)

    assert result is None


def test_policy_rejects_unknown_warning_rule():
    with pytest.raises(ValueError):
        FundamentalExitPolicy("bad", "future_magic")
