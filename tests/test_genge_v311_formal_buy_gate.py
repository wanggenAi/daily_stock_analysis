from dataclasses import replace

from src.strategies.genge_opportunity_discovery.production_model import (
    FORMAL_BUY_MAX_PRICE_TO_NEUTRAL,
    _apply_formal_buy_gate,
)
from src.strategies.genge_opportunity_discovery.selection_framework_v311 import (
    V311Decision,
    ValuationConfidence,
)


def _buy_decision(*, confidence=ValuationConfidence.HIGH, ratio=0.80):
    return V311Decision(
        action="BUY",
        target_position_fraction=1.0,
        valuation_confidence=confidence,
        reason_codes=("V31_BUY_GATES_PASS",),
        normalized_earnings=1.0,
        realistic_growth=0.10,
        market_implied_growth=0.05,
        expectation_gap=0.05,
        neutral_value=100.0,
        current_price=100.0 * ratio,
        price_to_neutral=ratio,
    )


def test_formal_buy_requires_high_confidence_and_twenty_percent_discount():
    decision = _apply_formal_buy_gate({}, _buy_decision(ratio=0.80))
    assert FORMAL_BUY_MAX_PRICE_TO_NEUTRAL == 0.80
    assert decision.action == "BUY"
    assert "BUY_VALUATION_CONFIDENCE_HIGH" in decision.reason_codes
    assert "PRICE_TO_NEUTRAL_AT_OR_BELOW_0_80" in decision.reason_codes


def test_formal_buy_blocks_price_near_base_value_even_when_under_old_085_threshold():
    decision = _apply_formal_buy_gate({}, _buy_decision(ratio=0.81))
    assert decision.action == "WAIT"
    assert decision.target_position_fraction == 0.0
    assert "BUY_MARGIN_OF_SAFETY_INSUFFICIENT" in decision.reason_codes
    assert "PRICE_TOO_CLOSE_TO_BASE_VALUE" in decision.reason_codes


def test_formal_buy_blocks_medium_confidence_even_at_large_discount():
    decision = _apply_formal_buy_gate(
        {}, _buy_decision(confidence=ValuationConfidence.MEDIUM, ratio=0.70)
    )
    assert decision.action == "WAIT"
    assert "BUY_VALUATION_CONFIDENCE_NOT_HIGH" in decision.reason_codes


def test_core_pool_or_candidate_quality_never_confers_buy_privilege_to_existing_position():
    decision = _apply_formal_buy_gate(
        {"v311_has_position": True}, _buy_decision(ratio=0.70)
    )
    assert decision.action == "HOLD"
    assert "CORE_POOL_CONFERS_NO_BUY_PRIVILEGE" in decision.reason_codes
    assert "EXISTING_POSITION_NOT_CANDIDATE_BUY" in decision.reason_codes


def test_non_buy_actions_are_not_changed_by_buy_gate():
    exit_decision = replace(_buy_decision(ratio=0.70), action="EXIT", target_position_fraction=0.0)
    assert _apply_formal_buy_gate({}, exit_decision) is exit_decision

    reduce_decision = replace(
        _buy_decision(ratio=1.30), action="REDUCE_25", target_position_fraction=0.75
    )
    assert _apply_formal_buy_gate({"v311_has_position": True}, reduce_decision) is reduce_decision
