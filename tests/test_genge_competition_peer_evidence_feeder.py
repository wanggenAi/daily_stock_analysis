from src.strategies.genge_opportunity_discovery.competition_peer_evidence_feeder import peer_rows, to_events


def test_peer_rows_require_explicit_evidence_ref():
    rows = peer_rows({"mappings": [
        {"peer_code": "601899", "peer_name": "紫金矿业", "evidence_ref": "official"},
        {"peer_code": "600000", "peer_name": "ignored", "evidence_ref": ""},
    ]})
    assert rows == [{"code": "601899", "stock_name": "紫金矿业", "industry": "", "normalized_industry": ""}]


def test_peer_event_conversion_is_research_only_input_shape():
    events = to_events([{
        "code": "601899",
        "stock_name": "紫金矿业",
        "title": "监管措施公告",
        "source": "https://example.test/filing",
        "publish_date": "2026-08-28",
        "direction": "NEGATIVE",
        "event_severity": "HIGH",
        "evidence_status": "VERIFIED",
        "normalized_summary": "fixture",
    }])
    assert len(events) == 1
    assert events[0]["direction"] == "WEAKENING"
    assert events[0]["materiality"] == "HIGH"
    assert events[0]["evidence_type"] == "PEER_MATERIAL_EVENT"
    assert events[0]["sell_relevance"] == "RESEARCH_ONLY"
