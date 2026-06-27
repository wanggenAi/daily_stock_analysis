from __future__ import annotations

from datetime import date

from src.strategies.genge_cycle_bottom.features import FeatureSet
from src.strategies.genge_cycle_bottom.signals import SignalType
from src.strategies.genge_cycle_bottom.strategy import GenGeCycleBottomStrategy


def _feature(trend_score: float = 70.0, financial_score: float = 70.0) -> FeatureSet:
    return FeatureSet(
        as_of_date=date(2024, 1, 1),
        close=10.0,
        financial_safety_score=financial_score,
        trend_stabilization_score=trend_score,
        market_environment_score=60.0,
        industry_cycle_score=50.0,
    )


def _confirm_feature() -> FeatureSet:
    return _feature(trend_score=82.0, financial_score=75.0)


def test_signal_classification_thresholds() -> None:
    strategy = GenGeCycleBottomStrategy()

    assert strategy._classify(49.9, _feature(), []) == SignalType.REJECT
    assert strategy._classify(55.0, _feature(), []) == SignalType.WATCH
    assert strategy._classify(70.0, _feature(), []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(80.0, _feature(trend_score=80.0), []) == SignalType.CONFIRM_BUY


def test_risk_flags_cap_or_reject_signal() -> None:
    strategy = GenGeCycleBottomStrategy()

    assert strategy._classify(80.0, _feature(trend_score=80.0), ["debt_ratio_high"]) == SignalType.WATCH
    assert strategy._classify(80.0, _feature(trend_score=80.0), ["debt_ratio_extreme"]) == SignalType.REJECT
    assert strategy._classify(80.0, _feature(trend_score=80.0, financial_score=30.0), ["loss_making"]) == SignalType.REJECT


def test_confirm_buy_requires_trend_and_complete_financial_cycle_context() -> None:
    strategy = GenGeCycleBottomStrategy()
    weak_trend = _feature(trend_score=77.9, financial_score=75.0)
    missing_context = _confirm_feature()
    missing_context.missing_fields.extend(["financial", "industry_cycle"])

    assert strategy._classify(82.0, weak_trend, []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(82.0, missing_context, []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(82.0, _confirm_feature(), []) == SignalType.CONFIRM_BUY
