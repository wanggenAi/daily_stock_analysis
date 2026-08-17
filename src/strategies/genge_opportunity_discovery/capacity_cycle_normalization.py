"""Reusable capacity-cycle normalization for batteries, solar, chemicals, etc.

Capacity-driven manufacturing can report explosive profit at high utilization /
favorable spreads and collapse when price falls below variable/full cost.  This
module normalizes the economics before valuation rather than capitalizing the
latest accounting profit.

Two explicit input modes are supported:

1. unit economics::

       normalized contribution
           = normalized sales units
             * (normalized realized unit price - normalized variable unit cost)
             - normalized fixed operating cost
             + explicit segment adjustment

2. revenue/margin economics when physical unit data are unavailable::

       normalized segment profit
           = normalized revenue
             * normalized operating margin
             + explicit segment adjustment

The second path is not a shortcut to infer margin from current results: both
normalized revenue and normalized operating margin must still be explicitly
supplied.  It simply allows point-in-time research to fail less often when GWh,
tonnes or other physical-unit disclosures are not available.

Effective capacity and utilization are diagnostics.  They never automatically
set normalized volume or margin.  No commodity price, utilization target,
capacity-growth rate, fixed-cost absorption rule or target multiple is hardcoded.

Nothing here creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional, Sequence


@dataclass(frozen=True)
class CapacityCycleSegmentResult:
    segment_id: str
    economic_scope_id: str
    normalization_mode: str
    normalized_sales_units: Optional[float]
    normalized_realized_unit_price: Optional[float]
    normalized_variable_unit_cost: Optional[float]
    normalized_fixed_operating_cost: Optional[float]
    normalized_revenue: Optional[float]
    normalized_operating_margin: Optional[float]
    normalized_segment_profit: Optional[float]
    effective_capacity_units: Optional[float]
    normalized_capacity_utilization: Optional[float]
    explicit_segment_profit_adjustment: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CapacityCycleProfitResult:
    unique_scope_count: int
    normalized_capacity_cycle_profit: Optional[float]
    normalized_non_cycle_profit: Optional[float]
    explicit_corporate_adjustment: Optional[float]
    normalized_sustainable_profit: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CapacityCycleEvidence:
    current_sales_units: Optional[float]
    current_effective_capacity_units: Optional[float]
    current_capacity_utilization: Optional[float]
    realized_unit_price_change: Optional[float]
    variable_unit_cost_change: Optional[float]
    gross_margin: Optional[float]
    gross_margin_change: Optional[float]
    inventory_value: Optional[float]
    inventory_growth: Optional[float]
    capital_expenditure: Optional[float]
    construction_in_progress: Optional[float]
    planned_capacity_additions: Optional[float]
    market_share: Optional[float]
    market_share_change: Optional[float]
    operating_cash_flow_growth: Optional[float]
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


def _utilization(*, sales_units: Optional[float], capacity_units: Optional[float]) -> Optional[float]:
    if sales_units is None or capacity_units is None or capacity_units <= 0:
        return None
    return sales_units / capacity_units


def normalize_capacity_cycle_unit_segment(
    *,
    segment_id: str,
    economic_scope_id: str,
    normalized_sales_units: Any,
    normalized_realized_unit_price: Any,
    normalized_variable_unit_cost: Any,
    normalized_fixed_operating_cost: Any,
    effective_capacity_units: Any = None,
    explicit_segment_profit_adjustment: Any = None,
) -> CapacityCycleSegmentResult:
    """Normalize one capacity-cycle segment from physical unit economics."""

    segment = str(segment_id or "").strip()
    scope = str(economic_scope_id or "").strip()
    units = _finite(normalized_sales_units)
    price = _finite(normalized_realized_unit_price)
    variable_cost = _finite(normalized_variable_unit_cost)
    fixed_cost = _finite(normalized_fixed_operating_cost)
    capacity = _finite(effective_capacity_units)
    adjustment = _finite(explicit_segment_profit_adjustment)

    if not segment:
        status = "SEGMENT_ID_UNAVAILABLE"
    elif not scope:
        status = "ECONOMIC_SCOPE_ID_UNAVAILABLE"
    elif units is None or units < 0:
        status = "NORMALIZED_SALES_UNITS_UNAVAILABLE"
    elif price is None or price < 0:
        status = "NORMALIZED_UNIT_PRICE_UNAVAILABLE"
    elif variable_cost is None or variable_cost < 0:
        status = "NORMALIZED_VARIABLE_UNIT_COST_UNAVAILABLE"
    elif fixed_cost is None or fixed_cost < 0:
        status = "NORMALIZED_FIXED_OPERATING_COST_UNAVAILABLE"
    elif capacity is not None and capacity <= 0:
        status = "INVALID_EFFECTIVE_CAPACITY"
    else:
        status = "OK"

    utilization = _utilization(sales_units=units, capacity_units=capacity)
    if status != "OK":
        return CapacityCycleSegmentResult(
            segment_id=segment,
            economic_scope_id=scope,
            normalization_mode="UNIT_ECONOMICS",
            normalized_sales_units=units,
            normalized_realized_unit_price=price,
            normalized_variable_unit_cost=variable_cost,
            normalized_fixed_operating_cost=fixed_cost,
            normalized_revenue=None,
            normalized_operating_margin=None,
            normalized_segment_profit=None,
            effective_capacity_units=capacity,
            normalized_capacity_utilization=utilization,
            explicit_segment_profit_adjustment=adjustment,
            status=status,
        )

    assert units is not None and price is not None and variable_cost is not None and fixed_cost is not None
    profit = units * (price - variable_cost) - fixed_cost + (adjustment or 0.0)
    revenue = units * price
    operating_margin = None if revenue == 0 else profit / revenue
    return CapacityCycleSegmentResult(
        segment_id=segment,
        economic_scope_id=scope,
        normalization_mode="UNIT_ECONOMICS",
        normalized_sales_units=units,
        normalized_realized_unit_price=price,
        normalized_variable_unit_cost=variable_cost,
        normalized_fixed_operating_cost=fixed_cost,
        normalized_revenue=revenue,
        normalized_operating_margin=operating_margin,
        normalized_segment_profit=profit,
        effective_capacity_units=capacity,
        normalized_capacity_utilization=utilization,
        explicit_segment_profit_adjustment=adjustment,
        status="OK",
    )


def normalize_capacity_cycle_revenue_margin_segment(
    *,
    segment_id: str,
    economic_scope_id: str,
    normalized_revenue: Any,
    normalized_operating_margin: Any,
    explicit_segment_profit_adjustment: Any = None,
) -> CapacityCycleSegmentResult:
    """Normalize a capacity-cycle segment when physical-unit data are unavailable.

    ``normalized_operating_margin`` may be negative.  It is an explicit
    through-cycle/scenario input and is not inferred from current gross margin.
    """

    segment = str(segment_id or "").strip()
    scope = str(economic_scope_id or "").strip()
    revenue = _finite(normalized_revenue)
    margin = _finite(normalized_operating_margin)
    adjustment = _finite(explicit_segment_profit_adjustment)

    if not segment:
        status = "SEGMENT_ID_UNAVAILABLE"
    elif not scope:
        status = "ECONOMIC_SCOPE_ID_UNAVAILABLE"
    elif revenue is None or revenue < 0:
        status = "NORMALIZED_REVENUE_UNAVAILABLE"
    elif margin is None:
        status = "NORMALIZED_OPERATING_MARGIN_UNAVAILABLE"
    else:
        status = "OK"

    profit = None if status != "OK" else revenue * margin + (adjustment or 0.0)
    return CapacityCycleSegmentResult(
        segment_id=segment,
        economic_scope_id=scope,
        normalization_mode="REVENUE_MARGIN",
        normalized_sales_units=None,
        normalized_realized_unit_price=None,
        normalized_variable_unit_cost=None,
        normalized_fixed_operating_cost=None,
        normalized_revenue=revenue,
        normalized_operating_margin=margin,
        normalized_segment_profit=profit,
        effective_capacity_units=None,
        normalized_capacity_utilization=None,
        explicit_segment_profit_adjustment=adjustment,
        status=status,
    )


def aggregate_capacity_cycle_profit(
    *,
    segment_results: Sequence[CapacityCycleSegmentResult],
    normalized_non_cycle_profit: Any,
    explicit_corporate_adjustment: Any = None,
) -> CapacityCycleProfitResult:
    """Aggregate non-overlapping capacity-cycle scopes and other profit."""

    non_cycle = _finite(normalized_non_cycle_profit)
    adjustment = _finite(explicit_corporate_adjustment)
    scope_ids = [result.economic_scope_id for result in segment_results]
    unique_scope_count = len(set(scope_ids))

    if not segment_results:
        status = "CAPACITY_CYCLE_SEGMENTS_UNAVAILABLE"
    elif len(scope_ids) != unique_scope_count:
        status = "DUPLICATE_ECONOMIC_SCOPE_ID"
    elif any(result.status != "OK" or result.normalized_segment_profit is None for result in segment_results):
        status = "CAPACITY_CYCLE_SEGMENT_INCOMPLETE"
    elif non_cycle is None:
        status = "NON_CYCLE_NORMALIZED_PROFIT_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return CapacityCycleProfitResult(
            unique_scope_count=unique_scope_count,
            normalized_capacity_cycle_profit=None,
            normalized_non_cycle_profit=non_cycle,
            explicit_corporate_adjustment=adjustment,
            normalized_sustainable_profit=None,
            status=status,
        )

    cycle_profit = sum(float(result.normalized_segment_profit) for result in segment_results)
    sustainable = cycle_profit + non_cycle + (adjustment or 0.0)
    return CapacityCycleProfitResult(
        unique_scope_count=unique_scope_count,
        normalized_capacity_cycle_profit=cycle_profit,
        normalized_non_cycle_profit=non_cycle,
        explicit_corporate_adjustment=adjustment,
        normalized_sustainable_profit=sustainable,
        status="OK",
    )


def reverse_implied_capacity_unit_margin(
    *,
    implied_total_normalized_profit: Any,
    normalized_non_cycle_profit: Any,
    other_cycle_scope_profit: Any,
    target_scope_sales_units: Any,
    target_scope_fixed_operating_cost: Any,
    explicit_corporate_adjustment: Any = None,
) -> tuple[Optional[float], str]:
    """Reverse-solve unit contribution margin required by implied total profit."""

    total = _finite(implied_total_normalized_profit)
    non_cycle = _finite(normalized_non_cycle_profit)
    other_cycle = _finite(other_cycle_scope_profit)
    units = _finite(target_scope_sales_units)
    fixed_cost = _finite(target_scope_fixed_operating_cost)
    adjustment = _finite(explicit_corporate_adjustment)

    if total is None:
        return None, "IMPLIED_TOTAL_PROFIT_UNAVAILABLE"
    if non_cycle is None:
        return None, "NON_CYCLE_NORMALIZED_PROFIT_UNAVAILABLE"
    if other_cycle is None:
        return None, "OTHER_CYCLE_SCOPE_PROFIT_UNAVAILABLE"
    if units is None or units <= 0:
        return None, "TARGET_SCOPE_SALES_UNITS_UNAVAILABLE"
    if fixed_cost is None or fixed_cost < 0:
        return None, "TARGET_SCOPE_FIXED_COST_UNAVAILABLE"

    target_profit_after_adjustment = total - non_cycle - other_cycle - (adjustment or 0.0)
    return (target_profit_after_adjustment + fixed_cost) / units, "OK"


def collect_capacity_cycle_evidence(
    *,
    current_sales_units: Any = None,
    current_effective_capacity_units: Any = None,
    current_capacity_utilization: Any = None,
    realized_unit_price_change: Any = None,
    variable_unit_cost_change: Any = None,
    gross_margin: Any = None,
    gross_margin_change: Any = None,
    inventory_value: Any = None,
    inventory_growth: Any = None,
    capital_expenditure: Any = None,
    construction_in_progress: Any = None,
    planned_capacity_additions: Any = None,
    market_share: Any = None,
    market_share_change: Any = None,
    operating_cash_flow_growth: Any = None,
) -> CapacityCycleEvidence:
    values = {
        "current_sales_units": _finite(current_sales_units),
        "current_effective_capacity_units": _finite(current_effective_capacity_units),
        "current_capacity_utilization": _finite(current_capacity_utilization),
        "realized_unit_price_change": _finite(realized_unit_price_change),
        "variable_unit_cost_change": _finite(variable_unit_cost_change),
        "gross_margin": _finite(gross_margin),
        "gross_margin_change": _finite(gross_margin_change),
        "inventory_value": _finite(inventory_value),
        "inventory_growth": _finite(inventory_growth),
        "capital_expenditure": _finite(capital_expenditure),
        "construction_in_progress": _finite(construction_in_progress),
        "planned_capacity_additions": _finite(planned_capacity_additions),
        "market_share": _finite(market_share),
        "market_share_change": _finite(market_share_change),
        "operating_cash_flow_growth": _finite(operating_cash_flow_growth),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return CapacityCycleEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
