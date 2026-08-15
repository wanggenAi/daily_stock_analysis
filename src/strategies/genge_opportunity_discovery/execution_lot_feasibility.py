"""Board-aware legal-order feasibility audit for formal execution plans.

This module is research/reporting only. It never promotes a candidate, changes a
position cap, rounds a budget upward, or submits an order. Formal signal
eligibility remains owned by the existing strict/risk-capped policy.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


BOARD_BUY_RULES = {
    "SSE_MAIN": {"minimum": 100, "increment": 100},
    "SZSE_MAIN": {"minimum": 100, "increment": 100},
    "CHINEXT": {"minimum": 100, "increment": 100},
    "STAR": {"minimum": 200, "increment": 1},
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip().lower() in {"", "nan", "none"}:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def board_buy_rule(board: Any) -> dict[str, int] | None:
    return BOARD_BUY_RULES.get(str(board or "").strip().upper())


def _max_legal_quantity(budget: float, price: float, *, minimum: int, increment: int) -> int:
    if budget <= 0 or price <= 0:
        return 0
    raw = int(math.floor(budget / price))
    if raw < minimum:
        return 0
    if increment == 1:
        return raw
    return (raw // increment) * increment


def audit_execution_row(
    row: Mapping[str, Any], *, portfolio_capital: float | None = None,
) -> dict[str, Any]:
    """Return legal-order feasibility without changing the formal execution row."""

    result = dict(row)
    rule = board_buy_rule(row.get("board"))
    if rule is None:
        result.update({
            "lot_feasibility_status": "UNKNOWN_BOARD",
            "minimum_buy_quantity": "",
            "buy_quantity_increment": "",
            "minimum_order_notional_entry_low": "",
            "minimum_order_notional_max_price": "",
            "required_capital_for_initial_min_order": "",
            "required_capital_for_max_min_order": "",
            "initial_budget_legal_quantity": "",
            "max_budget_legal_quantity": "",
        })
        return result

    entry_low = _safe_float(row.get("entry_low"))
    max_price = _safe_float(row.get("max_buy_price") or row.get("entry_high"))
    initial_pct = _safe_float(row.get("risk_budget_initial_position_pct"))
    max_pct = _safe_float(row.get("risk_budget_max_position_pct"))
    if entry_low is None or max_price is None or entry_low <= 0 or max_price <= 0:
        result.update({
            "lot_feasibility_status": "INVALID_PLAN_PRICE",
            "minimum_buy_quantity": rule["minimum"],
            "buy_quantity_increment": rule["increment"],
        })
        return result

    minimum = rule["minimum"]
    increment = rule["increment"]
    min_entry_notional = round(entry_low * minimum, 2)
    min_max_notional = round(max_price * minimum, 2)
    required_initial = (
        round(min_max_notional / (initial_pct / 100.0), 2)
        if initial_pct is not None and initial_pct > 0 else ""
    )
    required_max = (
        round(min_max_notional / (max_pct / 100.0), 2)
        if max_pct is not None and max_pct > 0 else ""
    )

    status = "LEGAL_MIN_ORDER_RULE_KNOWN"
    initial_qty: int | str = ""
    max_qty: int | str = ""
    if portfolio_capital is not None:
        capital = max(0.0, float(portfolio_capital))
        initial_budget = capital * max(0.0, initial_pct or 0.0) / 100.0
        max_budget = capital * max(0.0, max_pct or 0.0) / 100.0
        initial_qty = _max_legal_quantity(
            initial_budget, max_price, minimum=minimum, increment=increment,
        )
        max_qty = _max_legal_quantity(
            max_budget, max_price, minimum=minimum, increment=increment,
        )
        if max_qty <= 0:
            status = "NO_LOT_FEASIBLE_WITHIN_MAX_POSITION_CAP"
        elif initial_qty <= 0:
            status = "LOT_FEASIBLE_WITHIN_MAX_CAP_NOT_INITIAL_CAP"
        else:
            status = "LOT_FEASIBLE_WITHIN_INITIAL_CAP"

    result.update({
        "lot_feasibility_status": status,
        "minimum_buy_quantity": minimum,
        "buy_quantity_increment": increment,
        "minimum_order_notional_entry_low": min_entry_notional,
        "minimum_order_notional_max_price": min_max_notional,
        "required_capital_for_initial_min_order": required_initial,
        "required_capital_for_max_min_order": required_max,
        "initial_budget_legal_quantity": initial_qty,
        "max_budget_legal_quantity": max_qty,
    })
    return result


def audit_execution_rows(
    rows: list[Mapping[str, Any]], *, portfolio_capital: float | None = None,
) -> list[dict[str, Any]]:
    return [audit_execution_row(row, portfolio_capital=portfolio_capital) for row in rows]
