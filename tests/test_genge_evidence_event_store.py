import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.evidence_event_store import (
    append_events,
    normalize_event,
    recent_for_code,
)


def _event(**overrides):
    base = {
        "code": "600406",
        "name": "国电南瑞",
        "observed_at": "2026-08-28T06:00:00Z",
        "published_at": "2026-08-28T05:00:00Z",
        "source": "fixture",
        "source_ref": "fixture://600406/1",
        "evidence_type": "ORDER_OR_CONTRACT",
        "title": "重大合同公告",
        "summary": "fixture",
        "materiality": "MEDIUM",
        "direction": "STRENGTHENING",
        "thesis_link": "grid demand",
    }
    base.update(overrides)
    return base


def test_normalization_is_research_only():
    event = normalize_event(_event())
    assert event["code"] == "600406"
    assert event["formal_action_eligible"] is False
    assert event["formal_action_recomputed"] is False
    assert event["no_auto_trade"] is True
    assert event["evidence_id"].startswith("ev_")


def test_append_is_idempotent_and_builds_index(tmp_path: Path):
    root = tmp_path / "events"
    result1 = append_events(root, [_event()])
    result2 = append_events(root, [_event()])
    assert result1["accepted"] == 1
    assert result2["accepted"] == 0
    assert result2["duplicates"] == 1
    rows = recent_for_code(root, "600406")
    assert len(rows) == 1
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert index["event_count"] == 1
    assert index["formal_action_eligible"] is False
    assert index["no_auto_trade"] is True


def test_invalid_direction_fails_safe_to_unknown():
    event = normalize_event(_event(direction="BUY_NOW", materiality="CERTAIN"))
    assert event["direction"] == "UNKNOWN"
    assert event["materiality"] == "UNKNOWN"
