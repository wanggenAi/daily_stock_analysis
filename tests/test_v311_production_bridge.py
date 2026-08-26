"""Tests for the V3.1.1 discovery-to-production bridge."""

from src.strategies.genge_opportunity_discovery.v311_production_bridge import (
    add_holdings_to_source_evidence,
    join_selected_candidates_with_evidence,
    merge_source_and_current_rows,
)


def test_bridge_preserves_qualitative_evidence_and_overlays_fresh_inputs() -> None:
    source = {
        "code": "600000.SH",
        "stock_name": "bridge-fixture",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
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
    assert row["v31_long_term_demand_status"] == "PASS"
    assert row["v31_moat_status"] == "PASS"
    assert row["v31_current_price"] == 80.0
    assert row["v31_neutral_value"] == 100.0
    assert row["v311_production_bridge"] == "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT"


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
    assert "v31_long_term_demand_status" not in row
    assert "v31_moat_status" not in row


def test_top5_selects_codes_while_same_run_audit_supplies_full_v31_evidence() -> None:
    candidates = [
        {
            "code": "600036",
            "candidate_rank": "1",
            "candidate_action": "RESEARCH_WATCH",
            "stock_name": "top5-name",
            "v31_moat_status": "",
        }
    ]
    evidence = [
        {
            "code": "600036.SH",
            "stock_name": "evidence-name",
            "v31_predictability_status": "PASS",
            "v31_long_term_demand_status": "PASS",
            "v31_moat_status": "PASS",
            "v31_financial_safety_status": "PASS",
            "v31_earnings_authenticity_status": "PASS",
            "v31_score_total": "88",
            "production_action": "STALE_BUY",
        },
        {"code": "601899", "v31_predictability_status": "PASS"},
    ]

    rows = join_selected_candidates_with_evidence(candidates, evidence)

    assert len(rows) == 1
    row = rows[0]
    assert row["code"] == "600036"
    assert row["candidate_rank"] == "1"
    assert row["stock_name"] == "top5-name"
    assert row["v31_predictability_status"] == "PASS"
    assert row["v31_long_term_demand_status"] == "PASS"
    assert row["v31_moat_status"] == "PASS"
    assert row["v31_financial_safety_status"] == "PASS"
    assert row["v31_earnings_authenticity_status"] == "PASS"
    assert row["v311_source_scope"] == "CANDIDATE"
    assert row["v311_same_run_evidence_joined"] is True
    assert "production_action" not in row


def test_evidence_join_never_introduces_unselected_security() -> None:
    candidates = [{"code": "600036", "candidate_rank": "1"}]
    evidence = [
        {"code": "600036", "v31_moat_status": "PASS"},
        {"code": "601899", "v31_moat_status": "PASS"},
    ]

    rows = join_selected_candidates_with_evidence(candidates, evidence)

    assert [row["code"] for row in rows] == ["600036"]


def test_confirmed_holding_is_added_and_receives_same_run_evidence_when_available() -> None:
    candidates = join_selected_candidates_with_evidence(
        [{"code": "600036", "candidate_rank": "1"}],
        [{"code": "600036", "v31_moat_status": "PASS"}],
    )
    holdings = [
        {
            "code": "601899",
            "stock_name": "confirmed-holding",
            "confirmed_quantity": "1000",
            "holding_evidence_date": "2026-08-27",
        }
    ]
    evidence = [
        {
            "code": "601899.SH",
            "v31_long_term_demand_status": "PASS",
            "v31_moat_status": "PASS",
        }
    ]

    rows = add_holdings_to_source_evidence(candidates, holdings, evidence)
    holding = next(row for row in rows if row["code"] == "601899")

    assert holding["v311_source_scope"] == "HOLDING"
    assert holding["v311_same_run_evidence_joined"] is True
    assert holding["confirmed_quantity"] == "1000"
    assert holding["v31_moat_status"] == "PASS"


def test_confirmed_holding_without_rich_evidence_is_kept_but_evidence_is_not_fabricated() -> None:
    rows = add_holdings_to_source_evidence(
        [],
        [{"code": "601899", "confirmed_quantity": "1000"}],
        [],
    )

    assert len(rows) == 1
    assert rows[0]["code"] == "601899"
    assert rows[0]["v311_source_scope"] == "HOLDING"
    assert rows[0]["v311_same_run_evidence_joined"] is False
    assert "v31_moat_status" not in rows[0]


def test_fresh_current_row_for_explicit_holding_is_not_dropped() -> None:
    source = [
        {
            "code": "601899",
            "v311_source_scope": "HOLDING",
            "confirmed_quantity": "1000",
        }
    ]
    current = [
        {
            "code": "601899",
            "v31_current_price": 25.0,
            "v31_neutral_value": 30.0,
            "v311_expectation_input_status": "READY",
        }
    ]

    rows = merge_source_and_current_rows(source, current)

    assert len(rows) == 1
    assert rows[0]["v31_current_price"] == 25.0
    assert rows[0]["v31_neutral_value"] == 30.0
    assert rows[0]["confirmed_quantity"] == "1000"
