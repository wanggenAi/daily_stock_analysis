"""Runtime-aware producer for the three-pillar investor decision center.

The decision-center composer remains the authority-preserving composition layer.
This producer adds operational observability for event-driven deep calculation,
prefers automatically generated profiles over static bootstrap reviews, and
exposes terminal research-only BUY / WAIT_PRICE / RESEARCH_GAP / REJECT separately from
Canonical/Production actions.

Execution completion, process-terminal closure and research completeness are
separate concepts. COMPLETE means every requested gate is resolved;
EVIDENCE_EXHAUSTED means the same Lambda finished bounded evidence recovery but
some gates remain UNKNOWN. UNKNOWN is never converted to PASS here.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .three_pillar_decision_center import build_decision_center, render_markdown

RUNTIME_CONTRACT = "GEN_GE_THREE_PILLAR_DEEP_CALC_RUNTIME_V2"
TERMINAL_RESEARCH_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
TERMINAL_DECISIONS = frozenset({"BUY", "WAIT_PRICE", "RESEARCH_GAP", "REJECT"})
REQUIRED_DEEP_HARD_GATES = (
    "earnings_authenticity",
    "financial_safety",
    "long_term_demand",
    "moat",
    "predictability",
)

ERA_EVIDENCE_FAMILIES = (
    "POLICY_CAPITAL",
    "INDUSTRIAL_CAPITAL",
    "FINANCIAL_CAPITAL",
    "REAL_DEMAND",
    "TECHNOLOGY",
    "GLOBAL_STRUCTURE",
)
CAPITAL_FLOW_FAMILIES = (
    "POLICY_CAPITAL",
    "INDUSTRIAL_CAPITAL",
    "FINANCIAL_CAPITAL",
    "REAL_DEMAND",
)


def summarize_era_evidence(evidence_bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Expose actual evidence coverage instead of implying fund-flow knowledge."""
    raw = dict(evidence_bundle or {})
    rows = [row for row in (raw.get("records") or []) if isinstance(row, Mapping)]
    counts = {family: 0 for family in ERA_EVIDENCE_FAMILIES}
    for row in rows:
        family = str(row.get("family") or "").upper()
        if family in counts:
            counts[family] += 1

    covered = [family for family in CAPITAL_FLOW_FAMILIES if counts[family] > 0]
    missing = [family for family in CAPITAL_FLOW_FAMILIES if counts[family] == 0]
    status = (
        "MULTI_LAYER_COVERED"
        if not missing
        else "PARTIAL"
        if covered
        else "UNAVAILABLE"
    )
    return {
        "status": status,
        "evidence_count": len(rows),
        "family_counts": counts,
        "covered_capital_layers": covered,
        "missing_capital_layers": missing,
        "policy_capital_evidence_available": counts["POLICY_CAPITAL"] > 0,
        "industrial_capital_evidence_available": counts["INDUSTRIAL_CAPITAL"] > 0,
        "financial_capital_evidence_available": counts["FINANCIAL_CAPITAL"] > 0,
        "real_demand_evidence_available": counts["REAL_DEMAND"] > 0,
        "direct_stock_fund_flow_claimed": False,
        "interpretation": (
            "Policy/industrial/financial capital and real-demand evidence are separate layers. "
            "Missing FINANCIAL_CAPITAL must remain explicit; market-strength proxies never become direct fund-flow evidence."
        ),
    }


