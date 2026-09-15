import pytest

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
                "consumed_at": "2026-09-11T10:13:55+08:00",
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
    assert row["investor_action"] == "继续持有；历史分批加仓授权已消费，本轮新增可执行0股"
    assert row["holding_add_consumption"]["lineage_match"] == "EXACT"
    assert row["holding_add_consumption"]["remaining_executable_shares"] == 0
    assert out["capital_deployment"]["operations"] == []
    assert out["final_operation_table"] == []
    assert out["capital_deployment"]["planned_immediate_cash_cny"] == 0.0
    assert out["capital_deployment"]["cash_after_immediate_plan_cny"] == 59000.0
    assert out["decision_summary"]["planned_immediate_cash_cny"] == 0.0
    reconciliation = out["execution_consumption_reconciliation"]
    assert reconciliation["applied_consumption_count"] == 1
    assert reconciliation["exact_lineage_consumption_count"] == 1
    assert reconciliation["carried_forward_consumption_count"] == 0
    assert reconciliation["routine_canonical_refresh_rearms_consumed_add"] is False


def test_consumption_carries_across_routine_canonical_refresh_and_blocks_repeat_add():
    out = apply_execution_consumption(_dashboard(), _state(snapshot="old-snap", source="old-run"))
    row = out["stock_portfolio"]["rows"][0]
    assert row["holding_add_authorized"] is False
    assert row["investor_action"] == "继续持有；历史分批加仓授权已消费，本轮新增可执行0股"
    assert row["holding_add_consumption"]["lineage_match"] == "CARRIED_FORWARD"
    assert row["holding_add_consumption"]["source_canonical_snapshot_id"] == "old-snap"
    assert row["holding_add_consumption"]["applied_to_canonical_snapshot_id"] == "snap-1"
    assert out["capital_deployment"]["operations"] == []
    assert out["final_operation_table"] == []
    reconciliation = out["execution_consumption_reconciliation"]
    assert reconciliation["applied_consumption_count"] == 1
    assert reconciliation["exact_lineage_consumption_count"] == 0
    assert reconciliation["carried_forward_consumption_count"] == 1


def test_explicit_rearm_is_required_before_old_consumption_can_be_left_behind():
    dashboard = _dashboard()
    row = dashboard["stock_portfolio"]["rows"][0]
    row["holding_add_rearm_after_consumption"] = True
    row["holding_add_reason_codes"] += ";STAGED_ADD_REARM_AUTHORIZED"

    out = apply_execution_consumption(dashboard, _state(snapshot="old-snap", source="old-run"))
    updated = out["stock_portfolio"]["rows"][0]
    assert updated["holding_add_authorized"] is True
    assert updated["investor_action"] == "继续持有；可分批加仓1手"
    assert len(out["capital_deployment"]["operations"]) == 1
    reconciliation = out["execution_consumption_reconciliation"]
    assert reconciliation["applied_consumption_count"] == 0
    assert reconciliation["explicit_rearm_skipped_count"] == 1
    assert reconciliation["explicit_rearm_skipped_codes"] == ["603993"]


def test_exact_lineage_consumption_still_wins_even_if_row_claims_rearm():
    dashboard = _dashboard()
    dashboard["stock_portfolio"]["rows"][0]["holding_add_rearm_after_consumption"] = True
    out = apply_execution_consumption(dashboard, _state())
    assert out["stock_portfolio"]["rows"][0]["holding_add_authorized"] is False
    assert out["execution_consumption_reconciliation"]["applied_consumption_count"] == 1


def test_partial_consumption_below_allowance_is_not_over_suppressed():
    dashboard = _dashboard()
    dashboard["stock_portfolio"]["rows"][0]["holding_add_max_lots"] = 2
    out = apply_execution_consumption(dashboard, _state(shares=100))
    assert out["stock_portfolio"]["rows"][0]["holding_add_authorized"] is True
    assert len(out["capital_deployment"]["operations"]) == 1
    assert out["execution_consumption_reconciliation"]["applied_consumption_count"] == 0


def test_latest_exact_lineage_record_takes_precedence_over_older_carried_record():
    state = _state(snapshot="old-snap", source="old-run", shares=100)
    state["consumptions"].append({
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "code": "603993",
        "authorization_type": "HOLDING_STAGED_ADD",
        "consumed_shares": 0,
        "consumed_at": "2026-09-14T10:00:00+08:00",
        "no_auto_trade": True,
    })
    out = apply_execution_consumption(_dashboard(), state)
    assert out["stock_portfolio"]["rows"][0]["holding_add_authorized"] is True
    assert out["execution_consumption_reconciliation"]["exact_lineage_consumption_count"] == 1
    assert out["execution_consumption_reconciliation"]["applied_consumption_count"] == 0


def test_bad_execution_state_fails_closed_instead_of_guessing():
    state = _state()
    state["no_auto_trade"] = False
    with pytest.raises(ValueError, match="no-auto-trade"):
        apply_execution_consumption(_dashboard(), state)
