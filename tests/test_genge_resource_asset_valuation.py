import math

from src.strategies.genge_opportunity_discovery.resource_asset_valuation import (
    bridge_resource_equity_nav,
    build_resource_asset_evidence,
    value_finite_life_resource_asset,
)


def _asset(**overrides):
    params = {
        "asset_id": "tungsten-mine-a",
        "economic_scope_id": "mine-a-100pct",
        "economic_ownership": 0.8,
        "recoverable_units_100pct": 250.0,
        "annual_production_units_100pct": 100.0,
        "normalized_realized_unit_price": 10.0,
        "unit_cash_operating_cost": 4.0,
        "sustaining_capex_per_unit": 1.0,
        "royalty_rate_on_revenue": 0.1,
        "cash_tax_rate_on_positive_pretax_cash_flow": 0.25,
        "required_return": 0.1,
        "closure_and_reclamation_cash_outflow_100pct": 30.0,
    }
    params.update(overrides)
    return value_finite_life_resource_asset(**params)


def test_resource_nav_depletes_finite_recoverable_units_without_terminal_value():
    result = _asset()

    # Unit pre-tax cash flow before closure:
    # 10 - 4 - 1 - 10*10% = 4; after 25% tax = 3.
    # Production schedule is 100, 100, 50 units; closure outflow 30 in year 3.
    expected = 300.0 / 1.1 + 300.0 / (1.1**2) + 120.0 / (1.1**3)

    assert result.status == "OK"
    assert result.modeled_years == 3
    assert math.isclose(result.pv_100pct_resource_cash_flows, expected)
    assert math.isclose(result.attributable_resource_nav, expected * 0.8)
    assert result.valuation_model_applicable is True


def test_partial_final_year_does_not_round_reserves_up_to_full_year_production():
    result = _asset(
        recoverable_units_100pct=150.0,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )

    expected = 300.0 / 1.1 + 150.0 / (1.1**2)

    assert result.modeled_years == 2
    assert math.isclose(result.pv_100pct_resource_cash_flows, expected)


def test_negative_resource_economics_are_not_silently_floored_to_zero():
    result = _asset(
        normalized_realized_unit_price=4.0,
        unit_cash_operating_cost=4.0,
        sustaining_capex_per_unit=1.0,
        royalty_rate_on_revenue=0.0,
        cash_tax_rate_on_positive_pretax_cash_flow=0.25,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )

    assert result.status == "OK"
    assert result.pv_100pct_resource_cash_flows < 0
    assert result.attributable_resource_nav < 0


def test_cash_tax_applies_only_to_positive_asset_pretax_cash_flow():
    positive = _asset(
        recoverable_units_100pct=100.0,
        annual_production_units_100pct=100.0,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )
    negative = _asset(
        recoverable_units_100pct=100.0,
        annual_production_units_100pct=100.0,
        normalized_realized_unit_price=4.0,
        unit_cash_operating_cost=5.0,
        sustaining_capex_per_unit=0.0,
        royalty_rate_on_revenue=0.0,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )

    assert math.isclose(positive.pv_100pct_resource_cash_flows, 300.0 / 1.1)
    assert math.isclose(negative.pv_100pct_resource_cash_flows, -100.0 / 1.1)


def test_resource_asset_fails_closed_when_recoverable_units_are_missing():
    result = _asset(recoverable_units_100pct=None)

    assert result.status == "RECOVERABLE_UNITS_UNAVAILABLE"
    assert result.valuation_model_applicable is False
    assert result.attributable_resource_nav is None


def test_resource_asset_rejects_invalid_ownership_and_rates():
    ownership = _asset(economic_ownership=1.2)
    royalty = _asset(royalty_rate_on_revenue=-0.01)
    tax = _asset(cash_tax_rate_on_positive_pretax_cash_flow=1.01)
    negative_discount = _asset(required_return=-0.01)

    assert ownership.status == "INVALID_OR_MISSING_ECONOMIC_OWNERSHIP"
    assert royalty.status == "INVALID_OR_MISSING_ROYALTY_RATE"
    assert tax.status == "INVALID_OR_MISSING_CASH_TAX_RATE"
    assert negative_discount.status == "INVALID_OR_MISSING_REQUIRED_RETURN"


def test_zero_required_return_is_allowed_when_explicitly_researched():
    result = _asset(required_return=0.0)

    assert result.status == "OK"
    assert result.valuation_model_applicable is True


