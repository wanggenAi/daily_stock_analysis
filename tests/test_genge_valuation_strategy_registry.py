import pytest

from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import (
    CompanyArchetype,
    DEFAULT_VALUATION_STRATEGY_REGISTRY,
    StrategyDescriptor,
    StrategyRole,
    ValuationStrategyRegistry,
    route_valuation_strategies,
)


def test_bank_routes_away_from_generic_pe_model():
    decision = route_valuation_strategies(industry="银行")

    assert decision.primary_strategy_id == "bank_residual_income"
    assert decision.strategy_ids == ("bank_residual_income",)
    assert CompanyArchetype.GENERAL_EARNINGS not in decision.archetypes
    assert decision.status == "SPECIALIZED_EXCLUSIVE"


def test_rare_metals_get_capacity_normalization_before_generic_reverse_earnings():
    decision = route_valuation_strategies(industry="稀有金属")

    assert decision.strategy_ids == (
        "capacity_cycle_normalizer",
        "general_reverse_earnings",
    )
    assert decision.primary_strategy_id == "general_reverse_earnings"
    assert decision.archetypes == (
        CompanyArchetype.CAPACITY_CYCLE,
        CompanyArchetype.GENERAL_EARNINGS,
    )
    assert decision.status == "NORMALIZED_GENERIC"


def test_semiconductor_gets_product_cycle_normalization():
    decision = route_valuation_strategies(industry="半导体")

    assert decision.strategy_ids == (
        "product_cycle_normalizer",
        "general_reverse_earnings",
    )
    assert decision.routing_confidence == 0.8


def test_pipeline_driven_biotech_tag_routes_to_rnpv_without_generic_pe():
    decision = route_valuation_strategies(
        industry="医药",
        business_tags="创新药;临床管线",
    )

    assert decision.strategy_ids == ("biotech_rnpv",)
    assert decision.primary_strategy_id == "biotech_rnpv"
    assert decision.status == "SPECIALIZED_EXCLUSIVE"


def test_generic_pharma_does_not_silently_assume_biotech_rnpv():
    decision = route_valuation_strategies(industry="医药")

    assert decision.strategy_ids == ("general_reverse_earnings",)
    assert decision.status == "GENERIC_FALLBACK"


def test_explicit_normalizer_hint_adds_generic_valuation_bridge():
    decision = route_valuation_strategies(
        industry="未知",
        archetype_hints="capacity_cycle",
    )

    assert decision.strategy_ids == (
        "capacity_cycle_normalizer",
        "general_reverse_earnings",
    )
    assert decision.status == "EXPLICIT_ARCHETYPE_ROUTE"
    assert decision.routing_confidence == 1.0


def test_default_registry_is_immutable_when_extended():
    custom = StrategyDescriptor(
        strategy_id="future_specialized_model",
        archetype=CompanyArchetype.GENERAL_EARNINGS,
        role=StrategyRole.ALTERNATIVE_VALUATION,
        module_path="example.future_model",
        execution_order=120,
        pe_based=False,
        description="test-only extension",
    )

    extended = DEFAULT_VALUATION_STRATEGY_REGISTRY.with_strategy(custom)

    assert len(extended.strategies) == len(DEFAULT_VALUATION_STRATEGY_REGISTRY.strategies) + 1
    with pytest.raises(KeyError):
        DEFAULT_VALUATION_STRATEGY_REGISTRY.get("future_specialized_model")
    assert extended.get("future_specialized_model") == custom


def test_registry_rejects_duplicate_strategy_ids():
    strategy = StrategyDescriptor(
        strategy_id="duplicate",
        archetype=CompanyArchetype.GENERAL_EARNINGS,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="example.one",
        execution_order=100,
        pe_based=True,
        description="one",
    )

    with pytest.raises(ValueError, match="duplicate valuation strategy_id"):
        ValuationStrategyRegistry((strategy, strategy))


def test_route_metadata_never_promotes_to_trade_signal():
    payload = route_valuation_strategies(industry="公用事业").to_dict()

    assert payload["formal_signal_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["no_auto_trade"] is True
