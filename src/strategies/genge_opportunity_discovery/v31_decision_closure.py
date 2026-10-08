"""Reachable deep-research closure policy for GenGe V3.1.

This module separates *evidence completeness* from *decision completeness*.
It never converts UNKNOWN into PASS and never grants Formal/Production trading
authority.  The purpose is to stop treating one bounded non-critical UNKNOWN as
identical to an unsafe or fundamentally unresolved research state.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

CONTRACT = "GEN_GE_V31_DECISION_CLOSURE_V2"
CRITICAL_GATES = ("financial_safety", "earnings_authenticity")
SOFT_GATES = ("predictability", "long_term_demand", "moat")
ALL_GATES = CRITICAL_GATES + SOFT_GATES
MAX_SOFT_UNKNOWN_FOR_DECISION = 1

CLOSURE_STATES = {
    "FULL_EVIDENCE",
    "DECISION_READY_WITH_UNCERTAINTY",
    "RESEARCH_REQUIRED",
    "DECISIVE_REJECT",
}


def _names(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def classify_terminal_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one terminal row without promoting any gate status.

    Rules:
    - Any explicit gate FAIL / REJECT closes the *decision* as reject, even if
      unrelated evidence remains unknown.
    - BUY / WAIT_PRICE with no UNKNOWN is full-evidence closure.
    - After bounded retry, at most one UNKNOWN is tolerated only when it is a
      non-critical thesis gate and both capital-safety gates are proven (i.e.
      absent from unknown/failure lists).  This is research decision closure,
      not Formal BUY readiness.
    - Critical UNKNOWN, >1 soft UNKNOWN, missing profile, or non-evidence
      valuation gaps remain research-required.
    """
    decision = str(row.get("research_decision") or "").upper()
    reason = str(row.get("research_reason") or "").upper()
    failures = _names(row.get("hard_gate_failures"))
    unknowns = _names(row.get("hard_gate_unknowns"))
    failure_set = set(failures)
    unknown_set = set(unknowns)

    critical_unknowns = sorted(unknown_set.intersection(CRITICAL_GATES))
    soft_unknowns = sorted(unknown_set.intersection(SOFT_GATES))
    other_unknowns = sorted(unknown_set.difference(ALL_GATES))
    critical_failures = sorted(failure_set.intersection(CRITICAL_GATES))

    evidence_complete = not unknowns
    decision_ready = False
    state = "RESEARCH_REQUIRED"
    rationale = "MATERIAL_RESEARCH_GAPS_REMAIN"

    if failures or decision == "REJECT":
        state = "DECISIVE_REJECT"
        decision_ready = True
        rationale = "NEGATIVE_DECISION_IS_CLOSED_BY_EXPLICIT_FAILURE"
    elif decision in {"BUY", "WAIT_PRICE"} and not unknowns:
        state = "FULL_EVIDENCE"
        decision_ready = True
        rationale = "ALL_DEEP_GATES_RESOLVED"
    elif (
        decision == "RESEARCH_GAP"
        and reason == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
        and not critical_unknowns
        and not critical_failures
        and not other_unknowns
        and 0 < len(soft_unknowns) <= MAX_SOFT_UNKNOWN_FOR_DECISION
    ):
        state = "DECISION_READY_WITH_UNCERTAINTY"
        decision_ready = True
        rationale = "BOUNDED_NONCRITICAL_UNCERTAINTY_AFTER_RETRY"
    elif critical_unknowns:
        rationale = "CRITICAL_CAPITAL_GATE_UNKNOWN"
    elif len(soft_unknowns) > MAX_SOFT_UNKNOWN_FOR_DECISION:
        rationale = "TOO_MANY_NONCRITICAL_UNKNOWNS"
    elif reason == "DEEP_PROFILE_MISSING":
        rationale = "DEEP_PROFILE_MISSING"
    elif reason in {
        "SPECIALIZED_VALUATION_REQUIRED",
        "VALUATION_FINANCIAL_EVIDENCE_INCOMPLETE",
        "VALUATION_REFERENCE_INCOMPLETE",
    }:
        rationale = reason

    return {
        "contract": CONTRACT,
        "closure_state": state,
        "decision_ready": decision_ready,
        "evidence_complete": evidence_complete,
        "formal_buy_evidence_ready": state == "FULL_EVIDENCE" and decision == "BUY",
        "critical_unknown_gates": critical_unknowns,
        "soft_unknown_gates": soft_unknowns,
        "other_unknown_gates": other_unknowns,
        "failure_gates": sorted(failure_set),
        "max_soft_unknown_for_decision": MAX_SOFT_UNKNOWN_FOR_DECISION,
        "rationale": rationale,
        "unknown_is_pass": False,
        "formal_buy_authorized": False,
        "automatic_execution_allowed": False,
        "no_auto_trade": True,
    }


