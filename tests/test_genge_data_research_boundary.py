from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import genge_bind_decision_center_snapshot as binder
from scripts import genge_data_package as data_package
from scripts import genge_external_fresh_evidence as external_evidence
from scripts import genge_research_input as research_input


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _configure_package(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    package_dir = tmp_path / "data" / "data_package"
    monkeypatch.setattr(data_package, "PACKAGE_DIR", package_dir)
    monkeypatch.setattr(data_package, "LATEST_PATH", package_dir / "latest.json")
    monkeypatch.setattr(data_package, "SNAPSHOT_DIR", package_dir / "snapshots")
    monkeypatch.setattr(data_package, "STATE_PATH", package_dir / "watermarks.json")
    era = tmp_path / "data" / "era_radar"
    global_pulse = tmp_path / "data" / "global_market_pulse"
    monkeypatch.setattr(
        data_package,
        "PRODUCER_ROOTS",
        (
            ("era_radar", str(era), True, 8 * 60),
            ("global_market_pulse", str(global_pulse), True, 8 * 60),
        ),
    )
    return era, global_pulse


def test_snapshot_id_is_deterministic_and_business_timestamp_driven(monkeypatch, tmp_path):
    era, global_pulse = _configure_package(monkeypatch, tmp_path)
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    _write_json(era / "latest.json", {"research_as_of": now.isoformat(), "snapshot_id": "era-1"})
    _write_json(
        global_pulse / "latest.json",
        {
            "generated_at": now.isoformat(),
            "a_share_market_clock": {"last_valid_trade_date": "2026-10-09"},
        },
    )
    first = data_package.build_package(now=now, write=True)
    second = data_package.build_package(now=now + timedelta(minutes=5), write=True)
    assert first["package_status"] == "READY"
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["latest_trade_date"] == "2026-10-09"
    assert first["incremental_update_contract"]["filesystem_mtime_may_establish_freshness"] is False


def test_required_dataset_without_business_timestamp_is_invalid_even_when_file_is_new(monkeypatch, tmp_path):
    era, global_pulse = _configure_package(monkeypatch, tmp_path)
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    _write_json(era / "latest.json", {"snapshot_id": "no-real-clock"})
    _write_json(global_pulse / "latest.json", {"generated_at": now.isoformat()})
    package = data_package.build_package(now=now, write=True)
    assert package["package_status"] == "INVALID"
    assert "era_radar" in package["unknown_required_datasets"]


def test_stale_package_can_be_researched_but_cannot_authorize_execution(monkeypatch, tmp_path):
    era, global_pulse = _configure_package(monkeypatch, tmp_path)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=1)
    _write_json(era / "latest.json", {"research_as_of": old.isoformat()})
    _write_json(global_pulse / "latest.json", {"generated_at": old.isoformat(), "last_valid_trade_date": "2026-10-09"})
    package = data_package.build_package(now=now, write=True)
    assert package["package_status"] == "STALE"

    research_dir = tmp_path / "data" / "research_input"
    monkeypatch.setattr(research_input, "PACKAGE_LATEST", data_package.LATEST_PATH)
    monkeypatch.setattr(research_input, "PACKAGE_SNAPSHOTS", data_package.SNAPSHOT_DIR)
    monkeypatch.setattr(research_input, "OUT_DIR", research_dir)
    monkeypatch.setattr(research_input, "OUT_LATEST", research_dir / "latest.json")
    receipt = research_input.lock_research_input(mode="manual", allow_stale_research_only=True, write=True)
    assert receipt["research_allowed"] is True
    assert receipt["execution_allowed"] is False
    assert receipt["network_policy"] == "CANONICAL_PACKAGE_ONLY"


def test_external_fresh_evidence_never_has_formal_authority(monkeypatch, tmp_path):
    monkeypatch.setattr(external_evidence, "OUT_DIR", tmp_path / "external")
    event = external_evidence.ingest(
        {
            "source_url": "https://example.com/event",
            "observed_at": "2026-10-10T01:00:00+00:00",
            "thesis": "Material event requiring temporary verification",
            "affected_codes": ["600406"],
        },
        write=True,
    )
    assert event["tag"] == "EXTERNAL_FRESH_EVIDENCE"
    assert event["formal_action_authority"] == "NONE"
    assert event["automatic_execution_allowed"] is False
    assert event["backfill_status"] == "PENDING_CANONICAL_INGEST"


def test_decision_provenance_fail_closes_stale_execution_without_mutating_formal_action(tmp_path):
    package = tmp_path / "package.json"
    receipt = tmp_path / "receipt.json"
    decision = tmp_path / "decision.json"
    handoff = tmp_path / "handoff.json"
    _write_json(
        package,
        {
            "contract": "GEN_GE_REALTIME_DATA_PACKAGE_V1",
            "snapshot_id": "snap-1",
            "generated_at": "2026-10-10T00:00:00+00:00",
            "package_status": "STALE",
            "latest_trade_date": "2026-10-09",
            "pending_external_fresh_evidence_count": 0,
        },
    )
    _write_json(
        receipt,
        {
            "contract": "GEN_GE_RESEARCH_INPUT_LOCK_V1",
            "input_snapshot_id": "snap-1",
            "research_mode": "manual",
            "locked_at": "2026-10-10T00:01:00+00:00",
            "network_policy": "CANONICAL_PACKAGE_ONLY",
            "external_fresh_evidence_policy": "TAGGED_EXCEPTION_ONLY",
            "execution_allowed": False,
            "fail_closed_reason": "DATA_PACKAGE_STALE_NOT_EXECUTABLE",
        },
    )
    original_action = "REDUCE_25"
    _write_json(
        decision,
        {
            "formal_action_source": "FINALIZED_CANONICAL_ONLY",
            "formal_action_recomputed": False,
            "today_account_plan": {
                "available_cash_cny": 50000,
                "planned_immediate_cash_cny": 10000,
                "operations": [
                    {
                        "code": "600406",
                        "formal_action": original_action,
                        "immediate_execution_eligible": True,
                        "executable_shares": 100,
                    }
                ],
            },
        },
    )
    _write_json(handoff, {"formal_action_source": "FINALIZED_CANONICAL_ONLY"})
    output = binder.bind(decision_path=decision, package_path=package, receipt_path=receipt, handoff_path=handoff)
    op = output["today_account_plan"]["operations"][0]
    assert op["formal_action"] == original_action
    assert op["immediate_execution_eligible"] is False
    assert op["executable_shares"] == 0
    assert output["today_account_plan"]["planned_immediate_cash_cny"] == 0
    assert output["data_package_provenance"]["snapshot_id"] == "snap-1"
    assert output["data_freshness_execution_guard"]["execution_allowed"] is False
