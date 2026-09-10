"""Single frozen production entry point for GenGe V3.1.1.

Typed-insurer dependencies are intentionally lazy-loaded. Lightweight consumers
such as Candidate Terminal only need frozen policy constants and must not require
PyYAML merely by importing this module. Actual production evaluation still loads
the exact insurer implementation when it is called.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .holding_valuation_continuity import assess_holding_valuation_state, sell_review_required
from .selection_framework_v311 import (
    V311Decision,
    ValuationConfidence,
    assess_valuation_confidence_v311,
    decide_v311,
)

PRODUCTION_MODEL_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
PRODUCTION_MODEL_NAME = "GenGe V3.1.1 Production"
PRODUCTION_DECISION = "PROMOTE_HIGH_CONFIDENCE_STRICT_BUY_SAFETY_MARGIN_PLUS_EXPLICIT_SELL_RATIONALE"
SELL_CONTRACT = "V31_SELL_LADDER_WITH_EXPLICIT_RATIONALE_AND_CONTINUITY_REVIEW"
RESEARCH_MODEL_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
PRODUCTION_POLICY_SOURCE = "gen_ge_v3_1_1_high_confidence_strict_buy_safety_margin_plus_explicit_sell_rationale"
V32_SELL_CONFIRMATION_ENABLED = False
FORMAL_BUY_MAX_PRICE_TO_NEUTRAL = 0.80
HOLDING_ADD_POLICY_VERSION = "EXISTING_HOLDING_STAGED_ADD_V1"
HOLDING_ADD_MAX_PRICE_TO_NEUTRAL = 0.75
HOLDING_ADD_MAX_LOTS = 1
ALLOWED_ACTIONS = frozenset({"BUY","WAIT","HOLD","HOLD_NO_ADD","HOLD_REVIEW","REDUCE_25","REDUCE_50","CORE_ONLY","EXIT"})

_HARD_GATE_FIELDS = {
    "predictability": "v31_predictability_status",
    "long_term_demand": "v31_long_term_demand_status",
    "moat": "v31_moat_status",
    "financial_safety": "v31_financial_safety_status",
    "earnings_authenticity": "v31_earnings_authenticity_status",
}
_PASS_VALUES = frozenset({"PASS", "PASSED", "OK", "QUALIFIED", "TRUE", "YES", "STABLE", "STRENGTHENING"})
_FAIL_VALUES = frozenset({"FAIL", "FAILED", "NO", "FALSE", "UNQUALIFIED", "RED", "STRUCTURAL_DECLINE", "WEAKENING"})


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _has_position(data: Mapping[str, Any]) -> bool:
    if _truthy(data.get("v311_has_position")) or _truthy(data.get("v32_has_position")):
        return True
    if str(data.get("holding_status") or "").strip().upper() == "HELD":
        try:
            return float(data.get("confirmed_quantity") or 0.0) > 0.0
        except (TypeError, ValueError):
            pass
    try:
        return float(data.get("current_position_fraction") or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def _gate_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in _PASS_VALUES:
        return "PASS"
    if text in _FAIL_VALUES:
        return "FAIL"
    return "UNKNOWN"


def _holding_add_gate_state(data: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    failures: list[str] = []
    unknowns: list[str] = []
    for name, field in _HARD_GATE_FIELDS.items():
        status = _gate_status(data.get(field))
        if status == "FAIL":
            failures.append(name)
        elif status == "UNKNOWN":
            unknowns.append(name)
    return tuple(failures), tuple(unknowns)


def _holding_add_input_ready(data: Mapping[str, Any]) -> bool:
    expectation_status = str(data.get("v311_expectation_input_status") or "").strip().upper()
    price_date_status = str(data.get("price_date_verification_status") or "").strip().upper()
    price_mapping_status = str(data.get("price_mapping_status") or "").strip().upper()
    return expectation_status == "READY" and price_date_status == "VERIFIED" and price_mapping_status == "OK"


def _holding_add_assessment(
    data: Mapping[str, Any],
    decision: V311Decision,
    *,
    typed_insurer: bool,
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if typed_insurer:
        blockers.append("TYPED_INSURER_POLICY_SEPARATE")
    if decision.action != "HOLD":
        blockers.append("FORMAL_ACTION_NOT_HOLD")
    if not _has_position(data):
        blockers.append("NO_EXISTING_POSITION")
    if decision.valuation_confidence is not ValuationConfidence.HIGH:
        blockers.append("VALUATION_CONFIDENCE_NOT_HIGH")
    ratio = decision.price_to_neutral
    if ratio is None:
        blockers.append("PRICE_TO_NEUTRAL_INVALID")
    elif ratio > HOLDING_ADD_MAX_PRICE_TO_NEUTRAL:
        blockers.append("A_LEVEL_MARGIN_OF_SAFETY_NOT_MET")
    if not _holding_add_input_ready(data):
        blockers.append("FRESH_VERIFIED_INPUT_NOT_READY")
    failures, unknowns = _holding_add_gate_state(data)
    if failures:
        blockers.append("HARD_GATE_FAILURE:" + ",".join(failures))
    if blockers:
        return False, tuple(blockers)

    reasons = [
        "EXISTING_HOLDING_STAGED_ADD_AUTHORIZED",
        "VALUATION_CONFIDENCE_HIGH",
        "A_LEVEL_MARGIN_OF_SAFETY_PASS",
        f"price_to_neutral={ratio:.3f}<=0.75",
        "NO_KNOWN_HARD_GATE_FAILURE",
        "STAGED_ADD_CAP_ONE_LOT",
        "STAGED_ADD_NOT_FORMAL_BUY",
        "FORMAL_ACTION_UNCHANGED",
    ]
    if unknowns:
        reasons.append("HARD_GATE_UNKNOWNS_RETAINED:" + ",".join(unknowns))
    else:
        reasons.append("ALL_HARD_GATES_PASS")
    return True, tuple(reasons)


def _apply_formal_buy_gate(data: Mapping[str, Any], decision: V311Decision) -> V311Decision:
    if decision.action != "BUY":
        return decision
    if _has_position(data):
        return replace(
            decision,
            action="HOLD",
            target_position_fraction=1.0,
            reason_codes=("CORE_POOL_CONFERS_NO_BUY_PRIVILEGE", "EXISTING_POSITION_NOT_CANDIDATE_BUY"),
        )
    if decision.valuation_confidence is not ValuationConfidence.HIGH:
        return replace(
            decision,
            action="WAIT",
            target_position_fraction=0.0,
            reason_codes=("CORE_POOL_CONFERS_NO_BUY_PRIVILEGE", "BUY_VALUATION_CONFIDENCE_NOT_HIGH", *decision.reason_codes),
        )
    ratio = decision.price_to_neutral
    if ratio is None or ratio > FORMAL_BUY_MAX_PRICE_TO_NEUTRAL:
        return replace(
            decision,
            action="WAIT",
            target_position_fraction=0.0,
            reason_codes=("CORE_POOL_CONFERS_NO_BUY_PRIVILEGE", "BUY_MARGIN_OF_SAFETY_INSUFFICIENT", "PRICE_TOO_CLOSE_TO_BASE_VALUE"),
        )
    return replace(
        decision,
        reason_codes=("V31_BUY_GATES_PASS", "BUY_VALUATION_CONFIDENCE_HIGH", "MARGIN_OF_SAFETY_PASS", "PRICE_TO_NEUTRAL_AT_OR_BELOW_0_80"),
    )


def decide_production(data: Mapping[str, Any]) -> V311Decision:
    # Lazy import keeps policy-constant consumers independent of insurer/PyYAML runtime.
    from .insurer_typed_production import decide_insurer_v311, is_insurer_typed_input

    if is_insurer_typed_input(data):
        decision = decide_insurer_v311(data)
    else:
        decision = decide_v311(data)
    decision = _apply_formal_buy_gate(data, decision)

    # Dynamic valuation never manufactures REDUCE/EXIT. A material lowering of
    # the latest authorized valuation merely re-opens SELL review when the
    # frozen V3.1.1 ladder has not already produced a stronger action. Hard Gate
    # EXIT and existing SELL thresholds remain authoritative.
    if _has_position(data):
        valuation_state = assess_holding_valuation_state(data)
        if valuation_state["valuation_change"] in {"LOWERED", "INVALIDATED"} and decision.action in {
            "HOLD", "HOLD_NO_ADD", "BUY", "WAIT"
        }:
            return replace(
                decision,
                action="HOLD_REVIEW",
                target_position_fraction=None,
                reason_codes=(
                    "MATERIAL_VALUATION_CHANGE_REQUIRES_SELL_REVIEW",
                    f"VALUATION_{valuation_state['valuation_change']}",
                    *decision.reason_codes,
                ),
            )

    required, rationale_reasons = sell_review_required(data, decision.action)
    if required:
        return replace(
            decision,
            action="HOLD_REVIEW",
            target_position_fraction=None,
            reason_codes=("SELL_RATIONALE_REVIEW_REQUIRED", *rationale_reasons),
        )
    if rationale_reasons and decision.action in {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}:
        return replace(decision, reason_codes=tuple([*decision.reason_codes, *rationale_reasons]))
    return decision


def production_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    # These imports are required only when production is actually evaluated.
    from .insurer_typed_production import (
        assess_insurer_valuation_confidence_v311,
        insurer_typed_payload_metadata,
        is_insurer_typed_input,
    )

    typed_insurer = is_insurer_typed_input(data)
    decision = decide_production(data)
    confidence = (
        assess_insurer_valuation_confidence_v311(data)
        if typed_insurer
        else assess_valuation_confidence_v311(data)
    )
    valuation_state = assess_holding_valuation_state(data) if _has_position(data) else {
        "value_low": None,
        "neutral_value": decision.neutral_value,
        "value_high": None,
        "valuation_range_ready": False,
        "previous_value_low": None,
        "previous_neutral_value": None,
        "previous_value_high": None,
        "previous_valuation_available": False,
        "valuation_change": "STABLE",
        "valuation_change_materiality_threshold": 0.01,
        "price_value_zone": "UNKNOWN",
        "price_to_neutral_latest": decision.price_to_neutral,
        "upside_to_value_high": None,
        "profit_protection_overlay_eligible": False,
        "profit_protection_risk_reasons": "",
        "profit_alone_is_sell_reason": False,
        "profit_used_by_formal_decision": False,
    }
    add_failures, add_unknowns = _holding_add_gate_state(data)
    add_authorized, add_reasons = _holding_add_assessment(data, decision, typed_insurer=typed_insurer)
    payload = decision.as_dict()
    payload.update({
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "production_model_name": PRODUCTION_MODEL_NAME,
        "production_promotion_decision": PRODUCTION_DECISION,
        "production_sell_contract": SELL_CONTRACT,
        "production_policy_source": PRODUCTION_POLICY_SOURCE,
        "research_model_version": RESEARCH_MODEL_VERSION,
        "v32_sell_confirmation_enabled": V32_SELL_CONFIRMATION_ENABLED,
        "production_model_frozen": True,
        "valuation_confidence_reason_codes": ";".join(confidence.reason_codes),
        "formal_buy_requires_high_confidence": True,
        "formal_buy_max_price_to_neutral": FORMAL_BUY_MAX_PRICE_TO_NEUTRAL,
        "core_pool_confers_no_buy_privilege": True,
        "formal_sell_requires_explicit_rationale": True,
        "formal_sell_mechanical_valuation_only_forbidden": True,
        "dynamic_valuation_primary_reference": True,
        **valuation_state,
        "profit_protection_overlay_authority": "RISK_CONTEXT_ONLY_NO_FORMAL_ACTION_MUTATION",
        "holding_add_policy_version": HOLDING_ADD_POLICY_VERSION,
        "holding_add_authorized": add_authorized,
        "holding_add_authorization_reason_codes": ";".join(add_reasons),
        "holding_add_existing_position_only": True,
        "holding_add_requires_high_confidence": True,
        "holding_add_max_price_to_neutral": HOLDING_ADD_MAX_PRICE_TO_NEUTRAL,
        "holding_add_max_lots": HOLDING_ADD_MAX_LOTS,
        "holding_add_formal_action_unchanged": True,
        "holding_add_is_formal_buy": False,
        "holding_add_hard_gate_failures": ";".join(add_failures),
        "holding_add_hard_gate_unknowns": ";".join(add_unknowns),
        "holding_add_unknown_is_pass": False,
        "holding_add_no_auto_trade": True,
    })
    if typed_insurer:
        payload.update(insurer_typed_payload_metadata(data))
    return payload
