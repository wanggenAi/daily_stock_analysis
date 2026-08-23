from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from src.strategies.genge_opportunity_discovery.resource_valuation_execution import execute_rows
from src.strategies.genge_opportunity_discovery.v31_resource_scenario_merge import merge_rows
from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import route_valuation_strategies


def test_mine_owner_routes_to_resource_nav_but_generic_nonferrous_does_not():
    mine = route_valuation_strategies(industry="铜矿采选")
    assert mine.primary_strategy_id == "resource_asset_nav"
    assert "RESOURCE_ASSET" in {item.value for item in mine.archetypes}

    processor = route_valuation_strategies(industry="有色", business_tags="纯冶炼;加工为主")
    assert processor.primary_strategy_id == "general_reverse_earnings"
    assert "capacity_cycle_normalizer" in processor.strategy_ids
    assert "resource_asset_nav" not in processor.strategy_ids


def test_resource_business_tag_overrides_broad_nonferrous_prior():
    decision = route_valuation_strategies(industry="有色", business_tags="自有矿;权益矿;资源储量")
    assert decision.primary_strategy_id == "resource_asset_nav"
    assert decision.routing_confidence >= 0.95


def _scenario(price: float) -> dict:
    return {
        "assets": [{
            "asset_id": "mine-a",
            "economic_scope_id": "mine-a-resource",
            "economic_ownership": 1.0,
            "recoverable_units_100pct": 100.0,
            "annual_production_units_100pct": 10.0,
            "normalized_realized_unit_price": price,
            "unit_cash_operating_cost": 20.0,
            "sustaining_capex_per_unit": 5.0,
            "royalty_rate_on_revenue": 0.0,
            "cash_tax_rate_on_positive_pretax_cash_flow": 0.20,
            "required_return": 0.10,
            "closure_and_reclamation_cash_outflow_100pct": 0.0,
        }],
        "equity_bridge": {
            "non_resource_segment_value": 0.0,
            "unrestricted_cash": 0.0,
            "interest_bearing_debt_not_in_resource_cash_flows": 0.0,
            "other_corporate_liability_pv_not_in_resource_cash_flows": 0.0,
            "explicit_equity_adjustment": 0.0,
            "total_common_shares": 10.0,
        },
    }


def test_four_scenario_resource_nav_executes_and_maps_to_v31(tmp_path: Path):
    config = {
        "companies": {
            "601899": {
                "input_as_of": "2024-01-01",
                "review_after": "2025-12-31",
                "evidence_urls": ["https://example.invalid/official-filing"],
                "scenarios": {
                    "extreme_stress": _scenario(35.0),
                    "bear": _scenario(45.0),
                    "base": _scenario(55.0),
                    "bull": _scenario(70.0),
                },
            }
        }
    }
    path = tmp_path / "resource.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    routed = [{"code": "601899", "valuation_primary_strategy_id": "resource_asset_nav"}]
    executed = execute_rows(routed, as_of=date(2024, 6, 1), config_path=path)
    row = executed[0]
    assert row["resource_nav_executed"] is True
    assert row["resource_nav_status"] == "OK"
    assert float(row["resource_nav_extreme_stress_per_share"]) < float(row["resource_nav_bear_per_share"])
    assert float(row["resource_nav_bear_per_share"]) < float(row["resource_nav_base_per_share"])
    assert float(row["resource_nav_base_per_share"]) < float(row["resource_nav_bull_per_share"])

    merged = merge_rows([{"code": "601899", "v31_pessimistic_value": "", "v31_neutral_value": "", "v31_optimistic_value": "", "v31_extreme_stress_value": ""}], executed)[0]
    assert merged["v31_resource_scenario_status"] == "MAPPED"
    assert merged["v31_pessimistic_value"] == row["resource_nav_bear_per_share"]
    assert merged["v31_neutral_value"] == row["resource_nav_base_per_share"]
    assert merged["v31_optimistic_value"] == row["resource_nav_bull_per_share"]
    assert merged["v31_extreme_stress_value"] == row["resource_nav_extreme_stress_per_share"]
    assert merged["formal_signal_eligible"] is False
