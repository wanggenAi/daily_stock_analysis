import inspect

import pytest

from src.strategies.genge_opportunity_discovery.consumer_compounder_valuation import (
    build_compounder_three_scenario_valuation,
    collect_compounder_quality_evidence,
    derive_owner_earnings,
    evaluate_growth_consistency,
    reverse_implied_near_term_growth,
    value_compounder_dcf,
)


def test_owner_earnings_uses_raw_cfo_less_capex_when_scope_is_reliable():
    result = derive_owner_earnings(
        operating_cash_flow=120.0,
        capital_expenditure=20.0,
        reference_normalized_profit=95.0,
        cash_flow_scope_reliable=True,
    )

    assert result.raw_owner_earnings == pytest.approx(100.0)
    assert result.normalized_owner_earnings == pytest.approx(100.0)
    assert result.owner_earnings_conversion == pytest.approx(100.0 / 95.0)
    assert result.status == "RAW_CFO_LESS_CAPEX"


def test_cash_flow_scope_distortion_fails_closed_without_explicit_adjustment():
    result = derive_owner_earnings(
        operating_cash_flow=120.0,
        capital_expenditure=20.0,
        reference_normalized_profit=95.0,
        cash_flow_scope_reliable=False,
    )

    assert result.raw_owner_earnings == pytest.approx(100.0)
    assert result.normalized_owner_earnings is None
    assert result.owner_earnings_conversion is None
    assert result.status == "CASH_FLOW_SCOPE_DISTORTED_REQUIRES_ADJUSTMENT"


def test_explicit_adjusted_owner_earnings_can_override_unreliable_raw_scope():
    result = derive_owner_earnings(
        operating_cash_flow=120.0,
        capital_expenditure=20.0,
        reference_normalized_profit=95.0,
        cash_flow_scope_reliable=False,
        explicit_adjusted_owner_earnings=90.0,
    )

    assert result.normalized_owner_earnings == pytest.approx(90.0)
    assert result.owner_earnings_conversion == pytest.approx(90.0 / 95.0)
    assert result.status == "EXPLICIT_ADJUSTED_OWNER_EARNINGS"


def test_compounder_dcf_matches_explicit_two_stage_cash_flow_math():
    result = value_compounder_dcf(
        normalized_owner_earnings=100.0,
        near_term_growth_rate=0.05,
        growth_years=3,
        required_return=0.10,
        terminal_growth_rate=0.03,
        explicit_non_operating_equity_adjustment=20.0,
        total_common_shares=10.0,
        current_market_cap=1500.0,
    )

    y1 = 100.0 * 1.05
    y2 = y1 * 1.05
    y3 = y2 * 1.05
    pv_explicit = y1 / 1.10 + y2 / (1.10**2) + y3 / (1.10**3)
    terminal_owner_earnings = y3 * 1.03
    terminal_value = terminal_owner_earnings / (0.10 - 0.03)
    pv_terminal = terminal_value / (1.10**3)
    fair_equity = pv_explicit + pv_terminal + 20.0

    assert result.valuation_model_applicable is True
    assert result.pv_explicit_owner_earnings == pytest.approx(pv_explicit)
    assert result.terminal_owner_earnings == pytest.approx(terminal_owner_earnings)
    assert result.terminal_value_at_horizon == pytest.approx(terminal_value)
    assert result.pv_terminal_value == pytest.approx(pv_terminal)
    assert result.fair_equity_value == pytest.approx(fair_equity)
    assert result.fair_price == pytest.approx(fair_equity / 10.0)
    assert result.margin_of_safety == pytest.approx(fair_equity / 1500.0 - 1.0)


