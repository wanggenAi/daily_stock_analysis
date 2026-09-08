"""Board-aware legal-order feasibility audit for formal execution plans.

This module is research/reporting only. It never promotes a candidate, changes a
position cap, rounds a budget upward, or submits an order. Formal signal
eligibility remains owned by the existing strict/risk-capped policy.

Partial-reduction plans are intentionally *floor only*: an execution adapter may
make a formal reduction more conservative when exchange lot rules make the exact
target impossible, but it must never round the requested reduction upward and
thereby increase risk reduction beyond the Canonical authorization.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any, Mapping


BOARD_BUY_RULES = {
    "SSE_MAIN": {"minimum": 100, "increment": 100},
    "SZSE_MAIN": {"minimum": 100, "increment": 100},
    "CHINEXT": {"minimum": 100, "increment": 100},
    "STAR": {"minimum": 200, "increment": 1},
}
AUDIT_COLUMNS = [
    "code", "stock_name", "board", "execution_action", "preferred_plan",
    "entry_low", "entry_high", "max_buy_price", "risk_budget_initial_position_pct",
    "risk_budget_max_position_pct", "lot_feasibility_status", "minimum_buy_quantity",
    "buy_quantity_increment", "minimum_order_notional_entry_low",
    "minimum_order_notional_max_price", "required_capital_for_initial_min_order",
    "required_capital_for_max_min_order", "initial_budget_legal_quantity",
    "max_budget_legal_quantity",
]
PARTIAL_REDUCTION_ACTION_RE = re.compile(r"^REDUCE_(\d+(?:\.\d+)?)$")


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


def partial_reduction_pct_from_action(action: Any) -> float | None:
    """Parse a bounded percentage from a formal ``REDUCE_<pct>`` action."""

    match = PARTIAL_REDUCTION_ACTION_RE.fullmatch(str(action or "").strip().upper())
    if not match:
        return None
    pct = _safe_float(match.group(1))
    if pct is None or pct <= 0 or pct >= 100:
        return None
    return pct


def _largest_legal_sell_not_above_target(*, quantity: int, target: int, lot_size: int) -> int:
    """Return the largest legal sell quantity not exceeding ``target``.

    For a round-lot holding, the answer is a round-lot multiple. If the current
    holding already contains an odd-lot remainder, that *entire* remainder may be
    included once together with zero or more full lots. We never manufacture a
    new odd lot by splitting a round-lot holding.
    """

    if quantity <= 0 or target <= 0:
        return 0
    odd_lot = quantity % lot_size
    candidates = {(target // lot_size) * lot_size}
    if odd_lot:
        remaining = target - odd_lot
        if remaining >= 0:
            candidates.add(odd_lot + (remaining // lot_size) * lot_size)
    return max(0, min(quantity, max(x for x in candidates if x >= 0)))


def compute_partial_reduction_lot_plan(
    current_quantity: Any,
    reduction_pct: Any,
    *,
    lot_size: int = 100,
) -> dict[str, Any]:
    """Resolve a formal percentage reduction into a conservative legal share plan.

    The target is the mathematical percentage target floored to whole shares.
    The executable quantity is the largest exchange-lot-compatible quantity that
    does not exceed that target. Upward rounding is forbidden by invariant.
    """

    qty_value = _safe_float(current_quantity)
    pct = _safe_float(reduction_pct)
    if qty_value is None or qty_value < 0 or not float(qty_value).is_integer():
        raise ValueError("current_quantity must be a non-negative whole-share quantity")
    if pct is None or pct <= 0 or pct >= 100:
        raise ValueError("reduction_pct must be > 0 and < 100")
    if not isinstance(lot_size, int) or lot_size <= 0:
        raise ValueError("lot_size must be a positive integer")

    quantity = int(qty_value)
    raw_target = quantity * pct / 100.0
    target = min(quantity, max(0, int(math.floor(raw_target + 1e-12))))
    executable = _largest_legal_sell_not_above_target(
        quantity=quantity, target=target, lot_size=lot_size,
    )
    deferred = target - executable

    if target == 0:
        status = "NO_REDUCTION_REQUIRED"
        reason = "TARGET_BELOW_ONE_SHARE"
    elif executable == 0:
        status = "EXECUTION_DEFERRED_LOT_SIZE"
        reason = "LOT_SIZE_CONSTRAINT"
    elif deferred > 0:
        status = "EXECUTION_PARTIAL_LOT_SIZE"
        reason = "LOT_SIZE_CONSTRAINT"
    else:
        status = "EXECUTION_READY"
        reason = "LOT_SIZE_FEASIBLE"

    if not (0 <= executable <= target <= quantity):
        raise AssertionError("partial-reduction quantity invariant violated")
    if executable > target:
        raise AssertionError("partial reduction must never round upward")
    odd_lot = quantity % lot_size
    if executable and executable % lot_size not in {0, odd_lot}:
        raise AssertionError("partial-reduction lot compatibility invariant violated")

    return {
        "status": status,
        "reason": reason,
        "current_quantity": quantity,
        "reduction_pct": pct,
        "raw_target_reduction_shares": raw_target,
        "target_reduction_shares": target,
        "executable_reduction_shares": executable,
        "deferred_reduction_shares": deferred,
        "lot_size": lot_size,
        "preexisting_odd_lot_shares": odd_lot,
        "rounding_policy": "FLOOR_ONLY_NEVER_UP",
        "automatic_order_allowed": False,
        "no_auto_trade": True,
    }


def reduction_plan_for_action(
    action: Any,
    current_quantity: Any,
    *,
    lot_size: int = 100,
) -> dict[str, Any] | None:
    """Return a lot plan only for explicit percentage-reduction formal actions."""

    pct = partial_reduction_pct_from_action(action)
    if pct is None:
        return None
    return compute_partial_reduction_lot_plan(
        current_quantity=current_quantity,
        reduction_pct=pct,
        lot_size=lot_size,
    )


def audit_execution_row(
    row: Mapping[str, Any], *, portfolio_capital: float | None = None,
) -> dict[str, Any]:
    """Return legal-order feasibility without changing the formal execution row."""

    result = dict(row)
    rule = board_buy_rule(row.get("board"))
    if rule is None:
        result.update({
            "lot_feasibility_status": "UNKNOWN_BOARD",
            "minimum_buy_quantity": "", "buy_quantity_increment": "",
            "minimum_order_notional_entry_low": "", "minimum_order_notional_max_price": "",
            "required_capital_for_initial_min_order": "", "required_capital_for_max_min_order": "",
            "initial_budget_legal_quantity": "", "max_budget_legal_quantity": "",
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
        initial_qty = _max_legal_quantity(initial_budget, max_price, minimum=minimum, increment=increment)
        max_qty = _max_legal_quantity(max_budget, max_price, minimum=minimum, increment=increment)
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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_report(report_dir: Path, *, portfolio_capital: float | None = None) -> list[dict[str, Any]]:
    executions = _read_csv(report_dir / "actionable_execution_list.csv")
    strict_rows = {
        str(row.get("code") or "").zfill(6): row
        for row in _read_csv(report_dir / "strict_review_ready.csv")
    }
    joined = []
    for execution in executions:
        code = str(execution.get("code") or "").zfill(6)
        joined.append({**strict_rows.get(code, {}), **execution, "code": code})
    audited = audit_execution_rows(joined, portfolio_capital=portfolio_capital)
    with (report_dir / "execution_lot_feasibility.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in AUDIT_COLUMNS} for row in audited)
    return audited
