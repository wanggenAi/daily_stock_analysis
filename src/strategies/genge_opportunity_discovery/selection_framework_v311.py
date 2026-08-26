"""Production contract for the empirically validated GenGe V3.1.1 gate-only model.

This module intentionally mirrors the valuation-confidence rules that were
actually used by the frozen Round-8/9 ``v31_1_confidence_gate_only`` variant.
It is deliberately separate from ``selection_framework_v32``: V3.2 added
research-only rules and SELL confirmation that were not promoted.

V3.1.1 changes exactly one economic behaviour relative to V3.1:
LOW/INVALID valuation confidence blocks mechanical valuation BUY/SELL and
returns HOLD_REVIEW.  Hard-gate failure always wins and returns EXIT.  For
MEDIUM/HIGH confidence the original immediate V3.1 decision contract remains
in force.  Personal cost basis is never read.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .selection_framework_v31 import assess_v31


POLICY_VERSION = "gen_ge_v3_1_1_confidence_gate_only_round8_round9_validated"
SELL_ACTIONS = frozenset({"REDUCE_25", "REDUCE_50", "CORE_ONLY"})


class ValuationConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INVALID = "INVALID"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _first_finite(data: Mapping[str, Any], *fields: str) -> float | None:
    for field in fields:
        value = _finite(data.get(field))
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class ConfidenceAssessment:
    level: ValuationConfidence
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valuation_confidence": self.level.value,
            "valuation_confidence_reason_codes": ";".join(self.reason_codes),
        }


@dataclass(frozen=True)
class V311Decision:
    action: str
    target_position_fraction: float | None
    valuation_confidence: ValuationConfidence
    reason_codes: tuple[str, ...]
    normalized_earnings: float | None
    realistic_growth: float | None
    market_implied_growth: float | None
    expectation_gap: float | None
    neutral_value: float | None
    current_price: float | None
    price_to_neutral: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_model_version": POLICY_VERSION,
            "production_action": self.action,
            "production_target_position_fraction": self.target_position_fraction,
            "valuation_confidence": self.valuation_confidence.value,
            "reason_codes": ";".join(self.reason_codes),
            "normalized_earnings": self.normalized_earnings,
            "realistic_growth": self.realistic_growth,
            "market_implied_growth": self.market_implied_growth,
            "expectation_gap": self.expectation_gap,
            "neutral_value": self.neutral_value,
            "current_price": self.current_price,
            "price_to_neutral": self.price_to_neutral,
        }


def assess_valuation_confidence_v311(data: Mapping[str, Any]) -> ConfidenceAssessment:
    """Exact production form of the frozen Round-8/9 confidence gate.

    Aliases only adapt historical-panel names to production payload names; they
    do not add economic rules.  Missing observation-count, deduct-quality or
    cash-conversion evidence maps to LOW exactly as the Round-8/9 runner did.
    """
    current = _first_finite(data, "v31_current_price", "raw_latest_close", "current_price", "close")
    neutral = _first_finite(data, "v31_neutral_value", "neutral_value", "neutral_value_round6")
    normalized = _first_finite(
        data, "v31_normalized_profit", "normalized_earnings", "normalized_eps_round6"
    )
    realistic = _first_finite(
        data, "v31_realistic_profit_cagr", "realistic_growth", "realistic_growth_round6"
    )
    implied = _first_finite(
        data,
        "v31_market_implied_profit_cagr",
        "market_implied_growth",
        "market_implied_growth_round6",
    )

    invalid: list[str] = []
    if current is None or current <= 0:
        invalid.append("CURRENT_PRICE_INVALID")
    if neutral is None or neutral <= 0:
        invalid.append("NEUTRAL_VALUE_INVALID")
    if normalized is None or normalized <= 0:
        invalid.append("NORMALIZED_EARNINGS_INVALID")
    if realistic is None:
        invalid.append("REALISTIC_GROWTH_INVALID")
    if implied is None:
        invalid.append("MARKET_IMPLIED_GROWTH_INVALID")

    # Round-8/9 required ratio_expectation to be positive/finite.  In
    # production it is mathematically equivalent to current / neutral once
    # both required inputs above are valid.
    if current is not None and neutral is not None and neutral > 0:
        ratio = current / neutral
        if not math.isfinite(ratio) or ratio <= 0:
            invalid.append("PRICE_TO_NEUTRAL_INVALID")

    # Preserve the historical PIT guard when both dates are supplied.
    fund_date = data.get("fund_available_date")
    decision_date = data.get("date") or data.get("decision_date") or data.get("price_date")
    if fund_date not in (None, "") and decision_date not in (None, ""):
        try:
            import pandas as pd

            if pd.Timestamp(fund_date) > pd.Timestamp(decision_date):
                invalid.append("FUND_AVAILABLE_AFTER_DECISION_DATE")
        except (TypeError, ValueError):
            invalid.append("PIT_DATE_INVALID")

    if invalid:
        return ConfidenceAssessment(ValuationConfidence.INVALID, tuple(invalid))

    observations = _first_finite(data, "normalized_earnings_observation_count")
    observations = observations if observations is not None else 0.0
    deduct = _first_finite(
        data, "deduct_profit_quality_factor", "deduct_factor", "deduct_factor_round6"
    )
    cash = _first_finite(data, "cash_conversion_ratio", "cash_conversion")
    growth_range = _first_finite(data, "realistic_growth_four_report_range")
    growth_range = growth_range if growth_range is not None else 0.0
    implied_status = _text(data.get("implied_growth_status")).upper()

    low: list[str] = []
    if observations < 3:
        low.append("NORMALIZED_EARNINGS_HISTORY_SHORT")
    if deduct is None or deduct < 0.50:
        low.append("DEDUCT_PROFIT_QUALITY_LOW")
    if cash is None or cash <= 0:
        low.append("CASH_CONVERSION_NONPOSITIVE")
    if growth_range > 0.15:
        low.append("REALISTIC_GROWTH_UNSTABLE")
    if implied_status in {"INPUT_INCOMPLETE", "IMPLIED_ABOVE_SEARCH_RANGE"}:
        low.append("IMPLIED_GROWTH_UNRELIABLE")
    if low:
        return ConfidenceAssessment(ValuationConfidence.LOW, tuple(low))

    medium: list[str] = []
    if observations < 4:
        medium.append("NORMALIZED_EARNINGS_HISTORY_MEDIUM")
    if deduct is not None and deduct < 0.80:
        medium.append("DEDUCT_PROFIT_QUALITY_MEDIUM")
    if cash is not None and cash < 0.80:
        medium.append("CASH_CONVERSION_MEDIUM")
    if growth_range > 0.10:
        medium.append("REALISTIC_GROWTH_VARIABILITY_MEDIUM")
    if realistic is not None and (realistic <= 0.0 or realistic >= 0.30):
        medium.append("REALISTIC_GROWTH_AT_MODEL_BOUND")
    if medium:
        return ConfidenceAssessment(ValuationConfidence.MEDIUM, tuple(medium))

    return ConfidenceAssessment(ValuationConfidence.HIGH, ("ROUND8_9_CONFIDENCE_GATE_PASS",))


def decide_v311(data: Mapping[str, Any]) -> V311Decision:
    """Apply V3.1.1 gate-only policy with the original immediate V3.1 SELL."""
    v31 = assess_v31(data)
    confidence = assess_valuation_confidence_v311(data)
    current = _first_finite(data, "v31_current_price", "raw_latest_close", "current_price", "close")
    neutral = _first_finite(data, "v31_neutral_value", "neutral_value", "neutral_value_round6")
    normalized = _first_finite(
        data, "v31_normalized_profit", "normalized_earnings", "normalized_eps_round6"
    )
    realistic = _first_finite(
        data, "v31_realistic_profit_cagr", "realistic_growth", "realistic_growth_round6"
    )
    implied = _first_finite(
        data,
        "v31_market_implied_profit_cagr",
        "market_implied_growth",
        "market_implied_growth_round6",
    )
    gap = _first_finite(data, "v31_expectation_gap_pct", "expectation_gap", "expectation_gap_round6")
    ratio = current / neutral if current and neutral and neutral > 0 else None
    has_position = (
        _bool(data.get("v311_has_position"))
        or _bool(data.get("v32_has_position"))
        or ((_first_finite(data, "current_position_fraction") or 0.0) > 0)
    )

    def result(action: str, target: float | None, reasons: list[str]) -> V311Decision:
        return V311Decision(
            action=action,
            target_position_fraction=target,
            valuation_confidence=confidence.level,
            reason_codes=tuple(reasons),
            normalized_earnings=normalized,
            realistic_growth=realistic,
            market_implied_growth=implied,
            expectation_gap=gap,
            neutral_value=neutral,
            current_price=current,
            price_to_neutral=ratio,
        )

    # Hard logic always overrides valuation-confidence uncertainty.
    if v31.hard_gate_failures:
        return result("EXIT", 0.0, ["HARD_GATE_FAIL", *v31.hard_gate_failures])

    # This is the sole promoted V3.1.1 behaviour.
    if confidence.level in {ValuationConfidence.LOW, ValuationConfidence.INVALID}:
        return result(
            "HOLD_REVIEW",
            None,
            [f"VALUATION_CONFIDENCE_{confidence.level.value}", *confidence.reason_codes],
        )

    valuation_action = v31.exit_action
    if valuation_action in SELL_ACTIONS and has_position:
        return result(
            valuation_action,
            v31.target_position_fraction,
            ["V31_IMMEDIATE_VALUATION_SELL", valuation_action],
        )
    if valuation_action in SELL_ACTIONS and not has_position:
        return result("WAIT", 0.0, ["NO_POSITION_TO_REDUCE", valuation_action])

    if v31.buy_ready and ratio is not None and ratio <= 0.85:
        return result("BUY", 1.0, ["V31_BUY_GATES_PASS", "MARGIN_OF_SAFETY_PASS"])
    if not has_position:
        return result("WAIT", 0.0, ["BUY_CONDITIONS_NOT_MET"])
    if valuation_action == "HOLD_NO_ADD":
        return result("HOLD_NO_ADD", 1.0, ["PRICE_AT_OR_ABOVE_NEUTRAL"])
    if valuation_action == "HOLD_REVIEW":
        return result("HOLD_REVIEW", None, ["V31_VALUATION_INCOMPLETE"])
    return result("HOLD", 1.0, ["FUNDAMENTALS_INTACT", "NO_ACTION_THRESHOLD"])
