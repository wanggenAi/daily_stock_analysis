import pytest

from src.strategies.genge_opportunity_discovery.share_class_market_cap import (
    aggregate_share_class_market_cap,
)


def test_dual_listed_company_uses_class_specific_prices_for_actual_market_cap():
    result = aggregate_share_class_market_cap(
        {
            "A": {"shares": 668.0, "price": 417.48, "fx_to_reporting_currency": 1.0},
            "H": {"shares": 33.2531, "price": 350.0, "fx_to_reporting_currency": 0.92},
        },
        reference_class="A",
    )

    expected_actual = 668.0 * 417.48 + 33.2531 * 350.0 * 0.92
    expected_a_implied = (668.0 + 33.2531) * 417.48
    assert result.consolidated_market_cap == pytest.approx(expected_actual)
    assert result.reference_class_implied_total_equity_value == pytest.approx(expected_a_implied)
    assert result.consolidated_market_cap != pytest.approx(expected_a_implied)
    assert result.status == "OK"


def test_missing_h_share_quote_does_not_mislabel_a_price_times_total_shares_as_actual_market_cap():
    result = aggregate_share_class_market_cap(
        {
            "A": {"shares": 668.0, "price": 417.48, "fx_to_reporting_currency": 1.0},
            "H": {"shares": 33.2531, "price": None, "fx_to_reporting_currency": None},
        },
        reference_class="A",
    )

    assert result.consolidated_market_cap is None
    assert result.reference_class_implied_total_equity_value == pytest.approx((668.0 + 33.2531) * 417.48)
    assert result.status == "INCOMPLETE_SHARE_CLASS_PRICING"


def test_missing_share_count_fails_closed():
    result = aggregate_share_class_market_cap(
        {"A": {"shares": None, "price": 100.0, "fx_to_reporting_currency": 1.0}},
        reference_class="A",
    )

    assert result.total_economic_shares is None
    assert result.consolidated_market_cap is None
    assert result.status == "SHARE_COUNT_INCOMPLETE"
