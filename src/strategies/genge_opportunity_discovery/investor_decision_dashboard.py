"""Investor-first dashboard built only from authorized GenGe truth.

Formal holding actions are copied from Canonical. New-stock BUY is actionable
only when Candidate Terminal Review marks BUY *and* proves it is a mirror of an
already-authorized Formal/Production BUY. WAIT_PRICE is a price trigger only;
REJECT receives zero capital. This module may make execution more conservative
(lot sizing, cash caps, staged lower entries) but never loosens investment gates.
No automatic order placement is allowed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "GEN_GE_INVESTOR_DECISION_DASHBOARD_V2"
FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
TERMINAL_AUTHORITY = "RESEARCH_TERMINAL_VIEW"
NO_AUTO_TRADE = True
LOT_SIZE = 100
ACTION_LABELS = {
    "EXIT": "退出/卖出", "SELL": "卖出", "REDUCE_50": "减仓50%",
    "REDUCE_25": "减仓25%", "REDUCE": "减仓", "ADD": "加仓",
    "BUY": "买入", "HOLD_REVIEW": "持有观察", "HOLD": "继续持有", "": "观察",
}
ACTION_ORDER = {"EXIT": 0, "SELL": 0, "REDUCE_50": 1, "REDUCE_25": 1, "REDUCE": 1,
                "ADD": 2, "BUY": 2, "HOLD_REVIEW": 3, "HOLD": 4, "": 9}


def _num(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _bool(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


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


def _json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def _csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _md_table(path: Path | None, heading: str) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    inside = False
    header: list[str] = []
    rows: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            title = line[3:].strip().lower()
            if inside and title != heading.lower():
                break
            inside = title == heading.lower()
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [x.strip() for x in line.strip("|").split("|")]
        if not header:
            header = cells
        elif not all(re.fullmatch(r":?-{3,}:?", x.replace(" ", "")) for x in cells) and len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


def load_confirmed_holdings(path: Path | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _md_table(path, "Confirmed holdings"):
        code = _code(row.get("Code"))
        if code and str(row.get("Status") or "").upper() == "HELD":
            q, cost = _num(row.get("Quantity")), _num(row.get("Average cost (CNY)"))
            result[code] = {"code": code, "name": row.get("Name", ""),
                            "quantity": int(q) if q is not None else None,
                            "average_cost": cost, "status": "HELD"}
    return result


def load_confirmed_funds(path: Path | None) -> list[dict[str, Any]]:
    result = []
    for row in _md_table(path, "Confirmed funds"):
        if str(row.get("Status") or "").upper() in {"HELD", "CONFIRMED"}:
            result.append({"code": row.get("Code", ""), "name": row.get("Name", ""),
                           "units": _num(row.get("Units") or row.get("Quantity")),
                           "average_cost": _num(row.get("Average cost (CNY)")),
                           "status": row.get("Status", "")})
    return result


def load_capital(path: Path | None) -> dict[str, Any]:
    raw = _json(path)
    if not raw:
        return {"status": "UNAVAILABLE", "planning_cash_cny": 0.0, "planner": {},
                "automatic_order_allowed": False, "no_auto_trade": True}
    if raw.get("no_auto_trade") is not True:
        raise ValueError("capital source lost no-auto-trade contract")
    cash = _num(raw.get("planning_cash_cny"))
    if cash is None or cash < 0:
        raise ValueError("capital source requires non-negative planning_cash_cny")
    return {**raw, "planning_cash_cny": cash, "automatic_order_allowed": False, "no_auto_trade": True}


def _validate_canonical(snapshot: Mapping[str, Any]) -> None:
    production = snapshot.get("production") if snapshot else None
    if not isinstance(production, Mapping):
        raise ValueError("authorized canonical snapshot is required")
    for row in list(production.get("holding_decisions") or []) + list(production.get("candidate_decisions") or []):
        if row.get("no_auto_trade") is not True:
            raise ValueError("canonical decision lost no-auto-trade contract")
        if str(row.get("v311_production_bridge") or "") != "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT":
            raise ValueError("dashboard refuses non-production-bridge decision")


def _holdings(snapshot: Mapping[str, Any], holdings: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_code = {_code(x.get("code")): dict(x) for x in snapshot.get("production", {}).get("holding_decisions") or []}
    result = []
    for code, held in holdings.items():
        src = by_code.get(code, {})
        action = str(src.get("action") or src.get("production_action") or "").upper()
        price, cost = _num(src.get("current_price")), _num(held.get("average_cost"))
        pnl = (price / cost - 1) * 100 if price is not None and cost not in {None, 0} else None
        result.append({"code": code, "name": held.get("name") or src.get("stock_name") or "",
                       "quantity": held.get("quantity"), "average_cost": cost, "current_price": price,
                       "pnl_pct": None if pnl is None else round(pnl, 2), "formal_action": action,
                       "investor_action": ACTION_LABELS.get(action, action or "观察"),
                       "neutral_value": _num(src.get("neutral_value")),
                       "valuation_confidence": src.get("valuation_confidence") or "",
                       "reason_codes": src.get("reason_codes") or ""})
    result.sort(key=lambda x: (ACTION_ORDER.get(x["formal_action"], 8), x["code"]))
    return result


def _market(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not raw:
        return {"status": "UNAVAILABLE", "data_quality": "UNAVAILABLE", "allow_new_buy": None,
                "position_multiplier": None, "message": "最新全A市场状态未取到；不据此放宽买入。"}
    keys = ("as_of_date", "status", "allow_new_buy", "external_risk_level", "data_quality",
            "limit_up_count", "limit_down_count")
    out = {k: raw.get(k) for k in keys}
    for k in ("score", "position_multiplier", "advance_ratio", "median_return_1d_pct",
              "above_ma20_ratio", "above_ma60_ratio", "distribution_ratio"):
        out[k] = _num(raw.get(k))
    out["risk_reasons"] = list(raw.get("risk_reasons") or [])
    return out


def _terminal(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    buy, wait, reject, unauthorized = [], [], 0, 0
    for raw in rows:
        decision, code = str(raw.get("terminal_decision") or "").upper(), _code(raw.get("code"))
        if not code or decision not in {"BUY", "WAIT_PRICE", "REJECT"}:
            continue
        if not _bool(raw.get("no_auto_trade")):
            raise ValueError(f"terminal decision lost no-auto-trade contract: {code}")
        authority = str(raw.get("decision_authority") or TERMINAL_AUTHORITY)
        if authority != TERMINAL_AUTHORITY:
            raise ValueError(f"unexpected terminal authority: {authority}")
        item = {"rank": raw.get("master_research_rank"), "code": code,
                "name": raw.get("stock_name") or "", "industry": raw.get("industry") or "",
                "terminal_decision": decision, "current_price": _num(raw.get("terminal_current_price")),
                "wait_price_max": _num(raw.get("wait_price_max")),
                "reason_class": raw.get("terminal_reason_class") or "",
                "formal_buy_authorized": _bool(raw.get("terminal_formal_buy_authorized")),
                "valuation_confidence": raw.get("source_valuation_confidence") or "",
                "neutral_value": _num(raw.get("neutral_value") or raw.get("v31_neutral_value")),
                "buy_ratio": _num(raw.get("formal_buy_max_price_to_neutral"))}
        if decision == "BUY":
            if item["formal_buy_authorized"]:
                buy.append(item)
            else:
                unauthorized += 1
        elif decision == "WAIT_PRICE":
            if item["wait_price_max"] is None:
                raise ValueError(f"WAIT_PRICE missing wait_price_max: {code}")
            wait.append(item)
        else:
            reject += 1
    def rk(x: Mapping[str, Any]) -> tuple[int, str]:
        try: n = int(float(x.get("rank") or 10**9))
        except (TypeError, ValueError): n = 10**9
        return n, str(x.get("code") or "")
    buy.sort(key=rk); wait.sort(key=rk)
    return {"available": bool(buy or wait or reject), "buy_now": buy, "wait_price": wait,
            "reject_count": reject, "invalid_unauthorized_buy_count": unauthorized,
            "decision_authority": TERMINAL_AUTHORITY, "formal_buy_is_mirror_only": True}


def _planner_cfg(capital: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(capital.get("planner") or {})
    def val(name: str, default: float, low: float, high: float) -> float:
        n = _num(raw.get(name)); n = default if n is None else n
        return min(high, max(low, n))
    return {"max_deployment_ratio": val("max_deployment_ratio", .70, 0, 1),
            "max_single_name_ratio_of_available_cash": val("max_single_name_ratio_of_available_cash", .20, 0, 1),
            "max_names": int(val("max_names", 5, 1, 20)),
            "first_tranche_ratio": val("first_tranche_ratio", .50, 0, 1),
            "second_tranche_discount_pct": val("second_tranche_discount_pct", .02, 0, .20),
            "lot_size": LOT_SIZE}


def _lot_cash(cash: float, price: float) -> int:
    return 0 if cash <= 0 or price <= 0 else int(cash // (price * LOT_SIZE)) * LOT_SIZE


def _split(shares: int, ratio: float) -> tuple[int, int]:
    lots = shares // LOT_SIZE
    if lots <= 1: return shares, 0
    first = max(1, min(lots, int(round(lots * ratio))))
    return first * LOT_SIZE, (lots - first) * LOT_SIZE


def _plan(capital: Mapping[str, Any], market: Mapping[str, Any], holdings: list[dict[str, Any]], terminal: Mapping[str, Any]) -> dict[str, Any]:
    cash, cfg = _num(capital.get("planning_cash_cny")) or 0.0, _planner_cfg(capital)
    ratio = cfg["max_deployment_ratio"]
    mult = _num(market.get("position_multiplier"))
    if mult is not None: ratio = min(ratio, max(0.0, min(1.0, mult)))
    if market.get("allow_new_buy") is False: ratio = 0.0
    budget, per_name = round(cash * ratio, 2), round(cash * cfg["max_single_name_ratio_of_available_cash"], 2)
    actions = []
    for x in holdings:
        if x["formal_action"] in {"ADD", "BUY"} and (x.get("current_price") or 0) > 0:
            actions.append({"code": x["code"], "name": x["name"], "action": "ADD", "current_price": x["current_price"],
                            "source": "AUTHORIZED_CANONICAL_HOLDING_ACTION", "authorization_proven": True})
    for x in terminal.get("buy_now") or []:
        if (x.get("current_price") or 0) > 0 and x.get("formal_buy_authorized"):
            ceiling = x["neutral_value"] * x["buy_ratio"] if x.get("neutral_value") and x.get("buy_ratio") else None
            actions.append({"code": x["code"], "name": x["name"], "action": "BUY", "current_price": x["current_price"],
                            "source": "TERMINAL_FORMAL_BUY_MIRROR", "formal_ceiling": ceiling, "authorization_proven": True})
    dedup, seen = [], set()
    for x in actions:
        if x["code"] not in seen:
            dedup.append(x); seen.add(x["code"])
    actions = dedup[:cfg["max_names"]]
    operations, remaining = [], budget
    for i, x in enumerate(actions):
        target = min(per_name, remaining / max(1, len(actions) - i))
        p = float(x["current_price"]); shares = _lot_cash(target, p); a, b = _split(shares, cfg["first_tranche_ratio"])
        p1 = round(min(p, x.get("formal_ceiling")) if x.get("formal_ceiling") else p, 2)
        p2 = round(min(p1, p * (1 - cfg["second_tranche_discount_pct"])), 2)
        spend = round(a*p1 + b*p2, 2); remaining = max(0.0, round(remaining-spend, 2))
        operations.append({**x, "planned_shares": a+b, "first_tranche_shares": a, "first_entry_max_price": p1,
                           "second_tranche_shares": b, "second_entry_max_price": p2 if b else None,
                           "estimated_cash_cny": spend, "immediate_execution_eligible": bool(a+b),
                           "automatic_order_allowed": False, "no_auto_trade": True})
    deployed = round(sum(x["estimated_cash_cny"] for x in operations), 2)
    reserve_capacity, waits = max(0.0, cash-deployed), []
    for x in (terminal.get("wait_price") or [])[:cfg["max_names"]]:
        p = float(x["wait_price_max"]); reserve = min(per_name, reserve_capacity)
        shares = _lot_cash(reserve, p); a, b = _split(shares, cfg["first_tranche_ratio"])
        p2 = round(p*(1-cfg["second_tranche_discount_pct"]), 2); reserved = round(a*p+b*p2, 2)
        reserve_capacity = max(0.0, reserve_capacity-reserved)
        waits.append({"code": x["code"], "name": x["name"], "action": "WAIT_PRICE", "source": "TERMINAL_PRICE_TRIGGER",
                      "planned_trigger_shares": a+b, "first_tranche_shares": a, "first_entry_max_price": round(p,2),
                      "second_tranche_shares": b, "second_entry_max_price": p2 if b else None,
                      "reserved_cash_cny": reserved, "immediate_execution_eligible": False,
                      "automatic_order_allowed": False, "no_auto_trade": True})
    return {"status": "READY" if capital.get("status") != "UNAVAILABLE" else "CAPITAL_UNAVAILABLE",
            "available_cash_cny": round(cash,2), "capital_as_of": capital.get("as_of") or "",
            "deployment_budget_cny": budget, "effective_max_deployment_ratio": round(ratio,4),
            "planned_immediate_cash_cny": deployed, "cash_after_immediate_plan_cny": round(cash-deployed,2),
            "operations": operations, "wait_price_reservations": waits, "planner_config": cfg,
            "authorization_rule": "CANONICAL_HOLDING_ADD_OR_AUTHORIZED_TERMINAL_BUY_ONLY",
            "wait_price_rule": "WAIT_PRICE_IS_NOT_IMMEDIATE_BUY", "reject_allocation_rule": "REJECT_GETS_ZERO_CAPITAL",
            "automatic_order_allowed": False, "no_auto_trade": True}


def _industries(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    out = []
    for x in rows:
        score = _num(x.get("score"))
        if score is not None and str(x.get("industry") or "").strip():
            out.append({"industry": str(x.get("industry")), "status": x.get("status") or "UNKNOWN", "score": score})
    out.sort(key=lambda x: (-x["score"], x["industry"]))
    return {"direct_fund_flow_claimed": False, "method": "MARKET_BEHAVIOR_PROXY", "strongest_industries": out[:8]}


def build_dashboard(*, canonical: Mapping[str, Any], holdings: Mapping[str, Mapping[str, Any]], funds: list[dict[str, Any]],
                    capital: Mapping[str, Any] | None = None, terminal_decisions: Iterable[Mapping[str, Any]] = (),
                    hourly: Mapping[str, Any] | None = None, research_priority: Mapping[str, Any] | None = None,
                    market_regime: Mapping[str, Any] | None = None, industry_regimes: Iterable[Mapping[str, Any]] = (),
                    event_decision: Mapping[str, Any] | None = None, mode: str = "HOURLY", generated_at: str | None = None) -> dict[str, Any]:
    _validate_canonical(canonical)
    held = _holdings(canonical, holdings); market = _market(market_regime or {}); terminal = _terminal(terminal_decisions)
    cap = dict(capital or {"status":"UNAVAILABLE","planning_cash_cny":0.0,"planner":{},"no_auto_trade":True})
    if cap.get("no_auto_trade") is not True: raise ValueError("capital planner input lost no-auto-trade contract")
    plan = _plan(cap, market, held, terminal); counts = Counter(x["formal_action"] or "NO_ACTION" for x in held)
    urgent = sum(x["formal_action"] in {"EXIT","SELL","REDUCE","REDUCE_25","REDUCE_50"} for x in held)
    final_ops = list(plan["operations"]) + list(plan["wait_price_reservations"])
    return {"contract_version": CONTRACT_VERSION, "mode": str(mode).upper(),
            "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "canonical_snapshot_id": canonical.get("snapshot_id") or "", "canonical_source_run_id": canonical.get("source_run_id") or "",
            "latest_trade_date": canonical.get("latest_trade_date") or "", "formal_action_source": FORMAL_ACTION_SOURCE,
            "formal_action_recomputed": False, "no_auto_trade": True,
            "headline": f"市场={market.get('status','UNKNOWN')}；持仓减仓/退出={urgent}；新股正式BUY={len(terminal['buy_now'])}；等价格={len(terminal['wait_price'])}；计划立即投入≈¥{plan['planned_immediate_cash_cny']:.0f}",
            "market": market, "stock_portfolio": {"status":"CONFIRMED" if holdings else "NO_CONFIRMED_HOLDINGS","rows":held},
            "terminal_opportunities": terminal, "capital_deployment": plan, "final_operation_table": final_ops,
            "decision_summary": {"holding_count":len(held),"formal_action_counts":dict(sorted(counts.items())),
                                 "terminal_buy_count":len(terminal["buy_now"]),"terminal_wait_price_count":len(terminal["wait_price"]),
                                 "terminal_reject_count":terminal["reject_count"],"planned_immediate_cash_cny":plan["planned_immediate_cash_cny"]},
            "capital_direction": _industries(industry_regimes),
            "fund_portfolio": {"status":"CONFIRMED" if funds else "LATEST_HOLDINGS_NOT_PERSISTED","rows":funds},
            "event_review": {"triggered":bool((event_decision or {}).get("dispatch_required")),"trigger_codes":list((event_decision or {}).get("trigger_codes") or [])},
            "hourly_context": {"available":bool(hourly),"research_as_of":(hourly or {}).get("research_as_of") or ""},
            "data_health": {"canonical_authority_available":True,"terminal_decisions_available":terminal["available"],
                            "terminal_unauthorized_buy_suppressed":terminal["invalid_unauthorized_buy_count"],
                            "capital_source_status":cap.get("status") or "UNAVAILABLE","engineering_details_are_secondary":True},
            "presentation_contract": {"investor_first":True,"section_order":["market","stock_portfolio","terminal_buy_now","terminal_wait_price","capital_deployment","final_operation_table","capital_direction","fund_portfolio","data_health"],"engineering_details_are_secondary":True}}


def _f(value: Any) -> str:
    n = _num(value); return "—" if n is None else f"{n:.2f}"


def render_markdown(p: Mapping[str, Any]) -> str:
    m, t, plan = p.get("market",{}), p.get("terminal_opportunities",{}), p.get("capital_deployment",{})
    lines=["# 投资决策驾驶舱","",f"> {p.get('headline','')}","","## 1. 今天市场怎么样","",
           f"- 市场状态：**{m.get('status','UNKNOWN')}**；是否允许新买：**{m.get('allow_new_buy')}**；仓位倍率：**{_f(m.get('position_multiplier'))}**",
           f"- 上涨家数比例：**{_f((_num(m.get('advance_ratio')) or 0)*100 if m.get('advance_ratio') is not None else None)}%**；数据质量：**{m.get('data_quality','UNKNOWN')}**","",
           "## 2. 我的持仓怎么办","","| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作 | 现在怎么办 |","|---|---:|---:|---:|---:|---|---|"]
    for x in p.get("stock_portfolio",{}).get("rows") or []:
        lines.append(f"| {x.get('name','')} {x.get('code','')} | {x.get('quantity') or 0} | {_f(x.get('average_cost'))} | {_f(x.get('current_price'))} | {_f(x.get('pnl_pct'))} | {x.get('formal_action') or '—'} | **{x.get('investor_action')}** |")
    lines += ["","## 3. 今天能直接买什么","","| 股票 | 行业 | 当前价 | 估值信心 | 权限 |","|---|---|---:|---|---|"]
    for x in t.get("buy_now") or []: lines.append(f"| {x['name']} {x['code']} | {x.get('industry') or '—'} | {_f(x.get('current_price'))} | {x.get('valuation_confidence') or '—'} | **正式BUY镜像** |")
    if not t.get("buy_now"): lines.append("| — | — | — | — | 本轮没有已授权新股BUY |")
    lines += ["","## 4. WAIT_PRICE：跌到多少钱再买","","| 股票 | 当前价 | 最高等待买价 |","|---|---:|---:|"]
    for x in t.get("wait_price") or []: lines.append(f"| {x['name']} {x['code']} | {_f(x.get('current_price'))} | **≤{_f(x.get('wait_price_max'))}** |")
    if not t.get("wait_price"): lines.append("| — | — | 本轮没有合格 WAIT_PRICE |")
    lines += ["","## 5. 资金怎么花","",f"- 可规划现金：**¥{_f(plan.get('available_cash_cny'))}**；最高部署预算：**¥{_f(plan.get('deployment_budget_cny'))}**",
              f"- 计划立即投入：**¥{_f(plan.get('planned_immediate_cash_cny'))}**；计划后现金：**¥{_f(plan.get('cash_after_immediate_plan_cny'))}**",
              "- 只有 Canonical 持仓 ADD 或授权 Terminal BUY 才能立即分配；WAIT_PRICE 只预留，REJECT=0。","","## 6. 最终操作表","",
              "| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 |","|---|---|---:|---:|---:|---:|"]
    for x in p.get("final_operation_table") or []:
        wait=x.get("action")=="WAIT_PRICE"; shares=x.get("planned_trigger_shares") if wait else x.get("planned_shares"); amount=x.get("reserved_cash_cny") if wait else x.get("estimated_cash_cny")
        lines.append(f"| {x.get('name','')} {x.get('code','')} | **{x.get('action')}** | {shares or 0} | {_f(x.get('first_entry_max_price'))} | {_f(x.get('second_entry_max_price'))} | {_f(amount)} |")
    if not p.get("final_operation_table"): lines.append("| — | — | 0 | — | — | 0 |")
    strong=p.get("capital_direction",{}).get("strongest_industries") or []
    lines += ["","## 7. 当前强势方向（辅助，不代替BUY权限）","", "、".join(f"{x['industry']}({x['status']})" for x in strong) if strong else "最新行业代理暂缺。",
              "","## 8. 其他已确认资产","",f"- 基金状态：**{p.get('fund_portfolio',{}).get('status')}**","","## 9. 系统状态（最后看）","",
              f"- Canonical：**正常**；Terminal：**{'可用' if p.get('data_health',{}).get('terminal_decisions_available') else '暂无可用产物'}**；资金源：**{p.get('data_health',{}).get('capital_source_status')}**",
              "- 工程 SHA / artifact / CI 不放首页；只有影响数据可信度时才升级提示。","","- **no-auto-trade：true；所有订单必须人工确认。**",""]
    return "\n".join(lines)


def write_dashboard(*, canonical_path: Path, holdings_path: Path, funds_path: Path | None, capital_path: Path | None,
                    terminal_decisions_path: Path | None, hourly_path: Path | None, research_priority_path: Path | None,
                    market_regime_path: Path | None, industry_regimes_path: Path | None, event_decision_path: Path | None,
                    json_output: Path, markdown_output: Path, mode: str) -> dict[str, Any]:
    p=build_dashboard(canonical=_json(canonical_path),holdings=load_confirmed_holdings(holdings_path),funds=load_confirmed_funds(funds_path),
        capital=load_capital(capital_path),terminal_decisions=_csv(terminal_decisions_path),hourly=_json(hourly_path),research_priority=_json(research_priority_path),
        market_regime=_json(market_regime_path),industry_regimes=_csv(industry_regimes_path),event_decision=_json(event_decision_path),mode=mode)
    json_output.parent.mkdir(parents=True,exist_ok=True); markdown_output.parent.mkdir(parents=True,exist_ok=True)
    json_output.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding="utf-8"); markdown_output.write_text(render_markdown(p),encoding="utf-8"); return p


def main(argv: list[str] | None = None) -> int:
    q=argparse.ArgumentParser(); q.add_argument("--canonical",type=Path,required=True); q.add_argument("--holdings",type=Path,default=Path("CURRENT_HOLDINGS.md")); q.add_argument("--funds",type=Path,default=Path("CURRENT_FUNDS.md")); q.add_argument("--capital",type=Path,default=Path("CURRENT_CAPITAL.json")); q.add_argument("--terminal-decisions",type=Path); q.add_argument("--hourly",type=Path); q.add_argument("--research-priority",type=Path); q.add_argument("--market-regime",type=Path); q.add_argument("--industry-regimes",type=Path); q.add_argument("--event-decision",type=Path); q.add_argument("--json-output",type=Path,required=True); q.add_argument("--markdown-output",type=Path,required=True); q.add_argument("--mode",default="HOURLY"); a=q.parse_args(argv)
    p=write_dashboard(canonical_path=a.canonical,holdings_path=a.holdings,funds_path=a.funds,capital_path=a.capital,terminal_decisions_path=a.terminal_decisions,hourly_path=a.hourly,research_priority_path=a.research_priority,market_regime_path=a.market_regime,industry_regimes_path=a.industry_regimes,event_decision_path=a.event_decision,json_output=a.json_output,markdown_output=a.markdown_output,mode=a.mode)
    print(f"investor_dashboard={p['mode']};snapshot={p['canonical_snapshot_id']};terminal_buy={p['decision_summary']['terminal_buy_count']};wait_price={p['decision_summary']['terminal_wait_price_count']};planned_cash={p['decision_summary']['planned_immediate_cash_cny']}"); return 0

if __name__ == "__main__": raise SystemExit(main())
