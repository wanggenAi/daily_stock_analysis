import pytest

from src.strategies.genge_opportunity_discovery.scenario_odds import compute_scenario_odds


def test_scenario_odds_reports_raw_asymmetry_without_probabilities():
    result = compute_scenario_odds(
        current_market_cap=100.0,
        bear_fair_equity_value=80.0,
        base_fair_equity_value=120.0,
        bull_fair_equity_value=160.0,
    )

    assert result.status == "OK"
    assert result.bear_return == pytest.approx(-0.2)
    assert result.base_margin_of_safety == pytest.approx(0.2)
    assert result.bull_return == pytest.approx(0.6)
    assert result.downside_risk == pytest.approx(0.2)
    assert result.upside_potential == pytest.approx(0.6)
    assert result.upside_downside_ratio == pytest.approx(3.0)


def test_scenario_odds_does_not_return_infinity_when_bear_has_no_downside():
    result = compute_scenario_odds(
        current_market_cap=100.0,
        bear_fair_equity_value=105.0,
        base_fair_equity_value=120.0,
        bull_fair_equity_value=150.0,
    )

    assert result.status == "NO_BEAR_DOWNSIDE_RATIO_UNDEFINED"
    assert result.downside_risk == pytest.approx(0.0)
    assert result.upside_downside_ratio is None


def test_scenario_odds_fails_closed_on_missing_scenario():
    result = compute_scenario_odds(
        current_market_cap=100.0,
        bear_fair_equity_value=80.0,
        base_fair_equity_value=None,
        bull_fair_equity_value=160.0,
    )

    assert result.status == "SCENARIO_VALUE_INCOMPLETE"
    assert result.upside_downside_ratio is None
