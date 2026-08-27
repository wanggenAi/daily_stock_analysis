from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.strategies.genge_opportunity_discovery.confirmed_holdings_source import (
    STABLE_HOLDINGS_PATH,
    assess_confirmed_holdings_source,
)


HOLDINGS = """# CURRENT_HOLDINGS

## Confirmed holdings

| Code | Name | Quantity | Average cost (CNY) | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- |
| 603369 | 今世缘 | 300 | 29.5003 | HELD | 2026-08-25 |
| 001316 | 润贝航科 | 200 | 26.0955 | HELD | 2026-08-25 |
"""


class ConfirmedHoldingsSourceTest(unittest.TestCase):
    def test_default_source_is_durable_current_holdings(self):
        self.assertEqual(STABLE_HOLDINGS_PATH, Path("CURRENT_HOLDINGS.md"))

    def test_prior_explicit_confirmation_remains_valid_until_user_reports_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CURRENT_HOLDINGS.md"
            path.write_text(HOLDINGS, encoding="utf-8")

            result = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

            self.assertTrue(result.enabled)
            self.assertEqual(result.status, "HOLDINGS_EVALUATED_DURABLE_CONFIRMED_SOURCE")
            self.assertEqual(result.row_count, 2)
            self.assertIn("2026-08-25", result.reason)
            self.assertIn("until explicit user-reported transaction", result.reason)

    def test_future_evidence_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CURRENT_HOLDINGS.md"
            path.write_text(HOLDINGS.replace("2026-08-25", "2026-08-28"), encoding="utf-8")

            result = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

            self.assertFalse(result.enabled)
            self.assertEqual(result.status, "HOLDINGS_NOT_EVALUATED_INVALID_SOURCE")
            self.assertIn("future evidence date", result.reason)

    def test_non_positive_quantity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CURRENT_HOLDINGS.md"
            path.write_text(HOLDINGS.replace("| 300 |", "| 0 |", 1), encoding="utf-8")

            result = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

            self.assertFalse(result.enabled)
            self.assertIn("non-positive", result.reason)


if __name__ == "__main__":
    unittest.main()
