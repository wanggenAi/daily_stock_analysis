"""Regression tests for the shared V3.1.1 hourly/daily snapshot contract."""

import pytest

from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    build_snapshot,
    validate_snapshot,
)


def test_discovery_is_not_capped_by_deep_review_or_ledger() -> None:
    discovery = [
        {"code": "600001", "quant_rank": "1", "quant_score": "90", "latest_trade_date": "2026-08-26"},
        {"code": "600002", "quant_rank": "2", "quant_score": "89", "latest_trade_date": "2026-08-26"},
        {"code": "600003", "quant_rank": "3", "quant_score": "88", "latest_trade_date": "2026-08-26"},
        # Research-only board must not enter the user's executable discovery pool.
        {"code": "688001", "quant_rank": "4", "quant_score": "99", "latest_trade_date": "2026-08-26"},
    ]
    deep_review = [
        {
            "code": "600003",
            "v31_review_rank": "1",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
        }
    ]
    production = [
        {
            "code": "600003",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
        }
    ]

    snapshot = build_snapshot(
        discovery,
        deep_review,
        production,
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )

    assert snapshot["discovery"]["execution_eligible_count"] == 3
    assert [row["code"] for row in snapshot["discovery"]["rows"]] == [
        "600001",
        "600002",
        "600003",
    ]
    assert snapshot["deep_review"]["execution_eligible_count"] == 1
    assert snapshot["architecture_contract"]["ledger_may_filter_discovery"] is False
    assert snapshot["architecture_contract"]["candidate_ledger_is_downstream_memory_only"] is True


def test_all_sections_share_snapshot_identity_and_run_changes_identity() -> None:
    kwargs = {
        "discovery_rows": [{"code": "600001", "latest_trade_date": "2026-08-26"}],
        "deep_review_rows": [],
        "production_rows": [],
        "source_kind": "test",
        "generated_at": "2026-08-27T00:00:00+00:00",
    }
    first = build_snapshot(source_run_id="1", **kwargs)
    second = build_snapshot(source_run_id="2", **kwargs)

    assert first["snapshot_id"] != second["snapshot_id"]
    assert {
        first[section]["snapshot_id"]
        for section in ("discovery", "deep_review", "production")
    } == {first["snapshot_id"]}
    validate_snapshot(first, expected_source_run_id="1")


def test_mixed_section_snapshot_fails_closed() -> None:
    snapshot = build_snapshot(
        [{"code": "600001"}],
        [],
        [],
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )
    snapshot["production"]["snapshot_id"] = "old-snapshot"

    with pytest.raises(ValueError, match="section mismatch"):
        validate_snapshot(snapshot)


def test_sync_contract_does_not_change_formal_buy_or_freshness_rules() -> None:
    snapshot = build_snapshot(
        [],
        [],
        [],
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )

    assert snapshot["architecture_contract"]["formal_buy_thresholds_changed"] is False
    assert snapshot["freshness_contract"]["stale_or_unverified_price_may_promote_buy_add"] is False
