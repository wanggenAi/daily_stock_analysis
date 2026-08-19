from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import ConcentrationGuardPolicy
from src.strategies.genge_opportunity_discovery.historical_correlation_cluster_guard import CorrelationClusterPolicy
from src.strategies.genge_opportunity_discovery.historical_dynamic_cluster_guard import (
    DynamicClusterPolicy,
    _price_features,
    dynamic_clusters,
    replay_with_dynamic_cluster_guard,
)
from src.strategies.genge_opportunity_discovery.historical_correlation_cluster_guard import _return_maps
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import PortfolioConstructionPolicy


def _company(code: str, closes: list[float], start: date, opens: list[float] | None = None):
    rows = []
    for i, close in enumerate(closes):
        open_price = opens[i] if opens is not None else (closes[i - 1] if i else close)
        rows.append({
            "date": start + timedelta(days=i), "open": open_price,
            "high": max(open_price, close) * 1.01, "low": min(open_price, close) * 0.99,
            "close": close, "volume": 1_000_000, "amount": close * 1_000_000,
        })
    return HistoricalCompanyData(
        code=code, stock_name=code, price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(), financial_df=pd.DataFrame(), warnings=[],
    )


def _event(code: str, signal_day: date, entry_day: date, exit_day: date, rank: float):
    return {
        "event_id": f"{code}:0", "code": code, "stock_name": code,
        "signal_date": signal_day, "entry_date": entry_day, "exit_date": exit_day,
        "entry_price": 100.0, "exit_price": 240.0, "signal": {},
        "signal_rank": (1.0, rank, 10.0, -20.0, code), "reference_entry": 100.0,
        "risk_geometry": {"status": "OK", "stop_price": 97.0, "stop_distance_pct": 3.0, "source": "test"},
    }


def _entry_policy():
    return PortfolioConstructionPolicy(
        name="risk075_open4", mode="risk_budget", risk_per_trade_pct=0.75,
        max_single_name_fraction=0.20, max_total_gross_fraction=0.90,
        max_total_open_risk_pct=4.0,
    )


def _entry_corr():
    return CorrelationClusterPolicy(
        "corr65_cluster35", correlation_threshold=0.65, max_cluster_fraction=0.35,
        lookback_sessions=80, minimum_observations=60,
    )


def _concentration():
    return ConcentrationGuardPolicy(
        "conc90_to80", trigger_fraction=0.90, target_fraction=0.80,
        min_holding_sessions=0, cooldown_sessions=0, trim_cost_bps=0.0,
    )


def test_dynamic_policy_requires_target_below_trigger():
    with pytest.raises(ValueError):
        DynamicClusterPolicy("bad", 0.65, 0.40, 0.40)


def test_cluster_requires_stress_not_just_high_correlation():
    start = date(2024, 1, 1)
    pattern = [0.008 if i % 2 == 0 else -0.004 for i in range(100)]
    closes = [100.0]
    for r in pattern:
        closes.append(closes[-1] * (1 + r))
    data = {"A": _company("A", closes, start), "B": _company("B", closes, start)}
    as_of = start + timedelta(days=100)
    policy = DynamicClusterPolicy(
        "dyn", correlation_threshold=0.65, trigger_cluster_fraction=0.50,
        target_cluster_fraction=0.40, lookback_sessions=80, minimum_observations=60,
        trend_sessions=60,
    )
    clusters = dynamic_clusters(
        ["A", "B"], as_of=as_of, return_maps=_return_maps(data),
        price_features=_price_features(data, 60), policy=policy,
    )
    assert len(clusters) == 1
    assert clusters[0]["stressed"] is False


