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
        history_sufficiency_score=82.0,
        history_sufficiency_quality="adequate",
        long_term_position_risk_score=20.0,
        no_falling_knife_filter=True,
        stabilization_days=5,
        trend_confirmation_level="WEAK",
        stop_loss_distance_pct=8.0,
        industry_cycle_quality="user_supplied",
    )


def _confirm_feature() -> FeatureSet:
    feature = _feature(trend_score=82.0, financial_score=75.0)
    feature.trend_confirmation_level = "MEDIUM"
    return feature


def test_signal_classification_thresholds() -> None:
    strategy = GenGeCycleBottomStrategy()

    assert strategy._classify(49.9, _feature(), []) == SignalType.REJECT
    assert strategy._classify(55.0, _feature(), []) == SignalType.WATCH
    assert strategy._classify(70.0, _feature(), []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(80.0, _confirm_feature(), []) == SignalType.CONFIRM_BUY


def test_risk_flags_cap_or_reject_signal() -> None:
    strategy = GenGeCycleBottomStrategy()

    assert strategy._classify(80.0, _confirm_feature(), ["debt_ratio_high"]) == SignalType.WATCH
    assert strategy._classify(80.0, _confirm_feature(), ["debt_ratio_extreme"]) == SignalType.REJECT
    weak_finance = _confirm_feature()
    weak_finance.financial_safety_score = 30.0
    assert strategy._classify(80.0, weak_finance, ["loss_making"]) == SignalType.REJECT


def test_confirm_buy_requires_trend_and_complete_financial_cycle_context() -> None:
    strategy = GenGeCycleBottomStrategy()
    weak_trend = _feature(trend_score=77.9, financial_score=75.0)
    missing_context = _confirm_feature()
    missing_context.missing_fields.extend(["financial", "industry_cycle"])

    assert strategy._classify(82.0, weak_trend, []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(82.0, missing_context, []) == SignalType.LEFT_SMALL_BUY
    assert strategy._classify(82.0, _confirm_feature(), []) == SignalType.CONFIRM_BUY


def test_quality_gates_downgrade_confirm_buy() -> None:
    strategy = GenGeCycleBottomStrategy()

    none_trend = _confirm_feature()
    none_trend.trend_confirmation_level = "NONE"
    assert strategy._classify(82.0, none_trend, []) == SignalType.WATCH

    falling_knife = _confirm_feature()
    falling_knife.no_falling_knife_filter = False
    assert strategy._classify(82.0, falling_knife, []) == SignalType.WATCH

    trap = _confirm_feature()
    trap.value_trap_score = 70
    trap.value_trap_flag = True
    assert strategy._classify(82.0, trap, ["value_trap_risk"]) == SignalType.WATCH

    wide_stop = _confirm_feature()
    wide_stop.stop_loss_distance_pct = 18.0
    assert strategy._classify(82.0, wide_stop, []) == SignalType.LEFT_SMALL_BUY

    wide_left = _feature()
    wide_left.stop_loss_distance_pct = 16.0
    assert strategy._classify(70.0, wide_left, []) == SignalType.WATCH

    high_execution_risk = _confirm_feature()
    high_execution_risk.execution_risk_score = 60.0
    assert strategy._classify(82.0, high_execution_risk, []) == SignalType.WATCH

    degraded_execution = _confirm_feature()
    degraded_execution.execution_risk_score = 25.0
    assert strategy._classify(82.0, degraded_execution, []) == SignalType.LEFT_SMALL_BUY

    early_stabilization = _confirm_feature()
    early_stabilization.stabilization_days = 3
    assert strategy._classify(82.0, early_stabilization, []) == SignalType.WATCH

    manual_cycle = _confirm_feature()
    manual_cycle.industry_cycle_quality = "manual_template"
    assert strategy._classify(82.0, manual_cycle, []) == SignalType.LEFT_SMALL_BUY

    high_long_term_risk = _confirm_feature()
    high_long_term_risk.long_term_position_risk_score = 70.0
    assert strategy._classify(82.0, high_long_term_risk, []) == SignalType.WATCH

    limited_history_wide_stop = _confirm_feature()
    limited_history_wide_stop.history_sufficiency_quality = "limited"
    limited_history_wide_stop.stop_loss_distance_pct = 8.0
    assert strategy._classify(82.0, limited_history_wide_stop, []) == SignalType.WATCH

    degraded_long_term_risk = _confirm_feature()
    degraded_long_term_risk.long_term_position_risk_score = 46.0
    degraded_long_term_risk.stop_loss_distance_pct = 6.0
    assert strategy._classify(82.0, degraded_long_term_risk, []) == SignalType.LEFT_SMALL_BUY
