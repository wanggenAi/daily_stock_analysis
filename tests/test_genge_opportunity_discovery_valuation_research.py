from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from src.strategies.genge_opportunity_discovery.valuation_research_queue import (
    add_financial_quality,
    build_relative_pe_diagnostic,
    rank_valuation_research_rows,
    run_sidecar,
    select_wide_recall_rows,
)


class TestValuationResearchQueue(unittest.TestCase):
    def test_wide_recall_reserves_capacity_for_relaxable_technical_rows(self) -> None:
        rows = []
        for index in range(70):
            rows.append(
                {
                    "code": f"{index + 1:06d}",
                    "quant_status": "PRIORITY_RESEARCH",
                    "quant_rank": index + 1,
                    "quant_score": 90 - index / 10,
                    "hard_blockers": "",
                }
            )
        for index in range(20):
            rows.append(
                {
                    "code": f"30{index:04d}",
                    "quant_status": "HARD_REJECT",
                    "quant_rank": 100 + index,
                    "quant_score": 50 - index / 10,
                    "hard_blockers": "price_too_high",
                }
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

        selected = select_wide_recall_rows(rows, max_candidates=80, relaxed_reserve=20)

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

    def test_relative_pe_diagnostic_is_point_in_time_and_reverse_solves_growth(self) -> None:
        start = date(2026, 1, 1)
        valuation = pd.DataFrame(
            {
                "date": [start + timedelta(days=index) for index in range(6)],
                "pe": [10, 10, 10, 10, 20, 100],
            }
        )
        row = build_relative_pe_diagnostic(
            {
                "code": "300223",
                "stock_name": "北京君正",
                "quant_status": "SECONDARY_RESEARCH",
                "quant_rank": 8,
                "quant_score": 60,
                "hard_blockers": "",
            },
            valuation,
            as_of=start + timedelta(days=4),
            minimum_pe_samples=4,
        )

        self.assertEqual(row["current_pe"], 20.0)
        self.assertEqual(row["historical_median_pe"], 10.0)
        self.assertEqual(row["historical_pe_sample_count"], 4)
        self.assertEqual(row["required_profit_growth"], 1.0)
        self.assertEqual(row["required_profit_growth_pct"], 100.0)
        self.assertEqual(row["valuation_diagnostic_status"], "OK_RELATIVE_PE_EXPECTATION")
        self.assertFalse(row["formal_buy_eligible"])
        self.assertFalse(row["automatic_promotion_allowed"])
        self.assertTrue(row["no_auto_trade"])

    def test_current_pe_never_contaminates_its_own_reference(self) -> None:
        valuation = pd.DataFrame(
            {
                "date": ["2026-08-13", "2026-08-14", "2026-08-15"],
                "pe": [10.0, 20.0, 100.0],
            }
        )
        row = build_relative_pe_diagnostic(
            {"code": "600549", "quant_status": "SECONDARY_RESEARCH"},
            valuation,
            as_of=date(2026, 8, 15),
            minimum_pe_samples=2,
        )

        self.assertEqual(row["current_pe"], 100.0)
        self.assertEqual(row["historical_median_pe"], 15.0)
        self.assertEqual(row["historical_pe_sample_count"], 2)
        self.assertEqual(row["historical_pe_reference_end"], "2026-08-14")
        self.assertAlmostEqual(row["required_profit_growth"], 100.0 / 15.0 - 1.0, places=6)

    def test_non_positive_latest_profit_marks_pe_model_not_applicable(self) -> None:
        row = {
            "code": "000001",
            "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
            "required_profit_growth": -0.1,
        }
        financial = pd.DataFrame(
            {
                "report_date": ["2026-06-30"],
                "disclosure_date": ["2026-07-20"],
                "net_profit": [-10.0],
                "operating_cash_flow": [5.0],
            }
        )

        result = add_financial_quality(row, financial, as_of=date(2026, 8, 17))

        self.assertEqual(result["valuation_diagnostic_status"], "PE_MODEL_NOT_APPLICABLE")
        self.assertEqual(result["financial_review_status"], "OK")
        self.assertEqual(result["earnings_point_in_time_method"], "DISCLOSURE_DATE_PIT")
        self.assertLessEqual(float(result["earnings_quality_score"]), 25.0)

    def test_future_disclosure_fails_closed_instead_of_using_report_date(self) -> None:
        row = {
            "code": "600549",
            "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
            "required_profit_growth": 0.1,
        }
        financial = pd.DataFrame(
            {
                "report_date": ["2026-06-30"],
                "disclosure_date": ["2026-08-20"],
                "net_profit": [999.0],
                "operating_cash_flow": [999.0],
            }
        )

        result = add_financial_quality(row, financial, as_of=date(2026, 8, 17))

        self.assertEqual(
            result["financial_review_status"],
            "DISCLOSURE_DATE_NOT_YET_AVAILABLE",
        )
        self.assertEqual(
            result["earnings_point_in_time_method"],
            "DISCLOSURE_DATE_NOT_YET_AVAILABLE",
        )
        self.assertNotIn("latest_net_profit", result)

    def test_partial_disclosure_dates_do_not_treat_undated_row_as_known(self) -> None:
        row = {
            "code": "600549",
            "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
            "required_profit_growth": 0.1,
        }
        financial = pd.DataFrame(
            {
                "report_date": ["2026-03-31", "2026-06-30"],
                "disclosure_date": ["2026-04-25", None],
                "net_profit": [80.0, 999.0],
                "operating_cash_flow": [70.0, 999.0],
            }
        )

        result = add_financial_quality(row, financial, as_of=date(2026, 8, 17))

        self.assertEqual(result["latest_net_profit"], 80.0)
        self.assertEqual(result["financial_report_date"], "2026-03-31")
        self.assertEqual(result["financial_disclosure_date"], "2026-04-25")
        self.assertEqual(result["earnings_point_in_time_method"], "DISCLOSURE_DATE_PIT")

    def test_rank_prefers_lower_required_profit_growth(self) -> None:
        rows = rank_valuation_research_rows(
            [
                {
                    "code": "000002",
                    "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
                    "required_profit_growth": 0.5,
                    "quant_score": 90,
                },
                {
                    "code": "000001",
                    "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
                    "required_profit_growth": -0.2,
                    "quant_score": 50,
                },
                {
                    "code": "000003",
                    "valuation_diagnostic_status": "PE_HISTORY_INSUFFICIENT",
                    "quant_score": 100,
                },
            ]
        )

        self.assertEqual([row["code"] for row in rows], ["000001", "000002", "000003"])
        self.assertEqual([row["valuation_research_rank"] for row in rows], [1, 2, 3])

    def test_sidecar_writes_research_only_outputs_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_dir = root / "upstream" / "reports" / "all_a_full_scan" / "20260817"
            report_dir.mkdir(parents=True)
            with (report_dir / "all_a_quant_screen.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "code",
                        "stock_name",
                        "industry",
                        "quant_status",
                        "quant_rank",
                        "quant_score",
                        "hard_blockers",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "code": "300223",
                        "stock_name": "北京君正",
                        "industry": "半导体",
                        "quant_status": "SECONDARY_RESEARCH",
                        "quant_rank": 1,
                        "quant_score": 62,
                        "hard_blockers": "",
                    }
                )
                writer.writerow(
                    {
                        "code": "600549",
                        "stock_name": "厦门钨业",
                        "industry": "有色金属",
                        "quant_status": "HARD_REJECT",
                        "quant_rank": 2,
                        "quant_score": 55,
                        "hard_blockers": "price_too_high",
                    }
                )
            (report_dir / "run_summary.json").write_text(
                json.dumps({"as_of_date": "2026-08-17"}),
                encoding="utf-8",
            )

            valuation = pd.DataFrame(
                {
                    "date": pd.date_range("2026-01-01", periods=30, freq="D").date,
                    "pe": [10.0] * 29 + [8.0],
                }
            )
            financial = pd.DataFrame(
                {
                    "report_date": ["2026-06-30"],
                    "disclosure_date": ["2026-07-20"],
                    "net_profit": [100.0],
                    "operating_cash_flow": [90.0],
                }
            )
            valuation_results = {
                "300223": SimpleNamespace(valuation_df=valuation, financial_df=None),
                "600549": SimpleNamespace(valuation_df=valuation, financial_df=None),
            }
            financial_results = {
                "300223": SimpleNamespace(valuation_df=None, financial_df=financial),
                "600549": SimpleNamespace(valuation_df=None, financial_df=financial),
            }

            with patch(
                "src.strategies.genge_opportunity_discovery.valuation_research_queue._parallel_fetch",
                side_effect=[valuation_results, financial_results],
            ):
                output_dir, summary = run_sidecar(
                    report_root=root / "upstream" / "reports" / "all_a_full_scan",
                    output_root=root / "output",
                    cache_dir=root / "cache",
                    max_candidates=2,
                    relaxed_reserve=1,
                    financial_review_limit=2,
                    minimum_pe_samples=20,
                )

            self.assertEqual(summary["selected_count"], 2)
            self.assertEqual(summary["relaxed_recovery_count"], 1)
            self.assertTrue(summary["current_observation_excluded_from_reference"])
            self.assertFalse(summary["formal_buy_eligible"])
            self.assertFalse(summary["automatic_promotion_allowed"])
            self.assertTrue(summary["no_auto_trade"])
            self.assertTrue((output_dir / "valuation_research_queue.csv").exists())
            self.assertTrue((output_dir / "valuation_research_queue.md").exists())
            with (output_dir / "valuation_research_queue.csv").open(encoding="utf-8") as stream:
                output_rows = list(csv.DictReader(stream))
            self.assertEqual(len(output_rows), 2)
            self.assertTrue(all(row["formal_buy_eligible"] == "False" for row in output_rows))
            self.assertTrue(
                all(row["automatic_promotion_allowed"] == "False" for row in output_rows)
            )
            self.assertTrue(all(row["no_auto_trade"] == "True" for row in output_rows))


if __name__ == "__main__":
    unittest.main()
