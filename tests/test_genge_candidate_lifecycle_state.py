from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    DORMANT,
    INVALIDATED,
    apply_explicit_transition,
    apply_snapshot,
    apply_terminal_memory,
    empty_state,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _snapshot(
    *,
    snapshot_run: str,
    generated_at: str,
    include_candidate: bool = True,
) -> dict:
    deep = []
    production = []
    if include_candidate:
        deep = [
            {
                "code": "600312",
                "stock_name": "平高电气",
                "industry": "电网设备",
                "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
                "v31_review_rank": "1",
                "v31_candidate_class": "WATCH",
                "valuation_confidence": "MEDIUM",
                "latest_trade_date": "2026-08-27",
            }
        ]
        production = [
            {
                "code": "600312",
                "stock_name": "平高电气",
                "decision_scope": "CANDIDATE",
                "production_action": "HOLD_REVIEW",
                "production_model_version": PRODUCTION_VERSION,
                "v311_production_bridge": PRODUCTION_BRIDGE,
                "strict_pit_refresh_applied": "True",
                "upstream_policy_reused": "False",
                "no_auto_trade": "True",
                "current_price": "20.43",
                "decision_date": "2026-08-27",
                "price_date": "2026-08-27",
                "valuation_confidence": "MEDIUM",
            }
        ]
    return build_snapshot(
        [],
        deep,
        production,
        source_kind="every-industry",
        source_run_id=snapshot_run,
        upstream_run_id=f"upstream:{snapshot_run}",
        generated_at=generated_at,
        research_as_of=generated_at,
        source_hashes={
            "discovery_csv": f"{snapshot_run}-d",
            "deep_review_csv": f"{snapshot_run}-r",
            "production_csv": f"{snapshot_run}-p",
        },
    )


def test_same_snapshot_is_idempotent_and_does_not_increment_seen_count() -> None:
    snapshot = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    state, first_events = apply_snapshot(empty_state(), snapshot)
    state_again, second_events = apply_snapshot(state, snapshot)

    assert len(first_events) == 1
    assert first_events[0]["event"] == "NEW"
    assert state["candidates"]["600312"]["seen_count"] == 1
    assert second_events == []
    assert state_again["candidates"]["600312"]["seen_count"] == 1
    assert state_again["event_count"] == state["event_count"]


def test_new_snapshot_reseen_increments_once() -> None:
    first = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    second = _snapshot(snapshot_run="101", generated_at="2026-08-27T10:00:00+00:00")
    state, _ = apply_snapshot(empty_state(), first)
    state, events = apply_snapshot(state, second)

    assert events[0]["event"] == "RESEEN"
    assert state["candidates"]["600312"]["seen_count"] == 2
    assert state["candidates"]["600312"]["last_seen_source_run_id"] == "101"


def test_absence_from_new_snapshot_does_not_archive_candidate() -> None:
    first = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    absent = _snapshot(
        snapshot_run="101",
        generated_at="2026-08-27T10:00:00+00:00",
        include_candidate=False,
    )
    state, _ = apply_snapshot(empty_state(), first)
    state, events = apply_snapshot(state, absent)

    assert events == []
    assert state["candidates"]["600312"]["lifecycle_state"] == ACTIVE
    assert state["candidates"]["600312"]["seen_count"] == 1


def test_invalidated_candidate_rediscovery_does_not_auto_reactivate() -> None:
    first = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    second = _snapshot(snapshot_run="101", generated_at="2026-08-27T10:00:00+00:00")
    state, _ = apply_snapshot(empty_state(), first)
    state, event = apply_explicit_transition(
        state,
        {
            "code": "600312",
            "event": "INVALIDATED",
            "evidence_id": "filing:600312:2026-08-27:thesis-break",
            "evidence_observed_at": "2026-08-27T09:00:00+00:00",
            "reason": "explicit thesis-break evidence",
            "snapshot_id": first["snapshot_id"],
        },
    )
    assert event is not None
    assert state["candidates"]["600312"]["lifecycle_state"] == INVALIDATED

    state, events = apply_snapshot(state, second)

    assert events[0]["event"] == "REDISCOVERED_REVIEW_REQUIRED"
    assert events[0]["automatic_reactivation"] is False
    assert state["candidates"]["600312"]["lifecycle_state"] == INVALIDATED


def test_reactivation_requires_explicit_new_evidence_and_is_idempotent() -> None:
    snapshot = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    state, _ = apply_snapshot(empty_state(), snapshot)
    state, _ = apply_explicit_transition(
        state,
        {
            "code": "600312",
            "event": "INVALIDATED",
            "evidence_id": "evidence:invalidate:1",
            "evidence_observed_at": "2026-08-27T09:00:00+00:00",
            "reason": "thesis break",
        },
    )
    transition = {
        "code": "600312",
        "event": "REACTIVATED",
        "evidence_id": "evidence:reactivate:2",
        "evidence_observed_at": "2026-08-27T11:00:00+00:00",
        "reason": "new evidence resolves prior thesis break",
        "target_tier": "WATCH",
    }
    state, event = apply_explicit_transition(state, transition)
    state_again, duplicate = apply_explicit_transition(state, transition)

    assert event is not None and event["event"] == "REACTIVATED"
    assert state["candidates"]["600312"]["lifecycle_state"] == ACTIVE
    assert duplicate is None
    assert state_again["event_count"] == state["event_count"]


