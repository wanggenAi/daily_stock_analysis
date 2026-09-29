"""Regression checks for valuation-watch explanations without permission escalation."""
from copy import deepcopy

from src.strategies.genge_opportunity_discovery.holding_valuation_watch import (
    build_holding_valuation_watch,
)
from src.strategies.genge_opportunity_discovery.three_pillar_decision_center_runtime import (
    build_runtime_decision_center,
    render_runtime_markdown,
)


def sample():
    dashboard = {
        "no_auto_trade": True,
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "latest_trade_date": "2026-09-28",
        "canonical_snapshot_id": "snap-1",
        "market": {"status": "RED", "allow_new_buy": False, "as_of_date": "2026-09-28"},
        "freshness_contract": {
            "fresh": True, "canonical_latest_trade_date": "2026-09-28",
            "market_as_of": "2026-09-28",
        },
        "stock_portfolio": {"rows": [
            {
                "code": "603993", "name": "洛阳钼业", "quantity": 1100,
                "average_cost": 18.6244, "current_price": 16.83,
                "value_low": 18.02971886915772, "neutral_value": 28.12767,
                "valuation_confidence": "HIGH", "formal_action": "HOLD",
                "holding_add_authorized": False,
            },
            {
                "code": "001316", "name": "润贝航科", "quantity": 200,
                "average_cost": 25.745, "current_price": 27.60,
                "value_low": 21.64, "neutral_value": 49.36,
                "valuation_confidence": "LOW", "formal_action": "HOLD_REVIEW",
            },
        ]},
        "execution_consumption_reconciliation": {
            "applied": [{"code": "603993", "consumed_shares": 100}]
        },
        "capital_deployment": {
            "available_cash_cny": 50000, "capital_as_of": "2026-09-20",
            "deployment_budget_cny": 0, "planned_immediate_cash_cny": 0,
            "cash_after_immediate_plan_cny": 50000, "operations": [],
        },
        "terminal_opportunities": {
            "available": True, "buy_now": [], "wait_price": [], "reject_count": 0,
            "invalid_unauthorized_buy_count": 0,
        },
    }
    center = {
        "deep_review_profile_current_for_runtime": True,
        "pillar_1_holdings_deep_analysis": {"rows": [{
            "code": "603993", "name": "洛阳钼业", "quantity": 1100,
            "average_cost": 18.6244, "current_price": 16.83,
            "neutral_value": 28.12767, "valuation_confidence": "HIGH",
            "valuation_continuity": {"value_low": 18.02971886915772},
            "deep_review": {"gates": [
                {"gate": "earnings_authenticity", "status": "PASS"},
                {"gate": "financial_safety", "status": "PASS"},
                {"gate": "long_term_demand", "status": "PASS"},
                {"gate": "moat", "status": "PASS"},
                {"gate": "predictability", "status": "UNKNOWN"},
            ]},
        }]},
    }
    return dashboard, center


def test_discount_watch_explains_price_and_cash_without_order():
    dashboard, center = sample()
    result = build_holding_valuation_watch(dashboard, center)
    assert result["authority"] == "READ_ONLY_RESEARCH_SCENARIO"
    assert result["source_epoch_verified"] is True
    assert result["buy_now"] == result["executable_orders"] == []
    row, = result["rows"]
    assert row["code"] == "603993"
    assert row["discount_to_model_low_pct"] == 6.65
    assert row["deep_gate_pass_count"] == 4
    assert row["deep_gate_unverified"] == ["predictability"]
    assert row["existing_add_allowance_consumed"] is True
    assert {"MARKET_NEW_BUY_DISABLED", "NO_CURRENT_FORMAL_HOLDING_ADD",
            "PRIOR_ADD_ALLOWANCE_CONSUMED", "DEEP_GATES_NOT_ALL_PASS"} <= set(row["blockers"])
    scenario = row["non_authorized_scenario"]
    assert scenario["estimated_cash_cny_ex_fees"] == 1683.0
    assert scenario["planning_cash_after_cny_ex_fees"] == 48317.0
    assert scenario["estimated_new_average_cost_ex_fees"] == 18.4749
    assert scenario["executable_shares"] == 0
    assert scenario["order_limit_price"] is None
    assert scenario["authorized"] is False


def test_even_green_and_add_permission_never_create_order():
    dashboard, center = sample()
    dashboard["market"].update(status="GREEN", allow_new_buy=True)
    dashboard["stock_portfolio"]["rows"][0]["holding_add_authorized"] = True
    dashboard["execution_consumption_reconciliation"]["applied"] = []
    center["pillar_1_holdings_deep_analysis"]["rows"][0]["deep_review"]["gates"][4]["status"] = "PASS"
    result = build_holding_valuation_watch(dashboard, center)
    assert result["rows"][0]["non_authorized_scenario"]["executable_shares"] == 0
    assert result["buy_now"] == []
    assert "BROKER_CASH_UNVERIFIED_LIVE" in result["rows"][0]["blockers"]


def test_stale_canonical_or_profile_never_look_actionable():
    dashboard, center = sample()
    dashboard["freshness_contract"]["market_as_of"] = "2026-09-24"
    center["deep_review_profile_current_for_runtime"] = False
    result = build_holding_valuation_watch(dashboard, center)
    assert result["source_epoch_verified"] is False
    assert result["rows"][0]["display_bucket"] == "VALUATION_WATCH_NOT_ACTIONABLE"
    assert "MARKET_OR_CANONICAL_EPOCH_UNVERIFIED" in result["rows"][0]["blockers"]
    assert "DEEP_PROFILE_LINEAGE_NOT_CURRENT" in result["rows"][0]["blockers"]


def test_low_confidence_or_price_not_below_model_floor_not_featured():
    dashboard, center = sample()
    center["pillar_1_holdings_deep_analysis"]["rows"][0]["valuation_confidence"] = "LOW"
    assert build_holding_valuation_watch(dashboard, center)["rows"] == []
    center["pillar_1_holdings_deep_analysis"]["rows"][0]["valuation_confidence"] = "HIGH"
    center["pillar_1_holdings_deep_analysis"]["rows"][0]["current_price"] = 18.10
    assert build_holding_valuation_watch(dashboard, center)["rows"] == []


def test_actual_runtime_renders_watch_but_fails_closed_without_deep_lineage():
    dashboard, _ = sample()
    era = {"no_auto_trade": True, "formal_trading_authority": False, "trends": []}
    output = build_runtime_decision_center(dashboard=dashboard, era_radar=era)
    watch = output["holding_valuation_watch"]
    assert output["executive_summary"]["discounted_holding_watch_count"] == 1
    assert "DEEP_PROFILE_LINEAGE_NOT_CURRENT" in watch["rows"][0]["blockers"]
    assert "估值折价观察（非买单）" in render_runtime_markdown(output)
    assert output["today_account_plan"]["deployment_budget_cny"] == 0
    assert watch["buy_now"] == []
