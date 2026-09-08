"""Runtime-aware producer for the three-pillar investor decision center.

The decision-center composer remains the authority-preserving composition layer.
This producer adds operational observability for event-driven deep calculation
and prefers automatically generated profiles over static bootstrap reviews.

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


def build_runtime_decision_center(
    *,
    dashboard: Mapping[str, Any],
    era_radar: Mapping[str, Any],
    automatic_profiles: Mapping[str, Any] | None = None,
    static_profiles: Mapping[str, Any] | None = None,
    deep_calculation_status: Mapping[str, Any] | None = None,
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


def render_runtime_markdown(payload: Mapping[str, Any]) -> str:
    base = render_markdown(payload).rstrip()
    runtime = payload.get("deep_calculation_runtime") or {}
    source = payload.get("deep_review_profile_source") or "UNKNOWN"
    missing = runtime.get("missing_requested_codes") or []
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
