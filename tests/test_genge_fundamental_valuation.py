import math

import pytest

from src.strategies.genge_opportunity_discovery.fundamental_valuation import (
    bridge_equity_value,
    build_three_scenario_valuation,
    normalize_core_earnings,
    normalize_cycle_earnings,
    reverse_implied_profit,
)


def test_reported_recurring_profit_prevents_fair_value_gain_from_becoming_core_earnings():
    result = normalize_core_earnings(
        net_profit=5.71,
        recurring_profit=1.02,
        fair_value_change_gain=4.48,
        operating_cash_flow=-5.20,
    )

    assert result.normalized_core_operating_profit == pytest.approx(1.02)
    assert result.normalization_method == "REPORTED_RECURRING_PROFIT"
    assert result.recurring_profit_ratio == pytest.approx(1.02 / 5.71)
    assert result.non_recurring_profit_share == pytest.approx(1.0 - 1.02 / 5.71)
    assert result.cash_conversion_ratio == pytest.approx(-5.20 / 1.02)
    assert result.earnings_quality_score < 50


def test_identified_non_operating_items_are_removed_when_recurring_profit_is_missing():
    result = normalize_core_earnings(
        net_profit=9.30,
        investment_income=4.995,
        fair_value_change_gain=0.544,
    )

    assert result.normalized_core_operating_profit == pytest.approx(3.761)
    assert result.normalization_method == "HEADLINE_LESS_IDENTIFIED_NON_OPERATING_ITEMS"
    assert result.earnings_quality_confidence == "LOW"


def test_cycle_profit_requires_explicit_normalization_instead_of_inventing_haircut():
    result = normalize_cycle_earnings(forward_cycle_profit=100.0, is_cyclical=True)

    assert result.forward_cycle_profit == 100.0
    assert result.through_cycle_normalized_profit is None
    assert result.peak_earnings_discount is None
    assert result.cycle_normalization_method == "CYCLE_NORMALIZATION_REQUIRED"
    assert result.cycle_valuation_confidence == "LOW"


def test_explicit_cycle_ratio_separates_forward_and_through_cycle_profit():
    result = normalize_cycle_earnings(
        forward_cycle_profit=100.0,
        through_cycle_ratio=0.60,
        is_cyclical=True,
    )

    assert result.through_cycle_normalized_profit == pytest.approx(60.0)
    assert result.cycle_profit_gap == pytest.approx(40.0)
    assert result.peak_earnings_discount == pytest.approx(0.40)
    assert result.cycle_valuation_confidence == "MEDIUM"


def test_non_operating_assets_are_preserved_in_equity_value_after_profit_normalization():
    result = bridge_equity_value(
        normalized_core_operating_profit=20.0,
        fair_multiple=25.0,
        non_operating_asset_value=80.0,
        net_cash_or_investment_adjustment=20.0,
        total_shares=10.0,
    )

    assert result.core_operating_value == pytest.approx(500.0)
    assert result.fair_equity_value == pytest.approx(600.0)
    assert result.fair_price == pytest.approx(60.0)
    assert result.valuation_model_status == "OK"


def test_reverse_valuation_subtracts_non_operating_assets_before_implied_profit():
    result = reverse_implied_profit(
        current_market_cap=600.0,
        assumed_fair_multiple=25.0,
        reference_normalized_profit=20.0,
        non_operating_asset_value=80.0,
        net_cash_or_investment_adjustment=20.0,
    )

    assert result.implied_core_operating_value == pytest.approx(500.0)
    assert result.implied_core_profit == pytest.approx(20.0)
    assert result.required_profit_growth == pytest.approx(0.0)
    assert result.expectation_gap == pytest.approx(0.0)
    assert result.status == "OK"


def test_negative_normalized_profit_does_not_force_pe_valuation():
    result = bridge_equity_value(
        normalized_core_operating_profit=-2.0,
        fair_multiple=20.0,
        non_operating_asset_value=50.0,
    )

    assert result.valuation_model_applicable is False
    assert result.valuation_model_status == "PE_MODEL_NOT_APPLICABLE"
    assert result.fair_equity_value is None
    assert result.fair_price is None


def test_nan_and_missing_data_fail_closed_without_fake_precision():
    quality = normalize_core_earnings(net_profit=float("nan"))
    cycle = normalize_cycle_earnings(forward_cycle_profit=float("nan"), is_cyclical=True)
    reverse = reverse_implied_profit(current_market_cap=None, assumed_fair_multiple=20.0)

    assert quality.normalized_core_operating_profit is None
    assert quality.earnings_quality_confidence == "LOW"
    assert cycle.forward_cycle_profit is None
    assert cycle.through_cycle_normalized_profit is None
    assert reverse.implied_core_profit is None
    assert reverse.status == "MARKET_CAP_UNAVAILABLE"


def test_three_scenario_valuation_uses_through_cycle_profit_and_reverse_base_case():
    result = build_three_scenario_valuation(
        scenarios={
            "bear": {
                "forward_cycle_profit": 80.0,
                "through_cycle_ratio": 0.50,
                "is_cyclical": True,
                "fair_multiple": 12.0,
                "non_operating_asset_value": 20.0,
            },
            "base": {
                "forward_cycle_profit": 100.0,
                "through_cycle_ratio": 0.60,
                "is_cyclical": True,
                "fair_multiple": 15.0,
                "non_operating_asset_value": 20.0,
            },
            "bull": {
                "forward_cycle_profit": 120.0,
                "through_cycle_ratio": 0.70,
                "is_cyclical": True,
                "fair_multiple": 18.0,
                "non_operating_asset_value": 20.0,
            },
        },
        current_market_cap=920.0,
        total_shares=10.0,
    )

    base = result["scenarios"]["base"]
    reverse = result["reverse_valuation"]

    assert base["through_cycle_normalized_profit"] == pytest.approx(60.0)
    assert base["normalized_core_operating_profit"] == pytest.approx(60.0)
    assert base["core_operating_value"] == pytest.approx(900.0)
    assert base["fair_equity_value"] == pytest.approx(920.0)
    assert base["fair_price"] == pytest.approx(92.0)
    assert base["upside_downside"] == pytest.approx(0.0)
    assert reverse["implied_core_profit"] == pytest.approx(60.0)
    assert reverse["required_profit_growth"] == pytest.approx(0.0)


def test_three_scenario_valuation_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing valuation scenarios"):
        build_three_scenario_valuation(
            scenarios={
                "bear": {"normalized_core_operating_profit": 1.0, "fair_multiple": 10.0},
                "base": {"normalized_core_operating_profit": 2.0, "fair_multiple": 12.0},
            }
        )


def test_invalid_ratio_does_not_create_cycle_profit():
    result = normalize_cycle_earnings(
        forward_cycle_profit=100.0,
        through_cycle_ratio=1.5,
        is_cyclical=True,
    )

    assert result.through_cycle_normalized_profit is None
    assert result.cycle_normalization_method == "CYCLE_NORMALIZATION_REQUIRED"
    assert result.cycle_valuation_confidence == "LOW"


def test_reverse_valuation_flags_assets_above_market_cap():
    result = reverse_implied_profit(
        current_market_cap=50.0,
        assumed_fair_multiple=20.0,
        non_operating_asset_value=80.0,
    )

    assert result.implied_core_operating_value == pytest.approx(-30.0)
    assert result.implied_core_profit is None
    assert result.required_profit_growth is None
    assert result.status == "NON_OPERATING_VALUE_EXCEEDS_MARKET_CAP"
