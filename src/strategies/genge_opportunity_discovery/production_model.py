"""Single frozen production entry point for GenGe V3.1.1."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .holding_valuation_continuity import sell_review_required
from .selection_framework_v311 import (
    V311Decision,
    assess_valuation_confidence_v311,
    decide_v311,
)

PRODUCTION_MODEL_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
PRODUCTION_MODEL_NAME = "GenGe V3.1.1 Production"
PRODUCTION_DECISION = "PROMOTE_CONFIDENCE_GATE_PLUS_EXPLICIT_SELL_RATIONALE"
SELL_CONTRACT = "V31_SELL_LADDER_WITH_EXPLICIT_RATIONALE_AND_CONTINUITY_REVIEW"
RESEARCH_MODEL_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
PRODUCTION_POLICY_SOURCE = "gen_ge_v3_1_1_confidence_gate_round8_round9_plus_explicit_sell_rationale"
V32_SELL_CONFIRMATION_ENABLED = False
ALLOWED_ACTIONS = frozenset({"BUY","WAIT","HOLD","HOLD_NO_ADD","HOLD_REVIEW","REDUCE_25","REDUCE_50","CORE_ONLY","EXIT"})


def decide_production(data: Mapping[str, Any]) -> V311Decision:
    """Apply V3.1.1 and require an explicit causal rationale for formal sells.

    REDUCE/CORE_ONLY is permitted only when the sell-rationale guard proves
    either stable intrinsic value plus material price overextension or material,
    structured, thesis-linked new evidence.  Otherwise production fails closed
    to HOLD_REVIEW.  Hard-gate EXIT remains immediate and is not intercepted.
    """
    decision = decide_v311(data)
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
    decision = decide_production(data)
    confidence = assess_valuation_confidence_v311(data)
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
        "formal_sell_requires_explicit_rationale": True,
        "formal_sell_mechanical_valuation_only_forbidden": True,
    })
    return payload
