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
    market_raw = dashboard.get("market") if isinstance(dashboard.get("market"), Mapping) else {}
    market_snapshot = {
        "as_of_date": market_raw.get("as_of_date") or dashboard.get("latest_trade_date") or "",
        "status": market_raw.get("status") or "UNAVAILABLE",
        "data_quality": market_raw.get("data_quality") or "UNAVAILABLE",
        "allow_new_buy": market_raw.get("allow_new_buy"),
        "score": _num(market_raw.get("score")),
        "position_multiplier": _num(market_raw.get("position_multiplier")),
        "advance_ratio": _num(market_raw.get("advance_ratio")),
        "median_return_1d_pct": _num(market_raw.get("median_return_1d_pct")),
        "above_ma20_ratio": _num(market_raw.get("above_ma20_ratio")),
        "above_ma60_ratio": _num(market_raw.get("above_ma60_ratio")),
        "distribution_ratio": _num(market_raw.get("distribution_ratio")),
        "limit_up_count": int(_num(market_raw.get("limit_up_count")) or 0),
        "limit_down_count": int(_num(market_raw.get("limit_down_count")) or 0),
        "risk_reasons": list(market_raw.get("risk_reasons") or []),
    }
    return {
        "question": "世界和社会正在往哪里走，钱可能流向哪里，A股该研究什么？",
        "research_as_of": era_radar.get("research_as_of") or "",
        "direct_fund_flow_claimed": False,
        "a_share_market_snapshot": market_snapshot,
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
        "display_rule": "这里只展示 Formal/Production Candidate Terminal 的 BUY/WAIT_PRICE 镜像；其 REJECT 只汇总审计。Deep Research Terminal 的 RESEARCH_GAP/REJECT 属于独立研究层，不与本计数混用。",
        "authority_rule": "BUY 必须是既有 Formal/Production BUY 的镜像；研究趋势和深算上下文不能自行创造 BUY。",
    }



def _account_plan(dashboard: Mapping[str, Any]) -> dict[str, Any]:
    plan = dashboard.get("capital_deployment") if isinstance(dashboard.get("capital_deployment"), Mapping) else {}
    live = dashboard.get("live_execution_overlay") if isinstance(dashboard.get("live_execution_overlay"), Mapping) else {}
    available = _num(plan.get("available_cash_cny")) or 0.0
    budget = _num(plan.get("deployment_budget_cny")) or 0.0
    planned = _num(plan.get("planned_immediate_cash_cny")) or 0.0
    cash_after = _num(plan.get("cash_after_immediate_plan_cny"))
    if cash_after is None:
        cash_after = max(0.0, available - planned)
    expected_quotes = int(_num(live.get("expected_code_count")) or 0)
    applied_quotes = int(_num(live.get("applied_code_count")) or 0)
    session = str(live.get("market_session_state") or "UNKNOWN")
    market_data = str(live.get("market_data_status") or "UNAVAILABLE")
    quote_coverage_complete = expected_quotes == 0 or applied_quotes == expected_quotes
    immediate_execution_ready = bool(
        planned > 0
        and session.startswith("ACTIVE_")
        and market_data == "OK"
        and quote_coverage_complete
    )
    if planned > 0:
        plain = (
            f"已有授权计划，预计立即使用约¥{planned:.0f}；"
            f"执行后保留现金约¥{cash_after:.0f}。只有盘中价格覆盖和既有授权同时有效时才执行。"
        )
    else:
        plain = (
            f"本轮没有已授权的新资金投入，约¥{available:.0f}现金继续保留；"
            "已有持仓只按既有 Formal 动作管理，不为了凑交易而买入。"
        )
    return {
        "question": "今天账户里的钱具体怎么处理？",
        "available_cash_cny": available,
        "deployment_budget_cny": budget,
        "planned_immediate_cash_cny": planned,
        "cash_after_immediate_plan_cny": cash_after,
        "operations": list(dashboard.get("final_operation_table") or []),
        "market_session_state": session,
        "market_data_status": market_data,
        "live_quote_applied_count": applied_quotes,
        "live_quote_expected_count": expected_quotes,
        "live_quote_coverage_complete": quote_coverage_complete,
        "immediate_execution_ready": immediate_execution_ready,
        "cash_action": "AUTHORIZED_DEPLOYMENT" if planned > 0 else "KEEP_CASH",
        "plain_language": plain,
        "no_auto_trade": True,
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
    account_plan = _account_plan(dashboard)
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "latest_trade_date": dashboard.get("latest_trade_date") or "",
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id") or "",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "decision_questions": [
            holdings["question"],
            capital_map["question"],
            opportunities["question"],
            account_plan["question"],
        ],
        "executive_summary": {
            "holding_count": holdings["holding_count"],
            "holdings_complete_deep_review": holdings["complete_deep_review_count"],
            "holdings_deep_review_gaps": holdings["deep_review_gap_count"],
            "validated_macro_handoffs": capital_map["validated_handoff_count"],
            "new_buy_now_count": len(opportunities["buy_now"]),
            "new_wait_price_count": len(opportunities["wait_price"]),
            "terminal_reject_count": opportunities["terminal_reject_count"],
            "available_cash_cny": account_plan["available_cash_cny"],
            "planned_immediate_cash_cny": account_plan["planned_immediate_cash_cny"],
            "cash_after_immediate_plan_cny": account_plan["cash_after_immediate_plan_cny"],
        },
        "pillar_1_holdings_deep_analysis": holdings,
        "pillar_2_world_social_market_capital_map": capital_map,
        "pillar_3_deep_opportunities": opportunities,
        "today_account_plan": account_plan,
        "decision_readiness": {
            "portfolio_actions_available": holdings["holding_count"] > 0,
            "all_holdings_explicit_deep_review_complete": holdings["deep_review_gap_count"] == 0,
            "structural_trend_evidence_available": bool(capital_map["structural_world_social_trends"]),
            "validated_macro_to_a_share_handoff_available": capital_map["validated_handoff_count"] > 0,
            "terminal_opportunity_result_available": dashboard.get("terminal_opportunities", {}).get("available") is True,
            "live_execution_quote_coverage_complete": account_plan["live_quote_coverage_complete"],
            "rule": "缺少深算或映射证据时明确显示 gap；UNKNOWN 不得冒充 PASS，也不得为了填满页面制造机会。",
        },
    }


