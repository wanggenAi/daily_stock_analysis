"""Single frozen production entry point for GenGe V3.1.1."""
from __future__ import annotations

from typing import Any, Mapping

from .selection_framework_v32 import V32Decision, assess_valuation_confidence, decide_v32


PRODUCTION_MODEL_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
PRODUCTION_MODEL_NAME = "GenGe V3.1.1 Production"
PRODUCTION_DECISION = "PROMOTE_CONFIDENCE_GATE_ONLY"
SELL_CONTRACT = "V31_IMMEDIATE_VALUATION_LADDER"
RESEARCH_MODEL_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
ALLOWED_ACTIONS = frozenset(
    {
        "BUY",
        "WAIT",
        "HOLD",
        "HOLD_NO_ADD",
        "HOLD_REVIEW",
        "REDUCE_25",
        "REDUCE_50",
        "CORE_ONLY",
        "EXIT",
    }
)


def decide_production(data: Mapping[str, Any]) -> V32Decision:
    """Apply the promoted Confidence Gate with the original immediate V3.1 SELL contract."""
    return decide_v32(data, require_sell_confirmation=False)


def production_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    decision = decide_production(data)
    confidence = assess_valuation_confidence(data)
    payload = decision.as_dict()
    payload.update(
        {
            "production_model_version": PRODUCTION_MODEL_VERSION,
            "production_model_name": PRODUCTION_MODEL_NAME,
            "production_promotion_decision": PRODUCTION_DECISION,
            "production_sell_contract": SELL_CONTRACT,
            "research_model_version": RESEARCH_MODEL_VERSION,
            "production_model_frozen": True,
            "valuation_confidence_reason_codes": ";".join(confidence.reason_codes),
        }
    )
    return payload
