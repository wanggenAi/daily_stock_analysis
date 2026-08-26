from src.strategies.genge_opportunity_discovery.v311_expectation_merge import (
    merge_expectation_inputs,
)


def test_expectation_bridge_adds_only_sidecar_fields_and_preserves_research_evidence() -> None:
    valuation = [
        {
            "code": "600000",
            "quant_rank": "1",
            "valuation_primary_strategy_id": "general_reverse_earnings",
            "v31_moat_status": "PASS",
            "v31_pessimistic_value": "80",
            "required_profit_growth_vs_reference": "0.77",
        }
    ]
    expectation = [
        {
            "code": "600000",
            "v311_expectation_policy_source": "round6_expectation_gap_10y_strict_pit_frozen",
            "v31_current_price": "90",
            "v31_normalized_profit": "5",
            "v31_normalized_profit_method": "STRICT_PIT_NORMALIZED_CLEAN_EPS_ROUND6",
            "v31_neutral_value": "100",
            "v31_realistic_profit_cagr": "0.12",
            "v31_market_implied_profit_cagr": "0.08",
            "v31_expectation_gap_pct": "0.04",
            "normalized_earnings_observation_count": "4",
            "deduct_profit_quality_factor": "0.9",
            "cash_conversion_ratio": "1.1",
            "realistic_growth_four_report_range": "0.04",
            "implied_growth_status": "SOLVED",
        }
    ]
    row = merge_expectation_inputs(valuation, expectation)[0]
    assert row["v31_neutral_value"] == "100"
    assert row["v31_market_implied_profit_cagr"] == "0.08"
    assert row["v31_moat_status"] == "PASS"
    assert row["v31_pessimistic_value"] == "80"
    assert row["required_profit_growth_vs_reference"] == "0.77"
    assert row["v311_expectation_inputs_merged"] is True


def test_old_pe_required_growth_is_not_mapped_to_market_implied_growth() -> None:
    valuation = [
        {
            "code": "600000",
            "required_profit_growth_vs_reference": "0.55",
        }
    ]
    row = merge_expectation_inputs(valuation, [])[0]
    assert "v31_market_implied_profit_cagr" not in row
    assert row["required_profit_growth_vs_reference"] == "0.55"
    assert row["v311_expectation_inputs_merged"] is False


def test_bridge_rejects_an_unfrozen_policy_source() -> None:
    valuation = [{"code": "600000"}]
    expectation = [
        {
            "code": "600000",
            "v311_expectation_policy_source": "some_new_unvalidated_formula",
        }
    ]
    try:
        merge_expectation_inputs(valuation, expectation)
    except ValueError as exc:
        assert "unexpected V3.1.1 expectation policy source" in str(exc)
    else:
        raise AssertionError("unfrozen expectation policy must not enter production")