def _fmt(value: Any) -> str:
    n = _num(value)
    return "—" if n is None else f"{n:.2f}"


def _pct(value: Any) -> str:
    n = _num(value)
    return "—" if n is None else f"{n * 100:.2f}%"


def _market_read(snapshot: Mapping[str, Any]) -> str:
    advance = _num(snapshot.get("advance_ratio"))
    ma20 = _num(snapshot.get("above_ma20_ratio"))
    ma60 = _num(snapshot.get("above_ma60_ratio"))
    distribution = _num(snapshot.get("distribution_ratio"))
    observations: list[str] = []
    if advance is not None:
        if advance >= 0.65:
            observations.append("当日上涨面较广")
        elif advance <= 0.40:
            observations.append("当日上涨面偏弱")
        else:
            observations.append("当日涨跌广度中性")
    if ma20 is not None and ma60 is not None:
        if ma20 >= 0.60 and ma60 >= 0.60:
            observations.append("短中期趋势广度同步偏强")
        elif ma20 < 0.50 <= ma60:
            observations.append("短周期尚未全面修复，但中期广度仍有支撑")
        elif ma20 < 0.40 and ma60 < 0.40:
            observations.append("短中期趋势广度都偏弱")
        else:
            observations.append("短中期趋势仍有分化")
    if distribution is not None and distribution <= 0.05:
        observations.append("极端分化/派发代理暂不高")
    return "；".join(observations) or "市场脉搏数据不足，保持中性解读"


