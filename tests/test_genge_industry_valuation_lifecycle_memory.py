from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    INVALIDATED,
    empty_state,
    write_state,
)
from src.strategies.genge_opportunity_discovery.industry_valuation_bridge import (
    _read_candidate_state_codes,
    write_merged_report,
)


def test_lifecycle_json_returns_active_and_inactive_codes(tmp_path: Path) -> None:
    state = empty_state()
    state["candidates"] = {
        "600312": {
            "code": "600312",
            "stock_name": "平高电气",
            "lifecycle_state": ACTIVE,
            "research_tier": "WATCH",
            "seen_count": 2,
            "last_formal_action": "HOLD_REVIEW",
            "last_valuation_confidence": "MEDIUM",
            "last_seen_snapshot_id": "abc",
            "last_seen_source_run_id": "100",
            "last_event": "RESEEN",
            "last_event_at": "2026-08-27T08:00:00+00:00",
            "applied_evidence_ids": [],
            "history": [],
        },
        "603658": {
            "code": "603658",
            "stock_name": "安图生物",
            "lifecycle_state": INVALIDATED,
            "research_tier": "WAIT / DOWNGRADED",
            "seen_count": 24,
            "last_formal_action": "HOLD_REVIEW",
            "last_valuation_confidence": "INVALID",
            "last_seen_snapshot_id": "abc",
            "last_seen_source_run_id": "100",
            "last_event": "INVALIDATED",
            "last_event_at": "2026-08-27T08:00:00+00:00",
            "applied_evidence_ids": [],
            "history": [],
        },
    }
    path = tmp_path / "candidate_lifecycle_state.json"
    write_state(path, state)

    active, inactive = _read_candidate_state_codes(path) or (set(), set())

    assert active == {"600312"}
    assert inactive == {"603658"}


def test_missing_lifecycle_json_allows_legacy_bootstrap_fallback(tmp_path: Path) -> None:
    assert _read_candidate_state_codes(tmp_path / "missing.json") is None


def test_existing_but_invalid_lifecycle_json_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "candidate_lifecycle_state.json"
    path.write_text(json.dumps({"contract_version": "WRONG"}), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate lifecycle contract version mismatch"):
        _read_candidate_state_codes(path)


def test_active_candidate_missing_from_today_all_a_is_materialized_for_research(
    tmp_path: Path,
) -> None:
    state = empty_state()
    state["candidates"] = {
        "002120": {
            "code": "002120",
            "stock_name": "韵达股份",
            "lifecycle_state": ACTIVE,
            "research_tier": "WAIT_PRICE",
            "seen_count": 1,
            "last_formal_action": "WAIT",
            "last_valuation_confidence": "HIGH",
            "last_seen_snapshot_id": "day-1",
            "last_seen_source_run_id": "100",
            "last_event": "NEW",
            "last_event_at": "2026-09-16T19:54:15+00:00",
            "applied_evidence_ids": [],
            "history": [],
        }
    }
    candidate_state = tmp_path / "candidate_lifecycle_state.json"
    write_state(candidate_state, state)

    all_a_root = tmp_path / "all_a"
    report = all_a_root / "20260917"
    report.mkdir(parents=True)
    with (report / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["code", "stock_name", "industry", "quant_status", "quant_rank", "quant_score", "hard_blockers"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "code": "600001",
                "stock_name": "今日新候选",
                "industry": "测试行业",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_rank": "1",
                "quant_score": "90",
                "hard_blockers": "",
            }
        )
    (report / "run_summary.json").write_text("{}", encoding="utf-8")

    industry = tmp_path / "industry"
    industry.mkdir()
    with (industry / "industry_top_candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["code", "stock_name", "industry", "industry_research_rank", "quant_status", "quant_score", "hard_blockers"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "code": "600001",
                "stock_name": "今日新候选",
                "industry": "测试行业",
                "industry_research_rank": "1",
                "quant_status": "PRIORITY_RESEARCH",
                "quant_score": "90",
                "hard_blockers": "",
            }
        )

    # A static research-pool code with no current All-A row is not enough to
    # manufacture lifecycle memory. Only the machine ACTIVE candidate below may
    # be materialized from metadata alone.
    curated_pool = tmp_path / "curated.txt"
    curated_pool.write_text("000589.SZ\n", encoding="utf-8")

    output = tmp_path / "out"
    rows = write_merged_report(
        all_a_root,
        industry,
        output,
        global_limit=1,
        relaxed_reserve=1,
        per_industry=1,
        curated_pool=curated_pool,
        candidate_state=candidate_state,
        candidate_ledger=None,
    )

    by_code = {row["code"]: row for row in rows}
    assert "000589" not in by_code
    recalled = by_code["002120"]
    assert recalled["stock_name"] == "韵达股份"
    assert recalled["valuation_source_channel"] == "DURABLE_LIFECYCLE_RECALL"
    assert recalled["durable_recall_source_missing"] is True
    assert recalled["candidate_lifecycle_recall"] is True
    assert recalled["candidate_lifecycle_research_tier"] == "WAIT_PRICE"
    assert recalled["formal_signal_eligible"] is False
    assert recalled["automatic_promotion_allowed"] is False
    assert recalled["no_auto_trade"] is True

    summary = json.loads(
        (output / "industry_valuation_source_summary.json").read_text(encoding="utf-8")
    )
    assert summary["ledger_active_missing_codes"] == ["002120"]
    assert summary["ledger_active_materialized_without_all_a_count"] == 1
    assert "002120" in summary["curated_materialized_without_all_a_codes"]
