"""Consume one-shot Canonical holding-add authorizations after confirmed execution.

Formal actions remain Canonical-only. This read-side overlay only prevents an
already executed staged-add allowance from being planned again while the same
Canonical snapshot remains active. A new Canonical snapshot/source-run key does
not inherit an older consumption record.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_EXECUTION_CONSUMPTION_V1"
LOT_SIZE = 100
STAGED_ADD_SOURCE = "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD"
CONSUMED_REASON = "STAGED_ADD_AUTHORIZATION_CONSUMED"


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _consumption_map(
    execution_state: Mapping[str, Any], *, snapshot_id: str, source_run_id: str
) -> dict[str, dict[str, Any]]:
    if not execution_state:
        return {}
    if execution_state.get("contract_version") != CONTRACT:
        raise ValueError("execution consumption contract mismatch")
    if execution_state.get("no_auto_trade") is not True:
        raise ValueError("execution consumption state lost no-auto-trade")
    out: dict[str, dict[str, Any]] = {}
    for raw in execution_state.get("consumptions") or []:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("no_auto_trade") is not True:
            raise ValueError("execution consumption row lost no-auto-trade")
        if str(raw.get("canonical_snapshot_id") or "") != snapshot_id:
            continue
        if str(raw.get("canonical_source_run_id") or "") != source_run_id:
            continue
        if str(raw.get("authorization_type") or "") != "HOLDING_STAGED_ADD":
            continue
        code = _code(raw.get("code"))
        if not code:
            continue
        shares = max(0, _int(raw.get("consumed_shares")))
        previous = out.get(code)
        if previous is None or shares > _int(previous.get("consumed_shares")):
            out[code] = dict(raw)
    return out


def apply_execution_consumption(
    dashboard: Mapping[str, Any], execution_state: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Return dashboard with already-consumed staged adds suppressed.

    This function never changes ``formal_action`` or ``canonical_formal_action``.
    It only changes the derived repeatable add permission and capital plan.
    """
    payload = json.loads(json.dumps(dict(dashboard), ensure_ascii=False))
    snapshot_id = str(payload.get("canonical_snapshot_id") or "")
    source_run_id = str(payload.get("canonical_source_run_id") or "")
    consumptions = _consumption_map(
        dict(execution_state or {}), snapshot_id=snapshot_id, source_run_id=source_run_id
    )

    applied: list[dict[str, Any]] = []
    rows = payload.get("stock_portfolio", {}).get("rows") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _code(row.get("code"))
        record = consumptions.get(code)
        if record is None or row.get("holding_add_authorized") is not True:
            continue
        max_lots = max(1, _int(row.get("holding_add_max_lots")) or 1)
        allowance = max_lots * LOT_SIZE
        consumed = max(0, _int(record.get("consumed_shares")))
        if consumed < allowance:
            continue

        # Formal action itself is immutable here; only the one-shot staged ADD is consumed.
        row["holding_add_authorized"] = False
        reasons = [x for x in str(row.get("holding_add_reason_codes") or "").split(";") if x]
        if CONSUMED_REASON not in reasons:
            reasons.append(CONSUMED_REASON)
        row["holding_add_reason_codes"] = ";".join(reasons)
        row["holding_add_consumption"] = {
            "status": "CONSUMED",
            "canonical_snapshot_id": snapshot_id,
            "canonical_source_run_id": source_run_id,
            "consumed_shares": consumed,
            "allowance_shares": allowance,
            "consumed_at": record.get("consumed_at") or "",
            "authority": "EXECUTION_STATE_ONLY",
            "formal_action_mutation_allowed": False,
            "no_auto_trade": True,
        }
        if str(row.get("formal_action") or "").upper() == "HOLD":
            row["investor_action"] = "继续持有；当前Canonical的一手加仓授权已执行完毕，等待新Canonical重新授权"
        applied.append({"code": code, "consumed_shares": consumed, "allowance_shares": allowance})

    applied_codes = {x["code"] for x in applied}
    plan = payload.get("capital_deployment") if isinstance(payload.get("capital_deployment"), dict) else {}
    operations = list(plan.get("operations") or [])
    filtered = [
        op for op in operations
        if not (
            _code((op or {}).get("code")) in applied_codes
            and str((op or {}).get("source") or "") == STAGED_ADD_SOURCE
            and str((op or {}).get("action") or "").upper() == "ADD"
        )
    ]
    if len(filtered) != len(operations):
        plan["operations"] = filtered
        deployed = round(sum(_float((op or {}).get("estimated_cash_cny")) for op in filtered), 2)
        plan["planned_immediate_cash_cny"] = deployed
        available = _float(plan.get("available_cash_cny"))
        plan["cash_after_immediate_plan_cny"] = round(max(0.0, available - deployed), 2)
        payload["final_operation_table"] = [
            op for op in (payload.get("final_operation_table") or [])
            if not (
                _code((op or {}).get("code")) in applied_codes
                and str((op or {}).get("source") or "") == STAGED_ADD_SOURCE
                and str((op or {}).get("action") or "").upper() == "ADD"
            )
        ]
        if isinstance(payload.get("decision_summary"), dict):
            payload["decision_summary"]["planned_immediate_cash_cny"] = deployed
        headline = str(payload.get("headline") or "")
        payload["headline"] = re.sub(r"计划立即投入≈¥[0-9.]+", f"计划立即投入≈¥{deployed:.0f}", headline)

    payload["execution_consumption_reconciliation"] = {
        "contract_version": CONTRACT,
        "canonical_snapshot_id": snapshot_id,
        "canonical_source_run_id": source_run_id,
        "matching_consumption_count": len(consumptions),
        "applied_consumption_count": len(applied),
        "applied": applied,
        "formal_action_mutation_allowed": False,
        "automatic_order_allowed": False,
        "no_auto_trade": True,
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--execution-state", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)

    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    state = json.loads(args.execution_state.read_text(encoding="utf-8"))
    updated = apply_execution_consumption(dashboard, state)
    args.dashboard.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.markdown is not None:
        from .investor_decision_dashboard import render_markdown
        args.markdown.write_text(render_markdown(updated), encoding="utf-8")

    applied = updated.get("execution_consumption_reconciliation", {}).get("applied_consumption_count", 0)
    print(f"execution_consumption_applied={applied};snapshot={updated.get('canonical_snapshot_id','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
