import pytest

from src.strategies.genge_opportunity_discovery.share_dilution import (
    eps_from_profit,
    per_share_value,
    resolve_valuation_shares,
)


def test_explicit_incentive_and_financing_shares_expand_forward_denominator():
    result = resolve_valuation_shares(
        current_shares=100.0,
        incentive_shares=10.0,
        financing_shares=20.0,
    )

    assert result.valuation_shares == pytest.approx(130.0)
    assert result.dilution_ratio == pytest.approx(0.30)
    assert result.status == "EXPLICIT_DILUTION_ASSUMPTION"


def test_missing_dilution_inputs_do_not_invent_future_issuance():
    result = resolve_valuation_shares(current_shares=100.0)

    assert result.valuation_shares == pytest.approx(100.0)
    assert result.dilution_ratio == pytest.approx(0.0)
    assert result.status == "CURRENT_SHARES_ONLY"


def test_negative_potential_shares_fail_closed():
    result = resolve_valuation_shares(
        current_shares=100.0,
        financing_shares=-10.0,
    )

    assert result.valuation_shares is None
    assert result.dilution_ratio is None
    assert result.status == "INVALID_NEGATIVE_DILUTION_INPUT"


def test_forward_dilution_reduces_per_share_fair_value_without_changing_equity_value():
    result = per_share_value(
        equity_value=600.0,
        current_shares=10.0,
        valuation_shares=12.0,
    )

    assert result.current_share_fair_price == pytest.approx(60.0)
    assert result.diluted_fair_price == pytest.approx(50.0)
    assert result.dilution_price_impact == pytest.approx(-1.0 / 6.0)
    assert result.status == "OK"


def test_profit_forecast_is_primary_and_eps_is_derived_from_explicit_share_count():
    result = eps_from_profit(
        forecast_net_profit=120.0,
        current_shares=100.0,
        valuation_shares=120.0,
    )

    assert result.current_share_eps == pytest.approx(1.20)
    assert result.diluted_eps == pytest.approx(1.00)
    assert result.reported_consensus_eps is None
    assert result.status == "OK"


def test_reported_consensus_eps_mismatch_is_flagged_after_share_count_change():
    result = eps_from_profit(
        forecast_net_profit=120.0,
        current_shares=100.0,
        reported_consensus_eps=1.50,
        consistency_tolerance=0.08,
    )

    assert result.current_share_eps == pytest.approx(1.20)
    assert result.reported_eps_gap == pytest.approx(0.25)
    assert result.consensus_eps_consistent is False
    assert result.status == "REPORTED_EPS_SHARE_COUNT_MISMATCH"


def test_reported_consensus_eps_within_tolerance_is_audit_consistent():
    result = eps_from_profit(
        forecast_net_profit=120.0,
        current_shares=100.0,
        reported_consensus_eps=1.23,
        consistency_tolerance=0.08,
    )

    assert result.current_share_eps == pytest.approx(1.20)
    assert result.consensus_eps_consistent is True
    assert result.status == "OK"
