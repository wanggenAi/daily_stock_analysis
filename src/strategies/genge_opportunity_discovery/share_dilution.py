"""Share-count and dilution primitives for forward valuation research.

Forward fair-value work must not divide a 2027/2028 profit assumption by a stale
current share count when known equity incentives, placements, convertibles, or
other issuance can materially expand the denominator.  Likewise, consensus EPS
from third parties can become internally inconsistent around bonus issues and
capital changes; where profit forecasts are available, this module makes the
share-count assumption explicit and derives EPS from profit instead.

The module is pure and data-conditional.  It does not assume that announced
shares will definitely be issued.  Callers must pass only dilution assumptions
they want represented in the scenario and can keep announced-but-uncertain
items in a separate scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class DilutedShareCountResult:
    current_shares: Optional[float]
    incentive_shares: Optional[float]
    financing_shares: Optional[float]
    other_potential_shares: Optional[float]
    valuation_shares: Optional[float]
    dilution_ratio: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class PerShareValuationResult:
    equity_value: Optional[float]
    current_shares: Optional[float]
    valuation_shares: Optional[float]
    current_share_fair_price: Optional[float]
    diluted_fair_price: Optional[float]
    dilution_price_impact: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ProfitPerShareResult:
    forecast_net_profit: Optional[float]
    current_shares: Optional[float]
    valuation_shares: Optional[float]
    current_share_eps: Optional[float]
    diluted_eps: Optional[float]
    reported_consensus_eps: Optional[float]
    reported_eps_gap: Optional[float]
    consensus_eps_consistent: Optional[bool]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def resolve_valuation_shares(
    *,
    current_shares: Any,
    incentive_shares: Any = None,
    financing_shares: Any = None,
    other_potential_shares: Any = None,
) -> DilutedShareCountResult:
    """Resolve an explicit forward share-count assumption.

    ``None`` means the caller has not included that dilution source.  Zero means
    the caller explicitly assumes no shares from that source.  The function does
    not probability-weight announced issuance and never invents a dilution rate.
    """

    current = _finite(current_shares)
    incentive = _finite(incentive_shares)
    financing = _finite(financing_shares)
    other = _finite(other_potential_shares)

    if current is None or current <= 0:
        return DilutedShareCountResult(
            current_shares=current,
            incentive_shares=incentive,
            financing_shares=financing,
            other_potential_shares=other,
            valuation_shares=None,
            dilution_ratio=None,
            status="CURRENT_SHARE_COUNT_UNAVAILABLE",
        )

    supplied = [value for value in (incentive, financing, other) if value is not None]
    if any(value < 0 for value in supplied):
        return DilutedShareCountResult(
            current_shares=current,
            incentive_shares=incentive,
            financing_shares=financing,
            other_potential_shares=other,
            valuation_shares=None,
            dilution_ratio=None,
            status="INVALID_NEGATIVE_DILUTION_INPUT",
        )

    extra = sum(supplied)
    valuation_shares = current + extra
    dilution_ratio = valuation_shares / current - 1.0
    status = "EXPLICIT_DILUTION_ASSUMPTION" if supplied else "CURRENT_SHARES_ONLY"

    return DilutedShareCountResult(
        current_shares=current,
        incentive_shares=incentive,
        financing_shares=financing,
        other_potential_shares=other,
        valuation_shares=valuation_shares,
        dilution_ratio=dilution_ratio,
        status=status,
    )


def per_share_value(
    *,
    equity_value: Any,
    current_shares: Any,
    valuation_shares: Any = None,
) -> PerShareValuationResult:
    """Convert equity value to current-share and forward-diluted fair prices."""

    value = _finite(equity_value)
    current = _finite(current_shares)
    diluted = _finite(valuation_shares)

    if value is None:
        status = "EQUITY_VALUE_UNAVAILABLE"
        current_price = diluted_price = impact = None
    elif current is None or current <= 0:
        status = "CURRENT_SHARE_COUNT_UNAVAILABLE"
        current_price = diluted_price = impact = None
    elif diluted is not None and diluted <= 0:
        status = "VALUATION_SHARE_COUNT_INVALID"
        current_price = diluted_price = impact = None
    else:
        current_price = value / current
        if diluted is None:
            diluted_price = None
            impact = None
            status = "CURRENT_SHARES_ONLY"
        else:
            diluted_price = value / diluted
            impact = diluted_price / current_price - 1.0
            status = "OK"

    return PerShareValuationResult(
        equity_value=value,
        current_shares=current,
        valuation_shares=diluted,
        current_share_fair_price=current_price,
        diluted_fair_price=diluted_price,
        dilution_price_impact=impact,
        status=status,
    )


def eps_from_profit(
    *,
    forecast_net_profit: Any,
    current_shares: Any,
    valuation_shares: Any = None,
    reported_consensus_eps: Any = None,
    consistency_tolerance: float = 0.08,
) -> ProfitPerShareResult:
    """Derive EPS from net-profit forecasts and explicit share counts.

    Net-profit forecasts are preferred as the stable cross-source primitive.
    ``reported_consensus_eps`` is only an audit comparison.  If its gap from the
    EPS implied by the current share count exceeds ``consistency_tolerance``, the
    result flags the reported EPS as inconsistent instead of silently mixing the
    two denominators.
    """

    profit = _finite(forecast_net_profit)
    current = _finite(current_shares)
    diluted = _finite(valuation_shares)
    reported = _finite(reported_consensus_eps)
    tolerance = _finite(consistency_tolerance)

    if profit is None:
        return ProfitPerShareResult(
            forecast_net_profit=profit,
            current_shares=current,
            valuation_shares=diluted,
            current_share_eps=None,
            diluted_eps=None,
            reported_consensus_eps=reported,
            reported_eps_gap=None,
            consensus_eps_consistent=None,
            status="FORECAST_PROFIT_UNAVAILABLE",
        )
    if current is None or current <= 0:
        return ProfitPerShareResult(
            forecast_net_profit=profit,
            current_shares=current,
            valuation_shares=diluted,
            current_share_eps=None,
            diluted_eps=None,
            reported_consensus_eps=reported,
            reported_eps_gap=None,
            consensus_eps_consistent=None,
            status="CURRENT_SHARE_COUNT_UNAVAILABLE",
        )
    if diluted is not None and diluted <= 0:
        return ProfitPerShareResult(
            forecast_net_profit=profit,
            current_shares=current,
            valuation_shares=diluted,
            current_share_eps=None,
            diluted_eps=None,
            reported_consensus_eps=reported,
            reported_eps_gap=None,
            consensus_eps_consistent=None,
            status="VALUATION_SHARE_COUNT_INVALID",
        )

    current_eps = profit / current
    diluted_eps = profit / diluted if diluted is not None else None
    gap = None
    consistent = None
    status = "OK"

    if reported is not None and current_eps != 0:
        gap = reported / current_eps - 1.0
        if tolerance is None or tolerance < 0:
            status = "INVALID_CONSISTENCY_TOLERANCE"
        else:
            consistent = abs(gap) <= tolerance
            if not consistent:
                status = "REPORTED_EPS_SHARE_COUNT_MISMATCH"

    return ProfitPerShareResult(
        forecast_net_profit=profit,
        current_shares=current,
        valuation_shares=diluted,
        current_share_eps=current_eps,
        diluted_eps=diluted_eps,
        reported_consensus_eps=reported,
        reported_eps_gap=gap,
        consensus_eps_consistent=consistent,
        status=status,
    )
