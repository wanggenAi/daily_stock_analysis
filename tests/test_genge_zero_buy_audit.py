from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.strategies.genge_opportunity_discovery.zero_buy_audit import audit_zero_buy


class ZeroBuyAuditTest(unittest.TestCase):
    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_green_market_zero_buy_requires_second_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run_summary.json").write_text(
                json.dumps({"market_regime_status": "GREEN"}), encoding="utf-8"
            )
            self._write_csv(
                root / "near_ready.csv",
                [{
                    "code": "600001",
                    "stock_name": "A",
                    "missing_conditions": "exit_profile_sample_insufficient",
                    "hard_blockers": "",
                }],
            )
            audit, second_pass = audit_zero_buy(root)
            self.assertEqual(audit["status"], "ZERO_BUY_REQUIRES_SECOND_PASS")
            self.assertTrue(audit["requires_second_pass"])
            self.assertEqual(audit["soft_only_candidate_count"], 1)
            self.assertEqual(second_pass[0]["code"], "600001")

    def test_red_market_zero_buy_is_defensively_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run_summary.json").write_text(
                json.dumps({"market_regime_status": "RED"}), encoding="utf-8"
            )
            audit, _ = audit_zero_buy(root)
            self.assertEqual(audit["status"], "ZERO_BUY_DEFENSIVE_MARKET_ALLOWED")
            self.assertFalse(audit["requires_second_pass"])

    def test_existing_buy_passes_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run_summary.json").write_text(
                json.dumps({"market_regime_status": "GREEN"}), encoding="utf-8"
            )
            self._write_csv(
                root / "buy_ready.csv",
                [{"code": "600002", "stock_name": "B", "classification": "BUY_READY"}],
            )
            audit, _ = audit_zero_buy(root)
            self.assertEqual(audit["status"], "FORMAL_BUY_PRESENT")
            self.assertEqual(audit["formal_buy_count"], 1)
            self.assertFalse(audit["requires_second_pass"])


if __name__ == "__main__":
    unittest.main()
