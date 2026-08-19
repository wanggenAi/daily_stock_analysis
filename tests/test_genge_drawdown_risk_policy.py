from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    DEFAULT_DRAWDOWN_POLICY,
    StrategyMetrics,
    cagr_pct,
    exposure_multiplier,
    max_drawdown_pct,
    position_fraction,
    select_drawdown_optimized,
)


class DrawdownRiskPolicyTest(unittest.TestCase):
    def test_position_size_is_risk_budget_divided_by_stop_distance(self):
        size = position_fraction(stop_distance_pct=10.0)
        self.assertAlmostEqual(size, 0.125, places=6)

    def test_portfolio_drawdown_scales_new_risk(self):
        full = position_fraction(stop_distance_pct=10.0, portfolio_drawdown_pct=0.0)
        half = position_fraction(stop_distance_pct=10.0, portfolio_drawdown_pct=12.0)
        frozen = position_fraction(stop_distance_pct=10.0, portfolio_drawdown_pct=20.0)

        self.assertAlmostEqual(full, 0.125, places=6)
        self.assertAlmostEqual(half, 0.0625, places=6)
        self.assertEqual(frozen, 0.0)
        self.assertEqual(exposure_multiplier(-20.0), 0.0)

    def test_industry_and_single_name_caps_are_hard(self):
        self.assertEqual(
            position_fraction(
                stop_distance_pct=8.0,
                current_industry_fraction=DEFAULT_DRAWDOWN_POLICY.max_industry_fraction,
            ),
            0.0,
        )
        self.assertEqual(
            position_fraction(
                stop_distance_pct=8.0,
                current_name_fraction=DEFAULT_DRAWDOWN_POLICY.max_single_name_fraction,
            ),
            0.0,
        )

    def test_total_gross_cap_keeps_cash_buffer(self):
        room = position_fraction(
            stop_distance_pct=10.0,
            current_total_fraction=0.86,
        )
        self.assertAlmostEqual(room, 0.04, places=6)
        self.assertEqual(
            position_fraction(
                stop_distance_pct=10.0,
                current_total_fraction=DEFAULT_DRAWDOWN_POLICY.max_total_gross_fraction,
            ),
            0.0,
        )

    def test_total_open_risk_cap_blocks_risk_stacking(self):
        room = position_fraction(
            stop_distance_pct=10.0,
            current_open_risk_pct=5.5,
        )
        self.assertAlmostEqual(room, 0.05, places=6)
        self.assertEqual(
            position_fraction(
                stop_distance_pct=10.0,
                current_open_risk_pct=DEFAULT_DRAWDOWN_POLICY.max_total_open_risk_pct,
            ),
            0.0,
        )

    def test_optimizer_rejects_low_drawdown_if_cagr_is_destroyed(self):
        baseline = StrategyMetrics("baseline", cagr_pct=20.0, max_drawdown_pct=30.0)
        too_slow = StrategyMetrics("too_slow", cagr_pct=10.0, max_drawdown_pct=8.0)
        balanced = StrategyMetrics("balanced", cagr_pct=16.0, max_drawdown_pct=14.0)

        chosen = select_drawdown_optimized(baseline, [too_slow, balanced])

        self.assertIsNotNone(chosen)
        self.assertTrue(chosen.deployment_allowed)
        self.assertEqual(chosen.metrics.name, "balanced")
        self.assertGreaterEqual(chosen.cagr_retention_pct, 70.0)
        self.assertLessEqual(abs(chosen.metrics.max_drawdown_pct), 15.0)

    def test_no_candidate_can_sneak_through_when_all_fail(self):
        baseline = StrategyMetrics("baseline", cagr_pct=20.0, max_drawdown_pct=25.0)
        candidates = [
            StrategyMetrics("high_dd", cagr_pct=25.0, max_drawdown_pct=24.0),
            StrategyMetrics("low_return", cagr_pct=8.0, max_drawdown_pct=10.0),
        ]
        chosen = select_drawdown_optimized(baseline, candidates)

        self.assertIsNotNone(chosen)
        self.assertFalse(chosen.deployment_allowed)
        self.assertIn("no_deployable_configuration", chosen.reasons)

    def test_equity_metrics(self):
        self.assertAlmostEqual(max_drawdown_pct([100, 120, 90, 110]), 25.0, places=6)
        self.assertAlmostEqual(cagr_pct(100, 121, 2), 10.0, places=6)


if __name__ == "__main__":
    unittest.main()