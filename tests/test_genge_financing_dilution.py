import pytest

from src.strategies.genge_opportunity_discovery.financing_dilution import (
    bridge_primary_financing_dilution,
)


def test_primary_financing_adds_net_proceeds_before_recomputing_per_share_value():
    result = bridge_primary_financing_dilution(
        pre_financing_equity_value=1_000.0,
        current_shares=100.0,
        financing_shares=10.0,
        issue_price=8.0,
    )

    assert result.pre_financing_fair_price == pytest.approx(10.0)
    assert result.derived_gross_proceeds == pytest.approx(80.0)
    assert result.net_proceeds_used == pytest.approx(80.0)
    assert result.post_financing_equity_value == pytest.approx(1_080.0)
    assert result.post_financing_shares == pytest.approx(110.0)
    assert result.post_financing_fair_price == pytest.approx(1_080.0 / 110.0)
    assert result.per_share_impact == pytest.approx((1_080.0 / 110.0) / 10.0 - 1.0)
    assert result.status == "OK"


def test_financing_shares_without_issue_price_or_net_proceeds_fail_closed():
    result = bridge_primary_financing_dilution(
        pre_financing_equity_value=1_000.0,
        current_shares=100.0,
        financing_shares=10.0,
    )

    assert result.post_financing_shares == pytest.approx(110.0)
    assert result.post_financing_fair_price is None
    assert result.status == "FINANCING_PROCEEDS_REQUIRED"


def test_explicit_net_proceeds_take_priority_over_issue_price_approximation():
    result = bridge_primary_financing_dilution(
        pre_financing_equity_value=1_000.0,
        current_shares=100.0,
        financing_shares=10.0,
        net_proceeds=72.0,
        issue_price=8.0,
        financing_costs=8.0,
    )

    assert result.derived_gross_proceeds == pytest.approx(80.0)
    assert result.net_proceeds_used == pytest.approx(72.0)
    assert result.post_financing_equity_value == pytest.approx(1_072.0)


def test_zero_financing_shares_preserve_value_per_share():
    result = bridge_primary_financing_dilution(
        pre_financing_equity_value=1_000.0,
        current_shares=100.0,
        financing_shares=0.0,
    )

    assert result.post_financing_equity_value == pytest.approx(1_000.0)
    assert result.post_financing_shares == pytest.approx(100.0)
    assert result.post_financing_fair_price == pytest.approx(10.0)
    assert result.per_share_impact == pytest.approx(0.0)
    assert result.status == "OK"
