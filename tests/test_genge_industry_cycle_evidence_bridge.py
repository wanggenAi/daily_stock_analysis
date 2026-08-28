from datetime import date

from src.strategies.genge_opportunity_discovery.industry_cycle_evidence_bridge import collect


def test_bridge_maps_existing_company_industry_and_preserves_staleness():
    overlay = {"rows": [{"code": "002714", "name": "牧原股份", "formal_action": "HOLD"}]}
    company_rows = [{"date": "2026-06-06", "code": "002714", "industry": "猪肉"}]
    industry_rows = [
        {
            "date": "2026-06-24",
            "industry": "猪肉",
            "evidence_name": "猪粮比",
            "evidence_value": "约4.13",
            "evidence_direction": "NEGATIVE",
            "source": "https://example.invalid/nbs",
            "confidence": "HIGH",
            "note": "盈利压力",
        }
    ]
    events, status = collect(overlay, industry_rows, company_rows, today=date(2026, 8, 28))
    assert status["status"] == "CONNECTED"
    assert status["freshness_status"] == "CONNECTED_BUT_STALE"
    assert status["mapped_security_count"] == 1
    assert status["unmapped_security_count"] == 0
    assert len(events) == 1
    event = events[0]
    assert event["code"] == "002714"
    assert event["direction"] == "WEAKENING"
    assert event["materiality"] == "MEDIUM"
    assert event["evidence_type"] == "INDUSTRY_SUPPLY_DEMAND"


def test_bridge_does_not_invent_industry_mapping():
    overlay = {"rows": [{"code": "600406", "name": "国电南瑞"}]}
    events, status = collect(overlay, [], [], today=date(2026, 8, 28))
    assert events == []
    assert status["mapped_security_count"] == 0
    assert status["unmapped_security_count"] == 1
    assert status["formal_action_eligible"] is False
    assert status["no_auto_trade"] is True
