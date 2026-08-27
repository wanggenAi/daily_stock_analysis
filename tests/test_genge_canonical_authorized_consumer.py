from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.canonical_authority import finalize_canonical
from src.strategies.genge_opportunity_discovery.canonical_authorized_consumer import (
    load_authorized_view,
)
from src.strategies.genge_opportunity_discovery.canonical_operating_view import (
    DAILY_SETTLEMENT,
    HOURLY_MONITOR,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _snapshot(*, source_run_id: str = "123", source_kind: str = "every-industry") -> dict:
    discovery = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "industry": "银行",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "quant_score": "88",
            "latest_trade_date": "2026-08-27",
        }
    ]
    deep_review = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "industry": "银行",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "latest_trade_date": "2026-08-27",
        }
    ]
    production = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
            "production_model_version": PRODUCTION_VERSION,
            "v311_production_bridge": PRODUCTION_BRIDGE,
            "strict_pit_refresh_applied": "True",
            "upstream_policy_reused": "False",
            "no_auto_trade": "True",
            "current_price": "10.00",
            "decision_date": "2026-08-27",
            "price_date": "2026-08-27",
        }
    ]
    return build_snapshot(
        discovery,
        deep_review,
        production,
        source_kind=source_kind,
        source_run_id=source_run_id,
        upstream_run_id=f"upstream:{source_run_id}",
        generated_at="2026-08-27T03:00:00+00:00",
        research_as_of="2026-08-27T03:00:00+00:00",
        source_hashes={
            "discovery_csv": "a" * 64,
            "deep_review_csv": "b" * 64,
            "production_csv": "c" * 64,
        },
    )


def _finalize(tmp_path: Path, *, source_run_id: str = "123") -> Path:
    snapshot = _snapshot(source_run_id=source_run_id)
    source = tmp_path / f"snapshot-{source_run_id}.json"
    source.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    root = tmp_path / f"authorized-{source_run_id}"
    finalize_canonical(
        source,
        root,
        expected_source_run_id=source_run_id,
        source_workflow="GenGe V3.1.1 Every-Industry Research",
        expected_source_kind="every-industry",
        source_head_sha="deadbeef",
        finalizer_run_id=f"finalizer:{source_run_id}",
        finalizer_code_sha="cafebabe",
        finalized_at="2026-08-27T03:30:00+00:00",
    )
    return root


def test_hourly_and_daily_load_from_same_finalized_truth(tmp_path: Path) -> None:
    root = _finalize(tmp_path)

    hourly = load_authorized_view(root, mode=HOURLY_MONITOR)
    daily = load_authorized_view(root, mode=DAILY_SETTLEMENT)

    assert hourly["canonical_snapshot_id"] == daily["canonical_snapshot_id"]
    assert hourly["canonical_source_run_id"] == daily["canonical_source_run_id"] == "123"
    assert hourly["source_workflow"] == "GenGe V3.1.1 Every-Industry Research"
    assert hourly["view"]["mode"] == HOURLY_MONITOR
    assert daily["view"]["mode"] == DAILY_SETTLEMENT
    assert hourly["view"]["consumer_contract"]["decision_recalculation_allowed"] is False
    assert daily["view"]["consumer_contract"]["decision_mutation_allowed"] is False


def test_consumer_rejects_canonical_changed_after_finalization(tmp_path: Path) -> None:
    root = _finalize(tmp_path)
    snapshot_path = root / "canonical_snapshot" / "latest.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["research_as_of"] = "2026-08-27T04:00:00+00:00"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        load_authorized_view(root, mode=HOURLY_MONITOR)


def test_consumer_rejects_view_from_different_snapshot(tmp_path: Path) -> None:
    root_a = _finalize(tmp_path, source_run_id="123")
    root_b = _finalize(tmp_path, source_run_id="124")
    daily_a = root_a / "operating_views" / "daily.json"
    daily_b = root_b / "operating_views" / "daily.json"
    daily_a.write_text(daily_b.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="consumer snapshot mismatch|operating view snapshot mismatch"):
        load_authorized_view(root_a, mode=DAILY_SETTLEMENT)


def test_consumer_rejects_unrecognized_producer_workflow(tmp_path: Path) -> None:
    root = _finalize(tmp_path)
    authority_path = root / "production_authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["source_workflow"] = "Legacy Production"
    authority_path.write_text(json.dumps(authority, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unauthorized canonical producer workflow"):
        load_authorized_view(root, mode=HOURLY_MONITOR)


def test_consumer_rejects_missing_mode_view(tmp_path: Path) -> None:
    root = _finalize(tmp_path)
    (root / "operating_views" / "hourly.json").unlink()

    with pytest.raises(ValueError, match="missing required file"):
        load_authorized_view(root, mode=HOURLY_MONITOR)
