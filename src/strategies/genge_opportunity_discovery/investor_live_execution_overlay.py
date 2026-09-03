"""Overlay fresh intraday quotes onto the investor dashboard without changing authority.

Canonical remains the only source of Formal holding actions and Candidate Terminal
Review remains the only terminal BUY/WAIT_PRICE/REJECT source.  This module only
replaces *display/execution reference prices* with bounded-fresh hourly quotes,
recomputes P/L and lot sizing, and becomes more conservative when a fresh quote
is above the price that was authorized by the frozen decision evidence.

It never recomputes or promotes a Formal Action and never places orders.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import (
    _num,
    _plan,
    render_markdown,
)

OVERLAY_VERSION = "GEN_GE_INVESTOR_LIVE_EXECUTION_OVERLAY_V1"
DEFAULT_MAX_QUOTE_AGE_MINUTES = 120


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _quote_map(
    hourly: Mapping[str, Any], *, now: datetime, max_age_minutes: int
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    max_age_seconds = max(0, int(max_age_minutes)) * 60
    now_utc = now.astimezone(timezone.utc)
    for raw in hourly.get("rows") or []:
        code = str(raw.get("code") or "").strip().zfill(6)
        price = _num(raw.get("latest_price"))
        observed = _parse_dt(raw.get("latest_price_observed_at"))
        if not code or price is None or price <= 0 or observed is None:
            continue
        if str(raw.get("latest_price_status") or "").upper() != "OK":
            continue
        age = (now_utc - observed).total_seconds()
        if age < -300 or age > max_age_seconds:
            continue
        result[code] = {
            "price": price,
            "observed_at": raw.get("latest_price_observed_at") or "",
            "provider": raw.get("latest_price_provider") or "",
            "age_seconds": max(0, int(age)),
        }
    return result


def _overlay_price(row: dict[str, Any], quote: Mapping[str, Any], *, original_key: str) -> None:
    original = _num(row.get("current_price"))
    row[original_key] = original
    row["current_price"] = quote["price"]
    row["price_source"] = "HOURLY_FRESH_EXECUTION_QUOTE"
    row["price_observed_at"] = quote["observed_at"]
    row["price_provider"] = quote["provider"]
    row["price_age_seconds"] = quote["age_seconds"]


def apply_live_execution_overlay(
    dashboard: Mapping[str, Any],
    hourly: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
) -> dict[str, Any]:
    payload = copy.deepcopy(dict(dashboard))
    if payload.get("no_auto_trade") is not True:
        raise ValueError("dashboard lost no-auto-trade contract")
    if hourly.get("formal_action_recomputed") is not False:
        raise ValueError("hourly overlay must not recompute Formal Action")
    if hourly.get("overlay_may_overwrite_formal_action") is not False:
        raise ValueError("hourly overlay may not overwrite Formal Action")
    canonical_id = str(payload.get("canonical_snapshot_id") or "")
    if canonical_id and str(hourly.get("canonical_snapshot_id") or "") != canonical_id:
        raise ValueError("hourly quote overlay canonical snapshot mismatch")

    now = now or datetime.now(timezone.utc)
    quotes = _quote_map(hourly, now=now, max_age_minutes=max_age_minutes)
    applied: list[str] = []

    holding_rows = payload.get("stock_portfolio", {}).get("rows") or []
    for row in holding_rows:
        code = str(row.get("code") or "").strip().zfill(6)
        quote = quotes.get(code)
        if not quote:
            row.setdefault("price_source", "CANONICAL_FROZEN_PRICE")
            continue
        _overlay_price(row, quote, original_key="canonical_price")
        cost = _num(row.get("average_cost"))
        if cost not in {None, 0}:
            row["pnl_pct"] = round((float(quote["price"]) / float(cost) - 1) * 100, 2)
        applied.append(code)

    terminal = payload.get("terminal_opportunities") or {}
    for bucket in ("buy_now", "wait_price"):
        for row in terminal.get(bucket) or []:
            code = str(row.get("code") or "").strip().zfill(6)
            quote = quotes.get(code)
            if quote:
                _overlay_price(row, quote, original_key="terminal_reference_price")
                applied.append(code)
            else:
                row.setdefault("price_source", "TERMINAL_FROZEN_PRICE")

    # Re-plan with the same authority and cash rules, but never pay more for a
    # holding ADD than the price observed by the frozen Canonical decision.
    planning_holdings = copy.deepcopy(holding_rows)
    for row in planning_holdings:
        if str(row.get("formal_action") or "").upper() not in {"ADD", "BUY"}:
            continue
        live = _num(row.get("current_price"))
        frozen = _num(row.get("canonical_price"))
        if live is not None and frozen is not None:
            row["current_price"] = min(live, frozen)

    existing_plan = payload.get("capital_deployment") or {}
    capital = {
        "status": existing_plan.get("status") or "UNAVAILABLE",
        "planning_cash_cny": _num(existing_plan.get("available_cash_cny")) or 0.0,
        "as_of": existing_plan.get("capital_as_of") or "",
        "planner": dict(existing_plan.get("planner_config") or {}),
        "no_auto_trade": True,
    }
    market = payload.get("market") or {}
    new_plan = _plan(capital, market, planning_holdings, terminal)

    live_by_code = {
        str(row.get("code") or "").zfill(6): row for row in holding_rows
    }
    terminal_by_code = {
        str(row.get("code") or "").zfill(6): row
        for bucket in ("buy_now", "wait_price")
        for row in terminal.get(bucket) or []
    }
    for op in new_plan.get("operations") or []:
        code = str(op.get("code") or "").zfill(6)
        source_row = live_by_code.get(code) if op.get("source") == "AUTHORIZED_CANONICAL_HOLDING_ACTION" else terminal_by_code.get(code)
        live = _num((source_row or {}).get("current_price"))
        op["live_market_price"] = live
        op["price_observed_at"] = (source_row or {}).get("price_observed_at") or ""
        op["price_provider"] = (source_row or {}).get("price_provider") or ""
        if live is not None and op.get("first_entry_max_price") is not None and live > float(op["first_entry_max_price"]):
            op["immediate_execution_eligible"] = False
            op["execution_note"] = "LIVE_PRICE_ABOVE_AUTHORIZED_LIMIT_USE_LIMIT_ORDER_ONLY"
            op["action"] = f"{op.get('action')}_LIMIT"
        else:
            op["execution_note"] = "LIVE_PRICE_WITHIN_AUTHORIZED_LIMIT"

    payload["capital_deployment"] = new_plan
    payload["final_operation_table"] = list(new_plan.get("operations") or []) + list(new_plan.get("wait_price_reservations") or [])
    if isinstance(payload.get("decision_summary"), dict):
        payload["decision_summary"]["planned_immediate_cash_cny"] = new_plan.get("planned_immediate_cash_cny", 0)

    unique_applied = sorted(set(applied))
    latest_observed = max(
        (str(q.get("observed_at") or "") for q in quotes.values()), default=""
    )
    payload["live_execution_overlay"] = {
        "version": OVERLAY_VERSION,
        "available": bool(quotes),
        "eligible_quote_count": len(quotes),
        "applied_code_count": len(unique_applied),
        "applied_codes": unique_applied,
        "latest_quote_observed_at": latest_observed,
        "max_quote_age_minutes": int(max_age_minutes),
        "canonical_snapshot_match": True,
        "formal_action_recomputed": False,
        "formal_action_mutation_allowed": False,
        "quote_may_only_change_display_and_execution_reference": True,
        "no_auto_trade": True,
    }
    payload["headline"] = (
        f"市场={market.get('status','UNKNOWN')}；持仓减仓/退出="
        f"{sum(str(x.get('formal_action') or '').upper() in {'EXIT','SELL','REDUCE','REDUCE_25','REDUCE_50'} for x in holding_rows)}；"
        f"新股正式BUY={len(terminal.get('buy_now') or [])}；等价格={len(terminal.get('wait_price') or [])}；"
        f"计划立即投入≈¥{new_plan.get('planned_immediate_cash_cny',0):.0f}；盘中价覆盖={len(unique_applied)}"
    )
    return payload


def render_live_markdown(payload: Mapping[str, Any]) -> str:
    text = render_markdown(payload)
    overlay = payload.get("live_execution_overlay") or {}
    note = (
        f"- 盘中执行价覆盖：**{overlay.get('applied_code_count', 0)}只**；"
        f"最新行情时间：**{overlay.get('latest_quote_observed_at') or '—'}**；"
        "正式动作仍来自冻结 Canonical，盘中价只用于当前盈亏与人工下单价格/股数。\n\n"
    )
    marker = "## 2. 我的持仓怎么办"
    return text.replace(marker, note + marker, 1) if marker in text else text + "\n" + note


def write_overlay(
    *, dashboard_json: Path, hourly_json: Path, markdown_output: Path,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
) -> dict[str, Any]:
    dashboard = json.loads(dashboard_json.read_text(encoding="utf-8"))
    hourly = json.loads(hourly_json.read_text(encoding="utf-8"))
    payload = apply_live_execution_overlay(
        dashboard, hourly, max_age_minutes=max_age_minutes
    )
    dashboard_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output.write_text(render_live_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--hourly-json", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--max-age-minutes", type=int, default=DEFAULT_MAX_QUOTE_AGE_MINUTES)
    args = parser.parse_args(argv)
    payload = write_overlay(
        dashboard_json=args.dashboard_json,
        hourly_json=args.hourly_json,
        markdown_output=args.markdown_output,
        max_age_minutes=args.max_age_minutes,
    )
    overlay = payload["live_execution_overlay"]
    print(
        f"investor_live_execution_overlay=OK;quotes={overlay['eligible_quote_count']};"
        f"applied={overlay['applied_code_count']};formal_action_recomputed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
