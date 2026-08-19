from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.strategies.genge_opportunity_discovery.long_term_formal_buy import (
    PortfolioRiskState,
    evaluate_long_term_candidate,
    load_portfolio_risk_state,
)


def _second_pass() -> dict[str, object]:
    return {
        "code": "603198",
        "stock_name": "example",
        "industry": "liquor",
        "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
        "real_reward_risk_ratio": 3.0,
    }


def _plan() -> dict[str, object]:
    return {
        "code": "603198",
        "stock_name": "example",
        "industry": "liquor",
        "market_regime_status": "GREEN",
        "event_risk_level": "LOW",
        "hard_blockers": "",
        "real_reward_risk_ratio": 3.0,
        "preferred_plan": "pullback",
        "raw_latest_close": 10.0,
        "pullback_entry_low": 9.5,
        "pullback_entry_high": 10.5,
        "pullback_stop_price": 9.0,
        "pullback_target_1": 12.0,
        "pullback_target_2": 14.0,
        "pullback_status": "READY",
    }


def _valuation(required_growth: float = 0.10) -> dict[str, object]:
    return {
        "code": "603198",
        "stock_name": "example",
        "industry": "liquor",
        "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
        "valuation_diagnostic_status": "OK",
        "financial_review_status": "OK",
        "normalized_core_operating_profit": 100.0,
        "earnings_quality_score": 80.0,
        "earnings_quality_confidence": "HIGH",
        "valuation_routing_confidence": 0.80,
        "required_profit_growth_vs_reference": required_growth,
    }


class LongTermDrawdownIntegrationTest(unittest.TestCase):
    def test_ready_candidate_gets_risk_budgeted_position(self):
        row = evaluate_long_term_candidate(_second_pass(), _plan(), _valuation())

        self.assertEqual(row["long_term_classification"], "LONG_TERM_BUY_READY")
        self.assertTrue(row["long_term_formal_buy_eligible"])
        self.assertAlmostEqual(row["stop_distance_pct"], 10.0, places=6)
        self.assertAlmostEqual(row["recommended_position_pct"], 12.5, places=4)

    def test_twelve_percent_portfolio_drawdown_halves_new_risk(self):
        row = evaluate_long_term_candidate(
            _second_pass(),
            _plan(),
            _valuation(),
            portfolio_state=PortfolioRiskState(portfolio_drawdown_pct=12.0),
        )

        self.assertEqual(row["long_term_classification"], "LONG_TERM_BUY_READY")
        self.assertAlmostEqual(row["drawdown_exposure_multiplier"], 0.5, places=6)
        self.assertAlmostEqual(row["recommended_position_pct"], 6.25, places=4)

    def test_try_position_uses_half_the_ready_risk_budget(self):
        row = evaluate_long_term_candidate(
            _second_pass(),
            _plan(),
            _valuation(required_growth=0.20),
        )

        self.assertEqual(row["long_term_classification"], "LONG_TERM_TRY_POSITION")
        self.assertAlmostEqual(row["recommended_position_pct"], 6.25, places=4)

    def test_twenty_percent_portfolio_drawdown_freezes_new_buy(self):
        row = evaluate_long_term_candidate(
            _second_pass(),
            _plan(),
            _valuation(),
            portfolio_state=PortfolioRiskState(portfolio_drawdown_pct=20.0),
        )

        self.assertEqual(row["long_term_classification"], "LONG_TERM_REVIEW_BLOCKED")
        self.assertFalse(row["long_term_formal_buy_eligible"])
        self.assertEqual(row["recommended_position_pct"], 0.0)
        self.assertIn("portfolio_drawdown_hard_stop", row["long_term_blockers"])

    def test_name_and_industry_caps_can_block_additional_risk(self):
        name_capped = evaluate_long_term_candidate(
            _second_pass(),
            _plan(),
            _valuation(),
            portfolio_state=PortfolioRiskState(name_allocations={"603198": 0.20}),
        )
        self.assertEqual(name_capped["recommended_position_pct"], 0.0)
        self.assertIn("risk_budget_no_capacity", name_capped["long_term_blockers"])

        industry_capped = evaluate_long_term_candidate(
            _second_pass(),
            _plan(),
            _valuation(),
            portfolio_state=PortfolioRiskState(industry_allocations={"liquor": 0.35}),
        )
        self.assertEqual(industry_capped["recommended_position_pct"], 0.0)
        self.assertIn("risk_budget_no_capacity", industry_capped["long_term_blockers"])

    def test_portfolio_state_loader_accepts_percent_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portfolio_state.json"
            path.write_text(
                json.dumps(
                    {
                        "portfolio_drawdown_pct": 8.0,
                        "name_allocations": {"603198": 10},
                        "industry_allocations": {"liquor": 22},
                    }
                ),
                encoding="utf-8",
            )
            state = load_portfolio_risk_state(path)

        self.assertAlmostEqual(state.name_fraction("603198"), 0.10, places=6)
        self.assertAlmostEqual(state.industry_fraction("liquor"), 0.22, places=6)
        self.assertAlmostEqual(state.portfolio_drawdown_pct, 8.0, places=6)


if __name__ == "__main__":
    unittest.main()
