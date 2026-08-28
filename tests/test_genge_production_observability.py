import json
from datetime import datetime, timezone
from pathlib import Path

from src.strategies.genge_opportunity_discovery.production_observability import build


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _learning(root: Path, ts: str):
    _write(root / "data/research_priority/latest.json", {"generated_at": ts, "formal_action_eligible": False, "formal_action_recomputed": False, "p0_count": 2, "p1_count": 1, "mapping_gap_count": 3})
    _write(root / "data/price_value_history/summary.json", {"generated_at": ts, "formal_action_eligible": False, "formal_action_recomputed": False, "rows": [{"code": "600001"}]})
    _write(root / "data/formal_decision_outcomes/latest.json", {"generated_at": ts, "formal_action_eligible": False, "formal_action_recomputed": False, "parameter_tuning_allowed": False, "record_count": 4, "observed_horizon_count": 0, "pending_horizon_count": 12})


def test_observability_detects_consistent_durable_state(tmp_path):
    sid = "snap-1"; run = "run-1"; ts = "2026-08-28T06:00:00+00:00"
    _write(tmp_path / "data/production_status/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run})
    _write(tmp_path / "data/hourly_research_state/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts, "workset_count": 4})
    _write(tmp_path / "data/hourly_deep_overlay/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts})
    _write(tmp_path / "data/evidence_events/index.json", {"generated_at": ts, "event_count": 8, "security_count": 4})
    _write(tmp_path / "data/evidence_events/collector_status.json", {"generated_at": ts})
    _write(tmp_path / "data/transactions/holdings_projection.json", {"holding_count": 4})
    _write(tmp_path / "data/opportunity_snapshots/candidate_lifecycle_state.json", {"latest_applied_snapshot_id": sid, "last_persisted_source_run_id": run, "candidates": {"600001": {}}})
    _write(tmp_path / "data/opportunity_snapshots/holding_valuation_continuity_state.json", {"latest_applied_snapshot_id": sid, "latest_applied_source_run_id": run})
    _learning(tmp_path, ts)
    payload = build(tmp_path, now=datetime(2026, 8, 28, 7, 0, tzinfo=timezone.utc))
    assert payload["health"] == "HEALTHY"
    assert payload["failed_checks"] == []
    assert payload["research_learning"]["p0_count"] == 2
    assert payload["research_learning"]["parameter_tuning_allowed"] is False


def test_observability_degrades_on_identity_conflict(tmp_path):
    ts = "2026-08-28T06:00:00+00:00"
    _write(tmp_path / "data/production_status/latest.json", {"canonical_snapshot_id": "snap-a", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/hourly_research_state/latest.json", {"canonical_snapshot_id": "snap-b", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/hourly_deep_overlay/latest.json", {"canonical_snapshot_id": "snap-a", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/evidence_events/index.json", {"event_count": 0, "security_count": 0})
    _write(tmp_path / "data/transactions/holdings_projection.json", {"holding_count": 0})
    _write(tmp_path / "data/opportunity_snapshots/candidate_lifecycle_state.json", {"latest_applied_snapshot_id": "snap-a", "last_persisted_source_run_id": "run-a", "candidates": {}})
    _write(tmp_path / "data/opportunity_snapshots/holding_valuation_continuity_state.json", {"latest_applied_snapshot_id": "snap-a", "latest_applied_source_run_id": "run-a"})
    _learning(tmp_path, ts)
    payload = build(tmp_path)
    assert payload["health"] == "DEGRADED"
    assert "canonical_snapshot_identity_consistent" in payload["failed_checks"]


def test_observability_degrades_when_learning_state_missing(tmp_path):
    sid = "snap-1"; run = "run-1"; ts = "2026-08-28T06:00:00+00:00"
    _write(tmp_path / "data/production_status/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run})
    _write(tmp_path / "data/hourly_research_state/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts})
    _write(tmp_path / "data/hourly_deep_overlay/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts})
    _write(tmp_path / "data/evidence_events/index.json", {"event_count": 0, "security_count": 0})
    _write(tmp_path / "data/transactions/holdings_projection.json", {"holding_count": 0})
    _write(tmp_path / "data/opportunity_snapshots/candidate_lifecycle_state.json", {"latest_applied_snapshot_id": sid, "last_persisted_source_run_id": run, "candidates": {}})
    _write(tmp_path / "data/opportunity_snapshots/holding_valuation_continuity_state.json", {"latest_applied_snapshot_id": sid, "latest_applied_source_run_id": run})
    payload = build(tmp_path)
    assert payload["health"] == "DEGRADED"
    assert "research_priority_available" in payload["failed_checks"]
    assert "price_value_history_available" in payload["failed_checks"]
    assert "formal_decision_outcomes_available" in payload["failed_checks"]
