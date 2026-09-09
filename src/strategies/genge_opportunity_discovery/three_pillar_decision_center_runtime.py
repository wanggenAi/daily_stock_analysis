"""Runtime-aware producer for the three-pillar investor decision center.

The decision-center composer remains the authority-preserving composition layer.
This producer adds operational observability for event-driven deep calculation,
prefers automatically generated profiles over static bootstrap reviews, and
exposes terminal research-only BUY / WAIT_PRICE / REJECT separately from
Canonical/Production actions.

Execution completion, process-terminal closure and research completeness are
separate concepts. COMPLETE means every requested gate is resolved;
EVIDENCE_EXHAUSTED means the same Lambda finished bounded evidence recovery but
some gates remain UNKNOWN. UNKNOWN is never converted to PASS here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .three_pillar_decision_center import build_decision_center, render_markdown

RUNTIME_CONTRACT = "GEN_GE_THREE_PILLAR_DEEP_CALC_RUNTIME_V2"
TERMINAL_RESEARCH_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
TERMINAL_DECISIONS = frozenset({"BUY", "WAIT_PRICE", "REJECT"})


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


def normalize_runtime(status: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(status or {})
    execution = str(raw.get("execution_status") or "NOT_AVAILABLE").upper()
    research = str(raw.get("research_outcome") or "NOT_AVAILABLE").upper()
    terminal = str(raw.get("research_terminal_state") or research or "NOT_AVAILABLE").upper()
    run_state = str(raw.get("run_state") or "NOT_AVAILABLE").upper()
    missing = list(raw.get("missing_requested_codes") or [])
    requested = _int(raw.get("requested_count"))
    exhausted_count = _int(raw.get("evidence_exhausted_requested_count"))
    processed = _int(raw.get("processed_requested_count"))
    if not processed and requested and not missing:
        processed = requested
    partial = _int(raw.get("partial_requested_count"))
    if not partial and terminal == "EVIDENCE_EXHAUSTED":
        partial = exhausted_count or max(0, requested - _int(raw.get("complete_requested_count")))
    unresolved_reasons = raw.get("unresolved_reasons")
    if not isinstance(unresolved_reasons, Mapping):
        unresolved_reasons = {}
    immediate_retry = raw.get("immediate_retry_required") is True
    terminal_process = terminal in {"COMPLETE", "EVIDENCE_EXHAUSTED"}
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
        "processed_requested_count": processed,
        "complete_requested_count": _int(raw.get("complete_requested_count")),
        "partial_requested_count": partial,
        "evidence_exhausted_requested_count": exhausted_count,
        "unresolved_requested_gate_count": _int(raw.get("unresolved_requested_gate_count")),
        "missing_requested_codes": missing,
        "unresolved_reasons": dict(unresolved_reasons),
        "gap_closure_attempt_count": _int(raw.get("gap_closure_attempt_count")),
        "new_evidence_count": _int(raw.get("new_evidence_count")),
        "progressed_gate_count": _int(raw.get("progressed_gate_count")),
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
            "EVIDENCE_EXHAUSTED means bounded same-run recovery finished while unresolved UNKNOWN gates remain."
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
            "decision_counts": {"BUY": 0, "WAIT_PRICE": 0, "REJECT": 0},
            "all_requested_terminal": False,
            "research_buy": [],
            "research_wait_price": [],
            "research_reject_count": 0,
            "urgent_research_queue": [],
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
    reject_count = 0
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
        if decision == "BUY":
            buy.append(row)
        elif decision == "WAIT_PRICE":
            wait.append(row)
        else:
            reject_count += 1

    raw_counts = raw.get("decision_counts") if isinstance(raw.get("decision_counts"), Mapping) else {}
    counts = {
        "BUY": _int(raw_counts.get("BUY")),
        "WAIT_PRICE": _int(raw_counts.get("WAIT_PRICE")),
        "REJECT": _int(raw_counts.get("REJECT")),
    }
    actual_counts = {"BUY": len(buy), "WAIT_PRICE": len(wait), "REJECT": reject_count}
    if counts != actual_counts or sum(counts.values()) != requested:
        raise ValueError("terminal research decision_counts do not match terminal rows")

    urgent = [dict(row) for row in (raw.get("urgent_research_queue") or []) if isinstance(row, Mapping)]
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
        "research_reject_count": reject_count,
        "urgent_research_queue": urgent,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


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
    opportunities["research_buy"] = list(terminal.get("research_buy") or []) if current else []
    opportunities["research_wait_price"] = list(terminal.get("research_wait_price") or []) if current else []
    opportunities["research_reject_count"] = _int(terminal.get("research_reject_count")) if current else 0
    opportunities["urgent_evidence_queue"] = list(terminal.get("urgent_research_queue") or []) if current else []
    opportunities["research_actionable_count"] = (
        len(opportunities["research_buy"]) + len(opportunities["research_wait_price"])
    )
    opportunities["research_terminal_current"] = current
    opportunities["display_rule"] = (
        "Canonical buy_now/wait_price remain Formal/Production mirrors. Research BUY/WAIT_PRICE are displayed "
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
            "research_reject_count": opportunities["research_reject_count"],
            "urgent_evidence_queue_count": len(opportunities["urgent_evidence_queue"]),
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


def build_runtime_decision_center(
    *,
    dashboard: Mapping[str, Any],
    era_radar: Mapping[str, Any],
    automatic_profiles: Mapping[str, Any] | None = None,
    static_profiles: Mapping[str, Any] | None = None,
    deep_calculation_status: Mapping[str, Any] | None = None,
    terminal_research_decisions: Mapping[str, Any] | None = None,
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
    runtime = normalize_runtime(deep_calculation_status)
    terminal = normalize_terminal_research(terminal_research_decisions)
    payload["deep_calculation_runtime"] = runtime
    payload["deep_review_profile_source"] = profile_source
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
        }
    )
    _attach_terminal_research(payload, terminal, runtime)
    return payload


def _unresolved_text(reasons: Mapping[str, Any]) -> str:
    if not reasons:
        return "无"
    parts: list[str] = []
    for code, gates in reasons.items():
        if isinstance(gates, Mapping):
            names = "、".join(f"{gate}:{reason}" for gate, reason in gates.items())
            parts.append(f"{code}[{names}]")
        else:
            parts.append(f"{code}[{gates}]")
    return "；".join(parts)


def _urgent_text(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return "无"
    parts: list[str] = []
    for row in rows[:10]:
        code = str(row.get("code") or "")
        name = str(row.get("name") or "")
        score = row.get("quant_score")
        parts.append(f"{code} {name}(quant={score})".strip())
    return "；".join(parts)


def render_runtime_markdown(payload: Mapping[str, Any]) -> str:
    base = render_markdown(payload).rstrip()
    runtime = payload.get("deep_calculation_runtime") or {}
    source = payload.get("deep_review_profile_source") or "UNKNOWN"
    missing = runtime.get("missing_requested_codes") or []
    opportunities = payload.get("pillar_3_deep_opportunities") or {}
    terminal = opportunities.get("terminal_research_snapshot") or {}
    lines = [
        "",
        "## 自动深算运行状态",
        "",
        f"- 深算资料来源：**{source}**",
        f"- Lambda run：`{runtime.get('lambda_run_id') or '—'}`",
        f"- 触发来源：`{runtime.get('trigger_source') or '—'}`",
        f"- 计算执行：**{runtime.get('execution_status') or 'NOT_AVAILABLE'}**",
        f"- 运行状态：**{runtime.get('run_state') or 'NOT_AVAILABLE'}**",
        f"- 研究过程终态：**{runtime.get('research_terminal_state') or 'NOT_AVAILABLE'}**",
        f"- 请求深算：**{runtime.get('requested_count', 0)}**；已处理：**{runtime.get('processed_requested_count', 0)}**；完整：**{runtime.get('complete_requested_count', 0)}**；证据穷尽：**{runtime.get('evidence_exhausted_requested_count', 0)}**。",
        f"- 同轮补证据尝试：**{runtime.get('gap_closure_attempt_count', 0)}**；取得证据：**{runtime.get('new_evidence_count', 0)}**；推进硬门槛：**{runtime.get('progressed_gate_count', 0)}**。",
        f"- 尚未解决硬门槛：**{runtime.get('unresolved_requested_gate_count', 0)}**。",
        f"- 未决原因：{_unresolved_text(runtime.get('unresolved_reasons') or {})}",
        f"- 请求但未进入本次研究工件：**{'、'.join(missing) if missing else '无'}**。",
        f"- 是否需要你手工开启下一轮：**{runtime.get('manual_next_round_required', True)}**。",
        "- **执行 SUCCESS 不等于研究 COMPLETE**；EVIDENCE_EXHAUSTED 是流程已自动收口，不代表 UNKNOWN 被当成 PASS。",
        "",
        "## 深算终态研究决策",
        "",
        f"- 终态快照存在：**{terminal.get('available') is True}**；与当前 Deep Lambda 一致：**{terminal.get('current_for_deep_runtime') is True}**。",
        f"- 终态来源 Lambda：`{terminal.get('source_deep_lambda_run_id') or '—'}`；当前 Lambda：`{runtime.get('lambda_run_id') or '—'}`。",
        f"- 请求：**{terminal.get('requested_count', 0) if terminal.get('current_for_deep_runtime') else 0}**；研究 BUY：**{len(opportunities.get('research_buy') or [])}**；研究 WAIT_PRICE：**{len(opportunities.get('research_wait_price') or [])}**；研究 REJECT：**{opportunities.get('research_reject_count', 0)}**。",
        f"- 高吸引力但证据不足、优先补证：{_urgent_text(opportunities.get('urgent_evidence_queue') or [])}",
        "- **研究 BUY/WAIT_PRICE 与 Formal/Production 权限严格分离**；这里只提供研究动作，不会创建 Formal BUY、持仓加仓授权或自动交易。",
        "",
        "> 自动触发、自动计算、同轮补证据/有界重试、自动终结、自动持久化、自动刷新决策中心；Formal BUY 权限仍只来自既有 Canonical/Production authority，no_auto_trade=true。",
        "",
    ]
    return base + "\n" + "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard", type=Path, default=Path("data/investor_decision_dashboard/latest.json"))
    parser.add_argument("--era-radar", type=Path, default=Path("data/era_radar/latest.json"))
    parser.add_argument("--era-handoff", type=Path, default=Path("data/era_radar/research_handoff/latest.json"))
    parser.add_argument("--automatic-deep-reviews", type=Path, default=Path("data/deep_calculation/latest_profiles.json"))
    parser.add_argument("--static-deep-reviews", type=Path, default=Path("config/v31_explicit_deep_reviews.json"))
    parser.add_argument("--deep-calculation-status", type=Path, default=Path("data/deep_calculation/latest_status.json"))
    parser.add_argument("--terminal-research-decisions", type=Path, default=Path("data/deep_calculation/latest_research_decisions.json"))
    parser.add_argument("--industry-links", type=Path, default=Path("config/era_radar_industry_links.json"))
    parser.add_argument("--output-json", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("LATEST_DECISION_CENTER.md"))
    args = parser.parse_args()

    payload = build_runtime_decision_center(
        dashboard=_json(args.dashboard),
        era_radar=_json(args.era_radar),
        automatic_profiles=_json(args.automatic_deep_reviews),
        static_profiles=_json(args.static_deep_reviews),
        deep_calculation_status=_json(args.deep_calculation_status),
        terminal_research_decisions=_json(args.terminal_research_decisions),
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
