import inspect

import pytest

from src.strategies.genge_opportunity_discovery.capital_markets_valuation import (
    build_traditional_broker_three_scenario_valuation,
    collect_capital_markets_quality_evidence,
    value_hybrid_broker_platform_sotp,
    value_traditional_broker,
)


def test_traditional_broker_uses_explicit_mid_cycle_roe_for_fair_pb():
    result = value_traditional_broker(
        common_bvps=20.0,
        normalized_mid_cycle_roe=0.10,
        cost_of_equity=0.11,
        long_term_growth=0.04,
        current_price=18.0,
    )

    expected_pb = (0.10 - 0.04) / (0.11 - 0.04)
    assert result.valuation_model_applicable is True
    assert result.fair_common_pb == pytest.approx(expected_pb)
    assert result.fair_price == pytest.approx(20.0 * expected_pb)
    assert result.current_common_pb == pytest.approx(0.9)
    assert result.status == "OK"


def test_traditional_broker_reverse_solves_market_implied_mid_cycle_roe():
    result = value_traditional_broker(
        common_bvps=20.0,
        normalized_mid_cycle_roe=0.10,
        cost_of_equity=0.11,
        long_term_growth=0.04,
        current_price=18.0,
    )

    assert result.implied_mid_cycle_roe == pytest.approx(0.9 * (0.11 - 0.04) + 0.04)


def test_traditional_broker_invalid_cost_of_equity_growth_relation_fails_closed():
    result = value_traditional_broker(
        common_bvps=20.0,
        normalized_mid_cycle_roe=0.10,
        cost_of_equity=0.04,
        long_term_growth=0.04,
        current_price=18.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_common_pb is None
    assert result.status == "INVALID_COST_OF_EQUITY_GROWTH_RELATION"


def test_traditional_broker_api_has_no_quarterly_profit_annualization_shortcut():
    parameters = inspect.signature(value_traditional_broker).parameters

    assert "quarterly_profit" not in parameters
    assert "quarterly_roe" not in parameters
    assert "annualization_factor" not in parameters
    assert "normalized_mid_cycle_roe" in parameters


def test_hybrid_broker_platform_sotp_values_segments_separately():
    result = value_hybrid_broker_platform_sotp(
        normalized_broker_profit=80.0,
        broker_fair_multiple=15.0,
        normalized_platform_profit=20.0,
        platform_fair_multiple=30.0,
        explicit_equity_adjustment=100.0,
        current_market_cap=1800.0,
        total_common_shares=10.0,
    )

    assert result.broker_value == pytest.approx(1200.0)
    assert result.platform_value == pytest.approx(600.0)
    assert result.fair_equity_value == pytest.approx(1900.0)
    assert result.fair_price == pytest.approx(190.0)
    assert result.margin_of_safety == pytest.approx(1900.0 / 1800.0 - 1.0)
    assert result.status == "OK"


def test_hybrid_sotp_fails_closed_when_segment_profit_is_missing():
    result = value_hybrid_broker_platform_sotp(
        normalized_broker_profit=80.0,
        broker_fair_multiple=15.0,
        normalized_platform_profit=None,
        platform_fair_multiple=30.0,
        current_market_cap=1800.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.status == "SEGMENT_PROFIT_UNAVAILABLE"


def test_hybrid_sotp_does_not_accept_revenue_share_as_segment_profit_proxy():
    parameters = inspect.signature(value_hybrid_broker_platform_sotp).parameters

    assert "broker_revenue_share" not in parameters
    assert "platform_revenue_share" not in parameters
    assert "normalized_broker_profit" in parameters
    assert "normalized_platform_profit" in parameters


def test_hybrid_sotp_refuses_negative_segment_profit_without_alternative_model():
    result = value_hybrid_broker_platform_sotp(
        normalized_broker_profit=80.0,
        broker_fair_multiple=15.0,
        normalized_platform_profit=-5.0,
        platform_fair_multiple=30.0,
    )

    assert result.valuation_model_applicable is False
    assert result.status == "NEGATIVE_SEGMENT_PROFIT_REQUIRES_ALTERNATIVE_MODEL"


def test_capital_markets_quality_evidence_keeps_raw_fields_without_magic_score():
    result = collect_capital_markets_quality_evidence(
        market_turnover_change=0.70,
        brokerage_fee_growth=0.478,
        investment_banking_fee_growth=0.238,
        weighted_roe=0.1059,
    )

    assert result.market_turnover_change == pytest.approx(0.70)
    assert result.brokerage_fee_growth == pytest.approx(0.478)
    assert result.evidence_completeness == pytest.approx(4 / 8)
    assert "platform_service_growth" in result.missing_fields
    assert not hasattr(result, "quality_score")


def test_traditional_broker_three_scenario_builder_preserves_reverse_expectation_view():
    result = build_traditional_broker_three_scenario_valuation(
        common_bvps=20.0,
        current_price=18.0,
        scenarios={
            "bear": {
                "normalized_mid_cycle_roe": 0.07,
                "cost_of_equity": 0.12,
                "long_term_growth": 0.03,
            },
            "base": {
                "normalized_mid_cycle_roe": 0.10,
                "cost_of_equity": 0.11,
                "long_term_growth": 0.04,
            },
            "bull": {
                "normalized_mid_cycle_roe": 0.13,
                "cost_of_equity": 0.10,
                "long_term_growth": 0.04,
            },
        },
    )

    assert result["scenarios"]["bear"]["fair_common_pb"] < result["scenarios"]["base"]["fair_common_pb"]
    assert result["scenarios"]["base"]["fair_common_pb"] < result["scenarios"]["bull"]["fair_common_pb"]
    assert result["reverse_valuation"]["current_common_pb"] == pytest.approx(0.9)
    assert result["reverse_valuation"]["implied_mid_cycle_roe"] == pytest.approx(0.9 * 0.07 + 0.04)


def test_traditional_broker_three_scenario_builder_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing broker valuation scenarios"):
        build_traditional_broker_three_scenario_valuation(
            common_bvps=20.0,
            scenarios={
                "bear": {
                    "normalized_mid_cycle_roe": 0.07,
                    "cost_of_equity": 0.12,
                    "long_term_growth": 0.03,
                },
                "base": {
                    "normalized_mid_cycle_roe": 0.10,
                    "cost_of_equity": 0.11,
                    "long_term_growth": 0.04,
                },
            },
        )
