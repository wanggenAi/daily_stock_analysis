#!/usr/bin/env python3
"""Observer-only outcome evaluator for GenGe V3.1.1.

This module deliberately sits downstream of finalized canonical output.  It may
record/evaluate decisions and explicit executions, but it MUST NOT feed back
into canonical production decisions, thresholds, gates, or lifecycle state.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ALLOWED_ACTIONS = {
    "BUY", "ADD", "HOLD", "HOLD_REVIEW", "REDUCE", "REDUCE_25", "REDUCE_50",
    "EXIT", "WAIT_PRICE", "REJECT",
}
MILESTONES = (20, 50, 100)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{no}: JSONL row must be an object")
        rows.append(row)
    return rows


def _append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    payload = list(rows)
    if not payload:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in payload:
            fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
    return len(payload)


def stable_decision_id(snapshot_id: str, source_run_id: str, symbol: str, action: str) -> str:
    identity = "|".join((snapshot_id, source_run_id, symbol, action))
    return "dec_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def stable_execution_id(symbol: str, side: str, quantity: int, price: float, executed_at: str, decision_id: str | None) -> str:
    identity = "|".join((symbol, side, str(quantity), f"{price:.8f}", executed_at, decision_id or ""))
    return "exe_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_action(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    action = value.strip().upper().replace("-", "_").replace(" ", "_")
    if action in ALLOWED_ACTIONS:
        return action
    # Preserve parameterized REDUCE values without silently promoting unknown actions.
    if action.startswith("REDUCE_") and action[7:].isdigit():
        return action
    return None


def _candidate_records(node: Any) -> Iterable[Mapping[str, Any]]:
    """Yield dicts that look like symbol/action decisions without schema mutation."""
    if isinstance(node, Mapping):
        symbol = _first(node, "symbol", "code", "ticker", "stock_code")
        action = _first(node, "formal_action", "action", "decision", "canonical_action")
        if symbol is not None and _normalize_action(action):
            yield node
        for value in node.values():
            yield from _candidate_records(value)
    elif isinstance(node, list):
        for item in node:
            yield from _candidate_records(item)


def canonical_identity(canonical: Mapping[str, Any]) -> tuple[str, str, str | None, str | None]:
    snapshot_id = _first(canonical, "snapshot_id", "canonical_snapshot_id")
    source_run_id = _first(canonical, "source_run_id", "canonical_source_run_id", "producer_run_id")
    latest_trade_date = _first(canonical, "latest_trade_date")
    research_as_of = _first(canonical, "research_as_of")

    meta = canonical.get("metadata")
    if isinstance(meta, Mapping):
        snapshot_id = snapshot_id or _first(meta, "snapshot_id", "canonical_snapshot_id")
        source_run_id = source_run_id or _first(meta, "source_run_id", "canonical_source_run_id", "producer_run_id")
        latest_trade_date = latest_trade_date or _first(meta, "latest_trade_date")
        research_as_of = research_as_of or _first(meta, "research_as_of")

    if snapshot_id is None or source_run_id is None:
        raise ValueError("canonical snapshot_id/source_run_id are required; refusing ambiguous import")
    return str(snapshot_id), str(source_run_id), (str(latest_trade_date) if latest_trade_date else None), (str(research_as_of) if research_as_of else None)


def extract_decisions(canonical: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract an immutable observer projection from a finalized canonical snapshot."""
    original = copy.deepcopy(canonical)
    snapshot_id, source_run_id, latest_trade_date, research_as_of = canonical_identity(canonical)
    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    for row in _candidate_records(canonical):
        symbol = str(_first(row, "symbol", "code", "ticker", "stock_code")).strip()
        action = _normalize_action(_first(row, "formal_action", "action", "decision", "canonical_action"))
        if not symbol or not action:
            continue
        decision_id = stable_decision_id(snapshot_id, source_run_id, symbol, action)
        if decision_id in seen:
            continue
        seen.add(decision_id)
        event = {
            "event_type": "CANONICAL_DECISION_OBSERVED",
            "decision_id": decision_id,
            "snapshot_id": snapshot_id,
            "source_run_id": source_run_id,
            "symbol": symbol,
            "action": action,
            "latest_trade_date": latest_trade_date,
            "research_as_of": research_as_of,
            "observed_at": _utc_now(),
        }
        for src, dst in (("name", "name"), ("stock_name", "name"), ("rationale", "rationale"), ("reason", "rationale")):
            if src in row and row[src] not in (None, "") and dst not in event:
                event[dst] = row[src]
        events.append(event)
    if canonical != original:
        raise AssertionError("observer mutated canonical payload")
    return events


