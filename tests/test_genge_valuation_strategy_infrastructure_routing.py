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
