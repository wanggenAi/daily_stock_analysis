"""Project-NAV primitives for residential property developers.

Property developers are deliberately not valued primarily from current-period
P/E.  Revenue and profit recognized today normally come from projects presold
in earlier periods, while the economic value available to common shareholders
is driven by the remaining project cash flows, current sales/collections,
remaining construction and land commitments, financing and inventory quality.

The preferred valuation unit in this module is therefore an explicitly scoped
project (or non-overlapping project portfolio) with annual equity cash flows.
The module does **not** infer NAV from accounting inventory and contains no
universal inventory haircut.  Book inventory stays an evidence field only.

Project cash flows must already reflect the project's operating economics
(sales collections, remaining construction cost, taxes, selling expenses and
project-level financing/liabilities as appropriate).  The corporate bridge then
adds/subtracts only items explicitly declared to be outside those project cash
flows, which reduces double-counting risk.

Nothing here creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional, Sequence


@dataclass(frozen=True)
class DeveloperProjectNAVResult:
    project_id: str
    economic_ownership: Optional[float]
    required_return: Optional[float]
    pv_100pct_project_equity_cash_flows: Optional[float]
    attributable_project_nav: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class DeveloperEquityNAVResult:
    unique_project_count: int
    attributable_project_nav: Optional[float]
    unrestricted_cash: Optional[float]
    non_project_asset_value: Optional[float]
    corporate_interest_bearing_debt_not_in_projects: Optional[float]
    corporate_liability_pv_not_in_projects: Optional[float]
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
class DeveloperLiquidityResult:
    unrestricted_cash: Optional[float]
    expected_cash_collections_within_horizon: Optional[float]
    debt_principal_due_within_horizon: Optional[float]
    committed_land_and_construction_outflows_within_horizon: Optional[float]
    other_committed_cash_outflows_within_horizon: Optional[float]
    horizon_liquidity_surplus: Optional[float]
    coverage_of_committed_outflows: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class DeveloperEvidence:
    contracted_sales_growth: Optional[float]
    contracted_sales_area_growth: Optional[float]
    cash_collection_ratio: Optional[float]
    recognized_revenue_growth: Optional[float]
    recognized_gross_margin: Optional[float]
    recognized_gross_margin_change: Optional[float]
    inventory_book_value: Optional[float]
    inventory_impairment_charge: Optional[float]
    contract_liabilities: Optional[float]
    new_land_equity_spend: Optional[float]
    new_land_sale_value: Optional[float]
    interest_bearing_debt: Optional[float]
    near_term_debt: Optional[float]
    average_financing_cost: Optional[float]
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
            return None, "INVALID_PROJECT_CASH_FLOW_YEAR"
        value = _finite(raw_value)
        if year <= 0 or value is None:
            return None, "INVALID_PROJECT_CASH_FLOW"
        if year in result:
            return None, "DUPLICATE_PROJECT_CASH_FLOW_YEAR"
        result[year] = value
    if not result:
        return None, "PROJECT_EQUITY_CASH_FLOWS_UNAVAILABLE"
    return result, "OK"


def value_project_equity_cash_flows(
    *,
    project_id: str,
    annual_project_equity_cash_flows_100pct: Mapping[Any, Any],
    economic_ownership: Any,
    required_return: Any,
) -> DeveloperProjectNAVResult:
    """Present-value one non-overlapping project's remaining equity cash flows.

    Cash flows are at the 100%-project level and can be negative during land /
    construction periods.  ``economic_ownership`` converts the resulting NAV to
    the listed company's attributable share.  No terminal value is invented:
    the explicit cash-flow schedule must cover the modeled remaining project
    economics or be prepared upstream with a separately justified residual.
    """

    clean_id = str(project_id or "").strip()
    ownership = _finite(economic_ownership)
    required = _finite(required_return)
    flows, flow_status = _coerce_cash_flows(annual_project_equity_cash_flows_100pct)

    if not clean_id:
        status = "PROJECT_ID_UNAVAILABLE"
    elif ownership is None or not 0.0 <= ownership <= 1.0:
        status = "INVALID_OR_MISSING_ECONOMIC_OWNERSHIP"
    elif required is None or required <= -1.0:
        status = "INVALID_OR_MISSING_REQUIRED_RETURN"
    elif flow_status != "OK":
        status = flow_status
    else:
        status = "OK"

    if status != "OK":
        return DeveloperProjectNAVResult(
            project_id=clean_id,
            economic_ownership=ownership,
            required_return=required,
            pv_100pct_project_equity_cash_flows=None,
            attributable_project_nav=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert flows is not None and ownership is not None and required is not None
    pv_100pct = sum(value / ((1.0 + required) ** year) for year, value in flows.items())
    return DeveloperProjectNAVResult(
        project_id=clean_id,
        economic_ownership=ownership,
        required_return=required,
        pv_100pct_project_equity_cash_flows=pv_100pct,
        attributable_project_nav=pv_100pct * ownership,
        valuation_model_applicable=True,
        status="OK",
    )


def bridge_developer_equity_nav(
    *,
    project_results: Sequence[DeveloperProjectNAVResult],
    unrestricted_cash: Any,
    non_project_asset_value: Any,
    corporate_interest_bearing_debt_not_in_projects: Any,
    corporate_liability_pv_not_in_projects: Any,
    explicit_equity_adjustment: Any = None,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> DeveloperEquityNAVResult:
    """Bridge unique attributable project NAVs to developer common equity.

    The ``*_not_in_projects`` liability fields are deliberate.  If project-level
    cash flows already include project debt service, remaining construction
    liabilities or taxes, those items must not be subtracted again here.

    ``non_project_asset_value`` is a separately verified market/economic value
    for assets outside project cash flows (for example a property-management
    stake or investment property).  Accounting carrying amount is not silently
    treated as market value.
    """

    cash = _finite(unrestricted_cash)
    other_assets = _finite(non_project_asset_value)
    debt = _finite(corporate_interest_bearing_debt_not_in_projects)
    liabilities = _finite(corporate_liability_pv_not_in_projects)
    adjustment = _finite(explicit_equity_adjustment)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    ids = [result.project_id for result in project_results]
    unique_count = len(set(ids))

    if not project_results:
        status = "PROJECT_NAV_UNAVAILABLE"
    elif len(ids) != unique_count:
        status = "DUPLICATE_PROJECT_ID"
    elif any(not result.valuation_model_applicable or result.attributable_project_nav is None for result in project_results):
        status = "PROJECT_NAV_INCOMPLETE"
    elif cash is None or cash < 0:
        status = "UNRESTRICTED_CASH_UNAVAILABLE"
    elif other_assets is None or other_assets < 0:
        status = "NON_PROJECT_ASSET_VALUE_UNAVAILABLE"
    elif debt is None or debt < 0:
        status = "CORPORATE_DEBT_UNAVAILABLE"
    elif liabilities is None or liabilities < 0:
        status = "CORPORATE_LIABILITY_PV_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return DeveloperEquityNAVResult(
            unique_project_count=unique_count,
            attributable_project_nav=None,
            unrestricted_cash=cash,
            non_project_asset_value=other_assets,
            corporate_interest_bearing_debt_not_in_projects=debt,
            corporate_liability_pv_not_in_projects=liabilities,
            explicit_equity_adjustment=adjustment,
            fair_equity_nav=None,
            current_market_cap=market_cap,
            total_common_shares=shares,
            fair_nav_per_share=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert cash is not None and other_assets is not None and debt is not None and liabilities is not None
    project_nav = sum(float(result.attributable_project_nav) for result in project_results)
    fair_nav = project_nav + cash + other_assets - debt - liabilities + (adjustment or 0.0)
    fair_per_share = fair_nav / shares if shares is not None and shares > 0 else None
    margin = fair_nav / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return DeveloperEquityNAVResult(
        unique_project_count=unique_count,
        attributable_project_nav=project_nav,
        unrestricted_cash=cash,
        non_project_asset_value=other_assets,
        corporate_interest_bearing_debt_not_in_projects=debt,
        corporate_liability_pv_not_in_projects=liabilities,
        explicit_equity_adjustment=adjustment,
        fair_equity_nav=fair_nav,
        current_market_cap=market_cap,
        total_common_shares=shares,
        fair_nav_per_share=fair_per_share,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_per_share is not None else "OK_PRICE_UNAVAILABLE",
    )


def reverse_implied_project_recovery(
    *,
    current_market_cap: Any,
    reference_attributable_project_nav: Any,
    non_project_net_asset_value: Any,
) -> tuple[Optional[float], str]:
    """Reverse-solve the project-NAV recovery ratio embedded in market cap.

    ``non_project_net_asset_value`` is the already-netted economic value of cash,
    non-project assets, corporate debt/liabilities and explicit adjustments.
    Negative implied recovery is deliberately preserved rather than floored.
    """

    market_cap = _finite(current_market_cap)
    project_nav = _finite(reference_attributable_project_nav)
    non_project_net = _finite(non_project_net_asset_value)
    if market_cap is None or market_cap < 0:
        return None, "MARKET_CAP_UNAVAILABLE"
    if project_nav is None or project_nav <= 0:
        return None, "REFERENCE_PROJECT_NAV_UNAVAILABLE"
    if non_project_net is None:
        return None, "NON_PROJECT_NET_ASSET_VALUE_UNAVAILABLE"
    return (market_cap - non_project_net) / project_nav, "OK"


def assess_developer_horizon_liquidity(
    *,
    unrestricted_cash: Any,
    expected_cash_collections_within_horizon: Any,
    debt_principal_due_within_horizon: Any,
    committed_land_and_construction_outflows_within_horizon: Any,
    other_committed_cash_outflows_within_horizon: Any,
) -> DeveloperLiquidityResult:
    """Compare horizon-matched developer liquidity sources and commitments.

    This deliberately avoids subtracting every long-term borrowing from current
    cash.  Conversely, contracted sales are not counted unless the caller
    supplies the expected *cash collections* within the same horizon.
    """

    cash = _finite(unrestricted_cash)
    collections = _finite(expected_cash_collections_within_horizon)
    debt_due = _finite(debt_principal_due_within_horizon)
    project_outflows = _finite(committed_land_and_construction_outflows_within_horizon)
    other_outflows = _finite(other_committed_cash_outflows_within_horizon)

    values = [cash, collections, debt_due, project_outflows, other_outflows]
    if any(value is None or value < 0 for value in values):
        return DeveloperLiquidityResult(
            unrestricted_cash=cash,
            expected_cash_collections_within_horizon=collections,
            debt_principal_due_within_horizon=debt_due,
            committed_land_and_construction_outflows_within_horizon=project_outflows,
            other_committed_cash_outflows_within_horizon=other_outflows,
            horizon_liquidity_surplus=None,
            coverage_of_committed_outflows=None,
            status="HORIZON_LIQUIDITY_INPUT_UNAVAILABLE",
        )

    sources = cash + collections
    committed = debt_due + project_outflows + other_outflows
    surplus = sources - committed
    coverage = None if committed == 0 else sources / committed
    return DeveloperLiquidityResult(
        unrestricted_cash=cash,
        expected_cash_collections_within_horizon=collections,
        debt_principal_due_within_horizon=debt_due,
        committed_land_and_construction_outflows_within_horizon=project_outflows,
        other_committed_cash_outflows_within_horizon=other_outflows,
        horizon_liquidity_surplus=surplus,
        coverage_of_committed_outflows=coverage,
        status="OK",
    )


def collect_developer_evidence(
    *,
    contracted_sales_growth: Any = None,
    contracted_sales_area_growth: Any = None,
    cash_collection_ratio: Any = None,
    recognized_revenue_growth: Any = None,
    recognized_gross_margin: Any = None,
    recognized_gross_margin_change: Any = None,
    inventory_book_value: Any = None,
    inventory_impairment_charge: Any = None,
    contract_liabilities: Any = None,
    new_land_equity_spend: Any = None,
    new_land_sale_value: Any = None,
    interest_bearing_debt: Any = None,
    near_term_debt: Any = None,
    average_financing_cost: Any = None,
) -> DeveloperEvidence:
    """Keep leading/lagging developer evidence explicit; no magic score."""

    values = {
        "contracted_sales_growth": _finite(contracted_sales_growth),
        "contracted_sales_area_growth": _finite(contracted_sales_area_growth),
        "cash_collection_ratio": _finite(cash_collection_ratio),
        "recognized_revenue_growth": _finite(recognized_revenue_growth),
        "recognized_gross_margin": _finite(recognized_gross_margin),
        "recognized_gross_margin_change": _finite(recognized_gross_margin_change),
        "inventory_book_value": _finite(inventory_book_value),
        "inventory_impairment_charge": _finite(inventory_impairment_charge),
        "contract_liabilities": _finite(contract_liabilities),
        "new_land_equity_spend": _finite(new_land_equity_spend),
        "new_land_sale_value": _finite(new_land_sale_value),
        "interest_bearing_debt": _finite(interest_bearing_debt),
        "near_term_debt": _finite(near_term_debt),
        "average_financing_cost": _finite(average_financing_cost),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return DeveloperEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