def test_corporate_bridge_combines_resource_nav_with_non_overlapping_downstream_value():
    mine = _asset(
        economic_ownership=1.0,
        recoverable_units_100pct=100.0,
        annual_production_units_100pct=100.0,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )
    result = bridge_resource_equity_nav(
        resource_asset_results=[mine],
        non_resource_segment_value=500.0,
        unrestricted_cash=100.0,
        interest_bearing_debt_not_in_resource_cash_flows=150.0,
        other_corporate_liability_pv_not_in_resource_cash_flows=20.0,
        explicit_equity_adjustment=10.0,
        current_market_cap=600.0,
        total_common_shares=100.0,
    )

    expected_equity = (
        mine.attributable_resource_nav + 500.0 + 100.0 - 150.0 - 20.0 + 10.0
    )

    assert result.status == "OK"
    assert math.isclose(result.fair_equity_nav, expected_equity)
    assert math.isclose(result.fair_nav_per_share, expected_equity / 100.0)
    assert math.isclose(
        result.margin_of_safety,
        (expected_equity - 600.0) / expected_equity,
    )


def test_corporate_bridge_rejects_duplicate_resource_economic_scope():
    first = _asset(asset_id="mine-a")
    second = _asset(asset_id="mine-b")

    result = bridge_resource_equity_nav(
        resource_asset_results=[first, second],
        non_resource_segment_value=0.0,
        unrestricted_cash=0.0,
        interest_bearing_debt_not_in_resource_cash_flows=0.0,
        other_corporate_liability_pv_not_in_resource_cash_flows=0.0,
    )

    assert result.status == "DUPLICATE_RESOURCE_ECONOMIC_SCOPE"
    assert result.valuation_model_applicable is False


def test_corporate_bridge_requires_explicit_non_resource_segment_value():
    result = bridge_resource_equity_nav(
        resource_asset_results=[_asset()],
        non_resource_segment_value=None,
        unrestricted_cash=0.0,
        interest_bearing_debt_not_in_resource_cash_flows=0.0,
        other_corporate_liability_pv_not_in_resource_cash_flows=0.0,
    )

    assert result.status == "NON_RESOURCE_SEGMENT_VALUE_UNAVAILABLE"
    assert result.fair_equity_nav is None


def test_non_positive_equity_nav_does_not_report_margin_of_safety():
    mine = _asset(
        normalized_realized_unit_price=1.0,
        unit_cash_operating_cost=4.0,
        sustaining_capex_per_unit=1.0,
        royalty_rate_on_revenue=0.0,
        cash_tax_rate_on_positive_pretax_cash_flow=0.25,
        closure_and_reclamation_cash_outflow_100pct=0.0,
    )
    result = bridge_resource_equity_nav(
        resource_asset_results=[mine],
        non_resource_segment_value=0.0,
        unrestricted_cash=0.0,
        interest_bearing_debt_not_in_resource_cash_flows=0.0,
        other_corporate_liability_pv_not_in_resource_cash_flows=0.0,
        current_market_cap=100.0,
    )

    assert result.fair_equity_nav < 0
    assert result.margin_of_safety is None


def test_resource_evidence_reports_all_valuation_critical_missing_inputs():
    evidence = build_resource_asset_evidence(
        reported_resource_units=1000.0,
        recoverable_units_used_in_model=700.0,
        normalized_annual_production_units=70.0,
        normalized_realized_unit_price=10.0,
        economic_ownership=0.8,
    )

    assert evidence.evidence_completeness == 4 / 10
    assert evidence.missing_fields == (
        "normalized_unit_cash_operating_cost",
        "sustaining_capex_per_unit",
        "royalty_rate_on_revenue",
        "cash_tax_rate_on_positive_pretax_cash_flow",
        "required_return",
        "closure_and_reclamation_cash_outflow_100pct",
    )
    assert evidence.reported_resource_units == 1000.0
    assert evidence.reported_reserve_units is None


def test_resource_evidence_is_complete_only_when_full_nav_deck_is_present():
    evidence = build_resource_asset_evidence(
        recoverable_units_used_in_model=700.0,
        normalized_annual_production_units=70.0,
        normalized_realized_unit_price=10.0,
        normalized_unit_cash_operating_cost=4.0,
        sustaining_capex_per_unit=1.0,
        economic_ownership=0.8,
        royalty_rate_on_revenue=0.08,
        cash_tax_rate_on_positive_pretax_cash_flow=0.25,
        required_return=0.10,
        closure_and_reclamation_cash_outflow_100pct=30.0,
    )

    assert evidence.evidence_completeness == 1.0
    assert evidence.missing_fields == ()
