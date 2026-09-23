"""Deterministic bridge from Jev advisory routing to bounded research execution.

Jev remains advisory-only. This module may authorize a bounded *research* dispatch
only when Jev routing and existing deterministic triage agree. It can never
create or mutate Formal trading actions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.strategies.genge_opportunity_discovery.research_strategy_ledger import (
    append_attempts,
    current_strategy_exhaustion,
    has_strategy_scope,
    plan_strategy_attempts,
    reconcile_ledger,
)

CONTRACT = "GEN_GE_JEV_RESEARCH_ORCHESTRATION_V1"
ROUTING_CONTRACT = "GEN_GE_JEV_ROUTING_BRIDGE_V1"
AUTO_RESEARCH_ROUTES = {"EVIDENCE_REFRESH", "DEEP_RESEARCH"}
ALLOWED_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
MIN_AUTO_ROUTE_CONFIDENCE = 0.5
_DETERMINISTIC_PRIORITY = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_ATTENTION_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
_ROUTE_RANK = {"DEEP_RESEARCH": 0, "EVIDENCE_REFRESH": 1}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _code(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit() and len(text) <= 6:
        return text.zfill(6)
    return text


def _routing_guardrails_ok(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("contract") == ROUTING_CONTRACT
        and payload.get("execution_status") == "SUCCESS"
        and payload.get("authority") == "ADVISORY_RESEARCH_ROUTING_ONLY"
        and payload.get("automatic_dispatch_allowed") is False
        and payload.get("automatic_formal_buy_allowed") is False
        and payload.get("formal_trading_authority") is False
        and payload.get("mutates_authoritative_decision") is False
        and payload.get("may_suppress_existing_research") is False
        and payload.get("may_create_or_mutate_formal_action") is False
        and payload.get("unknown_is_pass") is False
        and payload.get("no_auto_trade") is True
    )


def _eligible_by_deterministic_triage(row: Mapping[str, Any]) -> bool:
    triage = _mapping(row.get("triage_context"))
    priority = str(triage.get("research_priority") or "").strip().upper()
    return (
        row.get("is_current_holding") is True
        or triage.get("urgent_research") is True
        or priority in {"P0", "P1", "P2"}
    )


def _sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    triage = _mapping(row.get("triage_context"))
    deterministic_priority = str(triage.get("research_priority") or "").strip().upper()
    route_confidence = row.get("route_confidence")
    route_confidence_value = (
        float(route_confidence) if isinstance(route_confidence, (int, float)) else 0.0
    )
    return (
        0 if row.get("is_current_holding") is True else 1,
        _ATTENTION_RANK.get(str(row.get("attention_priority") or ""), 99),
        _DETERMINISTIC_PRIORITY.get(deterministic_priority, 9),
        0 if triage.get("urgent_research") is True else 1,
        _ROUTE_RANK.get(str(row.get("route") or ""), 99),
        -route_confidence_value,
        _code(row.get("entity_id")),
    )


def build_orchestration_plan(
    routing_payload: Mapping[str, Any],
    *,
    max_dispatch: int = 12,
    strategy_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bounded research-only dispatch plan from persisted Jev routing."""

    max_dispatch = max(1, min(int(max_dispatch), 50))
    base: dict[str, Any] = {
        "contract": CONTRACT,
        "source_contract": routing_payload.get("contract"),
        "source_generated_at": routing_payload.get("generated_at"),
        "source_workflow_run_id": str(routing_payload.get("source_workflow_run_id") or ""),
        "source_workflow_run_attempt": str(
            routing_payload.get("source_workflow_run_attempt") or ""
        ),
        "source_workflow_head_sha": str(
            routing_payload.get("source_workflow_head_sha") or ""
        ),
        "authority": "DETERMINISTIC_RESEARCH_ORCHESTRATOR",
        "jev_direct_dispatch_allowed": False,
        "automatic_research_dispatch_allowed": True,
        "dispatch_is_research_only": True,
        "dispatch_target": "genge-v31-deep-calculation-lambda.yml",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "mutates_authoritative_decision": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "max_dispatch": max_dispatch,
        "min_auto_route_confidence": MIN_AUTO_ROUTE_CONFIDENCE,
        "selected": [],
        "human_review": [],
        "skipped": [],
        "lifecycle_transitions": [],
    }

    if not _routing_guardrails_ok(routing_payload):
        base["execution_status"] = "REFUSED_ROUTING_GUARDRAIL_MISMATCH"
        base["should_dispatch"] = False
        base["requested_codes"] = []
        base["requested_codes_csv"] = ""
        return base

    source_workflow_run_id = str(routing_payload.get("source_workflow_run_id") or "")
    reconciled_ledger = reconcile_ledger(
        strategy_ledger,
        [
            row
            for row in (routing_payload.get("routing_queue") or [])
            if isinstance(row, Mapping)
        ],
        current_source_workflow_run_id=source_workflow_run_id,
    )
    attempted_at = str(
        routing_payload.get("generated_at")
        or routing_payload.get("source_generated_at")
        or ""
    )

    candidates: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for raw in routing_payload.get("routing_queue") or []:
        if not isinstance(raw, Mapping):
            continue
        code = _code(raw.get("entity_id"))
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        route = str(raw.get("route") or "").strip().upper()
        attention = str(raw.get("attention_priority") or "").strip().upper()
        triage = dict(_mapping(raw.get("triage_context")))
        row = {
            "entity_id": code,
            "entity_name": str(raw.get("entity_name") or ""),
            "is_current_holding": raw.get("is_current_holding") is True,
            "existing_engine_action": str(raw.get("existing_engine_action") or ""),
            "route": route,
            "route_confidence": raw.get("route_confidence"),
            "attention_priority": attention,
            "attention_confidence": raw.get("attention_confidence"),
            "evidence_state": str(raw.get("evidence_state") or ""),
            "needs_more_evidence": raw.get("needs_more_evidence"),
            "needs_deep_research": raw.get("needs_deep_research"),
            "triage_context": triage,
            "research_context": dict(_mapping(raw.get("research_context"))),
            "research_evidence_fingerprint": str(
                raw.get("research_evidence_fingerprint") or ""
            ),
            "research_authority": "ORCHESTRATED_RESEARCH_ONLY",
            "formal_trading_authority": False,
            "no_auto_trade": True,
        }

        deterministic_eligible = _eligible_by_deterministic_triage(raw)
        strategy_attempts = plan_strategy_attempts(
            row,
            reconciled_ledger,
            source_workflow_run_id=source_workflow_run_id,
            attempted_at=attempted_at,
        )
        row["strategy_attempts"] = strategy_attempts
        strategy_scope = has_strategy_scope(row)
        exhaustion = current_strategy_exhaustion(row, reconciled_ledger)
        row["research_strategy_exhaustion"] = exhaustion
        lifecycle_state = str(triage.get("candidate_lifecycle_state") or "").strip().upper()
        row["candidate_lifecycle_state"] = lifecycle_state
        reactivation_epochs = sorted(
            {
                str(item.get("evidence_epoch") or "")
                for item in strategy_attempts
                if str(item.get("evidence_epoch") or "")
            }
        )
        if lifecycle_state == "DORMANT" and reactivation_epochs:
            row["pending_lifecycle_reactivation"] = {
                "event": "RESEARCH_REACTIVATED",
                "code": code,
                "evidence_id": (
                    f"jev-reactivation:{source_workflow_run_id}:{code}:"
                    + "|".join(reactivation_epochs)
                ),
                "reason": "new hard-gate evidence epoch reopened a bounded research strategy",
                "is_current_holding": False,
                "research_evidence_changed": True,
                "research_evidence_epoch": "|".join(reactivation_epochs),
                "source_run_id": source_workflow_run_id,
                "expected_prior_lifecycle_state": "DORMANT",
            }
        if (
            lifecycle_state == "ACTIVE"
            and exhaustion.get("exhausted") is True
            and row["is_current_holding"] is False
        ):
            base["lifecycle_transitions"].append(
                {
                    "event": "RESEARCH_EXHAUSTED",
                    "code": code,
                    "evidence_id": (
                        f"jev-exhaustion:{source_workflow_run_id}:{code}:"
                        f"{exhaustion.get('closure_epoch') or 'unknown'}"
                    ),
                    "reason": "all supported hard-gate strategies exhausted for the current evidence epoch",
                    "is_current_holding": False,
                    "research_evidence_changed": False,
                    "research_evidence_epoch": str(exhaustion.get("closure_epoch") or ""),
                    "source_run_id": source_workflow_run_id,
                    "expected_prior_lifecycle_state": "ACTIVE",
                }
            )

        ruleable_insufficient_evidence = (
            str(raw.get("evidence_state") or "").strip().upper() == "INSUFFICIENT"
            and deterministic_eligible
            and attention in {"HIGH", "MEDIUM"}
        )

        if route == "HUMAN_REVIEW":
            if ruleable_insufficient_evidence:
                if strategy_scope and not strategy_attempts:
                    base["skipped"].append(
                        {
                            "entity_id": code,
                            "entity_name": row["entity_name"],
                            "route": route,
                            "attention_priority": attention,
                            "reason": (
                                "RESEARCH_STRATEGIES_EXHAUSTED_DORMANT"
                                if exhaustion.get("exhausted") is True and row["is_current_holding"] is False
                                else "NO_NOVEL_RESEARCH_STRATEGY_IN_EVIDENCE_EPOCH"
                            ),
                        }
                    )
                    continue
                row["jev_route"] = "HUMAN_REVIEW"
                row["route"] = "EVIDENCE_REFRESH"
                row["dispatch_mode"] = "DETERMINISTIC_SAFE_FALLBACK"
                row["fallback_reason"] = (
                    "RULEABLE_INSUFFICIENT_EVIDENCE_DOES_NOT_REQUIRE_HUMAN_STOP"
                )
                candidates.append(row)
                continue
            row["review_reason"] = "JEV_ROUTE_HUMAN_REVIEW"
            base["human_review"].append(row)
            continue

        route_confidence = raw.get("route_confidence")
        route_confidence_ok = (
            isinstance(route_confidence, (int, float))
            and float(route_confidence) >= MIN_AUTO_ROUTE_CONFIDENCE
        )
        if (
            route in AUTO_RESEARCH_ROUTES
            and attention in {"HIGH", "MEDIUM"}
            and deterministic_eligible
        ):
            if strategy_scope and not strategy_attempts:
                base["skipped"].append(
                    {
                        "entity_id": code,
                        "entity_name": row["entity_name"],
                        "route": route,
                        "attention_priority": attention,
                        "reason": (
                            "RESEARCH_STRATEGIES_EXHAUSTED_DORMANT"
                            if exhaustion.get("exhausted") is True and row["is_current_holding"] is False
                            else "NO_NOVEL_RESEARCH_STRATEGY_IN_EVIDENCE_EPOCH"
                        ),
                    }
                )
                continue
            if not route_confidence_ok:
                if ruleable_insufficient_evidence:
                    row["dispatch_mode"] = "DETERMINISTIC_SAFE_FALLBACK"
                    row["fallback_reason"] = "LOW_OR_MISSING_JEV_ROUTE_CONFIDENCE"
                    candidates.append(row)
                    continue
                row["review_reason"] = "LOW_OR_MISSING_ROUTE_CONFIDENCE"
                base["human_review"].append(row)
                continue
            row["dispatch_mode"] = "JEV_AND_DETERMINISTIC_AGREEMENT"
            candidates.append(row)
            continue

        reason = "NOT_DETERMINISTICALLY_ELIGIBLE"
        if route not in AUTO_RESEARCH_ROUTES:
            reason = "ROUTE_NOT_AUTO_RESEARCH"
        elif attention not in {"HIGH", "MEDIUM"}:
            reason = "ATTENTION_BELOW_AUTO_RESEARCH"
        base["skipped"].append(
            {
                "entity_id": code,
                "entity_name": row["entity_name"],
                "route": route,
                "attention_priority": attention,
                "reason": reason,
            }
        )

    candidates.sort(key=_sort_key)
    selected = candidates[:max_dispatch]
    overflow = candidates[max_dispatch:]
    for row in selected:
        transition = row.pop("pending_lifecycle_reactivation", None)
        if isinstance(transition, Mapping):
            base["lifecycle_transitions"].append(dict(transition))
    for row in overflow:
        base["skipped"].append(
            {
                "entity_id": row["entity_id"],
                "entity_name": row["entity_name"],
                "route": row["route"],
                "attention_priority": row["attention_priority"],
                "reason": "MAX_DISPATCH_BOUND",
            }
        )

    base["selected"] = selected
    base["human_review"].sort(key=_sort_key)
    planned_strategy_attempts = [
        attempt
        for row in selected
        for attempt in (row.get("strategy_attempts") or [])
        if isinstance(attempt, Mapping)
    ]
    base["strategy_ledger"] = append_attempts(
        reconciled_ledger,
        planned_strategy_attempts,
    )
    requested_codes = [str(row["entity_id"]) for row in selected]
    base["requested_codes"] = requested_codes
    base["requested_codes_csv"] = ",".join(requested_codes)
    base["should_dispatch"] = bool(requested_codes)
    base["execution_status"] = "READY" if requested_codes else "NOOP"
    base["summary"] = {
        "selected_count": len(selected),
        "human_review_count": len(base["human_review"]),
        "skipped_count": len(base["skipped"]),
        "holding_selected_count": sum(
            1 for row in selected if row.get("is_current_holding") is True
        ),
        "evidence_refresh_count": sum(
            1 for row in selected if row.get("route") == "EVIDENCE_REFRESH"
        ),
        "deep_research_count": sum(
            1 for row in selected if row.get("route") == "DEEP_RESEARCH"
        ),
        "deterministic_fallback_count": sum(
            1
            for row in selected
            if row.get("dispatch_mode") == "DETERMINISTIC_SAFE_FALLBACK"
        ),
        "strategy_attempt_count": len(planned_strategy_attempts),
        "strategy_ledger_entry_count": len(
            base["strategy_ledger"].get("entries") or []
        ),
        "lifecycle_transition_count": len(base["lifecycle_transitions"]),
        "research_exhausted_dormant_count": sum(
            1 for item in base["lifecycle_transitions"] if item.get("event") == "RESEARCH_EXHAUSTED"
        ),
        "research_reactivated_count": sum(
            1 for item in base["lifecycle_transitions"] if item.get("event") == "RESEARCH_REACTIVATED"
        ),
    }
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--max-dispatch", type=int, default=12)
    parser.add_argument("--strategy-ledger-json", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.routing_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("routing payload must be a JSON object")
    ledger_payload: dict[str, Any] = {}
    if args.strategy_ledger_json and args.strategy_ledger_json.is_file():
        raw_ledger = json.loads(args.strategy_ledger_json.read_text(encoding="utf-8"))
        if not isinstance(raw_ledger, dict):
            raise ValueError("strategy ledger must be a JSON object")
        ledger_payload = raw_ledger
    plan = build_orchestration_plan(
        payload,
        max_dispatch=args.max_dispatch,
        strategy_ledger=ledger_payload,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(plan.get("summary") or {}, ensure_ascii=False, sort_keys=True))
    if args.require_ready and plan.get("execution_status") not in {"READY", "NOOP"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
