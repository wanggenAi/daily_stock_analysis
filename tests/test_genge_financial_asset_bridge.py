import pytest

from src.strategies.genge_opportunity_discovery.financial_asset_bridge import (
    normalize_profit_for_financial_asset_bridge,
)


def test_asset_bridge_removes_after_tax_financial_income_and_adds_back_interest_cost():
    result = normalize_profit_for_financial_asset_bridge(
        normalized_equity_profit=10.0,
        interest_income=1.0,
        interest_expense=0.4,
        recurring_investment_income=0.2,
        effective_tax_rate=0.25,
    )

    assert result.after_tax_financial_income_removed == pytest.approx(0.9)
    assert result.after_tax_financing_cost_added_back == pytest.approx(0.3)
    assert result.asset_bridge_profit == pytest.approx(9.4)
    assert result.status == "OK"


def test_plain_equity_profit_is_not_auto_adjusted_without_tax_rate():
    result = normalize_profit_for_financial_asset_bridge(
        normalized_equity_profit=10.0,
        interest_income=1.0,
    )

    assert result.asset_bridge_profit is None
    assert result.status == "TAX_RATE_REQUIRED_FOR_ASSET_BRIDGE"


def test_missing_financial_income_components_fail_closed():
    result = normalize_profit_for_financial_asset_bridge(
        normalized_equity_profit=10.0,
        effective_tax_rate=0.20,
    )

    assert result.asset_bridge_profit is None
    assert result.status == "FINANCIAL_INCOME_DETAIL_REQUIRED"


def test_partial_components_are_explicitly_flagged_not_silently_claimed_complete():
    result = normalize_profit_for_financial_asset_bridge(
        normalized_equity_profit=10.0,
        interest_income=1.0,
        effective_tax_rate=0.20,
    )

    assert result.asset_bridge_profit == pytest.approx(9.2)
    assert "interest_expense_missing_treated_as_zero" in result.warning_flags
    assert "recurring_investment_income_missing_treated_as_zero" in result.warning_flags


def test_missing_profit_fails_closed():
    result = normalize_profit_for_financial_asset_bridge(
        normalized_equity_profit=None,
        interest_income=1.0,
        effective_tax_rate=0.20,
    )

    assert result.asset_bridge_profit is None
    assert result.status == "EQUITY_PROFIT_UNAVAILABLE"
