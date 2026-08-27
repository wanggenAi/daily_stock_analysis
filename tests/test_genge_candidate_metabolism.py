from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import (
    _read_candidate_ledger_codes,
    merge_sources,
)


class CandidateMetabolismTest(unittest.TestCase):
    def test_ledger_parser_uses_only_active_and_archived_candidate_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "V31_CANDIDATE_LEDGER.md"
            ledger.write_text(
                """# V31_CANDIDATE_LEDGER

## CURRENT DEEP RESEARCH QUEUE
| 1 | 999999 | decoy | WATCH |

## Active candidate ledger

### 603993 洛阳钼业
- current tier: A1

### 600309 万华化学
- current tier: A1

## Research-only observations retained outside executable queue
### 688739 成大生物

## Archived / INVALIDATED

### 600312 平高电气
- invalidated: true
""",
                encoding="utf-8",
            )

            active, invalidated = _read_candidate_ledger_codes(ledger)

            self.assertEqual(active, {"603993", "600309"})
            self.assertEqual(invalidated, {"600312"})

    def test_invalidated_candidate_is_suppressed_from_every_recall_channel(self):
        all_a = [
            {
                "code": "600312",
                "industry": "电力设备",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 99,
                "hard_blockers": "",
            },
            {
                "code": "603993",
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

        rows = merge_sources(
            all_a,
            industry,
            global_limit=10,
            relaxed_reserve=0,
            per_industry=3,
            curated_codes={"600312", "603993"},
            excluded_codes={"600312"},
        )
        codes = {row["code"] for row in rows}

        self.assertNotIn("600312", codes)
        self.assertIn("603993", codes)

    def test_active_candidate_can_be_recalled_despite_low_rank_and_price_blocker(self):
        all_a = [
            {
                "code": "600001",
                "industry": "热门行业",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": 1,
                "quant_score": 95,
                "hard_blockers": "",
            },
            {
                "code": "603993",
                "stock_name": "洛阳钼业",
                "industry": "有色金属",
                "quant_status": "HARD_REJECT",
                "quant_rank": 2115,
                "quant_score": 37.2,
                "hard_reject_blockers": "price_too_high",
            },
        ]

        rows = merge_sources(
            all_a,
            [],
            global_limit=1,
            relaxed_reserve=0,
            curated_codes={"603993"},
        )
        by_code = {row["code"]: row for row in rows}
        recalled = by_code["603993"]

        self.assertEqual(recalled["valuation_source_channel"], "CURATED_RESEARCH_POOL")
        self.assertTrue(recalled["curated_research_recall"])
        self.assertEqual(recalled["hard_reject_blockers"], "price_too_high")
        self.assertFalse(recalled["formal_signal_eligible"])
        self.assertFalse(recalled["automatic_promotion_allowed"])
        self.assertTrue(recalled["no_auto_trade"])

    def test_invalidated_candidate_overrides_static_curated_recall(self):
        all_a = [
            {
                "code": "603658",
                "industry": "医疗器械",
                "quant_status": "HARD_REJECT",
                "quant_rank": 999,
                "quant_score": 40,
                "hard_reject_blockers": "price_too_high",
            }
        ]

        rows = merge_sources(
            all_a,
            [],
            global_limit=0,
            relaxed_reserve=0,
            curated_codes={"603658"},
            excluded_codes={"603658"},
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
