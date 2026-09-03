from __future__ import annotations

import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import (
    FINANCIAL_CACHE_KIND,
    FundamentalFetchResult,
    PublicFundamentalLoader,
    _normalize_financial_frame,
)
from src.strategies.genge_opportunity_discovery.valuation_research_report import (
    _financial_pit_row,
    _load_many,
    build_valuation_research_rows,
)


class _SequencedLoader:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def load(self, code, *, years, fetch_valuation, fetch_financial):
        self.calls.append((code, years, fetch_valuation, fetch_financial))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FundamentalRecoveryTest(unittest.TestCase):
    @staticmethod
    def _valuation_frame():
        return pd.DataFrame(
            {
                "date": ["2026-08-13", "2026-08-14", "2026-08-15"],
                "pe": [20.0, 20.0, 22.0],
            }
        )

    @staticmethod
    def _financial_frame():
        return pd.DataFrame(
            {
                "report_date": ["2026-06-30"],
                "disclosure_date": ["2026-08-10"],
                "net_profit": [100.0],
                "operating_cash_flow": [90.0],
            }
        )

    def test_research_loader_retries_exception_then_recovers(self):
        loader = _SequencedLoader(
            [
                ConnectionError("transient"),
                FundamentalFetchResult(valuation_df=self._valuation_frame()),
            ]
        )
        with patch(
            "src.strategies.genge_opportunity_discovery.valuation_research_report.time.sleep",
            return_value=None,
        ):
            result = _load_many(
                loader,
                ["600519"],
                years=5,
                fetch_valuation=True,
                fetch_financial=False,
                max_workers=1,
            )["600519"]

        self.assertIsNotNone(result.valuation_df)
        self.assertEqual(len(loader.calls), 2)
        self.assertIn(
            "research_loader:attempt_1:ConnectionError",
            result.provider_errors["valuation"],
        )

    def test_research_loader_combines_partial_recovery_without_refetching_success(self):
        loader = _SequencedLoader(
            [
                FundamentalFetchResult(),
                FundamentalFetchResult(valuation_df=self._valuation_frame()),
                FundamentalFetchResult(financial_df=self._financial_frame()),
            ]
        )
        with patch(
            "src.strategies.genge_opportunity_discovery.valuation_research_report.time.sleep",
            return_value=None,
        ):
            result = _load_many(
                loader,
                ["600519"],
                years=5,
                fetch_valuation=True,
                fetch_financial=True,
                max_workers=1,
            )["600519"]

        self.assertIsNotNone(result.valuation_df)
        self.assertIsNotNone(result.financial_df)
        self.assertEqual(
            loader.calls,
            [
                ("600519", 5, True, True),
                ("600519", 5, True, True),
                ("600519", 5, False, True),
            ],
        )

    def test_research_loader_does_not_repeat_first_success(self):
        loader = _SequencedLoader(
            [FundamentalFetchResult(valuation_df=self._valuation_frame())]
        )
        result = _load_many(
            loader,
            ["600519"],
            years=5,
            fetch_valuation=True,
            fetch_financial=False,
            max_workers=1,
        )["600519"]

        self.assertIsNotNone(result.valuation_df)
        self.assertEqual(loader.calls, [("600519", 5, True, False)])

    def test_research_loader_exhaustion_is_explicit_and_never_synthetic(self):
        loader = _SequencedLoader([FundamentalFetchResult() for _ in range(3)])
        with patch(
            "src.strategies.genge_opportunity_discovery.valuation_research_report.time.sleep",
            return_value=None,
        ):
            result = _load_many(
                loader,
                ["000001"],
                years=5,
                fetch_valuation=True,
                fetch_financial=True,
                max_workers=1,
            )["000001"]

        self.assertIsNone(result.valuation_df)
        self.assertIsNone(result.financial_df)
        self.assertEqual(len(loader.calls), 3)
        self.assertIn(
            "research_loader:recovery_exhausted:valuation_unavailable",
            result.provider_errors["valuation"],
        )
        self.assertIn(
            "research_loader:recovery_exhausted:financial_unavailable",
            result.provider_errors["financial"],
        )
        self.assertFalse(
            any(
                "synthetic" in error.lower()
                for errors in result.provider_errors.values()
                for error in errors
            )
        )

    def test_recovered_valuation_continues_research_instead_of_early_missing_reject(self):
        loader = _SequencedLoader(
            [
                FundamentalFetchResult(valuation_df=pd.DataFrame()),
                FundamentalFetchResult(valuation_df=self._valuation_frame()),
                FundamentalFetchResult(financial_df=self._financial_frame()),
            ]
        )
        with patch(
            "src.strategies.genge_opportunity_discovery.valuation_research_report.time.sleep",
            return_value=None,
        ):
            rows = build_valuation_research_rows(
                [
                    {
                        "code": "600519",
                        "stock_name": "贵州茅台",
                        "quant_status": "PRIORITY_RESEARCH",
                        "quant_rank": 1,
                        "quant_score": 90,
                    }
                ],
                as_of=date(2026, 8, 15),
                loader=loader,
                minimum_pe_samples=1,
                max_workers=1,
            )

        self.assertEqual(rows[0]["valuation_diagnostic_status"], "OK")
        self.assertEqual(rows[0]["financial_review_status"], "OK")
        self.assertEqual(rows[0]["earnings_point_in_time_method"], "DISCLOSURE_DATE_PIT")
        self.assertIn(
            "research_loader:attempt_1:empty_result",
            rows[0]["valuation_provider_errors"],
        )

    def test_normalized_cache_preserves_canonical_net_profit(self):
        frame = pd.DataFrame(
            {
                "report_date": ["2026-06-30"],
                "disclosure_date": ["2026-08-20"],
                "net_profit": [123.0],
                "operating_cash_flow": [99.0],
            }
        )
        normalized = _normalize_financial_frame(frame)
        self.assertEqual(float(normalized.iloc[0]["net_profit"]), 123.0)
        self.assertEqual(float(normalized.iloc[0]["operating_cash_flow"]), 99.0)

    def test_valuation_provider_retries_transient_failures(self):
        fake_ak = types.ModuleType("akshare")
        calls = {"pe": 0, "pb": 0, "market_cap": 0}

        def valuation(*, symbol, indicator, period):
            key = {
                "市盈率(TTM)": "pe",
                "市净率": "pb",
                "总市值": "market_cap",
            }[indicator]
            calls[key] += 1
            if key == "pe" and calls[key] < 3:
                raise ConnectionError("transient")
            return pd.DataFrame({"date": ["2026-09-02"], "value": [10.0]})

        fake_ak.stock_zh_valuation_baidu = valuation
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"akshare": fake_ak}
        ), patch(
            "src.strategies.genge_cycle_bottom.fundamentals.time.sleep",
            return_value=None,
        ):
            loader = PublicFundamentalLoader(Path(tmp))
            frame, provider, errors, cache_hit = loader.load_valuation("600519", years=5)

        self.assertFalse(cache_hit)
        self.assertEqual(provider, "akshare.stock_zh_valuation_baidu")
        self.assertIsNotNone(frame)
        self.assertEqual(calls["pe"], 3)
        self.assertEqual(calls["pb"], 1)
        self.assertEqual(calls["market_cap"], 1)
        self.assertTrue(any("attempt_1:ConnectionError" in item for item in errors))
        self.assertTrue(any("attempt_2:ConnectionError" in item for item in errors))

    def test_financial_fallback_merges_reported_profit_and_cashflow(self):
        fake_ak = types.ModuleType("akshare")
        seen_symbols = []

        def indicator(*, symbol, start_year):
            return pd.DataFrame(
                {
                    "日期": ["2026-06-30"],
                    "资产负债率(%)": [31.0],
                    "销售毛利率(%)": [90.0],
                }
            )

        def profit(*, symbol):
            seen_symbols.append(symbol)
            return pd.DataFrame(
                {
                    "REPORT_DATE": ["2026-06-30"],
                    "NOTICE_DATE": ["2026-08-20"],
                    "PARENT_NETPROFIT": [100.0],
                }
            )

        def cashflow(*, symbol):
            seen_symbols.append(symbol)
            return pd.DataFrame(
                {
                    "REPORT_DATE": ["2026-06-30"],
                    "NOTICE_DATE": ["2026-08-22"],
                    "NETCASH_OPERATE": [88.0],
                }
            )

        fake_ak.stock_financial_analysis_indicator = indicator
        fake_ak.stock_profit_sheet_by_report_em = profit
        fake_ak.stock_cash_flow_sheet_by_report_em = cashflow

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"akshare": fake_ak}
        ), patch(
            "src.strategies.genge_cycle_bottom.fundamentals.time.sleep",
            return_value=None,
        ):
            loader = PublicFundamentalLoader(Path(tmp))
            frame, provider, errors, cache_hit = loader.load_financial("600519", years=5)
            cache_exists = (Path(tmp) / FINANCIAL_CACHE_KIND / "600519.csv").exists()

        self.assertFalse(cache_hit)
        self.assertEqual(errors, [])
        self.assertIn("eastmoney_statements", provider)
        self.assertEqual(seen_symbols, ["SH600519", "SH600519"])
        self.assertIsNotNone(frame)
        row = frame.iloc[-1]
        self.assertEqual(float(row["net_profit"]), 100.0)
        self.assertEqual(float(row["operating_cash_flow"]), 88.0)
        self.assertEqual(float(row["debt_ratio"]), 31.0)
        self.assertEqual(str(row["disclosure_date"]), "2026-08-22")
        self.assertTrue(cache_exists)

        pit_row, pit_method = _financial_pit_row(frame, as_of=date(2026, 8, 21))
        self.assertEqual(pit_row, {})
        self.assertEqual(pit_method, "DISCLOSURE_DATE_NOT_YET_AVAILABLE")
        pit_row, pit_method = _financial_pit_row(frame, as_of=date(2026, 8, 22))
        self.assertEqual(float(pit_row["net_profit"]), 100.0)
        self.assertEqual(pit_method, "DISCLOSURE_DATE_PIT")

    def test_financial_fallback_exhaustion_stays_explicit_without_fake_values(self):
        fake_ak = types.ModuleType("akshare")
        calls = {"primary": 0, "profit": 0, "cash": 0}

        def primary(*, symbol, start_year):
            calls["primary"] += 1
            raise TimeoutError("down")

        def profit(*, symbol):
            calls["profit"] += 1
            raise TimeoutError("down")

        def cash(*, symbol):
            calls["cash"] += 1
            raise TimeoutError("down")

        fake_ak.stock_financial_analysis_indicator = primary
        fake_ak.stock_profit_sheet_by_report_em = profit
        fake_ak.stock_cash_flow_sheet_by_report_em = cash

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"akshare": fake_ak}
        ), patch(
            "src.strategies.genge_cycle_bottom.fundamentals.time.sleep",
            return_value=None,
        ):
            loader = PublicFundamentalLoader(Path(tmp))
            frame, provider, errors, cache_hit = loader.load_financial("000001", years=5)

        self.assertFalse(cache_hit)
        self.assertIsNone(frame)
        self.assertEqual(provider, "none")
        self.assertEqual(calls, {"primary": 3, "profit": 3, "cash": 3})
        self.assertGreaterEqual(len(errors), 9)
        self.assertFalse(any("synthetic" in item.lower() for item in errors))


if __name__ == "__main__":
    unittest.main()
