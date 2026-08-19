from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import ConcentrationGuardPolicy
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import PortfolioConstructionPolicy
from src.strategies.genge_opportunity_discovery.historical_winner_trend_guard import (
    WinnerTrendPolicy,
    replay_with_winner_trend_guard,
)


def _history(code: str):
    start = date(2024, 8, 1)
    rows = []
    # Long pre-history near 300 establishes a mature MA120 without future data.
    for i in range(130):
        day = start + timedelta(days=i)
        rows.append({
            "date": day, "open": 300.0, "high": 303.0, "low": 297.0,
            "close": 300.0, "volume": 1_000_000, "amount": 300_000_000,
        })
    signal_day = start + timedelta(days=130)
    entry_day = start + timedelta(days=131)
    break_day = start + timedelta(days=132)
    execution_day = start + timedelta(days=133)
    exit_day = start + timedelta(days=134)
    rows.extend([
        {"date": signal_day, "open": 300.0, "high": 303.0, "low": 297.0, "close": 300.0, "volume": 1_000_000, "amount": 300_000_000},
        # Event entry is frozen at 100; the close at 300 makes it a large winner.
        {"date": entry_day, "open": 100.0, "high": 305.0, "low": 99.0, "close": 300.0, "volume": 1_000_000, "amount": 300_000_000},
        # Still +100% vs entry, but now materially below the mature MA120.
        {"date": break_day, "open": 300.0, "high": 302.0, "low": 195.0, "close": 200.0, "volume": 1_000_000, "amount": 200_000_000},
        # Trim must execute fixed shares here; this open cannot resize the order.
        {"date": execution_day, "open": 180.0, "high": 190.0, "low": 175.0, "close": 185.0, "volume": 1_000_000, "amount": 185_000_000},
        {"date": exit_day, "open": 190.0, "high": 195.0, "low": 185.0, "close": 190.0, "volume": 1_000_000, "amount": 190_000_000},
    ])
    data = HistoricalCompanyData(
        code=code,
        stock_name=code,
        price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(),
        financial_df=pd.DataFrame(),
        warnings=[],
    )
    event = {
        "event_id": f"{code}:0",
        "code": code,
        "stock_name": code,
        "signal_date": signal_day,
        "entry_date": entry_day,
        "exit_date": exit_day,
        "entry_price": 100.0,
        "exit_price": 190.0,
        "signal": {},
        "signal_rank": (1.0, 70.0, 10.0, -20.0, code),
        "reference_entry": 100.0,
        "risk_geometry": {
            "status": "OK", "stop_price": 97.0,
            "stop_distance_pct": 3.0, "source": "test",
        },
    }
    return data, event, signal_day, entry_day, break_day, execution_day, exit_day


def _entry_policy():
    return PortfolioConstructionPolicy(
        name="risk075_open4", mode="risk_budget", risk_per_trade_pct=0.75,
        max_single_name_fraction=0.20, max_total_gross_fraction=0.90,
        max_total_open_risk_pct=4.0,
    )


def _concentration_policy():
    # Keep the concentration trigger above the synthetic winner weight so this
    # test isolates the trend guard.
    return ConcentrationGuardPolicy(
        "conc50_to30", trigger_fraction=0.50, target_fraction=0.30,
        min_holding_sessions=0, cooldown_sessions=0, trim_cost_bps=15.0,
    )


def test_winner_policy_requires_target_below_material_weight():
    with pytest.raises(ValueError):
        WinnerTrendPolicy(
            "bad", minimum_weight_fraction=0.20, minimum_gain_pct=50,
            moving_average_sessions=120, break_below_ma_pct=3,
            target_fraction=0.20,
        )


def test_large_profitable_winner_break_trims_fixed_shares_next_open():
    code = "600001"
    data, event, signal_day, _, break_day, execution_day, exit_day = _history(code)
    policy = WinnerTrendPolicy(
        "winner", minimum_weight_fraction=0.20, minimum_gain_pct=50.0,
        moving_average_sessions=120, break_below_ma_pct=3.0,
        target_fraction=0.12, minimum_holding_sessions=0,
        cooldown_sessions=0, trim_cost_bps=0.0,
    )
    _, allocations, trims, audit = replay_with_winner_trend_guard(
        [event], {code: data}, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration_policy(),
        winner_policy=policy,
    )

    assert allocations[0]["allocated_pct"] == 15.0
    assert len(trims) == 1
    trim = trims[0]
    assert trim["reason"] == "WINNER_TREND_BREAK"
    assert trim["decision_date"] == break_day
    assert trim["execution_date"] == execution_day
    assert trim["execution_open"] == 180.0
    assert trim["shares_frozen_before_open"] is True
    assert trim["risk_budget_released_proportionally"] is True
    assert trim["trigger_gain_pct"] == pytest.approx(100.0)
    # At the break close: initial shares=.15/100=.0015, mark=.30,
    # cash=.85, equity=1.15, target mark=.138. Frozen shares=(.30-.138)/200.
    assert trim["shares_sold"] == pytest.approx((0.30 - 1.15 * 0.12) / 200.0)
    assert audit["winner_trend_trim_count"] == 1
    assert audit["concentration_trim_count"] == 0


def test_profit_without_required_gain_does_not_trigger():
    code = "600002"
    data, event, signal_day, _, _, _, exit_day = _history(code)
    policy = WinnerTrendPolicy(
        "winner", minimum_weight_fraction=0.15, minimum_gain_pct=150.0,
        moving_average_sessions=120, break_below_ma_pct=3.0,
        target_fraction=0.10, minimum_holding_sessions=0,
        cooldown_sessions=0, trim_cost_bps=0.0,
    )
    _, _, trims, audit = replay_with_winner_trend_guard(
        [event], {code: data}, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration_policy(),
        winner_policy=policy,
    )

    # The break-day position is +100%, below the +150% requirement.
    assert trims == []
    assert audit["winner_trend_trim_count"] == 0


def test_trim_friction_is_explicit():
    code = "600003"
    data, event, signal_day, _, _, _, exit_day = _history(code)
    policy = WinnerTrendPolicy(
        "winner", minimum_weight_fraction=0.20, minimum_gain_pct=50.0,
        moving_average_sessions=120, break_below_ma_pct=3.0,
        target_fraction=0.12, minimum_holding_sessions=0,
        cooldown_sessions=0, trim_cost_bps=20.0,
    )
    _, _, trims, audit = replay_with_winner_trend_guard(
        [event], {code: data}, start_date=signal_day, end_date=exit_day,
        entry_policy=_entry_policy(), concentration_policy=_concentration_policy(),
        winner_policy=policy,
    )

    assert len(trims) == 1
    expected = trims[0]["gross_proceeds"] * 20.0 / 10_000.0
    assert trims[0]["friction_cost"] == pytest.approx(expected)
    assert audit["trim_friction_cost_dollars"] == pytest.approx(round(expected, 8))
