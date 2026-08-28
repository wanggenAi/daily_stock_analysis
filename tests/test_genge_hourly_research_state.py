import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.evidence_event_store import append_events
from src.strategies.genge_opportunity_discovery.hourly_research_state import build_state


def _price_overlay():
    return {
        "generated_at": "2026-08-28T06:00:00+00:00",
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "rows": [
            {
                "code": "600312",
                "name": "平高电气",
                "scope": "DEEP_REVIEW_FOCUS",
                "formal_action": "WAIT",
                "latest_price": 19.8,
                "validated_value_anchor": 25.5,
                "price_to_value": 0.776471,
                "margin_of_safety": 0.223529,
                "price_evidence_status": "PRICE_GATE_PASS_RESEARCH_ONLY",
                "deep_review_priority": "RAISE",
                "hourly_research_conclusion": "PRICE_ATTRACTIVE_RESEARCH_LEAD",
            }
        ],
    }


def test_new_negative_evidence_raises_reunderwrite_without_formal_action(tmp_path: Path):
    evidence_root = tmp_path / "evidence"
    append_events(evidence_root, [{"code": "600312", "observed_at": "2026-08-28T05:30:00Z", "published_at": "2026-08-28T05:20:00Z", "source": "fixture", "source_ref": "fixture://bad", "evidence_type": "REGULATORY_OR_POLICY", "title": "立案调查公告", "materiality": "HIGH", "direction": "WEAKENING", "thesis_link": "UNASSESSED"}])
    state = build_state(_price_overlay(), evidence_root, tmp_path / "prices")
    row = state["rows"][0]
    assert row["formal_action"] == "WAIT"
    assert row["formal_action_recomputed"] is False
    assert row["evidence_may_overwrite_formal_action"] is False
    assert row["thesis_status"] == "REUNDERWRITE_REQUIRED"
    assert row["hourly_research_conclusion"] == "NEW_EVIDENCE_REUNDERWRITE_LEAD"
    assert row["deep_review_priority"] == "RAISE"


def test_attractive_plus_strengthening_evidence_raises_deep_review_only(tmp_path: Path):
    evidence_root = tmp_path / "evidence"
    append_events(evidence_root, [{"code": "600312", "observed_at": "2026-08-28T05:30:00Z", "published_at": "2026-08-28T05:20:00Z", "source": "fixture", "source_ref": "fixture://good", "evidence_type": "ORDER_OR_CONTRACT", "title": "重大合同公告", "materiality": "MEDIUM", "direction": "STRENGTHENING", "thesis_link": "demand"}])
    state = build_state(_price_overlay(), evidence_root, tmp_path / "prices")
    row = state["rows"][0]
    assert row["thesis_status"] == "STRENGTHENING_RESEARCH_SIGNAL"
    assert row["hourly_research_conclusion"] == "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD"
    assert row["deep_review_priority"] == "RAISE"
    assert row["formal_action"] == "WAIT"
    assert row["formal_action_recomputed"] is False


def test_low_materiality_weakening_is_visible_but_does_not_escalate_thesis(tmp_path: Path):
    evidence_root = tmp_path / "evidence"
    append_events(evidence_root, [{"code": "600312", "observed_at": "2026-08-28T05:30:00Z", "published_at": "2026-08-28T05:20:00Z", "source": "commodity_fixture", "source_ref": "fixture://commodity", "evidence_type": "COMMODITY_PRICE", "title": "ordinary benchmark decline", "materiality": "LOW", "direction": "WEAKENING", "thesis_link": "commodity:fixture"}])
    state = build_state(_price_overlay(), evidence_root, tmp_path / "prices")
    row = state["rows"][0]
    assert row["weakening_evidence_count_72h"] == 1
    assert row["material_weakening_evidence_count_72h"] == 0
    assert row["thesis_status"] == "LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY"
    assert row["hourly_research_conclusion"] == "PRICE_ATTRACTIVE_RESEARCH_LEAD"
    assert row["formal_action"] == "WAIT"


def test_price_history_counts_attractive_observations(tmp_path: Path):
    price_root = tmp_path / "prices"
    day = price_root / "2026-08-28"
    day.mkdir(parents=True)
    for hour in ("13", "14"):
        payload = _price_overlay()
        payload["generated_at"] = f"2026-08-28T{int(hour)-8:02d}:00:00+00:00"
        (day / f"{hour}.json").write_text(json.dumps(payload), encoding="utf-8")
    state = build_state(_price_overlay(), tmp_path / "evidence", price_root)
    row = state["rows"][0]
    assert row["price_history_observation_count"] == 2
    assert row["price_attractive_observation_count"] == 2
    assert row["price_attractive_consecutive_observations"] == 2
    assert row["price_attractive_distinct_days"] == 1
    assert state["formal_action_recomputed"] is False
