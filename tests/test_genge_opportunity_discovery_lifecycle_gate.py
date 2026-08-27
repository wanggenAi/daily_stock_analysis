from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_persistence import (
    persist_finalized_snapshot,
)
from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    empty_state,
    write_state,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)
from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import (
    _read_candidate_state_codes,
)


def _snapshot() -> dict:
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
        source_run_id="gate-100",
        upstream_run_id="gate-upstream-100",
        generated_at="2026-08-27T08:00:00+00:00",
        research_as_of="2026-08-27T08:00:00+00:00",
        source_hashes={
            "discovery_csv": "gate-d",
            "deep_review_csv": "gate-r",
            "production_csv": "gate-p",
        },
    )


def test_one_shot_gate_same_snapshot_is_lifecycle_idempotent(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    legacy = tmp_path / "V31_CANDIDATE_LEDGER.md"
    legacy.write_text(
        """## Active candidate ledger
### 600312 平高电气
- **seen_count:** 99
- **current tier:** WATCH / BUY_REVIEW
""",
        encoding="utf-8",
    )
    state_path = tmp_path / "candidate_lifecycle_state.json"
    projection = tmp_path / "ledger.md"

    first, first_events = persist_finalized_snapshot(
        snapshot_path=snapshot_path,
        state_path=state_path,
        projection_path=projection,
        legacy_ledger=legacy,
    )
    second, second_events = persist_finalized_snapshot(
        snapshot_path=snapshot_path,
        state_path=state_path,
        projection_path=projection,
        legacy_ledger=legacy,
    )

    assert first_events[0]["event"] == "RESEEN"
    assert first["candidates"]["600312"]["seen_count"] == 1
    assert first["candidates"]["600312"]["legacy_seen_count_imported"] == 99
    assert second_events == []
    assert second["candidates"]["600312"]["seen_count"] == 1


def test_one_shot_gate_lifecycle_json_is_recall_authority(tmp_path: Path) -> None:
    state = empty_state()
    state["candidates"] = {
        "600312": {
            "code": "600312",
            "stock_name": "平高电气",
            "lifecycle_state": ACTIVE,
            "research_tier": "WATCH",
            "seen_count": 1,
            "last_formal_action": "HOLD_REVIEW",
            "last_valuation_confidence": "MEDIUM",
            "last_seen_snapshot_id": "abc",
            "last_seen_source_run_id": "100",
            "last_event": "RESEEN",
            "last_event_at": "2026-08-27T08:00:00+00:00",
            "applied_evidence_ids": [],
            "history": [],
        }
    }
    path = tmp_path / "candidate_lifecycle_state.json"
    write_state(path, state)

    active, inactive = _read_candidate_state_codes(path) or (set(), set())

    assert active == {"600312"}
    assert inactive == set()


def test_one_shot_gate_invalid_existing_lifecycle_state_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "candidate_lifecycle_state.json"
    path.write_text(json.dumps({"contract_version": "WRONG"}), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate lifecycle contract version mismatch"):
        _read_candidate_state_codes(path)
