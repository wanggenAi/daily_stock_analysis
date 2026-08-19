from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.strategies.genge_opportunity_discovery.hard_logic_price_map import (
    build_price_expectation_row,
    build_price_expectation_rows,
    earnings_stage_assessment,
    hard_logic_assessment,
    load_artifact_company_rows,
    write_price_map,
)


class HardLogicPriceMapTest(unittest.TestCase):
    def _base_row(self, **overrides):
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
        }
        row.update(overrides)
        return row

    def test_price_map_never_collapses_multiple_hard_logic_companies_to_top_one(self):
        rows = build_price_expectation_rows(
            [
                self._base_row(code="600001", stock_name="甲"),
                self._base_row(code="600002", stock_name="乙", required_profit_growth_pct="-5"),
                self._base_row(code="600003", stock_name="丙", required_profit_growth_pct="8"),
            ]
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual({row["code"] for row in rows}, {"600001", "600002", "600003"})
        self.assertEqual(sorted(row["price_map_rank"] for row in rows), [1, 2, 3])
        self.assertTrue(all(row["no_auto_trade"] for row in rows))

    def test_technical_exit_profile_failure_is_visible_but_not_company_veto(self):
        state, reasons, structural, context = hard_logic_assessment(
            self._base_row(strict_gate_failed="exit_profile_sample_insufficient;ma20_not_ready")
        )

        self.assertEqual(state, "PASS")
        self.assertFalse(structural)
        self.assertEqual(set(context), {"exit_profile_sample_insufficient", "ma20_not_ready"})
        self.assertIn("execution_context_ignored_for_company_quality", reasons)

    def test_market_entry_rr_and_execution_failures_are_not_company_vetoes(self):
        state, reasons, structural, context = hard_logic_assessment(
            self._base_row(
                strict_gate_failed=(
                    "market_regime_not_ready;entry_not_ready;reward_risk_below_min;"
                    "position_size_not_ready;execution_price_unavailable"
                )
            )
        )

        self.assertEqual(state, "PASS")
        self.assertFalse(structural)
        self.assertEqual(
            set(context),
            {
                "market_regime_not_ready",
                "entry_not_ready",
                "reward_risk_below_min",
                "position_size_not_ready",
                "execution_price_unavailable",
            },
        )
        self.assertIn("execution_context_ignored_for_company_quality", reasons)

    def test_even_old_hard_blocker_columns_downgrade_known_execution_tokens(self):
        state, _, structural, context = hard_logic_assessment(
            self._base_row(hard_blockers="exit_profile_sample_insufficient;reward_risk_below_min")
        )

        self.assertEqual(state, "PASS")
        self.assertFalse(structural)
        self.assertEqual(set(context), {"exit_profile_sample_insufficient", "reward_risk_below_min"})

    def test_structural_hard_risk_blocks_company_before_price_decision(self):
        row = build_price_expectation_row(self._base_row(hard_blockers="financial_integrity_risk"))

        self.assertEqual(row["hard_logic_state"], "BLOCKED")
        self.assertEqual(row["price_decision"], "HARD_LOGIC_BLOCKED")
        self.assertIn("financial_integrity_risk", row["structural_blockers"])

    def test_industry_research_candidate_needs_valuation_and_earnings_confirmation(self):
        missing_quality = build_price_expectation_row(self._base_row(earnings_quality_score=""))
        weak_quality = build_price_expectation_row(self._base_row(earnings_quality_score="40"))

        self.assertEqual(missing_quality["hard_logic_state"], "REVIEW")
        self.assertEqual(missing_quality["price_decision"], "HARD_LOGIC_REVIEW")
        self.assertEqual(weak_quality["hard_logic_state"], "REVIEW")

    def test_no_growth_or_contraction_requirement_is_directly_buyable_in_reverse_fallback(self):
        deep = build_price_expectation_row(self._base_row(required_profit_growth_pct="-20"))
        buyable = build_price_expectation_row(self._base_row(required_profit_growth_pct="0"))

        self.assertEqual(deep["valuation_framework"], "REFERENCE_ONLY_REVERSE_PE")
        self.assertEqual(deep["price_decision"], "BUY_DEEP_VALUE")
        self.assertEqual(buyable["price_decision"], "BUYABLE")
        self.assertTrue(deep["historical_pe_is_reference_only"])

    def test_positive_required_growth_without_business_support_is_not_guessed(self):
        row = build_price_expectation_row(self._base_row(required_profit_growth_pct="12"))

        self.assertEqual(row["price_decision"], "NEED_HARD_LOGIC_GROWTH_SUPPORT")
        self.assertIsNone(row["supported_profit_growth_base_pct"])
        self.assertIsNone(row["supported_fair_price_base"])

    def test_supported_business_growth_is_compared_directly_with_market_expectation(self):
        deep = build_price_expectation_row(
            self._base_row(
                required_profit_growth_pct="10",
                hard_logic_supported_profit_growth_base_pct="40",
            )
        )
        attractive = build_price_expectation_row(
            self._base_row(
                required_profit_growth_pct="10",
                hard_logic_supported_profit_growth_base_pct="25",
            )
        )
        expensive = build_price_expectation_row(
            self._base_row(
                required_profit_growth_pct="20",
                hard_logic_supported_profit_growth_base_pct="15",
            )
        )

        self.assertEqual(deep["price_decision"], "BUY_DEEP_VALUE")
        self.assertAlmostEqual(deep["expectation_headroom_pct"], 30.0)
        self.assertEqual(attractive["price_decision"], "BUYABLE_WITH_SUPPORTED_GROWTH")
        self.assertAlmostEqual(attractive["expectation_headroom_pct"], 15.0)
        self.assertEqual(expensive["price_decision"], "EXPECTATIONS_HIGH_WAIT")
        self.assertAlmostEqual(expensive["expectation_headroom_pct"], -5.0)

    def test_price_expectation_map_translates_growth_requirements_back_to_prices(self):
        row = build_price_expectation_row(
            self._base_row(current_price="40", required_profit_growth_pct="-20")
        )

        self.assertAlmostEqual(row["price_if_market_requires_minus20pct_growth"], 40.0)
        self.assertAlmostEqual(row["price_if_market_requires_zero_growth"], 50.0)
        self.assertAlmostEqual(row["historical_reference_price"], 50.0)
        self.assertAlmostEqual(row["price_if_market_requires_plus20pct_growth"], 60.0)
        self.assertAlmostEqual(row["deep_value_price_ceiling"], 40.0)
        self.assertAlmostEqual(row["buyable_price_ceiling"], 50.0)

    def test_supported_growth_creates_direct_buyable_and_deep_value_ceilings_in_reverse_fallback(self):
        row = build_price_expectation_row(
            self._base_row(
                current_price="40",
                required_profit_growth_pct="-20",
                hard_logic_supported_profit_growth_base_pct="25",
            )
        )

        self.assertAlmostEqual(row["buyable_price_ceiling"], 55.0)
        self.assertAlmostEqual(row["deep_value_price_ceiling"], 47.5)

    def test_forward_scenario_fair_value_overrides_historical_pe_as_buy_decision(self):
        row = build_price_expectation_row(
            self._base_row(
                code="603369",
                stock_name="今世缘",
                current_price="28.92",
                current_pe="13.9",
                historical_median_pe_reference="21",
                forward_eps_bear="2.00",
                forward_eps_base="2.08",
                forward_eps_bull="2.15",
                reasonable_pe_bear="12",
                reasonable_pe_base="15",
                reasonable_pe_bull="18",
                earnings_stage="EARLY_RECOVERY",
            )
        )

        self.assertEqual(row["valuation_framework"], "FORWARD_SCENARIO")
        self.assertEqual(row["earnings_stage"], "EARLY_RECOVERY")
        self.assertTrue(row["historical_pe_is_reference_only"])
        self.assertAlmostEqual(row["scenario_fair_price_bear"], 24.0)
        self.assertAlmostEqual(row["scenario_fair_price_base"], 31.2)
        self.assertAlmostEqual(row["scenario_fair_price_bull"], 38.7)
        self.assertAlmostEqual(row["entry_price_ceiling"], 26.52)
        self.assertAlmostEqual(row["ideal_price_ceiling"], 23.4)
        self.assertEqual(row["price_zone"], "HOLD_FAIR_ZONE")
        self.assertEqual(row["price_decision"], "HOLD_FAIR_VALUE")

    def test_forward_scenario_uses_margin_of_safety_for_buy_and_deep_value(self):
        buyable = build_price_expectation_row(
            self._base_row(
                current_price="26",
                scenario_fair_price_base="31.2",
                scenario_fair_price_bull="38.7",
            )
        )
        deep = build_price_expectation_row(
            self._base_row(
                current_price="23",
                scenario_fair_price_base="31.2",
                scenario_fair_price_bull="38.7",
            )
        )

        self.assertEqual(buyable["price_decision"], "BUYABLE")
        self.assertEqual(buyable["price_zone"], "BUY_ZONE")
        self.assertEqual(deep["price_decision"], "BUY_DEEP_VALUE")
        self.assertEqual(deep["price_zone"], "DEEP_VALUE_ZONE")

    def test_forward_scenario_marks_price_above_bull_as_overvalued_wait(self):
        row = build_price_expectation_row(
            self._base_row(
                current_price="40",
                scenario_fair_price_base="31.2",
                scenario_fair_price_bull="38.7",
            )
        )

        self.assertEqual(row["price_decision"], "OVERVALUED_WAIT")
        self.assertEqual(row["price_zone"], "OVERVALUED_ZONE")

    def test_forward_scenario_never_invents_missing_reasonable_pe(self):
        row = build_price_expectation_row(
            self._base_row(
                current_price="28.92",
                forward_eps_base="2.08",
                reasonable_pe_base="",
            )
        )

        self.assertEqual(row["scenario_valuation_status"], "FORWARD_BASE_VALUE_INPUTS_REQUIRED")
        self.assertEqual(row["valuation_framework"], "REFERENCE_ONLY_REVERSE_PE")
        self.assertIsNone(row["scenario_fair_price_base"])

    def test_direct_specialized_fair_price_does_not_require_pe(self):
        row = build_price_expectation_row(
            self._base_row(
                current_price="80",
                scenario_fair_price_base="100",
                scenario_fair_price_bull="120",
                current_pe="",
                historical_median_pe_reference="",
                required_profit_growth_pct="",
            )
        )

        self.assertEqual(row["valuation_framework"], "FORWARD_SCENARIO")
        self.assertEqual(row["price_decision"], "BUYABLE")
        self.assertAlmostEqual(row["entry_price_ceiling"], 85.0)

    def test_negative_eps_or_multiple_cannot_create_forward_fair_value(self):
        row = build_price_expectation_row(
            self._base_row(
                forward_eps_base="-2.08",
                reasonable_pe_base="15",
            )
        )

        self.assertIsNone(row["scenario_fair_price_base"])
        self.assertEqual(row["valuation_framework"], "REFERENCE_ONLY_REVERSE_PE")

    def test_earnings_stage_can_be_inferred_from_quarterly_inflection(self):
        stage, basis = earnings_stage_assessment(
            self._base_row(latest_quarter_profit_yoy_pct="19.17", previous_quarter_profit_yoy_pct="-15.76")
        )

        self.assertEqual(stage, "EARLY_RECOVERY")
        self.assertEqual(basis, "LATEST_PROFIT_YOY_TURNED_POSITIVE")

    def test_artifact_merge_restores_raw_price_but_only_keeps_research_union(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "reports" / "final_valuation_source"
            industry = root / "reports" / "industry_coverage"
            valuation = root / "reports" / "valuation_research_queue" / "20260819"
            scenario = root / "reports" / "forward_scenario_valuation"
            raw.mkdir(parents=True)
            industry.mkdir(parents=True)
            valuation.mkdir(parents=True)
            scenario.mkdir(parents=True)

            self._write_csv(
                raw / "all_a_quant_screen.csv",
                [
                    {"code": "600001", "stock_name": "甲", "current_price": "40", "quant_score": "90"},
                    {"code": "600999", "stock_name": "仅原始市场", "current_price": "9", "quant_score": "10"},
                ],
            )
            self._write_csv(
                industry / "industry_top_candidates.csv",
                [
                    {
                        "code": "600001",
                        "stock_name": "甲",
                        "industry": "行业A",
                        "industry_candidate_state": "RESEARCH_CANDIDATE",
                    }
                ],
            )
            self._write_csv(
                valuation / "valuation_research_routed.csv",
                [
                    {
                        "code": "600001",
                        "current_pe": "16",
                        "historical_median_pe_reference": "20",
                        "required_profit_growth_pct": "-20",
                        "valuation_diagnostic_status": "OK",
                    }
                ],
            )
            self._write_csv(
                scenario / "forward_scenario_valuation.csv",
                [
                    {
                        "code": "600001",
                        "forward_eps_base": "3",
                        "reasonable_pe_base": "15",
                    },
                    {
                        "code": "600777",
                        "forward_eps_base": "1",
                        "reasonable_pe_base": "10",
                    },
                ],
            )

            rows = load_artifact_company_rows(root)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["code"], "600001")
            self.assertEqual(rows[0]["current_price"], "40")
            self.assertEqual(rows[0]["industry"], "行业A")
            self.assertEqual(rows[0]["required_profit_growth_pct"], "-20")
            self.assertEqual(rows[0]["forward_eps_base"], "3")
            self.assertEqual(rows[0]["reasonable_pe_base"], "15")

    def test_written_summary_explicitly_disables_global_top_one_and_auto_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifact"
            out = Path(tmp) / "out"
            industry = root / "reports" / "industry_coverage"
            valuation = root / "reports" / "valuation_research_queue" / "20260819"
            raw = root / "reports" / "final_valuation_source"
            industry.mkdir(parents=True)
            valuation.mkdir(parents=True)
            raw.mkdir(parents=True)

            self._write_csv(
                raw / "all_a_quant_screen.csv",
                [{"code": "600001", "stock_name": "甲", "current_price": "40"}],
            )
            self._write_csv(
                industry / "industry_top_candidates.csv",
                [{
                    "code": "600001",
                    "industry": "A",
                    "industry_candidate_state": "RESEARCH_CANDIDATE",
                }],
            )
            self._write_csv(
                valuation / "valuation_research_routed.csv",
                [{
                    "code": "600001",
                    "current_pe": "16",
                    "historical_median_pe_reference": "20",
                    "required_profit_growth_pct": "-20",
                    "valuation_diagnostic_status": "OK",
                    "earnings_quality_score": "80",
                }],
            )

            write_price_map(root, out)
            summary = json.loads((out / "hard_logic_price_map_summary.json").read_text(encoding="utf-8"))

            self.assertFalse(summary["global_top1_required"])
            self.assertTrue(summary["technical_context_is_non_veto"])
            self.assertTrue(summary["historical_pe_is_reference_only"])
            self.assertTrue(summary["no_auto_trade"])
            self.assertFalse(summary["formal_signal_eligible"])

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
