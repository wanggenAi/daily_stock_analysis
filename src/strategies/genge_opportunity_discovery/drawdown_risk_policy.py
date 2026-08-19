"""Drawdown-first portfolio risk policy for GenGe opportunity research.

This module does not create BUY signals. It converts an already-qualified
research/trade setup into a bounded position budget and provides a strict
acceptance rule for walk-forward strategy calibration.

Design principle: improve drawdown without hiding the cost in destroyed CAGR.
A candidate configuration is deployable only when both drawdown and return
retention constraints pass on out-of-sample data.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence


RULE_VERSION = "genge_drawdown_first_risk_v1"


@dataclass(frozen=True)
class DrawdownRiskPolicy:
    # Portfolio-level acceptance gates.
    target_max_drawdown_pct: float = 15.0
    hard_max_drawdown_pct: float = 20.0
    min_relative_drawdown_improvement_pct: float = 20.0
    min_cagr_retention_pct: float = 70.0

    # Position/risk-budget constraints.
    risk_per_trade_pct: float = 1.25
    max_single_name_fraction: float = 0.20
    max_industry_fraction: float = 0.35
    minimum_stop_distance_pct: float = 5.0

    # Exposure scaling as portfolio drawdown deepens.
    dd_5_exposure_multiplier: float = 1.00
    dd_10_exposure_multiplier: float = 0.75
    dd_15_exposure_multiplier: float = 0.50
    dd_20_exposure_multiplier: float = 0.25


DEFAULT_DRAWDOWN_POLICY = DrawdownRiskPolicy()


@dataclass(frozen=True)
class StrategyMetrics:
    name: str
    cagr_pct: float
    max_drawdown_pct: float
    excess_cagr_pct: float | None = None
    turnover_per_year: float | None = None


@dataclass(frozen=True)
class CandidateEvaluation:
    metrics: StrategyMetrics
    accepted: bool
    deployment_allowed: bool
    calmar_ratio: float | None
    drawdown_improvement_pct: float | None
    cagr_retention_pct: float | None
    reasons: tuple[str, ...]


def _finite(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def drawdown_magnitude(drawdown_pct: float | int | None) -> float:
    """Normalize either -12.3 or +12.3 notation to a positive magnitude."""

    value = _finite(drawdown_pct)
    return abs(value) if value is not None else math.inf


def max_drawdown_pct(equity_values: Iterable[float]) -> float | None:
    peak: float | None = None
    worst = 0.0
    seen = False
    for raw in equity_values:
        value = _finite(raw)
        if value is None or value <= 0:
            continue
        seen = True
        peak = value if peak is None else max(peak, value)
        worst = max(worst, (peak - value) / peak * 100.0)
    return round(worst, 6) if seen else None


def cagr_pct(start_equity: float, end_equity: float, years: float) -> float | None:
    start = _finite(start_equity)
    end = _finite(end_equity)
    horizon = _finite(years)
    if start is None or end is None or horizon is None or start <= 0 or end <= 0 or horizon <= 0:
        return None
    return ((end / start) ** (1.0 / horizon) - 1.0) * 100.0


def calmar_ratio(cagr: float | int | None, max_drawdown: float | int | None) -> float | None:
    growth = _finite(cagr)
    dd = drawdown_magnitude(max_drawdown)
    if growth is None or not math.isfinite(dd) or dd <= 0:
        return None
    return growth / dd


def exposure_multiplier(
    portfolio_drawdown_pct: float | int | None,
    policy: DrawdownRiskPolicy = DEFAULT_DRAWDOWN_POLICY,
) -> float:
    """Scale new risk as the portfolio moves farther below its equity peak."""

    dd = drawdown_magnitude(portfolio_drawdown_pct)
    if not math.isfinite(dd):
        return 0.0
    if dd < 5.0:
        return policy.dd_5_exposure_multiplier
    if dd < 10.0:
        return policy.dd_10_exposure_multiplier
    if dd < 15.0:
        return policy.dd_15_exposure_multiplier
    if dd < policy.hard_max_drawdown_pct:
        return policy.dd_20_exposure_multiplier
    return 0.0


def position_fraction(
    *,
    stop_distance_pct: float,
    portfolio_drawdown_pct: float = 0.0,
    current_industry_fraction: float = 0.0,
    current_name_fraction: float = 0.0,
    policy: DrawdownRiskPolicy = DEFAULT_DRAWDOWN_POLICY,
) -> float:
    """Return maximum additional portfolio fraction for a qualified setup.

    Risk budget is expressed as the fraction of total equity lost if the frozen
    stop is reached. Example: 1.25% risk budget / 10% stop distance = 12.5%
    gross position before portfolio/industry/name caps and drawdown scaling.
    """

    stop = _finite(stop_distance_pct)
    if stop is None or stop <= 0:
        return 0.0
    stop = max(stop, policy.minimum_stop_distance_pct)
    risk_budget_fraction = policy.risk_per_trade_pct / stop

    name_room = max(0.0, policy.max_single_name_fraction - max(0.0, float(current_name_fraction)))
    industry_room = max(0.0, policy.max_industry_fraction - max(0.0, float(current_industry_fraction)))
    gross_room = min(risk_budget_fraction, name_room, industry_room)
    scaled = gross_room * exposure_multiplier(portfolio_drawdown_pct, policy)
    return round(max(0.0, min(1.0, scaled)), 6)


def _relative_improvement(baseline_dd: float, candidate_dd: float) -> float | None:
    if baseline_dd <= 0 or not math.isfinite(baseline_dd) or not math.isfinite(candidate_dd):
        return None
    return (baseline_dd - candidate_dd) / baseline_dd * 100.0


def _return_retention(baseline_cagr: float, candidate_cagr: float) -> float | None:
    if baseline_cagr <= 0:
        return 100.0 if candidate_cagr >= baseline_cagr else None
    return candidate_cagr / baseline_cagr * 100.0


def evaluate_candidate(
    baseline: StrategyMetrics,
    candidate: StrategyMetrics,
    policy: DrawdownRiskPolicy = DEFAULT_DRAWDOWN_POLICY,
) -> CandidateEvaluation:
    """Evaluate a walk-forward configuration against strict drawdown gates."""

    baseline_dd = drawdown_magnitude(baseline.max_drawdown_pct)
    candidate_dd = drawdown_magnitude(candidate.max_drawdown_pct)
    improvement = _relative_improvement(baseline_dd, candidate_dd)
    retention = _return_retention(float(baseline.cagr_pct), float(candidate.cagr_pct))
    reasons: list[str] = []

    if candidate_dd > policy.hard_max_drawdown_pct:
        reasons.append("hard_max_drawdown_exceeded")

    target_met = candidate_dd <= policy.target_max_drawdown_pct
    relative_met = improvement is not None and improvement >= policy.min_relative_drawdown_improvement_pct
    if not target_met and not relative_met:
        reasons.append("drawdown_not_improved_enough")

    if retention is None or retention < policy.min_cagr_retention_pct:
        reasons.append("cagr_retention_too_low")

    if candidate.cagr_pct <= 0:
        reasons.append("non_positive_cagr")

    accepted = not reasons
    return CandidateEvaluation(
        metrics=candidate,
        accepted=accepted,
        deployment_allowed=accepted,
        calmar_ratio=calmar_ratio(candidate.cagr_pct, candidate_dd),
        drawdown_improvement_pct=round(improvement, 6) if improvement is not None else None,
        cagr_retention_pct=round(retention, 6) if retention is not None else None,
        reasons=tuple(reasons),
    )


def select_drawdown_optimized(
    baseline: StrategyMetrics,
    candidates: Sequence[StrategyMetrics],
    policy: DrawdownRiskPolicy = DEFAULT_DRAWDOWN_POLICY,
) -> CandidateEvaluation | None:
    """Select the best *deployable* configuration by Calmar, never by CAGR alone.

    If no configuration satisfies all hard gates, return the best diagnostic
    candidate with ``deployment_allowed=False``. Callers must not silently
    deploy that fallback.
    """

    if not candidates:
        return None
    evaluations = [evaluate_candidate(baseline, candidate, policy) for candidate in candidates]

    def key(item: CandidateEvaluation) -> tuple[float, float, float]:
        calmar = item.calmar_ratio if item.calmar_ratio is not None else -math.inf
        dd = drawdown_magnitude(item.metrics.max_drawdown_pct)
        return (calmar, float(item.metrics.cagr_pct), -dd)

    accepted = [item for item in evaluations if item.accepted]
    if accepted:
        return max(accepted, key=key)

    diagnostic = max(evaluations, key=key)
    return CandidateEvaluation(
        metrics=diagnostic.metrics,
        accepted=False,
        deployment_allowed=False,
        calmar_ratio=diagnostic.calmar_ratio,
        drawdown_improvement_pct=diagnostic.drawdown_improvement_pct,
        cagr_retention_pct=diagnostic.cagr_retention_pct,
        reasons=diagnostic.reasons + ("no_deployable_configuration",),
    )
