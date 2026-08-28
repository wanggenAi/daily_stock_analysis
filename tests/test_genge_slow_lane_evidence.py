from datetime import datetime, timezone
from pathlib import Path

from src.strategies.genge_opportunity_discovery.competition_change_collector import collect as collect_competition
from src.strategies.genge_opportunity_discovery.evidence_event_store import append_events
from src.strategies.genge_opportunity_discovery.regulatory_policy_evidence_collector import _direction, _industry_map


def test_competition_without_reviewed_peer_map_emits_no_events(tmp_path: Path):
    events, status = collect_competition(
        peer_map={"mappings": []},
        evidence_root=tmp_path / "evidence",
        now=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    assert events == []
    assert status["status"] == "CONNECTED_NO_EVIDENCE_BACKED_PEER_MAPPINGS"
    assert status["formal_action_eligible"] is False
    assert status["no_auto_trade"] is True


def test_competition_never_reprocesses_derived_competitive_events(tmp_path: Path):
    root = tmp_path / "evidence"
    append_events(root, [
        {
            "code": "601899",
            "observed_at": "2026-08-28T01:00:00Z",
            "published_at": "2026-08-28T01:00:00Z",
            "source": "peer_official_material_event",
            "source_ref": "fixture://primary",
            "evidence_type": "PEER_MATERIAL_EVENT",
            "title": "primary peer filing",
            "materiality": "HIGH",
            "direction": "WEAKENING",
        },
        {
            "code": "601899",
            "observed_at": "2026-08-28T01:10:00Z",
            "published_at": "2026-08-28T01:10:00Z",
            "source": "competition_peer_event_bridge",
            "source_ref": "fixture://derived",
            "evidence_type": "COMPETITIVE_CHANGE",
            "title": "derived competitive context",
            "materiality": "MEDIUM",
            "direction": "UNKNOWN",
        },
    ])
    events, status = collect_competition(
        peer_map={"mappings": [{
            "target_code": "603993",
            "target_name": "洛阳钼业",
            "peer_code": "601899",
            "peer_name": "紫金矿业",
            "evidence_ref": "fixture://peer-map",
        }]},
        evidence_root=root,
        now=datetime(2026, 8, 28, 2, 0, tzinfo=timezone.utc),
    )
    assert len(events) == 1
    assert "primary peer filing" in events[0]["title"]
    assert status["recursive_derived_events_skipped"] == 1
    assert status["derived_evidence_recursion_allowed"] is False


def test_policy_direction_is_conservative():
    assert _direction("关于促进某产业高质量发展的指导意见") == "STRENGTHENING"
    assert _direction("关于压减某行业落后产能的通知") == "WEAKENING"
    assert _direction("某行业管理办法") == "UNKNOWN"


def test_industry_mapping_requires_company_cycle_evidence(tmp_path: Path):
    path = tmp_path / "company.csv"
    path.write_text(
        "date,code,stock_name,industry,evidence_name\n"
        "2026-04-01,600001,A公司,有色,旧证据\n"
        "2026-06-01,600001,A公司,稀土,新证据\n"
        "2026-06-01,600002,B公司,面板,证据\n",
        encoding="utf-8",
    )
    result = _industry_map(path, {"600001"})
    assert result == {"600001": "稀土"}
