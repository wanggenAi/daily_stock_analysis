"""Investor-first decision dashboard assembled from existing GenGe production truth.

This is a presentation/aggregation layer only. It must never recompute or mutate
Formal BUY/ADD/HOLD/REDUCE/EXIT decisions. Formal actions are copied only from
an authorized Canonical snapshot; research, market and event inputs remain
context for human decision-making.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "GEN_GE_INVESTOR_DECISION_DASHBOARD_V1"
FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
NO_AUTO_TRADE = True

ACTION_ORDER = {
    "EXIT": 0,
    "SELL": 0,
    "REDUCE_50": 1,
    "REDUCE_25": 1,
    "REDUCE": 1,
    "ADD": 2,
    "BUY": 2,
    "HOLD_REVIEW": 3,
    "HOLD": 4,
    "": 9,
}

ACTION_LABELS = {
    "EXIT": "退出/卖出",
    "SELL": "卖出",
    "REDUCE_50": "减仓50%",
    "REDUCE_25": "减仓25%",
    "REDUCE": "减仓",
    "ADD": "加仓",
    "BUY": "买入",
    "HOLD_REVIEW": "持有观察",
    "HOLD": "继续持有",
    "": "观察",
}


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON: {path}")
    return payload


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


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


def _parse_markdown_table(path: Path | None, heading: str) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    header: list[str] = []
    rows: list[dict[str, str]] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            title = line[3:].strip().lower()
            if in_section and title != heading.lower():
                break
            in_section = title == heading.lower()
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not header:
            header = cells
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def load_confirmed_holdings(path: Path | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _parse_markdown_table(path, "Confirmed holdings"):
        code = _code(row.get("Code"))
        if not code or str(row.get("Status") or "").strip().upper() != "HELD":
            continue
        quantity = _number(row.get("Quantity"))
        average_cost = _number(row.get("Average cost (CNY)"))
        result[code] = {
            "code": code,
            "name": row.get("Name", ""),
            "quantity": int(quantity) if quantity is not None else None,
            "average_cost": average_cost,
            "evidence_date": row.get("Evidence date", ""),
            "status": "HELD",
        }
    return result


def load_confirmed_funds(path: Path | None) -> list[dict[str, Any]]:
    rows = _parse_markdown_table(path, "Confirmed funds")
    funds: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("Status") or "").strip().upper()
        if status not in {"HELD", "CONFIRMED"}:
            continue
        units = _number(row.get("Units") or row.get("Quantity"))
        avg = _number(row.get("Average cost (CNY)") or row.get("Average cost"))
        funds.append(
            {
                "code": str(row.get("Code") or "").strip(),
                "name": str(row.get("Name") or "").strip(),
                "units": units,
                "average_cost": avg,
                "status": status,
                "evidence_date": str(row.get("Evidence date") or "").strip(),
            }
        )
    return funds


def _validate_formal_snapshot(snapshot: Mapping[str, Any]) -> None:
    if not snapshot:
        raise ValueError("authorized canonical snapshot is required")
    production = snapshot.get("production")
    if not isinstance(production, Mapping):
        raise ValueError("canonical snapshot missing production section")
    decisions = list(production.get("holding_decisions") or []) + list(production.get("candidate_decisions") or [])
    for row in decisions:
        if row.get("no_auto_trade") is not True:
            raise ValueError("canonical decision lost no-auto-trade contract")
        if str(row.get("v311_production_bridge") or "") != "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT":
            raise ValueError("dashboard refuses non-production-bridge decision")


def _holding_guidance(
    snapshot: Mapping[str, Any],
    holdings: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    decisions = snapshot.get("production", {}).get("holding_decisions") or []
    by_code = {_code(row.get("code")): dict(row) for row in decisions}
    output: list[dict[str, Any]] = []
    for code, holding in holdings.items():
        row = by_code.get(code, {})
        action = str(row.get("action") or "").strip().upper()
        current_price = _number(row.get("current_price"))
        neutral_value = _number(row.get("neutral_value"))
        average_cost = _number(holding.get("average_cost"))
        pnl_pct = None
        if current_price is not None and average_cost not in (None, 0):
            pnl_pct = (current_price / average_cost - 1.0) * 100.0
        margin_of_safety = None
        if current_price is not None and neutral_value not in (None, 0):
            margin_of_safety = (neutral_value - current_price) / neutral_value
        output.append(
            {
                "code": code,
                "name": holding.get("name") or row.get("stock_name") or "",
                "quantity": holding.get("quantity"),
                "average_cost": average_cost,
                "current_price": current_price,
                "pnl_pct": None if pnl_pct is None else round(pnl_pct, 2),
                "neutral_value": neutral_value,
                "margin_of_safety": None if margin_of_safety is None else round(margin_of_safety, 4),
                "formal_action": action,
                "investor_action": ACTION_LABELS.get(action, action or "观察"),
                "valuation_confidence": row.get("valuation_confidence") or "",
                "reason_codes": row.get("reason_codes") or "",
                "hard_gate_failures": row.get("hard_gate_failures") or "",
                "hard_gate_unknowns": row.get("hard_gate_unknowns") or "",
                "price_date": row.get("price_date") or "",
                "decision_date": row.get("decision_date") or "",
            }
        )
    output.sort(key=lambda item: (ACTION_ORDER.get(item["formal_action"], 8), item["code"]))
    return output


def _research_opportunities(snapshot: Mapping[str, Any], holding_codes: set[str], limit: int = 12) -> list[dict[str, Any]]:
    production_candidates = {
        _code(row.get("code")): dict(row)
        for row in snapshot.get("production", {}).get("candidate_decisions") or []
    }
    rows = snapshot.get("deep_review", {}).get("rows") or snapshot.get("discovery", {}).get("rows") or []
    opportunities: list[dict[str, Any]] = []
    for row in rows:
        code = _code(row.get("code"))
        if not code or code in holding_codes:
            continue
        formal = production_candidates.get(code, {})
        formal_action = str(formal.get("action") or "").strip().upper()
        candidate_class = str(row.get("candidate_class") or "").strip().upper()
        blockers = str(row.get("hard_blockers") or "").strip()
        confidence = str(row.get("valuation_confidence") or formal.get("valuation_confidence") or "").strip().upper()
        if formal_action in {"BUY", "ADD"}:
            tier = "FORMAL_BUY_OR_ADD"
        elif candidate_class.startswith("A") and not blockers and confidence in {"HIGH", "MEDIUM"}:
            tier = "NEAR_BUY_RESEARCH"
        elif candidate_class.startswith("A") or confidence == "HIGH":
            tier = "PRIORITY_RESEARCH"
        else:
            tier = "RESEARCH_CANDIDATE"
        opportunities.append(
            {
                "rank": row.get("rank"),
                "code": code,
                "name": row.get("stock_name") or formal.get("stock_name") or "",
                "industry": row.get("industry") or "",
                "tier": tier,
                "formal_action": formal_action,
                "current_price": _number(formal.get("current_price") or row.get("current_price")),
                "valuation_confidence": confidence,
                "candidate_class": candidate_class,
                "hard_blockers": blockers,
                "reason_codes": formal.get("reason_codes") or "",
                "why_not_buy_yet": "" if formal_action in {"BUY", "ADD"} else blockers or "尚未通过全部正式 BUY/ADD 门槛",
            }
        )
    tier_order = {
        "FORMAL_BUY_OR_ADD": 0,
        "NEAR_BUY_RESEARCH": 1,
        "PRIORITY_RESEARCH": 2,
        "RESEARCH_CANDIDATE": 3,
    }
    opportunities.sort(
        key=lambda item: (
            tier_order.get(item["tier"], 9),
            int(item["rank"]) if str(item.get("rank") or "").isdigit() else 10**9,
            item["code"],
        )
    )
    return opportunities[: max(0, limit)]


def _market_context(market: Mapping[str, Any]) -> dict[str, Any]:
    if not market:
        return {
            "status": "UNAVAILABLE",
            "data_quality": "UNAVAILABLE",
            "allow_new_buy": None,
            "message": "最新全A市场状态未取到；不据此放宽买入。",
        }
    return {
        "as_of_date": market.get("as_of_date") or "",
        "status": market.get("status") or "UNKNOWN",
        "score": _number(market.get("score")),
        "allow_new_buy": market.get("allow_new_buy"),
        "position_multiplier": _number(market.get("position_multiplier")),
        "advance_ratio": _number(market.get("advance_ratio")),
        "median_return_1d_pct": _number(market.get("median_return_1d_pct")),
        "above_ma20_ratio": _number(market.get("above_ma20_ratio")),
        "above_ma60_ratio": _number(market.get("above_ma60_ratio")),
        "distribution_ratio": _number(market.get("distribution_ratio")),
        "limit_up_count": market.get("limit_up_count"),
        "limit_down_count": market.get("limit_down_count"),
        "external_risk_level": market.get("external_risk_level") or "UNKNOWN",
        "risk_reasons": list(market.get("risk_reasons") or []),
        "data_quality": market.get("data_quality") or "UNKNOWN",
    }


def _capital_direction(industry_rows: Iterable[Mapping[str, Any]], limit: int = 8) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in industry_rows:
        score = _number(row.get("score"))
        sample_count = _number(row.get("sample_count"))
        if not str(row.get("industry") or "").strip() or score is None:
            continue
        rows.append(
            {
                "industry": str(row.get("industry") or "").strip(),
                "status": str(row.get("status") or "UNKNOWN"),
                "score": score,
                "sample_count": int(sample_count) if sample_count is not None else None,
                "advance_ratio": _number(row.get("advance_ratio")),
                "median_return_1d_pct": _number(row.get("median_return_1d_pct")),
                "above_ma20_ratio": _number(row.get("above_ma20_ratio")),
                "distribution_ratio": _number(row.get("distribution_ratio")),
            }
        )
    rows.sort(key=lambda item: (-item["score"], item["industry"]))
    strongest = rows[: max(0, limit)]
    weakest = list(reversed(rows[-min(limit, len(rows)):])) if rows else []
    return {
        "direct_fund_flow_available": False,
        "direct_fund_flow_claimed": False,
        "method": "MARKET_BEHAVIOR_PROXY_PRICE_VOLUME_BREADTH",
        "explanation": "不把厂商标签“主力净流入”当成交易真相；用行业涨跌广度、均值收益、MA参与度和派发比例判断资金/风险偏好正在集中到哪里。",
        "strongest_industries": strongest,
        "weakest_industries": weakest,
    }


def _trend_context(snapshot: Mapping[str, Any], research_priority: Mapping[str, Any], *, limit: int = 8) -> dict[str, Any]:
    holding_codes = {
        _code(row.get("code"))
        for row in snapshot.get("production", {}).get("holding_decisions") or []
    }
    industry_counter: Counter[str] = Counter()
    strengthening: list[dict[str, Any]] = []
    for row in snapshot.get("deep_review", {}).get("rows") or []:
        industry = str(row.get("industry") or "").strip()
        if industry:
            industry_counter[industry] += 1
    for row in research_priority.get("queue") or []:
        if _code(row.get("code")) in holding_codes:
            continue
        if str(row.get("thesis_status") or "") == "STRENGTHENING_RESEARCH_SIGNAL":
            strengthening.append(
                {
                    "code": _code(row.get("code")),
                    "name": row.get("name") or "",
                    "priority": row.get("priority") or "",
                    "signal": "STRENGTHENING_RESEARCH_SIGNAL",
                }
            )
    return {
        "live_macro_social_radar_authoritative": False,
        "basis": "CURRENT_CANONICAL_RESEARCH_AND_HOURLY_EVIDENCE",
        "message": "这里展示当前产业/公司研究信号，不把尚未接入实时官方采集的 Era Radar 回放数据冒充实时社会趋势。",
        "research_concentration": [
            {"industry": industry, "deep_review_count": count}
            for industry, count in industry_counter.most_common(limit)
        ],
        "strengthening_signals": strengthening[:limit],
    }


def _event_context(event: Mapping[str, Any]) -> dict[str, Any]:
    if not event:
        return {"triggered": False, "status": "NO_EVENT_CONTEXT"}
    return {
        "triggered": bool(event.get("dispatch_required")),
        "trigger_codes": list(event.get("trigger_codes") or []),
        "holding_trigger_count": event.get("holding_trigger_count", 0),
        "external_trigger_count": event.get("external_trigger_count", 0),
        "trigger_reasons": event.get("trigger_reasons") or event.get("reason_codes") or [],
        "signal_digest": event.get("signal_digest") or "",
        "formal_action_recomputed": event.get("formal_action_recomputed"),
        "formal_action_source": event.get("formal_action_source") or FORMAL_ACTION_SOURCE,
    }


def build_dashboard(
    *,
    canonical: Mapping[str, Any],
    holdings: Mapping[str, Mapping[str, Any]],
    funds: list[dict[str, Any]],
    hourly: Mapping[str, Any] | None = None,
    research_priority: Mapping[str, Any] | None = None,
    market_regime: Mapping[str, Any] | None = None,
    industry_regimes: Iterable[Mapping[str, Any]] = (),
    event_decision: Mapping[str, Any] | None = None,
    mode: str = "HOURLY",
    generated_at: str | None = None,
) -> dict[str, Any]:
    _validate_formal_snapshot(canonical)
    holding_rows = _holding_guidance(canonical, holdings)
    action_counts = Counter(item["formal_action"] or "NO_ACTION" for item in holding_rows)
    opportunities = _research_opportunities(canonical, set(holdings))
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    urgent = [item for item in holding_rows if item["formal_action"] in {"EXIT", "SELL", "REDUCE", "REDUCE_25", "REDUCE_50"}]
    add_buy = [item for item in holding_rows if item["formal_action"] in {"BUY", "ADD"}]
    candidate_buy = [item for item in opportunities if item["formal_action"] in {"BUY", "ADD"}]
    headline_parts: list[str] = []
    if urgent:
        headline_parts.append(f"{len(urgent)}只持仓需要减仓/退出处理")
    if add_buy:
        headline_parts.append(f"{len(add_buy)}只持仓达到加仓/买入动作")
    if candidate_buy:
        headline_parts.append(f"{len(candidate_buy)}只新候选达到正式BUY/ADD")
    if not headline_parts:
        headline_parts.append("当前没有新的正式买入/加仓或退出动作")
    if any(item["formal_action"] == "HOLD_REVIEW" for item in holding_rows):
        headline_parts.append("存在需要重点复核的持仓")

    funds_status = "CONFIRMED" if funds else "LATEST_HOLDINGS_NOT_PERSISTED"
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": str(mode or "HOURLY").upper(),
        "generated_at": generated,
        "canonical_snapshot_id": canonical.get("snapshot_id") or "",
        "canonical_source_run_id": canonical.get("source_run_id") or "",
        "latest_trade_date": canonical.get("latest_trade_date") or "",
        "formal_action_source": FORMAL_ACTION_SOURCE,
        "formal_action_recomputed": False,
        "no_auto_trade": NO_AUTO_TRADE,
        "headline": "；".join(headline_parts),
        "decision_summary": {
            "holding_count": len(holding_rows),
            "formal_action_counts": dict(sorted(action_counts.items())),
            "formal_candidate_buy_add_count": len(candidate_buy),
            "priority_research_count": len(opportunities),
        },
        "stock_portfolio": {
            "status": "CONFIRMED" if holdings else "NO_CONFIRMED_HOLDINGS",
            "rows": holding_rows,
        },
        "fund_portfolio": {
            "status": funds_status,
            "rows": funds,
            "message": "基金最新持仓已纳入驾驶舱。" if funds else "仓库尚无最新确认基金持仓；不从旧聊天或旧截图猜测，需最新持仓证据后再给补/减/卖决策。",
        },
        "market": _market_context(market_regime or {}),
        "capital_direction": _capital_direction(industry_regimes),
        "structural_trends": _trend_context(canonical, research_priority or {}),
        "opportunities": opportunities,
        "event_review": _event_context(event_decision or {}),
        "hourly_context": {
            "available": bool(hourly),
            "canonical_snapshot_id": (hourly or {}).get("canonical_snapshot_id") or "",
            "research_as_of": (hourly or {}).get("research_as_of") or "",
            "formal_action_recomputed": (hourly or {}).get("formal_action_recomputed"),
        },
        "presentation_contract": {
            "investor_first": True,
            "section_order": [
                "stock_portfolio",
                "fund_portfolio",
                "market",
                "capital_direction",
                "structural_trends",
                "opportunities",
                "event_review",
            ],
            "engineering_details_are_secondary": True,
        },
    }


def _fmt_pct(value: Any) -> str:
    num = _number(value)
    return "—" if num is None else f"{num:.2f}%"


def _fmt_num(value: Any) -> str:
    num = _number(value)
    return "—" if num is None else f"{num:.2f}"


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 投资决策驾驶舱",
        "",
        f"> {payload.get('headline') or ''}",
        "",
        f"- 数据日期：`{payload.get('latest_trade_date') or '未知'}`",
        f"- 模式：`{payload.get('mode')}`",
        "- 正式买卖动作只来自已授权 Canonical；小时/事件/趋势只提供研究上下文，不擅自改动作。",
        "",
        "## 1. 我的股票：现在该怎么做",
        "",
        "| 股票 | 持仓 | 成本 | 参考价 | 盈亏 | 正式动作 | 投资者动作 |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in payload.get("stock_portfolio", {}).get("rows") or []:
        name = f"{row.get('name','')} {row.get('code','')}".strip()
        lines.append(
            f"| {name} | {row.get('quantity') if row.get('quantity') is not None else '—'} | "
            f"{_fmt_num(row.get('average_cost'))} | {_fmt_num(row.get('current_price'))} | "
            f"{_fmt_pct(row.get('pnl_pct'))} | {row.get('formal_action') or '—'} | "
            f"**{row.get('investor_action') or '观察'}** |"
        )
    if not payload.get("stock_portfolio", {}).get("rows"):
        lines.append("| — | — | — | — | — | — | 暂无确认持仓 |")

    lines += ["", "## 2. 我的基金", ""]
    funds = payload.get("fund_portfolio", {})
    lines.append(f"- 状态：**{funds.get('status')}**")
    lines.append(f"- {funds.get('message')}")
    if funds.get("rows"):
        lines += ["", "| 基金 | 份额 | 成本 | 状态 |", "|---|---:|---:|---|"]
        for row in funds["rows"]:
            lines.append(
                f"| {row.get('name','')} {row.get('code','')} | {_fmt_num(row.get('units'))} | "
                f"{_fmt_num(row.get('average_cost'))} | {row.get('status')} |"
            )

    market = payload.get("market", {})
    lines += [
        "",
        "## 3. 市场现在是什么状态",
        "",
        f"- 市场状态：**{market.get('status','UNKNOWN')}**；评分：**{_fmt_num(market.get('score'))}**",
        f"- 是否允许新买：**{market.get('allow_new_buy')}**；建议仓位倍率：**{_fmt_num(market.get('position_multiplier'))}**",
        f"- 上涨家数比例：**{_fmt_pct((_number(market.get('advance_ratio')) or 0) * 100 if market.get('advance_ratio') is not None else None)}**；MA20上方比例：**{_fmt_pct((_number(market.get('above_ma20_ratio')) or 0) * 100 if market.get('above_ma20_ratio') is not None else None)}**",
        f"- 外部市场风险：**{market.get('external_risk_level','UNKNOWN')}**；数据质量：**{market.get('data_quality','UNKNOWN')}**",
    ]
    if market.get("risk_reasons"):
        lines.append(f"- 主要风险：`{', '.join(map(str, market['risk_reasons']))}`")

    capital = payload.get("capital_direction", {})
    lines += ["", "## 4. 钱往哪里走", "", "- 这里使用可审计的市场行为代理，不把“主力资金”厂商标签当成事实。"]
    strong = capital.get("strongest_industries") or []
    if strong:
        lines += ["", "| 强势行业 | 状态 | 强度 | 上涨比例 | MA20参与度 |", "|---|---|---:|---:|---:|"]
        for row in strong:
            lines.append(
                f"| {row.get('industry')} | {row.get('status')} | {_fmt_num(row.get('score'))} | "
                f"{_fmt_pct((_number(row.get('advance_ratio')) or 0) * 100 if row.get('advance_ratio') is not None else None)} | "
                f"{_fmt_pct((_number(row.get('above_ma20_ratio')) or 0) * 100 if row.get('above_ma20_ratio') is not None else None)} |"
            )
    else:
        lines.append("- 最新行业资金方向代理数据暂缺。")

    trends = payload.get("structural_trends", {})
    lines += ["", "## 5. 产业 / 社会发展趋势", "", f"- {trends.get('message','')}"]
    if trends.get("research_concentration"):
        lines.append("- 深度研究正在集中的行业：" + "、".join(f"{row['industry']}({row['deep_review_count']})" for row in trends["research_concentration"]))
    if trends.get("strengthening_signals"):
        lines.append("- 正在增强的公司级研究信号：" + "、".join(f"{row['name']}({row['code']})" for row in trends["strengthening_signals"]))

    lines += ["", "## 6. 全市场机会：哪些值得继续盯", "", "| 股票 | 行业 | 层级 | 正式动作 | 估值信心 | 为什么还不能买 |", "|---|---|---|---|---|---|"]
    for row in payload.get("opportunities") or []:
        lines.append(
            f"| {row.get('name','')} {row.get('code','')} | {row.get('industry') or '—'} | "
            f"{row.get('tier')} | {row.get('formal_action') or '—'} | "
            f"{row.get('valuation_confidence') or '—'} | {row.get('why_not_buy_yet') or '—'} |"
        )
    if not payload.get("opportunities"):
        lines.append("| — | — | — | — | — | 暂无候选 |")

    event = payload.get("event_review", {})
    lines += ["", "## 7. 事件触发 / 深算变化", ""]
    if event.get("triggered"):
        lines.append(
            f"- **发生事件触发**：{', '.join(event.get('trigger_codes') or []) or '未列出代码'}；"
            f"持仓触发 {event.get('holding_trigger_count',0)}，外部候选触发 {event.get('external_trigger_count',0)}。"
        )
    else:
        lines.append("- 当前没有需要单独展示的事件触发上下文。")

    lines += ["", "---", "技术运行、artifact、SHA、persistence 等工程信息不作为投资者首页内容；只有在影响数据可信度时才升级成风险提示。", ""]
    return "\n".join(lines)


def write_dashboard(
    *,
    canonical_path: Path,
    holdings_path: Path,
    funds_path: Path | None,
    hourly_path: Path | None,
    research_priority_path: Path | None,
    market_regime_path: Path | None,
    industry_regimes_path: Path | None,
    event_decision_path: Path | None,
    json_output: Path,
    markdown_output: Path,
    mode: str,
) -> dict[str, Any]:
    payload = build_dashboard(
        canonical=_load_json(canonical_path),
        holdings=load_confirmed_holdings(holdings_path),
        funds=load_confirmed_funds(funds_path),
        hourly=_load_json(hourly_path),
        research_priority=_load_json(research_priority_path),
        market_regime=_load_json(market_regime_path),
        industry_regimes=_read_csv(industry_regimes_path),
        event_decision=_load_json(event_decision_path),
        mode=mode,
    )
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--holdings", type=Path, default=Path("CURRENT_HOLDINGS.md"))
    parser.add_argument("--funds", type=Path, default=Path("CURRENT_FUNDS.md"))
    parser.add_argument("--hourly", type=Path)
    parser.add_argument("--research-priority", type=Path)
    parser.add_argument("--market-regime", type=Path)
    parser.add_argument("--industry-regimes", type=Path)
    parser.add_argument("--event-decision", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--mode", default="HOURLY")
    args = parser.parse_args(argv)
    payload = write_dashboard(
        canonical_path=args.canonical,
        holdings_path=args.holdings,
        funds_path=args.funds,
        hourly_path=args.hourly,
        research_priority_path=args.research_priority,
        market_regime_path=args.market_regime,
        industry_regimes_path=args.industry_regimes,
        event_decision_path=args.event_decision,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
        mode=args.mode,
    )
    print(
        "investor_dashboard="
        f"{payload['mode']};snapshot={payload['canonical_snapshot_id']};"
        f"holdings={payload['decision_summary']['holding_count']};"
        f"formal_candidate_buy_add={payload['decision_summary']['formal_candidate_buy_add_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
