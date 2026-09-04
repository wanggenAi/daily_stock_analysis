from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.decision_outcome_evaluator import (
    evaluate,
    extract_decisions,
    import_canonical,
    record_execution,
)


def _canonical() -> dict:
    return {
        "snapshot_id": "snap-1",
        "source_run_id": "run-1",
        "latest_trade_date": "2026-09-04",
        "research_as_of": "2026-09-04T06:00:00Z",
        "holding_decisions": [
            {"symbol": "603993", "name": "洛阳钼业", "formal_action": "HOLD"},
            {"symbol": "600406", "name": "国电南瑞", "formal_action": "REDUCE_25"},
        ],
        "candidate_decisions": [
            {"symbol": "600309", "name": "万华化学", "formal_action": "WAIT_PRICE"},
        ],
    }


def test_import_same_snapshot_twice_is_noop(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.json"
    decisions_path = tmp_path / "decision_events.jsonl"
    canonical_path.write_text(json.dumps(_canonical(), ensure_ascii=False), encoding="utf-8")

    first = import_canonical(canonical_path, decisions_path)
    second = import_canonical(canonical_path, decisions_path)

    assert first["status"] == "IMPORTED"
    assert first["appended"] == 3
    assert second["status"] == "NOOP"
    assert second["appended"] == 0
    assert len(decisions_path.read_text(encoding="utf-8").splitlines()) == 3


def test_execution_is_separate_from_canonical_decision(tmp_path: Path) -> None:
    canonical = _canonical()
    decisions = extract_decisions(canonical)
    executions_path = tmp_path / "execution_events.jsonl"
    decision = next(row for row in decisions if row["symbol"] == "603993")

    result = record_execution(
        executions_path,
        symbol="603993",
        side="BUY",
        quantity=100,
        price=18.50,
        executed_at="2026-09-04T02:00:00Z",
        decision_id=decision["decision_id"],
    )

    assert result["status"] == "RECORDED"
    execution = json.loads(executions_path.read_text(encoding="utf-8"))
    assert execution["event_type"] == "EXPLICIT_EXECUTION_RECORDED"
    assert execution["decision_id"] == decision["decision_id"]
    assert "quantity" not in decision
    assert decision["event_type"] == "CANONICAL_DECISION_OBSERVED"


def test_open_positions_excluded_from_closed_win_loss_stats() -> None:
    executions = [
        {
            "execution_id": "e1",
            "symbol": "600309",
            "side": "BUY",
            "quantity": 100,
            "price": 75.0,
            "fees": 0.0,
            "executed_at": "2026-09-01T01:00:00Z",
        },
    ]

    summary = evaluate([], executions)

    closed = summary["closed_trade_statistics"]
    assert closed["closed_sell_events"] == 0
    assert closed["wins"] == 0
    assert closed["losses"] == 0
    assert closed["win_rate"] is None
    assert closed["expectancy_per_closed_sell"] is None
    assert summary["executions"]["open_quantity_by_symbol"] == {"600309": 100}


def test_closed_fifo_trade_statistics_use_only_explicit_execution() -> None:
    executions = [
        {"execution_id": "e1", "symbol": "600309", "side": "BUY", "quantity": 100, "price": 70.0, "fees": 5.0, "executed_at": "2026-09-01T01:00:00Z"},
        {"execution_id": "e2", "symbol": "600309", "side": "SELL", "quantity": 100, "price": 75.0, "fees": 5.0, "executed_at": "2026-09-02T01:00:00Z"},
    ]

    summary = evaluate([], executions)
    closed = summary["closed_trade_statistics"]

    assert closed["closed_sell_events"] == 1
    assert closed["wins"] == 1
    assert closed["losses"] == 0
    assert closed["win_rate"] == 1.0
    assert closed["realized_pnl_by_symbol"]["600309"] == pytest.approx(490.0)


def test_extract_does_not_mutate_canonical_payload() -> None:
    canonical = _canonical()
    before = copy.deepcopy(canonical)

    extract_decisions(canonical)

    assert canonical == before


def test_execution_cannot_sell_unrecorded_inventory() -> None:
    executions = [
        {"execution_id": "e1", "symbol": "603993", "side": "SELL", "quantity": 100, "price": 20.0, "fees": 0.0, "executed_at": "2026-09-04T01:00:00Z"},
    ]

    with pytest.raises(ValueError, match="exceeds explicit open quantity"):
        evaluate([], executions)
