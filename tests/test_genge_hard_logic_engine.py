from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.hard_logic_engine import (
    evaluate_hard_logic,
    hard_logic_assessment,
)
from src.strategies.genge_opportunity_discovery.strict_hard_logic_price_map import (
    build_strict_price_expectation_rows,
)


class HardLogicEngineTest(unittest.TestCase):
    def _financial_candidate(self, **overrides):
        row = {
            "code": "600001",
            "stock_name": "测试公司",
            "industry": "测试行业",
            "industry_candidate_state": "RESEARCH_CANDIDATE",
            "valuation_diagnostic_status": "OK",
            "current_price": "40",
            "current_pe": "16",
            "historical_median_pe_reference": "20",
            "required_profit_growth_pct": "-20",
            "normalized_core_operating_profit": "100",
            "earnings_quality_score": "80",
            "quant_score": "95",
            "master_rank": "1",
        }
        row.update(overrides)
        return row

    def _hard_logic_candidate(self, **overrides):
        row = self._financial_candidate(
            hard_logic_structural_driver=(
                "未来多年行业渗透率提升和刚性需求扩张，形成可持续增量需求"
            ),
            hard_logic_supply_constraint=(
                "核心产能扩张周期长，客户认证与准入限制使有效供给释放受约束"
            ),
            hard_logic_company_edge=(
                "公司拥有核心工艺、头部客户定点和规模成本优势，竞争者短期难复制"
            ),
            hard_logic_profit_transmission=(
                "行业需求增长带动出货量与单车价值量提升，规模效应进一步改善毛利率并传导至净利润"
            ),
            hard_logic_invalidation=(
                "若渗透率连续低于预期、核心客户份额下降或竞争导致毛利率持续恶化则逻辑失效"
            ),
            hard_logic_duration_years="5",
            hard_logic_evidence_sources="公司公告;年度报告;行业协会数据",
        )
        row.update(overrides)
        return row

    def test_quant_valuation_and_quality_do_not_create_hard_logic(self):
        evaluation = evaluate_hard_logic(self._financial_candidate())

        self.assertEqual(evaluation.state, "REVIEW")
        self.assertIn("structural_driver", evaluation.missing_evidence)
        self.assertIn("company_edge", evaluation.missing_evidence)
        self.assertIn("profit_transmission", evaluation.missing_evidence)
        self.assertIn("valuation_or_quant_cannot_substitute_for_hard_logic", evaluation.reasons)

    def test_complete_structural_thesis_chain_passes(self):
        evaluation = evaluate_hard_logic(self._hard_logic_candidate())

        self.assertEqual(evaluation.state, "PASS")
        self.assertGreaterEqual(evaluation.score, 90)
        self.assertFalse(evaluation.missing_evidence)
        self.assertIn("hard_logic_chain_complete", evaluation.reasons)

    def test_supply_constraint_is_useful_but_not_mandatory_for_every_archetype(self):
        evaluation = evaluate_hard_logic(
            self._hard_logic_candidate(hard_logic_supply_constraint="")
        )

        self.assertEqual(evaluation.state, "PASS")
        self.assertEqual(evaluation.score, 95)

    def test_missing_company_specific_edge_forces_review(self):
        evaluation = evaluate_hard_logic(
            self._hard_logic_candidate(hard_logic_company_edge="")
        )

        self.assertEqual(evaluation.state, "REVIEW")
        self.assertIn("company_edge", evaluation.missing_evidence)

    def test_short_term_catalyst_is_not_a_durable_hard_logic(self):
        evaluation = evaluate_hard_logic(
            self._hard_logic_candidate(hard_logic_duration_years="1")
        )

        self.assertEqual(evaluation.state, "REVIEW")
        self.assertIn("durability_3y_plus", evaluation.missing_evidence)

    def test_explicit_pass_cannot_bypass_missing_evidence(self):
        evaluation = evaluate_hard_logic(
            self._financial_candidate(hard_logic_state="PASS")
        )

        self.assertEqual(evaluation.state, "REVIEW")
        self.assertIn("explicit_pass_not_trusted_without_structured_evidence", evaluation.reasons)

    def test_structural_company_risk_blocks_before_thesis_scoring(self):
        evaluation = evaluate_hard_logic(
            self._hard_logic_candidate(hard_blockers="financial_integrity_risk")
        )

        self.assertEqual(evaluation.state, "BLOCKED")
        self.assertIn("financial_integrity_risk", evaluation.structural_blockers)

    def test_technical_and_execution_context_do_not_veto_company_quality(self):
        state, reasons, structural, context = hard_logic_assessment(
            self._hard_logic_candidate(
                strict_gate_failed="ma20_not_ready;reward_risk_below_min;entry_not_ready"
            )
        )

        self.assertEqual(state, "PASS")
        self.assertFalse(structural)
        self.assertEqual(
            set(context),
            {"ma20_not_ready", "reward_risk_below_min", "entry_not_ready"},
        )
        self.assertIn("execution_context_ignored_for_company_quality", reasons)

    def test_non_pe_specialized_model_is_not_rejected_by_hard_logic_gate(self):
        evaluation = evaluate_hard_logic(
            self._hard_logic_candidate(
                valuation_diagnostic_status="PE_MODEL_NOT_APPLICABLE",
                current_pe="",
                historical_median_pe_reference="",
                scenario_fair_price_base="100",
            )
        )

        self.assertEqual(evaluation.state, "PASS")

    def test_strict_price_map_refuses_cheap_candidate_without_structural_thesis(self):
        rows = build_strict_price_expectation_rows(
            [self._financial_candidate(current_price="20", required_profit_growth_pct="-50")]
        )

        self.assertEqual(rows[0]["hard_logic_state"], "REVIEW")
        self.assertEqual(rows[0]["price_decision"], "HARD_LOGIC_REVIEW")

    def test_strict_price_map_allows_valuation_only_after_hard_logic_passes(self):
        rows = build_strict_price_expectation_rows(
            [
                self._hard_logic_candidate(
                    current_price="80",
                    scenario_fair_price_base="100",
                    scenario_fair_price_bull="120",
                )
            ]
        )

        self.assertEqual(rows[0]["hard_logic_state"], "PASS")
        self.assertEqual(rows[0]["valuation_framework"], "FORWARD_SCENARIO")
        self.assertEqual(rows[0]["price_decision"], "BUYABLE")
        self.assertAlmostEqual(rows[0]["entry_price_ceiling"], 85.0)


if __name__ == "__main__":
    unittest.main()
