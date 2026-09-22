"""Refresh investor execution prices directly from public intraday quotes.

This is deliberately separate from the hourly research overlay. Research lineage
remains frozen and authoritative; market quotes are ephemeral execution evidence.
The module reads the current investor dashboard, fetches only its current holding
and terminal BUY/WAIT_PRICE universe, then reuses the live-execution overlay to
update display/execution prices without changing Formal or Terminal authority.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from datetime import datetime, time as clock_time, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

from src.strategies.genge_opportunity_discovery.hourly_deep_overlay import (
    Quote,
    fetch_tencent_quotes,
)
from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import _num
from src.strategies.genge_opportunity_discovery.investor_live_execution_overlay import (
    apply_live_execution_overlay,
    render_live_markdown,
)

BEIJING = ZoneInfo("Asia/Shanghai")
DIRECT_OVERLAY_VERSION = "GEN_GE_DIRECT_EXECUTION_QUOTE_OVERLAY_V1"
DIRECT_PRICE_SOURCE = "DIRECT_PUBLIC_INTRADAY_EXECUTION_QUOTE"
DEFAULT_MAX_QUOTE_AGE_MINUTES = 15


def market_session_state(now: datetime) -> str:
    local = now.astimezone(BEIJING)
    if local.weekday() >= 5:
        return "CLOSED"
    current = local.time().replace(tzinfo=None)
    if clock_time(9, 30) <= current <= clock_time(11, 30):
        return "ACTIVE_MORNING"
    if clock_time(13, 0) <= current <= clock_time(15, 0):
        return "ACTIVE_AFTERNOON"
    if clock_time(11, 30) < current < clock_time(13, 0):
        return "LUNCH_BREAK"
    return "CLOSED"


def _code(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    return text[-6:].zfill(6) if text else ""


def execution_codes(dashboard: Mapping[str, Any]) -> list[str]:
    codes: set[str] = set()
    for row in dashboard.get("stock_portfolio", {}).get("rows") or []:
        code = _code(row.get("code"))
        if code:
            codes.add(code)
    terminal = dashboard.get("terminal_opportunities") or {}
    for bucket in ("buy_now", "wait_price"):
        for row in terminal.get(bucket) or []:
            code = _code(row.get("code"))
            if code:
                codes.add(code)
    return sorted(codes)


def _reset_to_frozen_prices(dashboard: Mapping[str, Any]) -> dict[str, Any]:
    """Remove an older execution overlay before applying the next quote snapshot."""
    payload = copy.deepcopy(dict(dashboard))
    for row in payload.get("stock_portfolio", {}).get("rows") or []:
        frozen = _num(row.get("canonical_price"))
        if frozen is not None:
            row["current_price"] = frozen
            cost = _num(row.get("average_cost"))
            if cost not in {None, 0}:
                row["pnl_pct"] = round((frozen / cost - 1.0) * 100.0, 2)
        row["price_source"] = "CANONICAL_FROZEN_PRICE"
        row.pop("price_observed_at", None)
        row.pop("price_provider", None)
        row.pop("price_age_seconds", None)

    terminal = payload.get("terminal_opportunities") or {}
    for bucket in ("buy_now", "wait_price"):
        for row in terminal.get(bucket) or []:
            frozen = _num(row.get("terminal_reference_price"))
            if frozen is not None:
                row["current_price"] = frozen
            row["price_source"] = "TERMINAL_FROZEN_PRICE"
            row.pop("price_observed_at", None)
            row.pop("price_provider", None)
            row.pop("price_age_seconds", None)
    payload.pop("live_execution_overlay", None)
    return payload


def fetch_quotes_with_retry(
    codes: Iterable[str],
    *,
    attempts: int = 3,
    provider: Callable[[Iterable[str]], Mapping[str, Quote]] = fetch_tencent_quotes,
) -> dict[str, Quote]:
    ordered = list(dict.fromkeys(codes))
    if not ordered:
        return {}
    best: dict[str, Quote] = {}
    for attempt in range(max(1, int(attempts))):
        snapshot = dict(provider(ordered))
        for code, quote in snapshot.items():
            previous = best.get(code)
            if quote.status == "OK" or previous is None:
                best[code] = quote
        if all(best.get(code) is not None and best[code].status == "OK" for code in ordered):
            break
        if attempt + 1 < attempts:
            time.sleep(1)
    return best


def _synthetic_quote_payload(
    dashboard: Mapping[str, Any], quotes: Mapping[str, Quote]
) -> dict[str, Any]:
    return {
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id"),
        "canonical_source_run_id": dashboard.get("canonical_source_run_id"),
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "rows": [
            {
                "code": code,
                "latest_price": quote.price,
                "latest_price_status": quote.status,
                "latest_price_observed_at": quote.observed_at,
                "latest_price_provider": quote.provider,
            }
            for code, quote in sorted(quotes.items())
        ],
    }


def _zero_immediate_deployment(payload: dict[str, Any], note: str) -> None:
    plan = payload.get("capital_deployment") or {}
    for op in plan.get("operations") or []:
        op["immediate_execution_eligible"] = False
        op["execution_note"] = note
    plan["planned_immediate_cash_cny"] = 0.0
    available = _num(plan.get("available_cash_cny"))
    if available is not None:
        plan["cash_after_immediate_plan_cny"] = available
    payload["capital_deployment"] = plan
    payload["final_operation_table"] = list(plan.get("operations") or []) + list(
        plan.get("wait_price_reservations") or []
    )
    if isinstance(payload.get("decision_summary"), dict):
        payload["decision_summary"]["planned_immediate_cash_cny"] = 0.0


def _existing_execution_overlay_is_fresh(
    dashboard: Mapping[str, Any], *, now: datetime, max_age_minutes: int
) -> bool:
    overlay = dashboard.get("live_execution_overlay") or {}
    if int(overlay.get("applied_code_count") or 0) <= 0:
        return False
    if overlay.get("canonical_snapshot_match") is False:
        return False
    observed_raw = str(overlay.get("latest_quote_observed_at") or "").strip()
    if not observed_raw:
        return False
    try:
        observed = datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if observed.tzinfo is None:
        return False
    age_seconds = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    return 0 <= age_seconds <= max(0, int(max_age_minutes)) * 60


def _headline(payload: Mapping[str, Any]) -> str:
    market = payload.get("market") or {}
    terminal = payload.get("terminal_opportunities") or {}
    plan = payload.get("capital_deployment") or {}
    holding_rows = payload.get("stock_portfolio", {}).get("rows") or []
    overlay = payload.get("live_execution_overlay") or {}
    return (
        f"市场={market.get('status','UNKNOWN')}；持仓减仓/退出="
        f"{sum(str(x.get('formal_action') or '').upper() in {'EXIT','SELL','REDUCE','REDUCE_25','REDUCE_50'} for x in holding_rows)}；"
        f"新股正式BUY={len(terminal.get('buy_now') or [])}；等价格={len(terminal.get('wait_price') or [])}；"
        f"计划立即投入≈¥{(_num(plan.get('planned_immediate_cash_cny')) or 0):.0f}；"
        f"盘中价覆盖={overlay.get('applied_code_count',0)}/{overlay.get('expected_code_count',0)}"
    )


def apply_direct_execution_quote_overlay(
    dashboard: Mapping[str, Any],
    *,
    quote_provider: Callable[[Iterable[str]], Mapping[str, Quote]] = fetch_tencent_quotes,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
    retry_attempts: int = 3,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    session = market_session_state(now)
    active = session.startswith("ACTIVE_")
    if not active and _existing_execution_overlay_is_fresh(
        dashboard, now=now, max_age_minutes=max_age_minutes
    ):
        payload = copy.deepcopy(dict(dashboard))
        before_actions = {
            _code(row.get("code")): row.get("formal_action")
            for row in payload.get("stock_portfolio", {}).get("rows") or []
        }
        _zero_immediate_deployment(payload, "MARKET_NOT_IN_CONTINUOUS_SESSION")
        after_actions = {
            _code(row.get("code")): row.get("formal_action")
            for row in payload.get("stock_portfolio", {}).get("rows") or []
        }
        if before_actions != after_actions:
            raise ValueError("off-session quote preservation mutated Formal Actions")
        overlay = payload.setdefault("live_execution_overlay", {})
        overlay.update(
            {
                "market_session_state": session,
                "market_session_active": False,
                "market_data_status": "OFF_SESSION",
                "quote_refresh_mode": "PRESERVE_FRESH_EXISTING_OFF_SESSION",
                "formal_action_recomputed": False,
                "formal_action_mutation_allowed": False,
                "quote_may_only_change_display_and_execution_reference": True,
                "missing_quote_blocks_immediate_execution": True,
                "preserved_fresh_overlay_off_session": True,
                "no_auto_trade": True,
                "refreshed_at": now.astimezone(timezone.utc).isoformat(),
                "refreshed_at_beijing": now.astimezone(BEIJING).isoformat(),
            }
        )
        payload["headline"] = _headline(payload)
        return payload

    baseline = _reset_to_frozen_prices(dashboard)
    before_actions = {
        _code(row.get("code")): row.get("formal_action")
        for row in baseline.get("stock_portfolio", {}).get("rows") or []
    }
    codes = execution_codes(baseline)
    quotes = fetch_quotes_with_retry(
        codes, attempts=retry_attempts, provider=quote_provider
    )
    payload = apply_live_execution_overlay(
        baseline,
        _synthetic_quote_payload(baseline, quotes),
        now=now,
        max_age_minutes=max_age_minutes,
    )

    after_actions = {
        _code(row.get("code")): row.get("formal_action")
        for row in payload.get("stock_portfolio", {}).get("rows") or []
    }
    if before_actions != after_actions:
        raise ValueError("direct execution quote overlay mutated Formal Actions")

    overlay = payload.get("live_execution_overlay") or {}
    applied_codes = set(overlay.get("applied_codes") or [])
    for row in payload.get("stock_portfolio", {}).get("rows") or []:
        if _code(row.get("code")) in applied_codes:
            row["price_source"] = DIRECT_PRICE_SOURCE
    terminal = payload.get("terminal_opportunities") or {}
    for bucket in ("buy_now", "wait_price"):
        for row in terminal.get(bucket) or []:
            if _code(row.get("code")) in applied_codes:
                row["price_source"] = DIRECT_PRICE_SOURCE

    if not active:
        _zero_immediate_deployment(payload, "MARKET_NOT_IN_CONTINUOUS_SESSION")

    overlay.update(
        {
            "version": DIRECT_OVERLAY_VERSION,
            "source": DIRECT_PRICE_SOURCE,
            "quote_refresh_mode": "DIRECT_DASHBOARD_EXECUTION_UNIVERSE",
            "market_session_state": session,
            "market_session_active": active,
            "market_data_status": (
                overlay.get("market_data_status") if active else "OFF_SESSION"
            ),
            "retry_attempts": max(1, int(retry_attempts)),
            "formal_action_recomputed": False,
            "formal_action_mutation_allowed": False,
            "quote_may_only_change_display_and_execution_reference": True,
            "missing_quote_blocks_immediate_execution": True,
            "no_auto_trade": True,
            "refreshed_at": now.astimezone(timezone.utc).isoformat(),
            "refreshed_at_beijing": now.astimezone(BEIJING).isoformat(),
        }
    )
    payload["live_execution_overlay"] = overlay

    payload["headline"] = _headline(payload)
    return payload


def write_direct_overlay(
    *,
    dashboard_json: Path,
    markdown_output: Path,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
    retry_attempts: int = 3,
) -> dict[str, Any]:
    dashboard = json.loads(dashboard_json.read_text(encoding="utf-8"))
    payload = apply_direct_execution_quote_overlay(
        dashboard,
        max_age_minutes=max_age_minutes,
        retry_attempts=retry_attempts,
    )
    dashboard_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown_output.write_text(render_live_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument(
        "--max-age-minutes", type=int, default=DEFAULT_MAX_QUOTE_AGE_MINUTES
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    args = parser.parse_args(argv)
    payload = write_direct_overlay(
        dashboard_json=args.dashboard_json,
        markdown_output=args.markdown_output,
        max_age_minutes=args.max_age_minutes,
        retry_attempts=args.retry_attempts,
    )
    overlay = payload.get("live_execution_overlay") or {}
    print(
        "investor_direct_execution_quote_overlay=OK;"
        f"session={overlay.get('market_session_state')};"
        f"coverage={overlay.get('applied_code_count',0)}/{overlay.get('expected_code_count',0)};"
        f"status={overlay.get('market_data_status')};formal_action_recomputed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
