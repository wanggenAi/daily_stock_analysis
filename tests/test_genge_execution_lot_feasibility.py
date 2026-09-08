from __future__ import annotations

from src.strategies.genge_opportunity_discovery import execution_lot_feasibility as audit


def test_main_board_requires_100_share_multiples():
    row = {
        "board": "SSE_MAIN",
        "entry_low": 29.52,
        "entry_high": 29.76,
        "max_buy_price": 29.76,
        "risk_budget_initial_position_pct": 0.62,
        "risk_budget_max_position_pct": 1.0,
    }
    result = audit.audit_execution_row(row, portfolio_capital=250000)
    assert result["minimum_buy_quantity"] == 100
    assert result["buy_quantity_increment"] == 100
    assert result["lot_feasibility_status"] == "NO_LOT_FEASIBLE_WITHIN_MAX_POSITION_CAP"
    assert result["max_budget_legal_quantity"] == 0


def test_star_minimum_200_then_one_share_increment():
    row = {
        "board": "STAR",
        "entry_low": 10.0,
        "max_buy_price": 10.0,
        "risk_budget_initial_position_pct": 1.0,
        "risk_budget_max_position_pct": 2.0,
    }
    result = audit.audit_execution_row(row, portfolio_capital=250000)
    assert result["minimum_buy_quantity"] == 200
    assert result["buy_quantity_increment"] == 1
    assert result["initial_budget_legal_quantity"] == 250
    assert result["max_budget_legal_quantity"] == 500
    assert result["lot_feasibility_status"] == "LOT_FEASIBLE_WITHIN_INITIAL_CAP"


def test_chinext_keeps_100_share_multiple():
    row = {
        "board": "CHINEXT",
        "entry_low": 10.0,
        "max_buy_price": 10.0,
        "risk_budget_initial_position_pct": 1.0,
        "risk_budget_max_position_pct": 2.0,
    }
    result = audit.audit_execution_row(row, portfolio_capital=250000)
    assert result["minimum_buy_quantity"] == 100
    assert result["buy_quantity_increment"] == 100
    assert result["initial_budget_legal_quantity"] == 200
    assert result["max_budget_legal_quantity"] == 500


def test_no_portfolio_capital_reports_thresholds_without_forcing_order():
    row = {
        "board": "SZSE_MAIN",
        "entry_low": 20.0,
        "max_buy_price": 21.0,
        "risk_budget_initial_position_pct": 1.0,
        "risk_budget_max_position_pct": 2.0,
    }
    result = audit.audit_execution_row(row)
    assert result["lot_feasibility_status"] == "LEGAL_MIN_ORDER_RULE_KNOWN"
    assert result["minimum_order_notional_max_price"] == 2100.0
    assert result["required_capital_for_initial_min_order"] == 210000.0
    assert result["required_capital_for_max_min_order"] == 105000.0
    assert result["initial_budget_legal_quantity"] == ""


def test_reduce_25_on_200_shares_defers_instead_of_rounding_up():
    result = audit.reduction_plan_for_action("REDUCE_25", 200, lot_size=100)
    assert result is not None
    assert result["target_reduction_shares"] == 50
    assert result["executable_reduction_shares"] == 0
    assert result["deferred_reduction_shares"] == 50
    assert result["status"] == "EXECUTION_DEFERRED_LOT_SIZE"
    assert result["reason"] == "LOT_SIZE_CONSTRAINT"
    assert result["rounding_policy"] == "FLOOR_ONLY_NEVER_UP"
    assert result["no_auto_trade"] is True


def test_reduce_25_on_500_shares_executes_only_one_lot_and_defers_25():
    result = audit.reduction_plan_for_action("REDUCE_25", 500, lot_size=100)
    assert result is not None
    assert result["target_reduction_shares"] == 125
    assert result["executable_reduction_shares"] == 100
    assert result["deferred_reduction_shares"] == 25
    assert result["status"] == "EXECUTION_PARTIAL_LOT_SIZE"
    assert result["executable_reduction_shares"] <= result["target_reduction_shares"]


def test_preexisting_odd_lot_can_be_sold_whole_but_not_split():
    result = audit.reduction_plan_for_action("REDUCE_25", 250, lot_size=100)
    assert result is not None
    assert result["target_reduction_shares"] == 62
    assert result["preexisting_odd_lot_shares"] == 50
    assert result["executable_reduction_shares"] == 50
    assert result["deferred_reduction_shares"] == 12
    assert result["status"] == "EXECUTION_PARTIAL_LOT_SIZE"


def test_non_percentage_reduce_action_does_not_invent_target():
    assert audit.reduction_plan_for_action("REDUCE", 200, lot_size=100) is None
    assert audit.reduction_plan_for_action("HOLD", 200, lot_size=100) is None
