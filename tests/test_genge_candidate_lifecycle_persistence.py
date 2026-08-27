from __future__ import annotations

import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_persistence import (
    bootstrap_state_from_legacy_ledger,
    persist_finalized_snapshot,
    render_ledger_projection,
)
from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    INVALIDATED,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _snapshot(run_id: str = "100", generated_at: str = "2026-08-27T08:00:00+00:00") -> dict:
    deep = [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "industry": "电网设备",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "v31_candidate_class": "WATCH / BUY_REVIEW",
            "valuation_confidence": "MEDIUM",
            "latest_trade_date": "2026-08-27",
        }
    ]
    production = [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
            "production_model_version": PRODUCTION_VERSION,
            "v311_production_bridge": PRODUCTION_BRIDGE,
            "strict_pit_refresh_applied": "True",
            "upstream_policy_reused": "False",
            "no_auto_trade": "True",
            "current_price": "20.43",
            "decision_date": "2026-08-27",
            "price_date": "2026-08-27",
            "valuation_confidence": "MEDIUM",
        }
    ]
    return build_snapshot(
        [],
        deep,
        production,
        source_kind="every-industry",
        source_run_id=run_id,
        upstream_run_id=f"upstream:{run_id}",
        generated_at=generated_at,
        research_as_of=generated_at,
        source_hashes={
            "discovery_csv": f"{run_id}-d",
            "deep_review_csv": f"{run_id}-r",
            "production_csv": f"{run_id}-p",
        },
    )


def test_legacy_bootstrap_imports_membership_and_seen_count(tmp_path: Path) -> None:
    ledger = tmp_path / "V31_CANDIDATE_LEDGER.md"
    ledger.write_text(
        """# V31_CANDIDATE_LEDGER

## Active candidate ledger

### 600312 平高电气
- **first_seen:** legacy first
- **last_seen:** legacy last
- **seen_count:** 7 durable observations
- **current tier:** WATCH / BUY_REVIEW
- **valuation confidence:** MEDIUM
- **GenGe V3.1.1 production action:** HOLD_REVIEW

## INVALIDATED candidate ledger

### 603658 安图生物
- **seen_count:** 24
- **current tier:** WAIT / DOWNGRADED
""",
        encoding="utf-8",
    )

    state = bootstrap_state_from_legacy_ledger(ledger)

    assert state["bootstrap_source"] == "LEGACY_MARKDOWN"
    assert state["candidates"]["600312"]["lifecycle_state"] == ACTIVE
    assert state["candidates"]["600312"]["seen_count"] == 7
    assert state["candidates"]["600312"]["research_tier"] == "WATCH / BUY_REVIEW"
    assert state["candidates"]["600312"]["last_formal_action"] == "HOLD_REVIEW"
    assert state["candidates"]["603658"]["lifecycle_state"] == INVALIDATED
    assert state["candidates"]["603658"]["seen_count"] == 24


def test_persistence_bootstraps_once_then_same_snapshot_is_noop(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    legacy = tmp_path / "V31_CANDIDATE_LEDGER.md"
    legacy.write_text(
        """## Active candidate ledger
### 600312 平高电气
- **seen_count:** 2
- **current tier:** WATCH / BUY_REVIEW
""",
        encoding="utf-8",
    )
    state_path = tmp_path / "candidate_lifecycle_state.json"
    projection = tmp_path / "projection.md"
    events = tmp_path / "events.json"
    summary = tmp_path / "summary.json"

    first_state, first_events = persist_finalized_snapshot(
        snapshot_path=snapshot_path,
        state_path=state_path,
        projection_path=projection,
        legacy_ledger=legacy,
        events_path=events,
        summary_path=summary,
    )
    second_state, second_events = persist_finalized_snapshot(
        snapshot_path=snapshot_path,
        state_path=state_path,
        projection_path=projection,
        legacy_ledger=legacy,
        events_path=events,
        summary_path=summary,
    )

    assert len(first_events) == 1
    assert first_events[0]["event"] == "RESEEN"
    assert first_state["candidates"]["600312"]["seen_count"] == 3
    assert second_events == []
    assert second_state["candidates"]["600312"]["seen_count"] == 3
    assert second_state["latest_applied_snapshot_id"] == snapshot["snapshot_id"]
    rendered = projection.read_text(encoding="utf-8")
    assert "GENERATED FILE — DO NOT EDIT" in rendered
    assert "Machine source of truth" in rendered
    assert "600312" in rendered
    summary_payload = json.loads(summary.read_text(encoding="utf-8"))
    assert summary_payload["canonical_snapshot_id"] == snapshot["snapshot_id"]
    assert summary_payload["discovery_is_filtered_by_lifecycle"] is False


def test_projection_separates_active_and_inactive_candidates() -> None:
    state = {
        "contract_version": "GEN_GE_V31_CANDIDATE_LIFECYCLE_V1",
        "latest_applied_snapshot_id": "abc",
        "latest_research_as_of": "2026-08-27T08:00:00+00:00",
        "applied_snapshot_ids": ["abc"],
        "event_count": 2,
        "no_auto_trade": True,
        "discovery_is_filtered_by_lifecycle": False,
        "candidates": {
            "600312": {
                "code": "600312",
                "stock_name": "平高电气",
                "lifecycle_state": ACTIVE,
                "research_tier": "WATCH",
                "seen_count": 2,
                "last_formal_action": "HOLD_REVIEW",
                "last_valuation_confidence": "MEDIUM",
                "last_seen_snapshot_id": "abc",
                "last_seen_source_run_id": "100",
                "last_event": "RESEEN",
                "last_event_at": "2026-08-27T08:00:00+00:00",
                "history": [],
            },
            "603658": {
                "code": "603658",
                "stock_name": "安图生物",
                "lifecycle_state": INVALIDATED,
                "research_tier": "WAIT / DOWNGRADED",
                "seen_count": 24,
                "last_formal_action": "HOLD_REVIEW",
                "last_valuation_confidence": "INVALID",
                "last_seen_snapshot_id": "abc",
                "last_seen_source_run_id": "100",
                "last_event": "INVALIDATED",
                "last_event_at": "2026-08-27T08:00:00+00:00",
                "history": [],
            },
        },
    }

    text = render_ledger_projection(state)

    assert "## Active candidate ledger" in text
    assert "## Archived / INVALIDATED candidate ledger" in text
    assert "600312" in text
    assert "603658" in text
    assert "discovery_is_filtered_by_lifecycle: `false`" in text
