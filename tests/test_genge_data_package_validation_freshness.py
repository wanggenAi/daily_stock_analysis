from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts import genge_data_package as package


NOW = datetime(2026, 10, 11, 8, 0, tzinfo=timezone.utc)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _seed_semantic_sources(root: Path) -> None:
    _write(
        root / "data/market_snapshots/2026-10-09.json",
        {
            "contract": "TEST_MARKET_SNAPSHOT",
            "generated_at": "2026-10-09T07:00:00+00:00",
            "trade_date": "2026-10-09",
        },
    )
    _write(
        root / "data/era_radar/latest.json",
        {
            "contract": "TEST_ERA_SEMANTIC",
            "research_as_of": "2026-10-08T03:00:00+00:00",
            "semantic_marker": "unchanged-era-state",
            "formal_trading_authority": False,
            "no_auto_trade": True,
        },
    )
    _write(
        root / "data/global_market_pulse/latest.json",
        {
            "contract_version": "GEN_GE_GLOBAL_MARKET_PULSE_V2",
            "generated_at": "2026-10-08T03:00:00+00:00",
            "a_share_market_clock": {"last_valid_trade_date": "2026-10-09"},
            "semantic_marker": "unchanged-global-state",
            "authority": "RESEARCH_ONLY",
            "formal_trading_authority": False,
            "formal_action_eligible": False,
            "no_auto_trade": True,
        },
    )


def _era_heartbeat(*, refreshed_at: str = "2026-10-11T07:30:00+00:00") -> dict:
    return {
        "contract": "ERA_RADAR_SOURCE_VALIDATION_V1",
        "refreshed_at": refreshed_at,
        "validation_status": "SUCCESS",
        "semantic_state": "PERSISTED",
        "successful_collectors": 5,
        "failed_collectors": 0,
        "evidence_fingerprint": "era-evidence-fingerprint",
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }


def _global_heartbeat(
    *,
    refreshed_at: str = "2026-10-11T07:30:00+00:00",
    latest_observation_at: str = "2026-10-11T07:00:00+00:00",
) -> dict:
    return {
        "contract": "GEN_GE_GLOBAL_MARKET_PULSE_VALIDATION_V1",
        "refreshed_at": refreshed_at,
        "validation_status": "SUCCESS",
        "coverage_status": "OK",
        "semantic_state": "NO_CHANGE",
        "semantic_fingerprint": "global-semantic-fingerprint",
        "latest_observation_at": latest_observation_at,
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }


def _seed_successful_validation(root: Path) -> None:
    _write(root / "data/era_radar/validation/latest.json", _era_heartbeat())
    _write(root / "data/global_market_pulse/validation/latest.json", _global_heartbeat())


def _dataset(payload: dict, name: str) -> dict:
    return next(row for row in payload["datasets"] if row["name"] == name)


def test_unchanged_semantic_content_can_be_fresh_after_successful_live_validation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _seed_successful_validation(tmp_path)
    era_path = tmp_path / "data/era_radar/latest.json"
    global_path = tmp_path / "data/global_market_pulse/latest.json"
    before_era = era_path.read_bytes()
    before_global = global_path.read_bytes()

    payload = package.build_package(now=NOW, write=False)
    era = _dataset(payload, "era_radar")
    global_pulse = _dataset(payload, "global_market_pulse")

    assert payload["package_status"] == "READY"
    assert payload["latest_trade_date"] == "2026-10-09"
    assert era["freshness_state"] == "FRESH"
    assert global_pulse["freshness_state"] == "FRESH"
    assert era["latest_observed_at"] == "2026-10-08T03:00:00+00:00"
    assert global_pulse["latest_observed_at"] == "2026-10-08T03:00:00+00:00"
    assert era["validation_evidence"]["accepted"] is True
    assert global_pulse["validation_evidence"]["accepted"] is True
    assert era_path.read_bytes() == before_era
    assert global_path.read_bytes() == before_global


def test_missing_validation_heartbeat_stays_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _write(tmp_path / "data/global_market_pulse/validation/latest.json", _global_heartbeat())

    payload = package.build_package(now=NOW, write=False)
    era = _dataset(payload, "era_radar")

    assert payload["package_status"] == "STALE"
    assert era["freshness_state"] == "STALE"
    assert era["validation_evidence"]["accepted"] is False
    assert era["validation_evidence"]["reason"] == "VALIDATION_HEARTBEAT_MISSING"


def test_old_validation_heartbeat_stays_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _seed_successful_validation(tmp_path)
    _write(
        tmp_path / "data/era_radar/validation/latest.json",
        _era_heartbeat(refreshed_at="2026-10-10T20:00:00+00:00"),
    )

    payload = package.build_package(now=NOW, write=False)
    era = _dataset(payload, "era_radar")

    assert payload["package_status"] == "STALE"
    assert era["freshness_state"] == "STALE"
    assert era["validation_evidence"]["reason"] == "VALIDATION_HEARTBEAT_STALE"


def test_failed_collection_validation_cannot_pass_freshness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _seed_successful_validation(tmp_path)
    failed = _era_heartbeat()
    failed["validation_status"] = "FAILED"
    failed["successful_collectors"] = 4
    failed["failed_collectors"] = 1
    _write(tmp_path / "data/era_radar/validation/latest.json", failed)

    payload = package.build_package(now=NOW, write=False)
    era = _dataset(payload, "era_radar")

    assert payload["package_status"] == "STALE"
    assert era["freshness_state"] == "STALE"
    assert era["validation_evidence"]["reason"] == "VALIDATION_NOT_SUCCESS"


def test_fresh_global_heartbeat_cannot_hide_stale_market_observation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _seed_successful_validation(tmp_path)
    _write(
        tmp_path / "data/global_market_pulse/validation/latest.json",
        _global_heartbeat(latest_observation_at="2026-10-10T20:00:00+00:00"),
    )

    payload = package.build_package(now=NOW, write=False)
    global_pulse = _dataset(payload, "global_market_pulse")

    assert payload["package_status"] == "STALE"
    assert global_pulse["freshness_state"] == "STALE"
    assert global_pulse["validation_evidence"]["reason"] == "GLOBAL_LATEST_OBSERVATION_STALE"


def test_validation_is_provenance_only_and_cannot_grant_authority(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_semantic_sources(tmp_path)
    _seed_successful_validation(tmp_path)
    era_semantic = tmp_path / "data/era_radar/latest.json"
    semantic_before = era_semantic.read_bytes()

    escalated = _era_heartbeat()
    escalated["formal_trading_authority"] = True
    _write(tmp_path / "data/era_radar/validation/latest.json", escalated)

    payload = package.build_package(now=NOW, write=False)
    era = _dataset(payload, "era_radar")

    assert payload["package_status"] == "STALE"
    assert era["freshness_state"] == "STALE"
    assert era["validation_evidence"]["reason"] == "VALIDATION_AUTHORITY_INVARIANT_FAILED"
    assert era_semantic.read_bytes() == semantic_before
    assert payload["incremental_update_contract"]["validation_heartbeat_may_mutate_semantic_content"] is False
    assert payload["incremental_update_contract"]["validation_heartbeat_may_grant_formal_trading_authority"] is False
