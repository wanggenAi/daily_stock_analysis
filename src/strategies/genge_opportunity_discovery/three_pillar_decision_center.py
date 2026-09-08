"""Three-pillar investor decision center.

This module composes already-authorized/persisted research truth into the three
questions an investor actually needs answered:

1. What should I do with my current holdings, and how complete is the deep review?
2. What structural world/social trends and current market-behaviour proxies point
   to capital directions worth researching?
3. Which new opportunities survived the terminal research process, with explicit
   BUY/WAIT_PRICE authority kept separate from research-only context?

It does not create Formal BUY authority, does not convert UNKNOWN to PASS, and
never places orders automatically.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_THREE_PILLAR_DECISION_CENTER_V1"
NO_AUTO_TRADE = True


def _json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _code(value: Any) -> str:
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


def _validate_inputs(dashboard: Mapping[str, Any], era_radar: Mapping[str, Any]) -> None:
    if not dashboard:
        raise ValueError("investor decision dashboard is required")
    if dashboard.get("no_auto_trade") is not True:
        raise ValueError("dashboard lost no-auto-trade contract")
    if dashboard.get("formal_action_source") != "FINALIZED_CANONICAL_ONLY":
        raise ValueError("dashboard Formal Action authority is not Canonical-only")
    if era_radar:
        if era_radar.get("no_auto_trade") is not True:
            raise ValueError("Era Radar lost no-auto-trade contract")
        if era_radar.get("formal_trading_authority") is not False:
            raise ValueError("Era Radar must remain research-only")


def _gate_summary(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {
            "status": "DEEP_REVIEW_MISSING",
            "complete": False,
            "pass_count": 0,
            "fail_count": 0,
            "unknown_count": 0,
            "gates": [],
        }
    gates = profile.get("gates")
    if not isinstance(gates, Mapping) or not gates:
        return {
            "status": "DEEP_REVIEW_MISSING",
            "complete": False,
            "pass_count": 0,
            "fail_count": 0,
            "unknown_count": 0,
            "gates": [],
        }
    rows: list[dict[str, Any]] = []
    pass_count = fail_count = unknown_count = 0
    for gate, raw in gates.items():
        item = raw if isinstance(raw, Mapping) else {}
        status = str(item.get("status") or "UNKNOWN").upper()
        if status == "PASS":
            pass_count += 1
        elif status == "FAIL":
            fail_count += 1
        else:
            status = "UNKNOWN"
            unknown_count += 1
        evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        rows.append(
            {
                "gate": str(gate),
                "status": status,
                "confidence": str(item.get("confidence") or ""),
                "rationale": str(item.get("rationale") or ""),
                "evidence_count": len(evidence),
            }
        )
    complete = unknown_count == 0
    if fail_count:
        status = "DEEP_REVIEW_COMPLETE_WITH_FAILURE" if complete else "DEEP_REVIEW_PARTIAL_WITH_FAILURE"
    elif complete:
        status = "DEEP_REVIEW_COMPLETE"
    else:
        status = "DEEP_REVIEW_PARTIAL"
    return {
        "status": status,
        "complete": complete,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "unknown_count": unknown_count,
        "gates": rows,
    }


def _holding_pillar(dashboard: Mapping[str, Any], profiles: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    complete_count = 0
    explicit_count = 0
    for raw in dashboard.get("stock_portfolio", {}).get("rows") or []:
        code = _code(raw.get("code"))
        profile = profiles.get(code) if isinstance(profiles, Mapping) else None
        deep = _gate_summary(profile if isinstance(profile, Mapping) else None)
        if deep["status"] != "DEEP_REVIEW_MISSING":
            explicit_count += 1
        if deep["complete"]:
            complete_count += 1
        rows.append(
            {
                "code": code,
                "name": raw.get("name") or "",
                "quantity": raw.get("quantity"),
                "average_cost": _num(raw.get("average_cost")),
                "current_price": _num(raw.get("current_price")),
                "pnl_pct": _num(raw.get("pnl_pct")),
                "formal_action": raw.get("formal_action") or "",
                "investor_action": raw.get("investor_action") or "",
                "neutral_value": _num(raw.get("neutral_value")),
                "valuation_confidence": raw.get("valuation_confidence") or "",
                "reason_codes": raw.get("reason_codes") or "",
                "holding_add_authorized": raw.get("holding_add_authorized") is True,
                "deep_review": deep,
            }
        )
    return {
        "question": "我手里的股票，现在该怎么办？",
        "status": dashboard.get("stock_portfolio", {}).get("status") or "UNKNOWN",
        "holding_count": len(rows),
        "explicit_deep_review_count": explicit_count,
        "complete_deep_review_count": complete_count,
        "deep_review_gap_count": max(0, len(rows) - complete_count),
        "rows": rows,
    }


def _trend_pillar(
    dashboard: Mapping[str, Any],
    era_radar: Mapping[str, Any],
    industry_links: Mapping[str, Any],
    era_handoff: Mapping[str, Any],
) -> dict[str, Any]:
    links = industry_links.get("links") if isinstance(industry_links.get("links"), Mapping) else {}
    trends: list[dict[str, Any]] = []
    for raw in era_radar.get("trends") or []:
        if not isinstance(raw, Mapping):
            continue
        trend_id = str(raw.get("trend_id") or "")
        if not trend_id:
            continue
        trends.append(
            {
                "trend_id": trend_id,
                "lifecycle": raw.get("lifecycle") or "UNKNOWN",
                "confidence_score": _num(raw.get("confidence_score")),
                "structural_score": _num(raw.get("structural_score")),
                "industrial_score": _num(raw.get("industrial_score")),
                "cyclical_score": _num(raw.get("cyclical_score")),
                "evidence_count": int(_num(raw.get("evidence_count")) or 0),
                "independent_families": int(_num(raw.get("independent_families")) or 0),
                "a_share_research_industries": list(links.get(trend_id) or []),
                "components": dict(raw.get("components") or {}),
            }
        )
    trends.sort(
        key=lambda x: (
            -(x.get("confidence_score") or 0.0),
            -(x.get("structural_score") or 0.0),
            -(x.get("industrial_score") or 0.0),
            x["trend_id"],
        )
    )
    tactical = list(dashboard.get("capital_direction", {}).get("strongest_industries") or [])
    queue = list(era_handoff.get("queue") or []) if isinstance(era_handoff, Mapping) else []
    return {
        "question": "世界和社会正在往哪里走，钱可能流向哪里，A股该研究什么？",
        "research_as_of": era_radar.get("research_as_of") or "",
        "direct_fund_flow_claimed": False,
        "structural_world_social_trends": trends[:10],
        "tactical_market_behavior_proxy": tactical,
        "validated_a_share_research_handoffs": queue,
        "validated_handoff_count": len(queue),
        "intersection_status": "VALIDATED_HANDOFFS_AVAILABLE" if queue else "NO_VALIDATED_A_SHARE_HANDOFF",
        "interpretation_rule": (
            "结构趋势回答中长期需求/利润池可能去哪里；市场行为代理回答近期风险偏好在哪里；"
            "只有经过映射和后续全权限深算的交集，才能进入个股决策。"
        ),
    }


def _opportunity_item(raw: Mapping[str, Any], profiles: Mapping[str, Any]) -> dict[str, Any]:
    code = _code(raw.get("code"))
    profile = profiles.get(code) if isinstance(profiles, Mapping) else None
    return {
        "code": code,
        "name": raw.get("name") or raw.get("stock_name") or "",
        "industry": raw.get("industry") or "",
        "terminal_decision": raw.get("terminal_decision") or "",
        "current_price": _num(raw.get("current_price")),
        "wait_price_max": _num(raw.get("wait_price_max")),
        "neutral_value": _num(raw.get("neutral_value")),
        "valuation_confidence": raw.get("valuation_confidence") or "",
        "reason_class": raw.get("reason_class") or "",
        "formal_buy_authorized": raw.get("formal_buy_authorized") is True,
        "deep_review": _gate_summary(profile if isinstance(profile, Mapping) else None),
    }


def _opportunity_pillar(dashboard: Mapping[str, Any], profiles: Mapping[str, Any], era_handoff: Mapping[str, Any]) -> dict[str, Any]:
    terminal = dashboard.get("terminal_opportunities", {})
    buy = [_opportunity_item(x, profiles) for x in terminal.get("buy_now") or []]
    wait = [_opportunity_item(x, profiles) for x in terminal.get("wait_price") or []]
    handoffs = list(era_handoff.get("queue") or []) if isinstance(era_handoff, Mapping) else []
    return {
        "question": "除了持仓，还有哪些润贝型或其他机会已经深算到能指导行动？",
        "buy_now": buy,
        "wait_price": wait,
        "terminal_reject_count": int(_num(terminal.get("reject_count")) or 0),
        "invalid_unauthorized_buy_count": int(_num(terminal.get("invalid_unauthorized_buy_count")) or 0),
        "macro_research_handoffs": handoffs,
        "actionable_count": len(buy) + len(wait),
        "display_rule": "只展示通过终端研究形成 BUY/WAIT_PRICE 的个股；REJECT 只汇总数量和审计，不淹没最终决策页面。",
        "authority_rule": "BUY 必须是既有 Formal/Production BUY 的镜像；研究趋势和深算上下文不能自行创造 BUY。",
    }


def build_decision_center(
    *,
    dashboard: Mapping[str, Any],
    era_radar: Mapping[str, Any],
    deep_review_config: Mapping[str, Any] | None = None,
    industry_links: Mapping[str, Any] | None = None,
    era_handoff: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    _validate_inputs(dashboard, era_radar)
    cfg = deep_review_config or {}
    profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), Mapping) else {}
    links = industry_links or {}
    handoff = era_handoff or {}
    holdings = _holding_pillar(dashboard, profiles)
    capital_map = _trend_pillar(dashboard, era_radar, links, handoff)
    opportunities = _opportunity_pillar(dashboard, profiles, handoff)
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "latest_trade_date": dashboard.get("latest_trade_date") or "",
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id") or "",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "decision_questions": [holdings["question"], capital_map["question"], opportunities["question"]],
        "executive_summary": {
            "holding_count": holdings["holding_count"],
            "holdings_complete_deep_review": holdings["complete_deep_review_count"],
            "holdings_deep_review_gaps": holdings["deep_review_gap_count"],
            "validated_macro_handoffs": capital_map["validated_handoff_count"],
            "new_buy_now_count": len(opportunities["buy_now"]),
            "new_wait_price_count": len(opportunities["wait_price"]),
            "terminal_reject_count": opportunities["terminal_reject_count"],
        },
        "pillar_1_holdings_deep_analysis": holdings,
        "pillar_2_world_social_market_capital_map": capital_map,
        "pillar_3_deep_opportunities": opportunities,
        "decision_readiness": {
            "portfolio_actions_available": holdings["holding_count"] > 0,
            "all_holdings_explicit_deep_review_complete": holdings["deep_review_gap_count"] == 0,
            "structural_trend_evidence_available": bool(capital_map["structural_world_social_trends"]),
            "validated_macro_to_a_share_handoff_available": capital_map["validated_handoff_count"] > 0,
            "terminal_opportunity_result_available": dashboard.get("terminal_opportunities", {}).get("available") is True,
            "rule": "缺少深算或映射证据时明确显示 gap；UNKNOWN 不得冒充 PASS，也不得为了填满页面制造机会。",
        },
    }


def _fmt(value: Any) -> str:
    n = _num(value)
    return "—" if n is None else f"{n:.2f}"


def render_markdown(payload: Mapping[str, Any]) -> str:
    h = payload["pillar_1_holdings_deep_analysis"]
    m = payload["pillar_2_world_social_market_capital_map"]
    o = payload["pillar_3_deep_opportunities"]
    lines = [
        "# 三支柱投资决策中心",
        "",
        "> 最终页面只回答三件事：我的持仓怎么办；钱可能往哪里去；还有什么股票值得行动。",
        "",
        "## 1. 我的持仓：深算后到底怎么办",
        "",
        f"- 持仓：**{h['holding_count']}**；已有显式深算：**{h['explicit_deep_review_count']}**；深算完整：**{h['complete_deep_review_count']}**；仍有 gap：**{h['deep_review_gap_count']}**。",
        "",
        "| 股票 | 盈亏% | 正式动作 | 现在怎么办 | 估值信心 | 深算状态 |",
        "|---|---:|---|---|---|---|",
    ]
    for x in h["rows"]:
        lines.append(
            f"| {x['name']} {x['code']} | {_fmt(x.get('pnl_pct'))} | {x.get('formal_action') or '—'} | "
            f"**{x.get('investor_action') or '—'}** | {x.get('valuation_confidence') or '—'} | {x['deep_review']['status']} |"
        )
    lines += ["", "## 2. 世界/社会/市场：钱可能在哪里", ""]
    lines.append("### 中长期结构趋势")
    lines.append("")
    lines.append("| 趋势 | 信心 | 结构 | 产业 | A股研究映射 |")
    lines.append("|---|---:|---:|---:|---|")
    for x in m["structural_world_social_trends"][:8]:
        mapped = "、".join(x.get("a_share_research_industries") or []) or "尚未映射"
        lines.append(
            f"| {x['trend_id']} | {_fmt(x.get('confidence_score'))} | {_fmt(x.get('structural_score'))} | "
            f"{_fmt(x.get('industrial_score'))} | {mapped} |"
        )
    lines += ["", "### 近期市场行为代理", ""]
    tactical = m["tactical_market_behavior_proxy"]
    lines.append("、".join(f"{x.get('industry')}({_fmt(x.get('score'))})" for x in tactical[:8]) if tactical else "暂无可用代理。")
    lines += ["", f"- 已验证的趋势→A股研究交接：**{m['validated_handoff_count']}**。",
              "- 这里不冒充‘主力净流入’；结构趋势、市场行为和个股深算必须分层验证。",
              "", "## 3. 新机会：润贝型以及其他机会深算结果", ""]
    if o["buy_now"]:
        lines.append("### BUY NOW")
        for x in o["buy_now"]:
            lines.append(f"- **{x['name']} {x['code']}**：现价 {_fmt(x.get('current_price'))}；估值信心 {x.get('valuation_confidence') or '—'}；深算 {x['deep_review']['status']}。")
    else:
        lines.append("- **本轮没有已授权新股 BUY。**")
    if o["wait_price"]:
        lines.append("")
        lines.append("### WAIT_PRICE")
        for x in o["wait_price"]:
            lines.append(f"- **{x['name']} {x['code']}**：等待 ≤{_fmt(x.get('wait_price_max'))}；深算 {x['deep_review']['status']}。")
    else:
        lines.append("- **本轮没有合格 WAIT_PRICE。**")
    lines += ["", f"- Terminal REJECT：**{o['terminal_reject_count']}**（只做汇总，不淹没决策页面）。",
              "", "## 决策完整性", ""]
    readiness = payload["decision_readiness"]
    lines.append(f"- 全部持仓显式深算完整：**{readiness['all_holdings_explicit_deep_review_complete']}**")
    lines.append(f"- 世界/社会结构趋势证据可用：**{readiness['structural_trend_evidence_available']}**")
    lines.append(f"- 已验证趋势→A股交接可用：**{readiness['validated_macro_to_a_share_handoff_available']}**")
    lines.append(f"- Terminal 机会结果可用：**{readiness['terminal_opportunity_result_available']}**")
    lines += ["", "> UNKNOWN != PASS；研究趋势不自动变成 BUY；no_auto_trade=true。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=Path("data/investor_decision_dashboard/latest.json"))
    parser.add_argument("--era-radar", type=Path, default=Path("data/era_radar/latest.json"))
    parser.add_argument("--era-handoff", type=Path, default=Path("data/era_radar/research_handoff/latest.json"))
    parser.add_argument("--deep-reviews", type=Path, default=Path("config/v31_explicit_deep_reviews.json"))
    parser.add_argument("--industry-links", type=Path, default=Path("config/era_radar_industry_links.json"))
    parser.add_argument("--output-json", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--output-md", type=Path, default=Path("LATEST_DECISION_CENTER.md"))
    args = parser.parse_args()
    payload = build_decision_center(
        dashboard=_json(args.dashboard),
        era_radar=_json(args.era_radar),
        deep_review_config=_json(args.deep_reviews),
        industry_links=_json(args.industry_links),
        era_handoff=_json(args.era_handoff),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["executive_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
