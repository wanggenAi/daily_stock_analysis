"""Shadow-only Jev decision layer for GenGe stock research routing.

This module deliberately has no interface that can mutate Formal/Production actions.
It prepares compact research state, asks TypeSafe Jev bounded typed questions, and
records shadow diagnostics for later calibration.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

CONTRACT = "GEN_GE_JEV_SHADOW_DECISION_V1"
STATE_SCHEMA_VERSION = "GEN_GE_JEV_STOCK_STATE_V2"
QUESTION_SET_VERSION = "GEN_GE_JEV_RESEARCH_ROUTING_V2"

QUESTION_SPECS: dict[str, dict[str, Any]] = {
    "needs_more_evidence": {
        "type": "noul",
        "instructions": (
            "Given only the supplied research and evidence state, is additional verified evidence "
            "needed before this research state can be considered sufficiently resolved? Judge "
            "research completeness only. Do not make or imply a trading recommendation."
        ),
    },
    "needs_deep_research": {
        "type": "noul",
        "instructions": (
            "Would this entity benefit from expensive deep research now, rather than only routine "
            "source refresh, to resolve material research uncertainty? Use supplied deterministic "
            "triage signals such as urgent_research, research_priority, current-holding status, "
            "resolved/unknown hard gates, and valuation research context only to decide research "
            "effort. Deep research is for synthesis, conflict, or material unresolved reasoning; "
            "do not choose it merely because evidence is missing. Do not make or imply a trading "
            "recommendation."
        ),
    },
    "research_route": {
        "type": "choice",
        "instructions": (
            "Which research route best fits the supplied state right now? Choose exactly one route. "
            "Differentiate concrete missing/stale source evidence (EVIDENCE_REFRESH) from cases that "
            "already have enough evidence to require synthesis or conflict resolution (DEEP_RESEARCH), "
            "and from materially ambiguous/high-stakes cases needing HUMAN_REVIEW. Do not choose "
            "EVIDENCE_REFRESH solely because some hard gates are UNKNOWN; use the supplied triage and "
            "gate context. Do not make or imply a trading recommendation."
        ),
        "criteria": {
            "NO_ESCALATION": "No urgent extra research is indicated; normal lifecycle refresh is sufficient.",
            "EVIDENCE_REFRESH": (
                "The main problem is missing, stale, incomplete, or insufficiently corroborated "
                "source evidence; gather verified evidence before deeper synthesis."
            ),
            "DEEP_RESEARCH": (
                "The available state needs deeper synthesis or reasoning now to resolve material "
                "uncertainty after or alongside evidence gathering."
            ),
            "HUMAN_REVIEW": (
                "The state is materially conflicting, ambiguous, or high-stakes enough that a "
                "human should inspect it before relying on automated routing."
            ),
        },
    },
    "attention_priority": {
        "type": "choice",
        "instructions": (
            "How much research attention should this entity receive relative to ordinary candidates? "
            "Use supplied deterministic triage signals such as current-holding status, urgent_research, "
            "research_priority, screening_attractiveness, quant context, and unresolved hard gates. "
            "Reserve HIGH for materially urgent or decision-relevant research; do not label an entity "
            "HIGH merely because evidence is insufficient. Judge research priority only, not investment "
            "attractiveness."
        ),
        "criteria": {
            "LOW": "Routine monitoring is sufficient; no material research urgency is visible.",
            "MEDIUM": "There is meaningful unresolved research work, but it is not unusually urgent.",
            "HIGH": (
                "Material uncertainty, conflict, or decision-relevant evidence gaps justify prompt "
                "research attention."
            ),
        },
    },
    "evidence_state": {
        "type": "choice",
        "instructions": (
            "Which label best describes the evidence state supplied for this entity? Judge only the "
            "evidence state shown; do not invent facts."
        ),
        "criteria": {
            "ADEQUATE_FOR_CURRENT_RESEARCH_STATE": (
                "The supplied evidence state is sufficiently resolved for the current research stage."
            ),
            "INSUFFICIENT": "Important research questions remain unresolved because evidence is insufficient.",
            "CONFLICTED": "The supplied evidence contains material conflict that needs reconciliation.",
            "STALE_OR_LINEAGE_UNCLEAR": (
                "Freshness, provenance, or lineage is unclear enough that the evidence should be refreshed."
            ),
        },
    },
}


class JevProvider(Protocol):
    def evaluate(
        self,
        state: Mapping[str, Any],
        *,
        model: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Return normalized provider output for one compact state."""