def render_markdown(payload: Mapping[str, Any]) -> str:
    h = payload["pillar_1_holdings_deep_analysis"]
    m = payload["pillar_2_world_social_market_capital_map"]
    o = payload["pillar_3_deep_opportunities"]
    lines = [
        "# 三支柱投资决策中心",
        "",
        "> 最终页面回答四件事：我的持仓怎么办；社会/市场/资金往哪里去；哪些股票值得行动；今天账户里的钱具体怎么处理。",
        "",
        "## 1. 我的持仓：深算后到底怎么办",
        "",
        f"- 持仓：**{h['holding_count']}**；已有显式深算：**{h['explicit_deep_review_count']}**；深算完整：**{h['complete_deep_review_count']}**；仍有 gap：**{h['deep_review_gap_count']}**。",
        "",
        "| 股票 | 现价 | 价值中枢 | 盈亏% | 正式动作 | 现在怎么办 | 估值信心 | 持续研究 | 深算状态 |",
        "|---|---:|---:|---:|---|---|---|---|---|",
    ]
    for x in h["rows"]:
        lifecycle = x.get("candidate_lifecycle") if isinstance(x.get("candidate_lifecycle"), Mapping) else {}
        lifecycle_text = (
            f"{lifecycle.get('lifecycle_state','—')}/seen={lifecycle.get('seen_count',0)}"
            if lifecycle
            else "—"
        )
        lines.append(
            f"| {x['name']} {x['code']} | {_fmt(x.get('current_price'))} | {_fmt(x.get('neutral_value'))} | "
            f"{_fmt(x.get('pnl_pct'))} | {x.get('formal_action') or '—'} | "
            f"**{x.get('investor_action') or '—'}** | {x.get('valuation_confidence') or '—'} | "
            f"{lifecycle_text} | {x['deep_review']['status']} |"
        )
    lines += ["", "### 每只持仓的决策链", ""]
    for x in h["rows"]:
        deep = x.get("deep_review") or {}
        lifecycle = x.get("candidate_lifecycle") if isinstance(x.get("candidate_lifecycle"), Mapping) else {}
        price = _num(x.get("current_price"))
        neutral = _num(x.get("neutral_value"))
        price_to_value = (price / neutral) if price is not None and neutral not in (None, 0) else None
        lifecycle_text = (
            f"{lifecycle.get('lifecycle_state','—')} / seen={lifecycle.get('seen_count',0)}"
            if lifecycle
            else "未接入当前生命周期快照"
        )
        reason = str(x.get("reason_codes") or "无显式原因码")
        lines.append(
            f"- **{x.get('name','')} {x.get('code','')}**：现价 {_fmt(price)} / 价值中枢 {_fmt(neutral)}"
            f"（价/值 {_fmt(price_to_value)}）；估值信心 **{x.get('valuation_confidence') or '—'}**；"
            f"Formal **{x.get('formal_action') or '—'}**；Deep **PASS {deep.get('pass_count',0)} / FAIL {deep.get('fail_count',0)} / UNKNOWN {deep.get('unknown_count',0)}**；"
            f"Lifecycle **{lifecycle_text}**；原因码：`{reason}`。"
        )
    lines += ["", "## 2. 世界/社会/市场：钱可能在哪里", ""]
    market = m.get("a_share_market_snapshot") or {}
    lines += ["### 今日A股大盘脉搏", ""]
    if market and market.get("status") != "UNAVAILABLE":
        lines.append(
            f"- {market.get('as_of_date') or '—'}：市场 **{market.get('status')}**；"
            f"数据质量 **{market.get('data_quality')}**；市场分数 **{_fmt(market.get('score'))}**；"
            f"仓位倍率 **{_fmt(market.get('position_multiplier'))}**。"
        )
        lines.append(
            f"- 上涨家数占比 **{_pct(market.get('advance_ratio'))}**；中位涨跌 **{_fmt(market.get('median_return_1d_pct'))}%**；"
            f"MA20 上方 **{_pct(market.get('above_ma20_ratio'))}**；MA60 上方 **{_pct(market.get('above_ma60_ratio'))}**；"
            f"涨停/跌停 **{market.get('limit_up_count', 0)}/{market.get('limit_down_count', 0)}**。"
        )
        lines.append(f"- 市场读法：**{_market_read(market)}**。这只是市场环境解释，不自行创造个股 BUY 权限。")
    else:
        lines.append("- 最新A股市场脉搏不可用；不据此放宽买入。")
    lines += ["", "### 中长期结构趋势", ""]
    lines.append("| 趋势 | 信心 | 结构 | 产业 | A股研究映射 |")
    lines.append("|---|---:|---:|---:|---|")
    for x in m["structural_world_social_trends"][:8]:
        mapped = "、".join(x.get("a_share_research_industries") or []) or "尚未映射"
        lines.append(
            f"| {x['trend_id']} | {_fmt(x.get('confidence_score'))} | {_fmt(x.get('structural_score'))} | "
            f"{_fmt(x.get('industrial_score'))} | {mapped} |"
        )
    coverage = m.get("capital_evidence_coverage") or {}
    family_counts = coverage.get("family_counts") or {}
    lines += ["", "### 资金流证据覆盖", ""]
    if coverage:
        lines.append(
            f"- 覆盖状态：**{coverage.get('status','UNAVAILABLE')}**；"
            f"政策资本 **{family_counts.get('POLICY_CAPITAL',0)}**；"
            f"产业资本 **{family_counts.get('INDUSTRIAL_CAPITAL',0)}**；"
            f"金融资本 **{family_counts.get('FINANCIAL_CAPITAL',0)}**；"
            f"真实需求 **{family_counts.get('REAL_DEMAND',0)}**。"
        )
        if coverage.get("financial_capital_evidence_available") is not True:
            lines.append("- **金融资本 live 证据尚未覆盖，因此当前不能声称‘资金流已经看清’；行业强弱只作为市场行为代理。**")
        else:
            lines.append("- 金融资本已有直接证据，但仍需与政策、产业资本、真实需求和个股深算交叉验证。")
    else:
        lines.append("- 资金流证据覆盖状态不可用；不据此制造资金流结论。")
    lines += ["", "### 近期市场行为代理", ""]
    tactical = m["tactical_market_behavior_proxy"]
    lines.append("、".join(f"{x.get('industry')}({_fmt(x.get('score'))})" for x in tactical[:8]) if tactical else "暂无可用代理。")
    lines += ["", f"- 已验证的趋势→A股研究交接：**{m['validated_handoff_count']}**。",
              "- 这里不冒充‘主力净流入’；结构趋势、市场行为和个股深算必须分层验证。",
              "", "## 3. 新机会：润贝型以及其他机会深算结果", ""]
    if o["buy_now"]:
        lines.append("### BUY NOW")
        for x in o["buy_now"]:
            lines.append(f"- **{x['name']} {x['code']}**：现价 {_fmt(x.get('current_price'))}；价值中枢 {_fmt(x.get('neutral_value'))}；估值信心 {x.get('valuation_confidence') or '—'}；深算 {x['deep_review']['status']}。")
    else:
        lines.append("- **本轮没有已授权新股 BUY。**")
    if o["wait_price"]:
        lines.append("")
        lines.append("### WAIT_PRICE")
        for x in o["wait_price"]:
            lines.append(f"- **{x['name']} {x['code']}**：等待 ≤{_fmt(x.get('wait_price_max'))}；深算 {x['deep_review']['status']}。")
    else:
        lines.append("- **本轮没有合格 WAIT_PRICE。**")
    lines += ["", f"- Formal/Production Candidate Terminal REJECT：**{o['terminal_reject_count']}**（只做汇总；与下方 Deep Research Terminal 的 RESEARCH_GAP/REJECT 是不同层级）。"]
    account = payload.get("today_account_plan") or {}
    lines += [
        "",
        "## 4. 今日账户资金怎么处理",
        "",
        f"- 可用现金：**¥{_fmt(account.get('available_cash_cny'))}**；可部署预算：**¥{_fmt(account.get('deployment_budget_cny'))}**；本轮计划立即投入：**¥{_fmt(account.get('planned_immediate_cash_cny'))}**；计划后现金：**¥{_fmt(account.get('cash_after_immediate_plan_cny'))}**。",
        f"- 盘中价覆盖：**{account.get('live_quote_applied_count',0)}/{account.get('live_quote_expected_count',0)}**；交易时段：**{account.get('market_session_state','UNKNOWN')}**；行情状态：**{account.get('market_data_status','UNAVAILABLE')}**。",
        f"- **{account.get('plain_language') or '资金计划不可用，保持现金。'}**",
        "",
        "### 今日最终操作表",
        "",
        "| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 | 执行状态 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    operations = account.get("operations") or []
    for x in operations:
        wait = str(x.get("action") or "").upper() == "WAIT_PRICE"
        shares = x.get("planned_trigger_shares") if wait else x.get("planned_shares")
        amount = x.get("reserved_cash_cny") if wait else x.get("estimated_cash_cny")
        if wait:
            execution_status = "等待价格触发，届时重新核验"
        elif x.get("immediate_execution_eligible") is True:
            execution_status = "具备执行条件，仍需人工确认"
        elif x.get("execution_note") == "LIVE_EXECUTION_QUOTE_UNAVAILABLE":
            execution_status = "暂不可执行：缺有效盘中价"
        elif x.get("execution_note") == "MARKET_NOT_IN_CONTINUOUS_SESSION":
            execution_status = "暂不可执行：非连续交易时段"
        elif x.get("execution_note") == "LIVE_PRICE_ABOVE_AUTHORIZED_LIMIT_USE_LIMIT_ORDER_ONLY":
            execution_status = "暂不可执行：现价高于授权上限"
        else:
            execution_status = "暂不可立即执行"
        lines.append(
            f"| {x.get('name','')} {x.get('code','')} | **{x.get('action') or '—'}** | {shares or 0} | "
            f"{_fmt(x.get('first_entry_max_price'))} | {_fmt(x.get('second_entry_max_price'))} | {_fmt(amount)} | {execution_status} |"
        )
    if not operations:
        lines.append("| — | 无新增资金动作 | 0 | — | — | 0 | 现金保留；持仓动作见第1节 |")
    lines += [
        "",
        "## 决策完整性",
        "",
    ]
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
