"""Tests for the V3.1.1 discovery-to-production bridge."""

from src.strategies.genge_opportunity_discovery.v311_production_bridge import (
    merge_source_and_current_rows,
)


def test_bridge_preserves_qualitative_evidence_and_overlays_fresh_inputs() -> None:
    source = {
        "code": "600000.SH",
        "stock_name": "bridge-fixture",
        "v31_long_term_demand": "PASS",
        "v31_hard_logic": "PASS",
        "v31_moat": "PASS",
        "v31_current_price": "88.0",
        "v31_neutral_value": "120.0",
    }
    current = {
        "code": "600000",
        "v31_current_price": 80.0,
        "v31_neutral_value": 100.0,
        "v311_expectation_input_status": "READY",
    }

    row = merge_source_and_current_rows([source], [current])[0]

    assert row["code"] == "600000"
    assert row["v31_long_term_demand"] == "PASS"
    assert row["v31_hard_logic"] == "PASS"
    assert row["v31_moat"] == "PASS"
    assert row["v31_current_price"] == 80.0
    assert row["v31_neutral_value"] == 100.0
    assert row["v311_production_bridge"] == "SOURCE_EVIDENCE_PLUS_FRESH_STRICT_PIT"


def test_bridge_fails_closed_instead_of_falling_back_to_stale_valuation() -> None:
    source = {
        "code": "000001",
        "v31_current_price": "88.0",
        "v31_normalized_profit": "9.0",
        "v31_neutral_value": "120.0",
    }
    current = {
        "code": "000001",
        "v31_current_price": 80.0,
        "v31_normalized_profit": None,
        "v31_neutral_value": None,
        "v311_expectation_input_status": "HOLD_REVIEW_INPUT_INCOMPLETE",
    }

    row = merge_source_and_current_rows([source], [current])[0]

    assert row["v31_current_price"] == 80.0
    assert row["v31_normalized_profit"] is None
    assert row["v31_neutral_value"] is None


def test_bridge_strips_stale_production_outputs_without_fabricating_evidence() -> None:
    source = {
        "code": "600036",
        "production_action": "BUY",
        "production_model_version": "STALE",
        "valuation_confidence": "HIGH",
        "reason_codes": "STALE",
        "v31_expectation_gap_thesis": "SOURCE_EVIDENCE",
    }
    current = {
        "code": "600036",
        "v31_current_price": 40.0,
        "v31_neutral_value": 50.0,
    }

    row = merge_source_and_current_rows([source], [current])[0]

    assert "production_action" not in row
    assert "production_model_version" not in row
    assert "valuation_confidence" not in row
    assert "reason_codes" not in row
    assert row["v31_expectation_gap_thesis"] == "SOURCE_EVIDENCE"
    assert "v31_long_term_demand" not in row
    assert "v31_moat" not in row
