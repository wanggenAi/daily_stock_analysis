import inspect

import pytest

from src.strategies.genge_opportunity_discovery.transport_cycle_valuation import (
    build_transport_three_scenario_valuation,
    collect_transport_cycle_evidence,
    reverse_implied_transport_ebitda,
    value_through_cycle_transport_ev,
)


def test_transport_ev_bridge_uses_through_cycle_ebitda_and_lease_consistent_net_debt():
    result = value_through_cycle_transport_ev(
        through_cycle_normalized_ebitda=100.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=150.0,
        explicit_non_operating_equity_adjustment=20.0,
        current_market_cap=500.0,
        total_common_shares=10.0,
    )

    assert result.fair_enterprise_value == pytest.approx(600.0)
    assert result.fair_equity_value == pytest.approx(470.0)
    assert result.fair_price == pytest.approx(47.0)
    assert result.current_enterprise_value == pytest.approx(630.0)
    assert result.implied_normalized_ebitda == pytest.approx(105.0)
    assert result.margin_of_safety == pytest.approx(470.0 / 500.0 - 1.0)
    assert result.status == "OK"


def test_net_cash_is_preserved_as_negative_net_debt_and_increases_equity_value():
    result = value_through_cycle_transport_ev(
        through_cycle_normalized_ebitda=100.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=-200.0,
    )

    assert result.fair_enterprise_value == pytest.approx(600.0)
    assert result.fair_equity_value == pytest.approx(800.0)


def test_transport_ev_fails_closed_without_lease_consistent_net_debt():
    result = value_through_cycle_transport_ev(
        through_cycle_normalized_ebitda=100.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=None,
    )

    assert result.valuation_model_applicable is False
    assert result.status == "LEASE_CONSISTENT_NET_DEBT_UNAVAILABLE"


def test_transport_ev_refuses_peak_or_negative_ebitda_as_normalized_input():
    zero = value_through_cycle_transport_ev(
        through_cycle_normalized_ebitda=0.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=100.0,
    )
    negative = value_through_cycle_transport_ev(
        through_cycle_normalized_ebitda=-10.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=100.0,
    )

    assert zero.status == "THROUGH_CYCLE_EBITDA_UNAVAILABLE"
    assert negative.status == "THROUGH_CYCLE_EBITDA_UNAVAILABLE"


def test_reverse_implied_transport_ebitda_matches_enterprise_value_bridge():
    implied, status = reverse_implied_transport_ebitda(
        current_market_cap=500.0,
        fair_ev_ebitda_multiple=6.0,
        net_debt_including_lease_liabilities=150.0,
        explicit_non_operating_equity_adjustment=20.0,
    )

    assert implied == pytest.approx((500.0 + 150.0 - 20.0) / 6.0)
    assert status == "OK"


def test_transport_api_has_no_hidden_freight_fare_fuel_or_cycle_haircut():
    signature = inspect.signature(value_through_cycle_transport_ev)

    assert "freight_rate" not in signature.parameters
    assert "passenger_yield" not in signature.parameters
    assert "fuel_price" not in signature.parameters
    assert "cycle_haircut" not in signature.parameters
    assert "through_cycle_normalized_ebitda" in signature.parameters
    assert "fair_ev_ebitda_multiple" in signature.parameters


def test_transport_evidence_keeps_volume_price_capacity_and_cost_separate():
    result = collect_transport_cycle_evidence(
        volume_or_rpk_growth=0.067,
        capacity_or_ask_growth=0.08,
        utilization_or_load_factor=0.9259,
        unit_revenue_or_yield_change=-0.038,
        fuel_unit_cost_change=-0.10,
        benchmark_rate_or_fare_index_change=-0.37,
        fleet_capacity_growth=0.073,
        lease_liabilities=200.0,
        net_debt_including_lease_liabilities=150.0,
    )

    assert result.volume_or_rpk_growth == pytest.approx(0.067)
    assert result.unit_revenue_or_yield_change == pytest.approx(-0.038)
    assert result.benchmark_rate_or_fare_index_change == pytest.approx(-0.37)
    assert result.evidence_completeness == pytest.approx(9 / 12)
    assert "capital_expenditure" in result.missing_fields
    assert not hasattr(result, "quality_score")


def test_three_scenario_transport_builder_preserves_reverse_expectation_view():
    result = build_transport_three_scenario_valuation(
        net_debt_including_lease_liabilities=150.0,
        current_market_cap=500.0,
        scenarios={
            "bear": {
                "through_cycle_normalized_ebitda": 70.0,
                "fair_ev_ebitda_multiple": 5.0,
            },
            "base": {
                "through_cycle_normalized_ebitda": 100.0,
                "fair_ev_ebitda_multiple": 6.0,
            },
            "bull": {
                "through_cycle_normalized_ebitda": 130.0,
                "fair_ev_ebitda_multiple": 7.0,
            },
        },
    )

    assert result["scenarios"]["bear"]["fair_equity_value"] < result["scenarios"]["base"]["fair_equity_value"]
    assert result["scenarios"]["base"]["fair_equity_value"] < result["scenarios"]["bull"]["fair_equity_value"]
    assert result["reverse_valuation"]["implied_normalized_ebitda"] == pytest.approx((500.0 + 150.0) / 6.0)
    assert result["reverse_valuation"]["expectation_gap_ebitda"] == pytest.approx((650.0 / 6.0) - 100.0)


def test_three_scenario_transport_builder_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing transport valuation scenarios"):
        build_transport_three_scenario_valuation(
            net_debt_including_lease_liabilities=150.0,
            scenarios={
                "bear": {
                    "through_cycle_normalized_ebitda": 70.0,
                    "fair_ev_ebitda_multiple": 5.0,
                },
                "base": {
                    "through_cycle_normalized_ebitda": 100.0,
                    "fair_ev_ebitda_multiple": 6.0,
                },
            },
        )
