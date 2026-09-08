"""Translate authorized investor decisions into executable share quantities.

This layer is deliberately downstream of investment authority. It never creates
or changes a Formal Action. It only turns already-authorized holding sell actions
and the dashboard's existing capital operations into a unified execution plan.

Partial A-share reductions are rounded *down* to the configured board lot. They
are never rounded up, because doing so could exceed the authorized reduction.
Full EXIT/SELL actions may liquidate the full recorded holding; odd-lot full exits
are flagged for manual order review. No order is ever placed automatically.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_INVESTOR_EXECUTION_OVERLAY_V1"
BOARD_LOT_SIZE = 100
NO_AUTO_TRADE = True
PARTIAL_SELL_FRACTIONS = {"REDUCE_25": 0.25, "REDUCE_50": 0.50}
FULL_EXIT_ACTIONS = frozenset({"EXIT", "SELL"})
SELL_ACTIONS = frozenset({"REDUCE_25", "REDUCE_50", "REDUCE", "EXIT", "SELL"})


def _int(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _holding_rows(dashboard: Mapping[str, Any]) -> list[dict[str, Any]]:
    portfolio = dashboard.get("stock_portfolio") or {}
    rows = portfolio.get("rows") if isinstance(portfolio, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError("dashboard stock_portfolio.rows is required")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _partial_sell_operation(row: Mapping[str, Any], action: str, fraction: float) -> dict[str, Any]:
    quantity = _int(row.get("quantity"))
    if quantity is None:
        return {
            "code": _code(row.get("code")),
            "name": row.get("name") or "",
            "side": "SELL",
            "action": action,
            "formal_action": action,
            "source": "AUTHORIZED_CANONICAL_HOLDING_SELL",
            "authorization_proven": True,
            "authorized_fraction": fraction,
            "authorized_max_shares": None,
            "executable_quantity": 0,
            "board_lot_size": BOARD_LOT_SIZE,
            "execution_status": "BLOCKED_HOLDING_QUANTITY_UNKNOWN",
            "immediate_execution_eligible": False,
            "manual_order_review_required": True,
            "over_authority": False,
            "no_auto_trade": True,
        }
    authorized = int(quantity * fraction)
    executable = (authorized // BOARD_LOT_SIZE) * BOARD_LOT_SIZE
    if executable > authorized:
        raise AssertionError("sell quantity exceeded authorized reduction")
    if authorized <= 0:
        status = "BLOCKED_ZERO_AUTHORIZED_SHARES"
    elif executable <= 0:
        status = "DEFER_BOARD_LOT_QUANTIZATION"
    else:
        status = "EXECUTION_REVIEW_REQUIRED"
    return {
        "code": _code(row.get("code")),
        "name": row.get("name") or "",
        "side": "SELL",
        "action": action,
        "formal_action": action,
        "source": "AUTHORIZED_CANONICAL_HOLDING_SELL",
        "authorization_proven": True,
        "holding_quantity": quantity,
        "authorized_fraction": fraction,
        "authorized_max_shares": authorized,
        "executable_quantity": executable,
        "board_lot_size": BOARD_LOT_SIZE,
        "execution_status": status,
        "immediate_execution_eligible": executable > 0,
        "manual_order_review_required": True,
        "current_price": _num(row.get("current_price")),
        "price_observed_at": row.get("price_observed_at") or "",
        "price_provider": row.get("price_provider") or "",
        "reason_codes": row.get("reason_codes") or "",
        "over_authority": False,
        "no_auto_trade": True,
    }


def _full_exit_operation(row: Mapping[str, Any], action: str) -> dict[str, Any]:
    quantity = _int(row.get("quantity"))
    executable = quantity or 0
    return {
        "code": _code(row.get("code")),
        "name": row.get("name") or "",
        "side": "SELL",
        "action": action,
        "formal_action": action,
        "source": "AUTHORIZED_CANONICAL_HOLDING_SELL",
        "authorization_proven": True,
        "holding_quantity": quantity,
        "authorized_fraction": 1.0,
        "authorized_max_shares": quantity,
        "executable_quantity": executable,
        "board_lot_size": BOARD_LOT_SIZE,
        "execution_status": "EXECUTION_REVIEW_REQUIRED" if executable > 0 else "BLOCKED_HOLDING_QUANTITY_UNKNOWN",
        "immediate_execution_eligible": executable > 0,
        "manual_order_review_required": True,
        "odd_lot_full_exit": bool(quantity is not None and quantity % BOARD_LOT_SIZE != 0),
        "current_price": _num(row.get("current_price")),
        "price_observed_at": row.get("price_observed_at") or "",
        "price_provider": row.get("price_provider") or "",
        "reason_codes": row.get("reason_codes") or "",
        "over_authority": False,
        "no_auto_trade": True,
    }


def _sell_operations(dashboard: Mapping[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for row in _holding_rows(dashboard):
        action = str(row.get("formal_action") or "").strip().upper()
        if action not in SELL_ACTIONS:
            continue
        if action in PARTIAL_SELL_FRACTIONS:
            operations.append(_partial_sell_operation(row, action, PARTIAL_SELL_FRACTIONS[action]))
        elif action in FULL_EXIT_ACTIONS:
            operations.append(_full_exit_operation(row, action))
        else:
            # Generic REDUCE has no frozen fraction. Do not invent one.
            operations.append({
                "code": _code(row.get("code")),
                "name": row.get("name") or "",
                "side": "SELL",
                "action": action,
                "formal_action": action,
                "source": "AUTHORIZED_CANONICAL_HOLDING_SELL",
                "authorization_proven": True,
                "authorized_fraction": None,
                "authorized_max_shares": None,
                "executable_quantity": 0,
                "board_lot_size": BOARD_LOT_SIZE,
                "execution_status": "BLOCKED_AMBIGUOUS_REDUCTION_FRACTION",
                "immediate_execution_eligible": False,
                "manual_order_review_required": True,
                "over_authority": False,
                "no_auto_trade": True,
            })
    return operations


def build_execution_overlay(dashboard: Mapping[str, Any]) -> dict[str, Any]:
    if dashboard.get("no_auto_trade") is not True:
        raise ValueError("dashboard lost no-auto-trade contract")
    if dashboard.get("formal_action_source") != "FINALIZED_CANONICAL_ONLY":
        raise ValueError("execution overlay requires finalized canonical Formal Actions")
    if dashboard.get("formal_action_recomputed") is not False:
        raise ValueError("execution overlay refuses recomputed Formal Actions")

    existing = dashboard.get("final_operation_table") or []
    if not isinstance(existing, list):
        raise ValueError("dashboard final_operation_table must be a list")
    existing_ops = [copy.deepcopy(dict(op)) for op in existing if isinstance(op, Mapping)]
    for op in existing_ops:
        op["execution_overlay_source"] = "DASHBOARD_EXISTING_OPERATION"
        op["no_auto_trade"] = True

    sells = _sell_operations(dashboard)
    sell_codes = {op["code"] for op in sells if op.get("code")}
    conflicting = sorted({
        _code(op.get("code")) for op in existing_ops
        if _code(op.get("code")) in sell_codes
        and str(op.get("action") or "").upper().startswith(("ADD", "BUY"))
    })
    if conflicting:
        raise ValueError("conflicting buy/add and sell authority for: " + ",".join(conflicting))

    unified = sells + existing_ops
    for op in sells:
        authorized = _int(op.get("authorized_max_shares"))
        executable = _int(op.get("executable_quantity")) or 0
        if authorized is not None and executable > authorized:
            raise AssertionError(f"execution exceeds authority for {op.get('code')}")

    return {
        "contract": CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_dashboard_contract": dashboard.get("contract_version") or dashboard.get("contract") or "",
        "source_generated_at": dashboard.get("generated_at") or dashboard.get("generated_at_beijing") or "",
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id") or "",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_mutation_allowed": False,
        "formal_trading_authority": False,
        "automatic_order_allowed": False,
        "no_auto_trade": True,
        "unknown_is_pass": False,
        "board_lot_size": BOARD_LOT_SIZE,
        "sell_operation_count": len(sells),
        "immediately_executable_sell_count": sum(bool(op.get("immediate_execution_eligible")) for op in sells),
        "deferred_sell_count": sum(not bool(op.get("immediate_execution_eligible")) for op in sells),
        "existing_operation_count": len(existing_ops),
        "operations": unified,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Investor Execution Plan",
        "",
        "> 只翻译已有投资 authority 为人工可执行数量；不产生新 BUY/SELL 权限，不自动交易。",
        "",
        f"- Sell decisions: {payload.get('sell_operation_count', 0)}",
        f"- Immediately executable sells: {payload.get('immediately_executable_sell_count', 0)}",
        f"- Deferred sells: {payload.get('deferred_sell_count', 0)}",
        "",
        "| Code | Name | Side | Action | Authorized max | Executable | Status |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for op in payload.get("operations") or []:
        lines.append(
            f"| {op.get('code','')} | {op.get('name','')} | {op.get('side') or ''} | "
            f"{op.get('action','')} | {op.get('authorized_max_shares','')} | "
            f"{op.get('executable_quantity', op.get('total_shares',''))} | "
            f"{op.get('execution_status', op.get('execution_note',''))} |"
        )
    return "\n".join(lines) + "\n"


def write_execution_overlay(*, dashboard_json: Path, json_output: Path, markdown_output: Path) -> dict[str, Any]:
    dashboard = json.loads(dashboard_json.read_text(encoding="utf-8"))
    payload = build_execution_overlay(dashboard)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = write_execution_overlay(
        dashboard_json=args.dashboard_json,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
    )
    print(
        f"investor_execution_overlay=OK;sells={payload['sell_operation_count']};"
        f"executable={payload['immediately_executable_sell_count']};no_auto_trade=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
