from __future__ import annotations

import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.candidate_terminal_closure import (
    TERMINAL_STATES,
    build_terminal_rows,
    terminalize_candidate,
    write_terminal_report,
)


def _formal(code: str = "000415", **overrides):
    row = {"code": code, "stock_name": "测试公司", "long_term_blockers": ""}
    row.update(overrides)
    return row


def _production(action: str, **overrides):
    row = {
        "code": "000415",
        "stock_name": "测试公司",
        "decision_scope": "CANDIDATE",
        "production_action": action,
        "valuation_confidence": "HIGH",
        "production_model_frozen": "True",
        "reason_codes": "",
        "formal_buy_max_price_to_neutral": "0.8",
        "no_auto_trade": "True",
    }
    row.update(overrides)
    return row


def test_buy_only_mirrors_authoritative_production_buy():
    row = terminalize_candidate(_formal(), _production("BUY"))
    assert row["terminal_candidate_state"] == "BUY"
    assert row["terminal_reason"] == "AUTHORITATIVE_V311_PRODUCTION_BUY"
    assert row["formal_buy_mirrored_only"] is True
    assert row["new_trade_authority_created"] is False
    assert row["no_auto_trade"] is True


def test_high_confidence_price_only_wait_becomes_wait_price():
    row = terminalize_candidate(
        _formal(),
        _production(
            "WAIT",
            reason_codes="BUY_MARGIN_OF_SAFETY_INSUFFICIENT;PRICE_TOO_CLOSE_TO_BASE_VALUE",
            neutral_value="10",
            current_price="9",
        ),
    )
    assert row["terminal_candidate_state"] == "WAIT_PRICE"
    assert row["wait_price_max"] == 8.0
    assert row["terminal_reason"] == "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK"


def test_low_confidence_wait_is_rejected_not_parked():
    row = terminalize_candidate(
        _formal(long_term_blockers="scenario_valuation_incomplete;falsification_incomplete"),
        _production(
            "WAIT",
            valuation_confidence="LOW",
            reason_codes="BUY_VALUATION_CONFIDENCE_NOT_HIGH",
        ),
    )
    assert row["terminal_candidate_state"] == "REJECT"
    assert "AFTER_EXHAUSTIVE_CLOSURE" in row["terminal_reason"]


def test_stale_price_reason_cannot_create_wait_price_when_price_already_passes():
    row = terminalize_candidate(
        _formal(),
        _production(
            "WAIT",
            reason_codes="BUY_MARGIN_OF_SAFETY_INSUFFICIENT",
            neutral_value="10",
            current_price="7.5",
        ),
    )
    assert row["terminal_candidate_state"] == "REJECT"
    assert row["terminal_reason"] == "NON_PRICE_WAIT_AFTER_EXHAUSTIVE_CLOSURE"


def test_research_only_board_is_terminal_reject():
    row = terminalize_candidate(_formal(code="688281"), None)
    assert row["terminal_candidate_state"] == "REJECT"
    assert row["terminal_reason"] == "EXECUTION_UNIVERSE_BLOCKED"


def test_missing_production_decision_is_terminal_reject():
    row = terminalize_candidate(_formal(), None)
    assert row["terminal_candidate_state"] == "REJECT"
    assert row["terminal_reason"].startswith("AUTHORITATIVE_PRODUCTION_DECISION_MISSING")


def test_build_rows_has_no_intermediate_state():
    rows = build_terminal_rows(
        [_formal("000415"), _formal("000783"), _formal("688281")],
        [
            _production("BUY", code="000415"),
            _production(
                "WAIT",
                code="000783",
                reason_codes="PRICE_TOO_CLOSE_TO_BASE_VALUE",
                neutral_value="12.5",
                current_price="11.0",
            ),
        ],
    )
    assert len(rows) == 3
    assert all(row["terminal_candidate_state"] in TERMINAL_STATES for row in rows)
    assert {row["terminal_candidate_state"] for row in rows} == {"BUY", "WAIT_PRICE", "REJECT"}


def test_report_summary_enforces_terminal_contract(tmp_path: Path):
    formal_csv = tmp_path / "formal.csv"
    production_csv = tmp_path / "production.csv"
    output_dir = tmp_path / "out"

    with formal_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "stock_name", "long_term_blockers"])
        writer.writeheader()
        writer.writerow(_formal())
    with production_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "code", "stock_name", "decision_scope", "production_action",
                "valuation_confidence", "production_model_frozen", "reason_codes",
                "formal_buy_max_price_to_neutral", "neutral_value", "current_price",
                "no_auto_trade",
            ],
        )
        writer.writeheader()
        writer.writerow(_production("BUY"))

    rows = write_terminal_report(formal_csv, production_csv, output_dir)
    assert rows[0]["terminal_candidate_state"] == "BUY"
    summary = json.loads((output_dir / "candidate_terminal_summary.json").read_text(encoding="utf-8"))
    assert summary["terminality_contract_satisfied"] is True
    assert summary["non_terminal_count"] == 0
    assert summary["new_trade_authority_created"] is False
    assert summary["canonical_authority_preserved"] is True
    assert summary["no_auto_trade"] is True
