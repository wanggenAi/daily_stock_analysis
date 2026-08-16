"""Product/mix normalization primitives for OEM and other product-cycle businesses.

This module is intentionally broader than the auto industry.  It is useful when
company economics depend on an explicitly changing product mix (for example
BEV/PHEV/ICE, domestic/overseas models, premium/mass-market products) and current
consolidated profit can move differently from unit volume.

The core unit-economics bridge is::

    normalized product profit
        = normalized units
          * (normalized net revenue per unit - normalized full operating cost per unit)
          + explicit segment adjustment

All quantities, prices and costs are caller supplied.  The adapter contains no
vehicle ASP, incentive, warranty, FX, utilization, product-mix or target-margin
defaults.  Negative unit margins are preserved.

Each segment carries an ``economic_scope_id``.  Aggregation rejects duplicated
scope IDs to catch obvious double counting, such as separately capitalizing an
internally supplied battery margin and a vehicle margin that already includes
that battery economics.  The research layer is still responsible for defining
non-overlapping scopes when public disclosure is incomplete.

Nothing here creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional, Sequence


@dataclass(frozen=True)
class ProductCycleSegmentResult:
    segment_id: str
    economic_scope_id: str
    normalized_units: Optional[float]
    normalized_net_revenue_per_unit: Optional[float]
    normalized_full_operating_cost_per_unit: Optional[float]
    normalized_unit_operating_margin: Optional[float]
    normalized_operating_contribution: Optional[float]
    explicit_segment_profit_adjustment: Optional[float]
    normalized_segment_profit: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ProductCycleProfitResult:
    unique_scope_count: int
    normalized_product_profit: Optional[float]
    normalized_non_product_profit: Optional[float]
    normalized_equity_method_income: Optional[float]
    explicit_corporate_adjustment: Optional[float]
    normalized_sustainable_profit: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ProductCycleEvidence:
    total_unit_sales_growth: Optional[float]
    primary_product_mix_share: Optional[float]
    secondary_product_mix_share: Optional[float]
    overseas_unit_share: Optional[float]
    average_net_revenue_per_unit_change: Optional[float]
    incentive_or_rebate_per_unit_change: Optional[float]
    gross_margin: Optional[float]
    gross_margin_change: Optional[float]
    capacity_utilization: Optional[float]
    inventory_days_change: Optional[float]
    warranty_cost_ratio: Optional[float]
    research_and_development_intensity: Optional[float]
    capital_expenditure: Optional[float]
    equity_method_income_share: Optional[float]
    fx_profit_or_loss: Optional[float]
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


def normalize_product_cycle_segment(
    *,
    segment_id: str,
    economic_scope_id: str,
    normalized_units: Any,
    normalized_net_revenue_per_unit: Any,
    normalized_full_operating_cost_per_unit: Any,
    explicit_segment_profit_adjustment: Any = None,
) -> ProductCycleSegmentResult:
    """Normalize one non-overlapping product scope from explicit unit economics."""

    clean_segment = str(segment_id or "").strip()
    clean_scope = str(economic_scope_id or "").strip()
    units = _finite(normalized_units)
    revenue_per_unit = _finite(normalized_net_revenue_per_unit)
    cost_per_unit = _finite(normalized_full_operating_cost_per_unit)
    adjustment = _finite(explicit_segment_profit_adjustment)

    if not clean_segment:
        status = "SEGMENT_ID_UNAVAILABLE"
    elif not clean_scope:
        status = "ECONOMIC_SCOPE_ID_UNAVAILABLE"
    elif units is None or units < 0:
        status = "NORMALIZED_UNITS_UNAVAILABLE"
    elif revenue_per_unit is None or revenue_per_unit < 0:
        status = "NORMALIZED_NET_REVENUE_PER_UNIT_UNAVAILABLE"
    elif cost_per_unit is None or cost_per_unit < 0:
        status = "NORMALIZED_FULL_OPERATING_COST_PER_UNIT_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return ProductCycleSegmentResult(
            segment_id=clean_segment,
            economic_scope_id=clean_scope,
            normalized_units=units,
            normalized_net_revenue_per_unit=revenue_per_unit,
            normalized_full_operating_cost_per_unit=cost_per_unit,
            normalized_unit_operating_margin=None,
            normalized_operating_contribution=None,
            explicit_segment_profit_adjustment=adjustment,
            normalized_segment_profit=None,
            status=status,
        )

    assert units is not None and revenue_per_unit is not None and cost_per_unit is not None
    unit_margin = revenue_per_unit - cost_per_unit
    contribution = units * unit_margin
    segment_profit = contribution + (adjustment or 0.0)
    return ProductCycleSegmentResult(
        segment_id=clean_segment,
        economic_scope_id=clean_scope,
        normalized_units=units,
        normalized_net_revenue_per_unit=revenue_per_unit,
        normalized_full_operating_cost_per_unit=cost_per_unit,
        normalized_unit_operating_margin=unit_margin,
        normalized_operating_contribution=contribution,
        explicit_segment_profit_adjustment=adjustment,
        normalized_segment_profit=segment_profit,
        status="OK",
    )


def aggregate_product_cycle_profit(
    *,
    segment_results: Sequence[ProductCycleSegmentResult],
    normalized_non_product_profit: Any,
    normalized_equity_method_income: Any,
    explicit_corporate_adjustment: Any = None,
) -> ProductCycleProfitResult:
    """Aggregate product scopes plus separately normalized non-product economics.

    ``normalized_equity_method_income`` is explicit because incumbent OEMs may
    derive material profit from joint ventures.  It must not be hidden in a
    vehicle unit-margin assumption and then added again at group level.
    """

    non_product = _finite(normalized_non_product_profit)
    equity_income = _finite(normalized_equity_method_income)
    adjustment = _finite(explicit_corporate_adjustment)
    scope_ids = [result.economic_scope_id for result in segment_results]
    unique_scope_count = len(set(scope_ids))

    if not segment_results:
        status = "PRODUCT_SEGMENTS_UNAVAILABLE"
    elif len(scope_ids) != unique_scope_count:
        status = "DUPLICATE_ECONOMIC_SCOPE_ID"
    elif any(result.status != "OK" or result.normalized_segment_profit is None for result in segment_results):
        status = "PRODUCT_SEGMENT_INCOMPLETE"
    elif non_product is None:
        status = "NON_PRODUCT_NORMALIZED_PROFIT_UNAVAILABLE"
    elif equity_income is None:
        status = "EQUITY_METHOD_INCOME_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return ProductCycleProfitResult(
            unique_scope_count=unique_scope_count,
            normalized_product_profit=None,
            normalized_non_product_profit=non_product,
            normalized_equity_method_income=equity_income,
            explicit_corporate_adjustment=adjustment,
            normalized_sustainable_profit=None,
            status=status,
        )

    product_profit = sum(float(result.normalized_segment_profit) for result in segment_results)
    sustainable = product_profit + non_product + equity_income + (adjustment or 0.0)
    return ProductCycleProfitResult(
        unique_scope_count=unique_scope_count,
        normalized_product_profit=product_profit,
        normalized_non_product_profit=non_product,
        normalized_equity_method_income=equity_income,
        explicit_corporate_adjustment=adjustment,
        normalized_sustainable_profit=sustainable,
        status="OK",
    )


def reverse_implied_product_unit_margin(
    *,
    implied_total_normalized_profit: Any,
    normalized_non_product_profit: Any,
    normalized_equity_method_income: Any,
    other_product_scope_profit: Any,
    target_scope_units: Any,
    explicit_corporate_adjustment: Any = None,
) -> tuple[Optional[float], str]:
    """Reverse-solve the target product unit margin required by market-implied profit."""

    total = _finite(implied_total_normalized_profit)
    non_product = _finite(normalized_non_product_profit)
    equity_income = _finite(normalized_equity_method_income)
    other_products = _finite(other_product_scope_profit)
    units = _finite(target_scope_units)
    adjustment = _finite(explicit_corporate_adjustment)

    if total is None:
        return None, "IMPLIED_TOTAL_PROFIT_UNAVAILABLE"
    if non_product is None:
        return None, "NON_PRODUCT_NORMALIZED_PROFIT_UNAVAILABLE"
    if equity_income is None:
        return None, "EQUITY_METHOD_INCOME_UNAVAILABLE"
    if other_products is None:
        return None, "OTHER_PRODUCT_SCOPE_PROFIT_UNAVAILABLE"
    if units is None or units <= 0:
        return None, "TARGET_SCOPE_UNITS_UNAVAILABLE"

    target_profit = total - non_product - equity_income - other_products - (adjustment or 0.0)
    return target_profit / units, "OK"


def collect_product_cycle_evidence(
    *,
    total_unit_sales_growth: Any = None,
    primary_product_mix_share: Any = None,
    secondary_product_mix_share: Any = None,
    overseas_unit_share: Any = None,
    average_net_revenue_per_unit_change: Any = None,
    incentive_or_rebate_per_unit_change: Any = None,
    gross_margin: Any = None,
    gross_margin_change: Any = None,
    capacity_utilization: Any = None,
    inventory_days_change: Any = None,
    warranty_cost_ratio: Any = None,
    research_and_development_intensity: Any = None,
    capital_expenditure: Any = None,
    equity_method_income_share: Any = None,
    fx_profit_or_loss: Any = None,
) -> ProductCycleEvidence:
    values = {
        "total_unit_sales_growth": _finite(total_unit_sales_growth),
        "primary_product_mix_share": _finite(primary_product_mix_share),
        "secondary_product_mix_share": _finite(secondary_product_mix_share),
        "overseas_unit_share": _finite(overseas_unit_share),
        "average_net_revenue_per_unit_change": _finite(average_net_revenue_per_unit_change),
        "incentive_or_rebate_per_unit_change": _finite(incentive_or_rebate_per_unit_change),
        "gross_margin": _finite(gross_margin),
        "gross_margin_change": _finite(gross_margin_change),
        "capacity_utilization": _finite(capacity_utilization),
        "inventory_days_change": _finite(inventory_days_change),
        "warranty_cost_ratio": _finite(warranty_cost_ratio),
        "research_and_development_intensity": _finite(research_and_development_intensity),
        "capital_expenditure": _finite(capital_expenditure),
        "equity_method_income_share": _finite(equity_method_income_share),
        "fx_profit_or_loss": _finite(fx_profit_or_loss),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return ProductCycleEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
