from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from stock_v2.engine import build_candidate, rank_candidates
from stock_v2.pipeline import run


class StockV2Tests(unittest.TestCase):
    def test_missing_evidence_does_not_hide_candidate(self):
        row = {
            "code": "600001", "stock_name": "样本A", "industry": "行业A",
            "actionability_score": "76", "raw_latest_close": "10.0",
            "pullback_entry_low": "9.8", "pullback_entry_high": "10.2",
            "company_evidence_status": "MISSING",
        }
        candidate = build_candidate(row, "top30_deep_review.csv", set())
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.state, "BUY")

    def test_hard_reject_stays_rejected(self):
        row = {"code": "600002", "stock_name": "样本B", "actionability_score": "99", "quant_status": "HARD_REJECT"}
        candidate = build_candidate(row, "top30_deep_review.csv", set())
        self.assertEqual(candidate.state, "REJECT")

    def test_industry_cap_then_refill(self):
        rows = []
        for i in range(12):
            rows.append({"code": f"600{i:03d}", "stock_name": f"S{i}", "industry": "同行业" if i < 8 else f"行业{i}", "actionability_score": str(90-i)})
        chosen, _ = rank_candidates(rows, "top30_deep_review.csv", set(), top_n=10, industry_cap=2)
        self.assertEqual(len(chosen), 10)
        self.assertLessEqual(sum(c.industry == "同行业" for c in chosen[:6]), 2)

    def test_pipeline_fallback_builds_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "LATEST_RESEARCH_RADAR.md").write_text(
                "# Radar\n\n| Top | Code | Name | Industry | Tier | PASS | UNKNOWN | Quant | Follow-up |\n|---:|---|---|---|---|---:|---:|---:|---|\n" +
                "\n".join(f"| {i+1} | 600{i:03d} | 样本{i} | 行业{i} | UNKNOWN_RESEARCH | 3 | 2 | {80-i} | EVIDENCE_CLOSURE |" for i in range(10)) + "\n",
                encoding="utf-8",
            )
            payload = run(root, top_n=30, industry_cap=3, output=root / "V2_DASHBOARD.md", json_output=root / "data/v2/latest_run.json")
            self.assertEqual(payload["stats"]["visible_pool"], 10)
            self.assertEqual(payload["source"]["mode"], "COMMITTED_SNAPSHOT_FALLBACK")
            self.assertTrue((root / "V2_DASHBOARD.md").exists())
            self.assertTrue((root / "data/v2/latest_run.json").exists())


if __name__ == "__main__":
    unittest.main()
