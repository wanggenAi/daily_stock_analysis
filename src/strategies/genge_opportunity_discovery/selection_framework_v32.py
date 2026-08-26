"""Frozen Round-8/9 candidate decision contract for GenGe V3.2.

V3.2 keeps every V3.1 hard gate, score, valuation band and position target.
It adds a valuation-confidence gate and confirmation for valuation-only SELL
actions. A hard-gate failure always bypasses both protections and returns EXIT.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .selection_framework_v31 import assess_v31


POLICY_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
SELL_ACTIONS = frozenset({"REDUCE_25", "REDUCE_50", "CORE_ONLY"})
READY_EXECUTION_STATES = frozenset({"GENERIC_REVERSE_DIAGNOSTIC_READY"})


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
class V32Decision:
    action: str
    target_position_fraction: float | None
    sell_confirmation_count: int
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
            "v32_sell_confirmation_count": self.sell_confirmation_count,
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


def assess_valuation_confidence(data: Mapping[str, Any]) -> ConfidenceAssessment:
    """Assess model-input quality without using price performance or cost basis."""
    current = _first_finite(data, "v31_current_price", "raw_latest_close", "current_price")
    neutral = _first_finite(data, "v31_neutral_value", "neutral_value")
    normalized = _first_finite(data, "v31_normalized_profit", "normalized_earnings")
    realistic = _first_finite(data, "v31_realistic_profit_cagr", "realistic_growth")
    implied = _first_finite(data, "v31_market_implied_profit_cagr", "market_implied_growth")

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
    if _text(data.get("v32_pit_audit_status")).upper() == "FAIL" or _bool(
        data.get("future_financial_merge_detected")
    ):
        invalid.append("PIT_INTEGRITY_INVALID")
    if invalid:
        return ConfidenceAssessment(ValuationConfidence.INVALID, tuple(invalid))

    low: list[str] = []
    execution_state = _text(data.get("valuation_model_execution_state")).upper()
    if execution_state and execution_state not in READY_EXECUTION_STATES:
        low.append("VALUATION_MODEL_NOT_EXECUTED")
    for field, code in (
        ("financial_review_status", "FINANCIAL_REVIEW_NOT_OK"),
        ("valuation_diagnostic_status", "VALUATION_DIAGNOSTIC_NOT_OK"),
    ):
        status = _text(data.get(field)).upper()
        if status and status not in {"OK", "PASS", "PASSED"}:
            low.append(code)
    earnings_confidence = _text(data.get("earnings_quality_confidence")).upper()
    if earnings_confidence in {"LOW", "INVALID"}:
        low.append("EARNINGS_QUALITY_LOW")
    observations = _first_finite(data, "normalized_earnings_observation_count")
    if observations is not None and observations < 3:
        low.append("NORMALIZED_EARNINGS_HISTORY_SHORT")
    deduct_factor = _first_finite(data, "deduct_profit_quality_factor", "deduct_factor")
    if deduct_factor is not None and deduct_factor < 0.50:
        low.append("DEDUCT_PROFIT_QUALITY_LOW")
    cash_conversion = _first_finite(data, "cash_conversion_ratio", "cash_conversion")
    if cash_conversion is not None and cash_conversion <= 0:
        low.append("CASH_CONVERSION_NONPOSITIVE")
    growth_range = _first_finite(data, "realistic_growth_four_report_range")
    if growth_range is not None and growth_range > 0.15:
        low.append("REALISTIC_GROWTH_UNSTABLE")
    implied_status = _text(data.get("implied_growth_status")).upper()
    if implied_status in {"INPUT_INCOMPLETE", "IMPLIED_ABOVE_SEARCH_RANGE"}:
        low.append("IMPLIED_GROWTH_UNRELIABLE")
    if low:
        return ConfidenceAssessment(ValuationConfidence.LOW, tuple(low))

    medium: list[str] = []
    routing_confidence = _first_finite(data, "valuation_routing_confidence")
    if routing_confidence is not None and routing_confidence < 0.80:
        medium.append("VALUATION_ROUTE_MEDIUM")
    if earnings_confidence == "MEDIUM":
        medium.append("EARNINGS_QUALITY_MEDIUM")
    if observations is not None and observations < 4:
        medium.append("NORMALIZED_EARNINGS_HISTORY_MEDIUM")
    if deduct_factor is not None and deduct_factor < 0.80:
        medium.append("DEDUCT_PROFIT_QUALITY_MEDIUM")
    if cash_conversion is not None and cash_conversion < 0.80:
        medium.append("CASH_CONVERSION_MEDIUM")
    if realistic is not None and (realistic <= 0.0 or realistic >= 0.30):
        medium.append("REALISTIC_GROWTH_AT_MODEL_BOUND")
    if growth_range is not None and growth_range > 0.10:
        medium.append("REALISTIC_GROWTH_VARIABILITY_MEDIUM")
    if medium:
        return ConfidenceAssessment(ValuationConfidence.MEDIUM, tuple(medium))
    return ConfidenceAssessment(ValuationConfidence.HIGH, ("VALUATION_INPUTS_COMPLETE",))


def decide_v32(data: Mapping[str, Any], *, require_sell_confirmation: bool = True) -> V32Decision:
    """Return one unified BUY/WAIT/HOLD/SELL decision for production consumers."""
    v31 = assess_v31(data)
    confidence = assess_valuation_confidence(data)
    current = _first_finite(data, "v31_current_price", "raw_latest_close", "current_price")
    neutral = _first_finite(data, "v31_neutral_value", "neutral_value")
    normalized = _first_finite(data, "v31_normalized_profit", "normalized_earnings")
    realistic = _first_finite(data, "v31_realistic_profit_cagr", "realistic_growth")
    implied = _first_finite(data, "v31_market_implied_profit_cagr", "market_implied_growth")
    gap = _first_finite(data, "v31_expectation_gap_pct", "expectation_gap")
    ratio = current / neutral if current and neutral and neutral > 0 else None
    has_position = _bool(data.get("v32_has_position")) or (
        (_first_finite(data, "v32_current_position_fraction", "current_position_fraction") or 0.0) > 0
    )

    def result(action: str, target: float | None, count: int, reasons: list[str]) -> V32Decision:
        return V32Decision(
            action=action,
            target_position_fraction=target,
            sell_confirmation_count=count,
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

    if v31.hard_gate_failures:
        return result("EXIT", 0.0, 0, ["HARD_GATE_FAIL", *v31.hard_gate_failures])
    if confidence.level in {ValuationConfidence.LOW, ValuationConfidence.INVALID}:
        return result(
            "HOLD_REVIEW", None, 0,
            [f"VALUATION_CONFIDENCE_{confidence.level.value}", *confidence.reason_codes],
        )

    valuation_action = v31.exit_action
    if valuation_action in SELL_ACTIONS and has_position:
        prior = int(_first_finite(data, "v32_prior_sell_confirmation_count") or 0)
        if require_sell_confirmation and prior < 1:
            return result(
                "HOLD_REVIEW", None, 1,
                ["VALUATION_SELL_CONFIRMATION_PENDING", valuation_action, *confidence.reason_codes],
            )
        return result(
            valuation_action, v31.target_position_fraction, min(prior + 1, 2),
            ["VALUATION_SELL_CONFIRMED", valuation_action, *confidence.reason_codes],
        )

    if valuation_action in SELL_ACTIONS and not has_position:
        return result("WAIT", 0.0, 0, ["NO_POSITION_TO_REDUCE", valuation_action])
    if v31.buy_ready and ratio is not None and ratio <= 0.85:
        return result("BUY", 1.0, 0, ["V31_BUY_GATES_PASS", "MARGIN_OF_SAFETY_PASS"])
    if not has_position:
        return result("WAIT", 0.0, 0, ["BUY_CONDITIONS_NOT_MET"])
    if valuation_action == "HOLD_NO_ADD":
        return result("HOLD_NO_ADD", 1.0, 0, ["PRICE_AT_OR_ABOVE_NEUTRAL"])
    return result("HOLD", 1.0, 0, ["FUNDAMENTALS_INTACT", "NO_ACTION_THRESHOLD"])
