from __future__ import annotations

from src.strategies.genge_opportunity_discovery import execution_lot_feasibility as policy


def execution(**updates):
    row = {
        "code": "603369",
        "stock_name": "今世缘",
        "entry_low": "29.52",
        "entry_high": "29.76",
        "max_buy_price": "29.76",
        "risk_budget_initial_position_pct": "0.62",
        "risk_budget_max_position_pct": "1.0",
    }
    row.update(updates)
    return row


def strict(**updates):
    row = {"code": "603369", "stock_name": "今世缘", "board": "SSE_MAIN"}
    row.update(updates)
    return row


def test_current_main_board_plan_has_no_legal_lot_inside_250k_max_cap():
    result = policy.audit_execution_row(
        execution(), strict(), portfolio_capital=250_000.0,
    )

    assert result["minimum_buy_quantity"] == 100
    assert result["buy_quantity_increment"] == 100
    assert result["minimum_order_notional_at_entry_low"] == 2952.0
    assert result["minimum_order_notional_at_max_buy_price"] == 2976.0
    assert result["initial_budget_amount"] == 1550.0
    assert result["max_budget_amount"] == 2500.0
    assert result["initial_feasible_quantity_at_entry_low"] == 0
    assert result["max_feasible_quantity_at_entry_low"] == 0
    assert result["execution_lot_feasibility_status"] == "NO_LOT_FEASIBLE_WITHIN_MAX_POSITION_CAP"
    assert result["formal_signal_changed"] is False
    assert result["automatic_order_allowed"] is False


def test_required_portfolio_capital_is_reported_without_user_capital():
    result = policy.audit_execution_row(
        execution(), strict(), portfolio_capital=None,
    )

    assert result["minimum_portfolio_capital_for_max_budget_at_entry_low"] == 295200.0
    assert result["minimum_portfolio_capital_for_max_budget_at_max_buy_price"] == 297600.0
    assert result["execution_lot_feasibility_status"] == "CAPITAL_NOT_SUPPLIED"


def test_max_cap_support_does_not_override_smaller_initial_budget():
    result = policy.audit_execution_row(
        execution(), strict(), portfolio_capital=300_000.0,
    )

    assert result["initial_budget_amount"] == 1860.0
    assert result["max_budget_amount"] == 3000.0
    assert result["initial_band_feasibility"] == "NO_ENTRY_BAND_LOT_FEASIBLE"
    assert result["max_band_feasibility"] == "FULL_ENTRY_BAND_LOT_FEASIBLE"
    assert result["execution_lot_feasibility_status"] == "INITIAL_BUDGET_NO_LOT_MAX_CAP_CAN_SUPPORT"


def test_main_board_full_band_becomes_feasible_only_inside_initial_budget():
    result = policy.audit_execution_row(
        execution(), strict(), portfolio_capital=500_000.0,
    )

    assert result["initial_budget_amount"] == 3100.0
    assert result["initial_feasible_quantity_at_max_buy_price"] == 100
    assert result["execution_lot_feasibility_status"] == "FULL_ENTRY_BAND_FEASIBLE_WITHIN_INITIAL_BUDGET"


def test_star_uses_200_share_minimum_and_one_share_increment():
    result = policy.audit_execution_row(
        execution(
            code="688001",
            stock_name="example",
            entry_low="10.00",
            max_buy_price="10.00",
            risk_budget_initial_position_pct="1.0",
            risk_budget_max_position_pct="1.0",
        ),
        strict(code="688001", stock_name="example", board="STAR"),
        portfolio_capital=205_000.0,
    )

    assert result["minimum_buy_quantity"] == 200
    assert result["buy_quantity_increment"] == 1
    assert result["initial_feasible_quantity_at_max_buy_price"] == 205
    assert result["execution_lot_feasibility_status"] == "FULL_ENTRY_BAND_FEASIBLE_WITHIN_INITIAL_BUDGET"


def test_unknown_board_fails_closed():
    result = policy.audit_execution_row(
        execution(), strict(board="UNKNOWN"), portfolio_capital=1_000_000.0,
    )

    assert result["execution_lot_feasibility_status"] == "LOT_RULE_OR_PRICE_UNKNOWN"
    assert result["automatic_order_allowed"] is False
