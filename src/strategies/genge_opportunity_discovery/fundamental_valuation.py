"""Fundamental reverse-valuation primitives for opportunity research.

The module is deliberately pure and data-conditional.  It does not fetch data,
place trades, or bypass any existing entry/risk gate.  Its job is to turn
verified fundamental inputs into auditable earnings-quality, cycle-normalized,
and equity-value diagnostics.

Two failure modes motivated this layer:

1. A headline net profit inflated by investment/fair-value gains must not be
   capitalised as recurring operating earnings.
2. A boom-year cyclical profit must not automatically become the permanent
   earnings base used for a normal growth-company multiple.

Missing inputs remain missing.  The module prefers LOW confidence / ``None``
over fabricated precision.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


@dataclass(frozen=True)
class ValuationPolicy:
    """Versionable thresholds used only for diagnostics/confidence scoring."""

    high_recurring_ratio: float = 0.90
    medium_recurring_ratio: float = 0.70
    high_cash_conversion: float = 0.80
    medium_cash_conversion: float = 0.50
    low_quality_non_recurring_share: float = 0.40
    medium_quality_non_recurring_share: float = 0.20


@dataclass(frozen=True)
class CoreEarningsResult:
    headline_net_profit: Optional[float]
    normalized_core_operating_profit: Optional[float]
    recurring_profit: Optional[float]
    recurring_profit_ratio: Optional[float]
    non_recurring_profit_share: Optional[float]
    operating_cash_flow: Optional[float]
    cash_conversion_ratio: Optional[float]
    earnings_quality_score: float
    earnings_quality_confidence: str
    normalization_method: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CycleEarningsResult:
    forward_cycle_profit: Optional[float]
    through_cycle_normalized_profit: Optional[float]
    peak_earnings_discount: Optional[float]
    cycle_profit_gap: Optional[float]
    cycle_normalization_method: str
    cycle_valuation_confidence: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class EquityValueBridgeResult:
    normalized_core_operating_profit: Optional[float]
    fair_multiple: Optional[float]
    core_operating_value: Optional[float]
    non_operating_asset_value: Optional[float]
    net_cash_or_investment_adjustment: Optional[float]
    fair_equity_value: Optional[float]
    total_shares: Optional[float]
    fair_price: Optional[float]
    valuation_model_applicable: bool
    valuation_model_status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ReverseValuationResult:
    current_market_cap: Optional[float]
    assumed_fair_multiple: Optional[float]
    non_operating_asset_value: Optional[float]
    net_cash_or_investment_adjustment: Optional[float]
    implied_core_operating_value: Optional[float]
    implied_core_profit: Optional[float]
    reference_normalized_profit: Optional[float]
    required_profit_growth: Optional[float]
    expectation_gap: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    top = _finite(numerator)
    bottom = _finite(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    value = top / bottom
    return value if math.isfinite(value) else None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _lower_confidence(left: str, right: str) -> str:
    left_rank = CONFIDENCE_RANK.get(str(left).upper(), 0)
    right_rank = CONFIDENCE_RANK.get(str(right).upper(), 0)
    rank = min(left_rank, right_rank)
    for name, value in CONFIDENCE_RANK.items():
        if value == rank:
            return name
    return "LOW"


def normalize_core_earnings(
    *,
    net_profit: Any,
    recurring_profit: Any = None,
    investment_income: Any = None,
    fair_value_change_gain: Any = None,
    operating_cash_flow: Any = None,
    policy: ValuationPolicy = ValuationPolicy(),
) -> CoreEarningsResult:
    """Derive a sustainable core-profit starting point without double counting.

    Preferred source is a reported recurring/扣非 profit figure.  When that is
    unavailable, explicitly supplied investment/fair-value items can be removed
    from headline profit as a *low-confidence approximation*.  The fallback is
    never presented as equivalent to an audited recurring-profit figure.
    """

    headline = _finite(net_profit)
    recurring = _finite(recurring_profit)
    investment = _finite(investment_income)
    fair_value = _finite(fair_value_change_gain)
    cash_flow = _finite(operating_cash_flow)

    method = "DATA_INSUFFICIENT"
    confidence = "LOW"
    core: Optional[float] = None

    if recurring is not None:
        core = recurring
        method = "REPORTED_RECURRING_PROFIT"
        confidence = "HIGH"
    elif headline is not None and (investment is not None or fair_value is not None):
        # Signed subtraction is intentional: a negative non-operating item should
        # increase the estimated core result rather than being silently ignored.
        core = headline - (investment or 0.0) - (fair_value or 0.0)
        method = "HEADLINE_LESS_IDENTIFIED_NON_OPERATING_ITEMS"
        confidence = "LOW"
    elif headline is not None:
        core = headline
        method = "HEADLINE_ONLY_UNADJUSTED"
        confidence = "LOW"

    recurring_ratio = _safe_ratio(recurring, headline)
    if recurring_ratio is None and core is not None and headline not in (None, 0):
        recurring_ratio = _safe_ratio(core, headline)

    non_recurring_share = None
    if recurring_ratio is not None:
        non_recurring_share = 1.0 - recurring_ratio

    cash_conversion = _safe_ratio(cash_flow, core)

    score = 50.0
    if recurring is not None:
        if recurring_ratio is not None and recurring_ratio >= policy.high_recurring_ratio:
            score += 25.0
        elif recurring_ratio is not None and recurring_ratio >= policy.medium_recurring_ratio:
            score += 12.0
        elif recurring_ratio is not None:
            score -= 20.0
    elif investment is not None or fair_value is not None:
        score -= 15.0
    else:
        score -= 20.0

    if non_recurring_share is not None:
        if non_recurring_share >= policy.low_quality_non_recurring_share:
            score -= 20.0
        elif non_recurring_share >= policy.medium_quality_non_recurring_share:
            score -= 8.0

    if cash_conversion is not None:
        if cash_conversion >= policy.high_cash_conversion:
            score += 15.0
        elif cash_conversion >= policy.medium_cash_conversion:
            score += 7.0
        elif cash_conversion < 0:
            score -= 20.0
        else:
            score -= 8.0
    elif cash_flow is None:
        confidence = _lower_confidence(confidence, "MEDIUM")

    if core is None:
        score = 0.0
        confidence = "LOW"
    elif core <= 0:
        score = min(score, 25.0)

    return CoreEarningsResult(
        headline_net_profit=headline,
        normalized_core_operating_profit=core,
        recurring_profit=recurring,
        recurring_profit_ratio=recurring_ratio,
        non_recurring_profit_share=non_recurring_share,
        operating_cash_flow=cash_flow,
        cash_conversion_ratio=cash_conversion,
        earnings_quality_score=round(_clamp(score), 2),
        earnings_quality_confidence=confidence,
        normalization_method=method,
    )


def normalize_cycle_earnings(
    *,
    forward_cycle_profit: Any,
    through_cycle_normalized_profit: Any = None,
    through_cycle_ratio: Any = None,
    is_cyclical: bool = True,
) -> CycleEarningsResult:
    """Keep current-cycle earnings separate from through-cycle earnings.

    The function deliberately does not invent a cycle haircut.  For a cyclical
    company, callers must provide either an independently estimated through-cycle
    profit or an explicit, auditable normalization ratio.  Missing cycle inputs
    remain ``None`` and confidence stays LOW.
    """

    forward = _finite(forward_cycle_profit)
    normalized = _finite(through_cycle_normalized_profit)
    ratio = _finite(through_cycle_ratio)
    method = "DATA_INSUFFICIENT"
    confidence = "LOW"

    if not is_cyclical:
        if normalized is None:
            normalized = forward
            method = "NON_CYCLICAL_FORWARD_AS_NORMALIZED"
        else:
            method = "EXPLICIT_THROUGH_CYCLE_PROFIT"
        confidence = "MEDIUM" if normalized is not None else "LOW"
    elif normalized is not None:
        method = "EXPLICIT_THROUGH_CYCLE_PROFIT"
        confidence = "HIGH"
    elif forward is not None and ratio is not None and 0 < ratio <= 1:
        normalized = forward * ratio
        method = "EXPLICIT_THROUGH_CYCLE_RATIO"
        confidence = "MEDIUM"
    elif forward is not None:
        method = "CYCLE_NORMALIZATION_REQUIRED"

    peak_discount = None
    gap = None
    if forward is not None and normalized is not None:
        gap = forward - normalized
        if forward > 0:
            peak_discount = 1.0 - normalized / forward

    return CycleEarningsResult(
        forward_cycle_profit=forward,
        through_cycle_normalized_profit=normalized,
        peak_earnings_discount=peak_discount,
        cycle_profit_gap=gap,
        cycle_normalization_method=method,
        cycle_valuation_confidence=confidence,
    )


def bridge_equity_value(
    *,
    normalized_core_operating_profit: Any,
    fair_multiple: Any,
    non_operating_asset_value: Any = None,
    net_cash_or_investment_adjustment: Any = None,
    total_shares: Any = None,
) -> EquityValueBridgeResult:
    """Value core earnings, then bridge explicitly to equity value.

    Non-operating gains are not capitalised as recurring earnings, but verified
    non-operating assets/net cash can still contribute to equity value.  This
    prevents the opposite error of treating the underlying assets as worthless.
    """

    profit = _finite(normalized_core_operating_profit)
    multiple = _finite(fair_multiple)
    assets = _finite(non_operating_asset_value)
    adjustment = _finite(net_cash_or_investment_adjustment)
    shares = _finite(total_shares)

    if profit is None:
        status = "VALUATION_DATA_INSUFFICIENT"
        core_value = fair_value = fair_price = None
        applicable = False
    elif profit <= 0:
        status = "PE_MODEL_NOT_APPLICABLE"
        core_value = fair_value = fair_price = None
        applicable = False
    elif multiple is None or multiple <= 0:
        status = "FAIR_MULTIPLE_UNAVAILABLE"
        core_value = fair_value = fair_price = None
        applicable = False
    else:
        core_value = profit * multiple
        fair_value = core_value + (assets or 0.0) + (adjustment or 0.0)
        fair_price = fair_value / shares if shares is not None and shares > 0 else None
        status = "OK" if shares is not None and shares > 0 else "OK_PRICE_UNAVAILABLE"
        applicable = True

    return EquityValueBridgeResult(
        normalized_core_operating_profit=profit,
        fair_multiple=multiple,
        core_operating_value=core_value,
        non_operating_asset_value=assets,
        net_cash_or_investment_adjustment=adjustment,
        fair_equity_value=fair_value,
        total_shares=shares,
        fair_price=fair_price,
        valuation_model_applicable=applicable,
        valuation_model_status=status,
    )


def reverse_implied_profit(
    *,
    current_market_cap: Any,
    assumed_fair_multiple: Any,
    reference_normalized_profit: Any = None,
    non_operating_asset_value: Any = None,
    net_cash_or_investment_adjustment: Any = None,
) -> ReverseValuationResult:
    """Reverse-solve the recurring core profit implied by the market cap."""

    market_cap = _finite(current_market_cap)
    multiple = _finite(assumed_fair_multiple)
    reference = _finite(reference_normalized_profit)
    assets = _finite(non_operating_asset_value)
    adjustment = _finite(net_cash_or_investment_adjustment)

    if market_cap is None or market_cap <= 0:
        status = "MARKET_CAP_UNAVAILABLE"
        operating_value = implied = growth = None
    elif multiple is None or multiple <= 0:
        status = "FAIR_MULTIPLE_UNAVAILABLE"
        operating_value = implied = growth = None
    else:
        operating_value = market_cap - (assets or 0.0) - (adjustment or 0.0)
        if operating_value < 0:
            status = "NON_OPERATING_VALUE_EXCEEDS_MARKET_CAP"
            implied = growth = None
        else:
            implied = operating_value / multiple
            growth = None
            if reference is not None and reference > 0:
                growth = implied / reference - 1.0
            status = "OK" if reference is not None and reference > 0 else "OK_REFERENCE_PROFIT_UNAVAILABLE"

    return ReverseValuationResult(
        current_market_cap=market_cap,
        assumed_fair_multiple=multiple,
        non_operating_asset_value=assets,
        net_cash_or_investment_adjustment=adjustment,
        implied_core_operating_value=operating_value,
        implied_core_profit=implied,
        reference_normalized_profit=reference,
        required_profit_growth=growth,
        expectation_gap=growth,
        status=status,
    )


def build_three_scenario_valuation(
    *,
    scenarios: Mapping[str, Mapping[str, Any]],
    current_market_cap: Any = None,
    total_shares: Any = None,
) -> Dict[str, Any]:
    """Build auditable bear/base/bull values from caller-supplied assumptions.

    Required scenario keys are ``bear``, ``base`` and ``bull``.  The engine does
    not create missing earnings or multiples.  Each scenario may provide:

    - ``normalized_core_operating_profit``
    - ``fair_multiple``
    - ``non_operating_asset_value``
    - ``net_cash_or_investment_adjustment``
    - ``forward_cycle_profit``
    - ``through_cycle_normalized_profit`` or ``through_cycle_ratio``
    - ``is_cyclical``
    """

    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        cycle = normalize_cycle_earnings(
            forward_cycle_profit=raw.get("forward_cycle_profit"),
            through_cycle_normalized_profit=raw.get("through_cycle_normalized_profit"),
            through_cycle_ratio=raw.get("through_cycle_ratio"),
            is_cyclical=bool(raw.get("is_cyclical", False)),
        )
        valuation_profit = _finite(raw.get("normalized_core_operating_profit"))
        if valuation_profit is None:
            valuation_profit = cycle.through_cycle_normalized_profit
        bridge = bridge_equity_value(
            normalized_core_operating_profit=valuation_profit,
            fair_multiple=raw.get("fair_multiple"),
            non_operating_asset_value=raw.get("non_operating_asset_value"),
            net_cash_or_investment_adjustment=raw.get("net_cash_or_investment_adjustment"),
            total_shares=total_shares,
        )
        market_cap = _finite(current_market_cap)
        upside_downside = None
        if market_cap is not None and market_cap > 0 and bridge.fair_equity_value is not None:
            upside_downside = bridge.fair_equity_value / market_cap - 1.0
        output["scenarios"][name] = {
            **cycle.to_dict(),
            **bridge.to_dict(),
            "upside_downside": upside_downside,
        }

    base = scenarios["base"]
    base_row = output["scenarios"]["base"]
    output["reverse_valuation"] = reverse_implied_profit(
        current_market_cap=current_market_cap,
        assumed_fair_multiple=base.get("fair_multiple"),
        reference_normalized_profit=base_row.get("normalized_core_operating_profit"),
        non_operating_asset_value=base.get("non_operating_asset_value"),
        net_cash_or_investment_adjustment=base.get("net_cash_or_investment_adjustment"),
    ).to_dict()
    return output
