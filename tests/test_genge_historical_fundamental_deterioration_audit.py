from __future__ import annotations

from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
)
from src.strategies.genge_opportunity_discovery.historical_fundamental_deterioration_audit import (
    disclosure_observation,
)


def _financial() -> pd.DataFrame:
    return normalize_financial_point_in_time(pd.DataFrame([
        {
            "report_date": date(2020, 6, 30),
            "disclosure_date": date(2020, 8, 20),
            "recurring_profit": 100.0,
            "cash_conversion_ratio": 1.0,
            "roe": 15.0,
            "debt_ratio": 30.0,
        },
        {
            "report_date": date(2021, 6, 30),
            "disclosure_date": date(2021, 8, 20),
            "recurring_profit": 120.0,
            "cash_conversion_ratio": 1.0,
            "roe": 15.0,
            "debt_ratio": 30.0,
        },
        {
            "report_date": date(2022, 6, 30),
            "disclosure_date": date(2022, 8, 20),
            "recurring_profit": 78.0,
            "cash_conversion_ratio": 1.0,
            "roe": 15.0,
            "debt_ratio": 30.0,
        },
        {
            "report_date": date(2023, 6, 30),
            "disclosure_date": date(2023, 8, 20),
            "recurring_profit": 50.0,
            "cash_conversion_ratio": 1.0,
            "roe": 15.0,
            "debt_ratio": 30.0,
        },
    ]))


def test_future_disclosure_cannot_change_prior_hard_logic():
    financial = _financial()
    before = point_in_time_hard_logic(financial, date(2022, 8, 19))
    after = point_in_time_hard_logic(financial, date(2022, 8, 20))

    assert before["latest_report_date"] == date(2021, 6, 30)
    assert after["latest_report_date"] == date(2022, 6, 30)
    assert before["supported_growth_base_pct"] == 20.0
    assert after["supported_growth_base_pct"] < 0.0


def test_score_drop_warning_can_fire_before_hard_logic_is_blocked():
    financial = _financial()
    entry_logic = point_in_time_hard_logic(financial, date(2021, 8, 20))
    observation = disclosure_observation(
        financial,
        as_of=date(2022, 8, 20),
        entry_score=float(entry_logic["score"]),
        previous_yoy=20.0,
    )

    # The 2022 half-year recurring profit falls from 120 to 78 (-35%). The
    # broad hard-logic score can remain PASS because cash/ROE/debt are still
    # healthy, but a large score drop plus negative YoY is observable now.
    assert observation["profit_yoy_pct"] == -35.0
    assert observation["hard_logic_state"] == "PASS"
    assert observation["score_drop15_and_yoy_negative"] is True
    assert observation["score_le55_and_yoy_le_minus20"] is False
    assert observation["base_nonpositive_and_yoy_le_minus10"] is True


def test_two_consecutive_negative_yoy_requires_prior_disclosure_warning():
    financial = _financial()
    entry_logic = point_in_time_hard_logic(financial, date(2021, 8, 20))
    first = disclosure_observation(
        financial,
        as_of=date(2022, 8, 20),
        entry_score=float(entry_logic["score"]),
        previous_yoy=20.0,
    )
    second = disclosure_observation(
        financial,
        as_of=date(2023, 8, 20),
        entry_score=float(entry_logic["score"]),
        previous_yoy=float(first["profit_yoy_pct"]),
    )

    assert first["two_consecutive_yoy_le_minus10"] is False
    assert second["profit_yoy_pct"] < -10.0
    assert second["two_consecutive_yoy_le_minus10"] is True
