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
ALLOWED_ENTRY_JUDGMENTS = {
    "ENTRY_NOW",
    "WAIT_PRICE",
    "WAIT_EVIDENCE",
    "DO_NOT_CHASE",
    "INVALIDATED",
    "NO_JUDGMENT",
}
ENTRY_INITIAL_MANUAL_CAP_PCT = 1.0
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


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _entry_advisory(
    *,
    raw_row: Mapping[str, Any],
    decisions: Mapping[str, Any],
    evidence_state: str,
) -> dict[str, Any]:
    """Validate Jev's entry judgment against deterministic current research state."""

    jev_judgment, confidence, probabilities = _choice(
        decisions, "entry_judgment", ALLOWED_ENTRY_JUDGMENTS
    )
    research = _mapping(raw_row.get("research_context"))
    triage = _mapping(raw_row.get("triage_context"))
    valuation = _mapping(triage.get("valuation"))
    capital = _mapping(raw_row.get("capital_context"))
    lineage = _mapping(raw_row.get("source_lineage"))

    decision = str(research.get("research_decision") or "").strip().upper()
    failures = [str(value) for value in (research.get("hard_gate_failures") or []) if str(value)]
    unknowns = [str(value) for value in (research.get("hard_gate_unknowns") or []) if str(value)]
    pass_count = research.get("hard_gate_pass_count")
    deep_lineage = str(research.get("deep_lambda_run_id") or "")
    source_deep_lineage = str(lineage.get("deep_lambda_run_id") or "")
    reference_price = _num(valuation.get("reference_price"))
    buy_ceiling = _num(valuation.get("research_buy_price_ceiling"))
    trade_date = str(valuation.get("reference_trade_date") or "")
    price_status = str(valuation.get("price_mapping_status") or "").upper()
    max_pct = _num(capital.get("suggested_max_portfolio_pct"))
    max_pct = max_pct if max_pct is not None and max_pct >= 0 else None

    validated = jev_judgment or "NO_JUDGMENT"
    reason = "JEV_ENTRY_JUDGMENT_ACCEPTED"
    supported = True

    if (
        (capital.get("authority") not in {None, "", "ADVISORY_ONLY"})
        or capital.get("automatic_execution_allowed") is True
        or capital.get("formal_buy_authorized") is True
        or capital.get("no_auto_trade") is False
    ):
        validated, reason, supported = "NO_JUDGMENT", "CAPITAL_AUTHORITY_GUARDRAIL_MISMATCH", False
    elif deep_lineage and source_deep_lineage and deep_lineage != source_deep_lineage:
        validated, reason, supported = "NO_JUDGMENT", "DEEP_LINEAGE_MISMATCH", False
    elif failures or decision == "REJECT":
        validated, reason = "INVALIDATED", "DETERMINISTIC_HARD_GATE_OR_RESEARCH_REJECT"
    elif unknowns or decision == "RESEARCH_GAP":
        validated, reason = "WAIT_EVIDENCE", "DETERMINISTIC_RESEARCH_EVIDENCE_INCOMPLETE"
    elif evidence_state in {"INSUFFICIENT", "CONFLICTED", "STALE_OR_LINEAGE_UNCLEAR"}:
        validated, reason = "WAIT_EVIDENCE", "JEV_EVIDENCE_STATE_NOT_CURRENTLY_ADEQUATE"
    elif pass_count != 5:
        validated, reason = "WAIT_EVIDENCE", "FIVE_HARD_GATES_NOT_EXPLICITLY_PASS"
    elif not deep_lineage or not source_deep_lineage:
        validated, reason, supported = "NO_JUDGMENT", "CURRENT_DEEP_LINEAGE_NOT_PROVEN", False
    elif reference_price is None or buy_ceiling is None or reference_price <= 0 or buy_ceiling <= 0:
        validated, reason, supported = "NO_JUDGMENT", "VERIFIED_PRICE_THRESHOLD_NOT_AVAILABLE", False
    elif price_status not in {"OK", "CURRENT", "VALID"}:
        validated, reason, supported = "NO_JUDGMENT", "PRICE_MAPPING_NOT_VERIFIED", False
    elif reference_price > buy_ceiling:
        if jev_judgment == "DO_NOT_CHASE":
            validated, reason = "DO_NOT_CHASE", "PRICE_ABOVE_RESEARCH_BUY_CEILING"
        else:
            validated, reason = "WAIT_PRICE", "PRICE_ABOVE_RESEARCH_BUY_CEILING"
    elif decision != "BUY":
        validated, reason = "WAIT_PRICE", "TERMINAL_RESEARCH_BUY_NOT_CURRENT"
    elif jev_judgment == "ENTRY_NOW":
        if max_pct is None or max_pct <= 0:
            validated, reason, supported = "NO_JUDGMENT", "VALIDATED_RISK_BUDGET_CAP_NOT_AVAILABLE", False
        else:
            validated, reason = "ENTRY_NOW", "JEV_ENTRY_NOW_PASSES_DETERMINISTIC_GUARDS"
    elif jev_judgment in {"WAIT_PRICE", "WAIT_EVIDENCE", "NO_JUDGMENT"}:
        validated, reason = jev_judgment, "JEV_CONSERVATIVE_ENTRY_JUDGMENT"
    elif jev_judgment == "DO_NOT_CHASE":
        validated, reason, supported = "NO_JUDGMENT", "DO_NOT_CHASE_NOT_SUPPORTED_BELOW_BUY_CEILING", False
    elif jev_judgment == "INVALIDATED":
        validated, reason, supported = "NO_JUDGMENT", "INVALIDATION_NOT_SUPPORTED_BY_DETERMINISTIC_EVIDENCE", False
    else:
        validated, reason, supported = "NO_JUDGMENT", "JEV_ENTRY_JUDGMENT_NOT_AVAILABLE", False

    initial_pct = (
        round(min(max_pct, ENTRY_INITIAL_MANUAL_CAP_PCT), 4)
        if validated == "ENTRY_NOW" and max_pct is not None and max_pct > 0
        else 0.0
    )
    max_manual_pct = round(max_pct, 4) if max_pct is not None else 0.0
    price_high = round(buy_ceiling, 4) if buy_ceiling is not None and buy_ceiling > 0 else None

    if validated == "ENTRY_NOW":
        entry_trigger = "CURRENT_5_OF_5_PASS_TERMINAL_BUY_AND_PRICE_AT_OR_BELOW_RESEARCH_BUY_CEILING"
    elif validated in {"WAIT_PRICE", "DO_NOT_CHASE"} and price_high is not None:
        entry_trigger = f"REVALIDATE_AND_PRICE_AT_OR_BELOW_{price_high:.4f}"
    elif validated == "WAIT_EVIDENCE":
        entry_trigger = "RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE"
    elif validated == "INVALIDATED":
        entry_trigger = "NO_ENTRY_UNTIL_INVALIDATING_EVIDENCE_IS_REVERSED_AND_FULL_REVALIDATION_PASSES"
    else:
        entry_trigger = "NO_DEFENSIBLE_ENTRY_TRIGGER_FROM_CURRENT_VERIFIED_INPUTS"

    return {
        "jev_judgment": jev_judgment or "NO_JUDGMENT",
        "validated_judgment": validated,
        "validation_reason": reason,
        "deterministically_supported": supported,
        "judgment_confidence": confidence,
        "judgment_probabilities": probabilities,
        "entry_reason": reason,
        "entry_trigger": entry_trigger,
        "entry_price_zone_low": None,
        "entry_price_zone_high": price_high,
        "reference_price": round(reference_price, 4) if reference_price is not None else None,
        "reference_trade_date": trade_date,
        "initial_manual_position_pct": initial_pct,
        "max_manual_position_pct": max_manual_pct,
        "add_condition": (
            "REVALIDATE_5_OF_5_PASS_AND_TERMINAL_BUY_WITH_PRICE_AT_OR_BELOW_CEILING"
            if validated == "ENTRY_NOW"
            else "NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED"
        ),
        "do_not_chase_condition": (
            f"PRICE_ABOVE_{price_high:.4f}_REQUIRES_REVALUATION"
            if price_high is not None
            else "NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE"
        ),
        "invalidation_condition": "ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY",
        "source_lineage": dict(lineage),
        "authority": "ADVISORY_ONLY",
        "formal_buy_authorized": False,
        "automatic_execution_allowed": False,
        "no_auto_trade": True,
    }


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

        entry_advisory = _entry_advisory(
            raw_row=raw_row,
            decisions=decisions,
            evidence_state=evidence_state,
        )

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
                "capital_context": dict(raw_row.get("capital_context") or {})
                if isinstance(raw_row.get("capital_context"), Mapping)
                else {},
                "source_lineage": dict(raw_row.get("source_lineage") or {})
                if isinstance(raw_row.get("source_lineage"), Mapping)
                else {},
                "entry_judgment": entry_advisory,
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
    entry_counts = Counter(
        str(_mapping(row.get("entry_judgment")).get("validated_judgment") or "NO_JUDGMENT")
        for row in queue
    )
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
        "entry_judgment_counts": dict(sorted(entry_counts.items())),
        "entry_now_count": entry_counts.get("ENTRY_NOW", 0),
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
                f"entry={_mapping(row.get('entry_judgment')).get('validated_judgment') or 'NO_JUDGMENT'} | "
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
