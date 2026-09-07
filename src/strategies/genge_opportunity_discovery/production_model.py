"""Single frozen production entry point for GenGe V3.1.1."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .holding_valuation_continuity import sell_review_required
from .insurer_typed_production import (
    assess_insurer_valuation_confidence_v311,
    decide_insurer_v311,
    insurer_typed_payload_metadata,
    is_insurer_typed_input,
)
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
ALLOWED_ACTIONS = frozenset({"BUY","ADD","WAIT","HOLD","HOLD_NO_ADD","HOLD_REVIEW","REDUCE_25","REDUCE_50","CORE_ONLY","EXIT"})

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
    return (
        expectation_status == "READY"
        and price_date_status == "VERIFIED"
        and price_mapping_status == "OK"
    )


def _apply_existing_holding_add_gate(data: Mapping[str, Any], decision: V311Decision) -> V311Decision:
    """Authorize only a one-lot staged ADD for an already-held, deeply cheap name.

    This is deliberately *not* a Formal BUY shortcut.  It never upgrades a new
    candidate, never converts UNKNOWN hard gates to PASS, never overrides an
    explicit hard-gate failure, and never applies to the typed-insurer path.
    It only allows a small staged ADD when an existing holding already has a
    HIGH-confidence, same-run/fresh valuation and trades in the frozen V3.1
    A-level margin band (<=75% of neutral value).  Unknown qualitative gates are
    retained and surfaced in the payload; the one-lot cap limits risk while a
    fuller re-underwrite remains pending.
    """
    if decision.action != "HOLD" or not _has_position(data):
        return decision
    if decision.valuation_confidence is not ValuationConfidence.HIGH:
        return decision
    ratio = decision.price_to_neutral
    if ratio is None or ratio > HOLDING_ADD_MAX_PRICE_TO_NEUTRAL:
        return decision
    if not _holding_add_input_ready(data):
        return decision
    failures, unknowns = _holding_add_gate_state(data)
    if failures:
        return decision

    reasons = [
        "EXISTING_HOLDING_STAGED_ADD",
        "VALUATION_CONFIDENCE_HIGH",
        "A_LEVEL_MARGIN_OF_SAFETY_PASS",
        f"price_to_neutral={ratio:.3f}<=0.75",
        "NO_KNOWN_HARD_GATE_FAILURE",
        "STAGED_ADD_CAP_ONE_LOT",
        "STAGED_ADD_NOT_FORMAL_BUY",
    ]
    if unknowns:
        reasons.append("HARD_GATE_UNKNOWNS_RETAINED:" + ",".join(unknowns))
    else:
        reasons.append("ALL_HARD_GATES_PASS")
    return replace(
        decision,
        action="ADD",
        target_position_fraction=None,
        reason_codes=tuple(reasons),
    )


def _apply_formal_buy_gate(data: Mapping[str, Any], decision: V311Decision) -> V311Decision:
    """Keep core-quality admission separate from formal price-action admission.

    Research/core-pool quality never confers BUY privilege.  A candidate may be
    excellent and remain WAIT until valuation evidence is HIGH confidence and
    price is at least 20% below the current neutral/base value.  Existing
    holdings are handled by the holding ladder and can never be re-labelled BUY
    by the candidate admission path.
    """
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
            reason_codes=(
                "CORE_POOL_CONFERS_NO_BUY_PRIVILEGE",
                "BUY_VALUATION_CONFIDENCE_NOT_HIGH",
                *decision.reason_codes,
            ),
        )

    ratio = decision.price_to_neutral
    if ratio is None or ratio > FORMAL_BUY_MAX_PRICE_TO_NEUTRAL:
        return replace(
            decision,
            action="WAIT",
            target_position_fraction=0.0,
            reason_codes=(
                "CORE_POOL_CONFERS_NO_BUY_PRIVILEGE",
                "BUY_MARGIN_OF_SAFETY_INSUFFICIENT",
                "PRICE_TOO_CLOSE_TO_BASE_VALUE",
            ),
        )

    return replace(
        decision,
        reason_codes=(
            "V31_BUY_GATES_PASS",
            "BUY_VALUATION_CONFIDENCE_HIGH",
            "MARGIN_OF_SAFETY_PASS",
            "PRICE_TO_NEUTRAL_AT_OR_BELOW_0_80",
        ),
    )


def decide_production(data: Mapping[str, Any]) -> V311Decision:
    """Apply V3.1.1 with strict BUY admission, staged holding ADD and SELL rationale.

    Formal BUY remains unchanged: it requires the underlying V3.1 buy gates,
    HIGH valuation confidence, no existing position, and price <=80% of neutral
    value.  A separate, risk-capped holding path may emit ADD only for an
    existing non-insurer holding with HIGH-confidence fresh valuation evidence,
    no known hard-gate failure, and price <=75% of neutral value.  Unknown hard
    gates remain UNKNOWN; they are not promoted to PASS.  Typed insurers remain
    capped by their own policy and cannot enter this ADD path.  REDUCE/CORE_ONLY
    still requires the explicit sell-rationale continuity guard.
    """
    typed_insurer = is_insurer_typed_input(data)
    if typed_insurer:
        decision = decide_insurer_v311(data)
    else:
        decision = decide_v311(data)
        decision = _apply_existing_holding_add_gate(data, decision)

    # Hard-gate EXIT and holding/sell actions are never weakened by the BUY gate.
    decision = _apply_formal_buy_gate(data, decision)

    required, rationale_reasons = sell_review_required(data, decision.action)
    if required:
        return replace(
            decision,
            action="HOLD_REVIEW",
            target_position_fraction=None,
            reason_codes=("SELL_RATIONALE_REVIEW_REQUIRED", *rationale_reasons),
        )
    if rationale_reasons and decision.action in {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}:
        return replace(
            decision,
            reason_codes=tuple([*decision.reason_codes, *rationale_reasons]),
        )
    return decision


def production_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    typed_insurer = is_insurer_typed_input(data)
    decision = decide_production(data)
    confidence = (
        assess_insurer_valuation_confidence_v311(data)
        if typed_insurer
        else assess_valuation_confidence_v311(data)
    )
    add_failures, add_unknowns = _holding_add_gate_state(data)
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
        "holding_add_policy_version": HOLDING_ADD_POLICY_VERSION,
        "holding_add_existing_position_only": True,
        "holding_add_requires_high_confidence": True,
        "holding_add_max_price_to_neutral": HOLDING_ADD_MAX_PRICE_TO_NEUTRAL,
        "holding_add_max_lots": HOLDING_ADD_MAX_LOTS,
        "holding_add_is_formal_buy": False,
        "holding_add_hard_gate_failures": ";".join(add_failures),
        "holding_add_hard_gate_unknowns": ";".join(add_unknowns),
        "holding_add_unknown_is_pass": False,
        "holding_add_no_auto_trade": True,
    })
    if typed_insurer:
        payload.update(insurer_typed_payload_metadata(data))
    return payload