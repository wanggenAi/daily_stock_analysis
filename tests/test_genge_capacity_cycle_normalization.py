import inspect

import pytest

from src.strategies.genge_opportunity_discovery.capacity_cycle_normalization import (
    aggregate_capacity_cycle_profit,
    collect_capacity_cycle_evidence,
    normalize_capacity_cycle_revenue_margin_segment,
    normalize_capacity_cycle_unit_segment,
    reverse_implied_capacity_unit_margin,
)


def test_unit_mode_rebuilds_profit_from_volume_price_variable_cost_and_fixed_cost():
    result = normalize_capacity_cycle_unit_segment(
        segment_id="ev-battery",
        economic_scope_id="ev-battery-external",
        normalized_sales_units=100.0,
        normalized_realized_unit_price=8.0,
        normalized_variable_unit_cost=5.0,
        normalized_fixed_operating_cost=100.0,
        effective_capacity_units=125.0,
    )

    assert result.normalized_revenue == pytest.approx(800.0)
    assert result.normalized_segment_profit == pytest.approx(200.0)
    assert result.normalized_operating_margin == pytest.approx(0.25)
    assert result.normalized_capacity_utilization == pytest.approx(0.8)
    assert result.status == "OK"


def test_unit_mode_preserves_negative_cycle_profit():
    result = normalize_capacity_cycle_unit_segment(
        segment_id="pv-module",
        economic_scope_id="pv-module",
        normalized_sales_units=100.0,
        normalized_realized_unit_price=4.0,
        normalized_variable_unit_cost=4.5,
        normalized_fixed_operating_cost=50.0,
    )

    assert result.normalized_segment_profit == pytest.approx(-100.0)
    assert result.normalized_operating_margin == pytest.approx(-0.25)


def test_capacity_utilization_is_diagnostic_not_a_volume_generator():
    signature = inspect.signature(normalize_capacity_cycle_unit_segment)

    assert "target_utilization" not in signature.parameters
    assert signature.parameters["normalized_sales_units"].default is inspect._empty
    assert signature.parameters["effective_capacity_units"].default is None


def test_revenue_margin_mode_requires_explicit_normalized_revenue_and_margin():
    result = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="ess",
        economic_scope_id="ess",
        normalized_revenue=500.0,
        normalized_operating_margin=0.12,
    )

    assert result.normalization_mode == "REVENUE_MARGIN"
    assert result.normalized_segment_profit == pytest.approx(60.0)
    assert result.status == "OK"


def test_revenue_margin_mode_preserves_negative_margin():
    result = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="solar-wafer",
        economic_scope_id="solar-wafer",
        normalized_revenue=500.0,
        normalized_operating_margin=-0.08,
    )

    assert result.normalized_segment_profit == pytest.approx(-40.0)


def test_capacity_cycle_module_has_no_hidden_commodity_or_utilization_defaults():
    unit_signature = inspect.signature(normalize_capacity_cycle_unit_segment)
    revenue_signature = inspect.signature(normalize_capacity_cycle_revenue_margin_segment)

    assert "lithium_price" not in unit_signature.parameters
    assert "silicon_price" not in unit_signature.parameters
    assert "cycle_haircut" not in unit_signature.parameters
    assert "target_utilization" not in unit_signature.parameters
    assert unit_signature.parameters["normalized_realized_unit_price"].default is inspect._empty
    assert unit_signature.parameters["normalized_variable_unit_cost"].default is inspect._empty
    assert revenue_signature.parameters["normalized_operating_margin"].default is inspect._empty


def test_aggregate_rejects_overlapping_economic_scope_ids():
    first = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="battery-total",
        economic_scope_id="battery-integrated",
        normalized_revenue=500.0,
        normalized_operating_margin=0.10,
    )
    second = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="battery-material-internal",
        economic_scope_id="battery-integrated",
        normalized_revenue=100.0,
        normalized_operating_margin=0.20,
    )

    result = aggregate_capacity_cycle_profit(
        segment_results=[first, second],
        normalized_non_cycle_profit=0.0,
    )

    assert result.normalized_sustainable_profit is None
    assert result.status == "DUPLICATE_ECONOMIC_SCOPE_ID"


def test_aggregate_keeps_non_cycle_profit_separate():
    ev = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="ev",
        economic_scope_id="ev",
        normalized_revenue=500.0,
        normalized_operating_margin=0.10,
    )
    ess = normalize_capacity_cycle_revenue_margin_segment(
        segment_id="ess",
        economic_scope_id="ess",
        normalized_revenue=300.0,
        normalized_operating_margin=0.15,
    )

    result = aggregate_capacity_cycle_profit(
        segment_results=[ev, ess],
        normalized_non_cycle_profit=30.0,
        explicit_corporate_adjustment=-5.0,
    )

    assert result.normalized_capacity_cycle_profit == pytest.approx(95.0)
    assert result.normalized_sustainable_profit == pytest.approx(120.0)
    assert result.status == "OK"


def test_reverse_implied_unit_margin_connects_market_profit_to_capacity_economics():
    margin, status = reverse_implied_capacity_unit_margin(
        implied_total_normalized_profit=300.0,
        normalized_non_cycle_profit=50.0,
        other_cycle_scope_profit=70.0,
        target_scope_sales_units=100.0,
        target_scope_fixed_operating_cost=80.0,
        explicit_corporate_adjustment=-20.0,
    )

    assert margin == pytest.approx((300.0 - 50.0 - 70.0 + 20.0 + 80.0) / 100.0)
    assert status == "OK"


def test_capacity_cycle_evidence_preserves_price_cost_utilization_inventory_and_capex():
    result = collect_capacity_cycle_evidence(
        current_sales_units=100.0,
        current_effective_capacity_units=130.0,
        current_capacity_utilization=0.77,
        realized_unit_price_change=-0.10,
        gross_margin=0.2063,
        gross_margin_change=-0.0178,
        inventory_value=130.8,
        inventory_growth=0.38,
        capital_expenditure=60.0,
        construction_in_progress=33.0,
        market_share=0.402,
        market_share_change=0.022,
        operating_cash_flow_growth=0.0261,
    )

    assert result.current_capacity_utilization == pytest.approx(0.77)
    assert result.inventory_growth == pytest.approx(0.38)
    assert result.market_share == pytest.approx(0.402)
    assert result.evidence_completeness == pytest.approx(13 / 15)
    assert "variable_unit_cost_change" in result.missing_fields
    assert not hasattr(result, "quality_score")
