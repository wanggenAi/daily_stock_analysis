import inspect

import pytest

from src.strategies.genge_opportunity_discovery.biological_cycle_normalization import (
    aggregate_biological_cycle_profit,
    collect_biological_cycle_evidence,
    normalize_biological_segment,
    reverse_implied_unit_margin,
)


def test_biological_segment_rebuilds_profit_from_explicit_unit_economics():
    result = normalize_biological_segment(
        segment_id="hog",
        normalized_output_units=100.0,
        normalized_unit_price=15.0,
        normalized_full_unit_cost=12.0,
        explicit_segment_profit_adjustment=-10.0,
    )

    assert result.normalized_unit_margin == pytest.approx(3.0)
    assert result.normalized_operating_contribution == pytest.approx(300.0)
    assert result.normalized_segment_profit == pytest.approx(290.0)
    assert result.status == "OK"


def test_negative_cycle_margin_is_preserved_not_floored():
    result = normalize_biological_segment(
        segment_id="hog-bottom",
        normalized_output_units=100.0,
        normalized_unit_price=9.7,
        normalized_full_unit_cost=11.6,
    )

    assert result.normalized_unit_margin == pytest.approx(-1.9)
    assert result.normalized_segment_profit == pytest.approx(-190.0)


def test_unit_economics_api_has_no_hidden_spot_price_or_historical_mean():
    signature = inspect.signature(normalize_biological_segment)

    assert "spot_price" not in signature.parameters
    assert "historical_mean_price" not in signature.parameters
    assert "cycle_haircut" not in signature.parameters
    assert signature.parameters["normalized_unit_price"].default is inspect._empty
    assert signature.parameters["normalized_full_unit_cost"].default is inspect._empty


def test_aggregate_keeps_feed_or_processing_profit_separate_from_biological_segments():
    hog = normalize_biological_segment(
        segment_id="hog",
        normalized_output_units=100.0,
        normalized_unit_price=15.0,
        normalized_full_unit_cost=12.0,
    )
    chicken = normalize_biological_segment(
        segment_id="chicken",
        normalized_output_units=50.0,
        normalized_unit_price=12.0,
        normalized_full_unit_cost=10.0,
    )

    result = aggregate_biological_cycle_profit(
        segment_results=[hog, chicken],
        normalized_non_biological_profit=80.0,
        explicit_corporate_adjustment=-20.0,
    )

    assert result.normalized_biological_profit == pytest.approx(400.0)
    assert result.normalized_sustainable_profit == pytest.approx(460.0)
    assert result.status == "OK"


def test_aggregate_rejects_duplicate_segment_ids():
    first = normalize_biological_segment(
        segment_id="hog",
        normalized_output_units=100.0,
        normalized_unit_price=15.0,
        normalized_full_unit_cost=12.0,
    )
    second = normalize_biological_segment(
        segment_id="hog",
        normalized_output_units=50.0,
        normalized_unit_price=16.0,
        normalized_full_unit_cost=13.0,
    )

    result = aggregate_biological_cycle_profit(
        segment_results=[first, second],
        normalized_non_biological_profit=0.0,
    )

    assert result.normalized_sustainable_profit is None
    assert result.status == "DUPLICATE_BIOLOGICAL_SEGMENT_ID"


def test_aggregate_requires_explicit_non_biological_profit_even_if_zero():
    segment = normalize_biological_segment(
        segment_id="hog",
        normalized_output_units=100.0,
        normalized_unit_price=15.0,
        normalized_full_unit_cost=12.0,
    )
    signature = inspect.signature(aggregate_biological_cycle_profit)

    assert signature.parameters["normalized_non_biological_profit"].default is inspect._empty
    result = aggregate_biological_cycle_profit(
        segment_results=[segment],
        normalized_non_biological_profit=None,
    )
    assert result.status == "NON_BIOLOGICAL_NORMALIZED_PROFIT_UNAVAILABLE"


def test_reverse_implied_unit_margin_connects_market_implied_profit_to_unit_economics():
    margin, status = reverse_implied_unit_margin(
        implied_total_normalized_profit=500.0,
        normalized_non_biological_profit=80.0,
        other_biological_segment_profit=120.0,
        target_segment_output_units=100.0,
        explicit_corporate_adjustment=-20.0,
    )

    assert margin == pytest.approx((500.0 - 80.0 - 120.0 + 20.0) / 100.0)
    assert status == "OK"


def test_biological_evidence_separates_spot_price_from_normalized_price_and_cost():
    result = collect_biological_cycle_evidence(
        spot_sale_price=9.69,
        normalized_unit_price=15.0,
        full_unit_cost=11.6,
        unit_cost_change=-0.03,
        output_growth=0.05,
        breeding_inventory=311.3,
        biological_asset_impairment=20.0,
        slaughter_or_processing_volume_growth=0.20,
    )

    assert result.spot_sale_price == pytest.approx(9.69)
    assert result.normalized_unit_price == pytest.approx(15.0)
    assert result.full_unit_cost == pytest.approx(11.6)
    assert result.evidence_completeness == pytest.approx(8 / 12)
    assert "feed_raw_material_cost_change" in result.missing_fields
    assert not hasattr(result, "quality_score")
