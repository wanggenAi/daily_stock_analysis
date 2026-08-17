from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import (
    route_valuation_strategies,
)


def test_airport_routes_to_yield_asset_not_transport_cycle():
    decision = route_valuation_strategies(industry="机场")

    assert decision.strategy_ids == ("yield_asset",)
    assert decision.primary_strategy_id == "yield_asset"


def test_shipping_stays_on_transport_cycle_model():
    decision = route_valuation_strategies(industry="航运")

    assert decision.strategy_ids == ("transport_cycle",)
    assert decision.primary_strategy_id == "transport_cycle"


def test_airline_transport_routes_to_transport_cycle():
    decision = route_valuation_strategies(industry="航空运输")

    assert decision.strategy_ids == ("transport_cycle",)
    assert decision.primary_strategy_id == "transport_cycle"


def test_aerospace_manufacturing_does_not_route_as_airline():
    decision = route_valuation_strategies(industry="航空装备")

    assert decision.strategy_ids == ("general_reverse_earnings",)
    assert decision.status == "GENERIC_FALLBACK"


def test_real_estate_developer_routes_to_project_nav():
    decision = route_valuation_strategies(industry="房地产开发")

    assert decision.strategy_ids == ("real_estate_nav",)
    assert decision.primary_strategy_id == "real_estate_nav"


def test_broad_real_estate_service_label_does_not_force_developer_nav():
    decision = route_valuation_strategies(industry="房地产服务")

    assert decision.strategy_ids == ("general_reverse_earnings",)
    assert decision.status == "GENERIC_FALLBACK"


def test_business_tag_can_upgrade_broad_real_estate_label_to_developer_nav():
    decision = route_valuation_strategies(
        industry="房地产",
        business_tags="住宅开发",
    )

    assert decision.strategy_ids == ("real_estate_nav",)
    assert decision.primary_strategy_id == "real_estate_nav"
