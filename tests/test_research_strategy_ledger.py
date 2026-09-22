from src.strategies.genge_opportunity_discovery.research_strategy_ledger import (
    append_attempts,
    has_strategy_scope,
    plan_strategy_attempts,
    reconcile_ledger,
)


def _row(
    *,
    code="000576",
    fingerprint="fp-1",
    reason="INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
):
    return {
        "entity_id": code,
        "research_evidence_fingerprint": fingerprint,
        "research_context": {
            "unresolved_gates": [
                {"gate": "predictability", "reason": reason},
                {
                    "gate": "financial_safety",
                    "reason": "SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT",
                },
            ]
        },
    }


def test_plans_one_attempt_per_supported_gate_for_new_evidence_epoch():
    row = _row()

    attempts = plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="100",
        attempted_at="2026-09-22T00:00:00+00:00",
    )

    assert {item["hard_gate"] for item in attempts} == {
        "predictability",
        "financial_safety",
    }
    assert {item["evidence_epoch"] for item in attempts} == {"fp-1"}
    assert all(item["attempt_status"] == "DISPATCH_PLANNED" for item in attempts)
    assert all(item["formal_trading_authority"] is False for item in attempts)
    assert all(item["no_auto_trade"] is True for item in attempts)


def test_same_strategy_and_fingerprint_is_not_planned_twice():
    row = _row()
    attempts = plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="100",
    )
    ledger = append_attempts({}, attempts)

    repeated = plan_strategy_attempts(
        row,
        ledger,
        source_workflow_run_id="101",
    )

    assert repeated == []


def test_new_evidence_fingerprint_reactivates_strategy():
    first = _row(fingerprint="fp-1")
    ledger = append_attempts(
        {},
        plan_strategy_attempts(first, {}, source_workflow_run_id="100"),
    )
    later = _row(fingerprint="fp-2")

    attempts = plan_strategy_attempts(
        later,
        ledger,
        source_workflow_run_id="101",
    )

    assert {item["hard_gate"] for item in attempts} == {
        "predictability",
        "financial_safety",
    }
    assert {item["evidence_fingerprint"] for item in attempts} == {"fp-2"}


def test_later_same_fingerprint_marks_accepted_attempt_as_no_progress_exhausted():
    row = _row()
    attempts = plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="100",
    )
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
    ledger = append_attempts({}, attempts)

    reconciled = reconcile_ledger(
        ledger,
        [row],
        current_source_workflow_run_id="101",
    )

    assert all(
        item["attempt_status"] == "EXHAUSTED_NO_PROGRESS"
        for item in reconciled["entries"]
    )
    assert all(item["new_evidence_acquired"] is False for item in reconciled["entries"])
    assert all(item["gate_changed"] is False for item in reconciled["entries"])
    assert all(item["strategy_exhausted"] is True for item in reconciled["entries"])


def test_changed_fingerprint_records_evidence_progress_without_inventing_gate_pass():
    first = _row(fingerprint="fp-1")
    attempts = plan_strategy_attempts(
        first,
        {},
        source_workflow_run_id="100",
    )
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
    ledger = append_attempts({}, attempts)

    later = _row(
        fingerprint="fp-2",
        reason="MULTI_YEAR_POSITIVITY_NOT_PROVEN",
    )
    reconciled = reconcile_ledger(
        ledger,
        [later],
        current_source_workflow_run_id="101",
    )
    by_gate = {item["hard_gate"]: item for item in reconciled["entries"]}

    assert by_gate["predictability"]["attempt_status"] == "COMPLETED_EVIDENCE_CHANGED"
    assert by_gate["predictability"]["new_evidence_acquired"] is True
    assert by_gate["predictability"]["gate_changed"] is True
    assert by_gate["financial_safety"]["attempt_status"] == "COMPLETED_EVIDENCE_CHANGED"
    assert by_gate["financial_safety"]["new_evidence_acquired"] is True


def test_same_source_run_does_not_close_write_ahead_attempt():
    row = _row()
    attempts = plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="100",
    )
    ledger = append_attempts({}, attempts)

    reconciled = reconcile_ledger(
        ledger,
        [row],
        current_source_workflow_run_id="100",
    )

    assert all(
        item["attempt_status"] == "DISPATCH_PLANNED"
        for item in reconciled["entries"]
    )


def test_missing_fingerprint_or_gate_state_is_not_falsely_governed():
    assert has_strategy_scope({"entity_id": "000001"}) is False
    assert plan_strategy_attempts(
        {"entity_id": "000001"},
        {},
        source_workflow_run_id="100",
    ) == []

def test_accepted_attempt_waits_until_exact_deep_result_is_visible():
    row = _row()
    attempts = plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="100",
    )
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
        item["deep_run_id"] = "900"
    ledger = append_attempts({}, attempts)

    before_result = _row()
    before_result["research_context"]["deep_lambda_run_id"] = "899"
    unreconciled = reconcile_ledger(
        ledger,
        [before_result],
        current_source_workflow_run_id="101",
    )
    assert all(
        item["attempt_status"] == "DISPATCH_ACCEPTED"
        for item in unreconciled["entries"]
    )

    after_result = _row()
    after_result["research_context"]["deep_lambda_run_id"] = "900"
    reconciled = reconcile_ledger(
        unreconciled,
        [after_result],
        current_source_workflow_run_id="102",
    )
    assert all(
        item["attempt_status"] == "EXHAUSTED_NO_PROGRESS"
        for item in reconciled["entries"]
    )

