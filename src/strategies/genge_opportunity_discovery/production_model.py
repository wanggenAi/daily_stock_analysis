"""Single frozen production entry point for GenGe V3.1.1."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .holding_valuation_continuity import continuity_review_required
from .selection_framework_v311 import (
    V311Decision,
    assess_valuation_confidence_v311,
    decide_v311,
)

PRODUCTION_MODEL_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
PRODUCTION_MODEL_NAME = "GenGe V3.1.1 Production"
PRODUCTION_DECISION = "PROMOTE_CONFIDENCE_GATE_PLUS_VALUATION_CONTINUITY"
SELL_CONTRACT = "V31_IMMEDIATE_VALUATION_LADDER_WITH_CONTINUITY_REVIEW"
RESEARCH_MODEL_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
PRODUCTION_POLICY_SOURCE = "gen_ge_v3_1_1_confidence_gate_round8_round9_plus_holding_valuation_continuity"
V32_SELL_CONFIRMATION_ENABLED = False
ALLOWED_ACTIONS = frozenset({"BUY","WAIT","HOLD","HOLD_NO_ADD","HOLD_REVIEW","REDUCE_25","REDUCE_50","CORE_ONLY","EXIT"})


def decide_production(data: Mapping[str, Any]) -> V311Decision:
    """Apply V3.1.1, then fail valuation-only sell discontinuities into review.

    Hard-gate EXIT remains untouched. The guard only intercepts valuation-driven
    REDUCE/CORE_ONLY transitions for an existing holding when the durable prior
    holding state shows a non-sell action and valuation continuity is not proven.
    """
    decision = decide_v311(data)
    required, reasons = continuity_review_required(data, decision.action)
    if required:
        return replace(
            decision,
            action="HOLD_REVIEW",
            target_position_fraction=None,
            reason_codes=("VALUATION_DISCONTINUITY_REVIEW", *reasons),
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
    })
    return payload
