from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stock_v2.engine import build_candidate, rank_candidates
from stock_v2.pipeline import run
from stock_v2.sources import load_market_context


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

    def test_global_transmission_adjusts_score_but_not_buy_state(self):
        row = {"code": "603993", "stock_name": "样本", "industry": "资源", "actionability_score": "60"}
        transmission = {
            "direction": "POSITIVE", "magnitude": "HIGH", "factors": ["COPPER", "GOLD"],
            "evidence_refs": ["https://example.com/issuer"],
        }
        candidate = build_candidate(row, "top30_deep_review.csv", set(), transmission)
        self.assertEqual(candidate.state, "WATCH")
        self.assertEqual(candidate.score, 64.0)
        self.assertTrue(any("COPPER,GOLD" in reason for reason in candidate.reasons))
        self.assertIn("https://example.com/issuer", candidate.evidence)

    def test_global_context_loader_uses_explicit_security_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "data/global_market_pulse/latest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "generated_at": "2026-10-16T00:00:00+00:00",
                "coverage": {"status": "OK", "ok_count": 2, "instrument_count": 2},
                "risk_regime": {"status": "NEUTRAL", "score": 52.0},
                "pre_open_intelligence": {"status": "AVAILABLE", "holiday_gap_risk": "NORMAL"},
                "series": {"SOX": {"status": "OK", "change_24h_pct": -1.2, "freshness": "FRESH"}},
                "security_transmission": [{
                    "code": "603993", "direction": "POSITIVE", "magnitude": "LOW",
                    "relevant_global_factors": ["COPPER"], "evidence_refs": ["https://example.com/cmoc"],
                }],
            }, ensure_ascii=False), encoding="utf-8")
            context = load_market_context(root)
            self.assertTrue(context["global"]["available"])
            self.assertEqual(context["global"]["risk_regime"]["status"], "NEUTRAL")
            self.assertIn("603993", context["global"]["security_transmission"])

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
