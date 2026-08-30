import json
from pathlib import Path

import pytest

from src.era_radar.collectors import JsonObservationCollector, RawObservation, collect_all, normalize_observation
from src.era_radar.discovery import discover_hypotheses
from src.era_radar.persistence import load_lifecycle, persist_snapshot
from src.era_radar.pipeline import build_snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "era_radar_observations.json"
AS_OF = "2026-08-30T01:00:00Z"


def test_collector_to_discovery_to_persistence_is_end_to_end(tmp_path):
    records = collect_all([JsonObservationCollector(FIXTURE)], AS_OF)
    hypotheses = discover_hypotheses(records)
    assert {item.trend_id for item in hypotheses} == {
        "compute_power_infrastructure",
        "consumer_fad_without_fundamentals",
        "demographic_longevity",
        "grid_modernization",
    }
    priorities = {item.trend_id: item.research_priority for item in hypotheses}
    assert priorities["consumer_fad_without_fundamentals"] == "WATCH"
    assert priorities["grid_modernization"] == "NORMAL"

    snapshot = build_snapshot(records, AS_OF)
    result = persist_snapshot(snapshot, tmp_path, records)
    assert result["status"] == "PERSISTED"
    assert json.loads((tmp_path / "latest.json").read_text())["formal_trading_authority"] is False
    evidence = json.loads((tmp_path / "evidence" / f"{snapshot.snapshot_id}.json").read_text())
    assert evidence["evidence_count"] == len(records)
    assert evidence["formal_trading_authority"] is False
    assert {row["trend_id"] for row in evidence["records"]} == {item.trend_id for item in snapshot.trends}
    assert (tmp_path / "ERA_CAPITAL_TREND_RADAR.md").exists()
    state = load_lifecycle(tmp_path / "trend_lifecycle_state.json")
    assert set(state) == {item.trend_id for item in snapshot.trends}

    second = persist_snapshot(snapshot, tmp_path, records)
    assert second["status"] == "ALREADY_PERSISTED"
    assert all(item["event"] == "NOOP" for item in second["events"])


def test_unregistered_source_fails_closed():
    observation = RawObservation(
        evidence_id="x",
        topic_keys=("x",),
        family="REAL_DEMAND",
        source_id="random_blog",
        source_key="x",
        source_name="x",
        source_url="https://example.test/x",
        observed_at="2026-08-29T00:00:00Z",
        published_at="2026-08-29T00:00:00Z",
        retrieved_at="2026-08-30T00:00:00Z",
        freshness="FRESH",
        direction=1,
        strength=1,
        quality=1,
        components={"real_demand_confirmation": 1},
    )
    with pytest.raises(ValueError, match="unregistered source_id"):
        normalize_observation(observation)


def test_financial_hype_does_not_become_high_priority():
    records = collect_all([JsonObservationCollector(FIXTURE)], AS_OF)
    hypothesis = next(item for item in discover_hypotheses(records) if item.trend_id == "consumer_fad_without_fundamentals")
    snapshot = build_snapshot(records, AS_OF)
    trend = next(item for item in snapshot.trends if item.trend_id == hypothesis.trend_id)
    assert hypothesis.research_priority == "WATCH"
    assert trend.lifecycle != "CONFIRMED"
    assert trend.confidence_score < 40


def test_persistence_rejects_older_snapshot(tmp_path):
    records = collect_all([JsonObservationCollector(FIXTURE)], AS_OF)
    newer = build_snapshot(records, AS_OF)
    persist_snapshot(newer, tmp_path, records)
    older = build_snapshot(records, "2026-08-30T00:30:00Z")
    with pytest.raises(ValueError, match="out-of-order"):
        persist_snapshot(older, tmp_path, records)