def test_dynamic_cluster_stress_trims_weak_member_next_open():
    start = date(2024, 1, 1)
    # 100 correlated pre-signal sessions around 100.
    pattern = [0.006 if i % 2 == 0 else -0.003 for i in range(100)]
    pre = [100.0]
    for r in pattern:
        pre.append(pre[-1] * (1 + r))
    signal_day = start + timedelta(days=100)
    entry_day = signal_day + timedelta(days=1)
    # After entry, both positions appreciate for long enough to form a large
    # correlated cluster, then weaken below a mature 60-session trend while
    # still worth ~250 each. The cluster remains >50% of account NAV.
    post = [300.0] * 65 + [250.0, 245.0, 240.0]
    closes_a = pre + post
    closes_b = pre + post
    # Entry-day open is the frozen 100 execution price. Later opens follow close.
    opens = list(closes_a)
    opens[len(pre)] = 100.0
    execution_index = len(pre) + 66
    opens[execution_index] = 230.0
    data = {
        "A": _company("A", closes_a, start, opens=opens),
        "B": _company("B", closes_b, start, opens=opens),
    }
    stress_day = start + timedelta(days=len(pre) + 65)
    execution_day = stress_day + timedelta(days=1)
    exit_day = start + timedelta(days=len(closes_a) - 1)
    events = [
        _event("A", signal_day, entry_day, exit_day, 90.0),
        _event("B", signal_day, entry_day, exit_day, 80.0),
    ]
    policy = DynamicClusterPolicy(
        "dyn", correlation_threshold=0.65, trigger_cluster_fraction=0.50,
        target_cluster_fraction=0.40, lookback_sessions=80, minimum_observations=60,
        trend_sessions=60, below_trend_ratio_trigger=0.50,
        median_return_20d_trigger_pct=-3.0, minimum_name_fraction_after_trim=0.05,
        minimum_holding_sessions=0, cooldown_sessions=0, trim_cost_bps=0.0,
    )
    _, allocations, trims, audit = replay_with_dynamic_cluster_guard(
        events, data, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration(),
        entry_correlation_policy=_entry_corr(), dynamic_policy=policy,
    )

    rows = {row["code"]: row for row in allocations}
    assert rows["A"]["allocated_pct"] == 15.0
    assert rows["B"]["allocated_pct"] == 15.0
    dynamic = [row for row in trims if row["reason"] == "DYNAMIC_CORRELATED_CLUSTER_STRESS"]
    assert dynamic
    first = dynamic[0]
    assert first["decision_date"] == stress_day
    assert first["execution_date"] == execution_day
    assert first["execution_open"] == 230.0
    assert first["shares_frozen_before_open"] is True
    assert first["risk_budget_released_proportionally"] is True
    assert audit["dynamic_cluster_trim_order_count"] >= 1


def test_unstressed_large_cluster_is_not_trimmed():
    start = date(2024, 1, 1)
    pattern = [0.006 if i % 2 == 0 else -0.003 for i in range(100)]
    pre = [100.0]
    for r in pattern:
        pre.append(pre[-1] * (1 + r))
    signal_day = start + timedelta(days=100)
    entry_day = signal_day + timedelta(days=1)
    post = [300.0] * 70
    closes = pre + post
    opens = list(closes); opens[len(pre)] = 100.0
    data = {"A": _company("A", closes, start, opens), "B": _company("B", closes, start, opens)}
    exit_day = start + timedelta(days=len(closes) - 1)
    events = [_event("A", signal_day, entry_day, exit_day, 90), _event("B", signal_day, entry_day, exit_day, 80)]
    policy = DynamicClusterPolicy(
        "dyn", 0.65, 0.50, 0.40, lookback_sessions=80, minimum_observations=60,
        trend_sessions=60, minimum_holding_sessions=0, cooldown_sessions=0, trim_cost_bps=0.0,
    )
    _, _, trims, audit = replay_with_dynamic_cluster_guard(
        events, data, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration(),
        entry_correlation_policy=_entry_corr(), dynamic_policy=policy,
    )
    assert [row for row in trims if row["reason"] == "DYNAMIC_CORRELATED_CLUSTER_STRESS"] == []
    assert audit["dynamic_cluster_trim_order_count"] == 0
