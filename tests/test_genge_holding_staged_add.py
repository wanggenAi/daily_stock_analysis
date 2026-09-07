from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import _plan
from src.strategies.genge_opportunity_discovery.production_model import (
    HOLDING_ADD_MAX_LOTS,
    HOLDING_ADD_MAX_PRICE_TO_NEUTRAL,
    decide_production,
    production_payload,
)


def _holding(**overrides):
    data = {
        "code": "603993",
        "v311_has_position": True,
        "holding_status": "HELD",
        "confirmed_quantity": 800,
        "v31_current_price": 18.0,
        "v31_neutral_value": 28.0,
        "v31_normalized_profit": 2.2,
        "v31_realistic_profit_cagr": 0.10,
        "v31_market_implied_profit_cagr": 0.08,
        "normalized_earnings_observation_count": 4,
        "deduct_profit_quality_factor": 0.90,
        "cash_conversion_ratio": 1.05,
        "realistic_growth_four_report_range": 0.05,
        "implied_growth_status": "SOLVED",
        "v311_expectation_input_status": "READY",
        "price_date_verification_status": "VERIFIED",
        "price_mapping_status": "OK",
    }
    data.update(overrides)
    return data


def test_existing_high_confidence_deep_value_holding_gets_staged_add():
    decision = decide_production(_holding())
    assert decision.action == "ADD"
    assert decision.valuation_confidence.value == "HIGH"
    assert "EXISTING_HOLDING_STAGED_ADD" in decision.reason_codes
    assert "STAGED_ADD_CAP_ONE_LOT" in decision.reason_codes


def test_exact_a_level_margin_boundary_is_eligible():
    decision = decide_production(_holding(v31_current_price=21.0, v31_neutral_value=28.0))
    assert HOLDING_ADD_MAX_PRICE_TO_NEUTRAL == pytest.approx(0.75)
    assert decision.action == "ADD"


def test_price_just_above_a_level_margin_stays_hold():
    decision = decide_production(_holding(v31_current_price=21.03, v31_neutral_value=28.0))
    assert decision.price_to_neutral > 0.75
    assert decision.action == "HOLD"


def test_medium_confidence_does_not_add():
    decision = decide_production(_holding(normalized_earnings_observation_count=3))
    assert decision.valuation_confidence.value == "MEDIUM"
    assert decision.action == "HOLD"


def test_low_confidence_does_not_add():
    decision = decide_production(_holding(normalized_earnings_observation_count=2))
    assert decision.valuation_confidence.value == "LOW"
    assert decision.action == "HOLD_REVIEW"


def test_explicit_hard_gate_failure_can_never_add():
    decision = decide_production(_holding(v31_moat_status="FAIL"))
    assert decision.action == "EXIT"
    assert "HARD_GATE_FAIL" in decision.reason_codes


def test_unknown_hard_gates_are_retained_not_promoted_to_pass():
    payload = production_payload(_holding())
    assert payload["production_action"] == "ADD"
    assert payload["holding_add_unknown_is_pass"] is False
    assert "moat" in payload["holding_add_hard_gate_unknowns"]
    assert payload["holding_add_hard_gate_failures"] == ""
    assert "HARD_GATE_UNKNOWNS_RETAINED" in payload["reason_codes"]


def test_new_candidate_without_position_can_never_use_holding_add_path():
    data = _holding(
        v311_has_position=False,
        holding_status="",
        confirmed_quantity=0,
    )
    decision = decide_production(data)
    assert decision.action == "WAIT"
    assert "EXISTING_HOLDING_STAGED_ADD" not in decision.reason_codes


@pytest.mark.parametrize(
    "field,value",
    [
        ("v311_expectation_input_status", "INPUT_INCOMPLETE"),
        ("price_date_verification_status", "UNVERIFIED"),
        ("price_mapping_status", "MISSING"),
    ],
)
def test_incomplete_or_unverified_same_run_inputs_block_add(field, value):
    decision = decide_production(_holding(**{field: value}))
    assert decision.action == "HOLD"


def test_typed_insurer_never_enters_generic_holding_add_path():
    decision = decide_production(
        {
            "code": "601318",
            "v311_has_position": True,
            "holding_status": "HELD",
            "confirmed_quantity": 300,
            "v31_current_price": 56.5,
            "price_date": "2026-09-07",
            "date": "2026-09-07",
        }
    )
    assert decision.action != "ADD"


def test_noncheap_existing_holding_never_adds():
    decision = decide_production(_holding(code="600406", v31_current_price=22.63, v31_neutral_value=17.46))
    assert decision.action != "ADD"


def test_add_payload_declares_separate_non_buy_contract_and_one_lot_cap():
    payload = production_payload(_holding())
    assert payload["production_action"] == "ADD"
    assert payload["holding_add_is_formal_buy"] is False
    assert payload["holding_add_existing_position_only"] is True
    assert payload["holding_add_requires_high_confidence"] is True
    assert payload["holding_add_max_lots"] == HOLDING_ADD_MAX_LOTS == 1
    assert payload["holding_add_no_auto_trade"] is True


def _capital():
    return {
        "status": "READY",
        "planning_cash_cny": 70000.0,
        "no_auto_trade": True,
        "planner": {
            "max_deployment_ratio": 0.70,
            "max_single_name_ratio_of_available_cash": 0.20,
            "max_names": 5,
            "first_tranche_ratio": 0.50,
            "second_tranche_discount_pct": 0.02,
        },
    }


def _market(allow=True):
    return {"allow_new_buy": allow, "position_multiplier": 0.50}


def test_dashboard_caps_authorized_holding_add_to_exactly_one_lot():
    plan = _plan(
        _capital(),
        _market(),
        [{"code": "603993", "name": "洛阳钼业", "formal_action": "ADD", "current_price": 18.33}],
        {"buy_now": [], "wait_price": []},
    )
    op = plan["operations"][0]
    assert op["planned_shares"] == 100
    assert op["first_tranche_shares"] == 100
    assert op["second_tranche_shares"] == 0
    assert op["estimated_cash_cny"] == pytest.approx(1833.0)
    assert op["no_auto_trade"] is True
    assert op["automatic_order_allowed"] is False


def test_dashboard_one_lot_cap_does_not_reduce_authorized_terminal_buy_sizing():
    plan = _plan(
        _capital(),
        _market(),
        [],
        {
            "buy_now": [
                {
                    "code": "600000",
                    "name": "测试新股",
                    "current_price": 10.0,
                    "formal_buy_authorized": True,
                    "neutral_value": 20.0,
                    "buy_ratio": 0.80,
                }
            ],
            "wait_price": [],
        },
    )
    assert plan["operations"][0]["action"] == "BUY"
    assert plan["operations"][0]["planned_shares"] > 100


def test_market_buy_block_also_blocks_holding_add_cash_deployment():
    plan = _plan(
        _capital(),
        _market(False),
        [{"code": "603993", "name": "洛阳钼业", "formal_action": "ADD", "current_price": 18.33}],
        {"buy_now": [], "wait_price": []},
    )
    assert plan["planned_immediate_cash_cny"] == 0
    assert plan["operations"][0]["planned_shares"] == 0
