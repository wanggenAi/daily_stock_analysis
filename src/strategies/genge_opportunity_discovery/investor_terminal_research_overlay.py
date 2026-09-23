"""Overlay research-only Deep Terminal decisions onto the investor dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

TERMINAL_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
TERMINAL_DECISIONS = {"BUY", "WAIT_PRICE", "RESEARCH_GAP", "REJECT"}
CAPITAL_ACTIONS = ("BUILD", "PROBE", "WATCH", "BLOCK")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def normalize_terminal_research(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("contract") != TERMINAL_CONTRACT:
        raise ValueError("unexpected terminal research contract")
    required = {
        "all_requested_terminal": True,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValueError(f"terminal research contract violation: {key}")

    rows = payload.get("terminal_rows") or []
    if not isinstance(rows, list):
        raise ValueError("terminal_rows must be a list")
    normalized_rows: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("terminal row must be an object")
        decision = str(raw.get("research_decision") or "").upper()
        if decision not in TERMINAL_DECISIONS:
            raise ValueError(f"invalid research decision: {decision}")
        if raw.get("research_authority") != "RESEARCH_ONLY" or raw.get("formal_buy_authorized") is not False or raw.get("no_auto_trade") is not True:
            raise ValueError("terminal row gained forbidden authority")
        normalized_rows.append(dict(raw))

    requested_count = int(payload.get("requested_count") or 0)
    counts = {d: sum(row.get("research_decision") == d for row in normalized_rows) for d in TERMINAL_DECISIONS}
    source_counts = payload.get("decision_counts") or {}
    if requested_count != len(normalized_rows) or requested_count != sum(counts.values()):
        raise ValueError("terminal research requested/count mismatch")
    if any(int(source_counts.get(d) or 0) != counts[d] for d in TERMINAL_DECISIONS):
        raise ValueError("terminal research decision_counts mismatch")

    capital_model_version = str(payload.get("capital_model_version") or "")
    capital_action_counts = {action: 0 for action in CAPITAL_ACTIONS}
    capital_probe_rows: list[dict[str, Any]] = []
    for row in normalized_rows:
        capital = row.get("capital_allocation")
        if not isinstance(capital, Mapping):
            if capital_model_version:
                raise ValueError("capital model row missing capital_allocation")
            continue
        action = str(capital.get("action") or "").upper()
        if action not in capital_action_counts:
            raise ValueError(f"invalid capital advisory action: {action or 'EMPTY'}")
        if capital.get("authority") != "ADVISORY_ONLY":
            raise ValueError("capital advisory gained forbidden authority")
        if capital.get("automatic_execution_allowed") is not False:
            raise ValueError("capital advisory cannot enable automatic execution")
        if capital.get("formal_buy_authorized") is not False:
            raise ValueError("capital advisory cannot grant Formal BUY")
        if capital.get("no_auto_trade") is not True:
            raise ValueError("capital advisory lost no-auto-trade")
        capital_action_counts[action] += 1
        if action in {"BUILD", "PROBE"}:
            capital_probe_rows.append(row)

    if capital_model_version:
        if payload.get("capital_advisory_authority") != "ADVISORY_ONLY":
            raise ValueError("terminal capital advisory authority mismatch")
        if payload.get("capital_advisory_automatic_execution_allowed") is not False:
            raise ValueError("terminal capital advisory cannot auto-execute")
        source_capital_counts = payload.get("capital_action_counts")
        if not isinstance(source_capital_counts, Mapping):
            raise ValueError("capital_action_counts missing for capital model")
        expected_capital_counts = {
            action: int(source_capital_counts.get(action) or 0)
            for action in CAPITAL_ACTIONS
        }
        if expected_capital_counts != capital_action_counts:
            raise ValueError("terminal capital_action_counts mismatch")
        if sum(capital_action_counts.values()) != requested_count:
            raise ValueError("capital advisory rows do not cover terminal workset")
        source_probe = payload.get("capital_probe_queue")
        if not isinstance(source_probe, list):
            raise ValueError("capital_probe_queue missing for capital model")
        source_probe_keys = sorted(
            (str(row.get("code") or ""), str((row.get("capital_allocation") or {}).get("action") or ""))
            for row in source_probe
            if isinstance(row, Mapping)
        )
        actual_probe_keys = sorted(
            (str(row.get("code") or ""), str((row.get("capital_allocation") or {}).get("action") or ""))
            for row in capital_probe_rows
        )
        if source_probe_keys != actual_probe_keys:
            raise ValueError("capital_probe_queue mismatch")

    urgent = payload.get("urgent_research_queue") or []
    if not isinstance(urgent, list):
        raise ValueError("urgent_research_queue must be a list")
    row_codes = {str(row.get("code") or "") for row in normalized_rows}
    urgent_rows = []
    for raw in urgent:
        if not isinstance(raw, Mapping) or str(raw.get("code") or "") not in row_codes:
            raise ValueError("urgent research row is outside terminal workset")
        if raw.get("research_decision") != "RESEARCH_GAP":
            raise ValueError("urgent research must remain RESEARCH_GAP")
        urgent_rows.append(dict(raw))

    return {
        "available": True,
        "contract": TERMINAL_CONTRACT,
        "source_deep_lambda_run_id": str(payload.get("source_deep_lambda_run_id") or ""),
        "source_every_industry_run_id": str(payload.get("source_every_industry_run_id") or ""),
        "requested_count": requested_count,
        "decision_counts": counts,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "terminal_rows": normalized_rows,
        "urgent_research_queue": urgent_rows,
        "urgent_research_count": len(urgent_rows),
        "capital_model_version": capital_model_version,
        "capital_action_counts": capital_action_counts,
        "capital_probe_queue": capital_probe_rows,
        "capital_probe_count": len(capital_probe_rows),
        "capital_advisory_authority": "ADVISORY_ONLY",
        "capital_advisory_automatic_execution_allowed": False,
    }


def apply_overlay(dashboard: Mapping[str, Any], terminal_payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(dashboard)
    if out.get("formal_action_source") != "FINALIZED_CANONICAL_ONLY" or out.get("formal_action_recomputed") is not False:
        raise ValueError("investor dashboard Formal authority is not Canonical-only")
    if out.get("no_auto_trade") is not True:
        raise ValueError("investor dashboard lost no-auto-trade")
    research = normalize_terminal_research(terminal_payload)
    out["terminal_research_snapshot"] = research
    summary = dict(out.get("decision_summary") or {})
    summary.update({
        "research_terminal_requested_count": research["requested_count"],
        "research_buy_count": research["decision_counts"]["BUY"],
        "research_wait_price_count": research["decision_counts"]["WAIT_PRICE"],
        "research_gap_count": research["decision_counts"]["RESEARCH_GAP"],
        "research_reject_count": research["decision_counts"]["REJECT"],
        "urgent_research_count": research["urgent_research_count"],
        "research_capital_probe_count": research["capital_probe_count"],
        "research_capital_action_counts": dict(research["capital_action_counts"]),
    })
    out["decision_summary"] = summary
    health = dict(out.get("data_health") or {})
    health.update({
        "terminal_research_available": True,
        "terminal_research_authority": "RESEARCH_ONLY",
        "terminal_research_formal_mutation_allowed": False,
        "terminal_capital_advisory_available": bool(research["capital_model_version"]),
        "terminal_capital_advisory_authority": "ADVISORY_ONLY",
        "terminal_capital_advisory_automatic_execution_allowed": False,
    })
    out["data_health"] = health
    presentation = dict(out.get("presentation_contract") or {})
    sections = list(presentation.get("section_order") or [])
    if "terminal_research" not in sections:
        pos = sections.index("stock_portfolio") + 1 if "stock_portfolio" in sections else 0
        sections.insert(pos, "terminal_research")
    presentation["section_order"] = sections
    out["presentation_contract"] = presentation
    return out


def _strip_existing_terminal_research(markdown: str) -> str:
    """Remove a previously rendered terminal-research section without touching later sections."""
    marker = "## 深算研究终态（Research-only，不等于正式交易授权）"
    lines = markdown.splitlines()
    out: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == marker:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out).rstrip()


def append_markdown(markdown: str, dashboard: Mapping[str, Any]) -> str:
    research = dashboard.get("terminal_research_snapshot") or {}
    if not research:
        return markdown
    markdown = _strip_existing_terminal_research(markdown)
    counts = research.get("decision_counts") or {}
    lines = [markdown, "", "## 深算研究终态（Research-only，不等于正式交易授权）", "",
             f"- 本轮深算：**{research.get('requested_count', 0)}** 只；研究 BUY **{counts.get('BUY', 0)}** / WAIT_PRICE **{counts.get('WAIT_PRICE', 0)}** / RESEARCH_GAP **{counts.get('RESEARCH_GAP', 0)}** / REJECT **{counts.get('REJECT', 0)}**。",
             f"- urgent research：**{research.get('urgent_research_count', 0)}** 只；这些标的仍是 RESEARCH_GAP，等待补证，不获得 Formal BUY。",
             "- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。"]
    if research.get("capital_model_version"):
        capital_counts = research.get("capital_action_counts") or {}
        lines += [
            f"- 风险预算：BUILD **{capital_counts.get('BUILD', 0)}** / PROBE **{capital_counts.get('PROBE', 0)}** / WATCH **{capital_counts.get('WATCH', 0)}** / BLOCK **{capital_counts.get('BLOCK', 0)}**；仅人工建议，不自动执行。",
            "",
            "### 风险预算 BUILD / PROBE",
            "",
        ]
        probes = research.get("capital_probe_queue") or []
        if not probes:
            lines.append("- 暂无。")
        for row in probes:
            capital = row.get("capital_allocation") or {}
            lines.append(
                f"- {row.get('name') or ''} {row.get('code')}: **{capital.get('action') or '—'}**；"
                f"conviction={capital.get('capital_conviction_score', '—')}；"
                f"建议账户仓位上限={capital.get('suggested_max_portfolio_pct', 0)}%；"
                f"研究结论仍为 {row.get('research_decision') or '—'}。"
            )
    lines += ["", "### 我的持仓深算", "",
             "| 股票 | 研究结论 | 原因 | 剩余证据缺口 | Urgent |", "|---|---|---|---|---|"]
    by_code = {str(row.get("code") or ""): row for row in research.get("terminal_rows") or []}
    urgent_codes = {str(row.get("code") or "") for row in research.get("urgent_research_queue") or []}
    for code in ("600406", "001316", "601318", "603993"):
        row = by_code.get(code)
        if not row:
            lines.append(f"| {code} | — | 本轮 workset 未包含 | — | — |")
            continue
        gaps = ", ".join(row.get("hard_gate_unknowns") or []) or "无"
        lines.append(f"| {row.get('name') or ''} {code} | **{row.get('research_decision')}** | {row.get('research_reason') or ''} | {gaps} | {'是' if code in urgent_codes else '否'} |")
    lines += ["", "### Urgent evidence queue", ""]
    urgent = research.get("urgent_research_queue") or []
    if not urgent:
        lines.append("- 暂无。")
    for row in urgent:
        gaps = ", ".join(row.get("hard_gate_unknowns") or []) or "无"
        reasons = ", ".join(row.get("urgent_research_reasons") or [])
        lines.append(f"- {row.get('name') or ''} {row.get('code')}: {row.get('research_decision') or 'RESEARCH_GAP'}；gaps={gaps}" + (f"；urgent={reasons}" if reasons else ""))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--dashboard-md", type=Path, required=True)
    parser.add_argument("--terminal-research-json", type=Path, required=True)
    args = parser.parse_args(argv)
    dashboard = _read_json(args.dashboard_json)
    terminal = _read_json(args.terminal_research_json)
    overlaid = apply_overlay(dashboard, terminal)
    original_md = args.dashboard_md.read_text(encoding="utf-8") if args.dashboard_md.is_file() else "# 投资决策驾驶舱\n"
    args.dashboard_json.write_text(json.dumps(overlaid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.dashboard_md.write_text(append_markdown(original_md, overlaid), encoding="utf-8")
    print(json.dumps({"research_requested": overlaid["decision_summary"]["research_terminal_requested_count"], "research_counts": overlaid["terminal_research_snapshot"]["decision_counts"], "urgent_research_count": overlaid["terminal_research_snapshot"]["urgent_research_count"], "formal_action_source": overlaid["formal_action_source"], "no_auto_trade": overlaid["no_auto_trade"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())