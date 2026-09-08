from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.investor_execution_overlay import (
    build_execution_overlay,
)


def _dashboard(*rows, existing=None):
    return {
        "contract_version": "GEN_GE_INVESTOR_DECISION_DASHBOARD_V2",
        "no_auto_trade": True,
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "canonical_snapshot_id": "snapshot-1",
        "stock_portfolio": {"rows": list(rows)},
        "final_operation_table": list(existing or []),
    }


def _holding(qty: int, action: str, code: str = "600406"):
    return {
        "code": code,
        "name": "测试持仓",
        "quantity": qty,
        "formal_action": action,
        "current_price": 20.0,
        "reason_codes": "AUTHORIZED_TEST",
    }


def _sell(payload):
    return [x for x in payload["operations"] if x.get("side") == "SELL"][0]


def test_reduce_25_of_200_defers_instead_of_rounding_up_to_100():
    op = _sell(build_execution_overlay(_dashboard(_holding(200, "REDUCE_25"))))
    assert op["authorized_max_shares"] == 50
    assert op["executable_quantity"] == 0
    assert op["execution_status"] == "DEFER_BOARD_LOT_QUANTIZATION"
    assert op["immediate_execution_eligible"] is False
    assert op["over_authority"] is False


def test_reduce_25_of_400_executes_exactly_one_lot():
    op = _sell(build_execution_overlay(_dashboard(_holding(400, "REDUCE_25"))))
    assert op["authorized_max_shares"] == 100
    assert op["executable_quantity"] == 100
    assert op["immediate_execution_eligible"] is True


def test_partial_sell_always_rounds_down_and_never_exceeds_authority():
    cases = [
        (500, "REDUCE_25", 125, 100),
        (300, "REDUCE_50", 150, 100),
        (700, "REDUCE_25", 175, 100),
        (700, "REDUCE_50", 350, 300),
    ]
    for qty, action, authorized, executable in cases:
        op = _sell(build_execution_overlay(_dashboard(_holding(qty, action))))
        assert op["authorized_max_shares"] == authorized
        assert op["executable_quantity"] == executable
        assert op["executable_quantity"] <= op["authorized_max_shares"]


def test_generic_reduce_is_blocked_because_fraction_is_not_frozen():
    op = _sell(build_execution_overlay(_dashboard(_holding(500, "REDUCE"))))
    assert op["authorized_fraction"] is None
    assert op["executable_quantity"] == 0
    assert op["execution_status"] == "BLOCKED_AMBIGUOUS_REDUCTION_FRACTION"


def test_full_exit_preserves_full_holding_and_flags_odd_lot_review():
    op = _sell(build_execution_overlay(_dashboard(_holding(250, "EXIT"))))
    assert op["authorized_max_shares"] == 250
    assert op["executable_quantity"] == 250
    assert op["odd_lot_full_exit"] is True
    assert op["manual_order_review_required"] is True


def test_existing_add_or_wait_operations_are_preserved():
    existing = [{
        "code": "603993",
        "name": "洛阳钼业",
        "action": "ADD",
        "source": "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD",
        "authorization_proven": True,
        "total_shares": 100,
    }]
    payload = build_execution_overlay(_dashboard(_holding(200, "REDUCE_25"), existing=existing))
    assert any(x.get("code") == "603993" and x.get("action") == "ADD" for x in payload["operations"])
    assert payload["no_auto_trade"] is True
    assert payload["automatic_order_allowed"] is False
    assert payload["formal_action_mutation_allowed"] is False


def test_conflicting_add_and_sell_for_same_code_fails_closed():
    existing = [{
        "code": "600406",
        "action": "ADD",
        "source": "AUTHORIZED_CANONICAL_HOLDING_ACTION",
        "authorization_proven": True,
    }]
    with pytest.raises(ValueError, match="conflicting buy/add and sell authority"):
        build_execution_overlay(_dashboard(_holding(200, "REDUCE_25"), existing=existing))


def test_overlay_refuses_noncanonical_or_auto_trade_dashboard():
    bad = _dashboard(_holding(200, "REDUCE_25"))
    bad["no_auto_trade"] = False
    with pytest.raises(ValueError, match="no-auto-trade"):
        build_execution_overlay(bad)

    bad = _dashboard(_holding(200, "REDUCE_25"))
    bad["formal_action_recomputed"] = True
    with pytest.raises(ValueError, match="recomputed Formal Actions"):
        build_execution_overlay(bad)
