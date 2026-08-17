from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import FundamentalFetchResult
from src.strategies.genge_opportunity_discovery.valuation_research_report import (
    build_pe_reference_diagnostic,
    build_valuation_research_rows,
    select_wide_recall_rows,
)


class _FakeLoader:
    def __init__(self, by_code):
        self.by_code = by_code
        self.calls = []

    def load(self, code, *, years, fetch_valuation, fetch_financial):
        self.calls.append((code, years, fetch_valuation, fetch_financial))
        return self.by_code[code]


class ValuationResearchProductionTest(unittest.TestCase):
    def test_wide_recall_reserves_capacity_for_relaxable_technical_rejects(self):
        rows = [
            {
                "code": f"{index + 1:06d}",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": index + 1,
                "quant_score": 90 - index / 10,
                "hard_blockers": "",
            }
            for index in range(70)
        ]
        rows.extend(
            {
                "code": f"30{index:04d}",
                "quant_status": "HARD_REJECT",
                "quant_rank": 100 + index,
                "quant_score": 50 - index / 10,
                "hard_blockers": "price_too_high",
            }
            for index in range(20)
        )
        rows.append(
            {
                "code": "999999",
                "quant_status": "HARD_REJECT",
                "quant_rank": 1,
                "quant_score": 100,
                "hard_blockers": "adjusted_percentile_missing",
            }
        )

        selected = select_wide_recall_rows(rows, research_limit=80, relaxed_reserve=20)

        self.assertEqual(len(selected), 80)
        self.assertEqual(
            sum(row["wide_recall_reason"] == "NORMAL_RESEARCH_QUEUE" for row in selected),
            60,
        )
        self.assertEqual(
            sum(
                row["wide_recall_reason"] == "RELAXABLE_TECHNICAL_RECOVERY"
                for row in selected
            ),
            20,
        )
        self.assertNotIn("999999", {row["code"] for row in selected})

    def test_relaxed_recovery_never_backfills_beyond_hard_cap(self):
        rows = [
            {
                "code": f"00{index + 1:04d}",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": index + 1,
                "quant_score": 90 - index,
                "hard_blockers": "",
            }
            for index in range(10)
        ]
        rows.extend(
            {
                "code": f"30{index:04d}",
                "quant_status": "HARD_REJECT",
                "quant_rank": 100 + index,
                "quant_score": 60 - index / 10,
                "hard_blockers": "price_too_high",
            }
            for index in range(50)
        )

        selected = select_wide_recall_rows(rows, research_limit=80, relaxed_reserve=20)

        self.assertEqual(len(selected), 30)
        self.assertEqual(
            sum(row["wide_recall_reason"] == "NORMAL_RESEARCH_QUEUE" for row in selected),
            10,
        )
        self.assertEqual(
            sum(
                row["wide_recall_reason"] == "RELAXABLE_TECHNICAL_RECOVERY"
                for row in selected
            ),
            20,
        )

    def test_current_pe_is_excluded_from_its_own_historical_reference(self):
        valuation = pd.DataFrame(
            {
                "date": ["2026-08-13", "2026-08-14", "2026-08-15"],
                "pe": [10.0, 20.0, 100.0],
            }
        )

        result = build_pe_reference_diagnostic(
            valuation,
            as_of=date(2026, 8, 15),
            minimum_history_samples=2,
        )

        self.assertEqual(result.current_pe, 100.0)
        self.assertEqual(result.reference_median_pe, 15.0)
        self.assertEqual(result.sample_count, 2)
        self.assertEqual(result.reference_end, "2026-08-14")
        self.assertAlmostEqual(result.required_profit_growth, 100.0 / 15.0 - 1.0)

    def test_future_disclosure_fails_closed_and_never_promotes_signal(self):
        source_rows = [
            {
                "code": "600549",
                "stock_name": "厦门钨业",
                "industry": "有色金属",
                "quant_status": "SECONDARY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 60,
                "hard_blockers": "",
            }
        ]
        valuation = pd.DataFrame(
            {
                "date": pd.date_range("2026-06-01", periods=21, freq="D").date,
                "pe": [10.0] * 20 + [12.0],
            }
        )
        financial = pd.DataFrame(
            {
                "report_date": ["2026-06-30"],
                "disclosure_date": ["2026-08-20"],
                "net_profit": [999.0],
                "operating_cash_flow": [999.0],
            }
        )
        loader = _FakeLoader(
            {
                "600549": FundamentalFetchResult(
                    valuation_df=valuation,
                    financial_df=financial,
                )
            }
        )

        rows = build_valuation_research_rows(
            source_rows,
            as_of=date(2026, 8, 17),
            loader=loader,
            research_limit=80,
            relaxed_reserve=20,
            financial_review_limit=30,
            minimum_pe_samples=20,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["financial_review_status"],
            "DISCLOSURE_DATE_NOT_YET_AVAILABLE",
        )
        self.assertEqual(
            rows[0]["earnings_point_in_time_method"],
            "DISCLOSURE_DATE_NOT_YET_AVAILABLE",
        )
        self.assertNotEqual(rows[0]["headline_net_profit"], 999.0)
        self.assertFalse(rows[0]["formal_signal_eligible"])
        self.assertFalse(rows[0]["automatic_promotion_allowed"])
        self.assertTrue(rows[0]["no_auto_trade"])

    def test_undated_financial_row_is_not_used_when_disclosure_dates_exist(self):
        source_rows = [
            {
                "code": "600549",
                "stock_name": "厦门钨业",
                "quant_status": "SECONDARY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 60,
                "hard_blockers": "",
            }
        ]
        valuation = pd.DataFrame(
            {
                "date": pd.date_range("2026-06-01", periods=21, freq="D").date,
                "pe": [10.0] * 20 + [12.0],
            }
        )
        financial = pd.DataFrame(
            {
                "report_date": ["2026-03-31", "2026-06-30"],
                "disclosure_date": ["2026-04-25", None],
                "net_profit": [80.0, 999.0],
                "operating_cash_flow": [70.0, 999.0],
            }
        )
        loader = _FakeLoader(
            {
                "600549": FundamentalFetchResult(
                    valuation_df=valuation,
                    financial_df=financial,
                )
            }
        )

        rows = build_valuation_research_rows(
            source_rows,
            as_of=date(2026, 8, 17),
            loader=loader,
            minimum_pe_samples=20,
        )

        self.assertEqual(rows[0]["headline_net_profit"], 80.0)
        self.assertEqual(rows[0]["financial_report_date"], date(2026, 3, 31))
        self.assertEqual(rows[0]["earnings_point_in_time_method"], "DISCLOSURE_DATE_PIT")


if __name__ == "__main__":
    unittest.main()
