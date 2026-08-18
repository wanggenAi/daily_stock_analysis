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


if __name__ == "__main__":
    unittest.main()