def test_compounder_dcf_fails_closed_when_required_return_does_not_exceed_terminal_growth():
    result = value_compounder_dcf(
        normalized_owner_earnings=100.0,
        near_term_growth_rate=0.05,
        growth_years=5,
        required_return=0.03,
        terminal_growth_rate=0.03,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.status == "INVALID_REQUIRED_RETURN_TERMINAL_GROWTH_RELATION"


def test_compounder_dcf_requires_explicit_growth_duration():
    result = value_compounder_dcf(
        normalized_owner_earnings=100.0,
        near_term_growth_rate=0.05,
        growth_years=None,
        required_return=0.10,
        terminal_growth_rate=0.03,
    )

    assert result.valuation_model_applicable is False
    assert result.status == "INVALID_GROWTH_DURATION"


def test_reverse_implied_growth_recovers_growth_used_to_create_market_value():
    original = value_compounder_dcf(
        normalized_owner_earnings=100.0,
        near_term_growth_rate=0.07,
        growth_years=5,
        required_return=0.10,
        terminal_growth_rate=0.03,
        explicit_non_operating_equity_adjustment=50.0,
    )
    assert original.fair_equity_value is not None

    implied, status = reverse_implied_near_term_growth(
        current_market_cap=original.fair_equity_value,
        normalized_owner_earnings=100.0,
        growth_years=5,
        required_return=0.10,
        terminal_growth_rate=0.03,
        lower_growth_bound=-0.05,
        upper_growth_bound=0.20,
        explicit_non_operating_equity_adjustment=50.0,
    )

    assert status == "OK"
    assert implied == pytest.approx(0.07, abs=1e-7)


def test_reverse_implied_growth_requires_caller_supplied_bracket_that_contains_solution():
    implied, status = reverse_implied_near_term_growth(
        current_market_cap=5000.0,
        normalized_owner_earnings=100.0,
        growth_years=5,
        required_return=0.10,
        terminal_growth_rate=0.03,
        lower_growth_bound=-0.05,
        upper_growth_bound=0.02,
    )

    assert implied is None
    assert status == "IMPLIED_GROWTH_NOT_BRACKETED"


def test_reverse_growth_api_does_not_hide_universal_growth_bounds():
    signature = inspect.signature(reverse_implied_near_term_growth)

    assert signature.parameters["lower_growth_bound"].default is inspect._empty
    assert signature.parameters["upper_growth_bound"].default is inspect._empty


def test_growth_consistency_uses_roic_times_reinvestment_identity():
    result = evaluate_growth_consistency(
        core_roic=0.25,
        reinvestment_rate=0.30,
        scenario_growth_rate=0.10,
    )

    assert result.roic_implied_sustainable_growth == pytest.approx(0.075)
    assert result.growth_consistency_gap == pytest.approx(0.025)
    assert result.status == "OK"


def test_compounder_quality_evidence_preserves_raw_fields_without_magic_score():
    result = collect_compounder_quality_evidence(
        recurring_profit_growth=0.10,
        organic_revenue_growth=0.08,
        gross_margin=0.42,
        core_roic=0.22,
        owner_earnings_conversion=0.95,
    )

    assert result.evidence_completeness == pytest.approx(5 / 11, abs=1e-6)
    assert "channel_inventory_change" in result.missing_fields
    assert not hasattr(result, "quality_score")


def test_three_scenario_compounder_builder_requires_explicit_growth_and_duration_per_scenario():
    result = build_compounder_three_scenario_valuation(
        normalized_owner_earnings=100.0,
        current_market_cap=1600.0,
        scenarios={
            "bear": {
                "near_term_growth_rate": 0.00,
                "growth_years": 3,
                "required_return": 0.11,
                "terminal_growth_rate": 0.02,
            },
            "base": {
                "near_term_growth_rate": 0.05,
                "growth_years": 5,
                "required_return": 0.10,
                "terminal_growth_rate": 0.03,
            },
            "bull": {
                "near_term_growth_rate": 0.09,
                "growth_years": 7,
                "required_return": 0.09,
                "terminal_growth_rate": 0.03,
            },
        },
    )

    assert result["scenarios"]["bear"]["fair_equity_value"] < result["scenarios"]["base"]["fair_equity_value"]
    assert result["scenarios"]["base"]["fair_equity_value"] < result["scenarios"]["bull"]["fair_equity_value"]


def test_three_scenario_compounder_builder_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing compounder valuation scenarios"):
        build_compounder_three_scenario_valuation(
            normalized_owner_earnings=100.0,
            scenarios={
                "bear": {
                    "near_term_growth_rate": 0.00,
                    "growth_years": 3,
                    "required_return": 0.11,
                    "terminal_growth_rate": 0.02,
                },
                "base": {
                    "near_term_growth_rate": 0.05,
                    "growth_years": 5,
                    "required_return": 0.10,
                    "terminal_growth_rate": 0.03,
                },
            },
        )
