"""Overlay research-only Deep Terminal decisions onto the investor dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

TERMINAL_CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
TERMINAL_DECISIONS = {"BUY", "WAIT_PRICE", "REJECT"}


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

    urgent = payload.get("urgent_research_queue") or []
    if not isinstance(urgent, list):
        raise ValueError("urgent_research_queue must be a list")
    row_codes = {str(row.get("code") or "") for row in normalized_rows}
    urgent_rows = []
    for raw in urgent:
        if not isinstance(raw, Mapping) or str(raw.get("code") or "") not in row_codes:
            raise ValueError("urgent research row is outside terminal workset")
        if raw.get("research_decision") != "REJECT":
            raise ValueError("urgent research must remain REJECT")
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
        "research_reject_count": research["decision_counts"]["REJECT"],
        "urgent_research_count": research["urgent_research_count"],
    })
    out["decision_summary"] = summary
    health = dict(out.get("data_health") or {})
    health.update({"terminal_research_available": True, "terminal_research_authority": "RESEARCH_ONLY", "terminal_research_formal_mutation_allowed": False})
    out["data_health"] = health
    presentation = dict(out.get("presentation_contract") or {})
    sections = list(presentation.get("section_order") or [])
    if "terminal_research" not in sections:
        pos = sections.index("stock_portfolio") + 1 if "stock_portfolio" in sections else 0
        sections.insert(pos, "terminal_research")
    presentation["section_order"] = sections
    out["presentation_contract"] = presentation
    return out


def append_markdown(markdown: str, dashboard: Mapping[str, Any]) -> str:
    research = dashboard.get("terminal_research_snapshot") or {}
    if not research:
        return markdown
    counts = research.get("decision_counts") or {}
    lines = [markdown.rstrip(), "", "## 深算研究终态（Research-only，不等于正式交易授权）", "",
             f"- 本轮深算：**{research.get('requested_count', 0)}** 只；研究 BUY **{counts.get('BUY', 0)}** / WAIT_PRICE **{counts.get('WAIT_PRICE', 0)}** / REJECT **{counts.get('REJECT', 0)}**。",
             f"- urgent research：**{research.get('urgent_research_count', 0)}** 只；这些标的本轮仍是 REJECT，不获得 Formal BUY。",
             "- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。", "", "### 我的持仓深算", "",
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
        lines.append(f"- {row.get('name') or ''} {row.get('code')}: REJECT；gaps={gaps}" + (f"；urgent={reasons}" if reasons else ""))
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