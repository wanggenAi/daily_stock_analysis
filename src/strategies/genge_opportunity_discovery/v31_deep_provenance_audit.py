"""Audit terminal V3.1 deep-review profiles for evidence-backed PASS provenance.

This module is observability/safety only. It never promotes a gate, creates a
Formal BUY, or places a trade. A terminal PASS is considered verified only when
it has both a resolved provenance source and at least one structured evidence
record. UNKNOWN remains UNKNOWN.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_V31_DEEP_PROVENANCE_AUDIT_V1"
GATES = (
    "predictability",
    "long_term_demand",
    "moat",
    "financial_safety",
    "earnings_authenticity",
)
UNRESOLVED_SOURCES = frozenset(
    {
        "",
        "UNRESOLVED",
        "AUTOMATIC_ATTEMPT",
        "QUALITATIVE_EVIDENCE_REQUIRED",
        "PROVENANCE_GUARD",
    }
)


def _status(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper()
    return text if text in {"PASS", "FAIL"} else "UNKNOWN"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _evidence_count(gate: Mapping[str, Any]) -> int:
    evidence = gate.get("evidence")
    if not isinstance(evidence, list):
        return 0
    return sum(1 for row in evidence if isinstance(row, Mapping) and bool(row))


def audit_profiles(
    payload: Mapping[str, Any],
    *,
    audit_run_id: str = "",
    audit_workflow: str = "",
    audit_run_attempt: str = "",
    audit_event: str = "",
) -> dict[str, Any]:
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ValueError("deep-review profiles must be an object")

    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    unverified: list[dict[str, Any]] = []
    verified_passes = 0
    hard_gate_count = 0

    for raw_code, raw_profile in profiles.items():
        code = str(raw_code)
        profile = raw_profile if isinstance(raw_profile, Mapping) else {}
        gates = profile.get("gates") if isinstance(profile.get("gates"), Mapping) else {}
        for gate_name in GATES:
            raw_gate = gates.get(gate_name)
            gate = raw_gate if isinstance(raw_gate, Mapping) else {}
            state = _status(gate.get("status"))
            hard_gate_count += 1
            status_counts[state] += 1
            source = str(gate.get("source") or "").strip().upper()
            source_counts[source or "UNSPECIFIED"] += 1
            if state != "PASS":
                continue
            evidence_count = _evidence_count(gate)
            source_ok = source not in UNRESOLVED_SOURCES
            evidence_ok = evidence_count > 0
            if source_ok and evidence_ok:
                verified_passes += 1
            else:
                unverified.append(
                    {
                        "code": code,
                        "gate": gate_name,
                        "source": source or "UNSPECIFIED",
                        "evidence_count": evidence_count,
                    }
                )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "contract": CONTRACT,
        "generated_at": now,
        "audit_run_id": str(audit_run_id or ""),
        "audit_workflow": str(audit_workflow or ""),
        "audit_run_attempt": str(audit_run_attempt or ""),
        "audit_event": str(audit_event or ""),
        "profile_count": len(profiles),
        "hard_gate_count": hard_gate_count,
        "pass_gate_count": status_counts["PASS"],
        "unknown_gate_count": status_counts["UNKNOWN"],
        "fail_gate_count": status_counts["FAIL"],
        "verified_pass_gate_count": verified_passes,
        "unverified_pass_gate_count": len(unverified),
        "all_pass_gates_have_verified_evidence": not unverified,
        "unverified_passes": unverified[:100],
        "gate_source_counts": dict(sorted(source_counts.items())),
        "initial_reverified_upstream_pass_count": _int(
            payload.get("reverified_upstream_pass_count")
        ),
        "initial_unverified_pass_downgraded_count": _int(
            payload.get("unverified_pass_downgraded_count")
        ),
        "initial_verified_pass_gate_count": _int(
            payload.get("verified_pass_gate_count")
        ),
        "initial_unverified_pass_gate_count": _int(
            payload.get("unverified_pass_gate_count")
        ),
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }


def augment_status(
    status: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    expected_lambda_run_id: str = "",
) -> dict[str, Any]:
    current = str(status.get("lambda_run_id") or "")
    expected = str(expected_lambda_run_id or "")
    if expected and current != expected:
        raise ValueError(
            f"deep status lambda_run_id mismatch: expected={expected} actual={current}"
        )
    if status.get("unknown_is_pass") is not False:
        raise ValueError("deep status must preserve UNKNOWN != PASS")
    if status.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("automatic Formal BUY must remain disabled")
    if status.get("formal_trading_authority") is not False:
        raise ValueError("deep research must not gain formal trading authority")
    if status.get("no_auto_trade") is not True:
        raise ValueError("no_auto_trade must remain true")
    if audit.get("all_pass_gates_have_verified_evidence") is not True:
        raise ValueError(
            f"terminal deep profile contains {audit.get('unverified_pass_gate_count')} unverified PASS gates"
        )

    out = dict(status)
    out.update(
        {
            "provenance_audit_contract": audit.get("contract"),
            "provenance_audit_generated_at": audit.get("generated_at"),
            "provenance_audit_run_id": str(audit.get("audit_run_id") or ""),
            "provenance_audit_workflow": str(audit.get("audit_workflow") or ""),
            "provenance_audit_run_attempt": str(audit.get("audit_run_attempt") or ""),
            "provenance_audit_event": str(audit.get("audit_event") or ""),
            "provenance_audit_complete": True,
            "profile_count": audit.get("profile_count"),
            "hard_gate_count": audit.get("hard_gate_count"),
            "pass_gate_count": audit.get("pass_gate_count"),
            "unknown_gate_count": audit.get("unknown_gate_count"),
            "fail_gate_count": audit.get("fail_gate_count"),
            "verified_pass_gate_count": audit.get("verified_pass_gate_count"),
            "unverified_pass_gate_count": audit.get("unverified_pass_gate_count"),
            "all_pass_gates_have_verified_evidence": True,
            "gate_source_counts": audit.get("gate_source_counts", {}),
            "initial_reverified_upstream_pass_count": audit.get(
                "initial_reverified_upstream_pass_count", 0
            ),
            "initial_unverified_pass_downgraded_count": audit.get(
                "initial_unverified_pass_downgraded_count", 0
            ),
            "initial_verified_pass_gate_count": audit.get(
                "initial_verified_pass_gate_count", 0
            ),
            "initial_unverified_pass_gate_count": audit.get(
                "initial_unverified_pass_gate_count", 0
            ),
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-json", type=Path, required=True)
    parser.add_argument("--status-json", type=Path, required=True)
    parser.add_argument("--output-status", type=Path, required=True)
    parser.add_argument("--output-audit", type=Path, required=True)
    parser.add_argument("--expected-lambda-run-id", default="")
    parser.add_argument("--audit-run-id", default="")
    parser.add_argument("--audit-workflow", default="")
    parser.add_argument("--audit-run-attempt", default="")
    parser.add_argument("--audit-event", default="")
    args = parser.parse_args()

    profiles = json.loads(args.profiles_json.read_text(encoding="utf-8"))
    status = json.loads(args.status_json.read_text(encoding="utf-8"))
    audit = audit_profiles(
        profiles,
        audit_run_id=args.audit_run_id,
        audit_workflow=args.audit_workflow,
        audit_run_attempt=args.audit_run_attempt,
        audit_event=args.audit_event,
    )
    args.output_audit.parent.mkdir(parents=True, exist_ok=True)
    args.output_audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    augmented = augment_status(
        status,
        audit,
        expected_lambda_run_id=args.expected_lambda_run_id,
    )
    args.output_status.parent.mkdir(parents=True, exist_ok=True)
    args.output_status.write_text(
        json.dumps(augmented, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
