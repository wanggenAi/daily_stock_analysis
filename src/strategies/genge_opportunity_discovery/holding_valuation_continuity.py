"""Holding sell-rationale and dynamic valuation-continuity guard for GenGe V3.1.1.

A formal REDUCE/CORE_ONLY must have a causal, auditable reason. Production may
not sell merely because a position has a large unrealized gain or because one
fresh run emitted a slightly different valuation. The current valuation range
is compared with the previous *authorized Canonical* baseline using a material
change rule; price is always interpreted against the latest valid range.

This module does not change the frozen V3.1/V3.1.1 BUY/SELL thresholds, Hard
Gate, confidence gate, or no-auto-trade contract. It is a fail-closed rationale
and continuity layer around the authorized producer. Personal cost basis is not
an input to Formal action generation: profit belongs to the investor-facing
Profit Protection Overlay and can never be a sell reason by itself.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from src.genge_v311_persistence_order import PersistenceOrder, classify_persistence_order

STATE_PATH = Path("data/opportunity_snapshots/holding_valuation_continuity_state.json")
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}
NON_SELL_ACTIONS = {"HOLD", "HOLD_NO_ADD", "HOLD_REVIEW", "BUY", "WAIT"}

VALUATION_CHANGE_MATERIALITY = 0.01
NEUTRAL_JUMP_THRESHOLD = 0.20
NORMALIZED_EARNINGS_JUMP_THRESHOLD = 0.20
MIN_STABLE_VALUE_OVEREXTENSION = 1.20
PROFIT_PROTECTION_MAX_UPSIDE_TO_HIGH = 0.10

# Exact frozen Round-6 valuation parameters. The generic range fallback below
# is allowed only when the supplied neutral value round-trips through this same
# equation, so a future model change fails closed instead of silently drifting.
ROUND6_POLICY_SOURCE = "round6_expectation_gap_10y_strict_pit_frozen"
ROUND6_DISCOUNT_RATE = 0.10
ROUND6_TERMINAL_GROWTH = 0.03
ROUND6_HORIZON_YEARS = 10
ROUND6_REALISTIC_GROWTH_CAP = 0.30
ROUND6_REVENUE_GROWTH_ALLOWANCE = 0.05
ROUND6_NEUTRAL_MATCH_TOLERANCE = 1e-8

MATERIAL_EVIDENCE_TYPES = {
    "EARNINGS_POWER_DETERIORATION",
    "GUIDANCE_CUT",
    "MARGIN_STRUCTURE_DETERIORATION",
    "CASH_FLOW_DETERIORATION",
    "BALANCE_SHEET_DETERIORATION",
    "MOAT_OR_COMPETITIVE_POSITION_DETERIORATION",
    "DEMAND_OR_INDUSTRY_THESIS_DETERIORATION",
    "REGULATORY_OR_POLICY_IMPAIRMENT",
    "CAPITAL_ALLOCATION_IMPAIRMENT",
    "VALUATION_MODEL_INPUT_CORRECTION",
}

PROFIT_PROTECTION_RISK_FLAGS = {
    "profit_protection_risk_evidence": "ADDITIONAL_RISK_EVIDENCE",
    "event_supply_risk_material": "EVENT_SUPPLY_RISK",
    "shareholder_reduction_window_active": "SHAREHOLDER_REDUCTION_WINDOW",
    "unlock_window_active": "SHARE_UNLOCK_WINDOW",
    "failed_spike_confirmed": "FAILED_SPIKE_CONFIRMED",
}


def _finite(v: Any):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _truthy(v: Any) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _code(v: Any):
    t = str(v or "").strip().upper()
    if "." in t:
        t = t.split(".")[0]
    for p in ("SH", "SZ", "BJ"):
        if t.startswith(p) and t[len(p):].isdigit():
            t = t[len(p):]
    return t.zfill(6) if t.isdigit() else t


def _first_finite(data: Mapping[str, Any], *fields: str) -> float | None:
    for field in fields:
        value = _finite(data.get(field))
        if value is not None:
            return value
    return None


def load_state(path: Path = STATE_PATH):
    if not path.exists():
        return {"contract_version": "V311_HOLDING_SELL_RATIONALE_V3", "holdings": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("holdings"), dict):
        raise ValueError("invalid holding valuation continuity state")
    return data


def _round6_value_expectation_10y(normalized_eps: float, start_growth: float) -> float | None:
    """Pure-Python mirror of the frozen Round-6 earning-power equation."""
    if normalized_eps <= 0 or not math.isfinite(normalized_eps) or not math.isfinite(start_growth):
        return None
    growth = min(max(float(start_growth), 0.0), ROUND6_REALISTIC_GROWTH_CAP)
    earnings = float(normalized_eps)
    present_value = 0.0
    for year in range(1, ROUND6_HORIZON_YEARS + 1):
        if year == 1:
            year_growth = growth
        else:
            fraction = (year - 1) / (ROUND6_HORIZON_YEARS - 1)
            year_growth = growth + (ROUND6_TERMINAL_GROWTH - growth) * fraction
        earnings *= 1.0 + year_growth
        present_value += earnings / ((1.0 + ROUND6_DISCOUNT_RATE) ** year)
    terminal_multiple = 1.0 / (ROUND6_DISCOUNT_RATE - ROUND6_TERMINAL_GROWTH)
    present_value += (
        terminal_multiple
        * earnings
        / ((1.0 + ROUND6_DISCOUNT_RATE) ** ROUND6_HORIZON_YEARS)
    )
    return float(present_value)


def _derive_strict_pit_generic_range(
    data: Mapping[str, Any], neutral: float | None
) -> dict[str, Any] | None:
    """Derive an auditable generic range when V3.1 scenario endpoints are absent.

    This is not a new valuation model. It reuses the exact frozen Round-6
    earning-power equation and varies only the starting-growth assumption by
    observed strict-PIT uncertainty. The uncertainty width is the maximum of
    the existing four-report realistic-growth range and disagreement between
    the two fundamental growth supports already used by Round 6. No price,
    personal cost basis, unrealized P&L or stock-specific constant is read.

    The fallback is fail-closed: it only runs for READY Round-6 strict-PIT rows,
    and only when the supplied neutral value round-trips through the frozen
    equation. Missing uncertainty evidence produces a zero-width range rather
    than invented dispersion; qualitative UNKNOWN gates remain untouched.
    """
    if str(data.get("v311_expectation_input_status") or "").strip().upper() != "READY":
        return None
    if str(data.get("v311_expectation_policy_source") or "").strip() != ROUND6_POLICY_SOURCE:
        return None
    normalized = _first_finite(data, "v31_normalized_profit", "normalized_earnings")
    realistic = _first_finite(data, "v31_realistic_profit_cagr", "realistic_growth")
    if normalized is None or normalized <= 0 or realistic is None or neutral is None or neutral <= 0:
        return None
    if realistic < 0 or realistic > ROUND6_REALISTIC_GROWTH_CAP:
        return None

    recomputed_neutral = _round6_value_expectation_10y(normalized, realistic)
    if recomputed_neutral is None:
        return None
    allowed_error = max(1e-10, abs(neutral) * ROUND6_NEUTRAL_MATCH_TOLERANCE)
    if abs(recomputed_neutral - neutral) > allowed_error:
        return None

    widths: list[float] = []
    four_report_range = _finite(data.get("realistic_growth_four_report_range"))
    if four_report_range is not None and four_report_range >= 0:
        widths.append(four_report_range)

    eps_growth = _finite(data.get("eps_growth_3y_round6"))
    if eps_growth is not None:
        eps_support = min(max(eps_growth, 0.0), ROUND6_REALISTIC_GROWTH_CAP)
        widths.append(abs(eps_support - realistic))

    revenue_growth = _finite(data.get("revenue_growth_3y_round6"))
    if revenue_growth is not None:
        revenue_support = min(
            max(revenue_growth + ROUND6_REVENUE_GROWTH_ALLOWANCE, 0.0),
            ROUND6_REALISTIC_GROWTH_CAP,
        )
        widths.append(abs(revenue_support - realistic))

    uncertainty_width = max(widths) if widths else 0.0
    low_growth = max(0.0, realistic - uncertainty_width)
    high_growth = min(ROUND6_REALISTIC_GROWTH_CAP, realistic + uncertainty_width)
    low = _round6_value_expectation_10y(normalized, low_growth)
    high = _round6_value_expectation_10y(normalized, high_growth)
    if low is None or high is None or low <= 0 or low > neutral or high < neutral:
        return None
    return {
        "low": low,
        "neutral": neutral,
        "high": high,
        "source": "V311_STRICT_PIT_GENERIC_RANGE",
        "method": "ROUND6_10Y_EARNING_POWER_REALISTIC_GROWTH_UNCERTAINTY_BAND",
        "growth_low": low_growth,
        "growth_neutral": realistic,
        "growth_high": high_growth,
        "growth_uncertainty_width": uncertainty_width,
        "neutral_roundtrip_verified": True,
    }


def _current_valuation_range(data: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, dict[str, Any]]:
    low = _first_finite(data, "v31_pessimistic_value", "value_low", "pessimistic_value")
    neutral = _first_finite(data, "v31_neutral_value", "neutral_value")
    high = _first_finite(data, "v31_optimistic_value", "value_high", "optimistic_value")
    if low is not None and high is not None:
        return low, neutral, high, {
            "source": "V31_EXPLICIT_SCENARIO_RANGE",
            "method": "UPSTREAM_SCENARIO_VALUATION",
            "growth_low": None,
            "growth_neutral": _first_finite(data, "v31_realistic_profit_cagr", "realistic_growth"),
            "growth_high": None,
            "growth_uncertainty_width": None,
            "neutral_roundtrip_verified": None,
        }
    if low is None and high is None:
        derived = _derive_strict_pit_generic_range(data, neutral)
        if derived:
            return derived["low"], derived["neutral"], derived["high"], derived
    return low, neutral, high, {
        "source": "INCOMPLETE_RANGE",
        "method": "FAIL_CLOSED_NO_GENERIC_RANGE",
        "growth_low": None,
        "growth_neutral": _first_finite(data, "v31_realistic_profit_cagr", "realistic_growth"),
        "growth_high": None,
        "growth_uncertainty_width": None,
        "neutral_roundtrip_verified": False,
    }


def _current_values(data: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    low, neutral, high, _ = _current_valuation_range(data)
    return low, neutral, high


def _previous_values(prev: Mapping[str, Any] | None) -> tuple[float | None, float | None, float | None]:
    prev = prev or {}
    return _finite(prev.get("value_low")), _finite(prev.get("neutral_value")), _finite(prev.get("value_high"))


def _range_invalid(low: float | None, neutral: float | None, high: float | None) -> bool:
    if neutral is None or neutral <= 0:
        return True
    if low is not None and low <= 0:
        return True
    if high is not None and high <= 0:
        return True
    if low is not None and low > neutral:
        return True
    if high is not None and neutral > high:
        return True
    if low is not None and high is not None and low > high:
        return True
    return False


def _material_delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return current / previous - 1.0


def _valuation_change(
    current: tuple[float | None, float | None, float | None],
    previous: tuple[float | None, float | None, float | None],
) -> str:
    low, neutral, high = current
    if _range_invalid(low, neutral, high):
        return "INVALIDATED"

    p_low, p_neutral, p_high = previous
    neutral_delta = _material_delta(neutral, p_neutral)
    if neutral_delta is not None and abs(neutral_delta) >= VALUATION_CHANGE_MATERIALITY:
        return "RAISED" if neutral_delta > 0 else "LOWERED"

    low_delta = _material_delta(low, p_low)
    high_delta = _material_delta(high, p_high)
    endpoint_deltas = [
        d for d in (low_delta, high_delta)
        if d is not None and abs(d) >= VALUATION_CHANGE_MATERIALITY
    ]
    if len(endpoint_deltas) == 2 and all(d > 0 for d in endpoint_deltas):
        return "RAISED"
    if len(endpoint_deltas) == 2 and all(d < 0 for d in endpoint_deltas):
        return "LOWERED"
    return "STABLE"


def _price_zone(price: float | None, low: float | None, neutral: float | None, high: float | None) -> str:
    if price is None or price <= 0 or _range_invalid(low, neutral, high):
        return "UNKNOWN"
    if low is None or high is None:
        return "UNKNOWN"
    if price < low:
        return "BELOW_VALUE"
    if price <= neutral:
        return "FAIR_VALUE"
    if price <= high:
        return "UPPER_VALUE"
    return "OVERVALUED"


def _profit_protection_risk_reasons(data: Mapping[str, Any]) -> tuple[str, ...]:
    reasons = [
        reason for field, reason in PROFIT_PROTECTION_RISK_FLAGS.items()
        if _truthy(data.get(field))
    ]
    evidence_ok, _ = _material_override_evidence(data)
    if evidence_ok:
        reasons.append("MATERIAL_THESIS_LINKED_RISK_EVIDENCE")
    return tuple(dict.fromkeys(reasons))


def assess_holding_valuation_state(data: Mapping[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Return latest-vs-authorized valuation state without creating an action."""
    state_path = path or STATE_PATH
    code = _code(data.get("code"))
    prev = load_state(state_path).get("holdings", {}).get(code)
    low, neutral, high, range_meta = _current_valuation_range(data)
    current = (low, neutral, high)
    previous = _previous_values(prev)
    p_low, p_neutral, p_high = previous
    price = _first_finite(data, "v31_current_price", "current_price", "raw_latest_close")
    change = _valuation_change(current, previous)
    zone = _price_zone(price, low, neutral, high)
    upside_to_high = None
    if price is not None and price > 0 and high is not None and high > 0:
        upside_to_high = high / price - 1.0
    risk_reasons = _profit_protection_risk_reasons(data)
    overlay_eligible = bool(
        prev
        and change in {"STABLE", "LOWERED"}
        and zone in {"UPPER_VALUE", "OVERVALUED"}
        and upside_to_high is not None
        and upside_to_high <= PROFIT_PROTECTION_MAX_UPSIDE_TO_HIGH
        and risk_reasons
    )
    return {
        "value_low": low,
        "neutral_value": neutral,
        "value_high": high,
        "valuation_range_ready": low is not None and high is not None and not _range_invalid(low, neutral, high),
        "valuation_range_source": range_meta.get("source"),
        "valuation_range_method": range_meta.get("method"),
        "valuation_range_growth_low": range_meta.get("growth_low"),
        "valuation_range_growth_neutral": range_meta.get("growth_neutral"),
        "valuation_range_growth_high": range_meta.get("growth_high"),
        "valuation_range_growth_uncertainty_width": range_meta.get("growth_uncertainty_width"),
        "valuation_range_neutral_roundtrip_verified": range_meta.get("neutral_roundtrip_verified"),
        "previous_value_low": p_low,
        "previous_neutral_value": p_neutral,
        "previous_value_high": p_high,
        "previous_valuation_available": bool(prev and p_neutral is not None and p_neutral > 0),
        "valuation_change": change,
        "valuation_change_materiality_threshold": VALUATION_CHANGE_MATERIALITY,
        "price_value_zone": zone,
        "price_to_neutral_latest": price / neutral if price is not None and neutral is not None and neutral > 0 else None,
        "upside_to_value_high": upside_to_high,
        "profit_protection_overlay_eligible": overlay_eligible,
        "profit_protection_risk_reasons": ";".join(risk_reasons),
        "profit_alone_is_sell_reason": False,
        "profit_used_by_formal_decision": False,
    }


