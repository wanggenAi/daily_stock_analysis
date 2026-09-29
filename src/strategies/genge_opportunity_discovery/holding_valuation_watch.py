"""Read-only holding valuation watch: explain discounted prices without inventing BUY.

This projection intentionally never generates executable lots, target orders, new
Formal authority or additional authorizations from previously consumed tranches.
It is displayed in the existing three-pillar investor report.
"""
from __future__ import annotations

from typing import Any, Mapping

CONTRACT = "GEN_GE_HOLDING_VALUATION_WATCH_V1"


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if n == n and abs(n) != float("inf") else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_holding_valuation_watch(
    dashboard: Mapping[str, Any], decision_center: Mapping[str, Any]
) -> dict[str, Any]:
    """Show what a single existing-market lot would mean; NEVER offer an order."""
    market = dashboard.get("market") or {}
    freshness = dashboard.get("freshness_contract") or {}
    plan = dashboard.get("capital_deployment") or {}
    published_date = str(dashboard.get("latest_trade_date") or "")
    source_current = bool(
        freshness.get("fresh") is True
        and published_date
        and str(freshness.get("canonical_latest_trade_date") or "") == published_date
        and str(freshness.get("market_as_of") or "") == published_date
        and str(market.get("as_of_date") or "") == published_date
    )
    profile_current = decision_center.get("deep_review_profile_current_for_runtime") is True
    source_rows = {
        str(row.get("code") or "").zfill(6): row
        for row in (dashboard.get("stock_portfolio") or {}).get("rows") or []
        if isinstance(row, Mapping)
    }
    stock_values = [
        _number(row.get("current_price")) * _number(row.get("quantity"))
        for row in source_rows.values()
        if (_number(row.get("current_price")) or 0) > 0
        and (_number(row.get("quantity")) or 0) > 0
    ]
    registered_stock_value = sum(stock_values)
    cash = _number(plan.get("available_cash_cny"))
    consumed = {
        str(row.get("code") or "").zfill(6)
        for row in (dashboard.get("execution_consumption_reconciliation") or {}).get("applied") or []
        if isinstance(row, Mapping) and (_number(row.get("consumed_shares")) or 0) > 0
    }
    rows = []
    for holding in (decision_center.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or []:
        if not isinstance(holding, Mapping):
            continue
        code = str(holding.get("code") or "").zfill(6)
        raw = source_rows.get(code)
        if not raw:
            continue
        price = _number(holding.get("current_price"))
        low = _number((holding.get("valuation_continuity") or {}).get("value_low"))
        if low is None:
            low = _number(raw.get("value_low"))
        neutral = _number(holding.get("neutral_value"))
        qty = _number(holding.get("quantity"))
        avg = _number(holding.get("average_cost"))
        if not all(v is not None and v > 0 for v in (price, low, neutral, qty, avg)):
            continue
        if price >= low or str(holding.get("valuation_confidence") or "") != "HIGH":
            continue
        blockers = []
        if not source_current:
            blockers.append("MARKET_OR_CANONICAL_EPOCH_UNVERIFIED")
        if not profile_current:
            blockers.append("DEEP_PROFILE_LINEAGE_NOT_CURRENT")
        if market.get("allow_new_buy") is not True:
            blockers.append("MARKET_NEW_BUY_DISABLED")
        if raw.get("holding_add_authorized") is not True:
            blockers.append("NO_CURRENT_FORMAL_HOLDING_ADD")
        if code in consumed:
            blockers.append("PRIOR_ADD_ALLOWANCE_CONSUMED")
        gates = (holding.get("deep_review") or {}).get("gates") or []
        unknown = [
            str(g.get("gate"))
            for g in gates
            if isinstance(g, Mapping) and g.get("status") != "PASS"
        ]
        if unknown:
            blockers.append("DEEP_GATES_NOT_ALL_PASS")
        # Every scenario uses a persisted EOD reference, not an executable quote.
        blockers.extend(("BROKER_CASH_UNVERIFIED_LIVE", "EXECUTION_QUOTE_NOT_LIVE"))
        lot = 100  # Standard Shanghai A-share illustrative purchase lot; never an order.
        scenario_cost = round(price * lot, 2)
        next_cost = round((qty * avg + scenario_cost) / (qty + lot), 4)
        rows.append({
            "code": code,
            "name": str(holding.get("name") or ""),
            "price_as_of": published_date,
            "price_evidence": "CANONICAL_EOD_NOT_LIVE",
            "reference_price": price,
            "model_value_low": low,
            "model_neutral_value": neutral,
            "valuation_confidence": "HIGH",
            "discount_to_model_low_pct": round((low - price) / low * 100, 2),
            "existing_shares_from_confirmed_snapshot": int(qty),
            "registered_stock_value_cny": round(registered_stock_value, 2),
            "existing_registered_stock_concentration_pct": (
                round(price * qty / registered_stock_value * 100, 2)
                if registered_stock_value > 0 else None
            ),
            "deep_gate_pass_count": sum(
                isinstance(g, Mapping) and g.get("status") == "PASS" for g in gates
            ),
            "deep_gate_unverified": unknown,
            "formal_action_unchanged": raw.get("formal_action") or "",
            "existing_add_allowance_consumed": code in consumed,
            "market_state": str(market.get("status") or "UNKNOWN"),
            "display_bucket": "VALUATION_WATCH_NOT_ACTIONABLE",
            "reason": "PRICE_BELOW_MODELED_LOWER_VALUE_BOUND",
            "non_authorized_scenario": {
                "kind": "ILLUSTRATIVE_100_SHARES_ONLY",
                "shares": lot,
                "assumed_price": price,
                "estimated_cash_cny_ex_fees": scenario_cost,
                "planning_cash_cny_as_of": plan.get("capital_as_of"),
                "planning_cash_cny": cash,
                "planning_cash_after_cny_ex_fees": (
                    round(cash - scenario_cost, 2) if cash is not None else None
                ),
                "estimated_new_total_shares": int(qty) + lot,
                "estimated_new_average_cost_ex_fees": next_cost,
                "loss_if_scenario_price_falls_another_10pct_cny": round(scenario_cost * .1, 2),
                "is_order": False,
                "authorized": False,
                "executable_shares": 0,
                "order_limit_price": None,
            },
            "blockers": blockers,
            "manual_recheck": [
                "CURRENT_SESSION_PRICE_AND_MARKET_REGIME",
                "LATEST_MATERIAL_FILINGS_AND_COMMODITY_RISKS",
                "CURRENT_CANONICAL_ADD_AUTHORITY_AND_PRIOR_CONSUMPTION",
                "ACTUAL_BROKER_SHARES_AND_AVAILABLE_CASH",
                "LIVE_QUOTE_LOT_AND_POSITION_EXPOSURE",
            ],
        })
    rows.sort(key=lambda row: (-row["discount_to_model_low_pct"], row["code"]))
    return {
        "contract_version": CONTRACT,
        "authority": "READ_ONLY_RESEARCH_SCENARIO",
        "source_epoch_verified": source_current,
        "deep_profile_lineage_verified": profile_current,
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id"),
        "market_as_of": published_date,
        "model_screen_rule": "HIGH_CONFIDENCE_PRICE_BELOW_MODEL_LOW_ONLY",
        "no_threshold_change": True,
        "no_auto_trade": True,
        "formal_action_recomputed": False,
        "buy_now": [],
        "executable_orders": [],
        "rows": rows,
    }
