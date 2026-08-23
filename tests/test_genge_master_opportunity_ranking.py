from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.master_opportunity_ranking import (
    actionable_long_term_rows,
    build_master_rows,
    enrich_industry_rows,
)


class MasterOpportunityRankingTest(unittest.TestCase):
    def test_existing_valuation_rank_is_preserved_before_industry_only_names(self):
        industry = [
            {
                "code": "600001",
                "stock_name": "估值股",
                "industry": "行业A",
                "industry_research_rank": "1",
                "industry_candidate_state": "RESEARCH_CANDIDATE",
                "quant_score": "80",
            },
            {
                "code": "600002",
                "stock_name": "行业股",
                "industry": "行业B",
                "industry_research_rank": "1",
                "industry_candidate_state": "RESEARCH_CANDIDATE",
                "quant_score": "95",
            },
        ]
        valuation = [
            {
                "code": "600001",
                "stock_name": "估值股",
                "valuation_research_rank": "1",
                "quant_score": "80",
                "valuation_diagnostic_status": "OK",
            }
        ]

        rows = build_master_rows(industry, valuation, [])

        self.assertEqual([row["code"] for row in rows], ["600001", "600002"])
        self.assertEqual([row["master_research_rank"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["master_research_bucket"], "VALUATION_RESEARCHED")
        self.assertEqual(rows[1]["master_research_bucket"], "INDUSTRY_RESEARCH_ONLY")
        self.assertTrue(all(row["no_auto_trade"] for row in rows))

    def test_formal_decision_is_overlay_not_new_research_score(self):
        industry = [
            {
                "code": "603369",
                "stock_name": "今世缘",
                "industry": "食品饮料",
                "industry_research_rank": "1",
                "industry_candidate_state": "RESEARCH_CANDIDATE",
                "quant_score": "82",
            },
            {
                "code": "688687",
                "stock_name": "凯因科技",
                "industry": "医药",
                "industry_research_rank": "1",
                "industry_candidate_state": "RESEARCH_CANDIDATE",
                "quant_score": "81",
            },
        ]
        valuation = [
            {"code": "603369", "valuation_research_rank": "1", "quant_score": "82"},
            {"code": "688687", "valuation_research_rank": "2", "quant_score": "81"},
        ]
        formal = [
            {
                "code": "603369",
                "stock_name": "今世缘",
                "long_term_classification": "LONG_TERM_BUY_READY",
                "long_term_formal_buy_eligible": "True",
                "real_reward_risk_ratio": "7.05",
            },
            {
                "code": "688687",
                "stock_name": "凯因科技",
                "long_term_classification": "LONG_TERM_REVIEW_BLOCKED",
                "long_term_formal_buy_eligible": "False",
                "long_term_blockers": "valuation_expectation_too_high",
                "real_reward_risk_ratio": "3.25",
            },
        ]

        rows = build_master_rows(industry, valuation, formal)
        by_code = {row["code"]: row for row in rows}

        self.assertEqual(by_code["603369"]["master_research_rank"], 1)
        self.assertEqual(by_code["603369"]["master_research_bucket"], "LONG_TERM_BUY_READY")
        self.assertEqual(by_code["688687"]["master_research_rank"], 2)
        self.assertEqual(by_code["688687"]["master_research_bucket"], "LONG_TERM_REVIEW_BLOCKED")

    def test_blocked_long_term_name_never_enters_actionable_output(self):
        formal = [
            {
                "code": "603369",
                "stock_name": "今世缘",
                "long_term_classification": "LONG_TERM_BUY_READY",
                "long_term_formal_buy_eligible": "True",
                "real_reward_risk_ratio": "7.05",
            },
            {
                "code": "688687",
                "stock_name": "凯因科技",
                "long_term_classification": "LONG_TERM_REVIEW_BLOCKED",
                "long_term_formal_buy_eligible": "False",
                "long_term_blockers": "earnings_quality_below_minimum;valuation_expectation_too_high",
            },
        ]

        rows = actionable_long_term_rows(formal)

        self.assertEqual([row["code"] for row in rows], ["603369"])
        self.assertTrue(rows[0]["no_auto_trade"])
        self.assertFalse(rows[0]["formal_signal_eligible"])
        self.assertFalse(rows[0]["automatic_promotion_allowed"])

    def test_legacy_try_position_is_visible_but_never_actionable(self):
        formal = [
            {
                "code": "600001",
                "stock_name": "旧试仓对象",
                "long_term_classification": "LONG_TERM_TRY_POSITION",
                "long_term_formal_buy_eligible": "True",
                "real_reward_risk_ratio": "3.0",
            }
        ]

        self.assertEqual(actionable_long_term_rows(formal), [])

    def test_every_industry_map_preserves_all_rows_and_adds_decision_overlay(self):
        industry = [
            {
                "code": "600001",
                "stock_name": "甲",
                "industry": "行业A",
                "industry_research_rank": "1",
                "industry_candidate_state": "RESEARCH_CANDIDATE",
            },
            {
                "code": "600002",
                "stock_name": "乙",
                "industry": "行业B",
                "industry_research_rank": "1",
                "industry_candidate_state": "BLOCKED_RESEARCH_ONLY",
            },
        ]
        valuation = [
            {
                "code": "600001",
                "valuation_research_rank": "4",
                "valuation_diagnostic_status": "OK",
                "financial_review_status": "OK",
            }
        ]
        formal = [
            {
                "code": "600001",
                "long_term_classification": "LONG_TERM_TRY_POSITION",
                "long_term_formal_buy_eligible": "True",
            }
        ]

        rows = enrich_industry_rows(industry, valuation, formal)

        self.assertEqual(len(rows), 2)
        self.assertEqual({row["industry"] for row in rows}, {"行业A", "行业B"})
        by_code = {row["code"]: row for row in rows}
        self.assertEqual(by_code["600001"]["long_term_classification"], "LONG_TERM_TRY_POSITION")
        self.assertEqual(
            by_code["600001"]["master_research_bucket"],
            "LONG_TERM_REVIEW_BLOCKED_LEGACY_TRY_POSITION",
        )
        self.assertEqual(by_code["600002"]["master_research_bucket"], "BLOCKED_INDUSTRY_RESEARCH_ONLY")


if __name__ == "__main__":
    unittest.main()
