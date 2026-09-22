"""Durable, fail-closed research strategy ledger for Jev-orchestrated Deep work.

The ledger tracks actual research scheduling, not trading authority.  A strategy
may be scheduled at most once for a code/hard-gate/evidence fingerprint.  A new
evidence fingerprint reopens the strategy; an unchanged fingerprint after a
later Jev evaluation closes the prior attempt as no-progress.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

CONTRACT = "GEN_GE_RESEARCH_STRATEGY_LEDGER_V1"

# These families describe the existing bounded Deep collectors.  They do not
# invent new evidence authority; they make the current collector family
# explicit so duplicate scheduling can be suppressed deterministically.
_GATE_STRATEGY = {
    "predictability": {
        "strategy_family": "STRICT_MULTI_YEAR_OFFICIAL_REPORT_REFRESH",
        "source_family": "OFFICIAL_EXCHANGE_DISCLOSURE",
        "query_family": "MULTI_YEAR_ANNUAL_REPORT",
    },
    "long_term_demand": {
        "strategy_family": "OFFICIAL_MULTI_SOURCE_INDUSTRY_DEMAND_REFRESH",
        "source_family": "OFFICIAL_GOVERNMENT_INDUSTRY_DATA",
        "query_family": "CURRENT_INDUSTRY_DEMAND",
    },
    "moat": {
        "strategy_family": "STRICT_MULTI_YEAR_OFFICIAL_MOAT_REFRESH",
        "source_family": "OFFICIAL_EXCHANGE_DISCLOSURE",
        "query_family": "MULTI_YEAR_DURABLE_MOAT",
    },
    "financial_safety": {
        "strategy_family": "SAME_RUN_PIT_FINANCIAL_SAFETY_REFRESH",
        "source_family": "OFFICIAL_COMPANY_FINANCIAL_DISCLOSURE",
        "query_family": "PIT_FINANCIAL_SAFETY",
    },
    "earnings_authenticity": {
        "strategy_family": "SAME_RUN_PIT_EARNINGS_AUTHENTICITY_REFRESH",
        "source_family": "OFFICIAL_COMPANY_FINANCIAL_DISCLOSURE",
        "query_family": "PIT_EARNINGS_AUTHENTICITY",
    },
}

_ACTIVE_ATTEMPT_STATUSES = {"DISPATCH_ACCEPTED"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _code(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit() and len(text) <= 6:
        return text.zfill(6)
    return text


def normalize_ledger(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a copy of a valid ledger or a new empty fail-closed ledger."""

    raw = dict(payload or {})
    entries = raw.get("entries")
    return {
        "contract": CONTRACT,
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "entries": [
            deepcopy(dict(item))
            for item in entries or []
            if isinstance(item, Mapping)
        ],
    }


def unresolved_gates(row: Mapping[str, Any]) -> dict[str, str]:
    context = _mapping(row.get("research_context"))
    result: dict[str, str] = {}
    for item in context.get("unresolved_gates") or []:
        if not isinstance(item, Mapping):
            continue
        gate = str(item.get("gate") or "").strip()
        if gate:
            result[gate] = str(item.get("reason") or "").strip()
    return result


def evidence_fingerprint(row: Mapping[str, Any]) -> str:
    return str(row.get("research_evidence_fingerprint") or "").strip()


