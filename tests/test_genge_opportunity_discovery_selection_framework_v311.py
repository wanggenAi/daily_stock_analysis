from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.selection_framework_v31 import SCORE_WEIGHTS
from src.strategies.genge_opportunity_discovery.selection_framework_v311 import (
    ValuationConfidence,
    assess_valuation_confidence_v311,
    decide_v311,
)


def complete_v311_row(*, current: float = 120.0, neutral: float = 100.0) -> dict:
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
        "v31_falsification_status": "PASS",
        "v31_margin_of_safety_status": "PASS",
        "v31_cagr_attractiveness_status": "PASS",
        "v31_pessimistic_loss_status": "PASS",
        "v31_portfolio_exposure_status": "PASS",
        "v31_market_position_status": "PASS",
        # These are exactly the confidence inputs used by frozen Round 8/9.
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


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({}, ValuationConfidence.HIGH),
        ({"normalized_earnings_observation_count": 3}, ValuationConfidence.MEDIUM),
        ({"deduct_profit_quality_factor": 0.70}, ValuationConfidence.MEDIUM),
        ({"cash_conversion_ratio": 0.70}, ValuationConfidence.MEDIUM),
        ({"realistic_growth_four_report_range": 0.12}, ValuationConfidence.MEDIUM),
        ({"v31_realistic_profit_cagr": 0.30}, ValuationConfidence.MEDIUM),
        ({"normalized_earnings_observation_count": 2}, ValuationConfidence.LOW),
        ({"deduct_profit_quality_factor": 0.49}, ValuationConfidence.LOW),
        ({"cash_conversion_ratio": 0.0}, ValuationConfidence.LOW),
        ({"realistic_growth_four_report_range": 0.16}, ValuationConfidence.LOW),
        ({"implied_growth_status": "IMPLIED_ABOVE_SEARCH_RANGE"}, ValuationConfidence.LOW),
        ({"v31_neutral_value": None}, ValuationConfidence.INVALID),
        ({"v31_normalized_profit": None}, ValuationConfidence.INVALID),
        ({"v31_market_implied_profit_cagr": None}, ValuationConfidence.INVALID),
    ],
)
def test_v311_confidence_matches_frozen_round8_round9_thresholds(updates: dict, expected: ValuationConfidence) -> None:
    row = complete_v311_row()
    row.update(updates)
    assert assess_valuation_confidence_v311(row).level is expected


def test_missing_round8_quality_evidence_is_low_not_silently_high() -> None:
    row = complete_v311_row()
    row.pop("normalized_earnings_observation_count")
    row.pop("deduct_profit_quality_factor")
    row.pop("cash_conversion_ratio")
    assert assess_valuation_confidence_v311(row).level is ValuationConfidence.LOW
    assert decide_v311(row).action == "HOLD_REVIEW"


def test_v32_only_extra_review_fields_do_not_change_v311_confidence() -> None:
    row = complete_v311_row()
    baseline = assess_valuation_confidence_v311(row)
    row.update(
        {
            "valuation_model_execution_state": "NOT_EXECUTED",
            "financial_review_status": "FAIL",
            "valuation_diagnostic_status": "FAIL",
            "valuation_routing_confidence": 0.01,
            "earnings_quality_confidence": "INVALID",
        }
    )
    assert assess_valuation_confidence_v311(row) == baseline


def test_low_or_invalid_confidence_only_blocks_mechanical_valuation_action() -> None:
    sell = complete_v311_row(current=150.0)
    sell["cash_conversion_ratio"] = -0.1
    assert decide_v311(sell).action == "HOLD_REVIEW"

    buy = complete_v311_row(current=70.0)
    buy["v32_has_position"] = False
    buy["cash_conversion_ratio"] = -0.1
    assert decide_v311(buy).action == "HOLD_REVIEW"


def test_medium_and_high_keep_immediate_v31_sell() -> None:
    high = complete_v311_row(current=150.0)
    assert decide_v311(high).action == "REDUCE_50"

    medium = complete_v311_row(current=150.0)
    medium["cash_conversion_ratio"] = 0.70
    decision = decide_v311(medium)
    assert decision.valuation_confidence is ValuationConfidence.MEDIUM
    assert decision.action == "REDUCE_50"


def test_hard_gate_failure_overrides_invalid_confidence() -> None:
    row = complete_v311_row()
    row["v31_neutral_value"] = None
    row["v31_moat_status"] = "FAIL"
    decision = decide_v311(row)
    assert decision.action == "EXIT"
    assert decision.target_position_fraction == 0.0


def test_cost_basis_cannot_change_v311_sell_decision() -> None:
    low_cost = complete_v311_row(current=180.0)
    low_cost["personal_cost_basis"] = 10.0
    high_cost = dict(low_cost)
    high_cost["personal_cost_basis"] = 300.0
    assert decide_v311(low_cost) == decide_v311(high_cost)


def test_pit_future_financial_date_is_invalid() -> None:
    row = complete_v311_row()
    row["date"] = "2026-08-20"
    row["fund_available_date"] = "2026-08-21"
    assessment = assess_valuation_confidence_v311(row)
    assert assessment.level is ValuationConfidence.INVALID
    assert "FUND_AVAILABLE_AFTER_DECISION_DATE" in assessment.reason_codes
