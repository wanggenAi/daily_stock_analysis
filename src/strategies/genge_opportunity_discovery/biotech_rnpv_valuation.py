"""Probability-adjusted biotech rNPV and cash-runway primitives.

Pre-profit / pipeline-driven biotech companies are deliberately routed away
from generic P/E valuation.  A shrinking accounting loss, or even one quarter
of headline profitability, does not make a P/E model economically applicable
when normalized recurring earnings remain negative and value is concentrated in
approved products plus clinical/regulatory pipeline assets.

This module implements only auditable primitives:

* explicit P/E applicability refusal;
* probability-adjusted asset cash-flow present value;
* separate treatment of success-contingent commercial cash flows and explicitly
  supplied development / committed cash flows;
* cash-runway analysis based on normalized annual burn, never Q1 extrapolation;
* catalyst-horizon / financing-risk comparison;
* an equity bridge that adds unique asset rNPVs to verified liquid resources
  and subtracts debt / corporate-overhead PV.

The engine intentionally contains **no default clinical-success probabilities,
no stage lookup table, no default discount rate, no default peak-sales multiple,
no default dilution rate and no default catalyst buffer**.  Those assumptions
must come from point-in-time evidence or explicit research scenarios.

Nothing here creates a Formal BUY or bypasses existing execution/risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class PEApplicabilityResult:
    normalized_sustainable_profit: Optional[float]
    pe_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BiotechAssetRNPVResult:
    asset_id: str
    probability_of_success: Optional[float]
    economic_ownership: Optional[float]
    required_return: Optional[float]
    pv_success_contingent_cash_flows: Optional[float]
    pv_explicit_development_cash_flows: Optional[float]
    probability_adjusted_commercial_value: Optional[float]
    risk_adjusted_asset_value: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CashRunwayResult:
    net_liquid_resources: Optional[float]
    normalized_annual_cash_burn: Optional[float]
    runway_years: Optional[float]
    runway_months: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class FinancingRiskResult:
    runway_years: Optional[float]
    catalyst_horizon_years: Optional[float]
    explicit_buffer_years: Optional[float]
    required_runway_years: Optional[float]
    financing_before_catalyst_likely: Optional[bool]
    runway_gap_years: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BiotechEquityValueResult:
    unique_asset_count: int
    total_asset_rnpv: Optional[float]
    liquid_resources: Optional[float]
    debt: Optional[float]
    corporate_overhead_pv: Optional[float]
    explicit_equity_adjustment: Optional[float]
    fair_equity_value: Optional[float]
    current_market_cap: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BiotechQualityEvidence:
    commercial_product_growth: Optional[float]
    commercial_gross_margin: Optional[float]
    normalized_recurring_profit: Optional[float]
    normalized_annual_cash_burn: Optional[float]
    research_and_development_intensity: Optional[float]
    approved_indication_count: Optional[float]
    late_stage_asset_count: Optional[float]
    accepted_nda_or_bla_count: Optional[float]
    partnership_or_royalty_share: Optional[float]
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


def _coerce_cash_flow_map(values: Mapping[Any, Any] | None) -> tuple[Optional[Dict[int, float]], str]:
    if values is None:
        return {}, "OK"
    result: Dict[int, float] = {}
    for raw_year, raw_value in values.items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            return None, "INVALID_CASH_FLOW_YEAR"
        value = _finite(raw_value)
        if year <= 0 or value is None:
            return None, "INVALID_CASH_FLOW"
        if year in result:
            return None, "DUPLICATE_CASH_FLOW_YEAR"
        result[year] = value
    return result, "OK"


def evaluate_pe_applicability(*, normalized_sustainable_profit: Any) -> PEApplicabilityResult:
    """Refuse P/E when normalized sustainable profit is absent or non-positive."""

    profit = _finite(normalized_sustainable_profit)
    if profit is None:
        return PEApplicabilityResult(
            normalized_sustainable_profit=None,
            pe_model_applicable=False,
            status="PE_MODEL_NOT_APPLICABLE_PROFIT_UNAVAILABLE",
        )
    if profit <= 0:
        return PEApplicabilityResult(
            normalized_sustainable_profit=profit,
            pe_model_applicable=False,
            status="PE_MODEL_NOT_APPLICABLE",
        )
    return PEApplicabilityResult(
        normalized_sustainable_profit=profit,
        pe_model_applicable=True,
        status="PE_MODEL_POTENTIALLY_APPLICABLE",
    )


def value_probability_adjusted_asset(
    *,
    asset_id: str,
    success_contingent_cash_flows: Mapping[Any, Any],
    explicit_development_cash_flows: Mapping[Any, Any] | None,
    probability_of_success: Any,
    economic_ownership: Any,
    required_return: Any,
) -> BiotechAssetRNPVResult:
    """Present-value one biotech asset with explicit probability and ownership.

    ``success_contingent_cash_flows`` should contain the future *unrisked* cash
    flows that would accrue if the asset/indication succeeds.  They are first
    discounted and then multiplied by the explicitly supplied probability of
    success and economic ownership.

    ``explicit_development_cash_flows`` are separately supplied expected/committed
    development cash flows and are **not** multiplied by success probability.
    This avoids the common mistake of multiplying already-expected R&D spending
    by the same terminal approval probability.  They may be negative or positive
    (for example, milestone receipts) and are still scaled by economic ownership.

    If a more detailed phase-by-phase probability tree is available, callers
    should prepare probability-weighted development cash flows upstream rather
    than expecting this primitive to invent stage-transition probabilities.
    """

    clean_id = str(asset_id or "").strip()
    probability = _finite(probability_of_success)
    ownership = _finite(economic_ownership)
    required = _finite(required_return)
    success_flows, success_status = _coerce_cash_flow_map(success_contingent_cash_flows)
    development_flows, development_status = _coerce_cash_flow_map(explicit_development_cash_flows)

    common = dict(
        asset_id=clean_id,
        probability_of_success=probability,
        economic_ownership=ownership,
        required_return=required,
    )

    if not clean_id:
        status = "ASSET_ID_UNAVAILABLE"
    elif probability is None or not 0.0 <= probability <= 1.0:
        status = "INVALID_OR_MISSING_SUCCESS_PROBABILITY"
    elif ownership is None or not 0.0 <= ownership <= 1.0:
        status = "INVALID_OR_MISSING_ECONOMIC_OWNERSHIP"
    elif required is None or required <= -1.0:
        status = "INVALID_OR_MISSING_REQUIRED_RETURN"
    elif success_status != "OK":
        status = success_status
    elif development_status != "OK":
        status = development_status
    elif not success_flows:
        status = "SUCCESS_CONTINGENT_CASH_FLOWS_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return BiotechAssetRNPVResult(
            **common,
            pv_success_contingent_cash_flows=None,
            pv_explicit_development_cash_flows=None,
            probability_adjusted_commercial_value=None,
            risk_adjusted_asset_value=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert probability is not None and ownership is not None and required is not None
    assert success_flows is not None and development_flows is not None

    pv_success = sum(value / ((1.0 + required) ** year) for year, value in success_flows.items())
    pv_development = sum(value / ((1.0 + required) ** year) for year, value in development_flows.items())
    probability_adjusted_commercial_value = pv_success * probability * ownership
    development_value = pv_development * ownership
    asset_value = probability_adjusted_commercial_value + development_value

    return BiotechAssetRNPVResult(
        **common,
        pv_success_contingent_cash_flows=pv_success,
        pv_explicit_development_cash_flows=pv_development,
        probability_adjusted_commercial_value=probability_adjusted_commercial_value,
        risk_adjusted_asset_value=asset_value,
        valuation_model_applicable=True,
        status="OK",
    )


def compute_cash_runway(
    *,
    liquid_resources: Any,
    debt_or_restricted_resources: Any,
    normalized_annual_cash_burn: Any,
) -> CashRunwayResult:
    """Compute runway from normalized annual burn; never infer infinity from Q1."""

    liquid = _finite(liquid_resources)
    debt = _finite(debt_or_restricted_resources)
    burn = _finite(normalized_annual_cash_burn)

    if liquid is None or liquid < 0:
        return CashRunwayResult(None, burn, None, None, "LIQUID_RESOURCES_UNAVAILABLE")
    if debt is None or debt < 0:
        return CashRunwayResult(None, burn, None, None, "DEBT_OR_RESTRICTED_RESOURCES_UNAVAILABLE")

    net_liquid = liquid - debt
    if net_liquid <= 0:
        return CashRunwayResult(net_liquid, burn, 0.0, 0.0, "NO_POSITIVE_NET_LIQUID_RESOURCES")
    if burn is None or burn <= 0:
        return CashRunwayResult(
            net_liquid,
            burn,
            None,
            None,
            "NORMALIZED_ANNUAL_BURN_NOT_POSITIVE_OR_UNAVAILABLE",
        )

    runway_years = net_liquid / burn
    return CashRunwayResult(
        net_liquid_resources=net_liquid,
        normalized_annual_cash_burn=burn,
        runway_years=runway_years,
        runway_months=runway_years * 12.0,
        status="OK",
    )


def assess_financing_before_catalyst(
    *,
    runway_years: Any,
    catalyst_horizon_years: Any,
    explicit_buffer_years: Any,
) -> FinancingRiskResult:
    """Compare runway with an explicit catalyst horizon and liquidity buffer."""

    runway = _finite(runway_years)
    catalyst = _finite(catalyst_horizon_years)
    buffer_years = _finite(explicit_buffer_years)

    if runway is None or runway < 0:
        status = "RUNWAY_UNAVAILABLE"
    elif catalyst is None or catalyst < 0:
        status = "CATALYST_HORIZON_UNAVAILABLE"
    elif buffer_years is None or buffer_years < 0:
        status = "EXPLICIT_BUFFER_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return FinancingRiskResult(
            runway_years=runway,
            catalyst_horizon_years=catalyst,
            explicit_buffer_years=buffer_years,
            required_runway_years=None,
            financing_before_catalyst_likely=None,
            runway_gap_years=None,
            status=status,
        )

    assert runway is not None and catalyst is not None and buffer_years is not None
    required_runway = catalyst + buffer_years
    gap = runway - required_runway
    return FinancingRiskResult(
        runway_years=runway,
        catalyst_horizon_years=catalyst,
        explicit_buffer_years=buffer_years,
        required_runway_years=required_runway,
        financing_before_catalyst_likely=gap < 0,
        runway_gap_years=gap,
        status="OK",
    )


def bridge_biotech_equity_value(
    *,
    asset_results: Sequence[BiotechAssetRNPVResult],
    liquid_resources: Any,
    debt: Any,
    corporate_overhead_pv: Any,
    explicit_equity_adjustment: Any = None,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> BiotechEquityValueResult:
    """Bridge unique asset rNPVs and verified balance-sheet resources to equity.

    ``corporate_overhead_pv`` should be a non-negative present value of future
    corporate costs that are not already included in asset-level cash flows.
    It is subtracted exactly once.

    Duplicate ``asset_id`` values are rejected to catch obvious double counting.
    Different indications of one molecule may legitimately be separate assets,
    but their scopes must be explicitly non-overlapping upstream; this generic
    layer cannot infer biological/commercial overlap from names alone.
    """

    liquid = _finite(liquid_resources)
    debt_value = _finite(debt)
    overhead = _finite(corporate_overhead_pv)
    adjustment = _finite(explicit_equity_adjustment)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    ids = [result.asset_id for result in asset_results]
    unique_count = len(set(ids))
    if len(ids) != unique_count:
        status = "DUPLICATE_ASSET_ID"
    elif any(not result.valuation_model_applicable or result.risk_adjusted_asset_value is None for result in asset_results):
        status = "ASSET_VALUATION_INCOMPLETE"
    elif liquid is None or liquid < 0:
        status = "LIQUID_RESOURCES_UNAVAILABLE"
    elif debt_value is None or debt_value < 0:
        status = "DEBT_UNAVAILABLE"
    elif overhead is None or overhead < 0:
        status = "CORPORATE_OVERHEAD_PV_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return BiotechEquityValueResult(
            unique_asset_count=unique_count,
            total_asset_rnpv=None,
            liquid_resources=liquid,
            debt=debt_value,
            corporate_overhead_pv=overhead,
            explicit_equity_adjustment=adjustment,
            fair_equity_value=None,
            current_market_cap=market_cap,
            total_common_shares=shares,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    total_assets = sum(float(result.risk_adjusted_asset_value) for result in asset_results)
    fair_equity = total_assets + liquid - debt_value - overhead + (adjustment or 0.0)
    fair_price = fair_equity / shares if shares is not None and shares > 0 else None
    margin = fair_equity / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return BiotechEquityValueResult(
        unique_asset_count=unique_count,
        total_asset_rnpv=total_assets,
        liquid_resources=liquid,
        debt=debt_value,
        corporate_overhead_pv=overhead,
        explicit_equity_adjustment=adjustment,
        fair_equity_value=fair_equity,
        current_market_cap=market_cap,
        total_common_shares=shares,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def collect_biotech_quality_evidence(
    *,
    commercial_product_growth: Any = None,
    commercial_gross_margin: Any = None,
    normalized_recurring_profit: Any = None,
    normalized_annual_cash_burn: Any = None,
    research_and_development_intensity: Any = None,
    approved_indication_count: Any = None,
    late_stage_asset_count: Any = None,
    accepted_nda_or_bla_count: Any = None,
    partnership_or_royalty_share: Any = None,
) -> BiotechQualityEvidence:
    values = {
        "commercial_product_growth": _finite(commercial_product_growth),
        "commercial_gross_margin": _finite(commercial_gross_margin),
        "normalized_recurring_profit": _finite(normalized_recurring_profit),
        "normalized_annual_cash_burn": _finite(normalized_annual_cash_burn),
        "research_and_development_intensity": _finite(research_and_development_intensity),
        "approved_indication_count": _finite(approved_indication_count),
        "late_stage_asset_count": _finite(late_stage_asset_count),
        "accepted_nda_or_bla_count": _finite(accepted_nda_or_bla_count),
        "partnership_or_royalty_share": _finite(partnership_or_royalty_share),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return BiotechQualityEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
