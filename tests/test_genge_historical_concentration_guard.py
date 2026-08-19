from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import (
    ConcentrationGuardPolicy,
    replay_with_concentration_guard,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import PortfolioConstructionPolicy


def _data(code: str, bars: list[tuple[float, float]]) -> HistoricalCompanyData:
    start = date(2025, 1, 2)
    rows = []
    for i, (open_price, close) in enumerate(bars):
        rows.append(
            {
                "date": start + timedelta(days=i),
                "open": open_price,
                "high": max(open_price, close) * 1.01,
                "low": min(open_price, close) * 0.99,
                "close": close,
                "volume": 1_000_000,
                "amount": 20_000_000,
            }
        )
    return HistoricalCompanyData(
        code=code,
        stock_name=code,
        price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(),
        financial_df=pd.DataFrame(),
        warnings=[],
    )


def _event(code: str, *, exit_offset: int = 4) -> dict:
    start = date(2025, 1, 2)
    return {
        "event_id": f"{code}:0",
        "code": code,
        "stock_name": code,
        "signal_date": start,
        "entry_date": start + timedelta(days=1),
        "exit_date": start + timedelta(days=exit_offset),
        "entry_price": 100.0,
        "exit_price": 150.0,
        "signal": {},
        "signal_rank": (1.0, 70.0, 10.0, -20.0, code),
        "reference_entry": 100.0,
        "risk_geometry": {
            "status": "OK",
            "stop_price": 97.0,
            "stop_distance_pct": 3.0,
            "source": "test",
        },
    }


def _entry_policy() -> PortfolioConstructionPolicy:
    return PortfolioConstructionPolicy(
        name="risk075_open4",
        mode="risk_budget",
        risk_per_trade_pct=0.75,
        max_single_name_fraction=0.20,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=4.0,
    )


def test_guard_policy_requires_target_below_trigger():
    with pytest.raises(ValueError):
        ConcentrationGuardPolicy("bad", trigger_fraction=0.30, target_fraction=0.30)


def test_profit_alone_does_not_trim_below_concentration_threshold():
    code = "600001"
    data = _data(code, [(100, 100), (100, 100), (170, 170), (170, 170), (170, 170)])
    guard = ConcentrationGuardPolicy(
        "guard", trigger_fraction=0.35, target_fraction=0.25,
        min_holding_sessions=0, cooldown_sessions=20, trim_cost_bps=0.0,
    )
    _, allocations, trims, audit = replay_with_concentration_guard(
        [_event(code)],
        {code: data},
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 6),
        entry_policy=_entry_policy(),
        guard_policy=guard,
    )

    assert allocations[0]["allocated_pct"] == 20.0
    assert trims == []
    assert audit["trim_count"] == 0


def test_trim_shares_are_frozen_at_close_and_execute_next_open():
    code = "600002"
    # Day 2 close at 300 pushes a 20% initial position above the 35% weight
    # trigger.  Day 3 opens at only 150.  The guard must still sell the number
    # of shares frozen from day-2 close rather than recomputing from day-3 open.
    data = _data(code, [(100, 100), (100, 100), (300, 300), (150, 150), (150, 150)])
    guard = ConcentrationGuardPolicy(
        "guard", trigger_fraction=0.35, target_fraction=0.25,
        min_holding_sessions=0, cooldown_sessions=20, trim_cost_bps=0.0,
    )
    _, _, trims, audit = replay_with_concentration_guard(
        [_event(code)],
        {code: data},
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 6),
        entry_policy=_entry_policy(),
        guard_policy=guard,
    )

    assert len(trims) == 1
    trim = trims[0]
    assert trim["decision_date"] == date(2025, 1, 4)
    assert trim["execution_date"] == date(2025, 1, 5)
    assert trim["execution_open"] == 150.0
    # Entry shares = 0.2 / 100 = .002.  At the trigger close, equity=1.4,
    # target mark=.35 and current mark=.6, so frozen shares=(.6-.35)/300.
    assert trim["shares_sold"] == pytest.approx((0.6 - 0.35) / 300.0)
    assert trim["shares_frozen_before_open"] is True
    assert audit["trim_count"] == 1


def test_trim_cost_is_charged_as_extra_one_way_friction():
    code = "600003"
    data = _data(code, [(100, 100), (100, 100), (300, 300), (300, 300), (150, 150)])
    guard = ConcentrationGuardPolicy(
        "guard", trigger_fraction=0.35, target_fraction=0.25,
        min_holding_sessions=0, cooldown_sessions=20, trim_cost_bps=20.0,
    )
    _, _, trims, audit = replay_with_concentration_guard(
        [_event(code)],
        {code: data},
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 6),
        entry_policy=_entry_policy(),
        guard_policy=guard,
    )

    assert len(trims) == 1
    expected_cost = trims[0]["gross_proceeds"] * 20.0 / 10_000.0
    assert trims[0]["friction_cost"] == pytest.approx(expected_cost)
    assert audit["trim_friction_cost_dollars"] == pytest.approx(round(expected_cost, 8))
