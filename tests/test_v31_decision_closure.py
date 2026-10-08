from __future__ import annotations

from src.strategies.genge_opportunity_discovery.v31_decision_closure import (
    classify_terminal_row,
    enrich_terminal_payload,
)


def _row(*, decision="RESEARCH_GAP", reason="EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY", unknown=None, failed=None, code="603993"):
    return {
        "code": code,
        "name": "sample",
        "research_decision": decision,
        "research_reason": reason,
        "research_authority": "RESEARCH_ONLY",
        "formal_buy_authorized": False,
        "no_auto_trade": True,
        "hard_gate_unknowns": list(unknown or []),
        "hard_gate_failures": list(failed or []),
    }


def _payload(rows, urgent=None):
    return {
        "requested_count": len(rows),
        "terminal_rows": rows,
        "urgent_research_queue": list(urgent or []),
        "unknown_is_pass": False,
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
    }


def test_one_soft_unknown_after_bounded_retry_is_decision_ready_not_fake_pass():
    closure = classify_terminal_row(_row(unknown=["predictability"]))
    assert closure["closure_state"] == "DECISION_READY_WITH_UNCERTAINTY"
    assert closure["decision_ready"] is True
    assert closure["evidence_complete"] is False
    assert closure["unknown_is_pass"] is False
    assert closure["formal_buy_authorized"] is False
    assert closure["automatic_execution_allowed"] is False


def test_critical_unknown_remains_research_required():
    closure = classify_terminal_row(_row(unknown=["financial_safety"]))
    assert closure["closure_state"] == "RESEARCH_REQUIRED"
    assert closure["decision_ready"] is False


def test_two_soft_unknowns_remain_research_required():
    closure = classify_terminal_row(_row(unknown=["predictability", "moat"]))
    assert closure["closure_state"] == "RESEARCH_REQUIRED"
    assert closure["decision_ready"] is False


def test_explicit_failure_closes_negative_decision_without_waiting_for_every_gate():
    closure = classify_terminal_row(
        _row(decision="REJECT", reason="HARD_GATE_FAIL", failed=["moat"], unknown=["predictability"])
    )
    assert closure["closure_state"] == "DECISIVE_REJECT"
    assert closure["decision_ready"] is True
    assert closure["evidence_complete"] is False


def test_full_buy_stays_full_evidence_but_overlay_never_grants_authority():
    closure = classify_terminal_row(_row(decision="BUY", reason="ALL_HARD_GATES_PASS", unknown=[]))
    assert closure["closure_state"] == "FULL_EVIDENCE"
    assert closure["formal_buy_evidence_ready"] is True
    assert closure["formal_buy_authorized"] is False


def test_overlay_removes_bounded_soft_unknown_from_urgent_loop_only():
    bounded = _row(code="603993", unknown=["predictability"])
    critical = _row(code="600406", unknown=["financial_safety"])
    enriched = enrich_terminal_payload(_payload([bounded, critical], urgent=[bounded, critical]))

    assert enriched["decision_ready_count"] == 1
    assert enriched["bounded_uncertainty_ready_count"] == 1
    assert enriched["research_required_count"] == 1
    assert enriched["evidence_complete_count"] == 0
    assert enriched["bounded_uncertainty_ready_codes"] == ["603993"]
    assert [r["code"] for r in enriched["urgent_research_queue"]] == ["600406"]
    assert enriched["unknown_is_pass"] is False
    assert enriched["formal_trading_authority"] is False
    assert enriched["no_auto_trade"] is True
