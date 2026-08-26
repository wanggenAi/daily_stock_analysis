"""Single frozen production entry point for GenGe V3.1.1."""
from __future__ import annotations

from typing import Any, Mapping

from .selection_framework_v311 import (
    V311Decision,
    assess_valuation_confidence_v311,
    decide_v311,
)


PRODUCTION_MODEL_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
PRODUCTION_MODEL_NAME = "GenGe V3.1.1 Production"
PRODUCTION_DECISION = "PROMOTE_CONFIDENCE_GATE_ONLY"
SELL_CONTRACT = "V31_IMMEDIATE_VALUATION_LADDER"
RESEARCH_MODEL_VERSION = "gen_ge_v3_2_candidate_round8_round9_frozen"
PRODUCTION_POLICY_SOURCE = "gen_ge_v3_1_1_confidence_gate_only_round8_round9_validated"
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


def decide_production(data: Mapping[str, Any]) -> V311Decision:
    """Apply the validated Round-8/9 Confidence Gate with immediate V3.1 SELL."""
    return decide_v311(data)


def production_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    decision = decide_production(data)
    confidence = assess_valuation_confidence_v311(data)
    payload = decision.as_dict()
    payload.update(
        {
            "production_model_version": PRODUCTION_MODEL_VERSION,
            "production_model_name": PRODUCTION_MODEL_NAME,
            "production_promotion_decision": PRODUCTION_DECISION,
            "production_sell_contract": SELL_CONTRACT,
            "production_policy_source": PRODUCTION_POLICY_SOURCE,
            "research_model_version": RESEARCH_MODEL_VERSION,
            "production_model_frozen": True,
            "valuation_confidence_reason_codes": ";".join(confidence.reason_codes),
        }
    )
    return payload
