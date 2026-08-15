from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_opportunity_discovery import factor_ic_monitor
from src.strategies.genge_opportunity_discovery import opportunity_engine_policy


def _observation_frame(*, cohorts: int, direction: int = 1) -> pd.DataFrame:
    rows = []
    start = date(2026, 1, 5)
    for cohort in range(cohorts):
        observation_date = start + timedelta(days=cohort)
        for number in range(40):
            factor = float(number)
            rows.append(
                {
                    "observation_date": observation_date.isoformat(),
                    "code": f"{number + 1:06d}",
                    "stock_name": f"S{number}",
                    "industry": "TEST",
                    "close": 10.0,
                    "factor_value": factor,
                    "factor_quality": factor,
                    "factor_reversal": factor,
                    "factor_momentum": factor,
                    "factor_earnings": factor,
                    "return_20d_pct": direction * factor,
                    "return_60d_pct": None,
                    "return_120d_pct": None,
                    "rule_version": factor_ic_monitor.RULE_VERSION,
                }
            )
    return pd.DataFrame(rows, columns=factor_ic_monitor.OBSERVATION_COLUMNS)


def _price_history(days: int) -> pd.DataFrame:
    start = date(2026, 1, 5)
    rows = []
    for index in range(days):
        close = 10.0 + index
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1_000_000.0,
                "amount": close * 1_000_000.0,
            }
        )
    return pd.DataFrame(rows)


def test_factor_effectiveness_positive_rank_ic_is_valid() -> None:
    result = factor_ic_monitor.factor_effectiveness(
        _observation_frame(cohorts=5, direction=1)
    )

    assert result["factor_summaries"]["VALUE"]["status"] == "VALID"
    assert result["factor_summaries"]["MOMENTUM"]["status"] == "VALID"
    assert result["engine_summaries"]["STRONG_TREND_PULLBACK"]["status"] == "VALID"
    assert result["factor_summaries"]["VALUE"]["aggregate_ic"] == 1.0


def test_factor_effectiveness_negative_rank_ic_is_invalid() -> None:
    result = factor_ic_monitor.factor_effectiveness(
        _observation_frame(cohorts=5, direction=-1)
    )

    assert result["factor_summaries"]["REVERSAL"]["status"] == "INVALID"
    assert result["factor_summaries"]["MOMENTUM"]["status"] == "INVALID"
    assert result["engine_summaries"]["VALLEY_REPAIR"]["status"] == "INVALID"
    assert result["engine_summaries"]["STRONG_TREND_PULLBACK"]["status"] == "INVALID"


def test_factor_effectiveness_insufficient_cohorts_stays_unknown() -> None:
    result = factor_ic_monitor.factor_effectiveness(
        _observation_frame(cohorts=4, direction=1)
    )

    assert result["factor_summaries"]["VALUE"]["status"] == "UNKNOWN"
    assert result["engine_summaries"]["STRONG_TREND_PULLBACK"]["status"] == "UNKNOWN"


def test_forward_return_is_not_filled_before_horizon_exists() -> None:
    observation = pd.DataFrame(
        [
            {
                "observation_date": "2026-01-05",
                "code": "000001",
                "stock_name": "TEST",
                "industry": "TEST",
                "close": 10.0,
                "factor_value": 1.0,
                "factor_quality": 1.0,
                "factor_reversal": 1.0,
                "factor_momentum": 1.0,
                "factor_earnings": 1.0,
                "return_20d_pct": None,
                "return_60d_pct": None,
                "return_120d_pct": None,
                "rule_version": factor_ic_monitor.RULE_VERSION,
            }
        ],
        columns=factor_ic_monitor.OBSERVATION_COLUMNS,
    )
    nineteen_sessions = BacktestInput(
        code="000001",
        stock_name="TEST",
        price_df=_price_history(20),
    )
    before = factor_ic_monitor.mature_forward_returns(
        observation,
        [nineteen_sessions],
        as_of=date(2026, 1, 24),
    )
    assert pd.isna(before.iloc[0]["return_20d_pct"])

    twenty_sessions = BacktestInput(
        code="000001",
        stock_name="TEST",
        price_df=_price_history(21),
    )
    matured = factor_ic_monitor.mature_forward_returns(
        observation,
        [twenty_sessions],
        as_of=date(2026, 1, 25),
    )
    assert matured.iloc[0]["return_20d_pct"] == 200.0
    assert pd.isna(matured.iloc[0]["return_60d_pct"])


def test_engine_specific_factor_invalid_does_not_veto_other_shape() -> None:
    row = {
        "price_percentile_5y": 0.20,
        "trend_confirmation_level": "STRONG",
        "industry_regime_status": "STRONG",
        "valley_factor_validity_status": "INVALID",
        "trend_factor_validity_status": "VALID",
        "earnings_factor_validity_status": "UNKNOWN",
    }
    plan = {
        "preferred_plan": "pullback",
        "pullback_status": "READY",
    }

    evaluation = opportunity_engine_policy.evaluate_engine(row, plan)

    assert evaluation.eligible is True
    assert evaluation.engine == "STRONG_TREND_PULLBACK"
    assert evaluation.factor_validity_status == "VALID"


def test_build_current_observations_orients_reversal_low_price_as_high_factor() -> None:
    rows = [
        {
            "code": "1",
            "stock_name": "LOW",
            "normalized_industry": "TEST",
            "close": 10.0,
            "valuation_score": 70.0,
            "financial_safety_score": 80.0,
            "price_percentile_5y": 0.10,
            "relative_strength_20d": -1.0,
            "relative_strength_60d": -2.0,
            "trend_stabilization_score": 50.0,
            "net_profit_yoy": 20.0,
            "previous_net_profit_yoy": 5.0,
        },
        {
            "code": "2",
            "stock_name": "HIGH",
            "normalized_industry": "TEST",
            "close": 20.0,
            "valuation_score": 60.0,
            "financial_safety_score": 70.0,
            "price_percentile_5y": 0.80,
            "relative_strength_20d": 3.0,
            "relative_strength_60d": 4.0,
            "trend_stabilization_score": 80.0,
            "net_profit_yoy": 5.0,
            "previous_net_profit_yoy": 5.0,
        },
    ]

    observations = factor_ic_monitor.build_current_observations(
        rows, as_of=date(2026, 8, 14)
    ).set_index("code")

    assert observations.loc["000001", "factor_reversal"] > observations.loc[
        "000002", "factor_reversal"
    ]
    assert observations.loc["000002", "factor_momentum"] > observations.loc[
        "000001", "factor_momentum"
    ]
    assert observations.loc["000001", "factor_earnings"] == 15.0
