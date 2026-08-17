"""Finite-life NAV primitives for mines and other depleting resource assets.

A mine is not just a capacity-cycle manufacturer. Current accounting earnings
answer what the operation earned at today's price/cost mix; recoverable reserves
answer how much finite economic inventory remains underground. This module
therefore values explicitly scoped resource assets from finite recoverable units
and a normalized, point-in-time researched commodity price/cost deck.

The model deliberately has no automatic terminal value, reserve-growth guess,
commodity-price escalation, scarcity premium or target multiple. Exploration
upside and resources that are not yet sufficiently supported for the chosen
valuation scope must be added only as explicit, separately justified equity
adjustments upstream.

For vertically integrated companies, downstream refining/manufacturing value
must be supplied to the corporate bridge as a *non-overlapping* non-resource
segment value. Mine cash flows must not also be capitalized inside that segment
value. This is essential for tungsten-style mine -> smelting -> hard-alloy
businesses.

Nothing here creates a Formal BUY, changes position sizing, or bypasses risk
gates. It is a research-only valuation primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional, Sequence


@dataclass(frozen=True)
class ResourceAssetNAVResult:
    asset_id: str
    economic_scope_id: str
    economic_ownership: Optional[float]
    recoverable_units_100pct: Optional[float]
    annual_production_units_100pct: Optional[float]
    normalized_realized_unit_price: Optional[float]
    unit_cash_operating_cost: Optional[float]
    sustaining_capex_per_unit: Optional[float]
    royalty_rate_on_revenue: Optional[float]
    cash_tax_rate_on_positive_pretax_cash_flow: Optional[float]
    required_return: Optional[float]
    closure_and_reclamation_cash_outflow_100pct: Optional[float]
    modeled_years: int
    pv_100pct_resource_cash_flows: Optional[float]
    attributable_resource_nav: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ResourceEquityNAVResult:
    unique_scope_count: int
    attributable_resource_nav: Optional[float]
    non_resource_segment_value: Optional[float]
    unrestricted_cash: Optional[float]
    interest_bearing_debt_not_in_resource_cash_flows: Optional[float]
    other_corporate_liability_pv_not_in_resource_cash_flows: Optional[float]
    explicit_equity_adjustment: Optional[float]
    fair_equity_nav: Optional[float]
    current_market_cap: Optional[float]
    total_common_shares: Optional[float]
    fair_nav_per_share: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ResourceAssetEvidence:
    reported_resource_units: Optional[float]
    reported_reserve_units: Optional[float]
    recoverable_units_used_in_model: Optional[float]
    current_annual_production_units: Optional[float]
    normalized_annual_production_units: Optional[float]
    current_realized_unit_price: Optional[float]
    normalized_realized_unit_price: Optional[float]
    current_unit_cash_operating_cost: Optional[float]
    normalized_unit_cash_operating_cost: Optional[float]
    sustaining_capex_per_unit: Optional[float]
    economic_ownership: Optional[float]
    royalty_rate_on_revenue: Optional[float]
    cash_tax_rate_on_positive_pretax_cash_flow: Optional[float]
    required_return: Optional[float]
    closure_and_reclamation_cash_outflow_100pct: Optional[float]
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


def value_finite_life_resource_asset(
    *,
    asset_id: str,
    economic_scope_id: str,
    economic_ownership: Any,
    recoverable_units_100pct: Any,
    annual_production_units_100pct: Any,
    normalized_realized_unit_price: Any,
    unit_cash_operating_cost: Any,
    sustaining_capex_per_unit: Any,
    royalty_rate_on_revenue: Any,
    cash_tax_rate_on_positive_pretax_cash_flow: Any,
    required_return: Any,
    closure_and_reclamation_cash_outflow_100pct: Any = 0.0,
) -> ResourceAssetNAVResult:
    """Discount one finite-life resource asset's remaining after-tax cash flow.

    Production is modeled at the explicitly supplied normalized annual rate
    until recoverable units are depleted; the last year may be fractional.
    Royalties are charged on revenue. Cash tax is charged only on positive
    pre-tax modeled cash flow because this primitive does not invent tax-loss
    utilization outside the asset scope. A separately researched closure /
    reclamation outflow is charged in the final modeled year.

    The constant normalized price/cost deck permits a closed-form present-value
    calculation. Runtime therefore does not grow with modeled mine life; a unit
    mismatch cannot turn valuation into a million-iteration loop.

    All physical and cash-flow inputs are 100%-asset values. Economic ownership
    is applied only after discounting, which keeps the scope auditable.
    """

    asset = str(asset_id or "").strip()
    scope = str(economic_scope_id or "").strip()
    ownership = _finite(economic_ownership)
    recoverable = _finite(recoverable_units_100pct)
    annual_production = _finite(annual_production_units_100pct)
    price = _finite(normalized_realized_unit_price)
    cash_cost = _finite(unit_cash_operating_cost)
    sustaining_capex = _finite(sustaining_capex_per_unit)
    royalty = _finite(royalty_rate_on_revenue)
    tax_rate = _finite(cash_tax_rate_on_positive_pretax_cash_flow)
    discount_rate = _finite(required_return)
    closure = _finite(closure_and_reclamation_cash_outflow_100pct)

    if not asset:
        status = "ASSET_ID_UNAVAILABLE"
    elif not scope:
        status = "ECONOMIC_SCOPE_ID_UNAVAILABLE"
    elif ownership is None or not 0.0 <= ownership <= 1.0:
        status = "INVALID_OR_MISSING_ECONOMIC_OWNERSHIP"
    elif recoverable is None or recoverable <= 0:
        status = "RECOVERABLE_UNITS_UNAVAILABLE"
    elif annual_production is None or annual_production <= 0:
        status = "ANNUAL_PRODUCTION_UNAVAILABLE"
    elif price is None or price < 0:
        status = "NORMALIZED_UNIT_PRICE_UNAVAILABLE"
    elif cash_cost is None or cash_cost < 0:
        status = "UNIT_CASH_OPERATING_COST_UNAVAILABLE"
    elif sustaining_capex is None or sustaining_capex < 0:
        status = "SUSTAINING_CAPEX_UNAVAILABLE"
    elif royalty is None or not 0.0 <= royalty <= 1.0:
        status = "INVALID_OR_MISSING_ROYALTY_RATE"
    elif tax_rate is None or not 0.0 <= tax_rate <= 1.0:
        status = "INVALID_OR_MISSING_CASH_TAX_RATE"
    elif discount_rate is None or discount_rate < 0.0:
        status = "INVALID_OR_MISSING_REQUIRED_RETURN"
    elif closure is None or closure < 0:
        status = "INVALID_OR_MISSING_CLOSURE_OUTFLOW"
    else:
        status = "OK"

    if status != "OK":
        return ResourceAssetNAVResult(
            asset_id=asset,
            economic_scope_id=scope,
            economic_ownership=ownership,
            recoverable_units_100pct=recoverable,
            annual_production_units_100pct=annual_production,
            normalized_realized_unit_price=price,
            unit_cash_operating_cost=cash_cost,
            sustaining_capex_per_unit=sustaining_capex,
            royalty_rate_on_revenue=royalty,
            cash_tax_rate_on_positive_pretax_cash_flow=tax_rate,
            required_return=discount_rate,
            closure_and_reclamation_cash_outflow_100pct=closure,
            modeled_years=0,
            pv_100pct_resource_cash_flows=None,
            attributable_resource_nav=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert ownership is not None
    assert recoverable is not None and annual_production is not None
    assert price is not None and cash_cost is not None and sustaining_capex is not None
    assert royalty is not None and tax_rate is not None and discount_rate is not None
    assert closure is not None

    pretax_cash_flow_per_unit = (
        price - cash_cost - sustaining_capex - price * royalty
    )
    after_tax_cash_flow_per_unit = pretax_cash_flow_per_unit - (
        max(pretax_cash_flow_per_unit, 0.0) * tax_rate
    )

    full_years = int(math.floor(recoverable / annual_production))
    remainder = recoverable - full_years * annual_production
    tolerance = max(recoverable, annual_production) * 1e-12
    if remainder <= tolerance:
        remainder = 0.0
    modeled_years = full_years + (1 if remainder > 0.0 else 0)

    full_year_cash_flow = annual_production * after_tax_cash_flow_per_unit
    if full_years <= 0:
        full_year_pv = 0.0
    elif discount_rate == 0.0:
        full_year_pv = full_year_cash_flow * full_years
    else:
        annuity_factor = (1.0 - (1.0 + discount_rate) ** (-full_years)) / discount_rate
        full_year_pv = full_year_cash_flow * annuity_factor

    partial_year_pv = 0.0
    if remainder > 0.0:
        partial_year_pv = (
            remainder
            * after_tax_cash_flow_per_unit
            * (1.0 + discount_rate) ** (-modeled_years)
        )

    closure_pv = closure * (1.0 + discount_rate) ** (-modeled_years)
    pv = full_year_pv + partial_year_pv - closure_pv

    return ResourceAssetNAVResult(
        asset_id=asset,
        economic_scope_id=scope,
        economic_ownership=ownership,
        recoverable_units_100pct=recoverable,
        annual_production_units_100pct=annual_production,
        normalized_realized_unit_price=price,
        unit_cash_operating_cost=cash_cost,
        sustaining_capex_per_unit=sustaining_capex,
        royalty_rate_on_revenue=royalty,
        cash_tax_rate_on_positive_pretax_cash_flow=tax_rate,
        required_return=discount_rate,
        closure_and_reclamation_cash_outflow_100pct=closure,
        modeled_years=modeled_years,
        pv_100pct_resource_cash_flows=pv,
        attributable_resource_nav=pv * ownership,
        valuation_model_applicable=True,
        status="OK",
    )


def bridge_resource_equity_nav(
    *,
    resource_asset_results: Sequence[ResourceAssetNAVResult],
    non_resource_segment_value: Any,
    unrestricted_cash: Any,
    interest_bearing_debt_not_in_resource_cash_flows: Any,
    other_corporate_liability_pv_not_in_resource_cash_flows: Any,
    explicit_equity_adjustment: Any = 0.0,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> ResourceEquityNAVResult:
    """Bridge non-overlapping resource NAV and downstream value to common equity.

    ``non_resource_segment_value`` must exclude mine/resource cash flows already
    represented by ``resource_asset_results``. Debt/liability inputs likewise
    must exclude obligations already embedded in those asset cash flows. The
    explicit names are intentionally verbose because double counting is one of
    the main failure modes in vertically integrated resource companies.
    """

    non_resource = _finite(non_resource_segment_value)
    cash = _finite(unrestricted_cash)
    debt = _finite(interest_bearing_debt_not_in_resource_cash_flows)
    liabilities = _finite(other_corporate_liability_pv_not_in_resource_cash_flows)
    adjustment = _finite(explicit_equity_adjustment)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    scopes = [result.economic_scope_id for result in resource_asset_results]
    unique_scope_count = len(set(scopes))

    if not resource_asset_results:
        status = "RESOURCE_ASSET_NAV_UNAVAILABLE"
    elif len(scopes) != unique_scope_count:
        status = "DUPLICATE_RESOURCE_ECONOMIC_SCOPE"
    elif any(
        not result.valuation_model_applicable
        or result.attributable_resource_nav is None
        for result in resource_asset_results
    ):
        status = "RESOURCE_ASSET_NAV_INCOMPLETE"
    elif non_resource is None or non_resource < 0:
        status = "NON_RESOURCE_SEGMENT_VALUE_UNAVAILABLE"
    elif cash is None or cash < 0:
        status = "UNRESTRICTED_CASH_UNAVAILABLE"
    elif debt is None or debt < 0:
        status = "CORPORATE_DEBT_UNAVAILABLE"
    elif liabilities is None or liabilities < 0:
        status = "CORPORATE_LIABILITY_PV_UNAVAILABLE"
    elif adjustment is None:
        status = "EXPLICIT_EQUITY_ADJUSTMENT_UNAVAILABLE"
    elif market_cap is not None and market_cap < 0:
        status = "INVALID_CURRENT_MARKET_CAP"
    elif shares is not None and shares <= 0:
        status = "INVALID_TOTAL_COMMON_SHARES"
    else:
        status = "OK"

    if status != "OK":
        return ResourceEquityNAVResult(
            unique_scope_count=unique_scope_count,
            attributable_resource_nav=None,
            non_resource_segment_value=non_resource,
            unrestricted_cash=cash,
            interest_bearing_debt_not_in_resource_cash_flows=debt,
            other_corporate_liability_pv_not_in_resource_cash_flows=liabilities,
            explicit_equity_adjustment=adjustment,
            fair_equity_nav=None,
            current_market_cap=market_cap,
            total_common_shares=shares,
            fair_nav_per_share=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert non_resource is not None and cash is not None and debt is not None
    assert liabilities is not None and adjustment is not None
    resource_nav = sum(
        result.attributable_resource_nav or 0.0 for result in resource_asset_results
    )
    equity_nav = resource_nav + non_resource + cash - debt - liabilities + adjustment
    fair_per_share = None if shares is None else equity_nav / shares
    margin_of_safety = (
        None
        if market_cap is None or equity_nav <= 0
        else (equity_nav - market_cap) / equity_nav
    )

    return ResourceEquityNAVResult(
        unique_scope_count=unique_scope_count,
        attributable_resource_nav=resource_nav,
        non_resource_segment_value=non_resource,
        unrestricted_cash=cash,
        interest_bearing_debt_not_in_resource_cash_flows=debt,
        other_corporate_liability_pv_not_in_resource_cash_flows=liabilities,
        explicit_equity_adjustment=adjustment,
        fair_equity_nav=equity_nav,
        current_market_cap=market_cap,
        total_common_shares=shares,
        fair_nav_per_share=fair_per_share,
        margin_of_safety=margin_of_safety,
        valuation_model_applicable=True,
        status="OK",
    )


def build_resource_asset_evidence(
    *,
    reported_resource_units: Any = None,
    reported_reserve_units: Any = None,
    recoverable_units_used_in_model: Any = None,
    current_annual_production_units: Any = None,
    normalized_annual_production_units: Any = None,
    current_realized_unit_price: Any = None,
    normalized_realized_unit_price: Any = None,
    current_unit_cash_operating_cost: Any = None,
    normalized_unit_cash_operating_cost: Any = None,
    sustaining_capex_per_unit: Any = None,
    economic_ownership: Any = None,
    royalty_rate_on_revenue: Any = None,
    cash_tax_rate_on_positive_pretax_cash_flow: Any = None,
    required_return: Any = None,
    closure_and_reclamation_cash_outflow_100pct: Any = None,
) -> ResourceAssetEvidence:
    """Build auditable valuation-readiness evidence without imputing values."""

    raw = {
        "reported_resource_units": _finite(reported_resource_units),
        "reported_reserve_units": _finite(reported_reserve_units),
        "recoverable_units_used_in_model": _finite(recoverable_units_used_in_model),
        "current_annual_production_units": _finite(current_annual_production_units),
        "normalized_annual_production_units": _finite(normalized_annual_production_units),
        "current_realized_unit_price": _finite(current_realized_unit_price),
        "normalized_realized_unit_price": _finite(normalized_realized_unit_price),
        "current_unit_cash_operating_cost": _finite(current_unit_cash_operating_cost),
        "normalized_unit_cash_operating_cost": _finite(normalized_unit_cash_operating_cost),
        "sustaining_capex_per_unit": _finite(sustaining_capex_per_unit),
        "economic_ownership": _finite(economic_ownership),
        "royalty_rate_on_revenue": _finite(royalty_rate_on_revenue),
        "cash_tax_rate_on_positive_pretax_cash_flow": _finite(
            cash_tax_rate_on_positive_pretax_cash_flow
        ),
        "required_return": _finite(required_return),
        "closure_and_reclamation_cash_outflow_100pct": _finite(
            closure_and_reclamation_cash_outflow_100pct
        ),
    }
    required = (
        "recoverable_units_used_in_model",
        "normalized_annual_production_units",
        "normalized_realized_unit_price",
        "normalized_unit_cash_operating_cost",
        "sustaining_capex_per_unit",
        "economic_ownership",
        "royalty_rate_on_revenue",
        "cash_tax_rate_on_positive_pretax_cash_flow",
        "required_return",
        "closure_and_reclamation_cash_outflow_100pct",
    )
    missing = tuple(field for field in required if raw[field] is None)
    completeness = (len(required) - len(missing)) / len(required)
    return ResourceAssetEvidence(
        **raw,
        evidence_completeness=completeness,
        missing_fields=missing,
    )
