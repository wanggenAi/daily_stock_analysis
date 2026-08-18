from src.strategies.genge_opportunity_discovery import valuation_research_report as base
from src.strategies.genge_opportunity_discovery.valuation_research_long_term_runner import (
    _base_row,
    _rank_key,
)


def test_base_row_preserves_long_term_source_channel():
    diag = base.PeReferenceDiagnostic(
        current_pe=20,
        reference_median_pe=18,
        sample_count=30,
        reference_start="2021-01-01",
        reference_end="2026-01-01",
        percentile=0.6,
        implied_profit_multiple=1.1,
        required_profit_growth=0.1,
        status="OK",
    )
    row = _base_row(
        {
            "code": "603369",
            "stock_name": "Sample",
            "industry": "Consumer",
            "valuation_source_channel": "GLOBAL_RECALL+LONG_TERM_SECOND_PASS",
            "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            "medium_horizon_exit_profile_limitation": True,
        },
        diag,
    )
    assert "LONG_TERM_SECOND_PASS" in row["valuation_source_channel"]
    assert row["long_term_second_pass_status"] == "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES"
    assert row["medium_horizon_exit_profile_limitation"] is True


def test_long_term_rows_sort_ahead_for_bounded_financial_review():
    common = {
        "valuation_diagnostic_status": "OK",
        "expectation_state": "BALANCED",
        "required_profit_growth_vs_reference": 0.1,
        "historical_pe_sample_count": 30,
        "quant_rank": 10,
        "code": "600000",
    }
    normal = dict(common, valuation_source_channel="GLOBAL_RECALL", code="600000")
    long_term = dict(common, valuation_source_channel="LONG_TERM_SECOND_PASS", code="603369")
    assert _rank_key(long_term) < _rank_key(normal)