def enrich_terminal_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Attach closure V2 to terminal output and de-escalate solved retry loops."""
    out = dict(payload)
    if out.get("unknown_is_pass") is not False:
        raise ValueError("terminal payload must preserve UNKNOWN != PASS")
    if out.get("formal_trading_authority") is not False:
        raise ValueError("terminal payload must not grant formal trading authority")
    if out.get("no_auto_trade") is not True:
        raise ValueError("terminal payload must preserve no-auto-trade")

    rows_raw = out.get("terminal_rows") or []
    if not isinstance(rows_raw, list):
        raise ValueError("terminal_rows must be a list")

    rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    decision_ready_count = 0
    evidence_complete_count = 0
    bounded_ready_codes: list[str] = []
    research_required_codes: list[str] = []

    for raw in rows_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("terminal row must be an object")
        row = dict(raw)
        closure = classify_terminal_row(row)
        row["deep_closure"] = closure
        rows.append(row)
        state = closure["closure_state"]
        state_counts[state] += 1
        if closure["decision_ready"]:
            decision_ready_count += 1
        if closure["evidence_complete"]:
            evidence_complete_count += 1
        code = str(row.get("code") or "")
        if state == "DECISION_READY_WITH_UNCERTAINTY":
            bounded_ready_codes.append(code)
        elif state == "RESEARCH_REQUIRED":
            research_required_codes.append(code)

    row_by_code = {str(row.get("code") or ""): row for row in rows}
    # Do not keep bounded-soft-uncertainty names in the urgent evidence loop.
    # They can reopen on material new evidence, but they are no longer an
    # immediate research blocker.
    urgent_rows: list[dict[str, Any]] = []
    for raw in out.get("urgent_research_queue") or []:
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("code") or "")
        row = row_by_code.get(code)
        closure = (row or {}).get("deep_closure") or {}
        if closure.get("closure_state") == "DECISION_READY_WITH_UNCERTAINTY":
            continue
        urgent_rows.append(dict(raw))

    requested = int(out.get("requested_count") or len(rows))
    if requested != len(rows):
        raise ValueError("requested_count does not match terminal_rows")

    closure_counts = {state: int(state_counts.get(state, 0)) for state in sorted(CLOSURE_STATES)}
    out["terminal_rows"] = rows
    out["urgent_research_queue"] = urgent_rows
    out["decision_closure_contract"] = CONTRACT
    out["decision_closure_counts"] = closure_counts
    out["decision_ready_count"] = decision_ready_count
    out["evidence_complete_count"] = evidence_complete_count
    out["bounded_uncertainty_ready_count"] = closure_counts["DECISION_READY_WITH_UNCERTAINTY"]
    out["research_required_count"] = closure_counts["RESEARCH_REQUIRED"]
    out["decisive_reject_count"] = closure_counts["DECISIVE_REJECT"]
    out["decision_ready_rate"] = round(decision_ready_count / requested, 4) if requested else 1.0
    out["evidence_complete_rate"] = round(evidence_complete_count / requested, 4) if requested else 1.0
    out["bounded_uncertainty_ready_codes"] = sorted(c for c in bounded_ready_codes if c)
    out["research_required_codes"] = sorted(c for c in research_required_codes if c)
    out["closure_policy"] = {
        "critical_gates": list(CRITICAL_GATES),
        "soft_gates": list(SOFT_GATES),
        "max_soft_unknown_for_decision": MAX_SOFT_UNKNOWN_FOR_DECISION,
        "unknown_is_pass": False,
        "formal_buy_requires_full_evidence": True,
        "automatic_execution_allowed": False,
        "no_auto_trade": True,
    }
    return out


def render_closure_markdown(payload: Mapping[str, Any]) -> str:
    counts = payload.get("decision_closure_counts") or {}
    lines = [
        "# GenGe V3.1 Deep Decision Closure V2",
        "",
        f"- decision ready: **{payload.get('decision_ready_count', 0)}/{payload.get('requested_count', 0)}** ({payload.get('decision_ready_rate', 0):.1%})",
        f"- evidence complete: **{payload.get('evidence_complete_count', 0)}/{payload.get('requested_count', 0)}** ({payload.get('evidence_complete_rate', 0):.1%})",
        f"- FULL_EVIDENCE: **{counts.get('FULL_EVIDENCE', 0)}**",
        f"- DECISION_READY_WITH_UNCERTAINTY: **{counts.get('DECISION_READY_WITH_UNCERTAINTY', 0)}**",
        f"- DECISIVE_REJECT: **{counts.get('DECISIVE_REJECT', 0)}**",
        f"- RESEARCH_REQUIRED: **{counts.get('RESEARCH_REQUIRED', 0)}**",
        "- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.",
        "",
    ]
    for row in payload.get("terminal_rows") or []:
        closure = row.get("deep_closure") or {}
        lines.append(
            f"- {row.get('code')} {row.get('name') or ''}: **{closure.get('closure_state')}**; "
            f"decision_ready={closure.get('decision_ready')}; unknown={','.join(row.get('hard_gate_unknowns') or []) or 'NONE'}"
        )
    return "\n".join(lines) + "\n"
