from copy import deepcopy

from src.era_radar.research_handoff_queue import build_handoff_queue


def _snapshot():
    return {
        "snapshot_id": "era-1",
        "research_as_of": "2026-09-08T01:00:00Z",
        "formal_trading_authority": False,
        "no_auto_trade": True,
        "trends": [
            {
                "trend_id": "electrification_infrastructure",
                "lifecycle": "CONFIRMED",
                "confidence_score": 76.0,
            }
        ],
    }


def _evidence():
    return [
        {
            "trend_id": "electrification_infrastructure",
            "source_tier": "HIGH_QUALITY_SECONDARY",
            "source_url": "https://api.worldbank.org/v2/example",
            "freshness": "FRESH",
        }
    ]


def _companies():
    return [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "industry": "电力设备",
            "source_type": "reviewed_research_mapping",
            "confidence": "HIGH",
        },
        {
            "code": "300001",
            "stock_name": "创业板样本",
            "industry": "电力设备",
            "source_type": "reviewed_research_mapping",
            "confidence": "HIGH",
        },
    ]


def _links():
    return {
        "authority": "RESEARCH_ONLY",
        "automatic_promotion_allowed": False,
        "unknown_mapping_is_match": False,
        "links": {"electrification_infrastructure": ["电力设备"]},
    }


def test_confirmed_trend_maps_only_reviewed_mainboard_research_candidate():
    payload = build_handoff_queue(_snapshot(), _evidence(), _companies(), _links())
    assert payload["queue_count"] == 1
    assert payload["trigger_full_authority_research"] is True
    assert payload["formal_action_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["no_auto_trade"] is True
    row = payload["queue"][0]
    assert row["code"] == "600312"
    assert row["industry_link"] == "电力设备"
    assert row["authority"] == "RESEARCH_ONLY"


def test_unknown_or_unreviewed_mapping_never_becomes_candidate():
    links = _links()
    links["links"] = {"different_trend": ["电力设备"]}
    assert build_handoff_queue(_snapshot(), _evidence(), _companies(), links)["queue_count"] == 0

    companies = deepcopy(_companies())
    companies[0]["confidence"] = "MEDIUM"
    assert build_handoff_queue(_snapshot(), _evidence(), companies, _links())["queue_count"] == 0


def test_insufficient_or_untrusted_trend_evidence_fails_closed():
    snapshot = _snapshot()
    snapshot["trends"][0]["confidence_score"] = 57.99
    assert build_handoff_queue(snapshot, _evidence(), _companies(), _links())["queue_count"] == 0

    evidence = _evidence()
    evidence[0]["freshness"] = "UNKNOWN"
    assert build_handoff_queue(_snapshot(), evidence, _companies(), _links())["queue_count"] == 0

    evidence = _evidence()
    evidence[0]["source_tier"] = "SECONDARY"
    assert build_handoff_queue(_snapshot(), evidence, _companies(), _links())["queue_count"] == 0


def test_handoff_diagnostics_explain_why_zero_queue_without_relaxing_rules():
    snapshot = _snapshot()
    snapshot["trends"][0]["lifecycle"] = "EMERGING"
    snapshot["trends"][0]["confidence_score"] = 33.69
    links = _links()
    links["links"] = {}

    payload = build_handoff_queue(snapshot, _evidence(), _companies(), links)

    assert payload["queue_count"] == 0
    assert payload["trigger_full_authority_research"] is False
    assert payload["handoff_ready_trend_count"] == 0
    assert payload["blocked_trend_count"] == 1
    diagnostic = payload["trend_diagnostics"][0]
    assert diagnostic["trend_id"] == "electrification_infrastructure"
    assert diagnostic["handoff_ready"] is False
    assert diagnostic["minimum_confidence"] == 58.0
    assert diagnostic["blockers"] == [
        "LIFECYCLE_NOT_HANDOFF_READY",
        "CONFIDENCE_BELOW_58",
        "TREND_INDUSTRY_LINK_MISSING",
    ]


def test_handoff_diagnostics_surface_provenance_and_mapping_gaps():
    evidence = _evidence()
    evidence[0]["source_tier"] = "SECONDARY"
    companies = deepcopy(_companies())
    companies[0]["industry"] = "银行"

    payload = build_handoff_queue(_snapshot(), evidence, companies, _links())

    assert payload["queue_count"] == 0
    diagnostic = payload["trend_diagnostics"][0]
    assert diagnostic["provenance_ok"] is False
    assert diagnostic["freshness_ok"] is True
    assert diagnostic["reviewed_company_match_count"] == 0
    assert "PROVENANCE_NOT_TRUSTED" in diagnostic["blockers"]
    assert "REVIEWED_COMPANY_MAPPING_MISSING" in diagnostic["blockers"]


def test_successful_handoff_has_ready_diagnostic_and_does_not_change_authority():
    payload = build_handoff_queue(_snapshot(), _evidence(), _companies(), _links())

    assert payload["queue_count"] == 1
    assert payload["handoff_ready_trend_count"] == 1
    diagnostic = payload["trend_diagnostics"][0]
    assert diagnostic["handoff_ready"] is True
    assert diagnostic["blockers"] == []
    assert diagnostic["handoff_count"] == 1
    assert payload["formal_action_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["no_auto_trade"] is True
