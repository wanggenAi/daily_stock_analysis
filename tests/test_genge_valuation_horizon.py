import math

from src.strategies.genge_opportunity_discovery.valuation_horizon import (
    CURRENT_FORWARD_PE,
    TERMINAL_PE,
    required_terminal_profit,
    value_profit_at_horizon,
)


def test_current_forward_pe_is_not_double_discounted():
    result = value_profit_at_horizon(
        profit=100.0,
        pe_multiple=25.0,
        horizon_years=2,
        required_return=0.12,
        multiple_semantics=CURRENT_FORWARD_PE,
    )
    assert result.status == "OK_CURRENT_FORWARD_MULTIPLE"
    assert result.present_equity_value == 2500.0
    assert result.discount_factor == 1.0


def test_terminal_pe_requires_discounting():
    result = value_profit_at_horizon(
        profit=100.0,
        pe_multiple=25.0,
        horizon_years=2,
        required_return=0.10,
        multiple_semantics=TERMINAL_PE,
    )
    assert result.status == "OK_TERMINAL_DISCOUNTED"
    assert math.isclose(result.horizon_equity_value, 2500.0)
    assert math.isclose(result.present_equity_value, 2500.0 / 1.21)


def test_terminal_pe_fails_closed_without_required_return():
    result = value_profit_at_horizon(
        profit=100.0,
        pe_multiple=25.0,
        horizon_years=2,
        multiple_semantics=TERMINAL_PE,
    )
    assert result.status == "REQUIRED_RETURN_REQUIRED"
    assert result.present_equity_value is None


def test_required_terminal_profit_and_growth_are_reverse_solved():
    result = required_terminal_profit(
        current_market_cap=2500.0,
        terminal_pe=25.0,
        horizon_years=2,
        required_return=0.10,
        current_normalized_profit=70.0,
    )
    assert result.status == "OK"
    assert math.isclose(result.required_terminal_equity_value, 3025.0)
    assert math.isclose(result.required_terminal_profit, 121.0)
    expected_cagr = (121.0 / 70.0) ** 0.5 - 1.0
    assert math.isclose(result.required_profit_cagr, expected_cagr)


def test_required_terminal_profit_rejects_missing_market_cap():
    result = required_terminal_profit(
        current_market_cap=None,
        terminal_pe=25.0,
        horizon_years=2,
        required_return=0.10,
    )
    assert result.status == "MARKET_CAP_UNAVAILABLE"
    assert result.required_terminal_profit is None
