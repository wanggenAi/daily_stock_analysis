from __future__ import annotations

from src.strategies.genge_opportunity_discovery.selection_framework_v31 import SCORE_WEIGHTS
from src.strategies.genge_opportunity_discovery.selection_framework_v32 import (
    ValuationConfidence,
    assess_valuation_confidence,
    decide_v32,
)


def complete_row(*, current: float = 120.0, neutral: float = 100.0) -> dict:
    row = {
        "code": "600000",
        "v31_candidate_class": "A1",
        "v31_normalized_profit": 10.0,
        "v31_normalized_profit_method": "PIT_MEDIAN",
        "v31_pessimistic_value": 70.0,
        "v31_neutral_value": neutral,
        "v31_optimistic_value": 150.0,
        "v31_extreme_stress_value": 50.0,
        "v31_current_price": current,
        "v31_market_implied_profit_cagr": 0.12,
        "v31_realistic_profit_cagr": 0.15,
        "v31_expectation_gap_pct": 0.03,
        "v31_expectation_gap_thesis": "market underestimates durable demand",
        "v31_risk_adjusted_3y_cagr": 0.10,
        "v31_potential_max_fundamental_loss_pct": -0.30,
        "v31_why_can_buy": "quality and expectation gap",
        "v31_strongest_bear_case": "demand fades",
        "v31_falsification_condition": "moat weakens",
        "v31_buy_condition_quality": "PASS",
        "v31_buy_condition_expectation_gap": "PASS",
        "v31_buy_condition_valuation": "PASS",
        "v31_buy_condition_risk_reward": "PASS",
        "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
        "financial_review_status": "OK",
        "valuation_diagnostic_status": "OK",
        "earnings_quality_confidence": "HIGH",
        "valuation_routing_confidence": 0.90,
        "normalized_earnings_observation_count": 4,
        "deduct_profit_quality_factor": 0.90,
        "cash_conversion_ratio": 0.95,
        "realistic_growth_four_report_range": 0.05,
        "implied_growth_status": "SOLVED",
        "v32_has_position": True,
    }
    for gate in (
        "predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity"
    ):
        row[f"v31_{gate}_status"] = "PASS"
    for name, maximum in SCORE_WEIGHTS.items():
        row[f"v31_score_{name}"] = maximum
    return row


def test_low_confidence_blocks_mechanical_buy_and_sell() -> None:
    sell = complete_row(current=150.0)
    sell["cash_conversion_ratio"] = -0.1
    decision = decide_v32(sell)
    assert decision.action == "HOLD_REVIEW"
    assert decision.valuation_confidence is ValuationConfidence.LOW

    buy = complete_row(current=70.0)
    buy["v32_has_position"] = False
    buy["cash_conversion_ratio"] = -0.1
    assert decide_v32(buy).action == "HOLD_REVIEW"


def test_invalid_inputs_block_mechanical_valuation_action() -> None:
    row = complete_row()
    row["v31_neutral_value"] = None
    confidence = assess_valuation_confidence(row)
    assert confidence.level is ValuationConfidence.INVALID
    assert decide_v32(row).action == "HOLD_REVIEW"


def test_hard_gate_failure_overrides_invalid_confidence_and_exits() -> None:
    row = complete_row()
    row["v31_neutral_value"] = None
    row["v31_moat_status"] = "FAIL"
    decision = decide_v32(row)
    assert decision.action == "EXIT"
    assert decision.target_position_fraction == 0.0


def test_sell_requires_two_consecutive_confirmations() -> None:
    row = complete_row(current=150.0)
    first = decide_v32(row)
    assert first.action == "HOLD_REVIEW"
    assert first.sell_confirmation_count == 1

    row["v32_prior_sell_confirmation_count"] = first.sell_confirmation_count
    second = decide_v32(row)
    assert second.action == "REDUCE_50"
    assert second.target_position_fraction == 0.50


def test_gate_only_variant_keeps_v31_immediate_sell_contract() -> None:
    decision = decide_v32(complete_row(current=150.0), require_sell_confirmation=False)
    assert decision.action == "REDUCE_50"


def test_cost_basis_is_ignored() -> None:
    cheap_cost = complete_row(current=180.0)
    cheap_cost["personal_cost_basis"] = 20.0
    expensive_cost = dict(cheap_cost)
    expensive_cost["personal_cost_basis"] = 300.0
    assert decide_v32(cheap_cost) == decide_v32(expensive_cost)
