from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.strategies.genge_opportunity_discovery.hard_logic_research_runner import (
    group_industry_seeds,
    normalize_research_payload,
    run_research,
)
from src.strategies.genge_opportunity_discovery.hard_logic_valuation_merge import (
    merge_hard_logic_into_valuation,
)


class HardLogicResearchRunnerTest(unittest.TestCase):
    def _payload(self, code="600001", name="甲公司", **overrides):
        payload = {
            "research_state": "PASS",
            "selected_code": code,
            "selected_name": name,
            "hard_logic_structural_driver": "行业未来五年渗透率持续提升并带来结构性增量需求",
            "hard_logic_supply_constraint": "核心产能与客户认证周期较长，有效供给扩张受约束",
            "hard_logic_company_edge": "公司拥有核心工艺与头部客户认证，规模成本优势难以快速复制",
            "hard_logic_profit_transmission": "渗透率提升带动销量和产品价值量上升，规模效应改善毛利率并传导到利润",
            "hard_logic_invalidation": "若渗透率连续低于预期或核心客户份额显著下降则逻辑失效",
            "hard_logic_duration_years": 5,
            "hard_logic_persistence": "结构性需求和认证壁垒预计持续五年以上",
            "hard_logic_evidence_sources": [
                {"title": "公司年度报告", "url": "source://annual-report"},
                {"title": "行业协会数据", "url": "source://industry"},
            ],
            "research_summary": "存在可审计的长期产业驱动和公司卡位。",
        }
        payload.update(overrides)
        return payload

    def test_topn_is_seed_only_and_industries_are_grouped(self):
        grouped = group_industry_seeds(
            [
                {"industry": "行业A", "code": "600002", "industry_rank": "2", "stock_name": "乙"},
                {"industry": "行业A", "code": "600001", "industry_rank": "1", "stock_name": "甲"},
                {"industry": "行业B", "code": "000001", "industry_rank": "1", "stock_name": "丙"},
            ],
            per_industry_limit=1,
        )

        self.assertEqual(list(grouped["行业A"])[0]["code"], "600001")
        self.assertEqual(list(grouped["行业B"])[0]["code"], "000001")

    def test_valid_seed_company_passes_deterministic_gate(self):
        row = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "甲公司"}],
            self._payload(),
            raw_universe_codes={"600001"},
        )

        self.assertEqual(row["research_state"], "PASS")
        self.assertEqual(row["hard_logic_state"], "PASS")
        self.assertEqual(row["selection_origin"], "SEED")
        self.assertGreaterEqual(row["hard_logic_score"], 90)

    def test_model_pass_missing_company_edge_is_downgraded(self):
        row = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "甲公司"}],
            self._payload(hard_logic_company_edge=""),
            raw_universe_codes={"600001"},
        )

        self.assertEqual(row["research_state"], "REVIEW")
        self.assertEqual(row["hard_logic_state"], "REVIEW")
        self.assertIn("company_edge", row["hard_logic_missing_evidence"])
        self.assertIn("deterministic_hard_logic_gate_rejected_model_pass", row["research_error"])

    def test_external_nomination_requires_membership_in_raw_all_a(self):
        accepted = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "甲"}],
            self._payload(code="600999", name="外部提名"),
            raw_universe_codes={"600001", "600999"},
        )
        rejected = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "甲"}],
            self._payload(code="600888", name="不存在"),
            raw_universe_codes={"600001", "600999"},
        )

        self.assertEqual(accepted["hard_logic_state"], "PASS")
        self.assertEqual(accepted["selection_origin"], "EXTERNAL_A_SHARE_NOMINATION")
        self.assertEqual(rejected["research_state"], "REVIEW")
        self.assertEqual(rejected["selected_code"], "")
        self.assertIn("selected_code_not_found_in_all_a_universe", rejected["research_error"])

    def test_no_pass_is_preserved_instead_of_forcing_a_stock(self):
        row = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "甲"}],
            self._payload(
                research_state="NO_PASS",
                selected_code="",
                selected_name="",
                hard_logic_structural_driver="",
                hard_logic_company_edge="",
                hard_logic_profit_transmission="",
            ),
            raw_universe_codes={"600001"},
        )

        self.assertEqual(row["research_state"], "NO_PASS")
        self.assertEqual(row["selected_code"], "")
        self.assertEqual(row["hard_logic_state"], "REVIEW")

    def test_run_research_writes_one_result_per_industry_with_fake_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "industry_top_candidates.csv"
            raw = root / "all_a_quant_screen.csv"
            out = root / "out"
            self._write_csv(
                candidates,
                [
                    {"industry": "行业A", "code": "600001", "stock_name": "甲", "industry_rank": "1"},
                    {"industry": "行业B", "code": "000001", "stock_name": "乙", "industry_rank": "1"},
                ],
            )
            self._write_csv(
                raw,
                [
                    {"industry": "行业A", "code": "600001", "stock_name": "甲"},
                    {"industry": "行业B", "code": "000001", "stock_name": "乙"},
                ],
            )

            def fake_call(industry, seeds):
                return json.dumps(
                    self._payload(
                        code=seeds[0]["code"],
                        name=seeds[0]["stock_name"],
                    ),
                    ensure_ascii=False,
                )

            rows = run_research(
                industry_candidates_csv=candidates,
                all_a_universe_csv=raw,
                output_dir=out,
                research_call=fake_call,
                max_workers=2,
            )

            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["hard_logic_state"] == "PASS" for row in rows))
            summary = json.loads((out / "hard_logic_research_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["industry_count"], 2)
            self.assertEqual(summary["hard_logic_pass_count"], 2)
            self.assertFalse(summary["topn_seed_is_answer"])
            self.assertFalse(summary["all_industries_force_stock"])

    def test_hard_logic_pass_is_forced_into_valuation_even_outside_seed_source(self):
        research = normalize_research_payload(
            "行业A",
            [{"code": "600001", "stock_name": "种子"}],
            self._payload(code="600999", name="真正硬逻辑公司"),
            raw_universe_codes={"600001", "600999"},
        )
        merged, stats = merge_hard_logic_into_valuation(
            valuation_rows=[{"code": "600001", "valuation_source_channel": "INDUSTRY_CHAMPION"}],
            hard_logic_rows=[research],
            raw_all_a_rows=[
                {"code": "600001", "stock_name": "种子"},
                {"code": "600999", "stock_name": "真正硬逻辑公司", "industry": "行业A"},
            ],
        )

        by_code = {row["code"]: row for row in merged}
        self.assertIn("600999", by_code)
        self.assertEqual(by_code["600999"]["hard_logic_state"], "PASS")
        self.assertEqual(by_code["600999"]["valuation_source_channel"], "HARD_LOGIC_PASS")
        self.assertEqual(stats["external_nomination_routed_count"], 1)

    def test_external_nomination_not_in_raw_all_a_cannot_enter_valuation(self):
        fake_research = {
            "industry": "行业A",
            "research_state": "PASS",
            "hard_logic_state": "PASS",
            "selected_code": "600999",
            "selected_name": "不存在",
            "selection_origin": "EXTERNAL_A_SHARE_NOMINATION",
        }
        merged, stats = merge_hard_logic_into_valuation(
            valuation_rows=[{"code": "600001"}],
            hard_logic_rows=[fake_research],
            raw_all_a_rows=[{"code": "600001"}],
        )

        self.assertEqual({row["code"] for row in merged}, {"600001"})
        self.assertEqual(stats["missing_from_all_a_count"], 1)

    @staticmethod
    def _write_csv(path: Path, rows):
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
