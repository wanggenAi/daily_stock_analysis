from __future__ import annotations

import unittest

from src.strategies.genge_opportunity_discovery.long_term_second_pass import (
    passes_all_non_exit_hard_gates,
    select_long_term_second_pass,
)


class LongTermSecondPassTest(unittest.TestCase):
    def test_exit_profile_only_candidate_is_preserved(self):
        row = {
            "code": "603369",
            "stock_name": "今世缘",
            "strict_gate_failed": "exit_profile_passed;exit_profile_sample_count;exit_profile_confidence",
            "hard_blockers": "",
            "actionability_score": "76.9",
            "quant_score": "82.9",
        }
        self.assertTrue(passes_all_non_exit_hard_gates(row))
        result = select_long_term_second_pass([row])
        self.assertEqual([r["code"] for r in result], ["603369"])
        self.assertFalse(result[0]["formal_signal_eligible"])
        self.assertTrue(result[0]["requires_valuation_review"])

    def test_non_exit_gate_prevents_second_pass(self):
        row = {
            "code": "600812",
            "strict_gate_failed": "financial_passed;exit_profile_passed",
            "hard_blockers": "",
        }
        self.assertFalse(passes_all_non_exit_hard_gates(row))
        self.assertEqual(select_long_term_second_pass([row]), [])

    def test_hard_blocker_is_never_bypassed(self):
        row = {
            "code": "000001",
            "strict_gate_failed": "exit_profile_passed",
            "hard_blockers": "price_too_high",
        }
        self.assertFalse(passes_all_non_exit_hard_gates(row))


if __name__ == "__main__":
    unittest.main()
