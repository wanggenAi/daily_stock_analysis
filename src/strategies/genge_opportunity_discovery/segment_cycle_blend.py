"""Segment-aware cycle normalization for mixed business models.

A company can contain both highly cyclical and structurally steadier businesses.
Applying one company-level cycle haircut can therefore understate stable segments
or overstate peak-cycle segments. This module keeps every segment assumption
explicit and fails closed when a cyclical segment lacks a through-cycle input.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class SegmentCycleBlendResult:
    forward_profit: Optional[float]
    through_cycle_normalized_profit: Optional[float]
    cyclical_forward_profit: Optional[float]
    non_cyclical_forward_profit: Optional[float]
    cycle_exposure_ratio: Optional[float]
    peak_earnings_discount: Optional[float]
    status: str
    segments: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forward_profit": self.forward_profit,
            "through_cycle_normalized_profit": self.through_cycle_normalized_profit,
            "cyclical_forward_profit": self.cyclical_forward_profit,
            "non_cyclical_forward_profit": self.non_cyclical_forward_profit,
            "cycle_exposure_ratio": self.cycle_exposure_ratio,
            "peak_earnings_discount": self.peak_earnings_discount,
            "status": self.status,
            "segments": self.segments,
        }


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def blend_segment_cycle_earnings(
    segments: Mapping[str, Mapping[str, Any]],
) -> SegmentCycleBlendResult:
    """Aggregate explicit segment earnings without a company-wide cycle shortcut.

    Each segment may contain:
      - ``forward_profit`` (required for aggregation)
      - ``is_cyclical``
      - ``through_cycle_profit`` OR ``through_cycle_ratio`` for cyclical segments

    A non-cyclical segment defaults its through-cycle profit to forward profit.
    A cyclical segment never receives an invented haircut: if neither explicit
    normalized profit nor ratio is supplied, aggregate normalized profit is None.
    """

    if not segments:
        return SegmentCycleBlendResult(
            forward_profit=None,
            through_cycle_normalized_profit=None,
            cyclical_forward_profit=None,
            non_cyclical_forward_profit=None,
            cycle_exposure_ratio=None,
            peak_earnings_discount=None,
            status="SEGMENTS_UNAVAILABLE",
            segments={},
        )

    rows: Dict[str, Dict[str, Any]] = {}
    total_forward = 0.0
    total_normalized = 0.0
    cyclical_forward = 0.0
    non_cyclical_forward = 0.0
    incomplete = False

    for name, raw in segments.items():
        forward = _finite(raw.get("forward_profit"))
        is_cyclical = bool(raw.get("is_cyclical", False))
        explicit_normalized = _finite(raw.get("through_cycle_profit"))
        ratio = _finite(raw.get("through_cycle_ratio"))

        if forward is None:
            incomplete = True
            normalized = None
            method = "FORWARD_PROFIT_UNAVAILABLE"
        elif forward < 0:
            incomplete = True
            normalized = None
            method = "NEGATIVE_FORWARD_PROFIT_UNSUPPORTED"
        elif not is_cyclical:
            normalized = explicit_normalized if explicit_normalized is not None else forward
            method = "EXPLICIT_THROUGH_CYCLE_PROFIT" if explicit_normalized is not None else "NON_CYCLICAL_FORWARD_AS_NORMALIZED"
        elif explicit_normalized is not None:
            normalized = explicit_normalized
            method = "EXPLICIT_THROUGH_CYCLE_PROFIT"
        elif ratio is not None and 0 < ratio <= 1:
            normalized = forward * ratio
            method = "EXPLICIT_THROUGH_CYCLE_RATIO"
        else:
            incomplete = True
            normalized = None
            method = "CYCLE_NORMALIZATION_REQUIRED"

        if forward is not None and forward >= 0:
            total_forward += forward
            if is_cyclical:
                cyclical_forward += forward
            else:
                non_cyclical_forward += forward
        if normalized is not None:
            total_normalized += normalized

        rows[str(name)] = {
            "forward_profit": forward,
            "is_cyclical": is_cyclical,
            "through_cycle_profit": normalized,
            "through_cycle_ratio": ratio,
            "normalization_method": method,
        }

    if total_forward <= 0:
        exposure = None
        discount = None
    else:
        exposure = cyclical_forward / total_forward
        discount = None if incomplete else 1.0 - total_normalized / total_forward

    return SegmentCycleBlendResult(
        forward_profit=total_forward if total_forward > 0 else None,
        through_cycle_normalized_profit=None if incomplete else total_normalized,
        cyclical_forward_profit=cyclical_forward if total_forward > 0 else None,
        non_cyclical_forward_profit=non_cyclical_forward if total_forward > 0 else None,
        cycle_exposure_ratio=exposure,
        peak_earnings_discount=discount,
        status="SEGMENT_NORMALIZATION_INCOMPLETE" if incomplete else "OK",
        segments=rows,
    )
