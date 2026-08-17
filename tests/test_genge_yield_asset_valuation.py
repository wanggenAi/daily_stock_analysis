import inspect

import pytest

from src.strategies.genge_opportunity_discovery.yield_asset_valuation import (
    collect_yield_asset_evidence,
    evaluate_dividend_coverage,
    reverse_implied_cost_of_equity,
    value_explicit_fcfe_stream,
    value_stable_yield_asset,
)


def test_explicit_fcfe_stream_has_no_implicit_terminal_value():
    result = value_explicit_fcfe_stream(
        annual_fcfe={1: 100.0, 2: 110.0, 3: 120.0},
        required_return=0.10,
        total_common_shares=10.0,
    )

    expected = 100.0 / 1.10 + 110.0 / (1.10**2) + 120.0 / (1.10**3)
    assert result.pv_explicit_fcfe == pytest.approx(expected)
    assert result.explicit_terminal_equity_value is None
    assert result.pv_terminal_equity_value is None
    assert result.fair_equity_value == pytest.approx(expected)
    assert result.fair_price == pytest.approx(expected / 10.0)


def test_explicit_terminal_value_is_discounted_from_last_forecast_year():
    result = value_explicit_fcfe_stream(
        annual_fcfe={1: 100.0, 2: 110.0, 3: 120.0},
        required_return=0.10,
        explicit_terminal_equity_value=1500.0,
    )

    expected_fcfe = 100.0 / 1.10 + 110.0 / (1.10**2) + 120.0 / (1.10**3)
    expected_terminal = 1500.0 / (1.10**3)
    assert result.pv_terminal_equity_value == pytest.approx(expected_terminal)
    assert result.fair_equity_value == pytest.approx(expected_fcfe + expected_terminal)


def test_explicit_fcfe_supports_finite_life_asset_with_zero_residual_value():
    result = value_explicit_fcfe_stream(
        annual_fcfe={1: 50.0, 2: 40.0},
        required_return=0.08,
        explicit_terminal_equity_value=0.0,
    )

    assert result.valuation_model_applicable is True
    assert result.pv_terminal_equity_value == pytest.approx(0.0)
    assert result.fair_equity_value == pytest.approx(50.0 / 1.08 + 40.0 / (1.08**2))


def test_stable_yield_asset_uses_explicit_gordon_fcfe_assumptions():
    result = value_stable_yield_asset(
        normalized_fcfe=100.0,
        cost_of_equity=0.08,
        long_term_growth=0.02,
        current_market_cap=1500.0,
        total_common_shares=10.0,
    )

    expected = 100.0 * 1.02 / (0.08 - 0.02)
    assert result.fair_equity_value == pytest.approx(expected)
    assert result.fair_price == pytest.approx(expected / 10.0)
    assert result.implied_cost_of_equity == pytest.approx(100.0 * 1.02 / 1500.0 + 0.02)
    assert result.margin_of_safety == pytest.approx(expected / 1500.0 - 1.0)
    assert result.status == "OK"


def test_stable_yield_asset_fails_closed_when_cost_of_equity_does_not_exceed_growth():
    result = value_stable_yield_asset(
        normalized_fcfe=100.0,
        cost_of_equity=0.02,
        long_term_growth=0.02,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.status == "INVALID_COST_OF_EQUITY_GROWTH_RELATION"


def test_reverse_implied_cost_of_equity_matches_gordon_identity():
    implied, status = reverse_implied_cost_of_equity(
        current_market_cap=1500.0,
        normalized_fcfe=100.0,
        long_term_growth=0.02,
    )

    assert implied == pytest.approx(100.0 * 1.02 / 1500.0 + 0.02)
    assert status == "OK"


def test_dividend_coverage_reports_raw_economics_without_safe_threshold():
    result = evaluate_dividend_coverage(normalized_fcfe=100.0, common_dividends=70.0)

    assert result.dividend_coverage_ratio == pytest.approx(100.0 / 70.0)
    assert result.payout_of_fcfe == pytest.approx(0.70)
    assert result.status == "OK"
    assert not hasattr(result, "safe_payout")


def test_utility_module_does_not_offer_raw_cfo_minus_capex_shortcut():
    stable_signature = inspect.signature(value_stable_yield_asset)
    explicit_signature = inspect.signature(value_explicit_fcfe_stream)

    assert "operating_cash_flow" not in stable_signature.parameters
    assert "capital_expenditure" not in stable_signature.parameters
    assert "operating_cash_flow" not in explicit_signature.parameters
    assert "capital_expenditure" not in explicit_signature.parameters
    assert "normalized_fcfe" in stable_signature.parameters


def test_yield_asset_evidence_keeps_maintenance_and_growth_capex_separate():
    result = collect_yield_asset_evidence(
        generation_or_volume_growth=0.05,
        realized_tariff_or_unit_revenue_change=-0.02,
        maintenance_capex=20.0,
        growth_capex=80.0,
        net_debt=500.0,
        normalized_fcfe=100.0,
    )

    assert result.maintenance_capex == pytest.approx(20.0)
    assert result.growth_capex == pytest.approx(80.0)
    assert result.evidence_completeness == pytest.approx(6 / 11)
    assert "fuel_unit_cost_change" in result.missing_fields
    assert not hasattr(result, "quality_score")
