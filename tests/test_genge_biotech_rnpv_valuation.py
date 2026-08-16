import inspect

import pytest

from src.strategies.genge_opportunity_discovery.biotech_rnpv_valuation import (
    assess_financing_before_catalyst,
    bridge_biotech_equity_value,
    collect_biotech_quality_evidence,
    compute_cash_runway,
    evaluate_pe_applicability,
    value_probability_adjusted_asset,
)


def _asset(asset_id="asset-a", value_probability=0.5):
    return value_probability_adjusted_asset(
        asset_id=asset_id,
        success_contingent_cash_flows={1: 100.0, 2: 120.0},
        explicit_development_cash_flows={1: -20.0},
        probability_of_success=value_probability,
        economic_ownership=0.8,
        required_return=0.10,
    )


def test_pe_model_refuses_non_positive_normalized_sustainable_profit():
    negative = evaluate_pe_applicability(normalized_sustainable_profit=-1.4)
    zero = evaluate_pe_applicability(normalized_sustainable_profit=0.0)

    assert negative.pe_model_applicable is False
    assert negative.status == "PE_MODEL_NOT_APPLICABLE"
    assert zero.pe_model_applicable is False
    assert zero.status == "PE_MODEL_NOT_APPLICABLE"


def test_positive_profit_only_marks_pe_as_potentially_applicable_not_automatic_value():
    result = evaluate_pe_applicability(normalized_sustainable_profit=2.0)

    assert result.pe_model_applicable is True
    assert result.status == "PE_MODEL_POTENTIALLY_APPLICABLE"


def test_asset_rnpv_discounts_cash_flows_and_applies_explicit_probability_and_ownership():
    result = _asset()

    pv_success = 100.0 / 1.10 + 120.0 / (1.10**2)
    pv_development = -20.0 / 1.10
    expected_commercial = pv_success * 0.5 * 0.8
    expected_asset = expected_commercial + pv_development * 0.8

    assert result.valuation_model_applicable is True
    assert result.pv_success_contingent_cash_flows == pytest.approx(pv_success)
    assert result.pv_explicit_development_cash_flows == pytest.approx(pv_development)
    assert result.probability_adjusted_commercial_value == pytest.approx(expected_commercial)
    assert result.risk_adjusted_asset_value == pytest.approx(expected_asset)
    assert result.status == "OK"


def test_development_cash_flows_are_not_multiplied_by_terminal_success_probability():
    low_probability = value_probability_adjusted_asset(
        asset_id="asset-low",
        success_contingent_cash_flows={1: 100.0},
        explicit_development_cash_flows={1: -20.0},
        probability_of_success=0.20,
        economic_ownership=1.0,
        required_return=0.10,
    )
    high_probability = value_probability_adjusted_asset(
        asset_id="asset-high",
        success_contingent_cash_flows={1: 100.0},
        explicit_development_cash_flows={1: -20.0},
        probability_of_success=0.80,
        economic_ownership=1.0,
        required_return=0.10,
    )

    assert low_probability.pv_explicit_development_cash_flows == pytest.approx(
        high_probability.pv_explicit_development_cash_flows
    )
    assert low_probability.probability_adjusted_commercial_value < high_probability.probability_adjusted_commercial_value


def test_approved_commercial_asset_can_use_probability_one_without_special_hidden_rule():
    result = value_probability_adjusted_asset(
        asset_id="approved-product-base-market",
        success_contingent_cash_flows={1: 50.0, 2: 45.0},
        explicit_development_cash_flows={},
        probability_of_success=1.0,
        economic_ownership=1.0,
        required_return=0.10,
    )

    assert result.probability_adjusted_commercial_value == pytest.approx(
        50.0 / 1.10 + 45.0 / (1.10**2)
    )
    assert result.status == "OK"


def test_success_probability_ownership_and_required_return_are_required_explicit_inputs():
    signature = inspect.signature(value_probability_adjusted_asset)

    assert signature.parameters["probability_of_success"].default is inspect._empty
    assert signature.parameters["economic_ownership"].default is inspect._empty
    assert signature.parameters["required_return"].default is inspect._empty


