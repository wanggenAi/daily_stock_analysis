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
