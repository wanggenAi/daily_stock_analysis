from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import merge_sources


class IndustryValuationBridgeTest(unittest.TestCase):
    def test_industry_champion_is_added_when_global_budget_misses_industry(self):
        all_a = [
            {
                "code": f"600{index:03d}",
                "industry": "热门行业",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": index + 1,
                "quant_score": 90 - index,
                "hard_blockers": "",
            }
            for index in range(10)
        ]
        all_a.append(
            {
                "code": "000999",
                "industry": "冷门行业",
                "quant_status": "SECONDARY_RESEARCH",
                "quant_rank": 999,
                "quant_score": 50,
                "hard_blockers": "",
            }
        )
        industry = [
            {
                "code": "000999",
                "industry": "冷门行业",
                "industry_research_rank": 1,
                "quant_status": "SECONDARY_RESEARCH",
                "quant_score": 50,
                "hard_blockers": "",
            }
        ]

        rows = merge_sources(
            all_a,
            industry,
            global_limit=3,
            relaxed_reserve=0,
            per_industry=3,
        )
        by_code = {row["code"]: row for row in rows}
        self.assertIn("000999", by_code)
        self.assertEqual(by_code["000999"]["valuation_source_channel"], "INDUSTRY_CHAMPION")

    def test_duplicate_global_and_industry_candidate_is_marked_both(self):
        all_a = [
            {
                "code": "600001",
                "industry": "电力设备",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 90,
                "hard_blockers": "",
            }
        ]
        industry = [
            {
                "code": "600001",
                "industry": "电力设备",
                "industry_research_rank": 1,
                "quant_status": "PRIORITY_RESEARCH",
                "quant_score": 90,
                "hard_blockers": "",
            }
        ]
        rows = merge_sources(all_a, industry, global_limit=1, relaxed_reserve=0, per_industry=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["valuation_source_channel"], "BOTH")

    def test_duplicate_global_row_backfills_missing_industry_provenance(self):
        all_a = [
            {
                "code": "603369",
                "industry": "",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 82.9,
                "hard_blockers": "",
            }
        ]
        industry = [
            {
                "code": "603369",
                "industry": "C15酒、饮料和精制茶制造业",
                "industry_research_rank": 2,
                "industry_candidate_state": "RESEARCH_CANDIDATE",
                "industry_status": "RESEARCH_CANDIDATES_AVAILABLE",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_score": 82.9,
                "hard_blockers": "",
            }
        ]

        rows = merge_sources(all_a, industry, global_limit=1, relaxed_reserve=0, per_industry=3)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["valuation_source_channel"], "BOTH")
        self.assertEqual(rows[0]["industry"], "C15酒、饮料和精制茶制造业")
        self.assertEqual(rows[0]["industry_research_rank"], 2)
        self.assertEqual(rows[0]["industry_candidate_state"], "RESEARCH_CANDIDATE")

    def test_hard_blocked_industry_name_is_not_forced_into_valuation(self):
        all_a = []
        industry = [
            {
                "code": "000002",
                "industry": "风险行业",
                "industry_research_rank": 1,
                "quant_status": "HARD_REJECT",
                "quant_score": 99,
                "hard_blockers": "financial_data_invalid",
            }
        ]
        rows = merge_sources(all_a, industry, global_limit=0, relaxed_reserve=0, per_industry=3)
        self.assertEqual(rows, [])

    def test_price_only_industry_blocker_is_research_eligible(self):
        all_a = []
        industry = [
            {
                "code": "600406",
                "industry": "电网设备",
                "industry_research_rank": 1,
                "quant_status": "HARD_REJECT",
                "quant_score": 27.5,
                "hard_blockers": "price_too_high",
            }
        ]

        rows = merge_sources(all_a, industry, global_limit=0, relaxed_reserve=0, per_industry=3)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "600406")
        self.assertEqual(rows[0]["valuation_source_channel"], "INDUSTRY_CHAMPION")
        self.assertEqual(rows[0]["hard_blockers"], "price_too_high")
        self.assertFalse(rows[0]["formal_signal_eligible"])
        self.assertFalse(rows[0]["automatic_promotion_allowed"])
        self.assertTrue(rows[0]["no_auto_trade"])

    def test_curated_research_pool_recalls_low_rank_price_blocked_name_without_promotion(self):
        all_a = [
            {
                "code": f"600{index:03d}",
                "industry": "热门行业",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": index + 1,
                "quant_score": 90 - index,
                "hard_blockers": "",
            }
            for index in range(10)
        ]
        all_a.append(
            {
                "code": "603993",
                "stock_name": "洛阳钼业",
                "industry": "有色金属",
                "quant_status": "HARD_REJECT",
                "quant_rank": 2115,
                "quant_score": 37.2,
                "hard_reject_blockers": "price_too_high",
            }
        )

        rows = merge_sources(
            all_a,
            [],
            global_limit=3,
            relaxed_reserve=0,
            per_industry=3,
            curated_codes={"603993.SH"},
        )
        by_code = {row["code"]: row for row in rows}
        recalled = by_code["603993"]

        self.assertEqual(recalled["valuation_source_channel"], "CURATED_RESEARCH_POOL")
        self.assertTrue(recalled["curated_research_recall"])
        self.assertEqual(recalled["wide_recall_reason"], "CURATED_DURABLE_RESEARCH")
        self.assertEqual(recalled["source_hard_blockers"], "price_too_high")
        self.assertEqual(recalled["hard_reject_blockers"], "price_too_high")
        self.assertFalse(recalled["formal_signal_eligible"])
        self.assertFalse(recalled["automatic_promotion_allowed"])
        self.assertTrue(recalled["no_auto_trade"])

    def test_curated_recall_marks_existing_row_without_changing_existing_channel(self):
        all_a = [
            {
                "code": "600406",
                "industry": "电网设备",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 90,
                "hard_blockers": "",
            }
        ]
        rows = merge_sources(
            all_a,
            [],
            global_limit=1,
            relaxed_reserve=0,
            curated_codes={"600406.SH"},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["valuation_source_channel"], "GLOBAL_RECALL")
        self.assertTrue(rows[0]["curated_research_recall"])
        self.assertFalse(rows[0]["formal_signal_eligible"])


if __name__ == "__main__":
    unittest.main()