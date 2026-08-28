import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.production_status_dashboard import build, render_md


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_shows_learning_without_changing_formal_authority(tmp_path):
    auth = tmp_path / "auth"
    _write(auth / "production_authority.json", {
        "authorized": True, "canonical_snapshot_id": "snap-1", "canonical_source_run_id": "run-1",
        "source_head_sha": "source-sha", "source_workflow": "fixture",
    })
    _write(auth / "canonical_snapshot/latest.json", {
        "snapshot_id": "snap-1", "source_run_id": "run-1",
        "production": {"candidate_decisions": [{"action": "WAIT"}], "holding_decisions": [{"action": "HOLD"}]},
    })
    _write(auth / "holdings_reconciliation.json", {"status": "HOLDINGS_IN_SYNC", "formal_holding_actions_currently_usable": True})
    _write(auth / "candidate_lifecycle/summary.json", {"active_count": 3, "inactive_count": 1})
    _write(tmp_path / "data/research_priority/latest.json", {"p0_count": 2, "p1_count": 1, "mapping_gap_count": 4})
    _write(tmp_path / "data/price_value_history/summary.json", {"rows": [{"code": "600001"}, {"code": "600002"}]})
    _write(tmp_path / "data/formal_decision_outcomes/latest.json", {"record_count": 4, "observed_horizon_count": 0, "pending_horizon_count": 12})

    status = build(auth, main_sha="main-sha", state_root=tmp_path)
    assert status["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert status["formal_action_counts"] == {"WAIT": 1, "HOLD": 1}
    assert status["research_learning"]["p0_count"] == 2
    assert status["research_learning"]["parameter_tuning_allowed"] is False
    md = render_md(status)
    assert "Research Learning" in md
    assert "Automatic V3.1.1 parameter tuning: **DISABLED**" in md
    assert "Formal actions come only from the finalized canonical" in md
