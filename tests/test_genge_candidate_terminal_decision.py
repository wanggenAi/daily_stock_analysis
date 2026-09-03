import csv

from src.strategies.genge_opportunity_discovery.candidate_terminal_decision import (
    build_terminal_rows,
    terminalize_candidate,
    write_report,
)


def _master(code="000415"):
    return {
        "code": code,
        "stock_name": "Sample",
        "industry": "Consumer",
        "master_research_rank": "1",
        "valuation_research_rank": "1",
        "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
        "financial_review_status": "OK",
        "valuation_diagnostic_status": "OK",
        "v31_predictability_status": "PASS",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
        "v31_financial_safety_status": "PASS",
        "v31_earnings_authenticity_status": "PASS",
        "v31_candidate_class": "A2",
        "v31_score_long_term_demand": 9,
        "v31_score_moat_direction": 18,
        "v31_score_earnings_quality": 8,
        "v31_score_roic_incremental_roic": 8,
        "v31_score_capital_allocation": 7,
        "v31_score_growth_runway": 8,
        "v31_score_normalized_earnings_certainty": 6,
        "v31_score_expectation_gap": 7,
        "v31_score_valuation_margin_of_safety": 10,
        "v31_score_market_position": 4,
        "v31_normalized_profit": 100,
        "v31_normalized_profit_method": "five_year_normalized_profit",
        "v31_pessimistic_value": 38,
        "v31_neutral_value": 60,
        "v31_optimistic_value": 80,
        "v31_extreme_stress_value": 32,
        "v31_current_price": 40,
        "v31_market_implied_profit_cagr": 0.06,
        "v31_realistic_profit_cagr": 0.14,
        "v31_expectation_gap_pct": 0.08,
        "v31_expectation_gap_thesis": "durable expectation gap",
        "v31_risk_adjusted_3y_cagr": 0.17,
        "v31_potential_max_fundamental_loss_pct": 0.20,
        "v31_why_can_buy": "moat and valuation",
        "v31_strongest_bear_case": "growth may disappoint",
        "v31_falsification_status": "PASS",
        "v31_margin_of_safety_status": "PASS",
        "v31_cagr_attractiveness_status": "PASS",
        "v31_pessimistic_loss_status": "PASS",
        "v31_portfolio_exposure_status": "PASS",
        "v31_market_position_status": "PASS",
    }


def _formal(code="000415"):
    return {
        "code": code,
        "long_term_formal_buy_eligible": "True",
        "v31_buy_ready": "True",
    }


def _production(action, code="000415", **overrides):
    row = {
        "code": code,
        "decision_scope": "CANDIDATE",
        "production_action": action,
        "valuation_confidence": "HIGH",
        "production_model_frozen": "True",
        "formal_buy_max_price_to_neutral": "0.8",
        "reason_codes": "",
    }
    row.update(overrides)
    return row


def test_buy_only_mirrors_formal_and_frozen_production_buy():
    row = terminalize_candidate(_master(), _formal(), _production("BUY"))
    assert row["terminal_decision"] == "BUY"
    assert row["terminal_formal_buy_authorized"] is True
    assert row["decision_authority"] == "RESEARCH_TERMINAL_VIEW"
    assert row["no_auto_trade"] is True


def test_production_buy_without_formal_authority_is_rejected():
    row = terminalize_candidate(_master(), {}, _production("BUY"))
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_formal_buy_authorized"] is False


def test_high_confidence_price_only_wait_uses_frozen_080_ceiling():
    row = terminalize_candidate(
        _master(),
        _formal(),
        _production(
            "WAIT",
            reason_codes="CORE_POOL_CONFERS_NO_BUY_PRIVILEGE;BUY_MARGIN_OF_SAFETY_INSUFFICIENT;PRICE_TOO_CLOSE_TO_BASE_VALUE",
            neutral_value="10",
            current_price="9",
        ),
    )
    assert row["terminal_decision"] == "WAIT_PRICE"
    assert row["wait_price_max"] == 8.0
    assert row["formal_buy_max_price_to_neutral"] == 0.8
    assert row["wait_price_semantics"] == "frozen_formal_buy_ceiling"


