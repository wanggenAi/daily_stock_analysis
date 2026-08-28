import json
from datetime import datetime, timezone
from pathlib import Path

from src.strategies.genge_opportunity_discovery.production_observability import build


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_observability_detects_consistent_durable_state(tmp_path):
    sid = "snap-1"
    run = "run-1"
    ts = "2026-08-28T06:00:00+00:00"
    _write(tmp_path / "data/production_status/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run})
    _write(tmp_path / "data/hourly_research_state/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts, "workset_count": 4})
    _write(tmp_path / "data/hourly_deep_overlay/latest.json", {"canonical_snapshot_id": sid, "canonical_source_run_id": run, "generated_at": ts})
    _write(tmp_path / "data/evidence_events/index.json", {"generated_at": ts, "event_count": 8, "security_count": 4})
    _write(tmp_path / "data/evidence_events/collector_status.json", {"generated_at": ts})
    _write(tmp_path / "data/transactions/holdings_projection.json", {"holding_count": 4})
    _write(tmp_path / "data/opportunity_snapshots/candidate_lifecycle_state.json", {"latest_applied_snapshot_id": sid, "last_persisted_source_run_id": run, "candidates": {"600001": {}}})
    _write(tmp_path / "data/opportunity_snapshots/holding_valuation_continuity_state.json", {"latest_applied_snapshot_id": sid, "latest_applied_source_run_id": run})

    payload = build(tmp_path, now=datetime(2026, 8, 28, 7, 0, tzinfo=timezone.utc))
    assert payload["health"] == "HEALTHY"
    assert payload["failed_checks"] == []
    assert payload["canonical_snapshot_ids_seen"] == [sid]
    assert payload["formal_action_recomputed"] is False


def test_observability_degrades_on_identity_conflict(tmp_path):
    _write(tmp_path / "data/production_status/latest.json", {"canonical_snapshot_id": "snap-a", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/hourly_research_state/latest.json", {"canonical_snapshot_id": "snap-b", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/hourly_deep_overlay/latest.json", {"canonical_snapshot_id": "snap-a", "canonical_source_run_id": "run-a"})
    _write(tmp_path / "data/evidence_events/index.json", {"event_count": 0, "security_count": 0})
    _write(tmp_path / "data/transactions/holdings_projection.json", {"holding_count": 0})
    _write(tmp_path / "data/opportunity_snapshots/candidate_lifecycle_state.json", {"latest_applied_snapshot_id": "snap-a", "last_persisted_source_run_id": "run-a", "candidates": {}})
    _write(tmp_path / "data/opportunity_snapshots/holding_valuation_continuity_state.json", {"latest_applied_snapshot_id": "snap-a", "latest_applied_source_run_id": "run-a"})

    payload = build(tmp_path)
    assert payload["health"] == "DEGRADED"
    assert "canonical_snapshot_identity_consistent" in payload["failed_checks"]
