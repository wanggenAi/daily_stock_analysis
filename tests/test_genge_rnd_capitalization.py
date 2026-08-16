import pytest

from src.strategies.genge_opportunity_discovery.rnd_capitalization import (
    assess_r_and_d_capitalization,
)


def test_large_capitalization_jump_is_flagged_without_automatic_profit_restatement():
    result = assess_r_and_d_capitalization(
        total_r_and_d_investment=1_268_199_698.15,
        r_and_d_expense=936_123_237.05,
        capitalized_r_and_d=332_076_461.10,
        net_profit=1_331_383_095.29,
        baseline_capitalization_rate=0.0563,
    )

    assert result.capitalization_rate == pytest.approx(0.2618, rel=1e-3)
    assert result.capitalization_rate_change > 0.20
    assert result.capitalized_r_and_d_to_net_profit > 0.20
    assert result.normalized_net_profit is None
    assert result.after_tax_profit_adjustment is None
    assert "r_and_d_capitalization_rate_jump_large" in result.warning_flags
    assert "capitalized_r_and_d_material_vs_net_profit" in result.warning_flags
    assert result.earnings_quality_penalty >= 40


def test_explicit_baseline_and_tax_rate_can_produce_auditable_stress_adjustment():
    result = assess_r_and_d_capitalization(
        total_r_and_d_investment=1_268_199_698.15,
        r_and_d_expense=936_123_237.05,
        capitalized_r_and_d=332_076_461.10,
        net_profit=1_331_383_095.29,
        baseline_capitalization_rate=0.0563,
        effective_tax_rate=0.15,
    )

    baseline_amount = 1_268_199_698.15 * 0.0563
    excess = 332_076_461.10 - baseline_amount
    expected_after_tax_adjustment = excess * 0.85

    assert result.excess_capitalized_r_and_d_vs_baseline == pytest.approx(excess)
    assert result.after_tax_profit_adjustment == pytest.approx(expected_after_tax_adjustment)
    assert result.normalized_net_profit == pytest.approx(1_331_383_095.29 - expected_after_tax_adjustment)


def test_capitalized_amount_can_be_derived_but_confidence_is_capped():
    result = assess_r_and_d_capitalization(
        total_r_and_d_investment=100.0,
        r_and_d_expense=80.0,
        net_profit=50.0,
    )

    assert result.capitalized_r_and_d == pytest.approx(20.0)
    assert result.capitalization_rate == pytest.approx(0.20)
    assert result.confidence == "MEDIUM"
    assert "capitalized_r_and_d_derived_from_total_less_expense" in result.warning_flags


def test_missing_baseline_never_invents_excess_capitalization_adjustment():
    result = assess_r_and_d_capitalization(
        total_r_and_d_investment=100.0,
        capitalized_r_and_d=30.0,
        net_profit=40.0,
        effective_tax_rate=0.15,
    )

    assert result.baseline_capitalization_rate is None
    assert result.excess_capitalized_r_and_d_vs_baseline is None
    assert result.normalized_net_profit is None


def test_invalid_rates_fail_closed():
    result = assess_r_and_d_capitalization(
        total_r_and_d_investment=100.0,
        capitalized_r_and_d=20.0,
        net_profit=50.0,
        baseline_capitalization_rate=1.2,
        effective_tax_rate=-0.1,
    )

    assert result.baseline_capitalization_rate is None
    assert result.normalized_net_profit is None
    assert "invalid_baseline_capitalization_rate" in result.warning_flags
    assert "invalid_effective_tax_rate" in result.warning_flags
