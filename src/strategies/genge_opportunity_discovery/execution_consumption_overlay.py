"""Consume one-shot Canonical holding-add authorizations after confirmed execution.

Formal actions remain Canonical-only. This read-side overlay prevents an already
executed staged-add allowance from being planned again. Consumption is sticky
across routine Canonical snapshot/source-run refreshes for the same security;
a fresh snapshot is not, by itself, a new one-shot authorization. Re-arming
a consumed staged add requires an explicit ``holding_add_rearm_after_consumption``
flag (or ``STAGED_ADD_REARM_AUTHORIZED`` reason) on the current Canonical row.
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
REARM_REASON = "STAGED_ADD_REARM_AUTHORIZED"
REARM_FIELD = "holding_add_rearm_after_consumption"


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


def _explicit_rearm(row: Mapping[str, Any]) -> bool:
    if row.get(REARM_FIELD) is True:
        return True
    reasons = {x.strip() for x in str(row.get("holding_add_reason_codes") or "").split(";") if x.strip()}
    return REARM_REASON in reasons


def _consumption_map(
    execution_state: Mapping[str, Any], *, snapshot_id: str, source_run_id: str
) -> dict[str, dict[str, Any]]:
    """Return the authoritative latest staged-add consumption per security.

    Exact current-lineage records take precedence. If there is no exact record,
    the latest prior consumption is carried forward: routine Canonical refreshes
    must not silently recreate a one-shot allowance. The current Canonical can
    explicitly re-arm later; that decision is handled by ``_explicit_rearm``.
    """
    if not execution_state:
        return {}
    if execution_state.get("contract_version") != CONTRACT:
        raise ValueError("execution consumption contract mismatch")
    if execution_state.get("no_auto_trade") is not True:
        raise ValueError("execution consumption state lost no-auto-trade")

    out: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(execution_state.get("consumptions") or []):
        if not isinstance(raw, Mapping):
            continue
        if raw.get("no_auto_trade") is not True:
            raise ValueError("execution consumption row lost no-auto-trade")
        if str(raw.get("authorization_type") or "") != "HOLDING_STAGED_ADD":
            continue
        code = _code(raw.get("code"))
        if not code:
            continue

        exact = (
            str(raw.get("canonical_snapshot_id") or "") == snapshot_id
            and str(raw.get("canonical_source_run_id") or "") == source_run_id
        )
        candidate = dict(raw)
        candidate["_lineage_match"] = "EXACT" if exact else "CARRIED_FORWARD"
        candidate["_ledger_index"] = index

        previous = out.get(code)
        if previous is None:
            out[code] = candidate
            continue

        previous_exact = previous.get("_lineage_match") == "EXACT"
        if exact and not previous_exact:
            out[code] = candidate
            continue
        if previous_exact and not exact:
            continue

        candidate_time = str(candidate.get("consumed_at") or "")
        previous_time = str(previous.get("consumed_at") or "")
        if (candidate_time, index, _int(candidate.get("consumed_shares"))) >= (
            previous_time,
            _int(previous.get("_ledger_index")),
            _int(previous.get("consumed_shares")),
        ):
            out[code] = candidate
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
    rearm_skipped: list[str] = []
    rows = payload.get("stock_portfolio", {}).get("rows") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _code(row.get("code"))
        record = consumptions.get(code)
        if record is None or row.get("holding_add_authorized") is not True:
            continue

        lineage_match = str(record.get("_lineage_match") or "CARRIED_FORWARD")
        if lineage_match != "EXACT" and _explicit_rearm(row):
            rearm_skipped.append(code)
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
            "source_canonical_snapshot_id": str(record.get("canonical_snapshot_id") or ""),
            "source_canonical_source_run_id": str(record.get("canonical_source_run_id") or ""),
            "applied_to_canonical_snapshot_id": snapshot_id,
            "applied_to_canonical_source_run_id": source_run_id,
            "lineage_match": lineage_match,
            "consumed_shares": consumed,
            "allowance_shares": allowance,
            "remaining_executable_shares": 0,
            "consumed_at": record.get("consumed_at") or "",
            "authority": "EXECUTION_STATE_ONLY",
            "rearm_requires_explicit_authority": True,
            "formal_action_mutation_allowed": False,
            "no_auto_trade": True,
        }
        if str(row.get("formal_action") or "").upper() == "HOLD":
            row["investor_action"] = "继续持有；历史分批加仓授权已消费，本轮新增可执行0股"
        applied.append({
            "code": code,
            "consumed_shares": consumed,
            "allowance_shares": allowance,
            "lineage_match": lineage_match,
        })

    applied_codes = {x["code"] for x in applied}
    plan = payload.get("capital_deployment") if isinstance(payload.get("capital_deployment"), dict) else {}
    operations = list(plan.get("operations") or [])
    filtered = [
        op for op in operations
        if not (
            _code((op or {}).get("code")) in applied_codes
            and str((op or {}).get("source") or "") == STAGED_ADD_SOURCE
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
            )
        ]
        if isinstance(payload.get("decision_summary"), dict):
            payload["decision_summary"]["planned_immediate_cash_cny"] = deployed
        headline = str(payload.get("headline") or "")
        payload["headline"] = re.sub(r"计划立即投入≈¥[0-9.]+", f"计划立即投入≈¥{deployed:.0f}", headline)

    exact_count = sum(1 for x in consumptions.values() if x.get("_lineage_match") == "EXACT")
    carried_count = sum(1 for x in consumptions.values() if x.get("_lineage_match") == "CARRIED_FORWARD")
    payload["execution_consumption_reconciliation"] = {
        "contract_version": CONTRACT,
        "canonical_snapshot_id": snapshot_id,
        "canonical_source_run_id": source_run_id,
        "matching_consumption_count": len(consumptions),
        "exact_lineage_consumption_count": exact_count,
        "carried_forward_consumption_count": carried_count,
        "explicit_rearm_skipped_count": len(rearm_skipped),
        "explicit_rearm_skipped_codes": rearm_skipped,
        "applied_consumption_count": len(applied),
        "applied": applied,
        "routine_canonical_refresh_rearms_consumed_add": False,
        "explicit_rearm_required": True,
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

    reconciliation = updated.get("execution_consumption_reconciliation", {})
    applied = reconciliation.get("applied_consumption_count", 0)
    carried = reconciliation.get("carried_forward_consumption_count", 0)
    print(
        f"execution_consumption_applied={applied};carried_forward={carried};"
        f"snapshot={updated.get('canonical_snapshot_id','')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
