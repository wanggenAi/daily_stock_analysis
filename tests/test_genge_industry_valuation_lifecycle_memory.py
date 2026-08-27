from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    INVALIDATED,
    empty_state,
    write_state,
)
from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import (
    _read_candidate_state_codes,
)


def test_lifecycle_json_returns_active_and_inactive_codes(tmp_path: Path) -> None:
    state = empty_state()
    state["candidates"] = {
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
            "applied_evidence_ids": [],
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
            "applied_evidence_ids": [],
            "history": [],
        },
    }
    path = tmp_path / "candidate_lifecycle_state.json"
    write_state(path, state)

    active, inactive = _read_candidate_state_codes(path) or (set(), set())

    assert active == {"600312"}
    assert inactive == {"603658"}


def test_missing_lifecycle_json_allows_legacy_bootstrap_fallback(tmp_path: Path) -> None:
    assert _read_candidate_state_codes(tmp_path / "missing.json") is None


def test_existing_but_invalid_lifecycle_json_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "candidate_lifecycle_state.json"
    path.write_text(json.dumps({"contract_version": "WRONG"}), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate lifecycle contract version mismatch"):
        _read_candidate_state_codes(path)
