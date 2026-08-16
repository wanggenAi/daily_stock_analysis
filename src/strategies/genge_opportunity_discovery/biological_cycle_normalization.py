"""Unit-economics normalization for livestock / biological cycles.

Livestock companies can report extremely low P/E near a price-cycle peak and
very high/negative P/E near the bottom.  Current accounting profit is therefore
not the right normalization anchor.

This module reconstructs biological-cycle operating contribution from explicit,
unit-consistent assumptions:

    normalized output units * (normalized unit price - normalized full unit cost)

The caller chooses the output unit (kg, head, bird, etc.) and must keep quantity,
price and cost consistent.  No spot price, historical mean price, feed-cost
assumption, mortality rate, sow capacity, output growth or target margin is
hard-coded.

Biological segments can then be aggregated with separately normalized feed,
slaughter, food-processing or other non-biological profit.  This module stops
at sustainable-profit normalization; the existing common valuation layer can
then decide whether a P/E, DCF or other explicit bridge is appropriate.

Nothing here creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional, Sequence


@dataclass(frozen=True)
class BiologicalSegmentResult:
    segment_id: str
    normalized_output_units: Optional[float]
    normalized_unit_price: Optional[float]
    normalized_full_unit_cost: Optional[float]
    normalized_unit_margin: Optional[float]
    normalized_operating_contribution: Optional[float]
    explicit_segment_profit_adjustment: Optional[float]
    normalized_segment_profit: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BiologicalCycleProfitResult:
    unique_segment_count: int
    normalized_biological_profit: Optional[float]
    normalized_non_biological_profit: Optional[float]
    explicit_corporate_adjustment: Optional[float]
    normalized_sustainable_profit: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BiologicalCycleEvidence:
    spot_sale_price: Optional[float]
    normalized_unit_price: Optional[float]
    full_unit_cost: Optional[float]
    unit_cost_change: Optional[float]
    output_growth: Optional[float]
    breeding_inventory: Optional[float]
    breeding_inventory_change: Optional[float]
    mortality_or_survival_change: Optional[float]
    feed_raw_material_cost_change: Optional[float]
    biological_asset_impairment: Optional[float]
    slaughter_or_processing_volume_growth: Optional[float]
    non_biological_profit_share: Optional[float]
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


def normalize_biological_segment(
    *,
    segment_id: str,
    normalized_output_units: Any,
    normalized_unit_price: Any,
    normalized_full_unit_cost: Any,
    explicit_segment_profit_adjustment: Any = None,
) -> BiologicalSegmentResult:
    """Normalize one species/product segment from explicit unit economics.

    Negative unit margins and negative normalized segment profit are preserved;
    they are economically meaningful at the bottom of a biological cycle and
    must not be floored to zero.
    """

    clean_id = str(segment_id or "").strip()
    output = _finite(normalized_output_units)
    price = _finite(normalized_unit_price)
    cost = _finite(normalized_full_unit_cost)
    adjustment = _finite(explicit_segment_profit_adjustment)

    if not clean_id:
        status = "SEGMENT_ID_UNAVAILABLE"
    elif output is None or output < 0:
        status = "NORMALIZED_OUTPUT_UNAVAILABLE"
    elif price is None or price < 0:
        status = "NORMALIZED_UNIT_PRICE_UNAVAILABLE"
    elif cost is None or cost < 0:
        status = "NORMALIZED_FULL_UNIT_COST_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return BiologicalSegmentResult(
            segment_id=clean_id,
            normalized_output_units=output,
            normalized_unit_price=price,
            normalized_full_unit_cost=cost,
            normalized_unit_margin=None,
            normalized_operating_contribution=None,
            explicit_segment_profit_adjustment=adjustment,
            normalized_segment_profit=None,
            status=status,
        )

    assert output is not None and price is not None and cost is not None
    unit_margin = price - cost
    contribution = output * unit_margin
    segment_profit = contribution + (adjustment or 0.0)
    return BiologicalSegmentResult(
        segment_id=clean_id,
        normalized_output_units=output,
        normalized_unit_price=price,
        normalized_full_unit_cost=cost,
        normalized_unit_margin=unit_margin,
        normalized_operating_contribution=contribution,
        explicit_segment_profit_adjustment=adjustment,
        normalized_segment_profit=segment_profit,
        status="OK",
    )


def aggregate_biological_cycle_profit(
    *,
    segment_results: Sequence[BiologicalSegmentResult],
    normalized_non_biological_profit: Any,
    explicit_corporate_adjustment: Any = None,
) -> BiologicalCycleProfitResult:
    """Aggregate unique biological segments plus separately normalized businesses.

    ``normalized_non_biological_profit`` is explicit because feed, slaughter,
    food processing or veterinary businesses should not inherit hog/chicken
    price-cycle assumptions merely because they are consolidated together.
    """

    non_bio = _finite(normalized_non_biological_profit)
    adjustment = _finite(explicit_corporate_adjustment)
    ids = [result.segment_id for result in segment_results]
    unique_count = len(set(ids))

    if not segment_results:
        status = "BIOLOGICAL_SEGMENTS_UNAVAILABLE"
    elif len(ids) != unique_count:
        status = "DUPLICATE_BIOLOGICAL_SEGMENT_ID"
    elif any(result.status != "OK" or result.normalized_segment_profit is None for result in segment_results):
        status = "BIOLOGICAL_SEGMENT_INCOMPLETE"
    elif non_bio is None:
        status = "NON_BIOLOGICAL_NORMALIZED_PROFIT_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return BiologicalCycleProfitResult(
            unique_segment_count=unique_count,
            normalized_biological_profit=None,
            normalized_non_biological_profit=non_bio,
            explicit_corporate_adjustment=adjustment,
            normalized_sustainable_profit=None,
            status=status,
        )

    biological_profit = sum(float(result.normalized_segment_profit) for result in segment_results)
    sustainable = biological_profit + non_bio + (adjustment or 0.0)
    return BiologicalCycleProfitResult(
        unique_segment_count=unique_count,
        normalized_biological_profit=biological_profit,
        normalized_non_biological_profit=non_bio,
        explicit_corporate_adjustment=adjustment,
        normalized_sustainable_profit=sustainable,
        status="OK",
    )


def reverse_implied_unit_margin(
    *,
    implied_total_normalized_profit: Any,
    normalized_non_biological_profit: Any,
    other_biological_segment_profit: Any,
    target_segment_output_units: Any,
    explicit_corporate_adjustment: Any = None,
) -> tuple[Optional[float], str]:
    """Reverse-solve target segment unit margin required by implied profit.

    This connects the biological normalization layer to the project's existing
    reverse-implied-profit framework.  For example, a market-cap/multiple bridge
    can first produce implied total normalized profit; this function then asks
    what hog/chicken unit margin that profit requires after explicitly removing
    other businesses.
    """

    total_profit = _finite(implied_total_normalized_profit)
    non_bio = _finite(normalized_non_biological_profit)
    other_bio = _finite(other_biological_segment_profit)
    output = _finite(target_segment_output_units)
    adjustment = _finite(explicit_corporate_adjustment)

    if total_profit is None:
        return None, "IMPLIED_TOTAL_PROFIT_UNAVAILABLE"
    if non_bio is None:
        return None, "NON_BIOLOGICAL_NORMALIZED_PROFIT_UNAVAILABLE"
    if other_bio is None:
        return None, "OTHER_BIOLOGICAL_PROFIT_UNAVAILABLE"
    if output is None or output <= 0:
        return None, "TARGET_SEGMENT_OUTPUT_UNAVAILABLE"

    target_profit = total_profit - non_bio - other_bio - (adjustment or 0.0)
    return target_profit / output, "OK"


def collect_biological_cycle_evidence(
    *,
    spot_sale_price: Any = None,
    normalized_unit_price: Any = None,
    full_unit_cost: Any = None,
    unit_cost_change: Any = None,
    output_growth: Any = None,
    breeding_inventory: Any = None,
    breeding_inventory_change: Any = None,
    mortality_or_survival_change: Any = None,
    feed_raw_material_cost_change: Any = None,
    biological_asset_impairment: Any = None,
    slaughter_or_processing_volume_growth: Any = None,
    non_biological_profit_share: Any = None,
) -> BiologicalCycleEvidence:
    """Carry biological-cycle leading/lagging evidence without a magic score."""

    values = {
        "spot_sale_price": _finite(spot_sale_price),
        "normalized_unit_price": _finite(normalized_unit_price),
        "full_unit_cost": _finite(full_unit_cost),
        "unit_cost_change": _finite(unit_cost_change),
        "output_growth": _finite(output_growth),
        "breeding_inventory": _finite(breeding_inventory),
        "breeding_inventory_change": _finite(breeding_inventory_change),
        "mortality_or_survival_change": _finite(mortality_or_survival_change),
        "feed_raw_material_cost_change": _finite(feed_raw_material_cost_change),
        "biological_asset_impairment": _finite(biological_asset_impairment),
        "slaughter_or_processing_volume_growth": _finite(slaughter_or_processing_volume_growth),
        "non_biological_profit_share": _finite(non_biological_profit_share),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return BiologicalCycleEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )
