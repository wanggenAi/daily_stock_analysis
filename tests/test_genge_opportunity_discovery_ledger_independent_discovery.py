from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import merge_sources
from src.strategies.genge_opportunity_discovery.ledger_independent_discovery import (
    DISCOVERY_CONTRACT_VERSION,
    build_discovery_rows,
)


class LedgerIndependentDiscoveryTest(unittest.TestCase):
    def test_archived_name_can_remain_in_discovery_but_leave_downstream_recall(self):
        all_a = [
            {
                "code": "600312",
                "stock_name": "current-evidence-name",
                "industry": "电力设备",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 99,
                "hard_blockers": "",
            },
            {
                "code": "603993",
                "stock_name": "another-name",
                "industry": "有色金属",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 2,
                "quant_score": 90,
                "hard_blockers": "",
            },
        ]
        industry = [
            {
                "code": "600312",
                "industry": "电力设备",
                "industry_research_rank": 1,
                "quant_status": "PRIORITY_RESEARCH",
                "quant_score": 99,
                "hard_blockers": "",
            }
        ]

        discovery = build_discovery_rows(
            all_a,
            industry,
            global_limit=10,
            relaxed_reserve=0,
            per_industry=3,
        )
        downstream = merge_sources(
            all_a,
            industry,
            global_limit=10,
            relaxed_reserve=0,
            per_industry=3,
            excluded_codes={"600312"},
        )

        discovery_codes = {row["code"] for row in discovery}
        downstream_codes = {row["code"] for row in downstream}
        self.assertIn("600312", discovery_codes)
        self.assertNotIn("600312", downstream_codes)
        self.assertIn("603993", discovery_codes)
        self.assertIn("603993", downstream_codes)

    def test_discovery_rows_prove_no_ledger_or_durable_recall_filter_was_applied(self):
        rows = build_discovery_rows(
            [
                {
                    "code": "600406",
                    "industry": "电网设备",
                    "quant_status": "PRIORITY_RESEARCH",
                    "quant_rank": 1,
                    "quant_score": 90,
                    "hard_blockers": "",
                }
            ],
            [],
            global_limit=1,
            relaxed_reserve=0,
            per_industry=3,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["discovery_contract_version"], DISCOVERY_CONTRACT_VERSION)
        self.assertFalse(row["discovery_ledger_filter_applied"])
        self.assertFalse(row["discovery_durable_recall_applied"])
        self.assertFalse(row["formal_signal_eligible"])
        self.assertFalse(row["automatic_promotion_allowed"])
        self.assertTrue(row["no_auto_trade"])


if __name__ == "__main__":
    unittest.main()
