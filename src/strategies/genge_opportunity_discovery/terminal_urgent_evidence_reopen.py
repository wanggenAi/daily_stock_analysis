"""Build a fail-closed Deep-Lambda reopen plan from terminal urgent research.

A new evidence epoch should make urgent evidence-blocked names eligible for another
Deep Calculation pass, but it must not narrow the persisted terminal workset.
Therefore this planner re-dispatches the complete previous terminal workset whenever
at least one strict urgent evidence-blocked row exists. It never changes a gate,
never converts UNKNOWN to PASS, and never creates Formal/Production authority.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_TERMINAL_URGENT_EVIDENCE_REOPEN_V1"
TERMINAL_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
EVIDENCE_BLOCKED_REASON = "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
TERMINAL_DECISIONS = frozenset({"BUY", "WAIT_PRICE", "REJECT"})


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            text = text[len(prefix) :]
            break
    return text.zfill(6) if text.isdigit() else text


def _safe_terminal_row(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("terminal research row must be an object")
    row = dict(raw)
    code = _code(row.get("code"))
    if not code or not code.isdigit() or len(code) != 6:
        raise ValueError("terminal research row has invalid A-share code")
    decision = str(row.get("research_decision") or "").upper()
    if decision not in TERMINAL_DECISIONS:
        raise ValueError(f"terminal row has invalid research decision: {code}")
    if row.get("research_authority") != "RESEARCH_ONLY":
        raise ValueError(f"terminal row authority violation: {code}")
    if row.get("formal_buy_authorized") is not False:
        raise ValueError(f"terminal row unexpectedly authorizes Formal BUY: {code}")
    if row.get("no_auto_trade") is not True:
        raise ValueError(f"terminal row unexpectedly allows auto trade: {code}")
    row["code"] = code
    row["research_decision"] = decision
    return row


def _validate_terminal(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
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

    raw_rows = payload.get("terminal_rows")
    if not isinstance(raw_rows, list):
        raise ValueError("terminal_rows must be a list")
    rows = [_safe_terminal_row(raw) for raw in raw_rows]
    codes = [row["code"] for row in rows]
    if len(codes) != len(set(codes)):
        raise ValueError("terminal workset contains duplicate codes")

    requested_count = payload.get("requested_count")
    if requested_count is not None and int(requested_count) != len(rows):
        raise ValueError("terminal requested_count does not match terminal_rows")

    actual_counts = Counter(row["research_decision"] for row in rows)
    declared_counts = payload.get("decision_counts")
    if isinstance(declared_counts, Mapping):
        for decision in TERMINAL_DECISIONS:
            if int(declared_counts.get(decision) or 0) != actual_counts.get(decision, 0):
                raise ValueError("terminal decision_counts do not match terminal_rows")

    return rows, {row["code"]: row for row in rows}


def build_reopen_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reopen the complete terminal workset when strict urgent rows need new evidence.

    The complete previous terminal workset is preserved so the next Terminal run
    cannot accidentally shrink from N names to only the urgent subset. The urgent
    subset is validated separately and remains the reason the new evidence epoch is
    dispatched. Specialized industries are eligible for evidence recovery, while
    their downstream valuation rules remain authoritative.
    """
    terminal_rows, terminal_by_code = _validate_terminal(payload)
    urgent_rows: list[dict[str, Any]] = []
    urgent_seen: set[str] = set()
    raw_urgent = payload.get("urgent_research_queue") or []
    if not isinstance(raw_urgent, list):
        raise ValueError("urgent_research_queue must be a list")

    for raw in raw_urgent:
        if not isinstance(raw, Mapping):
            raise ValueError("urgent research row must be an object")
        code = _code(raw.get("code"))
        if code not in terminal_by_code:
            raise ValueError(f"urgent row is outside terminal workset: {code}")
        terminal = terminal_by_code[code]
        if raw.get("urgent_research") is not True or terminal.get("urgent_research") is not True:
            raise ValueError(f"urgent queue row is not marked urgent: {code}")
        if terminal.get("research_decision") != "REJECT":
            raise ValueError(f"urgent reopen row must remain REJECT: {code}")
        if terminal.get("research_reason") != EVIDENCE_BLOCKED_REASON:
            raise ValueError(f"urgent reopen row is not evidence-blocked: {code}")
        if terminal.get("reopen_on_new_evidence") is not True:
            raise ValueError(f"urgent row is not reopenable on evidence: {code}")
        if terminal.get("hard_gate_failures"):
            raise ValueError(f"evidence reopen must not contain known hard-gate failure: {code}")
        if code in urgent_seen:
            continue
        urgent_seen.add(code)
        urgent_rows.append(
            {
                "code": code,
                "name": str(terminal.get("name") or ""),
                "industry": str(terminal.get("industry") or ""),
                "research_priority": str(terminal.get("research_priority") or ""),
                "hard_gate_unknowns": list(terminal.get("hard_gate_unknowns") or []),
                "urgent_research_reasons": list(terminal.get("urgent_research_reasons") or []),
            }
        )

    urgent_rows.sort(
        key=lambda row: (
            0 if row["research_priority"] == "P0" else 1,
            row["code"],
        )
    )
    requested_codes = [row["code"] for row in terminal_rows]
    urgent_codes = [row["code"] for row in urgent_rows]
    return {
        "contract": CONTRACT,
        "source_terminal_contract": TERMINAL_CONTRACT,
        "source_deep_lambda_run_id": str(payload.get("source_deep_lambda_run_id") or ""),
        "source_every_industry_run_id": str(payload.get("source_every_industry_run_id") or ""),
        "reopen_reason": "URGENT_EVIDENCE_CONTINUITY_RECHECK",
        "requested_count": len(requested_codes),
        "requested_codes": requested_codes,
        "urgent_requested_count": len(urgent_codes),
        "urgent_requested_codes": urgent_codes,
        "urgent_rows": urgent_rows,
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
