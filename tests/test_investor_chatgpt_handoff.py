"""H1 handoff must not turn dated advisory feeds into fresh trade authority."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.investor_chatgpt_handoff import (
    CONTRACT, build_handoff, render_markdown,
)
from src.strategies.genge_opportunity_discovery.generation_freshness import (
    evaluate_generation_freshness,
)


def save(root: Path, relative: str, value: dict) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def inputs(tmp_path: Path):
    dash = {
        "generated_at": "2026-09-28T00:00:00Z",
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "100",
        "latest_trade_date": "2026-09-24",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "formal_new_exposure_allowed": False,
        "freshness_contract": {
            "status": "STALE_UPSTREAM", "fresh": False,
            "canonical_source_run_id": "100",
            "canonical_latest_trade_date": "2026-09-24",
            "expected_min_trade_date": "2026-09-25",
        },
        "market": {"as_of_date": "2026-09-24", "status": "RED"},
        "holdings_reconciliation": {"status": "HOLDINGS_IN_SYNC", "in_sync": True},
        "stock_portfolio": {"rows": [
            {"code": "600406", "name": "test", "quantity": 200,
             "current_price": 22.27, "value_low": 12, "value_high": 26,
             "formal_action": "REDUCE_25", "action_authority": "FORMAL",
             "formal_action_currently_usable": True},
        ]},
        "fund_portfolio": {"status": "LATEST_HOLDINGS_NOT_PERSISTED", "rows": []},
        "decision_summary": {"research_buy_count": 1, "research_gap_count": 18},
        "terminal_opportunities": {"buy_now": [{"code": "999999"}], "wait_price": []},
        "terminal_research_snapshot": {"research_authority": "RESEARCH_ONLY"},
        "event_review": {"signal_digest": "old", "closure_status": "UNKNOWN"},
    }
    canonical = {"snapshot_id": "snap-1", "source_run_id": "100",
                 "latest_trade_date": "2026-09-24"}
    dashpath = save(tmp_path, "data/investor_decision_dashboard/latest.json", dash)
    canonicalpath = save(tmp_path, "incoming/canonical.json", canonical)
    return dash, canonical, dashpath, canonicalpath


def test_stale_old_session_is_honest_and_cannot_promote_research(tmp_path):
    _, _, _, canonical = inputs(tmp_path)
    m = build_handoff(tmp_path, canonical, finalizer_run_id="1001",
                      market_run_id="bad-id")
    assert m["contract_version"] == CONTRACT
    assert m["market_session_as_of"] == "2026-09-24"
    assert m["feeds"]["market_eod"]["status"] == "STALE_OR_UNVERIFIED"
    assert "STALE_OR_UNVERIFIED_MARKET_SESSION" in m["blocking_reasons"]
    assert m["formal_buy_now"] == [] and m["formal_wait_price"] == []
    assert m["research_audit"]["research_buy_count"] == 1
    assert m["holdings"][0]["recorded_formal_action"] == "REDUCE_25"
    assert m["holdings"][0]["executable_shares"] == 0
    assert m["feeds"]["broker_cash"]["amount_cny"] is None
    assert m["feeds"]["funds"]["status"] == "UNVERIFIED"
    assert m["production_provenance"]["finalizer_run_id"] == "1001"
    assert m["production_provenance"]["market_run_id"] is None
    assert m["no_auto_trade"] is True
    assert "NOT_AN_ORDER" not in render_markdown(m) or "executable shares 0" in render_markdown(m)


@pytest.mark.parametrize("changed", [
    {"snapshot_id": "other"}, {"source_run_id": "101"},
    {"latest_trade_date": "2026-09-25"},
])
def test_tampered_or_cross_epoch_canonical_fails_closed(tmp_path, changed):
    _, canonical, _, path = inputs(tmp_path)
    save(tmp_path, "incoming/canonical.json", {**canonical, **changed})
    with pytest.raises(ValueError, match="mismatch"):
        build_handoff(tmp_path, path)


@pytest.mark.parametrize("key,value", [
    ("formal_action_source", "RESEARCH"),
    ("formal_action_recomputed", True),
    ("no_auto_trade", False),
])
def test_report_must_preserve_frozen_formal_authority(tmp_path, key, value):
    d, _, path, canonical = inputs(tmp_path)
    d[key] = value
    path.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        build_handoff(tmp_path, canonical)


def test_rerender_does_not_create_new_semantic_epoch(tmp_path):
    d, _, path, canonical = inputs(tmp_path)
    first = build_handoff(tmp_path, canonical)
    d["generated_at"] = "2026-09-28T05:00:00Z"
    d["freshness_contract"]["evaluated_at"] = "2026-09-28T05:00:00Z"
    path.write_text(json.dumps(d), encoding="utf-8")
    second = build_handoff(tmp_path, canonical)
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["generated_at"] != second["generated_at"]
    assert first["source_files"]["dashboard"]["sha256"] != second["source_files"]["dashboard"]["sha256"]


def test_mismatched_center_manual_quote_and_unverified_event_remain_blocked(tmp_path):
    _, _, _, canonical = inputs(tmp_path)
    save(tmp_path, "data/decision_center/latest.json",
         {"canonical_snapshot_id": "old", "latest_trade_date": "2026-09-24"})
    save(tmp_path, "data/manual_execution_quotes/latest.json", {
        "canonical_snapshot_id": "old", "canonical_source_run_id": "99",
        "observed_at": "2026-09-28T09:35:00+08:00",
        "evidence_authority": "USER_CONFIRMED_BROKER_SCREENSHOT",
        "formal_trading_authority": False, "no_auto_trade": True,
    })
    m = build_handoff(tmp_path, canonical)
    assert m["lineage"]["center_matches_dashboard"] is False
    assert m["feeds"]["dated_manual_quotes"]["as_of"] is None
    assert m["feeds"]["executable_quotes"]["status"] == "UNVERIFIED"
    assert m["event_audit"]["verified_official_events"] == []
    assert m["feeds"]["official_issuer"]["status"] == "ORIGINAL_SOURCE_COVERAGE_NOT_PROVEN"


def test_even_fresh_upstream_cannot_establish_live_broker_or_exchange_calendar(tmp_path):
    d, _, path, canonical = inputs(tmp_path)
    d["freshness_contract"]["fresh"] = True
    d["freshness_contract"]["status"] = "OK"
    d["freshness_contract"]["formal_new_exposure_allowed"] = True
    d["formal_new_exposure_allowed"] = True
    path.write_text(json.dumps(d), encoding="utf-8")
    m = build_handoff(tmp_path, canonical)
    assert m["feeds"]["market_eod"]["status"] == "UPSTREAM_FRESH_CALENDAR_UNVERIFIED"
    assert not m["lineage"]["exchange_calendar_independently_verified"]
    assert m["formal_buy_now"] == []
    assert all(h["executable_shares"] == 0 for h in m["holdings"])


def test_bounded_sources_are_exact_local_files_without_invented_links(tmp_path):
    d, _, path, canonical = inputs(tmp_path)
    d["stock_portfolio"]["rows"] *= 25
    path.write_text(json.dumps(d), encoding="utf-8")
    m = build_handoff(tmp_path, canonical)
    assert len(m["holdings"]) == 16 and m["holdings_truncated"] == 9
    assert "sha256" in m["source_files"]["dashboard"]
    raw = path.read_bytes()
    git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert m["source_files"]["dashboard"]["immutable_git_blob_sha"] == git_blob
    assert m["source_files"]["dashboard"]["immutable_blob_url"].endswith("/" + git_blob)
    assert "pinned Git blob" in render_markdown(m)
    assert m["source_files"]["outcomes"]["status"] == "MISSING"
    assert "CURRENT_FUNDS.md" not in render_markdown(m)  # missing files are not linked
    assert "https://github.com/wanggenAi/daily_stock_analysis/blob/main/data/investor_decision_dashboard/latest.json" in render_markdown(m)


def test_only_proven_radar_is_labeled_research_only(tmp_path):
    _, _, _, canonical = inputs(tmp_path)
    save(tmp_path, "data/era_radar/latest.json", {
        "snapshot_id": "era-1", "formal_trading_authority": False,
        "no_auto_trade": True, "research_as_of": "2026-09-20T00:00:00Z",
        "trends": [{"trend_id": "power", "lifecycle": "EMERGING"}] * 7,
    })
    m = build_handoff(tmp_path, canonical)
    assert len(m["trend_research"]) == 5
    assert all(r["authority"] == "RESEARCH_ONLY" for r in m["trend_research"])
    assert m["feeds"]["era_cycle"]["as_of"] == "2026-09-20T00:00:00Z"


def test_real_generation_freshness_ok_is_accepted_without_trade_authority(tmp_path):
    d, canon, path, canonical_path = inputs(tmp_path)
    d["generated_at"] = "2026-09-29T19:24:27Z"
    d["latest_trade_date"] = "2026-09-29"
    d["market"]["as_of_date"] = "2026-09-29"
    canon["latest_trade_date"] = "2026-09-29"
    save(tmp_path, "incoming/canonical.json", canon)
    # Consume the REAL existing evaluator contract, not a made-up FRESH enum.
    freshness = evaluate_generation_freshness(
        {"generated_at": "2026-09-29T17:01:36Z",
         "latest_trade_date": "2026-09-29", "source_run_id": "100"},
        market_regime=d["market"],
        evaluated_at="2026-09-29T19:24:27Z",
        strict_missing_metadata=True,
    )
    assert freshness["status"] == "OK"
    assert freshness["fresh"] is True
    d["freshness_contract"] = freshness
    d["formal_new_exposure_allowed"] = freshness["formal_new_exposure_allowed"]
    path.write_text(json.dumps(d), encoding="utf-8")
    m = build_handoff(tmp_path, canonical_path)
    assert m["feeds"]["market_eod"]["status"] == "UPSTREAM_FRESH_CALENDAR_UNVERIFIED"
    assert "Market state: UPSTREAM_FRESH_CALENDAR_UNVERIFIED" in render_markdown(m)
    assert "STALE_OR_UNVERIFIED_MARKET_SESSION" not in m["blocking_reasons"]
    assert m["lineage"]["exchange_calendar_independently_verified"] is False
    assert m["lineage"]["live_broker_positions_verified"] is False
    assert m["feeds"]["broker_cash"]["status"] == "UNKNOWN"
    assert m["feeds"]["executable_quotes"]["status"] == "UNVERIFIED"
    assert m["formal_buy_now"] == [] and m["formal_wait_price"] == []
    assert m["no_auto_trade"] is True


@pytest.mark.parametrize("status,fresh,contract_allowed,dashboard_allowed", [
    ("FRESH", True, True, True),  # Not an emitted evaluator status.
    ("STALE_UPSTREAM", True, True, True),
    ("UNVERIFIABLE", True, True, True),
    ("OK", False, True, True),
    ("OK", True, False, True),
    ("OK", True, True, False),
])
def test_mismatched_freshness_bits_cannot_claim_current_market(
    tmp_path, status, fresh, contract_allowed, dashboard_allowed,
):
    d, _, path, canonical_path = inputs(tmp_path)
    d["freshness_contract"].update({
        "status": status, "fresh": fresh,
        "formal_new_exposure_allowed": contract_allowed,
    })
    d["formal_new_exposure_allowed"] = dashboard_allowed
    path.write_text(json.dumps(d), encoding="utf-8")
    m = build_handoff(tmp_path, canonical_path)
    assert m["feeds"]["market_eod"]["status"] == "STALE_OR_UNVERIFIED"
    assert "STALE_OR_UNVERIFIED_MARKET_SESSION" in m["blocking_reasons"]
    assert m["formal_buy_now"] == [] and m["no_auto_trade"] is True


def test_market_date_conflict_stays_blocked_even_when_freshness_bits_are_ok(tmp_path):
    d, _, path, canonical_path = inputs(tmp_path)
    d["freshness_contract"].update({
        "status": "OK", "fresh": True,
        "formal_new_exposure_allowed": True,
    })
    d["formal_new_exposure_allowed"] = True
    d["market"]["as_of_date"] = "2026-09-23"
    path.write_text(json.dumps(d), encoding="utf-8")
    m = build_handoff(tmp_path, canonical_path)
    assert m["feeds"]["market_eod"]["status"] == "STALE_OR_UNVERIFIED"
    assert "CROSS_FEED_MARKET_LINEAGE_MISMATCH" in m["blocking_reasons"]
