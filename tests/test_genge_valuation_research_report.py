from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import FundamentalFetchResult
from src.strategies.genge_opportunity_discovery.valuation_research_report import (
    build_pe_reference_diagnostic,
    build_valuation_research_rows,
    write_report,
)


class _FakeLoader:
    def __init__(self, by_code):
        self.by_code = by_code
        self.calls = []

    def load(self, code, *, years, fetch_valuation, fetch_financial):
        self.calls.append((code, years, fetch_valuation, fetch_financial))
        return self.by_code[code]


class ValuationResearchReportTest(unittest.TestCase):
    def test_pe_reference_excludes_current_observation(self):
        frame = pd.DataFrame(
            {
                "date": ["2026-08-13", "2026-08-14", "2026-08-15"],
                "pe": [10.0, 20.0, 30.0],
            }
        )
        result = build_pe_reference_diagnostic(frame, as_of=date(2026, 8, 15))

        self.assertEqual(result.status, "OK")
        self.assertEqual(result.current_pe, 30.0)
        self.assertEqual(result.reference_median_pe, 15.0)
        self.assertEqual(result.sample_count, 2)
        self.assertAlmostEqual(result.required_profit_growth, 1.0)

    def test_non_positive_pe_is_not_forced_into_pe_model(self):
        frame = pd.DataFrame(
            {
                "date": ["2026-08-13", "2026-08-14"],
                "pe": [-10.0, 0.0],
            }
        )
        result = build_pe_reference_diagnostic(frame, as_of=date(2026, 8, 14))
        self.assertEqual(result.status, "PE_MODEL_NOT_APPLICABLE")
        self.assertIsNone(result.required_profit_growth)

    def test_queue_ranks_low_implied_expectation_before_high_expectation(self):
        source_rows = [
            {"code": "600549", "stock_name": "厦门钨业", "industry": "稀有金属", "quant_status": "SECONDARY_RESEARCH", "quant_score": 60},
            {"code": "601020", "stock_name": "华钰矿业", "industry": "贵金属", "quant_status": "SECONDARY_RESEARCH", "quant_score": 70},
            {"code": "000001", "stock_name": "硬拒绝", "industry": "银行", "quant_status": "HARD_REJECT", "quant_score": 99},
        ]
        loader = _FakeLoader(
            {
                "600549": FundamentalFetchResult(
                    valuation_df=pd.DataFrame(
                        {"date": ["2026-08-13", "2026-08-14", "2026-08-15"], "pe": [20.0, 20.0, 22.0]}
                    ),
                    financial_df=pd.DataFrame(
                        {
                            "report_date": ["2026-06-30"],
                            "disclosure_date": ["2026-08-10"],
                            "net_profit": [100.0],
                            "operating_cash_flow": [90.0],
                        }
                    ),
                ),
                "601020": FundamentalFetchResult(
                    valuation_df=pd.DataFrame(
                        {"date": ["2026-08-13", "2026-08-14", "2026-08-15"], "pe": [10.0, 10.0, 25.0]}
                    ),
                    financial_df=pd.DataFrame(
                        {
                            "report_date": ["2026-06-30"],
                            "disclosure_date": ["2026-08-11"],
                            "net_profit": [100.0],
                            "operating_cash_flow": [40.0],
                        }
                    ),
                ),
            }
        )

        rows = build_valuation_research_rows(
            source_rows,
            as_of=date(2026, 8, 15),
            loader=loader,
            research_limit=80,
        )

        self.assertEqual([row["code"] for row in rows], ["600549", "601020"])
        self.assertAlmostEqual(rows[0]["required_profit_growth_vs_reference"], 0.1)
        self.assertAlmostEqual(rows[1]["required_profit_growth_vs_reference"], 1.5)
        self.assertTrue(all(row["formal_signal_eligible"] is False for row in rows))
        self.assertTrue(all(row["automatic_promotion_allowed"] is False for row in rows))
        self.assertTrue(all(row["no_auto_trade"] is True for row in rows))
        self.assertEqual({call[0] for call in loader.calls}, {"600549", "601020"})

    def test_disclosure_date_guard_prevents_future_financial_leakage(self):
        source_rows = [
            {"code": "600549", "stock_name": "厦门钨业", "quant_status": "SECONDARY_RESEARCH", "quant_score": 60}
        ]
        loader = _FakeLoader(
            {
                "600549": FundamentalFetchResult(
                    valuation_df=pd.DataFrame(
                        {"date": ["2026-08-13", "2026-08-14", "2026-08-15"], "pe": [20.0, 20.0, 20.0]}
                    ),
                    financial_df=pd.DataFrame(
                        {
                            "report_date": ["2026-03-31", "2026-06-30"],
                            "disclosure_date": ["2026-04-25", "2026-08-20"],
                            "net_profit": [80.0, 999.0],
                            "operating_cash_flow": [70.0, 999.0],
                        }
                    ),
                )
            }
        )

        rows = build_valuation_research_rows(
            source_rows,
            as_of=date(2026, 8, 15),
            loader=loader,
        )
        self.assertEqual(rows[0]["headline_net_profit"], 80.0)
        self.assertEqual(rows[0]["financial_report_date"], date(2026, 3, 31))
        self.assertEqual(rows[0]["earnings_point_in_time_method"], "DISCLOSURE_DATE_PIT")

    def test_write_report_creates_sidecar_without_formal_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            (report_dir / "run_summary.json").write_text(
                json.dumps({"as_of_date": "2026-08-15"}), encoding="utf-8"
            )
            with (report_dir / "top80_evidence_queue.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["code", "stock_name", "industry", "quant_status", "quant_score", "hard_blockers"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "code": "600549",
                        "stock_name": "厦门钨业",
                        "industry": "稀有金属",
                        "quant_status": "SECONDARY_RESEARCH",
                        "quant_score": 60,
                        "hard_blockers": "",
                    }
                )

            fake = _FakeLoader(
                {
                    "600549": FundamentalFetchResult(
                        valuation_df=pd.DataFrame(
                            {"date": ["2026-08-13", "2026-08-14", "2026-08-15"], "pe": [20.0, 20.0, 22.0]}
                        ),
                        financial_df=pd.DataFrame(
                            {
                                "report_date": ["2026-06-30"],
                                "disclosure_date": ["2026-08-10"],
                                "net_profit": [100.0],
                                "operating_cash_flow": [90.0],
                            }
                        ),
                    )
                }
            )

            from unittest.mock import patch

            with patch(
                "src.strategies.genge_opportunity_discovery.valuation_research_report.PublicFundamentalLoader",
                return_value=fake,
            ):
                rows = write_report(report_dir, research_limit=80)

            self.assertEqual(len(rows), 1)
            self.assertTrue((report_dir / "valuation_research_queue.csv").exists())
            self.assertTrue((report_dir / "valuation_research_queue.md").exists())
            text = (report_dir / "valuation_research_queue.md").read_text(encoding="utf-8")
            self.assertIn("formal signal eligible: False", text)


if __name__ == "__main__":
    unittest.main()
