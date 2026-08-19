from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.historical_systemic_index_guard import (
    SystemicExposurePolicy,
    apply_systemic_overlay,
    systemic_state,
)


def _maps(days, rows_by_day):
    result = {"index_a": {}, "index_b": {}}
    for day in days:
        row = dict(rows_by_day[day])
        result["index_a"][day] = dict(row)
        result["index_b"][day] = dict(row)
    return result


def _row(*, above60=True, above120=True, ret5=1.0, ret20=2.0, dd60=-1.0):
    return {
        "above_ma60": above60,
        "above_ma120": above120,
        "ret5_pct": ret5,
        "ret20_pct": ret20,
        "dd60_pct": dd60,
    }


def test_systemic_policy_requires_monotone_exposure():
    with pytest.raises(ValueError):
        SystemicExposurePolicy(
            "bad", green_fraction=1.0, yellow_fraction=0.5, red_fraction=0.7
        )


def test_systemic_state_green_yellow_red_are_deterministic():
    day = date(2025, 1, 2)
    green = _maps([day], {day: _row()})
    assert systemic_state(green, as_of=day)["status"] == "GREEN"

    yellow = _maps(
        [day],
        {day: _row(above60=False, above120=True, ret5=-3.0, ret20=-2.0, dd60=-5.0)},
    )
    assert systemic_state(yellow, as_of=day)["status"] == "YELLOW"

    red = _maps(
        [day],
        {day: _row(above60=False, above120=False, ret5=-6.0, ret20=-8.0, dd60=-13.0)},
    )
    state = systemic_state(red, as_of=day)
    assert state["status"] == "RED"
    assert "broad_5d_crash" in state["reasons"]


def test_red_signal_after_close_cannot_protect_same_day_loss():
    d0 = date(2025, 1, 2)
    d1 = d0 + timedelta(days=1)
    d2 = d0 + timedelta(days=2)
    base = pd.Series([1.0, 0.90, 0.81], index=[d0, d1, d2], dtype=float)
    maps = _maps(
        [d0, d1, d2],
        {
            d0: _row(),
            d1: _row(above60=False, above120=False, ret5=-6.0, ret20=-8.0, dd60=-13.0),
            d2: _row(above60=False, above120=False, ret5=-6.0, ret20=-8.0, dd60=-13.0),
        },
    )
    policy = SystemicExposurePolicy(
        "timing", green_fraction=1.0, yellow_fraction=0.8, red_fraction=0.5,
        rebalance_cost_bps=0.0,
    )
    curve, rows, audit = apply_systemic_overlay(base, feature_maps=maps, policy=policy)

    # d1 suffers the full -10% because d0 close was GREEN. Only after the d1
    # RED close does d2 run at 50% exposure, turning -10% base into -5%.
    assert curve.loc[d1] == pytest.approx(0.90)
    assert curve.loc[d2] == pytest.approx(0.90 * 0.95)
    by_day = {row["date"]: row for row in rows}
    assert by_day[d1]["exposure_used"] == 1.0
    assert by_day[d1]["next_session_target_exposure"] == 0.5
    assert by_day[d2]["exposure_used"] == 0.5
    assert audit["exposure_change_count"] == 1


def test_exposure_change_charges_explicit_turnover_friction():
    d0 = date(2025, 1, 2)
    d1 = d0 + timedelta(days=1)
    base = pd.Series([1.0, 1.0], index=[d0, d1], dtype=float)
    maps = _maps(
        [d0, d1],
        {
            d0: _row(above60=False, above120=False, ret5=-6.0, ret20=-8.0, dd60=-13.0),
            d1: _row(above60=False, above120=False, ret5=-6.0, ret20=-8.0, dd60=-13.0),
        },
    )
    policy = SystemicExposurePolicy(
        "cost", green_fraction=1.0, yellow_fraction=0.8, red_fraction=0.5,
        rebalance_cost_bps=10.0,
    )
    curve, _, audit = apply_systemic_overlay(base, feature_maps=maps, policy=policy)

    # d0 close schedules 1.0 -> .5. On d1 that .5 turnover costs 10bp:
    # 1.0 * .5 * .001 = .0005, with zero base return thereafter.
    assert curve.loc[d1] == pytest.approx(0.9995)
    assert audit["exposure_change_count"] == 1
    assert audit["total_rebalance_cost"] == pytest.approx(0.0005)


def test_unknown_state_uses_unknown_fraction_next_session_only():
    d0 = date(2025, 1, 2)
    d1 = d0 + timedelta(days=1)
    base = pd.Series([1.0, 1.10], index=[d0, d1], dtype=float)
    maps = {
        "index_a": {d0: _row(), d1: _row()},
    }
    policy = SystemicExposurePolicy(
        "unknown", unknown_fraction=0.75, rebalance_cost_bps=0.0
    )
    curve, rows, _ = apply_systemic_overlay(base, feature_maps=maps, policy=policy)

    # d0 UNKNOWN is only known after d0 close, so d1's +10% receives 75%
    # exposure, producing +7.5% rather than +10%.
    assert curve.loc[d1] == pytest.approx(1.075)
    assert rows[0]["status"] == "UNKNOWN"
    assert rows[1]["exposure_used"] == 0.75
