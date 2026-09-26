"""Read-only P0 investor V4 presentation projection; no trading authority."""
from __future__ import annotations

from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_INVESTOR_PRESENTATION_V4_P0"
CANONICAL_SOURCE = "FINALIZED_CANONICAL_ONLY"
NO_AUTO_TRADE = True


def _obj(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(v) for v in value if isinstance(v, Mapping)] if isinstance(value, list) else []


def project_v4_p0(
    dashboard: Mapping[str, Any],
    decision_center: Mapping[str, Any] | None = None,
    era_radar: Mapping[str, Any] | None = None,
    *,
    confirmed_funds_status: str = "UNVERIFIED",
) -> dict[str, Any]:
    """Map only known persisted presentation facts; unknown data never grants action.

    This P0 projection deliberately has *no* executable order table. P1 must
    integrate broker-fresh quotes, live authority and lot/cash eligibility before
    introducing executable rows.
    """
    if dashboard.get("no_auto_trade") is not True:
        raise ValueError("dashboard must forbid automatic orders")
    if dashboard.get("formal_action_source") != CANONICAL_SOURCE:
        raise ValueError("only finalized Canonical may supply formal actions")
    if dashboard.get("formal_action_recomputed") is not False:
        raise ValueError("projection cannot recompute Formal authority")
    center = _obj(decision_center)
    radar = _obj(era_radar)
    if center and (center.get("no_auto_trade") is not True
                   or center.get("formal_action_source") != CANONICAL_SOURCE
                   or center.get("formal_action_recomputed") is not False):
        raise ValueError("decision center must preserve Canonical authority")
    if radar and (radar.get("no_auto_trade") is not True
                  or radar.get("formal_trading_authority") is not False):
        raise ValueError("trend evidence must remain research only")

    market = _obj(dashboard.get("market"))
    freshness = _obj(dashboard.get("freshness_contract"))
    portfolio = _obj(dashboard.get("stock_portfolio"))
    terminal = _obj(dashboard.get("terminal_opportunities"))
    capital = _obj(dashboard.get("capital_deployment"))
    holdings = []
    for row in _rows(portfolio.get("rows")):
        lifecycle = str(row.get("action_lifecycle") or "UNKNOWN")
        # Formal source alone is NOT execution permission. Retain the recorded
        # action for context, and make its presentation permission explicit.
        formal_display = (dashboard.get("formal_holding_actions_currently_usable") is True
                          and row.get("formal_action_currently_usable") is True
                          and row.get("action_authority") == "FORMAL")
        holdings.append({
            "code": row.get("code"), "name": row.get("name"),
            "quantity": row.get("quantity"), "cost": row.get("average_cost"),
            "reference_price": row.get("current_price"),
            "reference_price_as_of": None,  # P1: validated quote lineage required
            "value_range": [row.get("value_low"), row.get("value_high")],
            "valuation_confidence": row.get("valuation_confidence") or "UNKNOWN",
            "recorded_action": row.get("formal_action") if formal_display else None,
            "recorded_action_lifecycle": lifecycle,
            "action_presentation_status": "RECORDED_NOT_EXECUTABLE" if formal_display else "RESEARCH_ONLY",
            "executable_shares": 0,  # Unknown current quote/broker evidence => fail closed
            "reason": "P0_NO_FRESH_EXECUTION_AUTHORITY",
        })
    # Never pass through upstream buy_now as a home-page buy merely because the
    # upstream report calls it buy_now. P1/P2 must verify the entire authority
    # and broker-price conjunction on the actual execution date.
    report_date = dashboard.get("latest_trade_date")
    center_date = center.get("latest_trade_date") if center else None
    lineage_matches = (not center or (
        center.get("canonical_snapshot_id") == dashboard.get("canonical_snapshot_id")
        and center_date == report_date))
    return {
        "contract_version": CONTRACT_VERSION,
        "projection_only": True,
        "no_auto_trade": NO_AUTO_TRADE,
        "formal_action_source": CANONICAL_SOURCE,
        "formal_action_recomputed": False,
        "generated_at": dashboard.get("generated_at"),
        "feeds": {
            "market": {"as_of": market.get("as_of_date") or report_date,
                       "scope": market.get("context_scope") or "UNKNOWN",
                       "freshness": freshness.get("status") or "UNKNOWN",
                       "source": "dashboard.market",
                       "fallback": "DISPLAY_ONLY_BLOCK_EXECUTION"},
            "canonical": {"as_of": report_date, "snapshot_id": dashboard.get("canonical_snapshot_id"),
                          "freshness": freshness.get("status") or "UNKNOWN",
                          "source": "dashboard canonical lineage",
                          "fallback": "NO_NEW_EXPOSURE"},
            "holdings": {"source": "user-confirmed holdings + dashboard reconciliation",
                         "as_of": None, "freshness": "BROKER_AS_OF_NOT_VALIDATED",
                         "fallback": "DISPLAY_ONLY"},
            "funds": {"source": "user-confirmed funds",
                      "as_of": None, "freshness": confirmed_funds_status,
                      "fallback": "LATEST_HOLDINGS_NOT_PERSISTED"},
            "trends": {"source": "era_radar", "as_of": radar.get("research_as_of"),
                       "freshness": "RESEARCH_ONLY" if radar else "MISSING",
                       "fallback": "NO_TRADE_AUTHORITY"},
        },
        "lineage_matches": lineage_matches,
        "market_status": market.get("status") or "UNKNOWN",
        "holdings": holdings,
        "funds_status": confirmed_funds_status,
        "formal_buy_now": [], "formal_wait_price": [],  # P0 has no execution proof
        "upstream_terminal_counts_audit_only": {
            "buy_now": len(_rows(terminal.get("buy_now"))),
            "wait_price": len(_rows(terminal.get("wait_price"))),
        },
        "trends_research_only": _rows(radar.get("trends")),
        "planning_cash_cny": capital.get("available_cash_cny"),
        "planned_immediate_cash_cny": 0,
        "action_status": "NO_EXECUTABLE_ACTION_P0_UNVERIFIED",
        "authority_blockers": ["P0_NO_EXECUTION_PROOF"] + ([] if lineage_matches else ["CROSS_FEED_LINEAGE_MISMATCH"]),
        "source_links": {
            "dashboard": "data/investor_decision_dashboard/latest.json",
            "decision_center": "data/decision_center/latest.json",
            "era_radar": "data/era_radar/latest.json",
        },
    }
