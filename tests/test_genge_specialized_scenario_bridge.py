from __future__ import annotations

from src.strategies.genge_opportunity_discovery.specialized_scenario_bridge import (
    bridge_specialized_scenario,
)
from src.strategies.genge_opportunity_discovery.specialized_scenario_postscan import (
    overlay_specialized_scenarios,
)


def _broker_row(**overrides):
    row = {
        "code": "600030",
        "valuation_primary_strategy_id": "capital_markets_cycle",
        "specialized_model_executed": True,
        "specialized_model_execution_state": "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY",
        "specialized_model_status": "OK",
        "specialized_current_pb": 1.20,
        "specialized_fair_pb": 1.50,
    }
    row.update(overrides)
    return row


def test_executed_broker_pb_model_converts_to_base_fair_share_price_without_new_multiple():
    result = bridge_specialized_scenario(_broker_row(), current_price=24.0)

    assert result.status == "OK_BASE_ONLY"
    assert result.fair_price_bear is None
    assert result.fair_price_base == 30.0
    assert result.fair_price_bull is None
    assert "share_price*fair_pb/current_pb" in result.basis
    assert "bear_bull_not_invented" in result.basis


def test_unexecuted_or_incomplete_specialized_model_never_creates_fair_price():
    unexecuted = bridge_specialized_scenario(
        _broker_row(
            specialized_model_executed=False,
            specialized_model_execution_state="SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        ),
        current_price=24.0,
    )
    missing_pb = bridge_specialized_scenario(
        _broker_row(specialized_current_pb=""),
        current_price=24.0,
    )

    assert unexecuted.fair_price_base is None
    assert unexecuted.status == "SPECIALIZED_MODEL_NOT_EXECUTED"
    assert missing_pb.fair_price_base is None
    assert missing_pb.status == "SPECIALIZED_FAIR_VALUE_INPUTS_INCOMPLETE"


def test_unsupported_resource_or_insurance_route_does_not_get_fake_fair_value():
    resource = bridge_specialized_scenario(
        {
            "valuation_primary_strategy_id": "resource_asset_nav",
            "specialized_model_executed": True,
            "specialized_model_execution_state": "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY",
            "specialized_model_status": "OK",
        },
        current_price=10.0,
    )
    insurance = bridge_specialized_scenario(
        {
            "valuation_primary_strategy_id": "insurance_embedded_value",
            "specialized_model_executed": True,
            "specialized_model_execution_state": "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY",
            "specialized_model_status": "OK",
        },
        current_price=10.0,
    )

    assert resource.fair_price_base is None
    assert insurance.fair_price_base is None
    assert resource.status == "SPECIALIZED_MODEL_HAS_NO_AUDITABLE_PER_SHARE_FAIR_VALUE_BRIDGE"
    assert insurance.status == "SPECIALIZED_MODEL_HAS_NO_AUDITABLE_PER_SHARE_FAIR_VALUE_BRIDGE"


def test_postscan_overlay_updates_only_executed_supported_specialized_route():
    forward_rows = [
        {
            "code": "600030",
            "current_price": "24.0",
            "valuation_primary_strategy_id": "capital_markets_cycle",
            "scenario_fair_price_base": "",
            "scenario_valuation_status": "SPECIALIZED_MODEL_REQUIRED",
        },
        {
            "code": "601899",
            "current_price": "15.0",
            "valuation_primary_strategy_id": "resource_asset_nav",
            "scenario_fair_price_base": "",
            "scenario_valuation_status": "SPECIALIZED_MODEL_REQUIRED",
        },
    ]
    specialized_rows = [
        _broker_row(),
        {
            "code": "601899",
            "valuation_primary_strategy_id": "resource_asset_nav",
            "specialized_model_executed": False,
            "specialized_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
            "specialized_model_status": "RESOURCE_ASSET_INPUTS_REQUIRED",
        },
    ]
    raw_rows = [
        {"code": "600030", "raw_latest_close": "24.0"},
        {"code": "601899", "raw_latest_close": "15.0"},
    ]

    rows, stats = overlay_specialized_scenarios(forward_rows, specialized_rows, raw_rows)
    by_code = {row["code"]: row for row in rows}

    assert by_code["600030"]["scenario_fair_price_base"] == 30.0
    assert by_code["600030"]["scenario_valuation_status"] == "SPECIALIZED_BASE_ONLY"
    assert by_code["600030"]["scenario_fair_price_bear"] if "scenario_fair_price_bear" in by_code["600030"] else True
    assert by_code["601899"]["scenario_fair_price_base"] == ""
    assert by_code["601899"]["specialized_scenario_bridge_status"] == "SPECIALIZED_MODEL_HAS_NO_AUDITABLE_PER_SHARE_FAIR_VALUE_BRIDGE"
    assert stats["specialized_route_count"] == 2
    assert stats["specialized_base_fair_value_ready_count"] == 1
    assert stats["specialized_unavailable_count"] == 1
