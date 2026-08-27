from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.canonical_operating_view import (
    DAILY_SETTLEMENT,
    HOURLY_MONITOR,
    build_operating_view,
    write_operating_views,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import build_snapshot


def _snapshot() -> dict:
    discovery = [
        {
            "code": "600001",
            "stock_name": "Candidate A",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "master_research_rank": "1",
            "latest_trade_date": "2026-08-26",
        },
        {
            "code": "000002",
            "stock_name": "Candidate B",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "master_research_rank": "2",
            "latest_trade_date": "2026-08-26",
        },
    ]
    deep_review = [
        {
            "code": "600001",
            "stock_name": "Candidate A",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "latest_trade_date": "2026-08-26",
        }
    ]
    production = [
        {
            "code": "600001",
            "stock_name": "Candidate A",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
            "valuation_confidence": "INVALID",
        },
        {
            "code": "600406",
            "stock_name": "Holding A",
            "decision_scope": "HOLDING",
            "production_action": "HOLD_REVIEW",
            "valuation_confidence": "INVALID",
            "confirmed_quantity": "200",
        },
    ]
    return build_snapshot(
        discovery,
        deep_review,
        production,
        source_kind="unit-test",
        source_run_id="123",
        upstream_run_id="self:123",
        generated_at="2026-08-27T02:00:00+00:00",
    )


def test_hourly_view_uses_same_truth_without_recomputing_actions() -> None:
    snapshot = _snapshot()
    view = build_operating_view(snapshot, mode=HOURLY_MONITOR)

    assert view["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert view["job_contract"]["responsibility"] == "INCREMENTAL_MONITORING"
    assert view["job_contract"]["full_market_reunderwrite"] is False
    assert view["consumer_contract"]["decision_recalculation_allowed"] is False
    assert view["consumer_contract"]["decision_mutation_allowed"] is False
    assert view["consumer_contract"]["formal_action_change_requires_new_validated_canonical_snapshot"] is True
    assert [row["code"] for row in view["holding_decisions"]] == ["600406"]
    assert view["focus_candidates"][0]["code"] == "600001"
    assert view["focus_candidates"][0]["canonical_decision"]["action"] == "HOLD_REVIEW"


def test_daily_view_is_full_settlement_over_same_snapshot() -> None:
    snapshot = _snapshot()
    view = build_operating_view(snapshot, mode=DAILY_SETTLEMENT)

    assert view["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert view["job_contract"]["responsibility"] == "FULL_DAILY_SETTLEMENT"
    assert view["job_contract"]["full_market_reunderwrite"] is True
    assert view["job_contract"]["settle_candidate_lifecycle"] is True
    assert view["counts"] == {
        "discovery": 2,
        "deep_review": 1,
        "candidate_decisions": 1,
        "holding_decisions": 1,
    }
    assert view["candidate_decisions"][0]["action"] == "HOLD_REVIEW"


def test_operating_view_rejects_invalid_canonical_snapshot() -> None:
    snapshot = _snapshot()
    snapshot["production"]["snapshot_id"] = "mixed-run"
    with pytest.raises(ValueError, match="section mismatch"):
        build_operating_view(snapshot, mode=HOURLY_MONITOR)


def test_write_operating_views_publishes_hourly_and_daily(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "latest.json"
    snapshot_path.write_text(json.dumps(_snapshot(), ensure_ascii=False), encoding="utf-8")

    outputs = write_operating_views(snapshot_path, tmp_path / "views")

    assert outputs[HOURLY_MONITOR].exists()
    assert outputs[DAILY_SETTLEMENT].exists()
    hourly = json.loads(outputs[HOURLY_MONITOR].read_text(encoding="utf-8"))
    daily = json.loads(outputs[DAILY_SETTLEMENT].read_text(encoding="utf-8"))
    assert hourly["canonical_snapshot_id"] == daily["canonical_snapshot_id"]
