from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd

from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
)
from src.strategies.genge_opportunity_discovery.winner_concentration_trim_backtest import (
    WinnerTrimPolicy,
    replay_with_winner_trim,
)


def _data(code: str, prices: list[float], start: date = date(2024, 1, 2)):
    rows = []
    for idx, price in enumerate(prices):
        day = start + timedelta(days=idx)
        rows.append({
            "date": day,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1_000_000,
        })
    return SimpleNamespace(code=code, stock_name=code, price_df=pd.DataFrame(rows))


def _event(code: str, signal_day: date, entry_day: date, exit_day: date, entry: float, exit_: float):
    return {
        "event_id": f"{code}:0:{signal_day}",
        "code": code,
        "stock_name": code,
        "signal_date": signal_day,
        "entry_date": entry_day,
        "exit_date": exit_day,
        "entry_price": entry,
        "exit_price": exit_,
        "signal_rank": (1.0, 1.0, 1.0, 1.0, code),
        "risk_geometry": {
            "status": "OK",
            "stop_price": entry * 0.95,
            "stop_distance_pct": 5.0,
            "source": "fixture",
        },
    }


def test_profitable_concentration_trim_reduces_only_excess_weight():
    start = date(2024, 1, 2)
    prices = [100, 100, 150, 220, 220, 220]
    data_map = {"000001": _data("000001", prices, start)}
    event = _event(
        "000001",
        signal_day=start,
        entry_day=start + timedelta(days=1),
        exit_day=start + timedelta(days=5),
        entry=100,
        exit_=220,
    )
    # 1% risk / 5% stop distance = 20% initial position.  After the price rises
    # to 220, the winner drifts above 30% of account NAV and becomes eligible.
    entry_policy = PortfolioConstructionPolicy(
        name="fixture",
        risk_per_trade_pct=1.0,
        max_single_name_fraction=0.80,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=10.0,
    )
    trim_policy = WinnerTrimPolicy(
        name="trim",
        trigger_weight_fraction=0.30,
        target_weight_fraction=0.22,
        minimum_gain_pct=50.0,
        cooldown_sessions=10,
        rebalance_cost_bps=0.0,
    )
    _, trims, _ = replay_with_winner_trim(
        [event],
        data_map,
        start_date=start,
        end_date=start + timedelta(days=5),
        trim_policy=trim_policy,
        entry_policy=entry_policy,
    )
    assert len(trims) == 1
    assert trims[0]["gain_pct"] >= 50.0
    assert trims[0]["weight_before_pct"] > 30.0
    assert 21.0 <= trims[0]["weight_after_pct"] <= 23.0


def test_no_trim_before_minimum_gain_even_if_weight_is_high():
    start = date(2024, 1, 2)
    prices = [100, 100, 110, 120, 120]
    data_map = {"000001": _data("000001", prices, start)}
    event = _event(
        "000001",
        signal_day=start,
        entry_day=start + timedelta(days=1),
        exit_day=start + timedelta(days=4),
        entry=100,
        exit_=120,
    )
    entry_policy = PortfolioConstructionPolicy(
        name="fixture",
        risk_per_trade_pct=2.0,
        max_single_name_fraction=0.90,
        max_total_gross_fraction=0.95,
        max_total_open_risk_pct=20.0,
    )
    trim_policy = WinnerTrimPolicy(
        name="trim",
        trigger_weight_fraction=0.30,
        target_weight_fraction=0.20,
        minimum_gain_pct=50.0,
        cooldown_sessions=1,
        rebalance_cost_bps=0.0,
    )
    _, trims, _ = replay_with_winner_trim(
        [event],
        data_map,
        start_date=start,
        end_date=start + timedelta(days=4),
        trim_policy=trim_policy,
        entry_policy=entry_policy,
    )
    assert trims == []


def test_cooldown_blocks_repeated_daily_trimming():
    start = date(2024, 1, 2)
    prices = [100, 100, 180, 300, 500, 700, 700]
    data_map = {"000001": _data("000001", prices, start)}
    event = _event(
        "000001",
        signal_day=start,
        entry_day=start + timedelta(days=1),
        exit_day=start + timedelta(days=6),
        entry=100,
        exit_=700,
    )
    entry_policy = PortfolioConstructionPolicy(
        name="fixture",
        risk_per_trade_pct=2.0,
        max_single_name_fraction=0.90,
        max_total_gross_fraction=0.95,
        max_total_open_risk_pct=20.0,
    )
    trim_policy = WinnerTrimPolicy(
        name="trim",
        trigger_weight_fraction=0.45,
        target_weight_fraction=0.35,
        minimum_gain_pct=50.0,
        cooldown_sessions=10,
        rebalance_cost_bps=0.0,
    )
    _, trims, _ = replay_with_winner_trim(
        [event],
        data_map,
        start_date=start,
        end_date=start + timedelta(days=6),
        trim_policy=trim_policy,
        entry_policy=entry_policy,
    )
    assert len(trims) == 1
