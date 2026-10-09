from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import _fail_closed_new_exposure


def test_stale_generation_blocks_all_direct_execution_but_preserves_formal_truth():
    payload = {
        "formal_holding_actions_currently_usable": True,
        "market": {"status": "RED", "allow_new_buy": True},
        "terminal_opportunities": {
            "buy_now": [{"code": "600036", "currently_actionable": True}],
            "wait_price": [{"code": "601899", "trigger_currently_usable": True}],
        },
        "stock_portfolio": {
            "status": "CONFIRMED",
            "rows": [
                {
                    "code": "600406",
                    "formal_action": "REDUCE_25",
                    "formal_action_currently_usable": True,
                    "action_authority": "FORMAL",
                    "execution_feasibility": {"executable_reduction_shares": 100},
                    "holding_add_authorized": False,
                    "investor_action": "减仓25%",
                },
                {
                    "code": "603993",
                    "formal_action": "HOLD",
                    "formal_action_currently_usable": True,
                    "action_authority": "FORMAL",
                    "execution_feasibility": None,
                    "holding_add_authorized": True,
                    "investor_action": "继续持有",
                },
            ],
        },
        "capital_deployment": {
            "available_cash_cny": 50000.0,
            "deployment_budget_cny": 35000.0,
            "effective_max_deployment_ratio": 0.7,
            "operations": [
                {"code": "600406", "action": "REDUCE_25"},
                {"code": "603993", "action": "ADD"},
            ],
            "planned_immediate_cash_cny": 10000.0,
            "cash_after_immediate_plan_cny": 40000.0,
            "wait_price_reservations": [{"code": "601899", "trigger_currently_usable": True}],
        },
        "final_operation_table": [
            {"code": "600406", "action": "REDUCE_25"},
            {"code": "603993", "action": "ADD"},
        ],
        "decision_summary": {"planned_immediate_cash_cny": 10000.0},
        "data_health": {},
    }
    freshness = {
        "status": "STALE_UPSTREAM",
        "reasons": ["CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION"],
    }

    _fail_closed_new_exposure(payload, freshness)

    assert payload["formal_holding_actions_currently_usable"] is False
    assert payload["formal_new_exposure_allowed"] is False
    assert payload["market"]["allow_new_buy"] is False
    assert payload["stock_portfolio"]["status"] == "STALE_UPSTREAM_REVIEW_ONLY"

    reduce_row = payload["stock_portfolio"]["rows"][0]
    assert reduce_row["formal_action"] == "REDUCE_25"
    assert reduce_row["formal_action_currently_usable"] is False
    assert reduce_row["action_authority"] == "FORMAL_STALE_REVIEW_ONLY"
    assert reduce_row["execution_feasibility"] is None
    assert "禁止直接执行" in reduce_row["investor_action"]

    hold_row = payload["stock_portfolio"]["rows"][1]
    assert hold_row["formal_action"] == "HOLD"
    assert hold_row["formal_action_currently_usable"] is False
    assert hold_row["holding_add_authorized"] is False

    assert payload["terminal_opportunities"]["buy_now"][0]["currently_actionable"] is False
    assert payload["terminal_opportunities"]["wait_price"][0]["trigger_currently_usable"] is False
    assert payload["capital_deployment"]["status"] == "STALE_UPSTREAM_BLOCK_ALL_EXECUTION"
    assert payload["capital_deployment"]["operations"] == []
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] == 0.0
    assert payload["capital_deployment"]["cash_after_immediate_plan_cny"] == 50000.0
    assert payload["final_operation_table"] == []
    assert payload["data_health"]["formal_holding_actions_currently_usable"] is False
    assert "禁止直接执行任何Formal动作" in payload["headline"]
