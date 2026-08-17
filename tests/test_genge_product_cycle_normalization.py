import inspect

import pytest

from src.strategies.genge_opportunity_discovery.product_cycle_normalization import (
    aggregate_product_cycle_profit,
    collect_product_cycle_evidence,
    normalize_product_cycle_segment,
    reverse_implied_product_unit_margin,
)


def _segment(segment_id="bev", scope="vehicle-bev", units=100.0, revenue=20.0, cost=17.0):
    return normalize_product_cycle_segment(
        segment_id=segment_id,
        economic_scope_id=scope,
        normalized_units=units,
        normalized_net_revenue_per_unit=revenue,
        normalized_full_operating_cost_per_unit=cost,
    )


def test_product_segment_rebuilds_profit_from_explicit_unit_economics():
    result = _segment()

    assert result.normalized_unit_operating_margin == pytest.approx(3.0)
    assert result.normalized_operating_contribution == pytest.approx(300.0)
    assert result.normalized_segment_profit == pytest.approx(300.0)
    assert result.status == "OK"


def test_negative_product_unit_margin_is_preserved():
    result = _segment(units=100.0, revenue=15.0, cost=17.0)

    assert result.normalized_unit_operating_margin == pytest.approx(-2.0)
    assert result.normalized_segment_profit == pytest.approx(-200.0)


def test_product_cycle_api_has_no_hidden_auto_price_mix_or_incentive_defaults():
    signature = inspect.signature(normalize_product_cycle_segment)

    assert "bev_share" not in signature.parameters
    assert "phev_share" not in signature.parameters
    assert "vehicle_asp" not in signature.parameters
    assert "incentive" not in signature.parameters
    assert signature.parameters["normalized_net_revenue_per_unit"].default is inspect._empty
    assert signature.parameters["normalized_full_operating_cost_per_unit"].default is inspect._empty


def test_aggregate_rejects_overlapping_economic_scope_ids():
    vehicle = _segment("vehicle", "integrated-vehicle-margin")
    internal_battery = _segment("battery", "integrated-vehicle-margin")

    result = aggregate_product_cycle_profit(
        segment_results=[vehicle, internal_battery],
        normalized_non_product_profit=0.0,
        normalized_equity_method_income=0.0,
    )

    assert result.normalized_sustainable_profit is None
    assert result.status == "DUPLICATE_ECONOMIC_SCOPE_ID"


def test_aggregate_keeps_non_product_and_equity_method_income_separate():
    bev = _segment("bev", "bev-retail", 100.0, 20.0, 17.0)
    phev = _segment("phev", "phev-retail", 50.0, 18.0, 16.0)

    result = aggregate_product_cycle_profit(
        segment_results=[bev, phev],
        normalized_non_product_profit=80.0,
        normalized_equity_method_income=40.0,
        explicit_corporate_adjustment=-20.0,
    )

    assert result.normalized_product_profit == pytest.approx(400.0)
    assert result.normalized_sustainable_profit == pytest.approx(500.0)
    assert result.status == "OK"


def test_aggregate_requires_explicit_equity_method_income_even_if_zero():
    segment = _segment()
    signature = inspect.signature(aggregate_product_cycle_profit)

    assert signature.parameters["normalized_equity_method_income"].default is inspect._empty
    result = aggregate_product_cycle_profit(
        segment_results=[segment],
        normalized_non_product_profit=0.0,
        normalized_equity_method_income=None,
    )
    assert result.status == "EQUITY_METHOD_INCOME_UNAVAILABLE"


def test_reverse_implied_product_margin_connects_market_profit_to_unit_economics():
    margin, status = reverse_implied_product_unit_margin(
        implied_total_normalized_profit=600.0,
        normalized_non_product_profit=80.0,
        normalized_equity_method_income=40.0,
        other_product_scope_profit=180.0,
        target_scope_units=100.0,
        explicit_corporate_adjustment=-20.0,
    )

    assert margin == pytest.approx((600.0 - 80.0 - 40.0 - 180.0 + 20.0) / 100.0)
    assert status == "OK"


def test_product_cycle_evidence_keeps_volume_mix_price_cost_proxies_separate():
    result = collect_product_cycle_evidence(
        total_unit_sales_growth=0.19,
        primary_product_mix_share=0.55,
        secondary_product_mix_share=0.32,
        overseas_unit_share=0.17,
        average_net_revenue_per_unit_change=-0.05,
        gross_margin=0.105,
        capacity_utilization=0.75,
        equity_method_income_share=0.08,
        fx_profit_or_loss=-2.0,
    )

    assert result.total_unit_sales_growth == pytest.approx(0.19)
    assert result.average_net_revenue_per_unit_change == pytest.approx(-0.05)
    assert result.evidence_completeness == pytest.approx(9 / 15)
    assert "warranty_cost_ratio" in result.missing_fields
    assert not hasattr(result, "quality_score")
