from types import SimpleNamespace
from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery import valuation_research_report as base
from src.strategies.genge_opportunity_discovery.valuation_research_long_term_runner import (
    _base_row,
    _build_valuation_research_rows,
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


class _Loader:
    def load(self, code, *, years, fetch_valuation, fetch_financial):
        if fetch_valuation:
            if code == "688687":
                valuation = pd.DataFrame(
                    [
                        {"date": "2026-08-14", "pe": 18.0},
                        {"date": "2026-08-17", "pe": -3.0},
                    ]
                )
            else:
                valuation = pd.DataFrame(
                    [
                        {"date": "2026-08-14", "pe": 18.0},
                        {"date": "2026-08-17", "pe": 20.0},
                    ]
                )
            return SimpleNamespace(valuation_df=valuation, financial_df=pd.DataFrame())
        financial = pd.DataFrame(
            [
                {
                    "report_date": "2026-06-30",
                    "net_profit": 100.0,
                    "recurring_profit": 95.0,
                    "investment_income": 0.0,
                    "fair_value_change_gain": 0.0,
                    "operating_cash_flow": 110.0,
                }
            ]
        )
        return SimpleNamespace(valuation_df=pd.DataFrame(), financial_df=financial)


def test_non_pe_long_term_candidate_still_gets_financial_review_first():
    rows = _build_valuation_research_rows(
        [
            {
                "code": "688687",
                "stock_name": "LongTerm",
                "industry": "Biotech",
                "quant_status": "SECONDARY_RESEARCH",
                "quant_rank": 2,
                "quant_score": 70,
                "valuation_source_channel": "LONG_TERM_SECOND_PASS",
                "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            },
            {
                "code": "600000",
                "stock_name": "Normal",
                "industry": "Bank",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 90,
                "valuation_source_channel": "GLOBAL_RECALL",
            },
        ],
        as_of=date(2026, 8, 17),
        loader=_Loader(),
        research_limit=2,
        relaxed_reserve=0,
        financial_review_limit=1,
        minimum_pe_samples=1,
        years=5,
        max_workers=1,
    )
    by_code = {row["code"]: row for row in rows}
    assert by_code["688687"]["valuation_diagnostic_status"] == "PE_MODEL_NOT_APPLICABLE"
    assert by_code["688687"]["financial_review_status"] == "OK"
    assert by_code["600000"]["financial_review_status"] == "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW"