def test_upgrade_does_not_reactivate_invalidated_candidate() -> None:
    snapshot = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    state, _ = apply_snapshot(empty_state(), snapshot)
    state, _ = apply_explicit_transition(
        state,
        {
            "code": "600312",
            "event": "INVALIDATED",
            "evidence_id": "evidence:invalidate:1",
            "evidence_observed_at": "2026-08-27T09:00:00+00:00",
            "reason": "thesis break",
        },
    )
    state, event = apply_explicit_transition(
        state,
        {
            "code": "600312",
            "event": "UPGRADED",
            "evidence_id": "evidence:better-quarter:2",
            "evidence_observed_at": "2026-08-27T10:00:00+00:00",
            "reason": "quarter improved but invalidation not formally resolved",
            "target_tier": "WATCH",
        },
    )

    assert event is not None
    assert state["candidates"]["600312"]["lifecycle_state"] == INVALIDATED


def test_out_of_order_snapshot_is_rejected() -> None:
    later = _snapshot(snapshot_run="101", generated_at="2026-08-27T10:00:00+00:00")
    earlier = _snapshot(snapshot_run="100", generated_at="2026-08-27T08:00:00+00:00")
    state, _ = apply_snapshot(empty_state(), later)

    with pytest.raises(ValueError, match="out-of-order canonical snapshot"):
        apply_snapshot(state, earlier)

def _active_terminal_candidate() -> dict:
    state = empty_state()
    state["candidates"]["002120"] = {
        "code": "002120",
        "stock_name": "韵达股份",
        "lifecycle_state": ACTIVE,
        "research_tier": "PENDING",
        "seen_count": 1,
        "history": [],
        "applied_evidence_ids": [],
    }
    return state


def test_retryable_research_gap_preserves_existing_wait_price_memory() -> None:
    state = _active_terminal_candidate()
    state, first_events = apply_terminal_memory(
        state,
        [
            {
                "code": "002120",
                "terminal_decision": "WAIT_PRICE",
                "terminal_reason_class": "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK",
                "terminal_reason_codes": "PRICE_TOO_CLOSE_TO_BASE_VALUE",
                "terminal_current_price": "9",
                "wait_price_max": "8",
                "source_production_action": "WAIT",
                "source_valuation_confidence": "HIGH",
                "terminal_formal_buy_authorized": False,
            }
        ],
        memory_id="terminal-day-1",
        observed_at="2026-09-16T10:00:00+00:00",
    )
    assert len(first_events) == 1
    candidate = state["candidates"]["002120"]
    assert candidate["last_terminal_decision"] == "WAIT_PRICE"
    assert candidate["last_wait_price_max"] == 8.0
    assert candidate["price_zone"] == "WAIT_PRICE"

    state, gap_events = apply_terminal_memory(
        state,
        [
            {
                "code": "002120",
                "terminal_decision": "RESEARCH_GAP",
                "terminal_reason_class": "EVIDENCE_INSUFFICIENT",
                "terminal_reason_codes": "hard_gate_unknown:moat",
                "terminal_current_price": "8.7",
                "source_production_action": "WAIT",
                "source_valuation_confidence": "LOW",
                "terminal_formal_buy_authorized": False,
            }
        ],
        memory_id="terminal-day-2",
        observed_at="2026-09-17T10:00:00+00:00",
    )

    candidate = state["candidates"]["002120"]
    assert candidate["last_terminal_decision"] == "WAIT_PRICE"
    assert candidate["last_wait_price_max"] == 8.0
    assert candidate["last_researched_time"] == "2026-09-17T10:00:00+00:00"
    assert candidate["last_price"] == 8.7
    assert candidate["price_zone"] == "WAIT_PRICE"
    assert candidate["next_action"] == "CONTINUE_RESEARCH_WAIT_PRICE"
    assert candidate["last_research_gap_reason_class"] == "EVIDENCE_INSUFFICIENT"
    assert gap_events[0]["event"] == "TERMINAL_RESEARCH_GAP_PRESERVED_WAIT_PRICE"
    assert gap_events[0]["effective_terminal_decision"] == "WAIT_PRICE"