@dataclass(frozen=True)
class JevShadowConfig:
    enabled: bool = False
    shadow_mode: bool = True
    model: str = "jev-latest"
    timeout_seconds: float = 3.0
    max_retries: int = 1

    @classmethod
    def from_env(cls) -> "JevShadowConfig":
        return cls(
            enabled=_env_bool("JEV_ENABLED", False),
            shadow_mode=_env_bool("JEV_SHADOW_MODE", True),
            model=(os.getenv("JEV_MODEL") or "jev-latest").strip() or "jev-latest",
            timeout_seconds=_env_float("JEV_TIMEOUT_SECONDS", 3.0, minimum=0.1),
            max_retries=_env_int("JEV_MAX_RETRIES", 1, minimum=0, maximum=5),
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, value))


def _code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit() and len(text) <= 6:
        return text.zfill(6)
    return text


def _compact_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _rows_by_code(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = dict(payload or {})
    candidates: list[Any] = []
    for key in ("terminal_rows", "rows", "research_rows", "queue"):
        value = raw.get(key)
        if isinstance(value, list):
            candidates = value
            break
    result: dict[str, dict[str, Any]] = {}
    for item in candidates:
        if not isinstance(item, Mapping):
            continue
        code = _code(item.get("code"))
        if code:
            result[code] = dict(item)
    return result


def _profile_gate_summary(profile: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    gates = profile.get("gates") if isinstance(profile, Mapping) else None
    if not isinstance(gates, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for gate, raw in gates.items():
        if not isinstance(raw, Mapping):
            continue
        result[str(gate)] = {
            "status": str(raw.get("status") or "UNKNOWN"),
            "confidence": str(raw.get("confidence") or ""),
            "source": str(raw.get("source") or ""),
        }
    return result


def _triage_sort_key(code: str, research_map: Mapping[str, Mapping[str, Any]]) -> tuple[Any, ...]:
    row = research_map.get(code) if isinstance(research_map, Mapping) else None
    research = row if isinstance(row, Mapping) else {}
    urgent_rank = 0 if research.get("urgent_research") is True else 1
    priority = str(research.get("research_priority") or "").strip().upper()
    priority_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority, 9)
    attractiveness = str(research.get("screening_attractiveness") or "").strip().upper()
    attractiveness_rank = {"HIGH": 0, "NORMAL": 1, "LOW": 2}.get(attractiveness, 9)
    quant_status = str(research.get("quant_status") or "").strip().upper()
    quant_status_rank = {
        "PRIORITY_RESEARCH": 0,
        "NORMAL": 1,
        "HARD_REJECT": 2,
    }.get(quant_status, 3)
    raw_score = research.get("quant_score")
    quant_score = float(raw_score) if isinstance(raw_score, (int, float)) else float("-inf")
    return (
        urgent_rank,
        priority_rank,
        attractiveness_rank,
        quant_status_rank,
        -quant_score,
        code,
    )


def _valuation_research_context(research: Mapping[str, Any]) -> dict[str, Any]:
    raw = research.get("valuation") if isinstance(research, Mapping) else None
    valuation = raw if isinstance(raw, Mapping) else {}
    keys = (
        "current_pe",
        "historical_median_pe_reference",
        "pe_to_history_ratio",
        "required_profit_growth_pct",
        "expectation_state",
        "financial_review_status",
        "earnings_quality_confidence",
        "earnings_quality_score",
    )
    return {key: valuation.get(key) for key in keys if key in valuation}


def build_stock_shadow_states(
    *,
    dashboard: Mapping[str, Any] | None,
    deep_status: Mapping[str, Any] | None,
    profiles: Mapping[str, Any] | None = None,
    research_decisions: Mapping[str, Any] | None = None,
    research_priority: Mapping[str, Any] | None = None,
    scope: str = "combined",
    max_entities: int = 25,
) -> list[dict[str, Any]]:
    """Build compact, deterministic Jev inputs without mutating source payloads."""

    if scope not in {"holdings", "unresolved", "combined"}:
        raise ValueError("scope must be holdings, unresolved, or combined")
    max_entities = max(1, min(int(max_entities), 500))

    dashboard_obj = dict(dashboard or {})
    status_obj = dict(deep_status or {})
    profiles_obj = dict(profiles or {})
    profile_map = profiles_obj.get("profiles") if isinstance(profiles_obj.get("profiles"), Mapping) else {}
    research_map = _rows_by_code(research_decisions)
    priority_obj = dict(research_priority or {})
    priority_map = _rows_by_code(priority_obj)
    priority_rows = priority_obj.get("queue") if isinstance(priority_obj.get("queue"), list) else []
    priority_order = [
        code
        for raw in priority_rows
        if isinstance(raw, Mapping)
        for code in [_code(raw.get("code"))]
        if code
    ]

    portfolio = dashboard_obj.get("stock_portfolio")
    holding_rows = portfolio.get("rows") if isinstance(portfolio, Mapping) else []
    holdings: dict[str, dict[str, Any]] = {}
    holding_order: list[str] = []
    if isinstance(holding_rows, list):
        for raw in holding_rows:
            if not isinstance(raw, Mapping):
                continue
            code = _code(raw.get("code"))
            if code and code not in holdings:
                holdings[code] = dict(raw)
                holding_order.append(code)

    unresolved_raw = status_obj.get("unresolved_reasons")
    unresolved = unresolved_raw if isinstance(unresolved_raw, Mapping) else {}
    unresolved_codes = sorted(
        (_code(code) for code in unresolved if _code(code)),
        key=lambda code: _triage_sort_key(code, research_map),
    )

    selected: list[str] = []
    if scope in {"holdings", "combined"}:
        selected.extend(holding_order)
    if scope in {"unresolved", "combined"}:
        # The live priority router is the broad candidate source of truth. Keep
        # holdings first, then consume its ranked queue, then append any Deep
        # unresolved continuity codes that are not already represented.
        selected.extend(code for code in priority_order if code not in selected)
        selected.extend(code for code in unresolved_codes if code not in selected)
    selected = selected[:max_entities]

    states: list[dict[str, Any]] = []
    for code in selected:
        holding = holdings.get(code, {})
        research = research_map.get(code, {})
        priority = priority_map.get(code, {})
        reasons_raw = unresolved.get(code, {})
        reasons = dict(reasons_raw) if isinstance(reasons_raw, Mapping) else {}
        profile = profile_map.get(code) if isinstance(profile_map, Mapping) else None
        gate_summary = _profile_gate_summary(profile if isinstance(profile, Mapping) else None)

        priority_missing = list(priority.get("near_buy_missing_evidence_items") or [])
        for item in priority_missing:
            text = str(item or "")
            if not text.startswith("hard_gate:"):
                continue
            gate = text.split(":", 1)[1].strip()
            if gate and gate not in reasons:
                reasons[gate] = "RESEARCH_PRIORITY_MISSING_EVIDENCE"

        unresolved_gates = [
            {"gate": str(gate), "reason": _compact_text(reason)}
            for gate, reason in sorted(reasons.items(), key=lambda item: str(item[0]))
        ]

        formal_action = str(holding.get("canonical_formal_action") or holding.get("formal_action") or "")
        research_decision = str(research.get("research_decision") or research.get("terminal_decision") or "")
        priority_label = str(priority.get("priority") or "").strip().upper()
        existing_action = (
            f"FORMAL:{formal_action}"
            if formal_action
            else f"RESEARCH:{research_decision}"
            if research_decision
            else f"RESEARCH_PRIORITY:{priority_label}"
            if priority_label
            else f"DEEP:{status_obj.get('research_terminal_state') or 'UNKNOWN'}"
        )

        states.append(
            {
                "state_schema_version": STATE_SCHEMA_VERSION,
                "entity": {
                    "code": code,
                    "name": str(
                        holding.get("name")
                        or research.get("name")
                        or research.get("stock_name")
                        or priority.get("name")
                        or ""
                    ),
                    "is_current_holding": code in holdings,
                },
                "holding_context": {
                    "formal_action": formal_action,
                    "formal_action_currently_usable": holding.get("formal_action_currently_usable"),
                    "price_value_zone": str(holding.get("price_value_zone") or ""),
                    "valuation_confidence": str(holding.get("valuation_confidence") or ""),
                    "valuation_change": str(holding.get("valuation_change") or ""),
                    "holding_add_authorized": holding.get("holding_add_authorized"),
                    "reason_codes": _compact_text(holding.get("reason_codes")),
                },
                "research_context": {
                    "research_decision": research_decision,
                    "research_reason": _compact_text(research.get("research_reason")),
                    "hard_gate_pass_count": research.get("hard_gate_pass_count"),
                    "hard_gate_failures": list(research.get("hard_gate_failures") or [])[:12],
                    "hard_gate_unknowns": list(research.get("hard_gate_unknowns") or [])[:12],
                    "unresolved_gates": unresolved_gates[:12],
                    "profile_gate_statuses": gate_summary,
                    "deep_execution_status": str(status_obj.get("execution_status") or ""),
                    "deep_terminal_state": str(status_obj.get("research_terminal_state") or ""),
                    "deep_lambda_run_id": str(status_obj.get("lambda_run_id") or ""),
                },
                "triage_context": {
                    "research_priority": str(
                        research.get("research_priority") or priority_label
                    ),
                    "research_priority_score": priority.get("priority_score"),
                    "urgent_research": (
                        research.get("urgent_research") is True
                        or priority_label in {"P0", "P1"}
                    ),
                    "urgent_research_reasons": list(
                        research.get("urgent_research_reasons")
                        or priority.get("reason_codes")
                        or []
                    )[:8],
                    "quant_status": str(research.get("quant_status") or ""),
                    "quant_score": research.get("quant_score"),
                    "screening_attractiveness": str(research.get("screening_attractiveness") or ""),
                    "industry": str(
                        research.get("industry")
                        or (profile.get("industry") if isinstance(profile, Mapping) else "")
                        or ""
                    ),
                    "near_buy_evidence_recovery_tier": priority.get(
                        "near_buy_evidence_recovery_tier"
                    ),
                    "near_buy_missing_evidence_items": priority_missing[:16],
                    "mapping_gaps": list(priority.get("mapping_gaps") or [])[:8],
                    "valuation": _valuation_research_context(research),
                },
                "source_lineage": {
                    "dashboard_snapshot_id": str(dashboard_obj.get("canonical_snapshot_id") or ""),
                    "dashboard_source_run_id": str(dashboard_obj.get("canonical_source_run_id") or ""),
                    "deep_code_epoch_sha": str(status_obj.get("deep_code_epoch_sha") or ""),
                    "deep_lambda_run_id": str(status_obj.get("lambda_run_id") or ""),
                },
                "guardrails": {
                    "jev_authority": "SHADOW_ONLY",
                    "formal_trading_authority": False,
                    "automatic_formal_buy_allowed": False,
                    "unknown_is_pass": False,
                    "no_auto_trade": True,
                },
                "existing_engine_action": existing_action,
                "existing_needs_more_evidence": bool(
                    unresolved_gates
                    or research_decision.upper() == "RESEARCH_GAP"
                    or priority_label in {"P0", "P1"}
                    or priority_missing
                ),
            }
        )
    return states


def _safe_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        dumped = dict_method()
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    raw = getattr(value, "__dict__", None)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _choice_payload(answer: Any) -> dict[str, Any]:
    raw = _safe_dump(answer)
    choice = getattr(answer, "choice", raw.get("choice"))
    confidence = getattr(answer, "confidence", raw.get("confidence"))
    probabilities = getattr(answer, "probabilities", raw.get("probabilities"))
    result: dict[str, Any] = {"type": "choice", "choice": str(choice or "")}
    if isinstance(confidence, (int, float)):
        result["confidence"] = round(float(confidence), 6)
    if isinstance(probabilities, Mapping):
        result["probabilities"] = {
            str(key): round(float(value), 6)
            for key, value in probabilities.items()
            if isinstance(value, (int, float))
        }
    return result


def _noul_payload(answer: Any) -> dict[str, Any]:
    raw = _safe_dump(answer)
    probability = getattr(answer, "noul", raw.get("noul"))
    try:
        probability_float = float(probability)
    except (TypeError, ValueError):
        probability_float = 0.5
    probability_float = min(1.0, max(0.0, probability_float))
    return {
        "type": "noul",
        "probability": round(probability_float, 6),
        "answer": probability_float >= 0.5,
        "confidence": round(abs(probability_float - 0.5) * 2.0, 6),
        "confidence_kind": "derived_from_binary_probability",
    }


class TypeSafeJevProvider:
    """Thin optional dependency boundary around typesafe-sdk."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def evaluate(
        self,
        state: Mapping[str, Any],
        *,
        model: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        try:
            from typesafe_sdk import Choice, Noul, TypeSafeClient
        except ImportError as exc:
            raise RuntimeError(
                "typesafe-sdk is required for live Jev evaluation; install typesafe-sdk==0.7.0"
            ) from exc

        questions: dict[str, Any] = {}
        for question_id, spec in QUESTION_SPECS.items():
            if spec["type"] == "noul":
                questions[question_id] = Noul(instructions=spec["instructions"])
            else:
                questions[question_id] = Choice(
                    instructions=spec["instructions"],
                    criteria=dict(spec["criteria"]),
                )

        with TypeSafeClient(
            api_key=self.api_key,
            model=model,
            timeout=timeout_seconds,
        ) as client:
            response = client.system_one(state=dict(state), questions=questions)

        decisions: dict[str, dict[str, Any]] = {}
        response_answers = getattr(response, "answers", None)
        response_choices = getattr(response, "choices", None)
        response_nouls = getattr(response, "nouls", None)
        for question_id, spec in QUESTION_SPECS.items():
            answer: Any = None
            if isinstance(response_answers, Mapping):
                answer = response_answers.get(question_id)
            if answer is None and spec["type"] == "choice" and isinstance(response_choices, Mapping):
                answer = response_choices.get(question_id)
            if answer is None and spec["type"] == "noul" and isinstance(response_nouls, Mapping):
                answer = response_nouls.get(question_id)
            if answer is None:
                raise ValueError(f"Jev response missing answer for {question_id}")
            decisions[question_id] = (
                _noul_payload(answer)
                if spec["type"] == "noul"
                else _choice_payload(answer)
            )

        return {
            "model": str(getattr(response, "model", model) or model),
            "decisions": decisions,
            "usage": _safe_dump(getattr(response, "usage", None)),
        }


def _fingerprint(state: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        state,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _error_kind(exc: Exception) -> str:
    text = f"{type(exc).__name__} {exc}".lower()
    return "TIMEOUT" if "timeout" in text else "ERROR"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    value = ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction
    return round(value, 3)


def evaluate_stock_shadow(
    *,
    states: list[Mapping[str, Any]],
    config: JevShadowConfig,
    provider: JevProvider | None = None,
) -> dict[str, Any]:
    """Evaluate compact states without any mutation path to authoritative decisions."""

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    base: dict[str, Any] = {
        "contract": CONTRACT,
        "generated_at": now,
        "authority": "SHADOW_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "mutates_authoritative_decision": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "question_set_version": QUESTION_SET_VERSION,
        "requested_model": config.model,
        "shadow_mode": config.shadow_mode,
        "entity_count": len(states),
        "rows": [],
    }

    if not config.enabled:
        base["execution_status"] = "SKIPPED_DISABLED"
        base["summary"] = _summary(base["rows"], skipped=1)
        return base
    if not config.shadow_mode:
        base["execution_status"] = "REFUSED_NON_SHADOW"
        base["summary"] = _summary(base["rows"], skipped=1)
        return base

    if provider is None:
        api_key = (os.getenv("TYPESAFE_API_KEY") or "").strip()
        if not api_key:
            base["execution_status"] = "SKIPPED_NO_SECRET"
            base["summary"] = _summary(base["rows"], skipped=1)
            return base
        provider = TypeSafeJevProvider(api_key)

    rows: list[dict[str, Any]] = []
    for state in states:
        entity = state.get("entity") if isinstance(state.get("entity"), Mapping) else {}
        code = _code(entity.get("code"))
        started = time.perf_counter()
        provider_result: dict[str, Any] | None = None
        error: Exception | None = None
        attempts = 0
        for attempt in range(config.max_retries + 1):
            attempts = attempt + 1
            try:
                provider_result = provider.evaluate(
                    state,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                )
                error = None
                break
            except Exception as exc:
                error = exc
                if attempt < config.max_retries:
                    time.sleep(min(0.25 * (2**attempt), 1.0))

        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        row: dict[str, Any] = {
            "entity_id": code,
            "entity_name": str(entity.get("name") or ""),
            "is_current_holding": entity.get("is_current_holding") is True,
            "state_fingerprint": _fingerprint(state),
            "state_schema_version": STATE_SCHEMA_VERSION,
            "question_set_version": QUESTION_SET_VERSION,
            "existing_engine_action": str(state.get("existing_engine_action") or ""),
            "existing_needs_more_evidence": state.get("existing_needs_more_evidence") is True,
            "triage_context": dict(state.get("triage_context") or {})
            if isinstance(state.get("triage_context"), Mapping)
            else {},
            "requested_model": config.model,
            "attempt_count": attempts,
            "latency_ms": latency_ms,
            "authority": "SHADOW_ONLY",
            "formal_trading_authority": False,
            "mutates_authoritative_decision": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
        }
        if provider_result is not None:
            row["status"] = "SUCCESS"
            row["served_model"] = str(provider_result.get("model") or config.model)
            row["decisions"] = dict(provider_result.get("decisions") or {})
            usage = provider_result.get("usage")
            row["usage"] = dict(usage) if isinstance(usage, Mapping) else {}
            evidence_answer = row["decisions"].get("needs_more_evidence", {}).get("answer")
            if isinstance(evidence_answer, bool):
                row["evidence_need_agrees_with_existing"] = (
                    evidence_answer == row["existing_needs_more_evidence"]
                )
        else:
            row["status"] = _error_kind(error or RuntimeError("unknown provider failure"))
            row["served_model"] = ""
            row["decisions"] = {}
            row["usage"] = {}
            row["error_type"] = type(error).__name__ if error is not None else "UnknownError"
            row["error_message"] = _compact_text(error, limit=240)
        rows.append(row)

    base["rows"] = rows
    base["execution_status"] = (
        "SUCCESS" if any(row["status"] == "SUCCESS" for row in rows) else "FAILED"
    )
    base["summary"] = _summary(rows, skipped=0)
    return base


def _summary(rows: list[Mapping[str, Any]], *, skipped: int) -> dict[str, Any]:
    successful = [row for row in rows if row.get("status") == "SUCCESS"]
    latencies = [
        float(row.get("latency_ms"))
        for row in successful
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    distributions: dict[str, dict[str, int]] = {}
    judgments = 0
    comparable = 0
    agreement = 0
    high_confidence_disagreement = 0
    served_models: dict[str, int] = {}

    for row in successful:
        served = str(row.get("served_model") or "")
        if served:
            served_models[served] = served_models.get(served, 0) + 1
        decisions = row.get("decisions") if isinstance(row.get("decisions"), Mapping) else {}
        judgments += len(decisions)
        for question_id, decision in decisions.items():
            if not isinstance(decision, Mapping):
                continue
            value = decision.get("choice")
            if value is None and "answer" in decision:
                value = str(bool(decision.get("answer"))).upper()
            if value is not None:
                distribution = distributions.setdefault(str(question_id), {})
                key = str(value)
                distribution[key] = distribution.get(key, 0) + 1

        comparison = row.get("evidence_need_agrees_with_existing")
        if isinstance(comparison, bool):
            comparable += 1
            if comparison:
                agreement += 1
            else:
                evidence_decision = decisions.get("needs_more_evidence")
                confidence = (
                    evidence_decision.get("confidence")
                    if isinstance(evidence_decision, Mapping)
                    else None
                )
                if isinstance(confidence, (int, float)) and confidence >= 0.8:
                    high_confidence_disagreement += 1

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "calls": len(rows),
        "judgments": judgments,
        "success_count": len(successful),
        "success_rate": round(len(successful) / len(rows), 6) if rows else 0.0,
        "status_counts": status_counts,
        "skipped_count": skipped,
        "latency_ms_p50": _percentile(latencies, 0.50),
        "latency_ms_p95": _percentile(latencies, 0.95),
        "decision_distributions": distributions,
        "served_models": served_models,
        "evidence_comparable_count": comparable,
        "evidence_agreement_count": agreement,
        "evidence_agreement_rate": round(agreement / comparable, 6) if comparable else None,
        "high_confidence_evidence_disagreement_count": high_confidence_disagreement,
    }


def render_shadow_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# GenGe Jev Shadow Decision Layer",
        "",
        f"- execution: **{payload.get('execution_status') or 'UNKNOWN'}**",
        "- authority: **SHADOW ONLY**",
        "- authoritative decision mutation: **False**",
        f"- requested model: **{payload.get('requested_model') or 'jev-latest'}**",
        f"- served models: **{json.dumps(summary.get('served_models') or {}, ensure_ascii=False, sort_keys=True)}**",
        f"- entities: **{payload.get('entity_count', 0)}**",
        f"- calls: **{summary.get('calls', 0)}**; judgments: **{summary.get('judgments', 0)}**",
        f"- success: **{summary.get('success_count', 0)}**; rate: **{summary.get('success_rate', 0)}**",
        f"- latency p50/p95 ms: **{summary.get('latency_ms_p50')} / {summary.get('latency_ms_p95')}**",
        f"- evidence agreement: **{summary.get('evidence_agreement_count', 0)}/{summary.get('evidence_comparable_count', 0)}**",
        f"- high-confidence evidence disagreements: **{summary.get('high_confidence_evidence_disagreement_count', 0)}**",
        "- guardrails: **Formal authority unchanged; UNKNOWN != PASS; no_auto_trade=true**",
        "",
        "## Decision distributions",
        "",
    ]
    distributions = (
        summary.get("decision_distributions")
        if isinstance(summary.get("decision_distributions"), Mapping)
        else {}
    )
    if distributions:
        for question_id, distribution in sorted(distributions.items()):
            lines.append(
                f"- {question_id}: "
                f"{json.dumps(distribution, ensure_ascii=False, sort_keys=True)}"
            )
    else:
        lines.append("- No live Jev decisions were produced.")

    disagreements = [
        row
        for row in payload.get("rows") or []
        if isinstance(row, Mapping) and row.get("evidence_need_agrees_with_existing") is False
    ]
    lines.extend(["", "## Shadow disagreements", ""])
    if not disagreements:
        lines.append("- None recorded.")
    else:
        for row in disagreements[:10]:
            decision = row.get("decisions", {}).get("needs_more_evidence", {})
            lines.append(
                f"- {row.get('entity_id')} {row.get('entity_name') or ''}: "
                f"existing={row.get('existing_needs_more_evidence')} "
                f"jev={decision.get('answer')} confidence={decision.get('confidence')}"
            )
    lines.extend(
        [
            "",
            "> This artifact is diagnostic only. It cannot create, suppress, or mutate "
            "BUY / WAIT_PRICE / REJECT, Formal actions, Candidate Lifecycle state, "
            "hard gates, or orders.",
            "",
        ]
    )
    return "\n".join(lines)
