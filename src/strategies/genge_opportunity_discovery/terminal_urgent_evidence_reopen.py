"""Build a fail-closed Deep-Lambda reopen plan from terminal urgent research.

This module bridges refreshed slow-lane evidence back into the research-only V3.1
Deep Calculation Lambda. It never changes a gate, never converts UNKNOWN to PASS,
and never creates Formal/Production trading authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_TERMINAL_URGENT_EVIDENCE_REOPEN_V1"
TERMINAL_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
EVIDENCE_BLOCKED_REASON = "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            text = text[len(prefix) :]
            break
    return text.zfill(6) if text.isdigit() else text


def _validate_terminal(payload: Mapping[str, Any]) -> None:
    if payload.get("contract") != TERMINAL_CONTRACT:
        raise ValueError("unexpected terminal research contract")
    if payload.get("all_requested_terminal") is not True:
        raise ValueError("terminal research workset is not fully terminal")
    if payload.get("research_authority") != "RESEARCH_ONLY":
        raise ValueError("terminal research authority must remain RESEARCH_ONLY")
    if payload.get("formal_trading_authority") is not False:
        raise ValueError("terminal research must not have Formal authority")
    if payload.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("automatic Formal BUY must remain disabled")
    if payload.get("unknown_is_pass") is not False:
        raise ValueError("UNKNOWN must never be PASS")
    if payload.get("no_auto_trade") is not True:
        raise ValueError("terminal research must remain no-auto-trade")


def build_reopen_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Select only reopenable urgent evidence-blocked REJECT rows.

    Specialized industries are intentionally not filtered here: evidence recovery
    applies to them too. Their valuation policy remains enforced downstream by the
    terminal decision engine and this planner has no authority to grant BUY.
    """
    _validate_terminal(payload)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in payload.get("urgent_research_queue") or []:
        if not isinstance(raw, Mapping):
            raise ValueError("urgent research row must be an object")
        row = dict(raw)
        code = _code(row.get("code"))
        if not code or not code.isdigit() or len(code) != 6:
            raise ValueError("urgent research row has invalid A-share code")
        if row.get("urgent_research") is not True:
            raise ValueError(f"urgent queue row is not marked urgent: {code}")
        if row.get("research_decision") != "REJECT":
            raise ValueError(f"urgent reopen row must remain REJECT: {code}")
        if row.get("research_reason") != EVIDENCE_BLOCKED_REASON:
            raise ValueError(f"urgent reopen row is not evidence-blocked: {code}")
        if row.get("reopen_on_new_evidence") is not True:
            raise ValueError(f"urgent row is not reopenable on evidence: {code}")
        if row.get("research_authority") != "RESEARCH_ONLY":
            raise ValueError(f"urgent row authority violation: {code}")
        if row.get("formal_buy_authorized") is not False:
            raise ValueError(f"urgent row unexpectedly authorizes Formal BUY: {code}")
        if row.get("no_auto_trade") is not True:
            raise ValueError(f"urgent row unexpectedly allows auto trade: {code}")
        if row.get("hard_gate_failures"):
            raise ValueError(f"evidence reopen must not contain known hard-gate failure: {code}")
        if code in seen:
            continue
        seen.add(code)
        selected.append(
            {
                "code": code,
                "name": str(row.get("name") or ""),
                "industry": str(row.get("industry") or ""),
                "research_priority": str(row.get("research_priority") or ""),
                "hard_gate_unknowns": list(row.get("hard_gate_unknowns") or []),
                "urgent_research_reasons": list(row.get("urgent_research_reasons") or []),
            }
        )

    selected.sort(
        key=lambda row: (
            0 if row["research_priority"] == "P0" else 1,
            row["code"],
        )
    )
    requested_codes = [row["code"] for row in selected]
    return {
        "contract": CONTRACT,
        "source_terminal_contract": TERMINAL_CONTRACT,
        "source_deep_lambda_run_id": str(payload.get("source_deep_lambda_run_id") or ""),
        "source_every_industry_run_id": str(payload.get("source_every_industry_run_id") or ""),
        "reopen_reason": "REFRESHED_EVIDENCE_EPOCH",
        "requested_count": len(requested_codes),
        "requested_codes": requested_codes,
        "rows": selected,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "automatic_gate_inference_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.terminal_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("terminal research payload must be an object")
    plan = build_reopen_plan(payload)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