def import_canonical(canonical_path: Path, decisions_path: Path) -> dict[str, Any]:
    canonical = _load_json(canonical_path)
    if not isinstance(canonical, Mapping):
        raise ValueError("canonical must be a JSON object")
    events = extract_decisions(canonical)
    existing = {row.get("decision_id") for row in _read_jsonl(decisions_path)}
    new_rows = [event for event in events if event["decision_id"] not in existing]
    _append_jsonl(decisions_path, new_rows)
    snapshot_id, source_run_id, _, _ = canonical_identity(canonical)
    return {
        "status": "IMPORTED" if new_rows else "NOOP",
        "snapshot_id": snapshot_id,
        "source_run_id": source_run_id,
        "discovered": len(events),
        "appended": len(new_rows),
    }


def record_execution(path: Path, *, symbol: str, side: str, quantity: int, price: float,
                     executed_at: str, fees: float = 0.0, decision_id: str | None = None,
                     notes: str | None = None) -> dict[str, Any]:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0 or price <= 0 or fees < 0:
        raise ValueError("quantity/price must be positive and fees non-negative")
    # Require caller-supplied timestamp: execution must never be inferred.
    if not executed_at.strip():
        raise ValueError("executed_at is required")
    event_id = stable_execution_id(symbol, side, quantity, price, executed_at, decision_id)
    existing = {row.get("execution_id") for row in _read_jsonl(path)}
    if event_id in existing:
        return {"status": "NOOP", "execution_id": event_id}
    row: dict[str, Any] = {
        "event_type": "EXPLICIT_EXECUTION_RECORDED",
        "execution_id": event_id,
        "decision_id": decision_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "fees": fees,
        "executed_at": executed_at,
        "recorded_at": _utc_now(),
    }
    if notes:
        row["notes"] = notes
    _append_jsonl(path, [row])
    return {"status": "RECORDED", "execution_id": event_id}


@dataclass
class Lot:
    quantity: int
    unit_cost: float
    opened_at: str


def _fifo_metrics(executions: Sequence[Mapping[str, Any]]) -> tuple[list[float], dict[str, int], dict[str, float]]:
    lots: dict[str, deque[Lot]] = defaultdict(deque)
    closed_pnls: list[float] = []
    open_qty: dict[str, int] = defaultdict(int)
    realized_by_symbol: dict[str, float] = defaultdict(float)

    ordered = sorted(executions, key=lambda x: (str(x.get("executed_at", "")), str(x.get("execution_id", ""))))
    for event in ordered:
        symbol = str(event["symbol"])
        side = str(event["side"]).upper()
        qty = int(event["quantity"])
        price = float(event["price"])
        fees = float(event.get("fees") or 0.0)
        if side == "BUY":
            unit_cost = price + fees / qty
            lots[symbol].append(Lot(qty, unit_cost, str(event["executed_at"])))
            open_qty[symbol] += qty
            continue
        if side != "SELL":
            raise ValueError(f"unsupported execution side: {side}")
        if qty > open_qty[symbol]:
            raise ValueError(f"SELL quantity exceeds explicit open quantity for {symbol}")
        remaining = qty
        sell_fee_per_share = fees / qty
        sale_group_pnl = 0.0
        while remaining:
            lot = lots[symbol][0]
            matched = min(remaining, lot.quantity)
            pnl = (price - sell_fee_per_share - lot.unit_cost) * matched
            sale_group_pnl += pnl
            lot.quantity -= matched
            remaining -= matched
            open_qty[symbol] -= matched
            if lot.quantity == 0:
                lots[symbol].popleft()
        closed_pnls.append(sale_group_pnl)
        realized_by_symbol[symbol] += sale_group_pnl
    return closed_pnls, dict(open_qty), dict(realized_by_symbol)


