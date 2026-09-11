from src.strategies.genge_opportunity_discovery.execution_consumption_overlay import apply_execution_consumption


def _dashboard():
    return {
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "headline": "市场=YELLOW；计划立即投入≈¥1900",
        "no_auto_trade": True,
        "stock_portfolio": {
            "rows": [
                {
                    "code": "603993",
                    "formal_action": "HOLD",
                    "canonical_formal_action": "HOLD",
                    "investor_action": "继续持有；可分批加仓1手",
                    "holding_add_authorized": True,
                    "holding_add_max_lots": 1,
                    "holding_add_reason_codes": "STAGED_ADD_CAP_ONE_LOT",
                }
            ]
        },
        "capital_deployment": {
            "available_cash_cny": 59000.0,
            "planned_immediate_cash_cny": 1900.0,
            "cash_after_immediate_plan_cny": 57100.0,
            "operations": [
                {
                    "code": "603993",
                    "action": "ADD",
                    "source": "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD",
                    "estimated_cash_cny": 1900.0,
                }
            ],
        },
        "final_operation_table": [
            {
                "code": "603993",
                "action": "ADD",
                "source": "AUTHORIZED_CANONICAL_HOLDING_STAGED_ADD",
                "estimated_cash_cny": 1900.0,
            }
        ],
        "decision_summary": {"planned_immediate_cash_cny": 1900.0},
    }


def _state(snapshot="snap-1", source="run-1", shares=100):
    return {
        "contract_version": "GEN_GE_EXECUTION_CONSUMPTION_V1",
        "no_auto_trade": True,
        "consumptions": [
            {
                "canonical_snapshot_id": snapshot,
                "canonical_source_run_id": source,
                "code": "603993",
                "authorization_type": "HOLDING_STAGED_ADD",
                "consumed_shares": shares,
                "no_auto_trade": True,
            }
        ],
    }


def test_consumed_staged_add_is_not_planned_twice_and_formal_hold_is_unchanged():
    out = apply_execution_consumption(_dashboard(), _state())
    row = out["stock_portfolio"]["rows"][0]
    assert row["formal_action"] == "HOLD"
    assert row["canonical_formal_action"] == "HOLD"
    assert row["holding_add_authorized"] is False
    assert "STAGED_ADD_AUTHORIZATION_CONSUMED" in row["holding_add_reason_codes"]
    assert out["capital_deployment"]["operations"] == []
    assert out["final_operation_table"] == []
    assert out["capital_deployment"]["planned_immediate_cash_cny"] == 0.0
    assert out["capital_deployment"]["cash_after_immediate_plan_cny"] == 59000.0
    assert out["decision_summary"]["planned_immediate_cash_cny"] == 0.0
    assert out["execution_consumption_reconciliation"]["applied_consumption_count"] == 1


def test_old_consumption_does_not_apply_to_new_canonical_snapshot():
    out = apply_execution_consumption(_dashboard(), _state(snapshot="old-snap"))
    row = out["stock_portfolio"]["rows"][0]
    assert row["holding_add_authorized"] is True
    assert len(out["capital_deployment"]["operations"]) == 1
    assert out["execution_consumption_reconciliation"]["applied_consumption_count"] == 0


def test_partial_consumption_below_allowance_is_not_over_suppressed():
    dashboard = _dashboard()
    dashboard["stock_portfolio"]["rows"][0]["holding_add_max_lots"] = 2
    out = apply_execution_consumption(dashboard, _state(shares=100))
    assert out["stock_portfolio"]["rows"][0]["holding_add_authorized"] is True
    assert len(out["capital_deployment"]["operations"]) == 1
