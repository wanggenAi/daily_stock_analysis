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
    PublicFundamentalLoader,
    _normalize_financial_frame,
)
from src.strategies.genge_opportunity_discovery.valuation_research_report import (
    _financial_pit_row,
)


class FundamentalRecoveryTest(unittest.TestCase):
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
