#!/usr/bin/env python3
"""Bind Decision Center and ChatGPT handoff to the exact consumed data package.

This is a provenance/safety adapter only. It never recomputes Formal actions.
If the locked package is not execution-ready, immediate execution semantics are
failed closed while the historical/research Formal values remain intact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT = "GEN_GE_DECISION_DATA_PROVENANCE_V1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fail_close_plan(payload: dict[str, Any], reason: str) -> None:
    plan = payload.get("today_account_plan") or payload.get("capital_deployment") or {}
    if not isinstance(plan, dict):
        return
    operations = plan.get("operations") or []
    for row in operations:
        if not isinstance(row, dict):
            continue
        row["immediate_execution_eligible"] = False
        row["execution_block_reason"] = reason
        if "executable_shares" in row:
            row["executable_shares"] = 0
        if "executable_quantity" in row:
            row["executable_quantity"] = 0
    plan["planned_immediate_cash_cny"] = 0.0
    available = plan.get("available_cash_cny")
    if available is not None:
        plan["cash_after_immediate_plan_cny"] = available
    plan["no_auto_trade"] = True
    if "today_account_plan" in payload:
        payload["today_account_plan"] = plan
    if "capital_deployment" in payload:
        payload["capital_deployment"] = plan
    if isinstance(payload.get("decision_summary"), dict):
        payload["decision_summary"]["planned_immediate_cash_cny"] = 0.0
    if isinstance(payload.get("final_operation_table"), list):
        for row in payload["final_operation_table"]:
            if isinstance(row, dict):
                row["immediate_execution_eligible"] = False
                row["execution_block_reason"] = reason
                if "executable_shares" in row:
                    row["executable_shares"] = 0
                if "executable_quantity" in row:
                    row["executable_quantity"] = 0


def bind(
    *,
    decision_path: Path,
    package_path: Path,
    receipt_path: Path,
    handoff_path: Path | None = None,
) -> dict[str, Any]:
    decision = _load(decision_path)
    package = _load(package_path)
    receipt = _load(receipt_path)

    package_id = str(package.get("snapshot_id") or "")
    receipt_id = str(receipt.get("input_snapshot_id") or "")
    if not package_id or package_id != receipt_id:
        raise ValueError(f"research input/package lineage mismatch: package={package_id!r} receipt={receipt_id!r}")
    if package.get("contract") != "GEN_GE_REALTIME_DATA_PACKAGE_V1":
        raise ValueError("unexpected data-package contract")
    if receipt.get("contract") != "GEN_GE_RESEARCH_INPUT_LOCK_V1":
        raise ValueError("unexpected research-input contract")

    execution_allowed = receipt.get("execution_allowed") is True and package.get("package_status") == "READY"
    reason = None if execution_allowed else str(receipt.get("fail_closed_reason") or f"DATA_PACKAGE_{package.get('package_status')}_NOT_EXECUTABLE")
    provenance = {
        "contract": CONTRACT,
        "data_package_contract": package.get("contract"),
        "snapshot_id": package_id,
        "package_generated_at": package.get("generated_at"),
        "package_status": package.get("package_status"),
        "latest_trade_date": package.get("latest_trade_date"),
        "research_input_contract": receipt.get("contract"),
        "research_mode": receipt.get("research_mode"),
        "research_input_locked_at": receipt.get("locked_at"),
        "network_policy": receipt.get("network_policy"),
        "external_fresh_evidence_policy": receipt.get("external_fresh_evidence_policy"),
        "pending_external_fresh_evidence_count": package.get("pending_external_fresh_evidence_count", 0),
        "execution_allowed": execution_allowed,
    }
    guard = {
        "execution_allowed": execution_allowed,
        "formal_actions_preserved": True,
        "formal_action_recomputed": False,
        "stale_or_partial_data_cannot_authorize_execution": True,
        "block_reason": reason,
        "no_auto_trade": True,
    }

    decision["data_package_provenance"] = provenance
    decision["data_freshness_execution_guard"] = guard
    decision["no_auto_trade"] = True
    if not execution_allowed:
        _fail_close_plan(decision, reason or "DATA_PACKAGE_NOT_EXECUTABLE")
    _write(decision_path, decision)

    if handoff_path and handoff_path.is_file():
        handoff = _load(handoff_path)
        handoff["data_package_provenance"] = provenance
        handoff["data_freshness_execution_guard"] = guard
        handoff["no_auto_trade"] = True
        if not execution_allowed:
            _fail_close_plan(handoff, reason or "DATA_PACKAGE_NOT_EXECUTABLE")
        _write(handoff_path, handoff)
    return decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--package", type=Path, default=Path("data/data_package/latest.json"))
    parser.add_argument("--receipt", type=Path, default=Path("data/research_input/latest.json"))
    parser.add_argument("--handoff", type=Path, default=Path("data/investor_chatgpt_handoff/latest.json"))
    args = parser.parse_args(argv)
    try:
        payload = bind(decision_path=args.decision, package_path=args.package, receipt_path=args.receipt, handoff_path=args.handoff)
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    p = payload.get("data_package_provenance") or {}
    print(json.dumps({"contract": CONTRACT, "snapshot_id": p.get("snapshot_id"), "package_status": p.get("package_status"), "execution_allowed": p.get("execution_allowed")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
