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
ALLOWED_ACTIONS = frozenset({"BUY","WAIT","HOLD","HOLD_NO_ADD","HOLD_REVIEW","REDUCE_25","REDUCE_50","CORE_ONLY","EXIT"})


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _has_position(data: Mapping[str, Any]) -> bool:
    if _truthy(data.get("v311_has_position")) or _truthy(data.get("v32_has_position")):
        return True
    try:
        return float(data.get("current_position_fraction") or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


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
    """Apply V3.1.1 with strict BUY admission and explicit SELL rationale.

    Formal BUY requires HIGH valuation confidence, no existing position, and a
    price no greater than 80% of neutral/base value after the underlying V3.1
    buy gates pass. Typed insurers may recover audited PIT EV/growth evidence
    for holding review, but that typed path is deliberately capped at MEDIUM
    confidence and cannot create Formal BUY eligibility. REDUCE/CORE_ONLY is
    permitted only when the sell-rationale guard proves either stable intrinsic
    value plus material price overextension or material, structured, thesis-
    linked new evidence. Otherwise production fails closed to HOLD_REVIEW.
    """
    if is_insurer_typed_input(data):
        decision = decide_insurer_v311(data)
    else:
        decision = decide_v311(data)

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
    })
    if typed_insurer:
        payload.update(insurer_typed_payload_metadata(data))
    return payload
