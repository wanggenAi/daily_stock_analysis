from src.strategies.genge_opportunity_discovery.research_strategy_ledger import (
    append_attempts,
    gate_evidence_fingerprint,
    has_strategy_scope,
    plan_strategy_attempts,
    reconcile_ledger,
)


def _row(
    *,
    code="000576",
    fingerprint="fp-1",
    predictability_reason="INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
    financial_reason="SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT",
    predictability_source="annual-report",
    financial_source="financial-report",
):
    return {
        "entity_id": code,
        "research_evidence_fingerprint": fingerprint,
        "research_context": {
            "unresolved_gates": [
                {"gate": "predictability", "reason": predictability_reason},
                {"gate": "financial_safety", "reason": financial_reason},
            ],
            "profile_gate_statuses": {
                "predictability": {
                    "status": "UNKNOWN",
                    "confidence": "LOW",
                    "source": predictability_source,
                },
                "financial_safety": {
                    "status": "UNKNOWN",
                    "confidence": "LOW",
                    "source": financial_source,
                },
            },
        },
    }


def test_plans_one_attempt_per_supported_gate_for_new_gate_epoch():
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
    assert len({item["evidence_epoch"] for item in attempts}) == 2
    assert {item["stock_evidence_fingerprint"] for item in attempts} == {"fp-1"}
    assert all(item["attempt_status"] == "DISPATCH_PLANNED" for item in attempts)
    assert all(item["formal_trading_authority"] is False for item in attempts)
    assert all(item["no_auto_trade"] is True for item in attempts)


def test_gate_fingerprint_ignores_unrelated_stock_level_epoch_change():
    first = _row(fingerprint="fp-1")
    later = _row(fingerprint="fp-2")

    first_fp = gate_evidence_fingerprint(
        first,
        gate="predictability",
        unresolved_reason="INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
    )
    later_fp = gate_evidence_fingerprint(
        later,
        gate="predictability",
        unresolved_reason="INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
    )

    assert first_fp == later_fp


def test_same_strategy_and_gate_epoch_is_not_planned_twice():
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


def test_stock_epoch_change_alone_does_not_reactivate_exhausted_gate_strategy():
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

    assert attempts == []


def test_gate_local_change_reactivates_only_that_gate_strategy():
    first = _row()
    ledger = append_attempts(
        {},
        plan_strategy_attempts(first, {}, source_workflow_run_id="100"),
    )
    later = _row(
        fingerprint="fp-2",
        predictability_reason="MULTI_YEAR_POSITIVITY_NOT_PROVEN",
    )

    attempts = plan_strategy_attempts(
        later,
        ledger,
        source_workflow_run_id="101",
    )

    assert [item["hard_gate"] for item in attempts] == ["predictability"]
    assert attempts[0]["stock_evidence_fingerprint"] == "fp-2"


def test_later_same_gate_epoch_marks_accepted_attempt_as_no_progress_exhausted():
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


def test_gate_local_progress_does_not_reopen_or_mark_other_gate_progressed():
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
        predictability_reason="MULTI_YEAR_POSITIVITY_NOT_PROVEN",
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
    assert by_gate["financial_safety"]["attempt_status"] == "EXHAUSTED_NO_PROGRESS"
    assert by_gate["financial_safety"]["new_evidence_acquired"] is False
    assert by_gate["financial_safety"]["gate_changed"] is False


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