def _material_override_evidence(data: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Only structured, material, thesis-linked evidence can justify re-underwrite."""
    evidence_id = str(data.get("valuation_continuity_evidence_id") or "").strip()
    evidence_at = str(data.get("valuation_continuity_evidence_observed_at") or "").strip()
    evidence_reason = str(data.get("valuation_continuity_evidence_reason") or "").strip()
    evidence_type = str(data.get("valuation_continuity_evidence_type") or "").strip().upper()
    material = _truthy(data.get("valuation_continuity_evidence_material"))
    thesis_link = str(data.get("valuation_continuity_thesis_link") or "").strip()

    missing = []
    if not evidence_id:
        missing.append("SELL_EVIDENCE_ID_MISSING")
    if not evidence_at:
        missing.append("SELL_EVIDENCE_TIME_MISSING")
    if not evidence_reason:
        missing.append("SELL_EVIDENCE_REASON_MISSING")
    if evidence_type not in MATERIAL_EVIDENCE_TYPES:
        missing.append("SELL_EVIDENCE_TYPE_NOT_MATERIAL")
    if not material:
        missing.append("SELL_EVIDENCE_NOT_MARKED_MATERIAL")
    if not thesis_link:
        missing.append("SELL_EVIDENCE_THESIS_LINK_MISSING")
    if evidence_reason and len(evidence_reason) < 20:
        missing.append("SELL_EVIDENCE_REASON_TOO_THIN")
    return not missing, tuple(missing)


def sell_review_required(data: Mapping[str, Any], action: str, *, path: Path = STATE_PATH):
    """Return whether a valuation-driven formal sell must fail closed to review."""
    if action not in SELL_ACTIONS:
        return False, ()
    if not bool(data.get("v311_has_position") or data.get("v32_has_position")):
        return False, ()

    code = _code(data.get("code"))
    prev = load_state(path).get("holdings", {}).get(code)
    if not prev:
        return True, ("SELL_RATIONALE_BASELINE_MISSING",)

    valuation = assess_holding_valuation_state(data, path=path)
    current_neutral = _finite(valuation.get("neutral_value"))
    current_norm = _finite(data.get("v31_normalized_profit") or data.get("normalized_earnings"))
    current_price = _first_finite(data, "v31_current_price", "current_price", "raw_latest_close")
    previous_neutral = _finite(prev.get("neutral_value"))
    previous_norm = _finite(prev.get("normalized_earnings"))

    continuity_failures = []
    if previous_neutral is None or previous_neutral <= 0 or current_neutral is None or current_neutral <= 0:
        continuity_failures.append("VALUATION_CONTINUITY_BASELINE_INCOMPLETE")
    else:
        neutral_jump = abs(current_neutral / previous_neutral - 1.0)
        if neutral_jump >= NEUTRAL_JUMP_THRESHOLD:
            continuity_failures.append("NEUTRAL_VALUE_DISCONTINUITY")

    if previous_norm and current_norm:
        if abs(current_norm / previous_norm - 1.0) >= NORMALIZED_EARNINGS_JUMP_THRESHOLD:
            continuity_failures.append("NORMALIZED_EARNINGS_DISCONTINUITY")

    if continuity_failures:
        override_ok, override_failures = _material_override_evidence(data)
        if override_ok:
            return False, ("SELL_RATIONALE_MATERIAL_REUNDERWRITE_EVIDENCE",)
        return True, tuple(["SELL_RATIONALE_NOT_PROVEN", *continuity_failures, *override_failures])

    if current_price is None or current_price <= 0 or current_neutral is None or current_neutral <= 0:
        return True, ("SELL_RATIONALE_PRICE_OR_VALUE_INVALID",)

    price_to_neutral = current_price / current_neutral
    if price_to_neutral < MIN_STABLE_VALUE_OVEREXTENSION:
        return True, ("SELL_RATIONALE_NOT_MATERIAL", "STABLE_VALUE_OVEREXTENSION_BELOW_MINIMUM")

    if valuation.get("profit_protection_overlay_eligible"):
        return False, ("SELL_RATIONALE_VALUE_RISK_PROTECTION",)
    return False, ("SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION",)


def continuity_review_required(data: Mapping[str, Any], action: str, *, path: Path = STATE_PATH):
    return sell_review_required(data, action, path=path)


def persist_from_snapshot(snapshot_path: Path, state_path: Path = STATE_PATH):
    """Persist only an authorized snapshot that moves durable state forward."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be an object")
    state_exists = state_path.is_file()
    state = load_state(state_path)

    current_sid = state.get("latest_applied_snapshot_id")
    current_run = state.get("latest_applied_source_run_id")
    if state_exists and (current_sid in (None, "") and current_run in (None, "")):
        if state.get("holdings"):
            raise ValueError("holding continuity state has baselines but no durable Canonical identity")

    order = classify_persistence_order(
        incoming_snapshot_id=snapshot.get("snapshot_id"),
        incoming_source_run_id=snapshot.get("source_run_id"),
        current_snapshot_id=current_sid,
        current_source_run_id=current_run,
    )
    if order in {PersistenceOrder.SAME, PersistenceOrder.STALE}:
        return state

    state["contract_version"] = "V311_HOLDING_SELL_RATIONALE_V3"
    holdings = state.setdefault("holdings", {})
    for row in snapshot.get("production", {}).get("holding_decisions", []):
        code = _code(row.get("code"))
        if not code:
            continue
        holdings[code] = {
            "action": row.get("action") or row.get("production_action"),
            "value_low": row.get("value_low"),
            "neutral_value": row.get("neutral_value"),
            "value_high": row.get("value_high"),
            "normalized_earnings": row.get("normalized_earnings"),
            "current_price": row.get("current_price"),
            "price_to_neutral": row.get("price_to_neutral"),
            "valuation_confidence": row.get("valuation_confidence"),
            "valuation_change": row.get("valuation_change"),
            "price_value_zone": row.get("price_value_zone"),
            "reason_codes": row.get("reason_codes"),
            "canonical_snapshot_id": snapshot.get("snapshot_id"),
            "canonical_source_run_id": str(snapshot.get("source_run_id")),
            "decision_date": row.get("decision_date"),
        }
    state["latest_applied_snapshot_id"] = snapshot.get("snapshot_id")
    state["latest_applied_source_run_id"] = str(snapshot.get("source_run_id"))
    state["no_auto_trade"] = True
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state
