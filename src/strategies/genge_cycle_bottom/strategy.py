"""Deterministic GenGe Cycle Bottom Strategy logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd

from .features import FeatureSet, build_feature_set, estimate_stop_loss, estimate_take_profit
from .signals import SignalType, StrategySignal


REJECT_RISK_FLAGS = {"st_or_delisting_risk", "loss_making"}
WATCH_CAP_RISK_FLAGS = {"debt_ratio_high", "debt_ratio_extreme", "negative_operating_cash_flow"}


@dataclass(frozen=True)
class StrategyConfig:
    max_single_position_pct: float = 20.0
    left_small_buy_position_pct: float = 5.0
    confirm_buy_position_pct: float = 10.0


class GenGeCycleBottomStrategy:
    """Pure-logic signal generator.

    The strategy never reads future bars. Future returns are calculated only by
    the backtest module after this class has emitted a signal.
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def generate_signal(
        self,
        *,
        code: str,
        stock_name: str,
        as_of_date,
        price_df: pd.DataFrame,
        valuation_df: Optional[pd.DataFrame] = None,
        financial_df: Optional[pd.DataFrame] = None,
        benchmark_df: Optional[pd.DataFrame] = None,
        industry_cycle_df: Optional[pd.DataFrame] = None,
        industry: Optional[str] = None,
        extra_risk_flags: Optional[Iterable[str]] = None,
    ) -> StrategySignal:
        features = build_feature_set(
            price_df=price_df,
            as_of_date=as_of_date,
            valuation_df=valuation_df,
            financial_df=financial_df,
            benchmark_df=benchmark_df,
            industry_cycle_df=industry_cycle_df,
            industry=industry,
        )
        risk_flags = sorted(set(features.risk_flags + list(extra_risk_flags or [])))
        total_score = self._total_score(features)
        signal_type = self._classify(total_score, features, risk_flags)
        max_position_pct = self._position_for_signal(signal_type)
        invalidation_reason = self._invalidation_reason(features, risk_flags)

        return StrategySignal(
            code=code,
            stock_name=stock_name or code,
            as_of_date=features.as_of_date.isoformat(),
            signal_type=signal_type,
            total_score=round(total_score, 2),
            price_percentile_score=round(features.price_percentile_score, 2),
            valuation_score=round(features.valuation_score, 2),
            financial_safety_score=round(features.financial_safety_score, 2),
            trend_stabilization_score=round(features.trend_stabilization_score, 2),
            market_environment_score=round(features.market_environment_score, 2),
            industry_cycle_score=round(features.industry_cycle_score, 2),
            price_percentile_3y=features.price_percentile_3y,
            price_percentile_5y=features.price_percentile_5y,
            price_percentile_10y=features.price_percentile_10y,
            distance_from_5y_low_pct=features.distance_from_5y_low_pct,
            distance_from_5y_high_pct=features.distance_from_5y_high_pct,
            distance_from_10y_low_pct=features.distance_from_10y_low_pct,
            distance_from_10y_high_pct=features.distance_from_10y_high_pct,
            risk_flags=risk_flags,
            missing_fields=features.missing_fields,
            stop_loss=estimate_stop_loss(features.close, features.ma60) if max_position_pct > 0 else None,
            take_profit=estimate_take_profit(features.close) if max_position_pct > 0 else None,
            invalidation_reason=invalidation_reason,
            max_position_pct=max_position_pct,
            explanation=self._explain(features, total_score, signal_type),
        )

    @staticmethod
    def _total_score(features: FeatureSet) -> float:
        return (
            features.price_percentile_score * 0.24
            + features.valuation_score * 0.18
            + features.financial_safety_score * 0.22
            + features.trend_stabilization_score * 0.20
            + features.market_environment_score * 0.08
            + features.industry_cycle_score * 0.08
        )

    @staticmethod
    def _classify(total_score: float, features: FeatureSet, risk_flags: list[str]) -> SignalType:
        if "st_or_delisting_risk" in risk_flags or "debt_ratio_extreme" in risk_flags:
            return SignalType.REJECT
        if "loss_making" in risk_flags and features.financial_safety_score < 45:
            return SignalType.REJECT

        if total_score < 50:
            signal = SignalType.REJECT
        elif total_score < 65:
            signal = SignalType.WATCH
        elif total_score < 78:
            signal = SignalType.LEFT_SMALL_BUY
        elif features.trend_stabilization_score >= 72:
            signal = SignalType.CONFIRM_BUY
        else:
            signal = SignalType.LEFT_SMALL_BUY

        if any(flag in WATCH_CAP_RISK_FLAGS for flag in risk_flags) and signal not in (SignalType.REJECT, SignalType.WATCH):
            return SignalType.WATCH
        if features.market_environment_score < 35 and signal == SignalType.CONFIRM_BUY:
            return SignalType.LEFT_SMALL_BUY
        return signal

    def _position_for_signal(self, signal_type: SignalType) -> float:
        if signal_type == SignalType.LEFT_SMALL_BUY:
            return min(self.config.left_small_buy_position_pct, self.config.max_single_position_pct)
        if signal_type == SignalType.CONFIRM_BUY:
            return min(self.config.confirm_buy_position_pct, self.config.max_single_position_pct)
        if signal_type == SignalType.ADD:
            return min(15.0, self.config.max_single_position_pct)
        return 0.0

    @staticmethod
    def _invalidation_reason(features: FeatureSet, risk_flags: list[str]) -> str:
        reasons: list[str] = []
        if features.ma20 is not None:
            reasons.append("收盘价重新跌破 MA20 且三日无法收回")
        if features.ma60 is not None:
            reasons.append("跌破 MA60 或低位平台下沿")
        if any(flag in risk_flags for flag in ("loss_making", "negative_operating_cash_flow", "debt_ratio_extreme")):
            reasons.append("财务安全边际恶化")
        return "；".join(reasons) or "低位修复逻辑失效或数据质量不足"

    @staticmethod
    def _explain(features: FeatureSet, total_score: float, signal_type: SignalType) -> str:
        percentile = features.price_percentile_5y
        percentile_text = "估值/价格分位数据不足" if percentile is None else f"5年价格分位约 {percentile:.1%}"
        trend_text = "趋势已有右侧确认" if features.trend_stabilization_score >= 72 else "趋势仍偏观察"
        industry_text = (
            f"行业周期 {features.industry_cycle_phase}"
            if features.industry_cycle_phase
            else "行业周期数据不足"
        )
        return (
            f"{percentile_text}，技术止跌分 {features.trend_stabilization_score:.1f}，"
            f"财务安全分 {features.financial_safety_score:.1f}，行业周期分 {features.industry_cycle_score:.1f}，"
            f"总分 {total_score:.1f}，"
            f"信号为 {signal_type.value}；{trend_text}。"
            f"{industry_text}。"
        )
