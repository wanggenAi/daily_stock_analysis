"""Build a durable advisory research-routing plan from Jev shadow output.

This bridge is intentionally non-authoritative. It may summarize and prioritize
research routes, but it cannot dispatch research, suppress deterministic work,
mutate Formal decisions, or authorize trades.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

CONTRACT = "GEN_GE_JEV_ROUTING_BRIDGE_V1"
SHADOW_CONTRACT = "GEN_GE_JEV_SHADOW_DECISION_V1"
ALLOWED_ROUTES = {
    "NO_ESCALATION",
    "EVIDENCE_REFRESH",
    "DEEP_RESEARCH",
    "VALUATION_CLOSURE",
    "HUMAN_REVIEW",
}
ALLOWED_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}
ALLOWED_EVIDENCE_STATES = {
    "ADEQUATE_FOR_CURRENT_RESEARCH_STATE",
    "INSUFFICIENT",
    "CONFLICTED",
    "STALE_OR_LINEAGE_UNCLEAR",
}
_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
_ROUTE_RANK = {
    "HUMAN_REVIEW": 0,
    "VALUATION_CLOSURE": 1,
    "DEEP_RESEARCH": 2,
    "EVIDENCE_REFRESH": 3,
    "NO_ESCALATION": 4,
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _choice(
    decisions: Mapping[str, Any],
    key: str,
    allowed: set[str],
) -> tuple[str | None, float | None, dict[str, float]]:
    raw = _mapping(decisions.get(key))
    choice = str(raw.get("choice") or "").strip().upper()
    if choice not in allowed:
        return None, None, {}
    confidence = raw.get("confidence")
    probabilities_raw = _mapping(raw.get("probabilities"))
    probabilities = {
        str(label): round(float(value), 6)
        for label, value in probabilities_raw.items()
        if str(label) in allowed and isinstance(value, (int, float))
    }
    return (
        choice,
        float(confidence) if isinstance(confidence, (int, float)) else None,
        probabilities,
    )


def _binary(
    decisions: Mapping[str, Any],
    key: str,
) -> tuple[bool | None, float | None]:
    raw = _mapping(decisions.get(key))
    answer = raw.get("answer")
    if not isinstance(answer, bool):
        return None, None
    confidence = raw.get("confidence")
    return answer, float(confidence) if isinstance(confidence, (int, float)) else None


def _global_guardrails_ok(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("authority") == "SHADOW_ONLY"
        and payload.get("formal_trading_authority") is False
        and payload.get("automatic_formal_buy_allowed") is False
        and payload.get("mutates_authoritative_decision") is False
        and payload.get("unknown_is_pass") is False
        and payload.get("no_auto_trade") is True
        and payload.get("shadow_mode") is True
    )


def build_routing_bridge(shadow_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a successful Jev shadow payload into an advisory routing queue."""

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    base: dict[str, Any] = {
        "contract": CONTRACT,
        "source_contract": shadow_payload.get("contract"),
        "generated_at": now,
        "source_generated_at": shadow_payload.get("generated_at"),
        "source_requested_model": shadow_payload.get("requested_model"),
        "authority": "ADVISORY_RESEARCH_ROUTING_ONLY",
        "research_authority": "DETERMINISTIC_SYSTEM_REMAINS_AUTHORITATIVE",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "automatic_dispatch_allowed": False,
        "mutates_authoritative_decision": False,
        "may_suppress_existing_research": False,
        "may_create_or_mutate_formal_action": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "routing_queue": [],
        "invalid_rows": [],
    }

    if shadow_payload.get("contract") != SHADOW_CONTRACT:
        base["execution_status"] = "REFUSED_SHADOW_CONTRACT_MISMATCH"
        return _finalize(base)

    if shadow_payload.get("execution_status") != "SUCCESS":
        base["execution_status"] = "REFUSED_SHADOW_NOT_SUCCESS"
        return _finalize(base)

    if not _global_guardrails_ok(shadow_payload):
        base["execution_status"] = "REFUSED_GUARDRAIL_MISMATCH"
        return _finalize(base)

    for raw_row in shadow_payload.get("rows") or []:
        if not isinstance(raw_row, Mapping):
            continue
        if raw_row.get("status") != "SUCCESS":
            continue
        if (
            raw_row.get("formal_trading_authority") is not False
            or raw_row.get("mutates_authoritative_decision") is not False
            or raw_row.get("unknown_is_pass") is not False
            or raw_row.get("no_auto_trade") is not True
        ):
            base["invalid_rows"].append(
                {
                    "entity_id": str(raw_row.get("entity_id") or ""),
                    "reason": "ROW_GUARDRAIL_MISMATCH",
                }
            )
            continue

        decisions = _mapping(raw_row.get("decisions"))
        route, route_confidence, route_probabilities = _choice(
            decisions, "research_route", ALLOWED_ROUTES
        )
        priority, priority_confidence, priority_probabilities = _choice(
            decisions, "attention_priority", ALLOWED_PRIORITIES
        )
        (
            evidence_state,
            evidence_state_confidence,
            evidence_state_probabilities,
        ) = _choice(decisions, "evidence_state", ALLOWED_EVIDENCE_STATES)
        needs_more_evidence, needs_more_evidence_confidence = _binary(
            decisions, "needs_more_evidence"
        )
        needs_deep_research, needs_deep_research_confidence = _binary(
            decisions, "needs_deep_research"
        )

        if route is None or priority is None or evidence_state is None:
            base["invalid_rows"].append(
                {
                    "entity_id": str(raw_row.get("entity_id") or ""),
                    "reason": "INCOMPLETE_TYPED_ROUTE",
                }
            )
            continue

        base["routing_queue"].append(
            {
                "entity_id": str(raw_row.get("entity_id") or ""),
                "entity_name": str(raw_row.get("entity_name") or ""),
                "is_current_holding": raw_row.get("is_current_holding") is True,
                "existing_engine_action": str(raw_row.get("existing_engine_action") or ""),
                "triage_context": dict(raw_row.get("triage_context") or {})
                if isinstance(raw_row.get("triage_context"), Mapping)
                else {},
                "research_context": dict(raw_row.get("research_context") or {})
                if isinstance(raw_row.get("research_context"), Mapping)
                else {},
                "research_evidence_fingerprint": str(
                    raw_row.get("research_evidence_fingerprint") or ""
                ),
                "route": route,
                "route_confidence": route_confidence,
                "route_probabilities": route_probabilities,
                "attention_priority": priority,
                "attention_confidence": priority_confidence,
                "attention_probabilities": priority_probabilities,
                "needs_more_evidence": needs_more_evidence,
                "needs_more_evidence_confidence": needs_more_evidence_confidence,
                "needs_deep_research": needs_deep_research,
                "needs_deep_research_confidence": needs_deep_research_confidence,
                "evidence_state": evidence_state,
                "evidence_state_confidence": evidence_state_confidence,
                "evidence_state_probabilities": evidence_state_probabilities,
                "served_model": str(raw_row.get("served_model") or ""),
                "state_fingerprint": str(raw_row.get("state_fingerprint") or ""),
                "research_authority": "ADVISORY_ONLY",
                "automatic_dispatch_allowed": False,
                "formal_trading_authority": False,
                "mutates_authoritative_decision": False,
                "may_suppress_existing_research": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
            }
        )

    base["routing_queue"].sort(
        key=lambda row: (
            0 if row.get("is_current_holding") is True else 1,
            _PRIORITY_RANK.get(str(row["attention_priority"]), 99),
            _ROUTE_RANK.get(str(row["route"]), 99),
            str(row["entity_id"]),
        )
    )
    base["execution_status"] = "SUCCESS" if base["routing_queue"] else "EMPTY"
    return _finalize(base)