def gate_evidence_fingerprint(
    row: Mapping[str, Any],
    *,
    gate: str,
    unresolved_reason: str,
) -> str:
    """Return a gate-local epoch so unrelated gate progress cannot reopen work."""

    context = _mapping(row.get("research_context"))
    statuses = _mapping(context.get("profile_gate_statuses"))
    status = _mapping(statuses.get(gate))
    payload = {
        "gate": str(gate or ""),
        "unresolved_reason": str(unresolved_reason or ""),
        "profile_gate_status": {
            "status": str(status.get("status") or ""),
            "confidence": str(status.get("confidence") or ""),
            "source": str(status.get("source") or ""),
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _same_attempt(
    entry: Mapping[str, Any],
    *,
    code: str,
    gate: str,
    strategy_family: str,
    fingerprint: str,
) -> bool:
    return (
        _code(entry.get("code")) == code
        and str(entry.get("hard_gate") or "") == gate
        and str(entry.get("strategy_family") or "") == strategy_family
        and str(entry.get("evidence_fingerprint") or "") == fingerprint
    )


def reconcile_ledger(
    payload: Mapping[str, Any] | None,
    routing_rows: list[Mapping[str, Any]],
    *,
    current_source_workflow_run_id: str,
) -> dict[str, Any]:
    """Close accepted attempts when a later research state is observable."""

    ledger = normalize_ledger(payload)
    by_code = {
        _code(row.get("entity_id")): row
        for row in routing_rows
        if isinstance(row, Mapping) and _code(row.get("entity_id"))
    }
    for entry in ledger["entries"]:
        if str(entry.get("attempt_status") or "") not in _ACTIVE_ATTEMPT_STATUSES:
            continue
        prior_source = str(entry.get("source_workflow_run_id") or "")
        if prior_source and prior_source == str(current_source_workflow_run_id or ""):
            continue
        code = _code(entry.get("code"))
        row = by_code.get(code)
        if row is None:
            continue

        # Do not judge an accepted attempt until the exact accepted Deep run is
        # visible in the later Jev state. A newer Jev workflow can start while
        # Deep is still running; treating that as "no progress" would exhaust a
        # strategy before its result exists.
        accepted_deep_run_id = str(entry.get("deep_run_id") or "")
        research_context = _mapping(row.get("research_context"))
        observed_deep_run_id = str(research_context.get("deep_lambda_run_id") or "")
        if accepted_deep_run_id and observed_deep_run_id != accepted_deep_run_id:
            continue

        gates = unresolved_gates(row)
        gate = str(entry.get("hard_gate") or "")
        previous_reason = str(entry.get("unresolved_reason") or "")
        current_reason = gates.get(gate)
        if current_reason is None:
            entry["attempt_status"] = "COMPLETED_GATE_RESOLVED"
            entry["new_evidence_acquired"] = None
            entry["gate_changed"] = True
            entry["strategy_exhausted"] = False
            continue

        current_fp = gate_evidence_fingerprint(
            row,
            gate=gate,
            unresolved_reason=current_reason,
        )
        if current_fp == str(entry.get("evidence_fingerprint") or ""):
            entry["attempt_status"] = "EXHAUSTED_NO_PROGRESS"
            entry["new_evidence_acquired"] = False
            entry["gate_changed"] = False
            entry["strategy_exhausted"] = True
            continue

        entry["new_evidence_acquired"] = True
        entry["gate_changed"] = current_reason != previous_reason
        entry["strategy_exhausted"] = False
        entry["result_evidence_fingerprint"] = current_fp
        entry["attempt_status"] = "COMPLETED_EVIDENCE_CHANGED"
    return ledger


def plan_strategy_attempts(
    row: Mapping[str, Any],
    ledger: Mapping[str, Any] | None,
    *,
    source_workflow_run_id: str,
    attempted_at: str | None = None,
) -> list[dict[str, Any]]:
    """Plan only never-before-used strategies for the current evidence epoch."""

    code = _code(row.get("entity_id"))
    stock_fingerprint = evidence_fingerprint(row)
    gates = unresolved_gates(row)
    if not code or not gates:
        return []

    normalized = normalize_ledger(ledger)
    attempts: list[dict[str, Any]] = []
    for gate, reason in sorted(gates.items()):
        spec = _GATE_STRATEGY.get(gate)
        if spec is None:
            continue
        fingerprint = gate_evidence_fingerprint(
            row,
            gate=gate,
            unresolved_reason=reason,
        )
        already_attempted = any(
            _same_attempt(
                entry,
                code=code,
                gate=gate,
                strategy_family=spec["strategy_family"],
                fingerprint=fingerprint,
            )
            for entry in normalized["entries"]
        )
        if already_attempted:
            continue
        attempts.append(
            {
                "code": code,
                "hard_gate": gate,
                "unresolved_reason": reason,
                **spec,
                "evidence_fingerprint": fingerprint,
                "evidence_epoch": fingerprint,
                "stock_evidence_fingerprint": stock_fingerprint,
                "attempt_status": "DISPATCH_PLANNED",
                "attempted_at": str(attempted_at or ""),
                "source_workflow_run_id": str(source_workflow_run_id or ""),
                "new_evidence_acquired": None,
                "gate_changed": None,
                "strategy_exhausted": False,
                "remaining_strategy_families": [],
                "formal_trading_authority": False,
                "no_auto_trade": True,
            }
        )
    return attempts


def append_attempts(
    ledger: Mapping[str, Any] | None,
    attempts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Append proposed attempts idempotently."""

    normalized = normalize_ledger(ledger)
    for raw in attempts:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        code = _code(row.get("code"))
        gate = str(row.get("hard_gate") or "")
        strategy = str(row.get("strategy_family") or "")
        fingerprint = str(row.get("evidence_fingerprint") or "")
        if not code or not gate or not strategy or not fingerprint:
            continue
        if any(
            _same_attempt(
                entry,
                code=code,
                gate=gate,
                strategy_family=strategy,
                fingerprint=fingerprint,
            )
            for entry in normalized["entries"]
        ):
            continue
        normalized["entries"].append(deepcopy(row))
    return normalized


def has_strategy_scope(row: Mapping[str, Any]) -> bool:
    """Whether this row has gate-level state that the ledger can govern."""

    return bool(unresolved_gates(row))
