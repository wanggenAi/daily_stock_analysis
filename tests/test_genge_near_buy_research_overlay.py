from __future__ import annotations

import csv
import json

import pytest

from scripts.near_buy_research_overlay import (
    build_overlay,
    classify_terminal_row,
    evaluate_forward_outcomes,
    write_overlay,
)


def _row(**overrides):
    row = {
        "master_research_rank": "1",
        "code": "001316",
        "stock_name": "Sample",
        "terminal_decision": "REJECT",
        "terminal_reason_class": "EVIDENCE_INSUFFICIENT",
        "terminal_reason_codes": "incomplete:scenario_valuation",
        "terminal_retryable_next_cycle": "True",
        "terminal_full_review_attempted": "True",
        "terminal_formal_buy_authorized": "False",
        "source_production_reason_codes": "STRICT_PIT_INPUT_INCOMPLETE",
        "v31_candidate_class": "A2",
        "v31_score_total": "82",
        "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
        "v31_hard_gate_failures": "",
        "v31_hard_gate_unknowns": "",
        "v31_score_complete": "True",
        "v31_normalized_profit_ready": "True",
        "v31_scenario_valuation_ready": "False",
        "v31_implied_expectation_ready": "True",
        "v31_expectation_gap_ready": "True",
        "v31_risk_adjusted_cagr_ready": "True",
        "v31_downside_ready": "True",
        "v31_falsification_ready": "True",
        "decision_authority": "RESEARCH_TERMINAL_VIEW",
        "formal_signal_eligible": "False",
        "automatic_promotion_allowed": "False",
        "no_auto_trade": "True",
    }
    row.update(overrides)
    return row


def test_missing_evidence_without_hard_fail_can_be_near_buy():
    result = classify_terminal_row(_row())
    assert result["research_opportunity_state"] == "NEAR_BUY"
    assert result["near_buy_evidence_state"] == "MISSING"
    assert "scenario_valuation" in result["missing_evidence_items"]
    assert result["starter_position_advisory_allowed"] is True
    assert result["starter_fraction_of_normal_target"] == 0.25


def test_confirmed_negative_cannot_be_near_buy():
    result = classify_terminal_row(
        _row(source_production_reason_codes="FUNDAMENTAL_BREAK")
    )
    assert result["research_opportunity_state"] == "NONE"
    assert result["near_buy_evidence_state"] == "CONFIRMED_NEGATIVE"
    assert result["starter_position_advisory_allowed"] is False


def test_hard_gate_failure_cannot_be_near_buy():
    result = classify_terminal_row(
        _row(
            terminal_reason_class="HARD_GATE_FAILED",
            terminal_reason_codes="hard_gate_failed:moat",
            v31_hard_gate_failures="moat",
            v31_scenario_valuation_ready="True",
        )
    )
    assert result["research_opportunity_state"] == "NONE"
    assert "hard_gate:moat" in result["confirmed_negative_items"]


def test_starter_advisory_never_mutates_terminal_or_formal_authority():
    source = _row(terminal_decision="WAIT_PRICE", terminal_reason_class="HIGH_CONFIDENCE_PRICE_ONLY_BLOCK")
    result = classify_terminal_row(source)
    assert result["terminal_decision"] == "WAIT_PRICE"
    assert result["formal_action_unchanged"] is True
    assert result["canonical_authority_unchanged"] is True
    assert result["automatic_promotion_allowed"] is False
    assert result["no_auto_trade"] is True
    assert result["near_buy_authority"] == "OBSERVER_ONLY_RESEARCH_OVERLAY"


def test_starter_fraction_is_hard_bounded_to_20_30_percent():
    with pytest.raises(ValueError, match="starter_fraction"):
        classify_terminal_row(_row(), starter_fraction=0.31)
    with pytest.raises(ValueError, match="starter_fraction"):
        classify_terminal_row(_row(), starter_fraction=0.19)


def test_low_score_or_unreviewed_candidate_is_not_near_buy():
    assert classify_terminal_row(_row(v31_score_total="69.9"))["research_opportunity_state"] == "NONE"
    assert classify_terminal_row(_row(terminal_full_review_attempted="False"))["research_opportunity_state"] == "NONE"


def test_overlay_ranks_near_buy_before_non_near_buy_without_changing_terminal_state():
    near = _row(code="001316", v31_score_total="82")
    no = _row(code="600000", v31_score_total="90", v31_hard_gate_failures="moat", terminal_reason_class="HARD_GATE_FAILED")
    rows = build_overlay([no, near])
    assert rows[0]["code"] == "001316"
    assert rows[0]["research_opportunity_state"] == "NEAR_BUY"
    assert rows[0]["terminal_decision"] == "REJECT"
    assert rows[1]["terminal_decision"] == "REJECT"


def test_write_overlay_serializes_contract(tmp_path):
    terminal = tmp_path / "terminal.csv"
    out = tmp_path / "out"
    source = _row()
    with terminal.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)

    write_overlay(terminal, out)
    summary = json.loads((out / "near_buy_research_summary.json").read_text(encoding="utf-8"))
    assert summary["near_buy_count"] == 1
    assert summary["formal_action_unchanged"] is True
    assert summary["canonical_authority_unchanged"] is True
    assert summary["hard_gate_failure_can_be_near_buy"] is False
    assert summary["confirmed_negative_can_be_near_buy"] is False
    assert summary["no_auto_trade"] is True
    assert (out / "near_buy_research_overlay.csv").exists()
    assert "Near-BUY: 1" in (out / "near_buy_research_overlay.md").read_text(encoding="utf-8")


def test_forward_5_10_20_60_metrics_and_drawdown_aggregate_correctly():
    observations = [
        {
            "return_5d": 0.10,
            "return_10d": 0.20,
            "return_20d": 0.30,
            "return_60d": 0.40,
            "benchmark_return_5d": 0.02,
            "benchmark_return_10d": 0.03,
            "benchmark_return_20d": 0.04,
            "benchmark_return_60d": 0.05,
            "max_drawdown_60d": -0.12,
        },
        {
            "return_5d": -0.05,
            "return_10d": -0.10,
            "return_20d": 0.05,
            "return_60d": -0.20,
            "benchmark_return_5d": 0.01,
            "benchmark_return_10d": 0.02,
            "benchmark_return_20d": 0.03,
            "benchmark_return_60d": 0.04,
            "max_drawdown_60d": -0.25,
        },
    ]
    result = evaluate_forward_outcomes(observations)
    assert result["forward_horizons_trading_days"] == [5, 10, 20, 60]
    assert result["horizons"]["5"]["average_return"] == pytest.approx(0.025)
    assert result["horizons"]["5"]["win_rate"] == 0.5
    assert result["horizons"]["5"]["profit_loss_ratio"] == pytest.approx(2.0)
    assert result["horizons"]["5"]["average_excess_return"] == pytest.approx(0.01)
    assert result["horizons"]["60"]["average_return"] == pytest.approx(0.10)
    assert result["max_drawdown_60d"]["worst"] == -0.25
    assert result["observer_only"] is True
    assert result["production_semantics_mutated"] is False
    assert result["canonical_authority_unchanged"] is True
    assert result["no_auto_trade"] is True
