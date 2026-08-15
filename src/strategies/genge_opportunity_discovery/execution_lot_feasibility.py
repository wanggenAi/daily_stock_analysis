"""Board-aware lot feasibility audit for formal execution plans.

This module does not create, promote, or execute signals. It post-processes the
existing actionable execution list and answers a narrower question: can the
smallest legal buy quantity fit inside the plan's initial/max position budget
for a supplied research portfolio size?

The quantity rules reflect current Shanghai/Shenzhen competitive A-share order
units: main-board and ChiNext buys use 100-share multiples; STAR orders require
at least 200 shares and may increase by one share above 200. Unknown boards fail
closed as LOT_RULE_UNKNOWN.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


LOT_RULE_VERSION = "CN_A_SHARE_COMPETITIVE_BUY_LOTS_2026_07"
BOARD_LOT_RULES: dict[str, tuple[int, int]] = {
    "SSE_MAIN": (100, 100),
    "SZSE_MAIN": (100, 100),
    "CHINEXT": (100, 100),
    "STAR": (200, 1),
}

OUTPUT_COLUMNS = [
    "code",
    "stock_name",
    "board",
    "lot_rule_version",
    "minimum_buy_quantity",
    "buy_quantity_increment",
    "entry_low",
    "max_buy_price",
    "minimum_order_notional_at_entry_low",
    "minimum_order_notional_at_max_buy_price",
    "risk_budget_initial_position_pct",
    "risk_budget_max_position_pct",
    "minimum_portfolio_capital_for_initial_budget_at_entry_low",
    "minimum_portfolio_capital_for_initial_budget_at_max_buy_price",
    "minimum_portfolio_capital_for_max_budget_at_entry_low",
    "minimum_portfolio_capital_for_max_budget_at_max_buy_price",
    "portfolio_capital",
    "initial_budget_amount",
    "max_budget_amount",
    "initial_feasible_quantity_at_entry_low",
    "initial_feasible_quantity_at_max_buy_price",
    "max_feasible_quantity_at_entry_low",
    "max_feasible_quantity_at_max_buy_price",
    "initial_band_feasibility",
    "max_band_feasibility",
    "execution_lot_feasibility_status",
    "formal_signal_changed",
    "automatic_order_allowed",
    "no_auto_trade",
]


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip().lower() in {"", "nan", "none"}:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round_money(value: float | None) -> float | str:
    return "" if value is None else round(value, 2)


def _required_capital(notional: float | None, position_pct: float | None) -> float | None:
    if notional is None or position_pct is None or position_pct <= 0:
        return None
    return notional / (position_pct / 100.0)


def feasible_quantity(*, budget: float, price: float, minimum: int, increment: int) -> int:
    """Largest legal buy quantity within budget at ``price``; zero fails closed."""

    if budget <= 0 or price <= 0 or minimum <= 0 or increment <= 0:
        return 0
    affordable = math.floor(budget / price)
    if affordable < minimum:
        return 0
    if increment == 1:
        return affordable
    return (affordable // increment) * increment


def _band_status(low_qty: int, high_qty: int, minimum: int) -> str:
    if high_qty >= minimum:
        return "FULL_ENTRY_BAND_LOT_FEASIBLE"
    if low_qty >= minimum:
        return "PARTIAL_ENTRY_BAND_LOT_FEASIBLE"
    return "NO_ENTRY_BAND_LOT_FEASIBLE"


def audit_execution_row(
    execution: Mapping[str, Any],
    strict_row: Mapping[str, Any],
    *,
    portfolio_capital: float | None,
) -> dict[str, Any]:
    code = str(execution.get("code") or strict_row.get("code") or "").zfill(6)
    board = str(strict_row.get("board") or execution.get("board") or "").upper()
    entry_low = _float(execution.get("entry_low"))
    max_buy_price = _float(execution.get("max_buy_price") or execution.get("entry_high"))
    initial_pct = _float(execution.get("risk_budget_initial_position_pct"))
    max_pct = _float(execution.get("risk_budget_max_position_pct"))
    rule = BOARD_LOT_RULES.get(board)

    base: dict[str, Any] = {
        "code": code,
        "stock_name": execution.get("stock_name") or strict_row.get("stock_name") or "",
        "board": board,
        "lot_rule_version": LOT_RULE_VERSION,
        "entry_low": entry_low if entry_low is not None else "",
        "max_buy_price": max_buy_price if max_buy_price is not None else "",
        "risk_budget_initial_position_pct": initial_pct if initial_pct is not None else "",
        "risk_budget_max_position_pct": max_pct if max_pct is not None else "",
        "portfolio_capital": portfolio_capital if portfolio_capital is not None else "",
        "formal_signal_changed": False,
        "automatic_order_allowed": False,
        "no_auto_trade": True,
    }

    if rule is None or entry_low is None or max_buy_price is None or entry_low <= 0 or max_buy_price <= 0:
        base.update({
            "minimum_buy_quantity": "",
            "buy_quantity_increment": "",
            "execution_lot_feasibility_status": "LOT_RULE_OR_PRICE_UNKNOWN",
        })
        return base

    minimum, increment = rule
    low_notional = minimum * entry_low
    high_notional = minimum * max_buy_price
    base.update({
        "minimum_buy_quantity": minimum,
        "buy_quantity_increment": increment,
        "minimum_order_notional_at_entry_low": _round_money(low_notional),
        "minimum_order_notional_at_max_buy_price": _round_money(high_notional),
        "minimum_portfolio_capital_for_initial_budget_at_entry_low": _round_money(
            _required_capital(low_notional, initial_pct)
        ),
        "minimum_portfolio_capital_for_initial_budget_at_max_buy_price": _round_money(
            _required_capital(high_notional, initial_pct)
        ),
        "minimum_portfolio_capital_for_max_budget_at_entry_low": _round_money(
            _required_capital(low_notional, max_pct)
        ),
        "minimum_portfolio_capital_for_max_budget_at_max_buy_price": _round_money(
            _required_capital(high_notional, max_pct)
        ),
    })

    if portfolio_capital is None or portfolio_capital <= 0:
        base.update({
            "initial_band_feasibility": "CAPITAL_NOT_SUPPLIED",
            "max_band_feasibility": "CAPITAL_NOT_SUPPLIED",
            "execution_lot_feasibility_status": "CAPITAL_NOT_SUPPLIED",
        })
        return base

    initial_budget = portfolio_capital * (initial_pct or 0.0) / 100.0
    max_budget = portfolio_capital * (max_pct or 0.0) / 100.0
    initial_low_qty = feasible_quantity(
        budget=initial_budget, price=entry_low, minimum=minimum, increment=increment,
    )
    initial_high_qty = feasible_quantity(
        budget=initial_budget, price=max_buy_price, minimum=minimum, increment=increment,
    )
    max_low_qty = feasible_quantity(
        budget=max_budget, price=entry_low, minimum=minimum, increment=increment,
    )
    max_high_qty = feasible_quantity(
        budget=max_budget, price=max_buy_price, minimum=minimum, increment=increment,
    )
    initial_band = _band_status(initial_low_qty, initial_high_qty, minimum)
    max_band = _band_status(max_low_qty, max_high_qty, minimum)

    if initial_band == "FULL_ENTRY_BAND_LOT_FEASIBLE":
        status = "FULL_ENTRY_BAND_FEASIBLE_WITHIN_INITIAL_BUDGET"
    elif initial_band == "PARTIAL_ENTRY_BAND_LOT_FEASIBLE":
        status = "PARTIAL_ENTRY_BAND_FEASIBLE_WITHIN_INITIAL_BUDGET"
    elif max_band != "NO_ENTRY_BAND_LOT_FEASIBLE":
        status = "INITIAL_BUDGET_NO_LOT_MAX_CAP_CAN_SUPPORT"
    else:
        status = "NO_LOT_FEASIBLE_WITHIN_MAX_POSITION_CAP"

    base.update({
        "initial_budget_amount": _round_money(initial_budget),
        "max_budget_amount": _round_money(max_budget),
        "initial_feasible_quantity_at_entry_low": initial_low_qty,
        "initial_feasible_quantity_at_max_buy_price": initial_high_qty,
        "max_feasible_quantity_at_entry_low": max_low_qty,
        "max_feasible_quantity_at_max_buy_price": max_high_qty,
        "initial_band_feasibility": initial_band,
        "max_band_feasibility": max_band,
        "execution_lot_feasibility_status": status,
    })
    return base


def build_feasibility_rows(
    executions: Iterable[Mapping[str, Any]],
    strict_rows: Iterable[Mapping[str, Any]],
    *,
    portfolio_capital: float | None,
) -> list[dict[str, Any]]:
    strict_by_code = {
        str(row.get("code") or "").zfill(6): dict(row)
        for row in strict_rows
        if str(row.get("code") or "").strip()
    }
    return [
        audit_execution_row(
            execution,
            strict_by_code.get(str(execution.get("code") or "").zfill(6), {}),
            portfolio_capital=portfolio_capital,
        )
        for execution in executions
    ]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OUTPUT_COLUMNS})


def _write_markdown(path: Path, rows: list[Mapping[str, Any]]) -> None:
    lines = [
        "# Execution Lot Feasibility",
        "",
        "This report does not create or change formal signals and never places orders.",
        "Lot infeasibility must not be solved by exceeding the strategy position cap.",
        "",
    ]
    if not rows:
        lines.append("No actionable execution rows in the current production report.")
    for row in rows:
        lines.extend([
            f"## {row.get('code')} {row.get('stock_name')}",
            f"- board: {row.get('board')}",
            f"- minimum buy quantity: {row.get('minimum_buy_quantity')}",
            f"- minimum order notional at plan max price: {row.get('minimum_order_notional_at_max_buy_price')}",
            f"- status: {row.get('execution_lot_feasibility_status')}",
            "- automatic order allowed: False",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_report_dir(path: Path | None) -> Path:
    if path is not None:
        return path
    root = Path("reports/all_a_full_scan")
    candidates = sorted(
        item for item in root.iterdir()
        if item.is_dir() and (item / "actionable_execution_list.csv").exists()
    ) if root.exists() else []
    if not candidates:
        raise RuntimeError("no all-A report with actionable_execution_list.csv found")
    return candidates[-1]


def _portfolio_capital(cli_value: float | None) -> float | None:
    if cli_value is not None:
        return cli_value if cli_value > 0 else None
    env_value = _float(os.environ.get("GENGE_RESEARCH_PORTFOLIO_CAPITAL"))
    return env_value if env_value is not None and env_value > 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--portfolio-capital", type=float)
    args = parser.parse_args(argv)
    report_dir = resolve_report_dir(args.report_dir)
    capital = _portfolio_capital(args.portfolio_capital)
    executions = _read_csv(report_dir / "actionable_execution_list.csv")
    strict_rows = _read_csv(report_dir / "strict_review_ready.csv")
    rows = build_feasibility_rows(executions, strict_rows, portfolio_capital=capital)
    _write_csv(report_dir / "actionable_execution_feasibility.csv", rows)
    _write_markdown(report_dir / "actionable_execution_feasibility.md", rows)
    print(
        f"execution_lot_feasibility={report_dir};count={len(rows)};"
        f"capital={'SUPPLIED' if capital is not None else 'NOT_SUPPLIED'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
