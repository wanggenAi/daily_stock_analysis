import pytest

from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import build_dashboard, render_markdown


def _decision(code, name, scope, action, price, value=60.0):
    return {
        "code": code, "stock_name": name, "scope": scope, "action": action,
        "current_price": price, "neutral_value": value, "valuation_confidence": "HIGH",
        "reason_codes": "TEST", "v311_production_bridge": "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT",
        "no_auto_trade": True,
    }


def _canonical():
    return {
        "snapshot_id": "snapshot-1", "source_run_id": "12345", "latest_trade_date": "2026-09-03",
        "production": {
            "holding_decisions": [
                _decision("601318", "中国平安", "HOLDING", "ADD", 58.0, 80.0),
                _decision("603993", "洛阳钼业", "HOLDING", "HOLD", 19.0, 28.0),
            ],
            "candidate_decisions": [_decision("600036", "招商银行", "CANDIDATE", "BUY", 41.0, 55.0)],
        },
    }


def _holdings():
    return {
        "601318": {"code": "601318", "name": "中国平安", "quantity": 300, "average_cost": 57.1676},
        "603993": {"code": "603993", "name": "洛阳钼业", "quantity": 600, "average_cost": 19.1087},
    }


def _capital():
    return {
        "status": "USER_CONFIRMED_FLOOR", "planning_cash_cny": 70000.0, "as_of": "2026-09-03T12:17:00+08:00",
        "planner": {"max_deployment_ratio": 0.70, "max_single_name_ratio_of_available_cash": 0.20,
                    "max_names": 5, "first_tranche_ratio": 0.50, "second_tranche_discount_pct": 0.02},
        "no_auto_trade": True,
    }


def _terminal():
    common = {"decision_authority": "RESEARCH_TERMINAL_VIEW", "no_auto_trade": "True"}
    return [
        {**common, "master_research_rank": "1", "code": "600036", "stock_name": "招商银行",
         "terminal_decision": "BUY", "terminal_current_price": "41", "terminal_formal_buy_authorized": "True",
         "source_valuation_confidence": "HIGH", "v31_neutral_value": "55", "formal_buy_max_price_to_neutral": "0.8"},
        {**common, "master_research_rank": "2", "code": "601899", "stock_name": "紫金矿业",
         "terminal_decision": "WAIT_PRICE", "terminal_current_price": "34", "wait_price_max": "32",
         "terminal_formal_buy_authorized": "False", "source_valuation_confidence": "HIGH"},
        {**common, "master_research_rank": "3", "code": "603986", "stock_name": "兆易创新",
         "terminal_decision": "REJECT", "terminal_formal_buy_authorized": "False"},
    ]


def test_dashboard_allocates_only_authorized_actions_and_preserves_wait_price():
    payload = build_dashboard(
        canonical=_canonical(), holdings=_holdings(), funds=[], capital=_capital(), terminal_decisions=_terminal(),
        market_regime={"status": "GREEN", "allow_new_buy": True, "position_multiplier": 1.0,
                       "advance_ratio": 0.55, "data_quality": "OK"},
        industry_regimes=[{"industry": "银行", "status": "STRONG", "score": "80"}], mode="DAILY",
        generated_at="2026-09-03T04:30:00+00:00",
    )
    assert payload["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert payload["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True
    assert [x["code"] for x in payload["terminal_opportunities"]["buy_now"]] == ["600036"]
    assert [x["code"] for x in payload["terminal_opportunities"]["wait_price"]] == ["601899"]
    assert payload["terminal_opportunities"]["reject_count"] == 1

    ops = payload["capital_deployment"]["operations"]
    assert {x["code"] for x in ops} == {"601318", "600036"}
    assert all(x["authorization_proven"] for x in ops)
    assert all(x["planned_shares"] % 100 == 0 for x in ops)
    assert all(x["automatic_order_allowed"] is False for x in ops)
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] <= payload["capital_deployment"]["deployment_budget_cny"] <= 49000.0
    assert payload["capital_deployment"]["cash_after_immediate_plan_cny"] >= 0

    waits = payload["capital_deployment"]["wait_price_reservations"]
    assert waits[0]["code"] == "601899"
    assert waits[0]["first_entry_max_price"] == 32.0
    assert waits[0]["immediate_execution_eligible"] is False
    assert "603986" not in {x["code"] for x in payload["final_operation_table"]}


def test_unauthorized_terminal_buy_is_suppressed_not_promoted():
    rows = _terminal()
    rows[0]["terminal_formal_buy_authorized"] = "False"
    payload = build_dashboard(canonical=_canonical(), holdings=_holdings(), funds=[], capital=_capital(), terminal_decisions=rows)
    assert payload["terminal_opportunities"]["buy_now"] == []
    assert payload["data_health"]["terminal_unauthorized_buy_suppressed"] == 1
    assert "600036" not in {x["code"] for x in payload["capital_deployment"]["operations"]}


def test_market_block_can_only_reduce_deployment_not_create_signal():
    payload = build_dashboard(canonical=_canonical(), holdings=_holdings(), funds=[], capital=_capital(), terminal_decisions=_terminal(),
                              market_regime={"status": "RED", "allow_new_buy": False, "position_multiplier": 0.0})
    assert payload["capital_deployment"]["deployment_budget_cny"] == 0
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] == 0
    assert payload["terminal_opportunities"]["buy_now"][0]["code"] == "600036"


def test_dashboard_rejects_bad_authority_and_renders_investor_first_order():
    canonical = _canonical()
    canonical["production"]["holding_decisions"][0]["no_auto_trade"] = False
    with pytest.raises(ValueError, match="no-auto-trade"):
        build_dashboard(canonical=canonical, holdings=_holdings(), funds=[])

    payload = build_dashboard(canonical=_canonical(), holdings=_holdings(), funds=[], capital=_capital(), terminal_decisions=_terminal())
    text = render_markdown(payload)
    sections = ["## 1. 今天市场怎么样", "## 2. 我的持仓怎么办", "## 3. 今天能直接买什么",
                "## 4. WAIT_PRICE：跌到多少钱再买", "## 5. 资金怎么花", "## 6. 最终操作表",
                "## 9. 系统状态（最后看）"]
    positions = [text.index(x) for x in sections]
    assert positions == sorted(positions)
    assert payload["presentation_contract"]["section_order"][:6] == [
        "market", "stock_portfolio", "terminal_buy_now", "terminal_wait_price", "capital_deployment", "final_operation_table"
    ]
