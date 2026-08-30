import importlib.util
import json
from pathlib import Path

import pytest

from src.genge_v311_persistence_order import (
    PersistenceIdentityError,
    PersistenceOrder,
    classify_persistence_order,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


holding = _load_module(
    "genge_holding_valuation_continuity_test",
    "src/strategies/genge_opportunity_discovery/holding_valuation_continuity.py",
)
formal = _load_module(
    "genge_formal_decision_history_test",
    "src/strategies/genge_opportunity_discovery/formal_decision_history.py",
)
status_dashboard = _load_module(
    "genge_production_status_dashboard_test",
    "src/strategies/genge_opportunity_discovery/production_status_dashboard.py",
)


def _snapshot(snapshot_id: str, run_id, *, code: str = "600001", action: str = "HOLD") -> dict:
    return {
        "snapshot_id": snapshot_id,
        "source_run_id": run_id,
        "research_as_of": "2026-08-30T00:00:00Z",
        "latest_trade_date": "2026-08-28",
        "production": {
            "candidate_decisions": [],
            "holding_decisions": [
                {
                    "code": code,
                    "action": action,
                    "neutral_value": "10.0",
                    "normalized_earnings": "1.0",
                    "current_price": "9.0",
                    "price_to_neutral": "0.9",
                    "valuation_confidence": "HIGH",
                    "reason_codes": "TEST_ONLY",
                    "decision_date": "2026-08-30",
                }
            ],
        },
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_persistence_order_is_strict_and_fail_closed():
    assert (
        classify_persistence_order(
            incoming_snapshot_id="snap-1", incoming_source_run_id="100"
        )
        is PersistenceOrder.INITIAL
    )
    assert (
        classify_persistence_order(
            incoming_snapshot_id="snap-2",
            incoming_source_run_id=101,
            current_snapshot_id="snap-1",
            current_source_run_id="100",
        )
        is PersistenceOrder.NEWER
    )
    assert (
        classify_persistence_order(
            incoming_snapshot_id="snap-1",
            incoming_source_run_id="100",
            current_snapshot_id="snap-1",
            current_source_run_id=100,
        )
        is PersistenceOrder.SAME
    )
    assert (
        classify_persistence_order(
            incoming_snapshot_id="snap-old",
            incoming_source_run_id=99,
            current_snapshot_id="snap-1",
            current_source_run_id=100,
        )
        is PersistenceOrder.STALE
    )
    with pytest.raises(PersistenceIdentityError):
        classify_persistence_order(
            incoming_snapshot_id="different",
            incoming_source_run_id=100,
            current_snapshot_id="snap-1",
            current_source_run_id=100,
        )
    for bad_run in (True, 0, -1, 1.5, "", "run-100", None):
        with pytest.raises(PersistenceIdentityError):
            classify_persistence_order(
                incoming_snapshot_id="snap", incoming_source_run_id=bad_run
            )
    with pytest.raises(PersistenceIdentityError):
        classify_persistence_order(
            incoming_snapshot_id="snap",
            incoming_source_run_id=101,
            current_snapshot_id="snap-1",
            current_source_run_id=None,
        )


def test_holding_continuity_never_regresses_latest_state(tmp_path):
    state_path = tmp_path / "holding_state.json"
    snap100 = tmp_path / "snap100.json"
    snap101 = tmp_path / "snap101.json"
    stale99 = tmp_path / "stale99.json"
    conflict = tmp_path / "conflict.json"
    _write_json(snap100, _snapshot("snap-100", 100))
    _write_json(snap101, _snapshot("snap-101", 101, action="HOLD_NO_ADD"))
    _write_json(stale99, _snapshot("snap-099", 99, action="REDUCE_25"))
    _write_json(conflict, _snapshot("other-snap-101", 101))

    holding.persist_from_snapshot(snap100, state_path)
    holding.persist_from_snapshot(snap101, state_path)
    latest_bytes = state_path.read_bytes()

    # A late old workflow_run and an exact duplicate are durable no-ops.
    holding.persist_from_snapshot(stale99, state_path)
    assert state_path.read_bytes() == latest_bytes
    holding.persist_from_snapshot(snap101, state_path)
    assert state_path.read_bytes() == latest_bytes

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["latest_applied_snapshot_id"] == "snap-101"
    assert state["latest_applied_source_run_id"] == "101"
    assert state["holdings"]["600001"]["action"] == "HOLD_NO_ADD"

    with pytest.raises(PersistenceIdentityError):
        holding.persist_from_snapshot(conflict, state_path)
    assert state_path.read_bytes() == latest_bytes


def test_holding_continuity_rejects_unordered_legacy_baseline(tmp_path):
    state_path = tmp_path / "holding_state.json"
    _write_json(
        state_path,
        {"contract_version": "legacy", "holdings": {"600001": {"neutral_value": "10"}}},
    )
    snap = tmp_path / "snap.json"
    _write_json(snap, _snapshot("snap-100", 100))
    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="no durable Canonical identity"):
        holding.persist_from_snapshot(snap, state_path)
    assert state_path.read_bytes() == before


def test_formal_history_keeps_immutable_old_records_without_regressing_latest(tmp_path):
    history_path = tmp_path / "history.jsonl"
    summary_path = tmp_path / "latest_summary.json"
    snap100 = tmp_path / "snap100.json"
    snap101 = tmp_path / "snap101.json"
    stale99 = tmp_path / "stale99.json"
    conflict = tmp_path / "conflict.json"
    _write_json(snap100, _snapshot("snap-100", 100, code="600100"))
    _write_json(snap101, _snapshot("snap-101", 101, code="600101"))
    _write_json(stale99, _snapshot("snap-099", 99, code="600099"))
    _write_json(conflict, _snapshot("different-101", 101, code="600102"))

    formal.append_snapshot(snap100, history_path, summary_path)
    formal.append_snapshot(snap101, history_path, summary_path)
    latest_before = json.loads(summary_path.read_text(encoding="utf-8"))
    assert latest_before["canonical_snapshot_id"] == "snap-101"
    assert latest_before["canonical_source_run_id"] == "101"

    stale_result = formal.append_snapshot(stale99, history_path, summary_path)
    latest_after = json.loads(summary_path.read_text(encoding="utf-8"))
    assert stale_result["persistence_order"] == "STALE"
    assert stale_result["latest_summary_updated"] is False
    assert latest_after == latest_before
    history = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert {row["canonical_snapshot_id"] for row in history} == {
        "snap-099",
        "snap-100",
        "snap-101",
    }

    before_history = history_path.read_bytes()
    before_summary = summary_path.read_bytes()
    with pytest.raises(PersistenceIdentityError):
        formal.append_snapshot(conflict, history_path, summary_path)
    assert history_path.read_bytes() == before_history
    assert summary_path.read_bytes() == before_summary


def test_formal_summary_legacy_run_id_is_recovered_only_from_matching_history(tmp_path):
    history_path = tmp_path / "history.jsonl"
    summary_path = tmp_path / "latest_summary.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write_json(snapshot_path, _snapshot("snap-100", 100))
    formal.append_snapshot(snapshot_path, history_path, summary_path)

    legacy = json.loads(summary_path.read_text(encoding="utf-8"))
    legacy.pop("canonical_source_run_id")
    _write_json(summary_path, legacy)
    result = formal.append_snapshot(snapshot_path, history_path, summary_path)
    migrated = json.loads(summary_path.read_text(encoding="utf-8"))
    assert result["persistence_order"] == "SAME"
    assert migrated["canonical_source_run_id"] == "100"

    _write_json(
        summary_path,
        {"canonical_snapshot_id": "missing-from-history", "contract_version": formal.CONTRACT_VERSION},
    )
    with pytest.raises(ValueError, match="cannot uniquely recover"):
        formal.append_snapshot(snapshot_path, history_path, summary_path)


def _status(snapshot_id: str, run_id: str, *, p0_count: int) -> dict:
    return {
        "canonical_snapshot_id": snapshot_id,
        "canonical_source_run_id": run_id,
        "research_learning": {"p0_count": p0_count},
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "no_auto_trade": True,
    }


def test_production_status_stale_event_cannot_overwrite_latest(tmp_path):
    json_output = tmp_path / "latest.json"
    md_output = tmp_path / "latest.md"
    current = _status("snap-101", "101", p0_count=3)
    status_dashboard.persist_status(current, json_output, md_output)
    json_before = json_output.read_bytes()
    md_before = md_output.read_bytes()

    stale = _status("snap-100", "100", p0_count=999)
    persisted = status_dashboard.persist_status(stale, json_output, md_output)
    assert persisted["canonical_snapshot_id"] == "snap-101"
    assert json_output.read_bytes() == json_before
    assert md_output.read_bytes() == md_before

    # Same Canonical truth may refresh non-authoritative learning projection.
    refreshed = _status("snap-101", "101", p0_count=4)
    status_dashboard.persist_status(refreshed, json_output, md_output)
    assert json.loads(json_output.read_text(encoding="utf-8"))["research_learning"]["p0_count"] == 4

    conflict = _status("different-101", "101", p0_count=5)
    conflict_before = json_output.read_bytes()
    with pytest.raises(PersistenceIdentityError):
        status_dashboard.persist_status(conflict, json_output, md_output)
    assert json_output.read_bytes() == conflict_before
