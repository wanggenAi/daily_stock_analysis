import pytest

from src.strategies.genge_opportunity_discovery.bank_valuation import (
    build_bank_three_scenario_valuation,
    build_common_book_value,
    collect_bank_quality_evidence,
    fair_pb_from_roe,
    implied_roe_from_pb,
    value_bank_common_equity,
)


def test_common_book_value_uses_common_equity_and_common_shares():
    result = build_common_book_value(
        common_equity=450.0,
        common_shares=10.0,
        current_price=40.0,
    )

    assert result.common_bvps == pytest.approx(45.0)
    assert result.current_common_pb == pytest.approx(40.0 / 45.0)
    assert result.status == "OK"


def test_reported_common_bvps_is_preferred_for_common_pb():
    result = build_common_book_value(
        common_equity=500.0,
        common_shares=10.0,
        common_bvps=45.0,
        current_price=40.0,
        current_market_cap=400.0,
    )

    assert result.common_bvps == pytest.approx(45.0)
    assert result.current_common_pb == pytest.approx(40.0 / 45.0)


def test_bank_book_value_fails_closed_without_common_book_value():
    result = build_common_book_value(current_price=10.0)

    assert result.current_common_pb is None
    assert result.status == "COMMON_BOOK_VALUE_UNAVAILABLE"


def test_fair_pb_uses_explicit_sustainable_roe_cost_of_equity_and_growth():
    fair_pb, status = fair_pb_from_roe(
        sustainable_roe=0.15,
        cost_of_equity=0.10,
        long_term_growth=0.04,
    )

    assert fair_pb == pytest.approx((0.15 - 0.04) / (0.10 - 0.04))
    assert status == "OK"


def test_reverse_pb_solves_market_implied_sustainable_roe():
    implied, status = implied_roe_from_pb(
        current_common_pb=1.20,
        cost_of_equity=0.10,
        long_term_growth=0.04,
    )

    assert implied == pytest.approx(1.20 * (0.10 - 0.04) + 0.04)
    assert status == "OK"


def test_low_pb_is_not_automatically_value_when_sustainable_roe_is_low():
    fair_pb, status = fair_pb_from_roe(
        sustainable_roe=0.05,
        cost_of_equity=0.10,
        long_term_growth=0.03,
    )

    assert fair_pb == pytest.approx((0.05 - 0.03) / (0.10 - 0.03))
    assert fair_pb < 0.30
    assert status == "OK"


def test_high_sustainable_roe_supports_higher_fair_pb_under_same_required_return():
    low_quality_pb, _ = fair_pb_from_roe(
        sustainable_roe=0.05,
        cost_of_equity=0.10,
        long_term_growth=0.03,
    )
    high_quality_pb, _ = fair_pb_from_roe(
        sustainable_roe=0.15,
        cost_of_equity=0.10,
        long_term_growth=0.03,
    )

    assert high_quality_pb > low_quality_pb
    assert high_quality_pb == pytest.approx((0.15 - 0.03) / (0.10 - 0.03))


def test_invalid_cost_of_equity_growth_relation_fails_closed():
    fair_pb, status = fair_pb_from_roe(
        sustainable_roe=0.15,
        cost_of_equity=0.04,
        long_term_growth=0.04,
    )

    assert fair_pb is None
    assert status == "INVALID_COST_OF_EQUITY_GROWTH_RELATION"


def test_bank_valuation_reports_fair_price_margin_and_implied_roe():
    result = value_bank_common_equity(
        common_bvps=45.0,
        sustainable_roe=0.15,
        cost_of_equity=0.10,
        long_term_growth=0.04,
        current_price=40.0,
    )

    expected_pb = (0.15 - 0.04) / (0.10 - 0.04)
    assert result.valuation_model_applicable is True
    assert result.fair_common_pb == pytest.approx(expected_pb)
    assert result.fair_price == pytest.approx(45.0 * expected_pb)
    assert result.current_common_pb == pytest.approx(40.0 / 45.0)
    assert result.implied_sustainable_roe == pytest.approx((40.0 / 45.0) * 0.06 + 0.04)
    assert result.margin_of_safety == pytest.approx(result.fair_price / 40.0 - 1.0)


def test_bank_quality_evidence_records_raw_fields_without_arbitrary_score():
    result = collect_bank_quality_evidence(
        net_interest_margin=0.0183,
        npl_ratio=0.0094,
        provision_coverage_ratio=3.8776,
        common_equity_tier1_ratio=0.1413,
    )

    assert result.net_interest_margin == pytest.approx(0.0183)
    assert result.npl_ratio == pytest.approx(0.0094)
    assert result.evidence_completeness == pytest.approx(4 / 7)
    assert "credit_cost" in result.missing_fields
    assert not hasattr(result, "quality_score")


def test_bank_three_scenario_builder_requires_explicit_scenarios_and_preserves_reverse_view():
    result = build_bank_three_scenario_valuation(
        common_bvps=40.0,
        current_price=36.0,
        scenarios={
            "bear": {
                "sustainable_roe": 0.08,
                "cost_of_equity": 0.11,
                "long_term_growth": 0.03,
            },
            "base": {
                "sustainable_roe": 0.11,
                "cost_of_equity": 0.10,
                "long_term_growth": 0.04,
            },
            "bull": {
                "sustainable_roe": 0.14,
                "cost_of_equity": 0.10,
                "long_term_growth": 0.04,
            },
        },
    )

    assert result["scenarios"]["bear"]["fair_common_pb"] < result["scenarios"]["base"]["fair_common_pb"]
    assert result["scenarios"]["base"]["fair_common_pb"] < result["scenarios"]["bull"]["fair_common_pb"]
    assert result["reverse_valuation"]["current_common_pb"] == pytest.approx(0.9)
    assert result["reverse_valuation"]["implied_sustainable_roe"] == pytest.approx(0.9 * 0.06 + 0.04)


def test_bank_three_scenario_builder_rejects_missing_required_scenario():
    with pytest.raises(ValueError, match="missing bank valuation scenarios"):
        build_bank_three_scenario_valuation(
            common_bvps=40.0,
            scenarios={
                "bear": {
                    "sustainable_roe": 0.08,
                    "cost_of_equity": 0.11,
                    "long_term_growth": 0.03,
                },
                "base": {
                    "sustainable_roe": 0.11,
                    "cost_of_equity": 0.10,
                    "long_term_growth": 0.04,
                },
            },
        )
