"""Freshness-safe wrapper for the intraday execution-price overlay."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from . import investor_live_execution_overlay_core as _core
from .investor_live_execution_overlay_core import *  # noqa: F401,F403

_ORIGINAL_APPLY = _core.apply_live_execution_overlay


def _freshness_blocks_new_exposure(payload: Mapping[str, Any]) -> bool:
    freshness = payload.get("freshness_contract") or {}
    return (
        payload.get("formal_new_exposure_allowed") is False
        or freshness.get("status") == "STALE_UPSTREAM"
    )


def _reassert_freshness_fail_closed(payload: dict[str, Any]) -> None:
    """Prevent execution-price overlays from resurrecting stale BUY/ADD plans."""
    payload["formal_new_exposure_allowed"] = False

    market = payload.setdefault("market", {})
    market["allow_new_buy"] = False
    market["freshness_override"] = "STALE_UPSTREAM_FAIL_CLOSED"

    terminal = payload.setdefault("terminal_opportunities", {})
    for row in terminal.get("buy_now") or []:
        row["currently_actionable"] = False
        row["freshness_blocked"] = True
    for row in terminal.get("wait_price") or []:
        row["trigger_currently_usable"] = False
        row["freshness_blocked"] = True

    plan = payload.setdefault("capital_deployment", {})
    available_cash = float(plan.get("available_cash_cny") or 0.0)
    plan["status"] = "STALE_UPSTREAM_BLOCK_NEW_EXPOSURE"
    plan["deployment_budget_cny"] = 0.0
    plan["effective_max_deployment_ratio"] = 0.0
    plan["operations"] = []
    plan["planned_immediate_cash_cny"] = 0.0
    plan["cash_after_immediate_plan_cny"] = available_cash
    for row in plan.get("wait_price_reservations") or []:
        row["trigger_currently_usable"] = False
        row["freshness_blocked"] = True

    payload["final_operation_table"] = list(plan.get("wait_price_reservations") or [])
    if isinstance(payload.get("decision_summary"), dict):
        payload["decision_summary"]["planned_immediate_cash_cny"] = 0.0

    overlay = payload.setdefault("live_execution_overlay", {})
    overlay["freshness_blocks_new_exposure"] = True
    overlay["formal_new_exposure_allowed"] = False
    overlay["freshness_fail_closed_reasserted"] = True

    health = payload.setdefault("data_health", {})
    health["freshness_status"] = "STALE_UPSTREAM"
    health["formal_new_exposure_allowed"] = False

    payload["headline"] = (
        "数据代际=STALE_UPSTREAM；禁止新增仓位；"
        f"市场={market.get('status', 'UNKNOWN')}；盘中价仅用于展示/审计；计划立即投入≈¥0"
    )


def apply_live_execution_overlay(
    dashboard: Mapping[str, Any],
    hourly: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_minutes: int = _core.DEFAULT_MAX_QUOTE_AGE_MINUTES,
) -> dict[str, Any]:
    freshness_blocked = _freshness_blocks_new_exposure(dashboard)
    payload = _ORIGINAL_APPLY(
        dashboard,
        hourly,
        now=now,
        max_age_minutes=max_age_minutes,
    )
    if freshness_blocked:
        _reassert_freshness_fail_closed(payload)
    else:
        overlay = payload.setdefault("live_execution_overlay", {})
        overlay["freshness_blocks_new_exposure"] = False
        overlay["formal_new_exposure_allowed"] = True
    return payload


_core.apply_live_execution_overlay = apply_live_execution_overlay


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
