"""Freshness-safe investor dashboard wrapper around the frozen dashboard core."""
from __future__ import annotations

import inspect
from typing import Any, Mapping

from . import investor_decision_dashboard_core as _core
from .investor_decision_dashboard_core import *  # noqa: F401,F403
from .generation_freshness import evaluate_generation_freshness

# Preserve the historical module's private-helper import surface. Several
# execution overlays and regression tests intentionally import single-underscore
# helpers from this path. ``import *`` omits them, so mirror every private core
# helper without overwriting wrapper-owned names.
for _compat_name, _compat_value in vars(_core).items():
    if _compat_name.startswith("_") and not _compat_name.startswith("__"):
        globals().setdefault(_compat_name, _compat_value)
del _compat_name, _compat_value

_ORIGINAL_BUILD = _core.build_dashboard
_ORIGINAL_RENDER = _core.render_markdown


def _fail_closed_new_exposure(payload: dict[str, Any], freshness: Mapping[str, Any]) -> None:
    payload["freshness_contract"] = dict(freshness)
    payload["formal_new_exposure_allowed"] = False
    payload["headline"] = "数据代际=STALE_UPSTREAM；禁止新增仓位；" + str(payload.get("headline") or "")

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

    for row in payload.get("stock_portfolio", {}).get("rows") or []:
        row["new_exposure_currently_usable"] = False
        if row.get("holding_add_authorized") or str(row.get("formal_action") or "").upper() in {"ADD", "BUY"}:
            row["investor_action"] = str(row.get("investor_action") or "") + "；数据代际陈旧，禁止新增仓位"

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

    payload["final_operation_table"] = [
        row for row in payload.get("final_operation_table") or []
        if str(row.get("action") or "").upper() not in {"BUY", "ADD"}
    ]
    summary = payload.setdefault("decision_summary", {})
    summary["planned_immediate_cash_cny"] = 0.0
    health = payload.setdefault("data_health", {})
    health["freshness_status"] = "STALE_UPSTREAM"
    health["freshness_reasons"] = list(freshness.get("reasons") or [])
    health["formal_new_exposure_allowed"] = False


def build_dashboard(*args: Any, **kwargs: Any) -> dict[str, Any]:
    bound = inspect.signature(_ORIGINAL_BUILD).bind_partial(*args, **kwargs)
    canonical = bound.arguments.get("canonical") or {}
    market_regime = bound.arguments.get("market_regime") or {}
    generated_at = bound.arguments.get("generated_at")
    payload = _ORIGINAL_BUILD(*args, **kwargs)
    freshness = evaluate_generation_freshness(
        canonical,
        market_regime=market_regime,
        evaluated_at=generated_at,
        strict_missing_metadata=False,
    )
    payload["freshness_contract"] = freshness
    payload["formal_new_exposure_allowed"] = freshness.get("formal_new_exposure_allowed") is True
    health = payload.setdefault("data_health", {})
    health["freshness_status"] = freshness.get("status")
    health["freshness_reasons"] = list(freshness.get("reasons") or [])
    health["formal_new_exposure_allowed"] = payload["formal_new_exposure_allowed"]
    if freshness.get("status") == "STALE_UPSTREAM":
        _fail_closed_new_exposure(payload, freshness)
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    text = _ORIGINAL_RENDER(payload)
    freshness = payload.get("freshness_contract") or {}
    if freshness.get("status") == "STALE_UPSTREAM":
        reasons = ", ".join(freshness.get("reasons") or []) or "UNKNOWN"
        banner = (
            "# ⚠️ 数据代际陈旧：STALE_UPSTREAM\n\n"
            f"> 新增仓位已 fail-closed；Formal 决策仅保留作审计/研究显示。原因：`{reasons}`\n\n"
        )
        return banner + text
    return text


_core.build_dashboard = build_dashboard
_core.render_markdown = render_markdown


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