def test_missing_or_invalid_success_probability_fails_closed():
    missing = value_probability_adjusted_asset(
        asset_id="a",
        success_contingent_cash_flows={1: 100.0},
        explicit_development_cash_flows={},
        probability_of_success=None,
        economic_ownership=1.0,
        required_return=0.10,
    )
    invalid = value_probability_adjusted_asset(
        asset_id="a",
        success_contingent_cash_flows={1: 100.0},
        explicit_development_cash_flows={},
        probability_of_success=1.2,
        economic_ownership=1.0,
        required_return=0.10,
    )

    assert missing.valuation_model_applicable is False
    assert missing.status == "INVALID_OR_MISSING_SUCCESS_PROBABILITY"
    assert invalid.valuation_model_applicable is False
    assert invalid.status == "INVALID_OR_MISSING_SUCCESS_PROBABILITY"


def test_cash_runway_uses_normalized_annual_burn():
    result = compute_cash_runway(
        liquid_resources=32.0,
        debt_or_restricted_resources=8.0,
        normalized_annual_cash_burn=6.0,
    )

    assert result.net_liquid_resources == pytest.approx(24.0)
    assert result.runway_years == pytest.approx(4.0)
    assert result.runway_months == pytest.approx(48.0)
    assert result.status == "OK"


def test_one_profitable_or_cash_positive_quarter_does_not_create_infinite_runway():
    result = compute_cash_runway(
        liquid_resources=32.0,
        debt_or_restricted_resources=8.0,
        normalized_annual_cash_burn=0.0,
    )

    assert result.runway_years is None
    assert result.runway_months is None
    assert result.status == "NORMALIZED_ANNUAL_BURN_NOT_POSITIVE_OR_UNAVAILABLE"


def test_financing_risk_requires_explicit_catalyst_buffer_and_flags_short_runway():
    result = assess_financing_before_catalyst(
        runway_years=1.5,
        catalyst_horizon_years=1.3,
        explicit_buffer_years=0.5,
    )

    assert result.required_runway_years == pytest.approx(1.8)
    assert result.runway_gap_years == pytest.approx(-0.3)
    assert result.financing_before_catalyst_likely is True
    assert result.status == "OK"


def test_financing_buffer_has_no_hidden_default():
    signature = inspect.signature(assess_financing_before_catalyst)

    assert signature.parameters["explicit_buffer_years"].default is inspect._empty


def test_equity_bridge_sums_unique_asset_rnpvs_and_balance_sheet_resources():
    first = _asset("asset-a", 0.5)
    second = _asset("asset-b", 0.7)

    result = bridge_biotech_equity_value(
        asset_results=[first, second],
        liquid_resources=30.0,
        debt=5.0,
        corporate_overhead_pv=10.0,
        explicit_equity_adjustment=2.0,
        current_market_cap=100.0,
        total_common_shares=10.0,
    )

    expected_assets = first.risk_adjusted_asset_value + second.risk_adjusted_asset_value
    expected_equity = expected_assets + 30.0 - 5.0 - 10.0 + 2.0
    assert result.total_asset_rnpv == pytest.approx(expected_assets)
    assert result.fair_equity_value == pytest.approx(expected_equity)
    assert result.fair_price == pytest.approx(expected_equity / 10.0)
    assert result.margin_of_safety == pytest.approx(expected_equity / 100.0 - 1.0)
    assert result.status == "OK"


def test_equity_bridge_rejects_duplicate_asset_ids_to_catch_obvious_double_counting():
    first = _asset("same-scope")
    second = _asset("same-scope")

    result = bridge_biotech_equity_value(
        asset_results=[first, second],
        liquid_resources=30.0,
        debt=5.0,
        corporate_overhead_pv=10.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.status == "DUPLICATE_ASSET_ID"


def test_equity_bridge_rejects_incomplete_asset_value():
    incomplete = value_probability_adjusted_asset(
        asset_id="incomplete",
        success_contingent_cash_flows={1: 100.0},
        explicit_development_cash_flows={},
        probability_of_success=None,
        economic_ownership=1.0,
        required_return=0.10,
    )

    result = bridge_biotech_equity_value(
        asset_results=[incomplete],
        liquid_resources=30.0,
        debt=5.0,
        corporate_overhead_pv=10.0,
    )

    assert result.valuation_model_applicable is False
    assert result.status == "ASSET_VALUATION_INCOMPLETE"


def test_biotech_quality_evidence_preserves_raw_fields_without_magic_score():
    result = collect_biotech_quality_evidence(
        commercial_product_growth=0.38,
        commercial_gross_margin=0.83,
        normalized_recurring_profit=-9.9,
        normalized_annual_cash_burn=5.2,
        research_and_development_intensity=0.537,
        approved_indication_count=12,
    )

    assert result.evidence_completeness == pytest.approx(6 / 9)
    assert "partnership_or_royalty_share" in result.missing_fields
    assert not hasattr(result, "quality_score")
