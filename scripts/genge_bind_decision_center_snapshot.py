#!/usr/bin/env python3
"""Bind Decision Center and ChatGPT handoff to the exact consumed data package.

This is primarily a provenance/safety adapter. It never recomputes Formal actions.
If the locked package is not execution-ready, immediate execution semantics are
failed closed while the historical/research Formal values remain intact.

The adapter also surfaces the persisted UNKNOWN-safe diversified research radar
inside the final investor page. That radar remains RESEARCH_ONLY: it is visibility
for what survived screening, not a source of Formal BUY authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_DECISION_DATA_PROVENANCE_V1"
RESEARCH_RADAR_CONTRACT = "GEN_GE_V31_UNKNOWN_SAFE_RESEARCH_RADAR_V1"
RESEARCH_RADAR_POLICY = "ONE_REPRESENTATIVE_PER_OFFICIAL_INDUSTRY"
RADAR_MD_START = "<!-- GEN_GE_DIVERSIFIED_RESEARCH_RADAR_START -->"
RADAR_MD_END = "<!-- GEN_GE_DIVERSIFIED_RESEARCH_RADAR_END -->"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _validate_research_radar(radar: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = radar.get("summary") if isinstance(radar.get("summary"), Mapping) else {}
    top_rows = [dict(row) for row in (radar.get("top_rows") or []) if isinstance(row, Mapping)]
    if summary.get("contract") != RESEARCH_RADAR_CONTRACT:
        raise ValueError("unexpected research-radar contract")
    if summary.get("authority") != "RESEARCH_ONLY":
        raise ValueError("research radar must remain RESEARCH_ONLY")
    if summary.get("formal_trading_authority") is not False:
        raise ValueError("research radar cannot grant Formal trading authority")
    if summary.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("research radar cannot grant automatic Formal BUY")
    if summary.get("unknown_is_pass") is not False:
        raise ValueError("research radar must preserve UNKNOWN != PASS")
    if summary.get("no_auto_trade") is not True:
        raise ValueError("research radar must preserve no-auto-trade")
    if summary.get("top_selection_policy") != RESEARCH_RADAR_POLICY:
        raise ValueError("research radar is not using the required diversified Top policy")
    if int(summary.get("top_count") or 0) != len(top_rows):
        raise ValueError("research radar top_count does not match top_rows")

    seen_industries: set[str] = set()
    for row in top_rows:
        if row.get("authority") != "RESEARCH_ONLY":
            raise ValueError("research radar row lost RESEARCH_ONLY authority")
        if row.get("formal_trading_authority") is not False:
            raise ValueError("research radar row attempted to gain Formal authority")
        if row.get("automatic_formal_buy_allowed") is not False:
            raise ValueError("research radar row attempted to grant automatic Formal BUY")
        if row.get("unknown_is_pass") is not False:
            raise ValueError("research radar row attempted to treat UNKNOWN as PASS")
        if row.get("no_auto_trade") is not True:
            raise ValueError("research radar row lost no-auto-trade")
        if int(row.get("fail_gate_count") or 0) != 0:
            raise ValueError("research radar Top contains a hard-gate FAIL")
        if row.get("selected_as_industry_representative") is not True:
            raise ValueError("research radar Top row is not an industry representative")
        industry_key = str(row.get("industry_key") or row.get("industry") or "").strip()
        if not industry_key:
            industry_key = f"UNCLASSIFIED:{_stock_code(row.get('code'))}"
        if industry_key in seen_industries:
            raise ValueError("research radar Top contains duplicate industries")
        seen_industries.add(industry_key)

    if int(summary.get("top_distinct_industry_count") or 0) != len(seen_industries):
        raise ValueError("research radar distinct-industry count does not match Top rows")
    return dict(summary), top_rows


def _attach_research_radar(decision: dict[str, Any], radar: Mapping[str, Any]) -> dict[str, Any]:
    summary, top_rows = _validate_research_radar(radar)
    holdings = decision.get("pillar_1_holdings_deep_analysis")
    holding_codes = {
        _stock_code(row.get("code"))
        for row in ((holdings or {}).get("rows") or [])
        if isinstance(row, Mapping) and _stock_code(row.get("code"))
    }

    investor_rows: list[dict[str, Any]] = []
    for raw in top_rows:
        code = _stock_code(raw.get("code"))
        unknown_gates = [part for part in str(raw.get("unknown_gates") or "").split(",") if part]
        verified_gates = [part for part in str(raw.get("verified_pass_gates") or "").split(",") if part]
        investor_rows.append(
            {
                "diversified_rank": int(raw.get("diversified_rank") or 0),
                "global_radar_rank": int(raw.get("radar_rank") or 0),
                "code": code,
                "name": str(raw.get("stock_name") or raw.get("name") or ""),
                "industry": str(raw.get("industry") or ""),
                "radar_tier": str(raw.get("radar_tier") or ""),
                "research_priority": str(raw.get("research_priority") or ""),
                "verified_pass_gate_count": int(raw.get("verified_pass_gate_count") or 0),
                "verified_pass_gates": verified_gates,
                "unknown_gate_count": int(raw.get("unknown_gate_count") or 0),
                "unknown_gates": unknown_gates,
                "quant_score": raw.get("quant_score"),
                "v31_review_rank": raw.get("v31_review_rank"),
                "followup": str(raw.get("followup") or ""),
                "portfolio_relation": "CURRENT_HOLDING" if code in holding_codes else "NEW_RESEARCH_CANDIDATE",
                "selection_policy": RESEARCH_RADAR_POLICY,
                "selection_trace": (
                    f"ALL_A_RESEARCH -> GLOBAL_RANK_{int(raw.get('radar_rank') or 0)} -> "
                    f"INDUSTRY_REPRESENTATIVE[{str(raw.get('industry') or 'UNCLASSIFIED')}] -> "
                    f"DIVERSIFIED_TOP_{int(raw.get('diversified_rank') or 0)}"
                ),
                "research_authority": "RESEARCH_ONLY",
                "formal_buy_authorized": False,
                "automatic_execution_allowed": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
            }
        )

    radar_view = {
        "available": True,
        "contract": RESEARCH_RADAR_CONTRACT,
        "generated_at": summary.get("generated_at") or "",
        "source_run_id": str(summary.get("source_run_id") or ""),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "radar_eligible_count": int(summary.get("radar_eligible_count") or 0),
        "distinct_industry_count": int(summary.get("distinct_industry_count") or 0),
        "same_industry_backup_count": int(summary.get("same_industry_backup_count") or 0),
        "top_count": len(investor_rows),
        "top_distinct_industry_count": int(summary.get("top_distinct_industry_count") or 0),
        "top_selection_policy": RESEARCH_RADAR_POLICY,
        "ranking_policy": str(summary.get("ranking_policy") or ""),
        "full_evidence_count": int(summary.get("full_evidence_count") or 0),
        "unknown_eligible_count": int(summary.get("unknown_eligible_count") or 0),
        "hard_fail_excluded_count": int(summary.get("hard_fail_excluded_count") or 0),
        "rows": investor_rows,
        "new_research_candidate_count": sum(
            1 for row in investor_rows if row["portfolio_relation"] == "NEW_RESEARCH_CANDIDATE"
        ),
        "current_holding_count": sum(
            1 for row in investor_rows if row["portfolio_relation"] == "CURRENT_HOLDING"
        ),
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "interpretation": (
            "This list explains which industry-diversified names survived the current research radar. "
            "It is not a BUY list and cannot create Formal authority."
        ),
    }

    opportunities = decision.get("pillar_3_deep_opportunities")
    if not isinstance(opportunities, dict):
        opportunities = {}
        decision["pillar_3_deep_opportunities"] = opportunities
    opportunities["diversified_research_radar"] = radar_view

    executive = decision.get("executive_summary")
    if isinstance(executive, dict):
        executive["diversified_research_top_count"] = radar_view["top_count"]
        executive["diversified_research_new_candidate_count"] = radar_view["new_research_candidate_count"]
        executive["diversified_research_industry_count"] = radar_view["top_distinct_industry_count"]

    readiness = decision.get("decision_readiness")
    if isinstance(readiness, dict):
        readiness["diversified_research_radar_available"] = True
        readiness["diversified_research_radar_authority"] = "RESEARCH_ONLY"
        readiness["diversified_research_top_unique_industries"] = (
            radar_view["top_count"] == radar_view["top_distinct_industry_count"]
        )
    return radar_view


def _render_research_radar_markdown(radar_view: Mapping[str, Any]) -> str:
    lines = [
        RADAR_MD_START,
        "### 行业去重研究雷达（研究候选，不是买单）",
        "",
        (
            f"- 全量候选 **{radar_view.get('candidate_count', 0)}** → 雷达合格 **{radar_view.get('radar_eligible_count', 0)}**；"
            f"覆盖 **{radar_view.get('distinct_industry_count', 0)}** 个行业；同业备选保留 **{radar_view.get('same_industry_backup_count', 0)}** 只。"
        ),
        (
            f"- 投资者 Top **{radar_view.get('top_count', 0)}** 只 / **{radar_view.get('top_distinct_industry_count', 0)}** 个不同行业；"
            f"其中新研究候选 **{radar_view.get('new_research_candidate_count', 0)}** 只、当前持仓 **{radar_view.get('current_holding_count', 0)}** 只。"
        ),
        f"- 选择规则：`{radar_view.get('top_selection_policy')}`；source run：`{radar_view.get('source_run_id') or '—'}`。",
        "- **这只是 RESEARCH_ONLY 研究入口，不是 BUY/WAIT_PRICE，更不会因为进 Top 就获得 Formal BUY。UNKNOWN 仍然不是 PASS。**",
        "",
        "| Top | 全局雷达排名 | 股票 | 行业 | 与账户关系 | 研究层级 | PASS | UNKNOWN | Quant | 下一步 |",
        "|---:|---:|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in radar_view.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        relation = "当前持仓" if row.get("portfolio_relation") == "CURRENT_HOLDING" else "新研究候选"
        unknowns = "、".join(row.get("unknown_gates") or []) or "—"
        followup = str(row.get("followup") or "—")
        if unknowns != "—":
            followup = f"{followup}；待补：{unknowns}"
        lines.append(
            f"| {row.get('diversified_rank', 0)} | {row.get('global_radar_rank', 0)} | "
            f"{row.get('name','')} {row.get('code','')} | {row.get('industry') or '—'} | {relation} | "
            f"{row.get('radar_tier') or '—'} | {row.get('verified_pass_gate_count', 0)} | "
            f"{row.get('unknown_gate_count', 0)} | {row.get('quant_score') or '—'} | {followup} |"
        )
    lines += [
        "",
        "- 每只股票的 `global_radar_rank + industry + diversified_rank + PASS/UNKNOWN` 都保留在机器数据里，用来回答“它为什么进榜、为什么不是同业另一只”。",
        RADAR_MD_END,
    ]
    return "\n".join(lines)


def _inject_research_radar_markdown(markdown: str, radar_view: Mapping[str, Any]) -> str:
    block = _render_research_radar_markdown(radar_view)
    if RADAR_MD_START in markdown and RADAR_MD_END in markdown:
        start = markdown.index(RADAR_MD_START)
        end = markdown.index(RADAR_MD_END, start) + len(RADAR_MD_END)
        return markdown[:start].rstrip() + "\n\n" + block + "\n\n" + markdown[end:].lstrip()
    anchor = "## 4. 今日账户资金怎么处理"
    if anchor in markdown:
        return markdown.replace(anchor, block + "\n\n" + anchor, 1)
    return markdown.rstrip() + "\n\n" + block + "\n"


def _fail_close_plan(payload: dict[str, Any], reason: str) -> None:
    plan = payload.get("today_account_plan") or payload.get("capital_deployment") or {}
    if not isinstance(plan, dict):
        return
    operations = plan.get("operations") or []
    for row in operations:
        if not isinstance(row, dict):
            continue
        row["immediate_execution_eligible"] = False
        row["execution_block_reason"] = reason
        if "executable_shares" in row:
            row["executable_shares"] = 0
        if "executable_quantity" in row:
            row["executable_quantity"] = 0
    plan["planned_immediate_cash_cny"] = 0.0
    available = plan.get("available_cash_cny")
    if available is not None:
        plan["cash_after_immediate_plan_cny"] = available
    plan["no_auto_trade"] = True
    if "today_account_plan" in payload:
        payload["today_account_plan"] = plan
    if "capital_deployment" in payload:
        payload["capital_deployment"] = plan
    if isinstance(payload.get("decision_summary"), dict):
        payload["decision_summary"]["planned_immediate_cash_cny"] = 0.0
    if isinstance(payload.get("final_operation_table"), list):
        for row in payload["final_operation_table"]:
            if isinstance(row, dict):
                row["immediate_execution_eligible"] = False
                row["execution_block_reason"] = reason
                if "executable_shares" in row:
                    row["executable_shares"] = 0
                if "executable_quantity" in row:
                    row["executable_quantity"] = 0


def bind(
    *,
    decision_path: Path,
    package_path: Path,
    receipt_path: Path,
    handoff_path: Path | None = None,
    research_radar_path: Path | None = None,
    decision_markdown_path: Path | None = None,
) -> dict[str, Any]:
    decision = _load(decision_path)
    package = _load(package_path)
    receipt = _load(receipt_path)

    package_id = str(package.get("snapshot_id") or "")
    receipt_id = str(receipt.get("input_snapshot_id") or "")
    if not package_id or package_id != receipt_id:
        raise ValueError(f"research input/package lineage mismatch: package={package_id!r} receipt={receipt_id!r}")
    if package.get("contract") != "GEN_GE_REALTIME_DATA_PACKAGE_V1":
        raise ValueError("unexpected data-package contract")
    if receipt.get("contract") != "GEN_GE_RESEARCH_INPUT_LOCK_V1":
        raise ValueError("unexpected research-input contract")

    radar_view: dict[str, Any] | None = None
    markdown_text: str | None = None
    if research_radar_path is not None and research_radar_path.is_file():
        radar_view = _attach_research_radar(decision, _load(research_radar_path))
        if decision_markdown_path is not None and decision_markdown_path.is_file():
            markdown_text = _inject_research_radar_markdown(
                decision_markdown_path.read_text(encoding="utf-8"),
                radar_view,
            )

    execution_allowed = receipt.get("execution_allowed") is True and package.get("package_status") == "READY"
    reason = None if execution_allowed else str(receipt.get("fail_closed_reason") or f"DATA_PACKAGE_{package.get('package_status')}_NOT_EXECUTABLE")
    provenance = {
        "contract": CONTRACT,
        "data_package_contract": package.get("contract"),
        "snapshot_id": package_id,
        "package_generated_at": package.get("generated_at"),
        "package_status": package.get("package_status"),
        "latest_trade_date": package.get("latest_trade_date"),
        "research_input_contract": receipt.get("contract"),
        "research_mode": receipt.get("research_mode"),
        "research_input_locked_at": receipt.get("locked_at"),
        "network_policy": receipt.get("network_policy"),
        "external_fresh_evidence_policy": receipt.get("external_fresh_evidence_policy"),
        "pending_external_fresh_evidence_count": package.get("pending_external_fresh_evidence_count", 0),
        "execution_allowed": execution_allowed,
    }
    guard = {
        "execution_allowed": execution_allowed,
        "formal_actions_preserved": True,
        "formal_action_recomputed": False,
        "stale_or_partial_data_cannot_authorize_execution": True,
        "block_reason": reason,
        "no_auto_trade": True,
    }

    decision["data_package_provenance"] = provenance
    decision["data_freshness_execution_guard"] = guard
    decision["no_auto_trade"] = True
    if not execution_allowed:
        _fail_close_plan(decision, reason or "DATA_PACKAGE_NOT_EXECUTABLE")
    _write(decision_path, decision)
    if markdown_text is not None and decision_markdown_path is not None:
        decision_markdown_path.write_text(markdown_text, encoding="utf-8")

    if handoff_path and handoff_path.is_file():
        handoff = _load(handoff_path)
        handoff["data_package_provenance"] = provenance
        handoff["data_freshness_execution_guard"] = guard
        handoff["no_auto_trade"] = True
        if radar_view is not None:
            handoff["diversified_research_radar"] = radar_view
        if not execution_allowed:
            _fail_close_plan(handoff, reason or "DATA_PACKAGE_NOT_EXECUTABLE")
        _write(handoff_path, handoff)
    return decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--package", type=Path, default=Path("data/data_package/latest.json"))
    parser.add_argument("--receipt", type=Path, default=Path("data/research_input/latest.json"))
    parser.add_argument("--handoff", type=Path, default=Path("data/investor_chatgpt_handoff/latest.json"))
    parser.add_argument("--research-radar", type=Path, default=Path("data/research_radar/latest.json"))
    parser.add_argument("--decision-markdown", type=Path, default=Path("LATEST_DECISION_CENTER.md"))
    args = parser.parse_args(argv)
    try:
        payload = bind(
            decision_path=args.decision,
            package_path=args.package,
            receipt_path=args.receipt,
            handoff_path=args.handoff,
            research_radar_path=args.research_radar,
            decision_markdown_path=args.decision_markdown,
        )
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    p = payload.get("data_package_provenance") or {}
    radar = ((payload.get("pillar_3_deep_opportunities") or {}).get("diversified_research_radar") or {})
    print(
        json.dumps(
            {
                "contract": CONTRACT,
                "snapshot_id": p.get("snapshot_id"),
                "package_status": p.get("package_status"),
                "execution_allowed": p.get("execution_allowed"),
                "diversified_research_radar_attached": radar.get("available") is True,
                "diversified_research_top_count": radar.get("top_count", 0),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
