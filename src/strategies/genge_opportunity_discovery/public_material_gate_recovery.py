"""Recover research hard gates from already-collected public material evidence.

This module does not invent PASS states. It only promotes a gate from UNKNOWN when the
incoming evidence payload explicitly contains a verified public-material gate result.
The terminal decision layer remains fail-closed for every other UNKNOWN.
"""
from __future__ import annotations

from typing import Any, Mapping

RECOVERABLE_GATES = ("predictability", "long_term_demand", "moat")
ALLOWED_STATUSES = {"PASS", "FAIL", "UNKNOWN"}


def recovered_gate_states(evidence_payload: Mapping[str, Any], code: str) -> dict[str, dict[str, Any]]:
    root = evidence_payload.get("public_material_gate_recovery")
    if not isinstance(root, Mapping):
        return {}
    stock = root.get(code)
    if not isinstance(stock, Mapping):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for gate in RECOVERABLE_GATES:
        raw = stock.get(gate)
        if not isinstance(raw, Mapping):
            continue
        status = str(raw.get("status") or "UNKNOWN").upper()
        if status not in ALLOWED_STATUSES:
            continue
        sources = raw.get("sources")
        verified = raw.get("verified", True)
        if verified is not True:
            continue
        if status == "PASS" and not (isinstance(sources, list) and any(str(x).strip() for x in sources)):
            continue
        out[gate] = {"status": status, "sources": list(sources or [])}
    return out


def merge_recovered_gates(profile: Mapping[str, Any], evidence_payload: Mapping[str, Any], code: str) -> dict[str, Any]:
    merged = dict(profile)
    gates = dict(profile.get("gates") or {}) if isinstance(profile.get("gates"), Mapping) else {}
    recovered = recovered_gate_states(evidence_payload, code)
    for gate, replacement in recovered.items():
        current = gates.get(gate) if isinstance(gates.get(gate), Mapping) else {}
        current_status = str(current.get("status") or "UNKNOWN").upper()
        # Never overwrite an explicit PASS/FAIL from the authoritative deep profile.
        if current_status != "UNKNOWN":
            continue
        gates[gate] = {
            **dict(current),
            **replacement,
            "recovered_from_public_material": True,
        }
    merged["gates"] = gates
    return merged
