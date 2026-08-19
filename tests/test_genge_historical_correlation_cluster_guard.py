from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import ConcentrationGuardPolicy
from src.strategies.genge_opportunity_discovery.historical_correlation_cluster_guard import (
    CorrelationClusterPolicy,
    _return_maps,
    point_in_time_correlation,
    replay_with_correlation_cluster_cap,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import PortfolioConstructionPolicy


def _company(code: str, closes: list[float], start: date) -> HistoricalCompanyData:
    rows = []
    previous = closes[0]
    for i, close in enumerate(closes):
        day = start + timedelta(days=i)
        open_price = previous
        rows.append({
            "date": day,
            "open": open_price,
            "high": max(open_price, close) * 1.01,
            "low": min(open_price, close) * 0.99,
            "close": close,
            "volume": 1_000_000,
            "amount": close * 1_000_000,
        })
        previous = close
    return HistoricalCompanyData(
        code=code, stock_name=code, price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(), financial_df=pd.DataFrame(), warnings=[],
    )


def _event(code: str, signal_day: date, entry_day: date, exit_day: date, rank: float) -> dict:
    return {
        "event_id": f"{code}:0", "code": code, "stock_name": code,
        "signal_date": signal_day, "entry_date": entry_day, "exit_date": exit_day,
        "entry_price": 100.0, "exit_price": 110.0, "signal": {},
        "signal_rank": (1.0, rank, 10.0, -20.0, code), "reference_entry": 100.0,
        "risk_geometry": {"status": "OK", "stop_price": 97.0, "stop_distance_pct": 3.0, "source": "test"},
    }


def _entry_policy():
    return PortfolioConstructionPolicy(
        name="risk075_open4", mode="risk_budget", risk_per_trade_pct=0.75,
        max_single_name_fraction=0.20, max_total_gross_fraction=0.90,
        max_total_open_risk_pct=4.0,
    )


def _concentration():
    return ConcentrationGuardPolicy(
        "conc90_to80", trigger_fraction=0.90, target_fraction=0.80,
        min_holding_sessions=0, cooldown_sessions=0, trim_cost_bps=0.0,
    )


def test_policy_rejects_invalid_observation_window():
    with pytest.raises(ValueError):
        CorrelationClusterPolicy(
            "bad", correlation_threshold=0.65, max_cluster_fraction=0.35,
            lookback_sessions=40, minimum_observations=50,
        )


def test_point_in_time_correlation_ignores_future_divergence():
    start = date(2024, 1, 1)
    base_returns = np.array([0.01 if i % 2 == 0 else -0.006 for i in range(90)])
    a = [100.0]
    b = [100.0]
    for r in base_returns:
        a.append(a[-1] * (1 + r))
        b.append(b[-1] * (1 + r))
    as_of = start + timedelta(days=90)
    # Future path diverges completely after the correlation observation date.
    for i in range(20):
        a.append(a[-1] * 1.01)
        b.append(b[-1] * 0.99)
    data = {"A": _company("A", a, start), "B": _company("B", b, start)}
    maps = _return_maps(data)
    corr = point_in_time_correlation(
        maps, "A", "B", as_of=as_of, lookback_sessions=80, minimum_observations=60,
    )
    assert corr == pytest.approx(1.0)


def test_same_day_correlated_reservations_share_cluster_capacity():
    start = date(2024, 1, 1)
    # 100 visible sessions with identical alternating returns -> correlation 1.
    pattern = [0.008 if i % 2 == 0 else -0.004 for i in range(100)]
    closes_a = [100.0]
    closes_b = [100.0]
    closes_c = [100.0]
    for i, r in enumerate(pattern):
        closes_a.append(closes_a[-1] * (1 + r))
        closes_b.append(closes_b[-1] * (1 + r))
        # Opposite-signed pattern is strongly negative, so C is a different cluster.
        closes_c.append(closes_c[-1] * (1 - r))
    # Add signal/entry/exit bars near 100 so execution remains simple.
    for _ in range(4):
        closes_a.append(closes_a[-1])
        closes_b.append(closes_b[-1])
        closes_c.append(closes_c[-1])

    signal_day = start + timedelta(days=100)
    entry_day = signal_day + timedelta(days=1)
    exit_day = signal_day + timedelta(days=3)
    data = {
        "A": _company("A", closes_a, start),
        "B": _company("B", closes_b, start),
        "C": _company("C", closes_c, start),
    }
    events = [
        _event("A", signal_day, entry_day, exit_day, 90.0),
        _event("B", signal_day, entry_day, exit_day, 80.0),
        _event("C", signal_day, entry_day, exit_day, 70.0),
    ]
    policy = CorrelationClusterPolicy(
        "corr", correlation_threshold=0.70, max_cluster_fraction=0.20,
        lookback_sessions=80, minimum_observations=60,
    )
    _, allocations, _, audit = replay_with_correlation_cluster_cap(
        events, data, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration(),
        correlation_policy=policy,
    )
    rows = {row["code"]: row for row in allocations}

    # 0.75% risk / 5% minimum stop-distance = 15% base size.
    assert rows["A"]["allocated_pct"] == 15.0
    # B sees A's same-day 15% reservation and only gets 5% cluster room.
    assert rows["B"]["allocated_pct"] == pytest.approx(5.0)
    assert rows["B"]["status"] == "ALLOCATED_CORRELATION_REDUCED"
    assert rows["B"]["correlated_pct_before"] == pytest.approx(15.0)
    # C is negatively correlated with A/B and therefore gets its full 15%.
    assert rows["C"]["allocated_pct"] == 15.0
    assert audit["correlation_reduced_count"] == 1
    assert audit["correlation_blocked_count"] == 0


def test_cluster_full_blocks_later_correlated_candidate():
    start = date(2024, 1, 1)
    pattern = [0.008 if i % 2 == 0 else -0.004 for i in range(100)]
    closes = [100.0]
    for r in pattern:
        closes.append(closes[-1] * (1 + r))
    closes.extend([closes[-1]] * 4)
    signal_day = start + timedelta(days=100)
    entry_day = signal_day + timedelta(days=1)
    exit_day = signal_day + timedelta(days=3)
    data = {code: _company(code, closes, start) for code in ("A", "B", "D")}
    events = [
        _event("A", signal_day, entry_day, exit_day, 90.0),
        _event("B", signal_day, entry_day, exit_day, 80.0),
        _event("D", signal_day, entry_day, exit_day, 70.0),
    ]
    policy = CorrelationClusterPolicy(
        "corr", correlation_threshold=0.70, max_cluster_fraction=0.20,
        lookback_sessions=80, minimum_observations=60,
    )
    _, allocations, _, audit = replay_with_correlation_cluster_cap(
        events, data, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration(),
        correlation_policy=policy,
    )
    rows = {row["code"]: row for row in allocations}
    assert rows["A"]["allocated_pct"] == 15.0
    assert rows["B"]["allocated_pct"] == pytest.approx(5.0)
    assert rows["D"]["allocated_pct"] == 0.0
    assert rows["D"]["status"] == "CORRELATION_CLUSTER_CAP"
    assert audit["correlation_blocked_count"] == 1
