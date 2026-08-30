import pytest

from src.era_radar.evidence import EvidenceRecord, normalize_for_scoring


def rec(**overrides):
    data = dict(
        evidence_id="e1",
        trend_id="grid_modernization",
        family="REAL_DEMAND",
        source_key="stats-series-1",
        source_name="Official statistics",
        source_url="https://example.test/series",
        source_tier="OFFICIAL",
        observed_at="2026-08-29T00:00:00Z",
        published_at="2026-08-29T08:00:00Z",
        retrieved_at="2026-08-30T00:00:00Z",
        freshness="FRESH",
        direction=1,
        strength=0.8,
        quality=0.9,
        components={"real_demand_confirmation": 0.9, "evidence_quality": 0.9},
    )
    data.update(overrides)
    return EvidenceRecord(**data)


def test_normalizes_valid_pit_evidence():
    result = normalize_for_scoring([rec()], "2026-08-30T01:00:00Z")
    assert list(result) == ["grid_modernization"]
    assert result["grid_modernization"][0].family == "REAL_DEMAND"


def test_future_publication_fails_closed():
    with pytest.raises(ValueError, match="PIT violation"):
        normalize_for_scoring([rec(published_at="2026-08-31T00:00:00Z")], "2026-08-30T01:00:00Z")


def test_future_retrieval_fails_closed():
    with pytest.raises(ValueError, match="PIT violation"):
        normalize_for_scoring([rec(retrieved_at="2026-08-30T02:00:00Z")], "2026-08-30T01:00:00Z")


def test_stale_evidence_is_rejected():
    with pytest.raises(ValueError, match="stale evidence"):
        normalize_for_scoring([rec(freshness="STALE")], "2026-08-30T01:00:00Z")


def test_missing_source_identity_is_rejected():
    with pytest.raises(ValueError, match="source identity"):
        normalize_for_scoring([rec(source_url="")], "2026-08-30T01:00:00Z")


def test_duplicate_evidence_id_is_rejected():
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        normalize_for_scoring([rec(), rec()], "2026-08-30T01:00:00Z")
