from __future__ import annotations

from src.strategies.genge_opportunity_discovery.candidate_lifecycle_state import (
    ACTIVE,
    DORMANT,
    apply_research_exhaustion_lifecycle,
    empty_state,
)
from src.strategies.genge_opportunity_discovery.research_priority_router import build_queue
from src.strategies.genge_opportunity_discovery.research_strategy_ledger import (
    gate_evidence_fingerprint,
    research_exhaustion_state,
)


def _row(*, evidence: str = "moat-proof-a", holding: bool = False) -> dict:
    return {
        "entity_id": "603105",
        "entity_name": "芯能科技",
        "is_current_holding": holding,
        "research_evidence_fingerprint": "stock-state-a",
        "research_context": {
            "research_decision": "RESEARCH_GAP",
            "unresolved_gates": [
                {
                    "gate": "moat",
                    "reason": "DURABLE_MOAT_CORROBORATION_THRESHOLD_NOT_MET",
                }
            ],
            "profile_gate_statuses": {
                "moat": {
                    "status": "UNKNOWN",
                    "source": "AUTOMATIC_ATTEMPT",
                    "confidence": "",
                    "evidence_fingerprint": evidence,
                }
            },
        },
    }


def _routing(row: dict, run_id: str = "900") -> dict:
    return {
        "contract": "GEN_GE_JEV_ROUTING_BRIDGE_V1",
        "execution_status": "SUCCESS",
        "authority": "ADVISORY_RESEARCH_ROUTING_ONLY",
        "automatic_dispatch_allowed": False,
        "automatic_formal_buy_allowed": False,
        "formal_trading_authority": False,
        "mutates_authoritative_decision": False,
        "may_create_or_mutate_formal_action": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "source_workflow_run_id": run_id,
        "generated_at": "2026-09-23T06:30:57+00:00",
        "routing_queue": [row],
    }


def _state() -> dict:
    state = empty_state()
    state["candidates"]["603105"] = {
        "code": "603105",
        "stock_name": "芯能科技",
        "lifecycle_state": ACTIVE,
        "research_tier": "A1-QUALITY / WAIT_PRICE",
        "seen_count": 2,
        "history": [],
        "applied_evidence_ids": [],
    }
    return state


def _exhausted_ledger(row: dict) -> dict:
    reason = "DURABLE_MOAT_CORROBORATION_THRESHOLD_NOT_MET"
    fingerprint = gate_evidence_fingerprint(
        row,
        gate="moat",
        unresolved_reason=reason,
    )
    return {
        "entries": [
            {
                "code": "603105",
                "hard_gate": "moat",
                "strategy_family": "STRICT_MULTI_YEAR_OFFICIAL_MOAT_REFRESH",
                "evidence_fingerprint": fingerprint,
                "attempt_status": "EXHAUSTED_NO_PROGRESS",
                "strategy_exhausted": True,
            }
        ]
    }


def test_exhaustion_requires_exact_current_epoch():
    row = _row()
    ledger = _exhausted_ledger(row)
    assert research_exhaustion_state(row, ledger)["exhausted"] is True

    changed = _row(evidence="moat-proof-b")
    reopened = research_exhaustion_state(changed, ledger)
    assert reopened["exhausted"] is False
    assert reopened["supported_gate_count"] == 1


def test_exhausted_nonholding_dorms_and_new_epoch_reactivates():
    row = _row()
    ledger = _exhausted_ledger(row)
    state, events = apply_research_exhaustion_lifecycle(
        _state(),
        _routing(row),
        ledger,
    )
    assert state["candidates"]["603105"]["lifecycle_state"] == DORMANT
    assert events[0]["event"] == "RESEARCH_EXHAUSTED_DORMANT"
    assert events[0]["formal_trading_authority"] is False

    changed = _row(evidence="moat-proof-b")
    state, events = apply_research_exhaustion_lifecycle(
        state,
        _routing(changed, run_id="901"),
        ledger,
    )
    assert state["candidates"]["603105"]["lifecycle_state"] == ACTIVE
    assert events[0]["event"] == "RESEARCH_EVIDENCE_REACTIVATED"
    assert events[0]["automatic_reactivation"] is True


def test_current_holding_is_never_dormant():
    row = _row(holding=True)
    state, events = apply_research_exhaustion_lifecycle(
        _state(),
        _routing(row),
        _exhausted_ledger(row),
    )
    assert state["candidates"]["603105"]["lifecycle_state"] == ACTIVE
    assert events == []


def test_dormant_candidate_loses_stale_tier_boost_but_new_signal_can_reenter():
    lifecycle = {
        "candidates": {
            "603105": {
                "stock_name": "芯能科技",
                "research_tier": "A1-QUALITY / WAIT_PRICE",
                "lifecycle_state": "DORMANT",
            }
        }
    }
    coverage = {
        "securities": [
            {
                "code": "603105",
                "name": "芯能科技",
                "scopes": ["ACTIVE_CANDIDATE"],
                "industry_mapped": True,
                "commodity_monitoring_state": "NOT_APPLICABLE",
                "peer_monitoring_state": "MAPPED",
            }
        ]
    }
    quiet = build_queue({"rows": []}, lifecycle, coverage)["queue"][0]
    assert quiet["lifecycle_state"] == "DORMANT"
    assert quiet["priority_score"] == 0
    assert "RESEARCH_DORMANT_WAIT_NEW_EVIDENCE" in quiet["reason_codes"]

    hourly = {
        "rows": [
            {
                "code": "603105",
                "scope": "DEEP_REVIEW_FOCUS",
                "formal_action": "",
                "hourly_research_conclusion": "NEW_EVIDENCE_REUNDERWRITE_LEAD",
                "thesis_status": "REUNDERWRITE_REQUIRED",
            }
        ]
    }
    reopened = build_queue(hourly, lifecycle, coverage)["queue"][0]
    assert reopened["priority_score"] >= 45
    assert reopened["priority"] in {"P0", "P1"}
    assert "REUNDERWRITE_REQUIRED" in reopened["reason_codes"]


def test_unsupported_unresolved_gate_blocks_dormancy_fail_closed():
    row = _row()
    row["research_context"]["unresolved_gates"].append(
        {"gate": "future_unmapped_gate", "reason": "NO_STRATEGY_DEFINED"}
    )
    state = research_exhaustion_state(row, _exhausted_ledger(_row()))
    assert state["exhausted"] is False
    assert state["blocker"].startswith("UNSUPPORTED_UNRESOLVED_GATES:")
