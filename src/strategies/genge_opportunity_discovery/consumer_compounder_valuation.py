"""Stable-compounder valuation primitives with explicit growth duration.

This adapter is intended for profitable, durable consumer/brand/manufacturing
franchises where neither a low historical price percentile nor an arbitrary
"quality PE" is enough to establish value.

The primary bridge is explicit owner earnings / FCFE-like cash flow and a
finite high-growth period followed by a Gordon terminal value.  Every growth
rate, duration and required return is caller supplied.  The reverse function
solves the near-term growth rate implied by current market capitalization over
an explicit bracket, which fits the project's expectation-gap framework.

Important scope guard: raw consolidated operating cash flow may be unusable
when a financial subsidiary or other structurally different business causes
large deposit/loan/interbank cash movements.  In that case the raw
``CFO - capex`` shortcut fails closed unless the caller supplies a separately
verified adjusted owner-earnings measure.

Nothing in this module creates a Formal BUY or changes downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class OwnerEarningsResult:
    operating_cash_flow: Optional[float]
    capital_expenditure: Optional[float]
    raw_owner_earnings: Optional[float]
    explicit_adjusted_owner_earnings: Optional[float]
    normalized_owner_earnings: Optional[float]
    reference_normalized_profit: Optional[float]
    owner_earnings_conversion: Optional[float]
    cash_flow_scope_reliable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CompounderDCFResult:
    normalized_owner_earnings: Optional[float]
    near_term_growth_rate: Optional[float]
    growth_years: Optional[int]
    required_return: Optional[float]
    terminal_growth_rate: Optional[float]
    explicit_non_operating_equity_adjustment: Optional[float]
    pv_explicit_owner_earnings: Optional[float]
    terminal_owner_earnings: Optional[float]
    terminal_value_at_horizon: Optional[float]
    pv_terminal_value: Optional[float]
    fair_equity_value: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    current_market_cap: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class GrowthConsistencyResult:
    core_roic: Optional[float]
    reinvestment_rate: Optional[float]
    roic_implied_sustainable_growth: Optional[float]
    scenario_growth_rate: Optional[float]
    growth_consistency_gap: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CompounderQualityEvidence:
    recurring_profit_growth: Optional[float]
    organic_revenue_growth: Optional[float]
    volume_growth: Optional[float]
    price_mix_growth: Optional[float]
    gross_margin: Optional[float]
    gross_margin_change: Optional[float]
    core_roic: Optional[float]
    owner_earnings_conversion: Optional[float]
    capex_intensity: Optional[float]
    working_capital_intensity: Optional[float]
    channel_inventory_change: Optional[float]
    evidence_completeness: float
    missing_fields: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.__dict__)
        payload["missing_fields"] = list(self.missing_fields)
        return payload


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def derive_owner_earnings(
    *,
    operating_cash_flow: Any = None,
    capital_expenditure: Any = None,
    reference_normalized_profit: Any = None,
    cash_flow_scope_reliable: bool = True,
    explicit_adjusted_owner_earnings: Any = None,
) -> OwnerEarningsResult:
    """Derive owner earnings while guarding against cash-flow scope mismatch.

    ``capital_expenditure`` is cash paid for fixed/intangible/other long-lived
    assets when the caller chooses the conservative ``CFO - capex`` measure.
    The function does not guess maintenance capex versus growth capex.

    When ``cash_flow_scope_reliable`` is false, raw CFO/capex remains visible
    diagnostically but is not accepted as normalized owner earnings.  A
    separately verified ``explicit_adjusted_owner_earnings`` can restore model
    applicability.
    """

    ocf = _finite(operating_cash_flow)
    capex = _finite(capital_expenditure)
    adjusted = _finite(explicit_adjusted_owner_earnings)
    reference_profit = _finite(reference_normalized_profit)

    raw = None
    if ocf is not None and capex is not None and capex >= 0:
        raw = ocf - capex

    normalized = adjusted
    status = "EXPLICIT_ADJUSTED_OWNER_EARNINGS" if adjusted is not None else "OWNER_EARNINGS_UNAVAILABLE"
    if normalized is None and cash_flow_scope_reliable and raw is not None:
        normalized = raw
        status = "RAW_CFO_LESS_CAPEX"
    elif normalized is None and not cash_flow_scope_reliable:
        status = "CASH_FLOW_SCOPE_DISTORTED_REQUIRES_ADJUSTMENT"

    conversion = None
    if normalized is not None and reference_profit is not None and reference_profit != 0:
        conversion = normalized / reference_profit

    return OwnerEarningsResult(
        operating_cash_flow=ocf,
        capital_expenditure=capex,
        raw_owner_earnings=raw,
        explicit_adjusted_owner_earnings=adjusted,
        normalized_owner_earnings=normalized,
        reference_normalized_profit=reference_profit,
        owner_earnings_conversion=conversion,
        cash_flow_scope_reliable=bool(cash_flow_scope_reliable),
        status=status,
    )


def _validate_dcf_inputs(
    *,
    normalized_owner_earnings: Any,
    near_term_growth_rate: Any,
    growth_years: Any,
    required_return: Any,
    terminal_growth_rate: Any,
) -> tuple[Optional[float], Optional[float], Optional[int], Optional[float], Optional[float], str]:
    cash = _finite(normalized_owner_earnings)
    growth = _finite(near_term_growth_rate)
    required = _finite(required_return)
    terminal_growth = _finite(terminal_growth_rate)
    try:
        years = int(growth_years)
    except (TypeError, ValueError):
        years = None

    if cash is None or cash <= 0:
        return cash, growth, years, required, terminal_growth, "NORMALIZED_OWNER_EARNINGS_UNAVAILABLE"
    if growth is None or growth <= -1.0:
        return cash, growth, years, required, terminal_growth, "NEAR_TERM_GROWTH_UNAVAILABLE"
    if years is None or years <= 0 or years != growth_years:
        return cash, growth, years, required, terminal_growth, "INVALID_GROWTH_DURATION"
    if required is None or required <= -1.0:
        return cash, growth, years, required, terminal_growth, "REQUIRED_RETURN_UNAVAILABLE"
    if terminal_growth is None or terminal_growth <= -1.0:
        return cash, growth, years, required, terminal_growth, "TERMINAL_GROWTH_UNAVAILABLE"
    if required <= terminal_growth:
        return cash, growth, years, required, terminal_growth, "INVALID_REQUIRED_RETURN_TERMINAL_GROWTH_RELATION"
    return cash, growth, years, required, terminal_growth, "OK"


def value_compounder_dcf(
    *,
    normalized_owner_earnings: Any,
    near_term_growth_rate: Any,
    growth_years: Any,
    required_return: Any,
    terminal_growth_rate: Any,
    explicit_non_operating_equity_adjustment: Any = None,
    total_common_shares: Any = None,
    current_market_cap: Any = None,
) -> CompounderDCFResult:
    """Value a stable compounder with an explicit finite growth-duration DCF."""

    cash, growth, years, required, terminal_growth, status = _validate_dcf_inputs(
        normalized_owner_earnings=normalized_owner_earnings,
        near_term_growth_rate=near_term_growth_rate,
        growth_years=growth_years,
        required_return=required_return,
        terminal_growth_rate=terminal_growth_rate,
    )
    adjustment = _finite(explicit_non_operating_equity_adjustment)
    shares = _finite(total_common_shares)
    market_cap = _finite(current_market_cap)

    common = dict(
        normalized_owner_earnings=cash,
        near_term_growth_rate=growth,
        growth_years=years,
        required_return=required,
        terminal_growth_rate=terminal_growth,
        explicit_non_operating_equity_adjustment=adjustment,
        total_common_shares=shares,
        current_market_cap=market_cap,
    )

    if status != "OK":
        return CompounderDCFResult(
            **common,
            pv_explicit_owner_earnings=None,
            terminal_owner_earnings=None,
            terminal_value_at_horizon=None,
            pv_terminal_value=None,
            fair_equity_value=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert cash is not None and growth is not None and years is not None
    assert required is not None and terminal_growth is not None

    pv_explicit = 0.0
    owner_earnings_at_year = cash
    for year in range(1, years + 1):
        owner_earnings_at_year *= 1.0 + growth
        pv_explicit += owner_earnings_at_year / ((1.0 + required) ** year)

    terminal_owner_earnings = owner_earnings_at_year * (1.0 + terminal_growth)
    terminal_value = terminal_owner_earnings / (required - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + required) ** years)
    fair_equity = pv_explicit + pv_terminal + (adjustment or 0.0)
    fair_price = fair_equity / shares if shares is not None and shares > 0 else None
    margin = fair_equity / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return CompounderDCFResult(
        **common,
        pv_explicit_owner_earnings=pv_explicit,
        terminal_owner_earnings=terminal_owner_earnings,
        terminal_value_at_horizon=terminal_value,
        pv_terminal_value=pv_terminal,
        fair_equity_value=fair_equity,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def reverse_implied_near_term_growth(
    *,
    current_market_cap: Any,
    normalized_owner_earnings: Any,
    growth_years: Any,
    required_return: Any,
    terminal_growth_rate: Any,
    lower_growth_bound: Any,
    upper_growth_bound: Any,
    explicit_non_operating_equity_adjustment: Any = None,
    tolerance: float = 1e-8,
    max_iterations: int = 200,
) -> tuple[Optional[float], str]:
    """Reverse-solve the finite-period growth rate implied by market cap.

    The caller must provide both growth bounds.  This module refuses to invent a
    universal search interval such as 0-20%, because the economically plausible
    range varies by franchise and life-cycle stage.
    """

    market_cap = _finite(current_market_cap)
    lower = _finite(lower_growth_bound)
    upper = _finite(upper_growth_bound)
    adjustment = _finite(explicit_non_operating_equity_adjustment)

    if market_cap is None or market_cap <= 0:
        return None, "MARKET_CAP_UNAVAILABLE"
    if lower is None or upper is None or lower >= upper or lower <= -1.0:
        return None, "INVALID_GROWTH_BOUNDS"

    target_operating_value = market_cap - (adjustment or 0.0)
    if target_operating_value <= 0:
        return None, "NON_OPERATING_VALUE_EXCEEDS_MARKET_CAP"

    def gap(growth: float) -> tuple[Optional[float], str]:
        result = value_compounder_dcf(
            normalized_owner_earnings=normalized_owner_earnings,
            near_term_growth_rate=growth,
            growth_years=growth_years,
            required_return=required_return,
            terminal_growth_rate=terminal_growth_rate,
        )
        if not result.valuation_model_applicable or result.fair_equity_value is None:
            return None, result.status
        return result.fair_equity_value - target_operating_value, "OK"

    lower_gap, status = gap(lower)
    if lower_gap is None:
        return None, status
    upper_gap, status = gap(upper)
    if upper_gap is None:
        return None, status
    if abs(lower_gap) <= tolerance:
        return lower, "OK"
    if abs(upper_gap) <= tolerance:
        return upper, "OK"
    if lower_gap * upper_gap > 0:
        return None, "IMPLIED_GROWTH_NOT_BRACKETED"

    lo, hi = lower, upper
    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        mid_gap, status = gap(mid)
        if mid_gap is None:
            return None, status
        if abs(mid_gap) <= tolerance or abs(hi - lo) <= tolerance:
            return mid, "OK"
        if lower_gap * mid_gap <= 0:
            hi = mid
            upper_gap = mid_gap
        else:
            lo = mid
            lower_gap = mid_gap
    return (lo + hi) / 2.0, "MAX_ITERATIONS_REACHED"


def evaluate_growth_consistency(
    *,
    core_roic: Any,
    reinvestment_rate: Any,
    scenario_growth_rate: Any = None,
) -> GrowthConsistencyResult:
    """Apply the accounting identity ``g ~= ROIC * reinvestment rate``.

    This is a consistency diagnostic, not a forecast.  It prevents a high
    growth scenario from being accepted without a plausible capital-efficiency
    / reinvestment mechanism.
    """

    roic = _finite(core_roic)
    reinvestment = _finite(reinvestment_rate)
    scenario_growth = _finite(scenario_growth_rate)
    if roic is None or reinvestment is None:
        return GrowthConsistencyResult(
            core_roic=roic,
            reinvestment_rate=reinvestment,
            roic_implied_sustainable_growth=None,
            scenario_growth_rate=scenario_growth,
            growth_consistency_gap=None,
            status="ROIC_OR_REINVESTMENT_UNAVAILABLE",
        )
    implied_growth = roic * reinvestment
    gap = None if scenario_growth is None else scenario_growth - implied_growth
    return GrowthConsistencyResult(
        core_roic=roic,
        reinvestment_rate=reinvestment,
        roic_implied_sustainable_growth=implied_growth,
        scenario_growth_rate=scenario_growth,
        growth_consistency_gap=gap,
        status="OK",
    )


def collect_compounder_quality_evidence(
    *,
    recurring_profit_growth: Any = None,
    organic_revenue_growth: Any = None,
    volume_growth: Any = None,
    price_mix_growth: Any = None,
    gross_margin: Any = None,
    gross_margin_change: Any = None,
    core_roic: Any = None,
    owner_earnings_conversion: Any = None,
    capex_intensity: Any = None,
    working_capital_intensity: Any = None,
    channel_inventory_change: Any = None,
) -> CompounderQualityEvidence:
    values = {
        "recurring_profit_growth": _finite(recurring_profit_growth),
        "organic_revenue_growth": _finite(organic_revenue_growth),
        "volume_growth": _finite(volume_growth),
        "price_mix_growth": _finite(price_mix_growth),
        "gross_margin": _finite(gross_margin),
        "gross_margin_change": _finite(gross_margin_change),
        "core_roic": _finite(core_roic),
        "owner_earnings_conversion": _finite(owner_earnings_conversion),
        "capex_intensity": _finite(capex_intensity),
        "working_capital_intensity": _finite(working_capital_intensity),
        "channel_inventory_change": _finite(channel_inventory_change),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return CompounderQualityEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )


def build_compounder_three_scenario_valuation(
    *,
    normalized_owner_earnings: Any,
    scenarios: Mapping[str, Mapping[str, Any]],
    explicit_non_operating_equity_adjustment: Any = None,
    total_common_shares: Any = None,
    current_market_cap: Any = None,
) -> Dict[str, Any]:
    """Build explicit Bear/Base/Bull growth-duration valuations."""

    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing compounder valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        output["scenarios"][name] = value_compounder_dcf(
            normalized_owner_earnings=raw.get("normalized_owner_earnings", normalized_owner_earnings),
            near_term_growth_rate=raw.get("near_term_growth_rate"),
            growth_years=raw.get("growth_years"),
            required_return=raw.get("required_return"),
            terminal_growth_rate=raw.get("terminal_growth_rate"),
            explicit_non_operating_equity_adjustment=raw.get(
                "explicit_non_operating_equity_adjustment", explicit_non_operating_equity_adjustment
            ),
            total_common_shares=total_common_shares,
            current_market_cap=current_market_cap,
        ).to_dict()
    return output
