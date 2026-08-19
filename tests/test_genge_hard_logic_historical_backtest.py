from __future__ import annotations

import unittest
from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    HistoricalCompanyData,
    _sell_reason,
    financials_visible_as_of,
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
    point_in_time_valuation,
    simulate_company,
)


class HardLogicHistoricalBacktestTest(unittest.TestCase):
    def test_missing_disclosure_date_uses_conservative_lag_not_report_date(self):
        frame = pd.DataFrame(
            [{"report_date": "2024-12-31", "disclosure_date": None, "recurring_profit": 100, "roe": 12}]
        )
        normalized = normalize_financial_point_in_time(frame)

        self.assertTrue(financials_visible_as_of(normalized, date(2025, 3, 1)).empty)
        self.assertEqual(len(financials_visible_as_of(normalized, date(2025, 5, 20))), 1)

    def test_nat_disclosure_date_uses_same_conservative_fallback(self):
        frame = pd.DataFrame(
            [{
                "report_date": date(2024, 12, 31),
                "disclosure_date": pd.NaT,
                "recurring_profit": 100,
                "roe": 12,
            }]
        )
        normalized = normalize_financial_point_in_time(frame)

        self.assertEqual(len(normalized), 1)
        self.assertTrue(financials_visible_as_of(normalized, date(2025, 3, 1)).empty)
        self.assertEqual(len(financials_visible_as_of(normalized, date(2025, 5, 20))), 1)

    def test_future_disclosure_cannot_improve_historical_hard_logic(self):
        frame = normalize_financial_point_in_time(
            pd.DataFrame(
                [
                    {
                        "report_date": "2023-12-31",
                        "disclosure_date": "2024-04-20",
                        "recurring_profit": 100,
                        "cash_conversion_ratio": 1.0,
                        "roe": 12,
                        "debt_ratio": 40,
                    },
                    {
                        "report_date": "2024-12-31",
                        "disclosure_date": "2025-04-20",
                        "recurring_profit": 200,
                        "cash_conversion_ratio": 1.1,
                        "roe": 15,
                        "debt_ratio": 35,
                    },
                ]
            )
        )

        before = point_in_time_hard_logic(frame, date(2025, 3, 31))
        after = point_in_time_hard_logic(frame, date(2025, 4, 21))

        self.assertNotIn("profit_growth_strong", before["reasons"])
        self.assertIn("profit_growth_strong", after["reasons"])
        self.assertEqual(after["state"], "PASS")

    def test_valuation_reference_excludes_current_observation(self):
        start = date(2022, 1, 1)
        rows = [{"date": start + timedelta(days=i), "pe": 20.0} for i in range(130)]
        rows.append({"date": start + timedelta(days=130), "pe": 40.0})
        state = point_in_time_valuation(pd.DataFrame(rows), start + timedelta(days=130))

        self.assertIsNotNone(state)
        self.assertAlmostEqual(state["historical_reference_pe"], 20.0)
        self.assertAlmostEqual(state["current_pe"], 40.0)
        self.assertAlmostEqual(state["required_profit_growth_pct"], 100.0)

    def test_walk_forward_buys_low_expectation_and_sells_when_expectations_fill(self):
        start = date(2022, 1, 3)
        dates = [start + timedelta(days=i) for i in range(420)]
        prices = []
        valuations = []
        for i, day in enumerate(dates):
            if i < 180:
                pe = close = 20.0
            elif i < 260:
                pe = close = 12.0
            else:
                pe = close = 24.0
            prices.append(
                {
                    "date": day,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 1_000_000,
                    "amount": 20_000_000,
                }
            )
            valuations.append({"date": day, "pe": pe})

        financial = pd.DataFrame(
            [
                {
                    "report_date": "2020-12-31",
                    "disclosure_date": "2021-04-15",
                    "recurring_profit": 100,
                    "cash_conversion_ratio": 1.0,
                    "roe": 12,
                    "debt_ratio": 40,
                },
                {
                    "report_date": "2021-12-31",
                    "disclosure_date": "2022-04-15",
                    "recurring_profit": 120,
                    "cash_conversion_ratio": 1.0,
                    "roe": 12,
                    "debt_ratio": 40,
                },
            ]
        )
        data = HistoricalCompanyData(
            code="600001",
            stock_name="测试牛股",
            price_df=pd.DataFrame(prices),
            valuation_df=pd.DataFrame(valuations),
            financial_df=financial,
            warnings=[],
        )

        trades, signals, case = simulate_company(
            data,
            start_date=dates[0],
            end_date=dates[-1],
            evaluation_stride=5,
            cost_bps_per_side=0.0,
        )

        self.assertGreaterEqual(len(trades), 1)
        self.assertEqual(signals[0]["signal_action"], "BUY")
        self.assertLessEqual(float(trades[0]["entry_price"]), 12.0)
        self.assertEqual(trades[0]["exit_reason"], "SELL_EXPECTATIONS_FULL_HIGH_VALUATION")
        self.assertGreaterEqual(float(trades[0]["exit_price"]), 24.0)
        self.assertGreater(float(trades[0]["net_return_pct"]), 90.0)
        self.assertEqual(case["status"], "OK")

    def test_expectation_exit_requires_high_historical_valuation_zone(self):
        logic = {"state": "PASS"}
        low_zone = {
            "required_profit_growth_pct": 40,
            "supported_profit_growth_base_pct": 20,
            "historical_pe_percentile": 55,
        }
        high_zone = dict(low_zone, historical_pe_percentile=80)
        self.assertIsNone(_sell_reason(low_zone, logic))
        self.assertEqual(_sell_reason(high_zone, logic), "SELL_EXPECTATIONS_FULL_HIGH_VALUATION")

    def test_hard_logic_invalidation_exits_even_when_valuation_is_low(self):
        self.assertEqual(
            _sell_reason(
                {
                    "required_profit_growth_pct": -20,
                    "supported_profit_growth_base_pct": 20,
                    "historical_pe_percentile": 5,
                },
                {"state": "BLOCKED"},
            ),
            "SELL_HARD_LOGIC_INVALIDATED",
        )

    def test_negative_visible_core_profit_blocks_new_buy(self):
        frame = normalize_financial_point_in_time(
            pd.DataFrame(
                [{"report_date": "2024-12-31", "disclosure_date": "2025-04-20", "recurring_profit": -1}]
            )
        )
        state = point_in_time_hard_logic(frame, date(2025, 4, 21))
        self.assertEqual(state["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
