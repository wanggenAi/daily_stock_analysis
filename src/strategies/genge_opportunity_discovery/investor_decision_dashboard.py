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


def _refresh_stale_headline(payload: dict[str, Any]) -> None:
    """Rebuild the investor headline from the fail-closed payload state."""
    market = payload.get("market") or {}
    rows = (payload.get("stock_portfolio") or {}).get("rows") or []
    terminal = payload.get("terminal_opportunities") or {}
    plan = payload.get("capital_deployment") or {}
    urgent = sum(bool(_core._is_risk_reduction(row.get("formal_action"))) for row in rows)
    new_urgent = sum(
        bool(_core._is_risk_reduction(row.get("formal_action"))) and row.get("action_lifecycle") == "NEW"
        for row in rows
    )
    planned_cash = float(plan.get("planned_immediate_cash_cny") or 0.0)
    payload["headline"] = (
        "数据代际=STALE_UPSTREAM；禁止直接执行任何Formal动作；"
        f"市场={market.get('status','UNKNOWN')}；"
        f"持仓Formal可用={payload.get('formal_holding_actions_currently_usable') is True}；"
        f"持仓减仓/退出目标(仅审计)={urgent}；本轮新增减仓/退出(仅审计)={new_urgent}；"
        f"新股正式BUY={len(terminal.get('buy_now') or [])}；"
        f"等价格={len(terminal.get('wait_price') or [])}；计划立即投入≈¥{planned_cash:.0f}"
    )


def _fail_closed_new_exposure(payload: dict[str, Any], freshness: Mapping[str, Any]) -> None:
    """Fail closed every executable action when the authoritative generation is stale.

    Frozen Formal actions remain visible as historical/audit truth, but stale prices
    or stale market context must never be presented as directly executable.  This is
    intentionally stricter than merely blocking BUY/ADD: a stale REDUCE/EXIT can be
    just as harmful when the market has moved materially since the last completed
    session.
    """
    payload["freshness_contract"] = dict(freshness)
    payload["formal_new_exposure_allowed"] = False
    payload["formal_holding_actions_currently_usable"] = False

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

    portfolio = payload.setdefault("stock_portfolio", {})
    portfolio["status"] = "STALE_UPSTREAM_REVIEW_ONLY"
    for row in portfolio.get("rows") or []:
        row["new_exposure_currently_usable"] = False
        row["formal_action_currently_usable"] = False
        if row.get("action_authority") == "FORMAL" or row.get("formal_action"):
            row["action_authority"] = "FORMAL_STALE_REVIEW_ONLY"
        row["execution_feasibility"] = None
        row["holding_add_authorized"] = False
        action_text = str(row.get("investor_action") or "")
        stale_suffix = "数据代际陈旧，Formal动作仅供审计/研究，禁止直接执行"
        if stale_suffix not in action_text:
            row["investor_action"] = f"{action_text}；{stale_suffix}" if action_text else stale_suffix

    plan = payload.setdefault("capital_deployment", {})
    available_cash = float(plan.get("available_cash_cny") or 0.0)
    plan["status"] = "STALE_UPSTREAM_BLOCK_ALL_EXECUTION"
    plan["deployment_budget_cny"] = 0.0
    plan["effective_max_deployment_ratio"] = 0.0
    plan["operations"] = []
    plan["planned_immediate_cash_cny"] = 0.0
    plan["cash_after_immediate_plan_cny"] = available_cash
    for row in plan.get("wait_price_reservations") or []:
        row["trigger_currently_usable"] = False
        row["freshness_blocked"] = True

    # Any row in this table is intentionally an execution surface.  Keep the
    # underlying Formal actions in stock_portfolio for audit, but publish no
    # executable rows until the generation is current again.
    payload["final_operation_table"] = []

    summary = payload.setdefault("decision_summary", {})
    summary["planned_immediate_cash_cny"] = 0.0
    summary["formal_holding_actions_currently_usable"] = False
    health = payload.setdefault("data_health", {})
    health["freshness_status"] = "STALE_UPSTREAM"
    health["freshness_reasons"] = list(freshness.get("reasons") or [])
    health["formal_new_exposure_allowed"] = False
    health["formal_holding_actions_currently_usable"] = False
    _refresh_stale_headline(payload)


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
            f"> 所有直接执行动作已 fail-closed；Formal 决策仅保留作审计/研究显示。原因：`{reasons}`\n\n"
        )
        return banner + text
    return text


_core.build_dashboard = build_dashboard
_core.render_markdown = render_markdown


def main(argv: list[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
