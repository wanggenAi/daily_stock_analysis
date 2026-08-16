import pytest

from src.strategies.genge_opportunity_discovery.insurance_valuation import (
    build_insurance_three_scenario_valuation,
    collect_insurance_quality_evidence,
    reverse_implied_nbv_franchise_multiple,
    value_insurance_appraisal,
)


def test_ev_plus_explicit_nbv_franchise_multiple_builds_appraisal_value():
    result = value_insurance_appraisal(
        embedded_value=1000.0,
        normalized_annual_nbv=50.0,
        nbv_franchise_multiple=5.0,
        current_market_cap=1100.0,
        total_common_shares=10.0,
    )

    assert result.future_new_business_value == pytest.approx(250.0)
    assert result.fair_equity_value == pytest.approx(1250.0)
    assert result.fair_price == pytest.approx(125.0)
    assert result.current_p_ev == pytest.approx(1.10)
    assert result.implied_nbv_franchise_multiple == pytest.approx(2.0)
    assert result.margin_of_safety == pytest.approx(1250.0 / 1100.0 - 1.0)
    assert result.status == "OK"


def test_market_discount_to_embedded_value_preserves_negative_implied_franchise_multiple():
    implied, status = reverse_implied_nbv_franchise_multiple(
        current_market_cap=900.0,
        embedded_value=1000.0,
        normalized_annual_nbv=50.0,
    )

    assert implied == pytest.approx(-2.0)
    assert status == "OK"


def test_missing_embedded_value_fails_closed():
    result = value_insurance_appraisal(
        embedded_value=None,
        normalized_annual_nbv=50.0,
        nbv_franchise_multiple=5.0,
        current_market_cap=1100.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.status == "EMBEDDED_VALUE_UNAVAILABLE"


def test_missing_normalized_annual_nbv_does_not_invent_quarterly_annualization():
    result = value_insurance_appraisal(
        embedded_value=1000.0,
        normalized_annual_nbv=None,
        nbv_franchise_multiple=5.0,
        current_market_cap=1100.0,
    )

    assert result.valuation_model_applicable is False
    assert result.future_new_business_value is None
    assert result.status == "NORMALIZED_ANNUAL_NBV_UNAVAILABLE"


def test_missing_franchise_multiple_does_not_invent_target_p_ev_or_appraisal_value():
    result = value_insurance_appraisal(
        embedded_value=1000.0,
        normalized_annual_nbv=50.0,
        nbv_franchise_multiple=None,
        current_market_cap=1100.0,
    )

    assert result.valuation_model_applicable is False
    assert result.fair_equity_value is None
    assert result.current_p_ev == pytest.approx(1.10)
    assert result.status == "NBV_FRANCHISE_MULTIPLE_UNAVAILABLE"


def test_explicit_equity_adjustment_is_applied_once_and_reverse_solved_consistently():
    result = value_insurance_appraisal(
        embedded_value=1000.0,
        normalized_annual_nbv=50.0,
        nbv_franchise_multiple=4.0,
        explicit_equity_adjustment=-100.0,
        current_market_cap=1050.0,
    )

    assert result.fair_equity_value == pytest.approx(1100.0)
    assert result.implied_nbv_franchise_multiple == pytest.approx((1050.0 - 1000.0 + 100.0) / 50.0)


def test_insurance_quality_evidence_keeps_raw_metrics_without_magic_score():
    result = collect_insurance_quality_evidence(
        nbv_growth=0.20,
        nbv_margin=0.285,
        persistency_13m=0.974,
        persistency_25m=0.949,
        total_or_comprehensive_investment_yield=0.063,
        p_and_c_combined_ratio=0.968,
    )

    assert result.nbv_growth == pytest.approx(0.20)
    assert result.persistency_13m == pytest.approx(0.974)
    assert result.p_and_c_combined_ratio == pytest.approx(0.968)
    assert result.evidence_completeness == pytest.approx(6 / 10)
    assert not hasattr(result, "quality_score")


def test_three_scenario_insurance_valuation_uses_explicit_nbv_and_multiple_per_scenario():
    result = build_insurance_three_scenario_valuation(
        embedded_value=1000.0,
        current_market_cap=1100.0,
        scenarios={
            "bear": {
                "normalized_annual_nbv": 40.0,
                "nbv_franchise_multiple": 2.0,
            },
            "base": {
                "normalized_annual_nbv": 50.0,
                "nbv_franchise_multiple": 4.0,
            },
            "bull": {
                "normalized_annual_nbv": 60.0,
                "nbv_franchise_multiple": 6.0,
            },
        },
    )

    assert result["scenarios"]["bear"]["fair_equity_value"] == pytest.approx(1080.0)
    assert result["scenarios"]["base"]["fair_equity_value"] == pytest.approx(1200.0)
    assert result["scenarios"]["bull"]["fair_equity_value"] == pytest.approx(1360.0)
    assert result["reverse_valuation"]["implied_nbv_franchise_multiple"] == pytest.approx(2.0)
    assert result["reverse_valuation"]["expectation_gap_multiple"] == pytest.approx(-2.0)


def test_three_scenario_insurance_builder_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing insurance valuation scenarios"):
        build_insurance_three_scenario_valuation(
            embedded_value=1000.0,
            scenarios={
                "bear": {
                    "normalized_annual_nbv": 40.0,
                    "nbv_franchise_multiple": 2.0,
                },
                "base": {
                    "normalized_annual_nbv": 50.0,
                    "nbv_franchise_multiple": 4.0,
                },
            },
        )