def test_low_confidence_wait_is_reject_not_wait_price():
    row = terminalize_candidate(
        _master(),
        _formal(),
        _production(
            "WAIT",
            valuation_confidence="LOW",
            reason_codes="BUY_VALUATION_CONFIDENCE_NOT_HIGH",
            neutral_value="10",
            current_price="9",
        ),
    )
    assert row["terminal_decision"] == "REJECT"


def test_unknown_hard_gate_is_terminal_evidence_reject():
    master = _master()
    master.pop("v31_moat_status")
    row = terminalize_candidate(master, _formal(), _production("WAIT"))
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_reason_class"] == "EVIDENCE_INSUFFICIENT"
    assert "hard_gate_unknown:moat" in row["terminal_reason_codes"]


def test_hard_gate_failure_is_terminal_reject():
    master = _master()
    master["v31_long_term_demand_status"] = "STRUCTURAL_DECLINE"
    row = terminalize_candidate(master, _formal(), _production("WAIT"))
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_reason_class"] == "HARD_GATE_FAILED"
    assert row["terminal_retryable_next_cycle"] is False


def test_master_candidate_outside_strict_formal_review_is_not_left_in_limbo():
    row = terminalize_candidate(_master(), None, None)
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_reason_class"] == "FORMAL_REVIEW_NOT_PROVEN"
    assert row["terminal_full_review_attempted"] is True


def test_research_only_board_is_terminal_reject():
    row = terminalize_candidate(_master("688281"), None, None)
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_reason_class"] == "EXECUTION_UNIVERSE_RESEARCH_ONLY"


def test_every_master_row_gets_exactly_one_terminal_state_and_duplicates_collapse():
    master_buy = _master("000415")
    master_wait = _master("000783")
    master_wait["master_research_rank"] = "2"
    master_reject = _master("600000")
    master_reject["master_research_rank"] = "3"
    rows = build_terminal_rows(
        [master_reject, master_buy, master_wait, dict(master_wait)],
        [_formal("000415"), _formal("000783")],
        [
            _production("BUY", "000415"),
            _production(
                "WAIT",
                "000783",
                reason_codes="PRICE_TOO_CLOSE_TO_BASE_VALUE",
                neutral_value="12.5",
                current_price="11",
            ),
        ],
    )
    assert len(rows) == 3
    assert [row["terminal_decision"] for row in rows] == ["BUY", "WAIT_PRICE", "REJECT"]
    assert all(row["terminal_decision"] in {"BUY", "WAIT_PRICE", "REJECT"} for row in rows)
    assert all(row["no_auto_trade"] is True for row in rows)


def test_terminal_report_exposes_actionable_fields_in_plain_job_log_source(tmp_path):
    master_csv = tmp_path / "master.csv"
    formal_csv = tmp_path / "formal.csv"
    production_csv = tmp_path / "production.csv"
    output_dir = tmp_path / "out"

    for path, rows in (
        (master_csv, [_master()]),
        (formal_csv, [_formal()]),
        (
            production_csv,
            [
                _production(
                    "WAIT",
                    reason_codes="PRICE_TOO_CLOSE_TO_BASE_VALUE",
                    neutral_value="10",
                    current_price="9",
                )
            ],
        ),
    ):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_report(master_csv, formal_csv, production_csv, output_dir)
    text = (output_dir / "candidate_terminal_decisions.md").read_text(
        encoding="utf-8"
    )
    assert "decision=WAIT_PRICE" in text
    assert "current_price=9.0" in text
    assert "wait_price_max=8.0" in text
    assert "reason=HIGH_CONFIDENCE_PRICE_ONLY_BLOCK" in text
    assert "provider_errors=none" in text
    assert "retryable=True" in text
    assert "authority=RESEARCH_TERMINAL_VIEW" in text


def test_evidence_exhaustion_is_retryable_reject_not_unknown_pass():
    master = _master()
    master.pop("v31_moat_status")
    row = terminalize_candidate(master, _formal(), _production("WAIT"))
    assert row["terminal_decision"] == "REJECT"
    assert row["terminal_retryable_next_cycle"] is True
    assert row["terminal_formal_buy_authorized"] is False
