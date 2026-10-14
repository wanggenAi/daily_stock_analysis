from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import (
    _fail_closed_new_exposure,
)


def test_stale_fail_closed_keeps_dashboard_reconciliation_usability_consistent():
    payload = {
        "formal_holding_actions_currently_usable": True,
        "holdings_reconciliation": {
            "status": "HOLDINGS_IN_SYNC",
            "formal_holding_actions_currently_usable": True,
        },
        "market": {},
        "terminal_opportunities": {"buy_now": [], "wait_price": []},
        "stock_portfolio": {"rows": []},
        "capital_deployment": {
            "available_cash_cny": 10000.0,
            "wait_price_reservations": [],
        },
        "decision_summary": {},
        "data_health": {},
    }
    freshness = {"status": "STALE_UPSTREAM", "reasons": ["TEST_STALE"]}

    _fail_closed_new_exposure(payload, freshness)

    assert payload["formal_holding_actions_currently_usable"] is False
    assert (
        payload["holdings_reconciliation"]["formal_holding_actions_currently_usable"]
        is False
    )
    assert (
        payload["decision_summary"]["formal_holding_actions_currently_usable"]
        is False
    )
    assert payload["data_health"]["formal_holding_actions_currently_usable"] is False
    assert payload["capital_deployment"]["operations"] == []
    assert payload["final_operation_table"] == []
