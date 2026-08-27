from __future__ import annotations

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    apply_snapshot,
    empty_state,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _production_row(code: str, action: str) -> dict:
    return {
        "code": code,
        "stock_name": f"Stock-{code}",
        "decision_scope": "CANDIDATE",
        "production_action": action,
        "production_model_version": PRODUCTION_VERSION,
        "v311_production_bridge": PRODUCTION_BRIDGE,
        "strict_pit_refresh_applied": "True",
        "upstream_policy_reused": "False",
        "no_auto_trade": "True",
        "current_price": "20.00",
        "decision_date": "2026-08-27",
        "price_date": "2026-08-27",
        "valuation_confidence": "MEDIUM",
        "v311_expectation_input_status": "READY" if action in {"BUY", "ADD"} else "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_input_error": "" if action in {"BUY", "ADD"} else "TEST_INCOMPLETE",
    }


def _snapshot(*, run_id: str, deep_rows: list[dict], production_rows: list[dict]) -> dict:
    return build_snapshot(
        [],
        deep_rows,
        production_rows,
        source_kind="every-industry",
        source_run_id=run_id,
        upstream_run_id=f"upstream:{run_id}",
        generated_at="2026-08-27T08:00:00+00:00",
        research_as_of="2026-08-27T08:00:00+00:00",
        source_hashes={
            "discovery_csv": f"{run_id}-d",
            "deep_review_csv": f"{run_id}-r",
            "production_csv": f"{run_id}-p",
        },
    )


def test_generic_production_only_hold_review_does_not_enter_durable_lifecycle() -> None:
    snapshot = _snapshot(
        run_id="100",
        deep_rows=[],
        production_rows=[_production_row("600001", "HOLD_REVIEW")],
    )

    state, events = apply_snapshot(empty_state(), snapshot)

    assert events == []
    assert state["candidates"] == {}
    assert state["latest_applied_snapshot_id"] == snapshot["snapshot_id"]


def test_deep_review_hold_review_enters_durable_lifecycle() -> None:
    deep = [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "industry": "电网设备",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "v31_candidate_class": "WATCH / BUY_REVIEW",
            "valuation_confidence": "MEDIUM",
            "latest_trade_date": "2026-08-27",
        }
    ]
    snapshot = _snapshot(
        run_id="101",
        deep_rows=deep,
        production_rows=[_production_row("600312", "HOLD_REVIEW")],
    )

    state, events = apply_snapshot(empty_state(), snapshot)

    assert len(events) == 1
    assert events[0]["event"] == "NEW"
    assert state["candidates"]["600312"]["research_tier"] == "WATCH / BUY_REVIEW"
    assert state["candidates"]["600312"]["last_formal_action"] == "HOLD_REVIEW"


def test_production_only_formal_buy_enters_durable_lifecycle() -> None:
    snapshot = _snapshot(
        run_id="102",
        deep_rows=[],
        production_rows=[_production_row("600406", "BUY")],
    )

    state, events = apply_snapshot(empty_state(), snapshot)

    assert len(events) == 1
    assert events[0]["event"] == "NEW"
    assert state["candidates"]["600406"]["last_formal_action"] == "BUY"


def test_existing_active_candidate_can_be_reseen_by_production_reunderwrite() -> None:
    state = empty_state()
    state["candidates"] = {
        "600312": {
            "code": "600312",
            "stock_name": "平高电气",
            "lifecycle_state": ACTIVE,
            "research_tier": "WATCH / BUY_REVIEW",
            "first_seen_snapshot_id": "legacy",
            "first_seen_source_run_id": "legacy",
            "last_seen_snapshot_id": "legacy",
            "last_seen_source_run_id": "legacy",
            "seen_count": 1,
            "last_formal_action": "HOLD_REVIEW",
            "last_valuation_confidence": "MEDIUM",
            "last_event": "LEGACY_IMPORT",
            "last_event_at": "2026-08-26T08:00:00+00:00",
            "applied_evidence_ids": [],
            "history": [],
        }
    }
    snapshot = _snapshot(
        run_id="103",
        deep_rows=[],
        production_rows=[_production_row("600312", "HOLD_REVIEW")],
    )

    state, events = apply_snapshot(state, snapshot)

    assert len(events) == 1
    assert events[0]["event"] == "RESEEN"
    assert events[0]["observed_scope"] == "PRODUCTION_REUNDERWRITE"
    assert state["candidates"]["600312"]["seen_count"] == 2
