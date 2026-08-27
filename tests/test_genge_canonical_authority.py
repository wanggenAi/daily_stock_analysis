from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.canonical_authority import (
    AUTHORITY_CONTRACT_VERSION,
    finalize_canonical,
    validate_authority,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _snapshot(*, source_kind: str = "every-industry") -> dict:
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
        source_run_id="123",
        upstream_run_id="456",
        generated_at="2026-08-27T03:00:00+00:00",
        research_as_of="2026-08-27T03:00:00+00:00",
        source_hashes={
            "discovery_csv": "a" * 64,
            "deep_review_csv": "b" * 64,
            "production_csv": "c" * 64,
        },
    )


def test_finalize_canonical_publishes_one_truth_for_both_consumers(tmp_path: Path) -> None:
    snapshot = _snapshot()
    source = tmp_path / "latest.json"
    source.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    outputs = finalize_canonical(
        source,
        tmp_path / "authorized",
        expected_source_run_id="123",
        source_workflow="GenGe V3.1.1 Every-Industry Research",
        expected_source_kind="every-industry",
        source_head_sha="deadbeef",
        finalizer_run_id="789",
        finalizer_code_sha="cafebabe",
        finalized_at="2026-08-27T03:30:00+00:00",
    )

    authority = json.loads(outputs["authority"].read_text(encoding="utf-8"))
    hourly = json.loads(outputs["hourly"].read_text(encoding="utf-8"))
    daily = json.loads(outputs["daily"].read_text(encoding="utf-8"))
    copied = json.loads(outputs["canonical"].read_text(encoding="utf-8"))

    assert authority["contract_version"] == AUTHORITY_CONTRACT_VERSION
    assert authority["authorized"] is True
    assert authority["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert hourly["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert daily["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert copied == snapshot
    assert authority["consumer_contract"]["one_formal_truth_per_production_cycle"] is True
    assert authority["consumer_contract"]["canonical_is_only_formal_decision_truth"] is True
    assert authority["consumer_contract"]["consumer_may_recompute_formal_action"] is False
    assert authority["consumer_contract"]["overlay_may_overwrite_formal_action"] is False
    validate_authority(authority, copied, hourly_view=hourly, daily_view=daily)


def test_finalize_canonical_accepts_authoritative_premarket_one_shot(tmp_path: Path) -> None:
    snapshot = _snapshot(source_kind="GenGe All-A V3.1.1 One Shot")
    source = tmp_path / "latest.json"
    source.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    outputs = finalize_canonical(
        source,
        tmp_path / "authorized",
        expected_source_run_id="123",
        source_workflow="GenGe All-A V3.1.1 One Shot",
        expected_source_kind="GenGe All-A V3.1.1 One Shot",
    )
    authority = json.loads(outputs["authority"].read_text(encoding="utf-8"))
    assert authority["authorized"] is True
    assert authority["canonical_source_kind"] == "GenGe All-A V3.1.1 One Shot"


def test_finalize_canonical_rejects_wrong_source_run(tmp_path: Path) -> None:
    source = tmp_path / "latest.json"
    source.write_text(json.dumps(_snapshot(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="source run mismatch"):
        finalize_canonical(
            source,
            tmp_path / "authorized",
            expected_source_run_id="999",
            source_workflow="GenGe V3.1.1 Every-Industry Research",
        )


def test_finalize_canonical_rejects_non_authoritative_source_kind(tmp_path: Path) -> None:
    snapshot = _snapshot(source_kind="untrusted-research-workflow")
    source = tmp_path / "latest.json"
    source.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="rejects source_kind"):
        finalize_canonical(
            source,
            tmp_path / "authorized",
            expected_source_run_id="123",
            source_workflow="Untrusted Research Workflow",
        )


def test_finalize_canonical_rejects_workflow_source_kind_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "latest.json"
    source.write_text(json.dumps(_snapshot(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="source kind mismatch"):
        finalize_canonical(
            source,
            tmp_path / "authorized",
            expected_source_run_id="123",
            source_workflow="GenGe All-A V3.1.1 One Shot",
            expected_source_kind="GenGe All-A V3.1.1 One Shot",
        )
