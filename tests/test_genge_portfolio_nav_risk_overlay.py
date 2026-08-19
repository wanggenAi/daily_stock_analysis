from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_opportunity_discovery.portfolio_nav_risk_overlay import (
    PortfolioOverlayPolicy,
    apply_portfolio_overlay,
)
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import max_drawdown_pct


def _curve(returns: list[float]) -> pd.Series:
    nav = 1.0
    values = []
    days = []
    start = date(2025, 1, 1)
    for i, ret in enumerate(returns):
        nav *= 1.0 + ret
        values.append(nav)
        days.append(start + timedelta(days=i))
    return pd.Series(values, index=pd.Index(days, name="date"), dtype=float)


def test_overlay_does_not_use_future_return_for_current_exposure():
    baseline = _curve([0.0, -0.10, -0.10, 0.20])
    policy = PortfolioOverlayPolicy(
        name="dd",
        max_gross_fraction=0.90,
        use_drawdown_guard=True,
        dd_level_1_pct=5.0,
        dd_level_2_pct=10.0,
        dd_level_3_pct=15.0,
        dd_multiplier_1=0.75,
        dd_multiplier_2=0.50,
        dd_multiplier_3=0.25,
        rebalance_cost_bps=0.0,
    )
    _, audit = apply_portfolio_overlay(baseline, policy)

    assert float(audit.iloc[1]["exposure_used_today"]) == 0.90
    assert float(audit.iloc[1]["next_session_exposure"]) < 0.90
    assert float(audit.iloc[2]["exposure_used_today"]) == float(audit.iloc[1]["next_session_exposure"])


def test_drawdown_guard_reduces_crash_drawdown_against_gross90_only():
    baseline = _curve([0.0] + [-0.04] * 8 + [0.02] * 10)
    plain = PortfolioOverlayPolicy(
        name="plain",
        max_gross_fraction=0.90,
        use_drawdown_guard=False,
        rebalance_cost_bps=0.0,
    )
    guarded = PortfolioOverlayPolicy(
        name="guarded",
        max_gross_fraction=0.90,
        volatility_target_pct=None,
        dd_level_1_pct=5.0,
        dd_level_2_pct=10.0,
        dd_level_3_pct=15.0,
        dd_multiplier_1=0.75,
        dd_multiplier_2=0.50,
        dd_multiplier_3=0.25,
        rebalance_cost_bps=0.0,
    )
    plain_curve, _ = apply_portfolio_overlay(baseline, plain)
    guarded_curve, _ = apply_portfolio_overlay(baseline, guarded)

    assert float(max_drawdown_pct(guarded_curve)) < float(max_drawdown_pct(plain_curve))


def test_volatility_target_cuts_exposure_after_high_realized_volatility():
    returns = [0.0] + [0.06, -0.06] * 15
    baseline = _curve(returns)
    policy = PortfolioOverlayPolicy(
        name="vol",
        max_gross_fraction=0.90,
        volatility_target_pct=20.0,
        volatility_lookback_sessions=10,
        volatility_floor_fraction=0.25,
        use_drawdown_guard=False,
        rebalance_cost_bps=0.0,
    )
    _, audit = apply_portfolio_overlay(baseline, policy)
    late = audit.iloc[-1]
    assert float(late["next_session_exposure"]) < 0.90
    assert float(late["next_session_exposure"]) >= 0.25


def test_rebalance_friction_never_improves_nav():
    baseline = _curve([0.0, -0.08, 0.10, -0.08, 0.10, 0.02])
    free = PortfolioOverlayPolicy(
        name="free",
        max_gross_fraction=0.90,
        use_drawdown_guard=True,
        dd_level_1_pct=5.0,
        dd_level_2_pct=10.0,
        dd_level_3_pct=15.0,
        rebalance_cost_bps=0.0,
    )
    costly = PortfolioOverlayPolicy(
        name="costly",
        max_gross_fraction=0.90,
        use_drawdown_guard=True,
        dd_level_1_pct=5.0,
        dd_level_2_pct=10.0,
        dd_level_3_pct=15.0,
        rebalance_cost_bps=20.0,
    )
    free_curve, _ = apply_portfolio_overlay(baseline, free)
    costly_curve, _ = apply_portfolio_overlay(baseline, costly)
    assert float(costly_curve.iloc[-1]) <= float(free_curve.iloc[-1])