def test_explicit_reject_replaces_wait_price_memory() -> None:
    state = _active_terminal_candidate()
    state, _ = apply_terminal_memory(
        state,
        [
            {
                "code": "002120",
                "terminal_decision": "WAIT_PRICE",
                "terminal_reason_class": "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK",
                "terminal_reason_codes": "PRICE_TOO_CLOSE_TO_BASE_VALUE",
                "terminal_current_price": "9",
                "wait_price_max": "8",
                "source_production_action": "WAIT",
                "source_valuation_confidence": "HIGH",
                "terminal_formal_buy_authorized": False,
            }
        ],
        memory_id="terminal-before-reject",
        observed_at="2026-09-16T10:00:00+00:00",
    )
    state, events = apply_terminal_memory(
        state,
        [
            {
                "code": "002120",
                "terminal_decision": "REJECT",
                "terminal_reason_class": "HARD_GATE_FAILED",
                "terminal_reason_codes": "hard_gate_failed:financial_safety",
                "terminal_current_price": "8.6",
                "source_production_action": "REJECT",
                "source_valuation_confidence": "HIGH",
                "terminal_formal_buy_authorized": False,
            }
        ],
        memory_id="terminal-hard-fail",
        observed_at="2026-09-17T10:00:00+00:00",
    )

    candidate = state["candidates"]["002120"]
    assert candidate["last_terminal_decision"] == "REJECT"
    assert candidate["price_zone"] == ""
    assert candidate["next_action"] == "NO_ACTION"
    assert events[0]["effective_terminal_decision"] == "REJECT"


def test_terminal_memory_rejects_unauthorized_buy_and_cannot_admit_new_candidate() -> None:
    state = _active_terminal_candidate()
    with pytest.raises(ValueError, match="unauthorized terminal BUY memory"):
        apply_terminal_memory(
            state,
            [
                {
                    "code": "002120",
                    "terminal_decision": "BUY",
                    "terminal_formal_buy_authorized": False,
                    "source_production_action": "BUY",
                    "source_valuation_confidence": "HIGH",
                }
            ],
            memory_id="terminal-unauthorized-buy",
            observed_at="2026-09-17T10:00:00+00:00",
        )

    state, events = apply_terminal_memory(
        state,
        [
            {
                "code": "000589",
                "terminal_decision": "RESEARCH_GAP",
                "terminal_reason_class": "DEEP_PROFILE_MISSING",
            }
        ],
        memory_id="terminal-no-admission",
        observed_at="2026-09-17T11:00:00+00:00",
    )
    assert events == []
    assert "000589" not in state["candidates"]



def test_research_exhaustion_moves_only_nonholding_active_candidate_to_dormant() -> None:
    state = _active_terminal_candidate()
    transition = {
        "code": "002120",
        "event": "RESEARCH_EXHAUSTED",
        "evidence_id": "jev-exhaustion:run-1:002120:epoch-a",
        "evidence_observed_at": "2026-09-23T04:00:00+00:00",
        "reason": "all supported hard-gate strategies exhausted for the current evidence epoch",
        "is_current_holding": False,
        "research_evidence_epoch": "epoch-a",
    }
    state, event = apply_explicit_transition(state, transition)

    assert event is not None
    assert state["candidates"]["002120"]["lifecycle_state"] == DORMANT
    assert event["research_evidence_epoch"] == "epoch-a"
    assert event["automatic_reactivation"] is False

    holding_state = _active_terminal_candidate()
    with pytest.raises(ValueError, match="forbidden for current holdings"):
        apply_explicit_transition(
            holding_state,
            {
                **transition,
                "evidence_id": "jev-exhaustion:holding",
                "is_current_holding": True,
            },
        )


def test_dormant_candidate_reactivates_only_on_changed_research_evidence() -> None:
    state = _active_terminal_candidate()
    state, _ = apply_explicit_transition(
        state,
        {
            "code": "002120",
            "event": "RESEARCH_EXHAUSTED",
            "evidence_id": "jev-exhaustion:run-1:002120:epoch-a",
            "evidence_observed_at": "2026-09-23T04:00:00+00:00",
            "reason": "current evidence epoch exhausted",
            "is_current_holding": False,
            "research_evidence_epoch": "epoch-a",
        },
    )

    with pytest.raises(ValueError, match="requires changed research evidence"):
        apply_explicit_transition(
            state,
            {
                "code": "002120",
                "event": "RESEARCH_REACTIVATED",
                "evidence_id": "jev-reactivation:run-2:002120:epoch-b",
                "evidence_observed_at": "2026-09-23T05:00:00+00:00",
                "reason": "candidate re-entered research routing",
                "research_evidence_changed": False,
                "research_evidence_epoch": "epoch-b",
            },
        )

    state, event = apply_explicit_transition(
        state,
        {
            "code": "002120",
            "event": "RESEARCH_REACTIVATED",
            "evidence_id": "jev-reactivation:run-2:002120:epoch-b",
            "evidence_observed_at": "2026-09-23T05:00:00+00:00",
            "reason": "new hard-gate evidence epoch reopened a bounded research strategy",
            "research_evidence_changed": True,
            "research_evidence_epoch": "epoch-b",
        },
    )
    assert event is not None
    assert event["automatic_reactivation"] is True
    assert state["candidates"]["002120"]["lifecycle_state"] == ACTIVE
