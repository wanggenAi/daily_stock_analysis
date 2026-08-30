from src.era_radar.evidence import EvidenceRecord
from src.era_radar.pipeline import build_snapshot, render_markdown


def record(evidence_id, trend_id, family, source_key, **components):
    return EvidenceRecord(
        evidence_id=evidence_id,
        trend_id=trend_id,
        family=family,
        source_key=source_key,
        source_name=source_key,
        source_url=f"https://example.test/{source_key}",
        source_tier="OFFICIAL" if family in {"POLICY_CAPITAL", "REAL_DEMAND"} else "PRIMARY",
        observed_at="2026-08-29T00:00:00Z",
        published_at="2026-08-29T01:00:00Z",
        retrieved_at="2026-08-30T00:00:00Z",
        freshness="FRESH",
        direction=1,
        strength=0.9,
        quality=0.9,
        components={**components, "evidence_quality": 0.9},
    )


def fixture():
    return [
        record("a1", "grid", "REAL_DEMAND", "grid-demand", structural_demand=0.8, real_demand_confirmation=0.9),
        record("a2", "grid", "INDUSTRIAL_CAPITAL", "grid-capex", industrial_capex=0.9, investable_bottleneck_strength=0.7),
        record("a3", "grid", "POLICY_CAPITAL", "grid-plan", policy_commitment=0.8),
        record("b1", "compute_power", "REAL_DEMAND", "dc-load", structural_demand=0.9, real_demand_confirmation=0.7),
        record("b2", "compute_power", "TECHNOLOGY", "accelerators", technology_enablement=0.9, investable_bottleneck_strength=0.8),
        record("b3", "compute_power", "INDUSTRIAL_CAPITAL", "dc-capex", industrial_capex=0.8, profit_pool_quality=0.7),
    ]


def test_snapshot_is_order_independent_and_deterministic():
    records = fixture()
    left = build_snapshot(records, "2026-08-30T01:00:00Z")
    right = build_snapshot(list(reversed(records)), "2026-08-30T01:00:00Z")
    assert left.snapshot_id == right.snapshot_id
    assert left.to_dict() == right.to_dict()


def test_snapshot_has_no_formal_trading_authority():
    snapshot = build_snapshot(fixture(), "2026-08-30T01:00:00Z")
    assert snapshot.formal_trading_authority is False
    assert snapshot.no_auto_trade is True
    payload = snapshot.to_dict()
    serialized = str(payload)
    assert "BUY" not in serialized
    assert "SELL" not in serialized
    assert "REDUCE" not in serialized


def test_projection_ranks_trends_but_remains_research_only():
    snapshot = build_snapshot(fixture(), "2026-08-30T01:00:00Z")
    markdown = render_markdown(snapshot)
    assert "No Formal trading authority" in markdown
    assert "grid" in markdown
    assert "compute_power" in markdown