def _max_drawdown(realized_pnls: Sequence[float]) -> float | None:
    if not realized_pnls:
        return None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in realized_pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def evaluate(decisions: Sequence[Mapping[str, Any]], executions: Sequence[Mapping[str, Any]],
             current_prices: Mapping[str, float] | None = None) -> dict[str, Any]:
    decision_by_id = {str(row["decision_id"]): row for row in decisions if row.get("decision_id")}
    executed_decision_ids = {str(row["decision_id"]) for row in executions if row.get("decision_id")}
    action_counts = Counter(str(row.get("action")) for row in decisions if row.get("action"))
    closed_pnls, open_qty, realized_by_symbol = _fifo_metrics(executions)

    wins = [p for p in closed_pnls if p > 0]
    losses = [p for p in closed_pnls if p < 0]
    flat = [p for p in closed_pnls if math.isclose(p, 0.0, abs_tol=1e-9)]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    closed_count = len(closed_pnls)

    unrealized: dict[str, float] = {}
    if current_prices:
        # Cost-basis-level unrealized P&L needs explicit open lots.  To avoid inventing
        # cost basis from holdings/canonical data, expose only availability here.
        for symbol, qty in open_qty.items():
            if qty > 0 and symbol in current_prices:
                unrealized[symbol] = float("nan")

    linked_exec = sum(1 for row in executions if row.get("decision_id") in decision_by_id)
    next_milestone = next((m for m in MILESTONES if closed_count < m), None)
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "observer_only": True,
        "production_semantics_mutated": False,
        "canonical_decisions": {
            "total": len(decisions),
            "by_action": dict(sorted(action_counts.items())),
            "with_explicit_execution": len(executed_decision_ids & set(decision_by_id)),
        },
        "executions": {
            "total": len(executions),
            "linked_to_canonical_decision": linked_exec,
            "open_quantity_by_symbol": {k: v for k, v in sorted(open_qty.items()) if v},
        },
        "closed_trade_statistics": {
            "closed_sell_events": closed_count,
            "wins": len(wins),
            "losses": len(losses),
            "flat": len(flat),
            "win_rate": (len(wins) / closed_count if closed_count else None),
            "average_win": (gross_profit / len(wins) if wins else None),
            "average_loss": (sum(losses) / len(losses) if losses else None),
            "profit_factor": (gross_profit / gross_loss if gross_loss else (None if not wins else "INF")),
            "expectancy_per_closed_sell": (sum(closed_pnls) / closed_count if closed_count else None),
            "max_drawdown_realized_series": _max_drawdown(closed_pnls),
            "realized_pnl_by_symbol": dict(sorted(realized_by_symbol.items())),
            "note": "Open positions are excluded from win/loss/expectancy. Max drawdown uses explicit chronological realized sell P&L only.",
        },
        "milestones": {
            "completed_closed_loops": closed_count,
            "next": next_milestone,
            "reached": [m for m in MILESTONES if closed_count >= m],
        },
        "observational_only": {
            "add_reduce_effectiveness": "NOT_COMPUTED_WITHOUT_EXPLICIT_COUNTERFACTUAL_SERIES",
            "causal_claims_allowed": False,
        },
    }
    if unrealized:
        result["unrealized_pnl"] = {
            "status": "NOT_COMPUTED",
            "reason": "Explicit current prices alone are insufficient here; evaluator intentionally does not infer open-lot cost basis from canonical/holdings.",
        }
    return result


def _load_prices(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    raw = _load_json(path)
    if not isinstance(raw, Mapping):
        raise ValueError("prices JSON must be an object mapping symbol to price")
    return {str(k): float(v) for k, v in raw.items()}


def _write_summary(path: Path, summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import-canonical")
    imp.add_argument("--canonical", type=Path, required=True)
    imp.add_argument("--decisions", type=Path, required=True)

    rec = sub.add_parser("record-execution")
    rec.add_argument("--executions", type=Path, required=True)
    rec.add_argument("--symbol", required=True)
    rec.add_argument("--side", choices=("BUY", "SELL"), required=True)
    rec.add_argument("--quantity", type=int, required=True)
    rec.add_argument("--price", type=float, required=True)
    rec.add_argument("--executed-at", required=True)
    rec.add_argument("--fees", type=float, default=0.0)
    rec.add_argument("--decision-id")
    rec.add_argument("--notes")

    ev = sub.add_parser("evaluate")
    ev.add_argument("--decisions", type=Path, required=True)
    ev.add_argument("--executions", type=Path, required=True)
    ev.add_argument("--summary", type=Path, required=True)
    ev.add_argument("--prices", type=Path)

    args = parser.parse_args(argv)
    if args.command == "import-canonical":
        output = import_canonical(args.canonical, args.decisions)
    elif args.command == "record-execution":
        output = record_execution(
            args.executions, symbol=args.symbol, side=args.side, quantity=args.quantity,
            price=args.price, executed_at=args.executed_at, fees=args.fees,
            decision_id=args.decision_id, notes=args.notes,
        )
    else:
        output = evaluate(_read_jsonl(args.decisions), _read_jsonl(args.executions), _load_prices(args.prices))
        _write_summary(args.summary, output)
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