def test_missing_gate_state_is_not_falsely_governed():
    assert has_strategy_scope({"entity_id": "000001"}) is False
    assert plan_strategy_attempts(
        {"entity_id": "000001", "research_evidence_fingerprint": "fp"},
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

def test_semantic_evidence_change_reactivates_only_affected_gate():
    first = _row(fingerprint="fp-stable")
    first["research_context"]["profile_gate_statuses"]["predictability"][
        "evidence_fingerprint"
    ] = "predictability-evidence-a"
    first["research_context"]["profile_gate_statuses"]["financial_safety"][
        "evidence_fingerprint"
    ] = "financial-evidence-a"
    ledger = append_attempts(
        {},
        plan_strategy_attempts(first, {}, source_workflow_run_id="100"),
    )

    later = _row(fingerprint="fp-stable")
    later["research_context"]["profile_gate_statuses"]["predictability"][
        "evidence_fingerprint"
    ] = "predictability-evidence-b"
    later["research_context"]["profile_gate_statuses"]["financial_safety"][
        "evidence_fingerprint"
    ] = "financial-evidence-a"

    attempts = plan_strategy_attempts(
        later,
        ledger,
        source_workflow_run_id="101",
    )

    assert [item["hard_gate"] for item in attempts] == ["predictability"]


def test_financial_diagnostic_change_reactivates_financial_gate_strategy():
    first = _row(fingerprint="fp-stable")
    first["triage_context"] = {
        "valuation": {
            "financial_gate_diagnostics": {
                "cash_conversion_ratio": 0.70,
                "operating_cash_flow": 100.0,
            }
        }
    }
    ledger = append_attempts(
        {},
        plan_strategy_attempts(first, {}, source_workflow_run_id="100"),
    )

    later = _row(fingerprint="fp-stable")
    later["triage_context"] = {
        "valuation": {
            "financial_gate_diagnostics": {
                "cash_conversion_ratio": 0.78,
                "operating_cash_flow": 120.0,
            }
        }
    }
    attempts = plan_strategy_attempts(
        later,
        ledger,
        source_workflow_run_id="101",
    )

    assert [item["hard_gate"] for item in attempts] == ["financial_safety"]



def test_profile_unknowns_fill_empty_routing_gate_scope_without_researching_pass_or_fail():
    row = {
        "entity_id": "001316",
        "research_evidence_fingerprint": "fp-live",
        "research_context": {
            "unresolved_gates": [],
            "profile_gate_statuses": {
                "predictability": {"status": "UNKNOWN", "source": "AUTOMATIC_ATTEMPT"},
                "long_term_demand": {"status": "UNKNOWN", "source": "AUTOMATIC_ATTEMPT"},
                "moat": {"status": "UNKNOWN", "source": "AUTOMATIC_ATTEMPT"},
                "financial_safety": {"status": "PASS", "source": "AUTOMATIC_MACHINE"},
                "earnings_authenticity": {"status": "FAIL", "source": "AUTOMATIC_MACHINE"},
            },
        },
    }

    attempts = plan_strategy_attempts(row, {}, source_workflow_run_id="200")
    assert has_strategy_scope(row) is True
    assert {item["hard_gate"] for item in attempts} == {
        "predictability",
        "long_term_demand",
        "moat",
    }
    assert all(item["unresolved_reason"] == "PROFILE_GATE_STATUS_UNKNOWN" for item in attempts)


def test_profile_unknown_fallback_is_deduplicated_and_exhaustible():
    row = {
        "entity_id": "600406",
        "research_evidence_fingerprint": "fp-live",
        "research_context": {
            "unresolved_gates": [],
            "profile_gate_statuses": {
                gate: {
                    "status": "UNKNOWN",
                    "source": "AUTOMATIC_ATTEMPT",
                    "evidence_fingerprint": f"{gate}-same",
                }
                for gate in (
                    "predictability",
                    "long_term_demand",
                    "moat",
                    "financial_safety",
                    "earnings_authenticity",
                )
            },
            "deep_lambda_run_id": "900",
        },
    }
    attempts = plan_strategy_attempts(row, {}, source_workflow_run_id="200")
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
        item["deep_run_id"] = "900"
    ledger = append_attempts({}, attempts)

    reconciled = reconcile_ledger(
        ledger,
        [row],
        current_source_workflow_run_id="201",
    )
    assert len(reconciled["entries"]) == 5
    assert all(item["attempt_status"] == "EXHAUSTED_NO_PROGRESS" for item in reconciled["entries"])
    assert plan_strategy_attempts(
        row,
        reconciled,
        source_workflow_run_id="202",
    ) == []


def test_profile_workset_gap_blocks_attempt_without_false_exhaustion():
    initial = _row()
    attempts = plan_strategy_attempts(
        initial,
        {},
        source_workflow_run_id="100",
    )
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
        item["deep_run_id"] = "900"
    ledger = append_attempts({}, attempts)

    blocked = _row()
    blocked["research_context"]["deep_lambda_run_id"] = "900"
    blocked["research_context"]["unresolved_gates"].append(
        {
            "gate": "profile",
            "reason": "REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE",
        }
    )
    reconciled = reconcile_ledger(
        ledger,
        [blocked],
        current_source_workflow_run_id="101",
    )

    assert has_strategy_scope(blocked) is True
    assert all(
        item["attempt_status"] == "BLOCKED_WORKSET_COVERAGE"
        for item in reconciled["entries"]
    )
    assert all(item["strategy_exhausted"] is False for item in reconciled["entries"])
    assert all(item["new_evidence_acquired"] is None for item in reconciled["entries"])
    assert all(item["workset_coverage_blocked"] is True for item in reconciled["entries"])
    assert plan_strategy_attempts(
        blocked,
        reconciled,
        source_workflow_run_id="102",
    ) == []


def test_profile_workset_recovery_reopens_same_gate_epoch_after_blocked_dispatch():
    initial = _row()
    attempts = plan_strategy_attempts(initial, {}, source_workflow_run_id="100")
    for item in attempts:
        item["attempt_status"] = "DISPATCH_ACCEPTED"
        item["deep_run_id"] = "900"
    ledger = append_attempts({}, attempts)

    blocked = _row()
    blocked["research_context"]["deep_lambda_run_id"] = "900"
    blocked["research_context"]["unresolved_gates"].append(
        {
            "gate": "profile",
            "reason": "REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE",
        }
    )
    reconciled = reconcile_ledger(
        ledger,
        [blocked],
        current_source_workflow_run_id="101",
    )

    recovered = _row()
    retried = plan_strategy_attempts(
        recovered,
        reconciled,
        source_workflow_run_id="102",
    )

    assert {item["hard_gate"] for item in retried} == {
        "predictability",
        "financial_safety",
    }
    updated = append_attempts(reconciled, retried)
    assert len(updated["entries"]) == 4
    assert sum(
        item["attempt_status"] == "BLOCKED_WORKSET_COVERAGE"
        for item in updated["entries"]
    ) == 2
    assert sum(
        item["attempt_status"] == "DISPATCH_PLANNED"
        for item in updated["entries"]
    ) == 2


def test_exact_deep_pass_and_fail_override_stale_explicit_unresolved_scope():
    row = _row()
    row["research_context"]["profile_gate_statuses"]["predictability"]["status"] = "PASS"
    row["research_context"]["profile_gate_statuses"]["financial_safety"]["status"] = "FAIL"

    assert has_strategy_scope(row) is False
    assert plan_strategy_attempts(
        row,
        {},
        source_workflow_run_id="300",
    ) == []


def test_exact_deep_pass_removes_only_resolved_gates_from_live_like_scope():
    row = {
        "entity_id": "603105",
        "research_evidence_fingerprint": "fp-live-603105",
        "research_context": {
            "unresolved_gates": [
                {"gate": "earnings_authenticity", "reason": "RESEARCH_PRIORITY_MISSING_EVIDENCE"},
                {"gate": "financial_safety", "reason": "RESEARCH_PRIORITY_MISSING_EVIDENCE"},
                {
                    "gate": "long_term_demand",
                    "reason": "OFFICIAL_INDEPENDENT_CORROBORATION_THRESHOLD_NOT_MET",
                },
                {"gate": "moat", "reason": "DURABLE_MOAT_CORROBORATION_THRESHOLD_NOT_MET"},
                {"gate": "predictability", "reason": "RESEARCH_PRIORITY_MISSING_EVIDENCE"},
            ],
            "profile_gate_statuses": {
                "earnings_authenticity": {"status": "PASS", "source": "AUTOMATIC_MACHINE"},
                "financial_safety": {"status": "PASS", "source": "AUTOMATIC_MACHINE"},
                "long_term_demand": {"status": "UNKNOWN", "source": "AUTOMATIC_ATTEMPT"},
                "moat": {"status": "UNKNOWN", "source": "AUTOMATIC_ATTEMPT"},
                "predictability": {
                    "status": "PASS",
                    "source": "AUTOMATIC_STRICT_MULTI_YEAR_OFFICIAL_EVIDENCE_CLOSURE",
                },
            },
        },
    }

    attempts = plan_strategy_attempts(row, {}, source_workflow_run_id="301")

    assert {item["hard_gate"] for item in attempts} == {"long_term_demand", "moat"}
    assert all(
        item["unresolved_reason"]
        in {
            "OFFICIAL_INDEPENDENT_CORROBORATION_THRESHOLD_NOT_MET",
            "DURABLE_MOAT_CORROBORATION_THRESHOLD_NOT_MET",
        }
        for item in attempts
    )