def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
    queue = payload.get("routing_queue") or []
    route_counts = Counter(str(row.get("route") or "") for row in queue)
    priority_counts = Counter(str(row.get("attention_priority") or "") for row in queue)
    actionable = sum(
        1
        for row in queue
        if row.get("route") in {"EVIDENCE_REFRESH", "DEEP_RESEARCH", "VALUATION_CLOSURE", "HUMAN_REVIEW"}
    )
    payload["summary"] = {
        "routing_count": len(queue),
        "actionable_research_count": actionable,
        "invalid_row_count": len(payload.get("invalid_rows") or []),
        "route_counts": dict(sorted(route_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
    }
    return payload


def render_routing_markdown(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Jev Research Routing Advisory",
        "",
        f"- execution: **{payload.get('execution_status') or 'UNKNOWN'}**",
        "- authority: **ADVISORY RESEARCH ROUTING ONLY**",
        "- automatic dispatch: **False**",
        "- Formal decision mutation: **False**",
        "- may suppress deterministic research: **False**",
        "- UNKNOWN != PASS; no_auto_trade=true",
        f"- routed entities: **{summary.get('routing_count', 0)}**",
        f"- actionable research routes: **{summary.get('actionable_research_count', 0)}**",
        f"- invalid rows: **{summary.get('invalid_row_count', 0)}**",
        "",
        "## Route counts",
        "",
        f"- {json.dumps(summary.get('route_counts') or {}, ensure_ascii=False, sort_keys=True)}",
        "",
        "## Advisory queue",
        "",
    ]
    queue = payload.get("routing_queue") or []
    if not queue:
        lines.append("- No advisory routes available.")
    else:
        for row in queue:
            lines.append(
                "- "
                f"{row.get('entity_id')} {row.get('entity_name') or ''} | "
                f"priority={row.get('attention_priority')} | "
                f"route={row.get('route')} | "
                f"evidence={row.get('evidence_state')} | "
                f"engine={row.get('existing_engine_action') or 'N/A'}"
            )
    lines.extend(
        [
            "",
            "> Jev is advisory here. Existing deterministic research obligations remain in force, "
            "and this file cannot create, suppress, or mutate Formal actions or orders.",
            "",
        ]
    )
    return "\n".join(lines)
