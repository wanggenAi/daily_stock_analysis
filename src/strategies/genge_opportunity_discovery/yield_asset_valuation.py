"""Valuation primitives for regulated utilities and long-lived yield assets.

A broad "utility" industry label contains several different economic models:

* mature hydro / regulated assets can resemble long-duration equity yield assets;
* nuclear / renewable build-outs may have stable operating assets but very large
  growth capex and financing requirements;
* thermal generators combine utility characteristics with fuel-price, tariff and
  utilization cycles.

This module therefore avoids a universal utility P/E.  It exposes:

* an explicit FCFE stream DCF with **no implicit terminal value**;
* a Gordon FCFE path only when the caller explicitly chooses a stable/perpetual
  approximation;
* reverse implied cost of equity for the stable path;
* dividend coverage diagnostics;
* raw operating/capital-cycle evidence without a magic score.

``normalized_fcfe`` is always caller prepared.  The module intentionally does
not derive it from raw ``CFO - capex`` because maintenance capex, growth capex,
project debt and cash-flow classification can differ materially across utility
subtypes.

Nothing here creates a Formal BUY or bypasses downstream technical/risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class ExplicitFCFEValuationResult:
    required_return: Optional[float]
    pv_explicit_fcfe: Optional[float]
    explicit_terminal_equity_value: Optional[float]
    pv_terminal_equity_value: Optional[float]
    explicit_equity_adjustment: Optional[float]
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
class StableYieldValuationResult:
    normalized_fcfe: Optional[float]
    cost_of_equity: Optional[float]
    long_term_growth: Optional[float]
    fair_equity_value: Optional[float]
    current_market_cap: Optional[float]
    implied_cost_of_equity: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class DividendCoverageResult:
    normalized_fcfe: Optional[float]
    common_dividends: Optional[float]
    dividend_coverage_ratio: Optional[float]
    payout_of_fcfe: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class YieldAssetEvidence:
    generation_or_volume_growth: Optional[float]
    realized_tariff_or_unit_revenue_change: Optional[float]
    utilization_change: Optional[float]
    fuel_unit_cost_change: Optional[float]
    maintenance_capex: Optional[float]
    growth_capex: Optional[float]
    net_debt: Optional[float]
    interest_expense: Optional[float]
    normalized_fcfe: Optional[float]
    dividend_payout: Optional[float]
    hydrology_or_resource_variance: Optional[float]
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


def _coerce_cash_flows(values: Mapping[Any, Any]) -> tuple[Optional[Dict[int, float]], str]:
    result: Dict[int, float] = {}
    for raw_year, raw_value in values.items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            return None, "INVALID_FCFE_YEAR"
        value = _finite(raw_value)
        if year <= 0 or value is None:
            return None, "INVALID_FCFE"
        if year in result:
            return None, "DUPLICATE_FCFE_YEAR"
        result[year] = value
    if not result:
        return None, "EXPLICIT_FCFE_UNAVAILABLE"
    return result, "OK"


def value_explicit_fcfe_stream(
    *,
    annual_fcfe: Mapping[Any, Any],
    required_return: Any,
    explicit_terminal_equity_value: Any = None,
    explicit_equity_adjustment: Any = None,
    total_common_shares: Any = None,
    current_market_cap: Any = None,
) -> ExplicitFCFEValuationResult:
    """Value explicitly forecast FCFE with no automatic terminal assumption.

    The optional terminal equity value is interpreted at the end of the last
    explicit forecast year and discounted back.  For finite-life concessions or
    assets, callers can leave it ``None`` and the model will not manufacture a
    residual value.  For long-lived growth assets, callers may supply a terminal
    value only after constructing it explicitly upstream.
    """

    flows, flow_status = _coerce_cash_flows(annual_fcfe)
    required = _finite(required_return)
    terminal = _finite(explicit_terminal_equity_value)
    adjustment = _finite(explicit_equity_adjustment)
    shares = _finite(total_common_shares)
    market_cap = _finite(current_market_cap)

    common = dict(
        required_return=required,
        explicit_terminal_equity_value=terminal,
        explicit_equity_adjustment=adjustment,
        total_common_shares=shares,
        current_market_cap=market_cap,
    )

    if flow_status != "OK":
        status = flow_status
    elif required is None or required <= -1.0:
        status = "REQUIRED_RETURN_UNAVAILABLE"
    elif terminal is not None and terminal < 0:
        status = "INVALID_TERMINAL_EQUITY_VALUE"
    else:
        status = "OK"

    if status != "OK":
        return ExplicitFCFEValuationResult(
            **common,
            pv_explicit_fcfe=None,
            pv_terminal_equity_value=None,
            fair_equity_value=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert flows is not None and required is not None
    last_year = max(flows)
    pv_explicit = sum(value / ((1.0 + required) ** year) for year, value in flows.items())
    pv_terminal = None if terminal is None else terminal / ((1.0 + required) ** last_year)
    fair_equity = pv_explicit + (pv_terminal or 0.0) + (adjustment or 0.0)
    fair_price = fair_equity / shares if shares is not None and shares > 0 else None
    margin = fair_equity / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return ExplicitFCFEValuationResult(
        **common,
        pv_explicit_fcfe=pv_explicit,
        pv_terminal_equity_value=pv_terminal,
        fair_equity_value=fair_equity,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def value_stable_yield_asset(
    *,
    normalized_fcfe: Any,
    cost_of_equity: Any,
    long_term_growth: Any,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> StableYieldValuationResult:
    """Value a caller-declared stable/long-duration asset using Gordon FCFE."""

    fcfe = _finite(normalized_fcfe)
    required = _finite(cost_of_equity)
    growth = _finite(long_term_growth)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    common = dict(
        normalized_fcfe=fcfe,
        cost_of_equity=required,
        long_term_growth=growth,
        current_market_cap=market_cap,
        total_common_shares=shares,
    )

    if fcfe is None or fcfe <= 0:
        status = "NORMALIZED_FCFE_UNAVAILABLE"
    elif required is None:
        status = "COST_OF_EQUITY_UNAVAILABLE"
    elif growth is None:
        status = "LONG_TERM_GROWTH_UNAVAILABLE"
    elif required <= growth:
        status = "INVALID_COST_OF_EQUITY_GROWTH_RELATION"
    else:
        status = "OK"

    if status != "OK":
        return StableYieldValuationResult(
            **common,
            fair_equity_value=None,
            implied_cost_of_equity=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert fcfe is not None and required is not None and growth is not None
    fair_equity = fcfe * (1.0 + growth) / (required - growth)
    implied_cost = None
    if market_cap is not None and market_cap > 0:
        implied_cost = fcfe * (1.0 + growth) / market_cap + growth
    fair_price = fair_equity / shares if shares is not None and shares > 0 else None
    margin = fair_equity / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return StableYieldValuationResult(
        **common,
        fair_equity_value=fair_equity,
        implied_cost_of_equity=implied_cost,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def reverse_implied_cost_of_equity(
    *,
    current_market_cap: Any,
    normalized_fcfe: Any,
    long_term_growth: Any,
) -> tuple[Optional[float], str]:
    """Reverse-solve the cost of equity implied by a stable FCFE market cap."""

    market_cap = _finite(current_market_cap)
    fcfe = _finite(normalized_fcfe)
    growth = _finite(long_term_growth)
    if market_cap is None or market_cap <= 0:
        return None, "MARKET_CAP_UNAVAILABLE"
    if fcfe is None or fcfe <= 0:
        return None, "NORMALIZED_FCFE_UNAVAILABLE"
    if growth is None:
        return None, "LONG_TERM_GROWTH_UNAVAILABLE"
    return fcfe * (1.0 + growth) / market_cap + growth, "OK"


def evaluate_dividend_coverage(
    *, normalized_fcfe: Any, common_dividends: Any
) -> DividendCoverageResult:
    """Report dividend coverage without hard-coding a safe payout threshold."""

    fcfe = _finite(normalized_fcfe)
    dividends = _finite(common_dividends)
    if fcfe is None or fcfe <= 0:
        return DividendCoverageResult(fcfe, dividends, None, None, "NORMALIZED_FCFE_UNAVAILABLE")
    if dividends is None or dividends < 0:
        return DividendCoverageResult(fcfe, dividends, None, None, "COMMON_DIVIDENDS_UNAVAILABLE")
    return DividendCoverageResult(
        normalized_fcfe=fcfe,
        common_dividends=dividends,
        dividend_coverage_ratio=(None if dividends == 0 else fcfe / dividends),
        payout_of_fcfe=dividends / fcfe,
        status="OK",
    )


def collect_yield_asset_evidence(
    *,
    generation_or_volume_growth: Any = None,
    realized_tariff_or_unit_revenue_change: Any = None,
    utilization_change: Any = None,
    fuel_unit_cost_change: Any = None,
    maintenance_capex: Any = None,
    growth_capex: Any = None,
    net_debt: Any = None,
    interest_expense: Any = None,
    normalized_fcfe: Any = None,
    dividend_payout: Any = None,
    hydrology_or_resource_variance: Any = None,
) -> YieldAssetEvidence:
    """Carry utility/yield-asset drivers explicitly without a composite score."""

    values = {
        "generation_or_volume_growth": _finite(generation_or_volume_growth),
        "realized_tariff_or_unit_revenue_change": _finite(realized_tariff_or_unit_revenue_change),
        "utilization_change": _finite(utilization_change),
        "fuel_unit_cost_change": _finite(fuel_unit_cost_change),
        "maintenance_capex": _finite(maintenance_capex),
        "growth_capex": _finite(growth_capex),
        "net_debt": _finite(net_debt),
        "interest_expense": _finite(interest_expense),
        "normalized_fcfe": _finite(normalized_fcfe),
        "dividend_payout": _finite(dividend_payout),
        "hydrology_or_resource_variance": _finite(hydrology_or_resource_variance),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return YieldAssetEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
