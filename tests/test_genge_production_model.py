from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery.production_decision_scan import (
    build_decisions,
    read_holdings_markdown,
)
from src.strategies.genge_opportunity_discovery.production_model import (
    ALLOWED_ACTIONS,
    PRODUCTION_MODEL_VERSION,
    production_payload,
)
from tests.test_genge_opportunity_discovery_selection_framework_v32 import complete_row


def test_production_is_gate_only_with_immediate_v31_sell() -> None:
    row = complete_row(current=150.0)
    payload = production_payload(row)
    assert payload["production_model_version"] == PRODUCTION_MODEL_VERSION
    assert payload["production_action"] == "REDUCE_50"
    assert payload["production_sell_contract"] == "V31_IMMEDIATE_VALUATION_LADDER"


def test_production_action_vocabulary_is_complete_and_frozen() -> None:
    assert ALLOWED_ACTIONS == {
        "BUY", "WAIT", "HOLD", "HOLD_NO_ADD", "HOLD_REVIEW",
        "REDUCE_25", "REDUCE_50", "CORE_ONLY", "EXIT",
    }


def test_production_can_emit_every_frozen_action() -> None:
    cases = {
        "BUY": (70.0, False),
        "WAIT": (90.0, False),
        "HOLD": (90.0, True),
        "HOLD_NO_ADD": (110.0, True),
        "REDUCE_25": (125.0, True),
        "REDUCE_50": (145.0, True),
        "CORE_ONLY": (180.0, True),
    }
    observed = set()
    for expected, (price, held) in cases.items():
        row = complete_row(current=price)
        row.update(
            {
                "v31_falsification_status": "PASS",
                "v31_margin_of_safety_status": "PASS",
                "v31_cagr_attractiveness_status": "PASS",
                "v31_pessimistic_loss_status": "PASS",
                "v31_portfolio_exposure_status": "PASS",
                "v31_market_position_status": "PASS",
            }
        )
        row["v32_has_position"] = held
        action = production_payload(row)["production_action"]
        assert action == expected
        observed.add(action)

    review = complete_row(current=90.0)
    review["cash_conversion_ratio"] = -0.1
    observed.add(production_payload(review)["production_action"])
    failed = complete_row(current=90.0)
    failed["v31_moat_status"] = "FAIL"
    observed.add(production_payload(failed)["production_action"])
    assert observed == ALLOWED_ACTIONS


def test_production_low_confidence_is_hold_review() -> None:
    row = complete_row(current=150.0)
    row["cash_conversion_ratio"] = -0.1
    assert production_payload(row)["production_action"] == "HOLD_REVIEW"


def test_holding_cost_is_display_only() -> None:
    candidate = complete_row(current=180.0)
    candidate["code"] = "600000"
    low_cost = {"code": "600000", "display_only_average_cost": "10", "confirmed_quantity": "100"}
    high_cost = {"code": "600000", "display_only_average_cost": "300", "confirmed_quantity": "100"}
    first = build_decisions([candidate], [low_cost])[0]
    second = build_decisions([candidate], [high_cost])[0]
    assert first["production_action"] == second["production_action"] == "CORE_ONLY"
    assert first["cost_basis_used_by_decision"] is False


def test_missing_holding_valuation_is_safe_review() -> None:
    row = build_decisions([], [{"code": "600000", "stock_name": "test", "confirmed_quantity": "100"}])[0]
    assert row["production_action"] == "HOLD_REVIEW"
    assert row["valuation_confidence"] == "INVALID"


def test_parse_current_holdings_contract() -> None:
    path = Path(__file__).resolve().parents[1] / "CURRENT_HOLDINGS.md"
    holdings = read_holdings_markdown(path)
    assert {row["code"] for row in holdings} >= {"603369", "001316", "600276", "600406"}


def test_scanner_preserves_authoritative_candidate_production_decision() -> None:
    row = {
        "code": "600000",
        "production_model_version": "GEN_GE_V3_1_1_PRODUCTION",
        "production_action": "BUY",
        "valuation_confidence": "HIGH",
        "reason_codes": "V31_BUY_GATES_PASS;MARGIN_OF_SAFETY_PASS",
    }
    decision = build_decisions([row])[0]
    assert decision["production_action"] == "BUY"
    assert decision["valuation_confidence"] == "HIGH"


def test_research_only_market_never_enters_production_candidate_output() -> None:
    research_only = {
        "code": "688001",
        "production_model_version": "GEN_GE_V3_1_1_PRODUCTION",
        "production_action": "BUY",
        "valuation_confidence": "HIGH",
    }
    assert build_decisions([research_only]) == []
