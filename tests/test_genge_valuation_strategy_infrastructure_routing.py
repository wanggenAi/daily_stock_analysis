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