def _json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def select_latest_deep_calculation_status(
    terminal_status: Mapping[str, Any] | None,
    partial_status: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    """Choose the newest durable runtime checkpoint, including failed/partial runs.

    latest_status.json is the last terminal run, while latest_partial_status.json
    can be newer when evidence closure failed after the initial checkpoint. The
    user-facing decision center must describe the newest actual run instead of
    silently presenting an older SUCCESS as if it were current.
    """
    candidates: list[tuple[str, dict[str, Any]]] = []
    for source, raw in (
        ("TERMINAL_STATUS", terminal_status),
        ("PARTIAL_CHECKPOINT", partial_status),
    ):
        payload = dict(raw or {})
        if payload:
            candidates.append((source, payload))
    if not candidates:
        return {}, "NOT_AVAILABLE"
    source, payload = max(
        candidates,
        key=lambda item: (
            _timestamp(item[1].get("generated_at")),
            _int(item[1].get("lambda_run_id")),
        ),
    )
    return payload, source


def choose_deep_review_config(
    automatic_profiles: Mapping[str, Any] | None,
    static_profiles: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    automatic = dict(automatic_profiles or {})
    if isinstance(automatic.get("profiles"), Mapping) and automatic.get("profiles"):
        if automatic.get("unknown_is_pass") is not False:
            raise ValueError("automatic deep profiles must preserve UNKNOWN != PASS")
        if automatic.get("automatic_formal_buy_allowed") is not False:
            raise ValueError("automatic deep profiles must not create Formal BUY authority")
        if automatic.get("no_auto_trade") is not True:
            raise ValueError("automatic deep profiles must preserve no-auto-trade")
        return automatic, "AUTOMATIC_DEEP_CALCULATION"
    return dict(static_profiles or {}), "STATIC_BOOTSTRAP_FALLBACK"


def _attach_deep_qualified_research_leads(
    payload: dict[str, Any],
    automatic_profiles: Mapping[str, Any] | None,
    *,
    profile_current_for_runtime: bool,
    terminal_research_codes: set[str] | None = None,
) -> None:
    """Expose fully resolved hard-gate research leads without inventing BUY authority."""

    opportunities = payload.get("pillar_3_deep_opportunities")
    if not isinstance(opportunities, dict):
        return

    opportunities["deep_qualified_research_leads"] = []
    opportunities["deep_qualified_research_lead_count"] = 0
    opportunities["deep_qualified_research_authority"] = "RESEARCH_ONLY"
    opportunities["deep_qualified_research_formal_buy_authorized"] = False

    if not profile_current_for_runtime:
        return

    raw_profiles = (automatic_profiles or {}).get("profiles")
    if not isinstance(raw_profiles, Mapping):
        return

    terminal_codes = terminal_research_codes or set()
    holding_codes = {
        str(row.get("code") or "").strip().zfill(6)
        for row in ((payload.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or [])
        if isinstance(row, Mapping) and str(row.get("code") or "").strip()
    }
    formal_codes = {
        str(row.get("code") or "").strip().zfill(6)
        for key in ("buy_now", "wait_price")
        for row in (opportunities.get(key) or [])
        if isinstance(row, Mapping) and str(row.get("code") or "").strip()
    }

    leads: list[dict[str, Any]] = []
    for raw_code, profile in raw_profiles.items():
        if not isinstance(profile, Mapping):
            continue
        code = str(raw_code or "").strip().zfill(6)
        if (
            not code
            or code in holding_codes
            or code in formal_codes
            or code in terminal_codes
        ):
            continue
        gates = profile.get("gates")
        if not isinstance(gates, Mapping):
            continue
        statuses = {
            gate: str((gates.get(gate) or {}).get("status") or "UNKNOWN").strip().upper()
            if isinstance(gates.get(gate), Mapping)
            else "UNKNOWN"
            for gate in REQUIRED_DEEP_HARD_GATES
        }
        if not all(statuses[gate] == "PASS" for gate in REQUIRED_DEEP_HARD_GATES):
            continue
        leads.append(
            {
                "code": code,
                "name": str(profile.get("name") or ""),
                "industry": str(profile.get("industry") or ""),
                "hard_gate_pass_count": len(REQUIRED_DEEP_HARD_GATES),
                "hard_gate_total_count": len(REQUIRED_DEEP_HARD_GATES),
                "hard_gate_statuses": statuses,
                "research_authority": "RESEARCH_ONLY",
                "formal_buy_authorized": False,
                "automatic_execution_allowed": False,
                "account_action": "DO_NOT_BUY_YET",
                "research_action": "CONTINUE_VALUATION_PRICE_AND_AUTHORITY_CLOSURE",
                "no_auto_trade": True,
            }
        )

    leads.sort(key=lambda row: (row["code"], row["name"]))
    opportunities["deep_qualified_research_leads"] = leads[:20]
    opportunities["deep_qualified_research_lead_count"] = len(leads)
    payload["executive_summary"]["deep_qualified_research_lead_count"] = len(leads)
    payload["decision_readiness"]["deep_qualified_research_leads_current"] = bool(leads)


def normalize_runtime(status: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(status or {})
    execution = str(raw.get("execution_status") or "NOT_AVAILABLE").upper()
    research = str(raw.get("research_outcome") or "NOT_AVAILABLE").upper()
    terminal = str(raw.get("research_terminal_state") or research or "NOT_AVAILABLE").upper()
    run_state = str(raw.get("run_state") or "NOT_AVAILABLE").upper()
    if execution == "PARTIAL" and run_state == "NOT_AVAILABLE":
        run_state = "PARTIAL_CHECKPOINT"

    def available(key: str) -> bool:
        return key in raw and raw.get(key) is not None and str(raw.get(key)).strip() != ""

    missing_available = "missing_requested_codes" in raw
    missing = list(raw.get("missing_requested_codes") or [])
    requested_available = available("requested_count")
    requested = _int(raw.get("requested_count"))
    profile_count_available = available("profile_count")
    profile_count = _int(raw.get("profile_count"))
    requested_profile_count_available = available("requested_profile_count")
    requested_profile_count = _int(raw.get("requested_profile_count"))
    exhausted_count = _int(raw.get("evidence_exhausted_requested_count"))
    handoff_incomplete_count = _int(raw.get("handoff_incomplete_requested_count"))
    processed = _int(raw.get("processed_requested_count"))
    terminal_process = terminal in {"COMPLETE", "EVIDENCE_EXHAUSTED", "HANDOFF_INCOMPLETE"}
    if not processed and requested_profile_count_available:
        processed = requested_profile_count
    elif not processed and requested and terminal_process:
        processed = requested
    elif not processed and requested and missing_available and not missing:
        processed = requested
    processed_available = (
        available("processed_requested_count")
        or requested_profile_count_available
        or (requested_available and terminal_process)
        or (requested_available and missing_available and not missing)
    )
    partial = _int(raw.get("partial_requested_count"))
    if not partial and terminal in {"EVIDENCE_EXHAUSTED", "HANDOFF_INCOMPLETE"}:
        partial = exhausted_count
    unresolved_reasons = raw.get("unresolved_reasons")
    if not isinstance(unresolved_reasons, Mapping):
        unresolved_reasons = {}
    immediate_retry = raw.get("immediate_retry_required") is True
    return {
        "contract": RUNTIME_CONTRACT,
        "lambda_workflow": str(raw.get("lambda_workflow") or "GenGe V3.1 Deep Calculation Lambda"),
        "lambda_run_id": str(raw.get("lambda_run_id") or ""),
        "lambda_run_attempt": str(raw.get("lambda_run_attempt") or ""),
        "source_run_id": str(raw.get("source_run_id") or ""),
        "trigger_source": str(raw.get("trigger_source") or ""),
        "generated_at": str(raw.get("generated_at") or ""),
        "run_state": run_state,
        "execution_status": execution,
        "research_outcome": research,
        "research_terminal_state": terminal,
        "requested_count": requested,
        "requested_count_available": requested_available,
        "processed_requested_count": processed,
        "processed_requested_count_available": processed_available,
        "complete_requested_count": _int(raw.get("complete_requested_count")),
        "complete_requested_count_available": available("complete_requested_count"),
        "partial_requested_count": partial,
        "partial_requested_count_available": available("partial_requested_count"),
        "evidence_exhausted_requested_count": exhausted_count,
        "evidence_exhausted_requested_count_available": available("evidence_exhausted_requested_count"),
        "handoff_incomplete_requested_count": handoff_incomplete_count,
        "handoff_incomplete_requested_count_available": available("handoff_incomplete_requested_count"),
        "profile_count": profile_count,
        "profile_count_available": profile_count_available,
        "requested_profile_count": requested_profile_count,
        "requested_profile_count_available": requested_profile_count_available,
        "workset_coverage_known": raw.get("workset_coverage_known") is True,
        "workset_coverage_complete": raw.get("workset_coverage_complete") is True,
        "unresolved_requested_gate_count": _int(raw.get("unresolved_requested_gate_count")),
        "unresolved_requested_gate_count_available": available("unresolved_requested_gate_count"),
        "missing_requested_codes": missing,
        "missing_requested_codes_available": missing_available,
        "unresolved_reasons": dict(unresolved_reasons),
        "gap_closure_attempt_count": _int(raw.get("gap_closure_attempt_count")),
        "new_evidence_count": _int(raw.get("new_evidence_count")),
        "progressed_gate_count": _int(raw.get("progressed_gate_count")),
        "hard_gate_count": _int(raw.get("hard_gate_count")),
        "pass_gate_count": _int(raw.get("pass_gate_count")),
        "fail_gate_count": _int(raw.get("fail_gate_count")),
        "verified_pass_gate_count": _int(raw.get("verified_pass_gate_count")),
        "unverified_pass_gate_count": _int(raw.get("unverified_pass_gate_count")),
        "provenance_audit_complete": raw.get("provenance_audit_complete") is True,
        "provenance_audit_run_id": str(raw.get("provenance_audit_run_id") or ""),
        "material_event_failed_gate_count": _int(raw.get("material_event_failed_gate_count")),
        "historical_material_event_evidence_count": _int(raw.get("historical_material_event_evidence_count")),
        "historical_material_event_failed_gate_count": _int(raw.get("historical_material_event_failed_gate_count")),
        "material_event_risk_ledger_complete": raw.get("material_event_risk_ledger_complete") is True,
        "material_event_risk_ledger_count": _int(raw.get("material_event_risk_ledger_count")),
        "immediate_retry_required": immediate_retry,
        "execution_completed": run_state == "COMPLETED",
        "execution_succeeded": execution == "SUCCESS",
        "research_process_terminal": terminal_process,
        "research_complete": terminal == "COMPLETE",
        "manual_next_round_required": not terminal_process or immediate_retry,
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
        "interpretation": (
            "execution_succeeded means compute finished; COMPLETE means all requested hard gates resolved; "
            "EVIDENCE_EXHAUSTED means bounded same-run recovery finished for materialized profiles while unresolved UNKNOWN gates remain; "
            "HANDOFF_INCOMPLETE means the run finished but one or more requested codes never entered the Deep profile workset."
        ),
    }


def normalize_terminal_research(
    terminal_research: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate and normalize persisted research-only terminal decisions.

    This layer never promotes Research Authority into Formal/Production authority.
    A terminal file may contain research BUY / WAIT_PRICE, but every row must remain
    explicitly unauthorized for Formal BUY and no-auto-trade must stay true.
    """
    raw = dict(terminal_research or {})
    if not raw:
        return {
            "available": False,
            "contract": TERMINAL_RESEARCH_CONTRACT,
            "generated_at": "",
            "source_deep_lambda_run_id": "",
            "source_every_industry_run_id": "",
            "requested_count": 0,
            "decision_counts": {"BUY": 0, "WAIT_PRICE": 0, "RESEARCH_GAP": 0, "REJECT": 0},
            "all_requested_terminal": False,
            "research_buy": [],
            "research_wait_price": [],
            "research_gap": [],
            "research_gap_count": 0,
            "research_reject_count": 0,
            "urgent_research_queue": [],
            "capital_model_version": "",
            "capital_action_counts": {"BUILD": 0, "PROBE": 0, "WATCH": 0, "BLOCK": 0},
            "capital_probe_queue": [],
            "capital_advisory_authority": "ADVISORY_ONLY",
            "capital_advisory_automatic_execution_allowed": False,
            "research_authority": "RESEARCH_ONLY",
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
        }

    if raw.get("contract") != TERMINAL_RESEARCH_CONTRACT:
        raise ValueError("unexpected terminal research decision contract")
    if raw.get("research_authority") != "RESEARCH_ONLY":
        raise ValueError("terminal research decisions must remain RESEARCH_ONLY")
    if raw.get("formal_trading_authority") is not False:
        raise ValueError("terminal research decisions cannot grant Formal trading authority")
    if raw.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("terminal research decisions cannot grant automatic Formal BUY")
    if raw.get("unknown_is_pass") is not False:
        raise ValueError("terminal research decisions must preserve UNKNOWN != PASS")
    if raw.get("no_auto_trade") is not True:
        raise ValueError("terminal research decisions must preserve no-auto-trade")

    rows = [dict(row) for row in (raw.get("terminal_rows") or []) if isinstance(row, Mapping)]
    requested = _int(raw.get("requested_count"))
    if requested != len(rows):
        raise ValueError(
            "terminal research requested_count must equal the number of terminal rows"
        )
    if raw.get("all_requested_terminal") is not True:
        raise ValueError("terminal research file must explicitly close every requested code")

    buy: list[dict[str, Any]] = []
    wait: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    reject_count = 0
    capital_action_counts = {"BUILD": 0, "PROBE": 0, "WATCH": 0, "BLOCK": 0}
    capital_probe_queue: list[dict[str, Any]] = []
    for row in rows:
        decision = str(row.get("research_decision") or "").upper()
        if decision not in TERMINAL_DECISIONS:
            raise ValueError(f"invalid terminal research decision: {decision or 'EMPTY'}")
        if row.get("research_authority") != "RESEARCH_ONLY":
            raise ValueError("terminal research row lost RESEARCH_ONLY authority")
        if row.get("formal_buy_authorized") is not False:
            raise ValueError("terminal research row attempted to authorize Formal BUY")
        if row.get("no_auto_trade") is not True:
            raise ValueError("terminal research row lost no-auto-trade")
        capital = row.get("capital_allocation")
        if isinstance(capital, Mapping):
            action = str(capital.get("action") or "").upper()
            if action not in capital_action_counts:
                raise ValueError(f"invalid capital advisory action: {action or 'EMPTY'}")
            if capital.get("authority") != "ADVISORY_ONLY":
                raise ValueError("capital advisory attempted to gain authority")
            if capital.get("automatic_execution_allowed") is not False:
                raise ValueError("capital advisory cannot enable automatic execution")
            if capital.get("formal_buy_authorized") is not False:
                raise ValueError("capital advisory cannot grant Formal BUY")
            if capital.get("no_auto_trade") is not True:
                raise ValueError("capital advisory lost no-auto-trade")
            capital_action_counts[action] += 1
            if action in {"BUILD", "PROBE"}:
                capital_probe_queue.append(row)
        if decision == "BUY":
            buy.append(row)
        elif decision == "WAIT_PRICE":
            wait.append(row)
        elif decision == "RESEARCH_GAP":
            gaps.append(row)
        else:
            reject_count += 1

    raw_counts = raw.get("decision_counts") if isinstance(raw.get("decision_counts"), Mapping) else {}
    counts = {
        "BUY": _int(raw_counts.get("BUY")),
        "WAIT_PRICE": _int(raw_counts.get("WAIT_PRICE")),
        "RESEARCH_GAP": _int(raw_counts.get("RESEARCH_GAP")),
        "REJECT": _int(raw_counts.get("REJECT")),
    }
    actual_counts = {"BUY": len(buy), "WAIT_PRICE": len(wait), "RESEARCH_GAP": len(gaps), "REJECT": reject_count}
    if counts != actual_counts or sum(counts.values()) != requested:
        raise ValueError("terminal research decision_counts do not match terminal rows")

    urgent = [dict(row) for row in (raw.get("urgent_research_queue") or []) if isinstance(row, Mapping)]
    raw_capital_counts = raw.get("capital_action_counts") if isinstance(raw.get("capital_action_counts"), Mapping) else {}
    if raw_capital_counts:
        expected_capital_counts = {key: _int(raw_capital_counts.get(key)) for key in capital_action_counts}
        if expected_capital_counts != capital_action_counts:
            raise ValueError("terminal capital_action_counts do not match terminal rows")
    capital_probe_queue.sort(
        key=lambda row: (
            0 if str((row.get("capital_allocation") or {}).get("action") or "").upper() == "BUILD" else 1,
            -float((row.get("capital_allocation") or {}).get("capital_conviction_score") or 0.0),
            str(row.get("code") or ""),
        )
    )
    return {
        "available": True,
        "contract": TERMINAL_RESEARCH_CONTRACT,
        "generated_at": str(raw.get("generated_at") or ""),
        "source_deep_lambda_run_id": str(raw.get("source_deep_lambda_run_id") or ""),
        "source_every_industry_run_id": str(raw.get("source_every_industry_run_id") or ""),
        "requested_count": requested,
        "decision_counts": counts,
        "all_requested_terminal": True,
        "research_buy": buy,
        "research_wait_price": wait,
        "research_gap": gaps,
        "research_gap_count": len(gaps),
        "research_reject_count": reject_count,
        "urgent_research_queue": urgent,
        "capital_model_version": str(raw.get("capital_model_version") or ""),
        "capital_action_counts": capital_action_counts,
        "capital_probe_queue": capital_probe_queue,
        "capital_advisory_authority": "ADVISORY_ONLY",
        "capital_advisory_automatic_execution_allowed": False,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def _research_investor_view(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    decision = str(item.get("research_decision") or "").upper()
    unknowns = [str(x) for x in (item.get("hard_gate_unknowns") or []) if str(x)]
    capital = item.get("capital_allocation") if isinstance(item.get("capital_allocation"), Mapping) else {}
    capital_action = str(capital.get("action") or "").upper()
    max_pct = _num(capital.get("suggested_max_portfolio_pct")) or 0.0
    if decision == "RESEARCH_GAP" and capital_action == "PROBE":
        waiting = "、".join(unknowns) or "缺失证据"
        item["investor_action"] = (
            f"研究结论仍为RESEARCH_GAP，但风险预算层允许人工小仓试探；"
            f"建议账户仓位上限约{max_pct:.2f}%，继续补齐：{waiting}"
        )
        item["account_action"] = "MANUAL_PROBE_ADVISORY"
    elif decision == "RESEARCH_GAP" and not capital:
        waiting = "、".join(unknowns) or "缺失证据"
        item["investor_action"] = f"暂不买；等待补齐：{waiting}"
        item["account_action"] = "DO_NOT_BUY_YET"
    elif decision == "RESEARCH_GAP":
        waiting = "、".join(unknowns) or "缺失证据"
        item["investor_action"] = f"暂不投入新增资金；等待补齐：{waiting}"
        item["account_action"] = "WATCH_OR_BLOCK"
    elif decision == "BUY" and capital_action == "BUILD":
        item["investor_action"] = (
            f"研究层达到BUY条件；风险预算层建议人工分批建仓，上限约{max_pct:.2f}%；"
            "仍未获得Formal BUY授权，不自动下单"
        )
        item["account_action"] = "MANUAL_BUILD_ADVISORY"
    elif decision == "BUY":
        item["investor_action"] = "研究层达到BUY条件，但未获得Formal BUY授权；不得直接下单"
        item["account_action"] = "RESEARCH_BUY_NOT_FORMAL"
    elif decision == "WAIT_PRICE":
        item["investor_action"] = "研究层等待价格；未获得Formal BUY授权，达到价格也需重新核验正式权限"
        item["account_action"] = "WAIT_PRICE_RESEARCH_ONLY"
    else:
        item["investor_action"] = "不买；研究层已淘汰"
        item["account_action"] = "DO_NOT_BUY"
    return item


def _attach_terminal_research(
    payload: dict[str, Any],
    terminal: dict[str, Any],
    runtime: Mapping[str, Any],
) -> None:
    opportunities = payload["pillar_3_deep_opportunities"]
    deep_lambda = str(runtime.get("lambda_run_id") or "")
    terminal_lambda = str(terminal.get("source_deep_lambda_run_id") or "")
    current = bool(terminal.get("available") and deep_lambda and terminal_lambda == deep_lambda)
    terminal = dict(terminal)
    terminal["current_for_deep_runtime"] = current
    terminal["stale_for_deep_runtime"] = bool(terminal.get("available") and not current)

    # Existing buy_now/wait_price remain Canonical/Production mirrors. Research-only
    # decisions live in distinct fields and never become Formal actions here.
    opportunities["canonical_formal_buy_now"] = list(opportunities.get("buy_now") or [])
    opportunities["canonical_formal_wait_price"] = list(opportunities.get("wait_price") or [])
    opportunities["terminal_research_snapshot"] = terminal
    opportunities["research_buy"] = [
        _research_investor_view(row) for row in (terminal.get("research_buy") or [])
    ] if current else []
    opportunities["research_wait_price"] = [
        _research_investor_view(row) for row in (terminal.get("research_wait_price") or [])
    ] if current else []
    opportunities["research_gap"] = [
        _research_investor_view(row) for row in (terminal.get("research_gap") or [])
    ] if current else []
    opportunities["research_gap_count"] = _int(terminal.get("research_gap_count")) if current else 0
    opportunities["research_reject_count"] = _int(terminal.get("research_reject_count")) if current else 0
    opportunities["urgent_evidence_queue"] = [
        _research_investor_view(row) for row in (terminal.get("urgent_research_queue") or [])
    ] if current else []
    opportunities["research_capital_probe"] = [
        _research_investor_view(row) for row in (terminal.get("capital_probe_queue") or [])
    ] if current else []
    opportunities["research_capital_probe_count"] = len(opportunities["research_capital_probe"])
    opportunities["capital_model_version"] = terminal.get("capital_model_version") or ""
    opportunities["capital_action_counts"] = dict(terminal.get("capital_action_counts") or {})
    opportunities["capital_advisory_authority"] = "ADVISORY_ONLY"
    opportunities["capital_advisory_automatic_execution_allowed"] = False
    opportunities["research_actionable_count"] = (
        len(opportunities["research_buy"]) + len(opportunities["research_wait_price"])
    )
    opportunities["research_terminal_current"] = current
    opportunities["display_rule"] = (
        "Canonical buy_now/wait_price remain Formal/Production mirrors. Research BUY/WAIT_PRICE/RESEARCH_GAP are displayed "
        "separately and only when their source Deep Lambda exactly matches the current deep runtime."
    )
    opportunities["authority_rule"] = (
        "Research BUY/WAIT_PRICE never create Formal BUY, holding-add authorization, or orders. "
        "Formal actions remain FINALIZED_CANONICAL_ONLY; UNKNOWN is never promoted to PASS."
    )

    summary = payload["executive_summary"]
    summary.update(
        {
            "research_terminal_requested_count": _int(terminal.get("requested_count")) if current else 0,
            "research_buy_count": len(opportunities["research_buy"]),
            "research_wait_price_count": len(opportunities["research_wait_price"]),
            "research_gap_count": opportunities["research_gap_count"],
            "research_reject_count": opportunities["research_reject_count"],
            "urgent_evidence_queue_count": len(opportunities["urgent_evidence_queue"]),
            "research_capital_probe_count": opportunities["research_capital_probe_count"],
        }
    )
    payload["decision_readiness"].update(
        {
            "terminal_research_snapshot_available": terminal.get("available") is True,
            "terminal_research_current_for_deep_runtime": current,
            "terminal_research_all_requested_terminal": bool(
                current and terminal.get("all_requested_terminal") is True
            ),
        }
    )


def _stock_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def summarize_candidate_lifecycle(
    state: Mapping[str, Any] | None,
    focus_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Expose durable candidate-memory health and the lifecycle of report-relevant names."""
    raw = dict(state or {})
    candidates = raw.get("candidates") if isinstance(raw.get("candidates"), Mapping) else {}
    active_rows: list[dict[str, Any]] = []
    dormant_count = 0
    archived_or_invalidated_count = 0
    retained_history_event_count = 0
    tier_counts: Counter[str] = Counter()
    by_code: dict[str, dict[str, Any]] = {}
    for key, value in candidates.items():
        if not isinstance(value, Mapping):
            continue
        row = dict(value)
        code = _stock_code(row.get("code") or key)
        state_name = str(row.get("lifecycle_state") or "UNKNOWN").upper()
        history = row.get("history") if isinstance(row.get("history"), list) else []
        retained_history_event_count += len(history)
        item = {
            "code": code,
            "name": str(row.get("stock_name") or ""),
            "lifecycle_state": state_name,
            "research_tier": str(row.get("research_tier") or "UNKNOWN"),
            "seen_count": _int(row.get("seen_count")),
            "last_event": str(row.get("last_event") or ""),
            "last_event_at": str(row.get("last_event_at") or ""),
            "last_formal_action": str(row.get("last_formal_action") or ""),
            "last_valuation_confidence": str(row.get("last_valuation_confidence") or ""),
        }
        by_code[code] = item
        if state_name == "ACTIVE":
            active_rows.append(item)
            tier_counts[item["research_tier"]] += 1
        elif state_name == "DORMANT":
            dormant_count += 1
        elif state_name in {"ARCHIVED", "INVALIDATED"}:
            archived_or_invalidated_count += 1
    active_rows.sort(key=lambda row: (-row["seen_count"], row["code"]))
    focus = []
    for code in focus_codes or []:
        normalized = _stock_code(code)
        if normalized in by_code:
            focus.append(dict(by_code[normalized]))
    authoritative_event_count = (
        _int(raw.get("event_count"))
        if raw.get("event_count") is not None
        else retained_history_event_count
    )
    return {
        "available": bool(candidates),
        "contract_version": str(raw.get("contract_version") or ""),
        "latest_applied_snapshot_id": str(raw.get("latest_applied_snapshot_id") or ""),
        "latest_research_as_of": str(raw.get("latest_research_as_of") or ""),
        "active_candidate_count": len(active_rows),
        "dormant_research_candidate_count": dormant_count,
        "archived_or_invalidated_count": archived_or_invalidated_count,
        "lifecycle_event_count": authoritative_event_count,
        "retained_history_event_count": retained_history_event_count,
        "tier_counts": dict(tier_counts),
        "focus_candidates": focus,
        "focus_by_code": {row["code"]: row for row in focus},
        "most_persistent_candidates": active_rows[:10],
        "discovery_is_filtered_by_lifecycle": False,
        "formal_authority_granted": False,
        "no_auto_trade": True,
        "interpretation": (
            "Candidate Lifecycle preserves research continuity across scans; it does not filter broad discovery "
            "and cannot create Formal trading authority."
        ),
    }


def _attach_holding_valuation_continuity(
    payload: dict[str, Any],
    state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(state or {})
    holdings_state = raw.get("holdings") if isinstance(raw.get("holdings"), Mapping) else {}
    holding_rows = [
        row
        for row in ((payload.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or [])
        if isinstance(row, dict)
    ]
    matched = 0
    for row in holding_rows:
        code = _stock_code(row.get("code"))
        source = holdings_state.get(code) if isinstance(holdings_state, Mapping) else None
        if not isinstance(source, Mapping):
            row["valuation_continuity"] = {}
            continue
        matched += 1
        row["valuation_continuity"] = {
            "action": str(source.get("action") or ""),
            "value_low": _num(source.get("value_low")),
            "neutral_value": _num(source.get("neutral_value")),
            "value_high": _num(source.get("value_high")),
            "current_price": _num(source.get("current_price")),
            "valuation_confidence": str(source.get("valuation_confidence") or ""),
            "valuation_change": str(source.get("valuation_change") or ""),
            "price_value_zone": str(source.get("price_value_zone") or "UNKNOWN"),
            "reason_codes": str(source.get("reason_codes") or ""),
            "decision_date": str(source.get("decision_date") or ""),
            "canonical_snapshot_id": str(source.get("canonical_snapshot_id") or ""),
        }
    summary = {
        "available": bool(holdings_state),
        "contract_version": str(raw.get("contract_version") or ""),
        "latest_applied_snapshot_id": str(raw.get("latest_applied_snapshot_id") or ""),
        "latest_applied_source_run_id": str(raw.get("latest_applied_source_run_id") or ""),
        "tracked_holding_count": len(holdings_state),
        "current_portfolio_match_count": matched,
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "interpretation": (
            "Persisted valuation continuity explains value-zone and causal action history; "
            "this report never recomputes or escalates Formal actions from the state file."
        ),
    }
    payload["holding_valuation_continuity"] = summary
    payload["executive_summary"]["holding_valuation_continuity_match_count"] = matched
    return summary


def _attach_capability_visibility(
    payload: dict[str, Any],
    candidate_lifecycle_state: Mapping[str, Any] | None,
    valuation_continuity: Mapping[str, Any] | None = None,
) -> None:
    holdings = payload.get("pillar_1_holdings_deep_analysis") or {}
    holding_rows = [row for row in (holdings.get("rows") or []) if isinstance(row, dict)]
    opportunities = payload.get("pillar_3_deep_opportunities") or {}
    focus_codes = [str(row.get("code") or "") for row in holding_rows]
    focus_codes.extend(str(row.get("code") or "") for row in (opportunities.get("urgent_evidence_queue") or []))
    lifecycle = summarize_candidate_lifecycle(candidate_lifecycle_state, focus_codes)
    focus_by_code = lifecycle.get("focus_by_code") or {}
    for row in holding_rows:
        row["candidate_lifecycle"] = dict(focus_by_code.get(_stock_code(row.get("code"))) or {})

    runtime = payload.get("deep_calculation_runtime") or {}
    capital = payload.get("pillar_2_world_social_market_capital_map") or {}
    market = capital.get("a_share_market_snapshot") or {}
    coverage = capital.get("capital_evidence_coverage") or {}
    terminal = opportunities.get("terminal_research_snapshot") or {}
    account = payload.get("today_account_plan") or {}
    valuation_covered = sum(
        1
        for row in holding_rows
        if row.get("neutral_value") is not None or bool(str(row.get("valuation_confidence") or "").strip())
    )
    capabilities = [
        {
            "capability": "市场大趋势 / 全A脉搏",
            "status": "ACTIVE" if market.get("status") not in {None, "", "UNAVAILABLE"} else "MISSING",
            "result": f"{market.get('status') or 'UNAVAILABLE'} / score={market.get('score') if market.get('score') is not None else '—'} / {market.get('as_of_date') or '—'}",
        },
        {
            "capability": "持仓 + 估值 + Formal Action",
            "status": "ACTIVE" if holding_rows else "MISSING",
            "result": f"holdings={len(holding_rows)} / valuation-covered={valuation_covered} / formal-source={payload.get('formal_action_source') or '—'}",
        },
        {
            "capability": "持仓估值连续性 / 价值区间",
            "status": "ACTIVE" if (valuation_continuity or {}).get("current_portfolio_match_count", 0) > 0 else "MISSING",
            "result": f"matched={(valuation_continuity or {}).get('current_portfolio_match_count',0)} / tracked={(valuation_continuity or {}).get('tracked_holding_count',0)} / formal-recomputed=False",
        },
        {
            "capability": "Candidate Lifecycle 持续研究记忆",
            "status": "ACTIVE" if lifecycle.get("available") else "MISSING",
            "result": f"active={lifecycle.get('active_candidate_count', 0)} / dormant={lifecycle.get('dormant_research_candidate_count', 0)} / archived-invalidated={lifecycle.get('archived_or_invalidated_count', 0)} / events={lifecycle.get('lifecycle_event_count', 0)} / focus={len(lifecycle.get('focus_candidates') or [])}",
        },
        {
            "capability": "Deep 五类硬门槛 + 官方证据",
            "status": "ACTIVE" if runtime.get("execution_succeeded") else "PARTIAL",
            "result": f"requested={runtime.get('requested_count', 0)} / verified-pass={runtime.get('verified_pass_gate_count', 0)} / unresolved={runtime.get('unresolved_requested_gate_count', 0)}",
        },
        {
            "capability": "Deep Provenance 证据审计",
            "status": "ACTIVE" if runtime.get("provenance_audit_complete") is True else "PARTIAL",
            "result": f"audit={runtime.get('provenance_audit_complete') is True} / run={runtime.get('provenance_audit_run_id') or '—'} / unverified-pass={runtime.get('unverified_pass_gate_count', 0)}",
        },
        {
            "capability": "世界 / 社会 / 资本趋势雷达",
            "status": str(coverage.get("status") or "UNAVAILABLE"),
            "result": " / ".join(
                f"{name}={count}" for name, count in (coverage.get("family_counts") or {}).items()
            ) or "no live evidence families",
        },
        {
            "capability": "Deep Research Terminal",
            "status": "ACTIVE" if terminal.get("available") is True and terminal.get("current_for_deep_runtime") is True else "PARTIAL",
            "result": f"BUY={len(opportunities.get('research_buy') or [])} / WAIT={len(opportunities.get('research_wait_price') or [])} / GAP={opportunities.get('research_gap_count', 0)} / REJECT={opportunities.get('research_reject_count', 0)}",
        },
        {
            "capability": "资金计划 + 执行价覆盖",
            "status": "ACTIVE" if account else "MISSING",
            "result": f"cash={account.get('available_cash_cny', 0)} / immediate={account.get('planned_immediate_cash_cny', 0)} / quotes={account.get('live_quote_applied_count', 0)}/{account.get('live_quote_expected_count', 0)}",
        },
    ]
    payload["candidate_lifecycle"] = lifecycle
    payload["system_capability_visibility"] = {
        "status": "ACTIVE_WITH_LIMITATIONS" if any(row["status"] in {"PARTIAL", "MISSING", "UNAVAILABLE"} for row in capabilities) else "ACTIVE",
        "capabilities": capabilities,
        "interpretation": "Only production-wired capabilities are shown here. A design doc or isolated module does not count as active.",
        "no_auto_trade": True,
    }
    payload["executive_summary"]["active_candidate_lifecycle_count"] = lifecycle.get("active_candidate_count", 0)
    payload["executive_summary"]["lifecycle_event_count"] = lifecycle.get("lifecycle_event_count", 0)


def _finalize_investor_report_readiness(payload: dict[str, Any]) -> None:
    holdings = payload.get("pillar_1_holdings_deep_analysis") or {}
    holding_rows = [row for row in (holdings.get("rows") or []) if isinstance(row, Mapping)]
    opportunities = payload.get("pillar_3_deep_opportunities") or {}
    account = payload.get("today_account_plan") or {}
    capital = payload.get("pillar_2_world_social_market_capital_map") or {}
    coverage = capital.get("capital_evidence_coverage") or {}
    runtime = payload.get("deep_calculation_runtime") or {}

    holding_actions_complete = all(
        bool(str(row.get("investor_action") or "").strip()) for row in holding_rows
    )
    terminal_current = opportunities.get("research_terminal_current") is True
    terminal_available = (opportunities.get("terminal_research_snapshot") or {}).get("available") is True
    account_action_complete = bool(str(account.get("plain_language") or "").strip())

    # A report can remain action-complete while a newer research generation is
    # still running: stale research is not promoted, and the safe candidate
    # action becomes "do not add new exposure yet". Evidence freshness remains
    # a separate limitation below.
    action_complete = bool(holding_actions_complete and account_action_complete)

    limitations: list[str] = []
    if runtime.get("research_complete") is not True:
        limitations.append("DEEP_RESEARCH_EVIDENCE_PARTIAL")
    if terminal_available and not terminal_current:
        limitations.append("TERMINAL_RESEARCH_NOT_CURRENT_FOR_ACTIVE_DEEP")
    if coverage.get("financial_capital_evidence_available") is not True:
        limitations.append("FINANCIAL_CAPITAL_LIVE_EVIDENCE_MISSING")
    if payload.get("decision_readiness", {}).get("validated_macro_to_a_share_handoff_available") is not True:
        limitations.append("ERA_TO_A_SHARE_HANDOFF_NOT_VALIDATED")
    if payload.get("decision_readiness", {}).get("live_execution_quote_coverage_complete") is not True:
        limitations.append("LIVE_EXECUTION_QUOTE_COVERAGE_INCOMPLETE_OR_OFF_SESSION")

    evidence_complete = not limitations
    payload["investor_report_readiness"] = {
        "status": "ACTION_COMPLETE" if action_complete else "ACTION_INCOMPLETE",
        "action_complete": action_complete,
        "evidence_complete": evidence_complete,
        "limitations": limitations,
        "interpretation": (
            "ACTION_COMPLETE means the report still gives a concrete hold/buy-wait/do-not-buy/cash action "
            "without promoting missing evidence. EVIDENCE completeness is tracked separately."
        ),
        "no_auto_trade": True,
    }
    payload["executive_summary"]["investor_action_report_complete"] = action_complete
    payload["executive_summary"]["investor_evidence_complete"] = evidence_complete


def _mark_stale_profile_lineage(payload: dict[str, Any]) -> None:
    """Prevent last-terminal profiles from masquerading as the newest runtime."""

    holdings = payload.get("pillar_1_holdings_deep_analysis")
    if isinstance(holdings, dict):
        holding_count = _int(holdings.get("holding_count"))
        holdings["last_profile_explicit_deep_review_count"] = _int(
            holdings.get("explicit_deep_review_count")
        )
        holdings["last_profile_complete_deep_review_count"] = _int(
            holdings.get("complete_deep_review_count")
        )
        holdings["explicit_deep_review_count"] = 0
        holdings["complete_deep_review_count"] = 0
        holdings["deep_review_gap_count"] = holding_count
        for row in holdings.get("rows") or []:
            if not isinstance(row, dict):
                continue
            deep = row.get("deep_review")
            if not isinstance(deep, dict):
                continue
            deep["last_profile_status"] = deep.get("status") or "DEEP_REVIEW_MISSING"
            deep["status"] = "STALE_PROFILE_LAST_TERMINAL"
            deep["current_for_runtime"] = False

        summary = payload.get("executive_summary")
        if isinstance(summary, dict):
            summary["holdings_complete_deep_review"] = 0
            summary["holdings_deep_review_gaps"] = holding_count

        readiness = payload.get("decision_readiness")
        if isinstance(readiness, dict):
            readiness["all_holdings_explicit_deep_review_complete"] = holding_count == 0

    opportunities = payload.get("pillar_3_deep_opportunities")
    if isinstance(opportunities, dict):
        for key in ("buy_now", "wait_price"):
            for row in opportunities.get(key) or []:
                if not isinstance(row, dict):
                    continue
                deep = row.get("deep_review")
                if not isinstance(deep, dict):
                    continue
                deep["last_profile_status"] = deep.get("status") or "DEEP_REVIEW_MISSING"
                deep["status"] = "STALE_PROFILE_LAST_TERMINAL"
                deep["current_for_runtime"] = False


def _attach_jev_entry_judgments(
    payload: dict[str, Any],
    jev_routing: Mapping[str, Any] | None,
    runtime: Mapping[str, Any],
) -> None:
    """Expose only current, deterministically validated Jev entry judgments."""

    opportunities = payload["pillar_3_deep_opportunities"]
    routing = dict(jev_routing or {})
    runtime_run_id = str(runtime.get("lambda_run_id") or "")
    rows: list[dict[str, Any]] = []
    stale_count = 0
    invalid_count = 0

    if (
        routing.get("contract") != "GEN_GE_JEV_ROUTING_BRIDGE_V1"
        or routing.get("execution_status") != "SUCCESS"
        or routing.get("formal_trading_authority") is not False
        or routing.get("automatic_formal_buy_allowed") is not False
        or routing.get("unknown_is_pass") is not False
        or routing.get("no_auto_trade") is not True
    ):
        opportunities["jev_entry_judgments"] = []
        opportunities["jev_entry_judgment_count"] = 0
        opportunities["jev_entry_now_count"] = 0
        opportunities["jev_entry_judgment_source_run_id"] = str(
            routing.get("source_workflow_run_id") or ""
        )
        opportunities["jev_entry_judgment_status"] = "NOT_AVAILABLE_OR_GUARDRAIL_REJECTED"
        return

    for raw in routing.get("routing_queue") or []:
        if not isinstance(raw, Mapping):
            continue
        entry = raw.get("entry_judgment")
        if not isinstance(entry, Mapping):
            continue
        if (
            entry.get("authority") != "ADVISORY_ONLY"
            or entry.get("formal_buy_authorized") is not False
            or entry.get("automatic_execution_allowed") is not False
            or entry.get("no_auto_trade") is not True
        ):
            invalid_count += 1
            continue
        lineage = entry.get("source_lineage")
        lineage = lineage if isinstance(lineage, Mapping) else {}
        source_deep = str(lineage.get("deep_lambda_run_id") or "")
        if not runtime_run_id or source_deep != runtime_run_id:
            stale_count += 1
            continue
        item = {
            "code": _stock_code(raw.get("entity_id")),
            "name": str(raw.get("entity_name") or ""),
            **dict(entry),
            "jev_route": str(raw.get("route") or ""),
            "jev_route_confidence": raw.get("route_confidence"),
            "source_jev_run_id": str(routing.get("source_workflow_run_id") or ""),
        }
        if item["code"]:
            rows.append(item)

    order = {
        "ENTRY_NOW": 0,
        "WAIT_PRICE": 1,
        "WAIT_EVIDENCE": 2,
        "DO_NOT_CHASE": 3,
        "INVALIDATED": 4,
        "NO_JUDGMENT": 5,
    }
    rows.sort(
        key=lambda row: (
            order.get(str(row.get("validated_judgment") or ""), 99),
            -float(row.get("judgment_confidence") or 0.0),
            str(row.get("code") or ""),
        )
    )
    opportunities["jev_entry_judgments"] = rows
    opportunities["jev_entry_judgment_count"] = len(rows)
    opportunities["jev_entry_now_count"] = sum(
        1 for row in rows if row.get("validated_judgment") == "ENTRY_NOW"
    )
    opportunities["jev_entry_judgment_source_run_id"] = str(
        routing.get("source_workflow_run_id") or ""
    )
    opportunities["jev_entry_judgment_stale_row_count"] = stale_count
    opportunities["jev_entry_judgment_invalid_row_count"] = invalid_count
    opportunities["jev_entry_judgment_status"] = "CURRENT" if rows else "EMPTY_CURRENT"
    opportunities["jev_entry_authority_rule"] = (
        "Jev entry judgments are ADVISORY_ONLY. Numeric price/sizing fields are "
        "deterministically validated; they never create Canonical Formal BUY or orders."
    )
    payload["executive_summary"]["jev_entry_judgment_count"] = len(rows)
    payload["executive_summary"]["jev_entry_now_count"] = opportunities["jev_entry_now_count"]


def build_runtime_decision_center(
    *,
    dashboard: Mapping[str, Any],
    era_radar: Mapping[str, Any],
    automatic_profiles: Mapping[str, Any] | None = None,
    static_profiles: Mapping[str, Any] | None = None,
    deep_calculation_status: Mapping[str, Any] | None = None,
    partial_deep_calculation_status: Mapping[str, Any] | None = None,
    terminal_research_decisions: Mapping[str, Any] | None = None,
    jev_routing: Mapping[str, Any] | None = None,
    era_evidence_bundle: Mapping[str, Any] | None = None,
    candidate_lifecycle_state: Mapping[str, Any] | None = None,
    holding_valuation_continuity_state: Mapping[str, Any] | None = None,
    industry_links: Mapping[str, Any] | None = None,
    era_handoff: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    deep_config, profile_source = choose_deep_review_config(automatic_profiles, static_profiles)
    payload = build_decision_center(
        dashboard=dashboard,
        era_radar=era_radar,
        deep_review_config=deep_config,
        industry_links=industry_links,
        era_handoff=era_handoff,
        generated_at=generated_at,
    )
    capital_coverage = summarize_era_evidence(era_evidence_bundle)
    capital_map = payload["pillar_2_world_social_market_capital_map"]
    capital_map["capital_evidence_coverage"] = capital_coverage
    capital_map["direct_financial_capital_evidence_available"] = capital_coverage[
        "financial_capital_evidence_available"
    ]
    payload["executive_summary"]["capital_flow_evidence_status"] = capital_coverage["status"]
    payload["decision_readiness"]["financial_capital_evidence_available"] = capital_coverage[
        "financial_capital_evidence_available"
    ]
    payload["decision_readiness"]["capital_flow_multi_layer_covered"] = (
        capital_coverage["status"] == "MULTI_LAYER_COVERED"
    )
    selected_status, status_source = select_latest_deep_calculation_status(
        deep_calculation_status,
        partial_deep_calculation_status,
    )
    runtime = normalize_runtime(selected_status)
    last_terminal_runtime = normalize_runtime(deep_calculation_status)
    runtime["status_source"] = status_source
    runtime["last_terminal_run_id"] = last_terminal_runtime.get("lambda_run_id") or ""
    runtime["last_terminal_execution_status"] = last_terminal_runtime.get("execution_status") or "NOT_AVAILABLE"
    runtime["last_terminal_research_terminal_state"] = (
        last_terminal_runtime.get("research_terminal_state") or "NOT_AVAILABLE"
    )
    profile_run_id = str((automatic_profiles or {}).get("lambda_run_id") or "")
    runtime_run_id = str(runtime.get("lambda_run_id") or "")
    profile_current_for_runtime = bool(
        profile_source == "AUTOMATIC_DEEP_CALCULATION"
        and profile_run_id
        and runtime_run_id
        and profile_run_id == runtime_run_id
    )
    if (
        profile_source == "AUTOMATIC_DEEP_CALCULATION"
        and runtime_run_id
        and not profile_current_for_runtime
    ):
        _mark_stale_profile_lineage(payload)
    terminal = normalize_terminal_research(terminal_research_decisions)
    payload["deep_calculation_runtime"] = runtime
    payload["deep_review_profile_source"] = profile_source
    payload["deep_review_profile_lambda_run_id"] = profile_run_id
    payload["deep_review_profile_current_for_runtime"] = profile_current_for_runtime
    payload["deep_review_profile_lineage_state"] = (
        "CURRENT"
        if profile_current_for_runtime
        else "STALE_LAST_TERMINAL"
        if profile_source == "AUTOMATIC_DEEP_CALCULATION" and runtime_run_id
        else "UNVERIFIED"
    )
    payload["executive_summary"].update(
        {
            "deep_calculation_execution_status": runtime["execution_status"],
            "deep_calculation_research_outcome": runtime["research_outcome"],
            "deep_calculation_terminal_state": runtime["research_terminal_state"],
            "deep_calculation_unresolved_gate_count": runtime["unresolved_requested_gate_count"],
            "deep_calculation_progressed_gate_count": runtime["progressed_gate_count"],
        }
    )
    payload["decision_readiness"].update(
        {
            "deep_calculation_last_run_completed": runtime["execution_completed"],
            "deep_calculation_last_run_successful": runtime["execution_succeeded"],
            "deep_calculation_process_terminal": runtime["research_process_terminal"],
            "deep_calculation_requested_research_complete": runtime["research_complete"],
            "deep_calculation_manual_next_round_required": runtime["manual_next_round_required"],
            "deep_review_profile_current_for_runtime": profile_current_for_runtime,
        }
    )
    _attach_terminal_research(payload, terminal, runtime)
    _attach_jev_entry_judgments(payload, jev_routing, runtime)
    terminal_research_codes: set[str] = set()
    if (
        terminal.get("available") is True
        and runtime_run_id
        and str(terminal.get("source_deep_lambda_run_id") or "") == runtime_run_id
    ):
        terminal_research_codes = {
            _stock_code(row.get("code"))
            for row in ((terminal_research_decisions or {}).get("terminal_rows") or [])
            if isinstance(row, Mapping) and _stock_code(row.get("code"))
        }
    _attach_deep_qualified_research_leads(
        payload,
        automatic_profiles,
        profile_current_for_runtime=profile_current_for_runtime,
        terminal_research_codes=terminal_research_codes,
    )
    valuation_continuity = _attach_holding_valuation_continuity(
        payload, holding_valuation_continuity_state
    )
    _attach_capability_visibility(payload, candidate_lifecycle_state, valuation_continuity)
    _finalize_investor_report_readiness(payload)
    return payload


def _unresolved_text(reasons: Mapping[str, Any]) -> str:
    if not reasons:
        return "当前 checkpoint 未携带逐股未决明细"
    reason_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    examples: list[str] = []
    for code, gates in reasons.items():
        if isinstance(gates, Mapping):
            for gate, reason in gates.items():
                gate_counts[str(gate)] += 1
                reason_counts[str(reason)] += 1
            if len(examples) < 5:
                names = "、".join(f"{gate}:{reason}" for gate, reason in list(gates.items())[:3])
                examples.append(f"{code}[{names}]")
        else:
            reason_counts[str(gates)] += 1
            if len(examples) < 5:
                examples.append(f"{code}[{gates}]")
    top_reasons = "、".join(f"{reason}×{count}" for reason, count in reason_counts.most_common(5))
    top_gates = "、".join(f"{gate}×{count}" for gate, count in gate_counts.most_common(5))
    sample = "；".join(examples) or "无"
    return (
        f"涉及 {len(reasons)} 只；门槛分布：{top_gates or '无'}；"
        f"Top原因：{top_reasons or '无'}；样例：{sample}"
    )


def _runtime_metric_text(runtime: Mapping[str, Any], key: str) -> str:
    if runtime.get(f"{key}_available") is not True:
        return "未携带"
    return str(runtime.get(key, 0))


def _code_list_text(codes: list[Any], limit: int = 12) -> str:
    normalized = [str(code) for code in codes if str(code or "").strip()]
    if not normalized:
        return "无"
    shown = "、".join(normalized[:limit])
    remaining = len(normalized) - limit
    return f"{shown}（另 {remaining} 只）" if remaining > 0 else shown


def _urgent_text(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return "无"
    parts: list[str] = []
    for row in rows[:10]:
        code = str(row.get("code") or "")
        name = str(row.get("name") or "")
        score = row.get("quant_score")
        action = str(row.get("investor_action") or "暂不买")
        parts.append(f"{code} {name}(quant={score}；{action})".strip())
    return "；".join(parts)


def render_runtime_markdown(payload: Mapping[str, Any]) -> str:
    base = render_markdown(payload).rstrip()
    runtime = payload.get("deep_calculation_runtime") or {}
    source = payload.get("deep_review_profile_source") or "UNKNOWN"
    profile_run_id = payload.get("deep_review_profile_lambda_run_id") or ""
    profile_current = payload.get("deep_review_profile_current_for_runtime") is True
    missing = runtime.get("missing_requested_codes") or []
    opportunities = payload.get("pillar_3_deep_opportunities") or {}
    terminal = opportunities.get("terminal_research_snapshot") or {}
    report_ready = payload.get("investor_report_readiness") or {}
    lines = [
        "",
        "## 今日汇报可执行性",
        "",
        f"- 行动结论完整：**{report_ready.get('action_complete') is True}**；证据完整：**{report_ready.get('evidence_complete') is True}**。",
        f"- 当前限制：{_code_list_text(report_ready.get('limitations') or [], limit=10)}。",
        "- 证据不完整不会被冒充 PASS；但它必须被翻译成暂不买、等待、持有或保留现金等明确动作。",
        "",
        "## 本次汇报真正用了哪些系统能力",
        "",
        "| 能力 | 状态 | 当前真正产出的结果 |",
        "|---|---|---|",
        *[
            f"| {row.get('capability','—')} | **{row.get('status','UNKNOWN')}** | {row.get('result','—')} |"
            for row in ((payload.get("system_capability_visibility") or {}).get("capabilities") or [])
        ],
        "",
        f"- Candidate Lifecycle：当前 ACTIVE **{(payload.get('candidate_lifecycle') or {}).get('active_candidate_count', 0)}**；DORMANT **{(payload.get('candidate_lifecycle') or {}).get('dormant_research_candidate_count', 0)}**；ARCHIVED/INVALIDATED **{(payload.get('candidate_lifecycle') or {}).get('archived_or_invalidated_count', 0)}**；累计生命周期事件 **{(payload.get('candidate_lifecycle') or {}).get('lifecycle_event_count', 0)}**。DORMANT 表示当前证据 epoch 的研究策略已耗尽，等待新研究证据；它不是归档或失效。",
        "- 上表只统计已经进入生产链并影响最终汇报的能力；仅存在于设计文档、孤立模块或过期 artifact 的功能不算 ACTIVE。",
        "",
        "### 当前持仓的持续研究记忆",
        "",
        *(
            [
                f"- {row.get('name','')} {row.get('code','')}：{(row.get('candidate_lifecycle') or {}).get('lifecycle_state','未进入生命周期')} / tier={(row.get('candidate_lifecycle') or {}).get('research_tier','—')} / 历史被系统重新看见 {(row.get('candidate_lifecycle') or {}).get('seen_count',0)} 次。"
                for row in ((payload.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or [])
            ]
        ),
        "",
        "## 自动深算运行状态",
        "",
        f"- 当前运行状态来源：**{runtime.get('status_source') or 'NOT_AVAILABLE'}**",
        f"- 深算资料来源：**{source}**；资料 Lambda：`{profile_run_id or '—'}`；与当前运行一致：**{profile_current}**",
        (
            "- ⚠️ 最新自动 profiles 属于上一轮 Deep runtime；顶部持仓/机会的深算完整度已按当前 runtime 视为未完成，"
            "旧 profile 状态仅保留为 last_profile_status 供审计。"
            if source == "AUTOMATIC_DEEP_CALCULATION" and runtime.get("lambda_run_id") and not profile_current
            else "- 深算 profile lineage 与当前 runtime 一致。"
            if profile_current
            else "- 深算 profile lineage 尚未被证明与当前 runtime 一致。"
        ),
        f"- Lambda run：`{runtime.get('lambda_run_id') or '—'}`",
        f"- 触发来源：`{runtime.get('trigger_source') or '—'}`",
        f"- 计算执行：**{runtime.get('execution_status') or 'NOT_AVAILABLE'}**",
        f"- 运行状态：**{runtime.get('run_state') or 'NOT_AVAILABLE'}**",
        f"- 研究过程终态：**{runtime.get('research_terminal_state') or 'NOT_AVAILABLE'}**",
        f"- 请求深算：**{_runtime_metric_text(runtime, 'requested_count')}**；已处理：**{_runtime_metric_text(runtime, 'processed_requested_count')}**；完整：**{_runtime_metric_text(runtime, 'complete_requested_count')}**；证据穷尽：**{_runtime_metric_text(runtime, 'evidence_exhausted_requested_count')}**。",
        f"- Workset profile：总数 **{_runtime_metric_text(runtime, 'profile_count')}**；请求代码已落 profile **{_runtime_metric_text(runtime, 'requested_profile_count')}**；handoff 未完成 **{_runtime_metric_text(runtime, 'handoff_incomplete_requested_count')}**；覆盖可审计：**{runtime.get('workset_coverage_known') is True}**；完整覆盖：**{runtime.get('workset_coverage_complete') is True}**。",
        f"- 同轮补证据尝试：**{runtime.get('gap_closure_attempt_count', 0)}**；取得证据：**{runtime.get('new_evidence_count', 0)}**；推进硬门槛：**{runtime.get('progressed_gate_count', 0)}**。",
        f"- 尚未解决硬门槛：**{_runtime_metric_text(runtime, 'unresolved_requested_gate_count')}**。",
        f"- 未决原因摘要：{_unresolved_text(runtime.get('unresolved_reasons') or {})}",
        (
            f"- 请求但未进入本次研究工件：**{_code_list_text(missing)}**。"
            if runtime.get("missing_requested_codes_available") is True
            else "- 请求但未进入本次研究工件：**未携带**。"
        ),
        f"- 上一次完整终态 run：`{runtime.get('last_terminal_run_id') or '—'}`；执行 **{runtime.get('last_terminal_execution_status') or 'NOT_AVAILABLE'}**；研究终态 **{runtime.get('last_terminal_research_terminal_state') or 'NOT_AVAILABLE'}**。",
        f"- 是否需要你手工开启下一轮：**{runtime.get('manual_next_round_required', True)}**。",
        "- **执行 SUCCESS 不等于研究 COMPLETE**；EVIDENCE_EXHAUSTED 只表示已进入 profile 的对象完成了有界补证；HANDOFF_INCOMPLETE 表示仍有请求代码未进入 profile，二者都不会把 UNKNOWN 当成 PASS。",
        "",
        "## 五类硬门槛已通过的研究线索",
        "",
        f"- 当前 runtime 中非持仓、非 Formal BUY/WAIT_PRICE、五类硬门槛全部明确 PASS：**{opportunities.get('deep_qualified_research_lead_count', 0)}**。",
        *[
            f"- **{row.get('code')} {row.get('name')}**（{row.get('industry') or '行业未标注'}）：硬门槛 **{row.get('hard_gate_pass_count', 0)}/{row.get('hard_gate_total_count', 5)} PASS**；下一步 **继续估值、价格与 Formal authority 闭环**；当前账户动作 **暂不买**。"
            for row in (opportunities.get("deep_qualified_research_leads") or [])
        ],
        "- 这是一层研究资格可见性，不是 BUY/WAIT_PRICE；不会改变阈值、不会把 UNKNOWN 当 PASS，也不会创建 Formal 交易权限。",
        "",
        "## 深算终态研究决策",
        "",
        f"- 终态快照存在：**{terminal.get('available') is True}**；与当前 Deep Lambda 一致：**{terminal.get('current_for_deep_runtime') is True}**。",
        f"- 终态来源 Lambda：`{terminal.get('source_deep_lambda_run_id') or '—'}`；当前 Lambda：`{runtime.get('lambda_run_id') or '—'}`。",
        f"- 请求：**{terminal.get('requested_count', 0) if terminal.get('current_for_deep_runtime') else 0}**；研究 BUY：**{len(opportunities.get('research_buy') or [])}**；研究 WAIT_PRICE：**{len(opportunities.get('research_wait_price') or [])}**；研究 RESEARCH_GAP：**{opportunities.get('research_gap_count', 0)}**；研究 REJECT：**{opportunities.get('research_reject_count', 0)}**。",
        f"- 高吸引力但证据不足、优先补证：{_urgent_text(opportunities.get('urgent_evidence_queue') or [])}",
        f"- 风险预算层 BUILD/PROBE 候选：**{opportunities.get('research_capital_probe_count', 0)}**；该层只把不确定性映射为仓位上限，不把 UNKNOWN 改成 PASS。",
        *[
            f"  - {row.get('code')} {row.get('name')}: **{(row.get('capital_allocation') or {}).get('action')}**；conviction={(row.get('capital_allocation') or {}).get('capital_conviction_score')}；建议账户上限={(row.get('capital_allocation') or {}).get('suggested_max_portfolio_pct')}%"
            for row in (opportunities.get("research_capital_probe") or [])
        ],
        "- **研究 BUY/WAIT_PRICE 与 Formal/Production 权限严格分离**；风险预算建议同样不创建 Formal BUY、持仓加仓授权或自动交易。",
        "",
        "## Jev 买入判断（研究建议，不是 Formal BUY）",
        "",
        f"- 当前可用判断：**{opportunities.get('jev_entry_judgment_count', 0)}**；其中 ENTRY_NOW **{opportunities.get('jev_entry_now_count', 0)}**；Jev run：`{opportunities.get('jev_entry_judgment_source_run_id') or '—'}`。",
        *[
            (
                f"- **{row.get('code')} {row.get('name')}**：**{row.get('validated_judgment')}**；"
                f"触发={row.get('entry_trigger') or '—'}；"
                f"买入价上限={row.get('entry_price_zone_high') if row.get('entry_price_zone_high') is not None else '—'}；"
                f"首仓={row.get('initial_manual_position_pct', 0)}%；"
                f"最大研究仓位={row.get('max_manual_position_pct', 0)}%；"
                f"加仓条件={row.get('add_condition') or '—'}；"
                f"不追条件={row.get('do_not_chase_condition') or '—'}；"
                f"失效条件={row.get('invalidation_condition') or '—'}。"
            )
            for row in (opportunities.get("jev_entry_judgments") or [])
        ],
        "- Jev 负责判断；价格阈值和仓位必须通过 deterministic 校验。该层 authority=ADVISORY_ONLY，Formal BUY=false，automatic execution=false。",
        "",
        "> 自动触发、自动计算、同轮补证据/有界重试、自动终结、自动持久化、自动刷新决策中心；Formal BUY 权限仍只来自既有 Canonical/Production authority，no_auto_trade=true。",
        "",
    ]
    return base + "\n" + "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard", type=Path, default=Path("data/investor_decision_dashboard/latest.json"))
    parser.add_argument("--era-radar", type=Path, default=Path("data/era_radar/latest.json"))
    parser.add_argument("--era-evidence", type=Path, default=None)
    parser.add_argument("--candidate-lifecycle", type=Path, default=Path("data/opportunity_snapshots/candidate_lifecycle_state.json"))
    parser.add_argument("--holding-valuation-continuity", type=Path, default=Path("data/opportunity_snapshots/holding_valuation_continuity_state.json"))
    parser.add_argument("--era-handoff", type=Path, default=Path("data/era_radar/research_handoff/latest.json"))
    parser.add_argument("--automatic-deep-reviews", type=Path, default=Path("data/deep_calculation/latest_profiles.json"))
    parser.add_argument("--static-deep-reviews", type=Path, default=Path("config/v31_explicit_deep_reviews.json"))
    parser.add_argument("--deep-calculation-status", type=Path, default=Path("data/deep_calculation/latest_status.json"))
    parser.add_argument("--deep-calculation-partial-status", type=Path, default=Path("data/deep_calculation/latest_partial_status.json"))
    parser.add_argument("--terminal-research-decisions", type=Path, default=Path("data/deep_calculation/latest_research_decisions.json"))
    parser.add_argument("--jev-routing", type=Path, default=Path("data/jev_shadow/latest_routing.json"))
    parser.add_argument("--industry-links", type=Path, default=Path("config/era_radar_industry_links.json"))
    parser.add_argument("--output-json", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("LATEST_DECISION_CENTER.md"))
    args = parser.parse_args()

    era_radar = _json(args.era_radar)
    era_evidence_path = args.era_evidence
    if era_evidence_path is None:
        snapshot_id = str(era_radar.get("snapshot_id") or "").strip()
        era_evidence_path = (
            args.era_radar.parent / "evidence" / f"{snapshot_id}.json"
            if snapshot_id
            else None
        )

    payload = build_runtime_decision_center(
        dashboard=_json(args.dashboard),
        era_radar=era_radar,
        automatic_profiles=_json(args.automatic_deep_reviews),
        static_profiles=_json(args.static_deep_reviews),
        deep_calculation_status=_json(args.deep_calculation_status),
        partial_deep_calculation_status=_json(args.deep_calculation_partial_status),
        terminal_research_decisions=_json(args.terminal_research_decisions),
        jev_routing=_json(args.jev_routing),
        era_evidence_bundle=_json(era_evidence_path),
        candidate_lifecycle_state=_json(args.candidate_lifecycle),
        holding_valuation_continuity_state=_json(args.holding_valuation_continuity),
        industry_links=_json(args.industry_links),
        era_handoff=_json(args.era_handoff),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_runtime_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["executive_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
