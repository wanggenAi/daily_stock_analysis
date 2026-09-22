from src.strategies.genge_opportunity_discovery.jev_research_orchestrator import (
    CONTRACT,
    build_orchestration_plan,
)


def _routing():
    return {
        "contract": "GEN_GE_JEV_ROUTING_BRIDGE_V1",
        "execution_status": "SUCCESS",
        "authority": "ADVISORY_RESEARCH_ROUTING_ONLY",
        "automatic_dispatch_allowed": False,
        "automatic_formal_buy_allowed": False,
        "formal_trading_authority": False,
        "mutates_authoritative_decision": False,
        "may_suppress_existing_research": False,
        "may_create_or_mutate_formal_action": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "source_workflow_run_id": "12345",
        "routing_queue": [
            {
                "entity_id": "600406",
                "entity_name": "国电南瑞",
                "is_current_holding": True,
                "existing_engine_action": "FORMAL:REDUCE_25",
                "route": "EVIDENCE_REFRESH",
                "route_confidence": 0.52,
                "attention_priority": "HIGH",
                "attention_confidence": 0.85,
                "evidence_state": "INSUFFICIENT",
                "needs_more_evidence": True,
                "needs_deep_research": True,
                "triage_context": {
                    "research_priority": "P0",
                    "urgent_research": True,
                },
            },
            {
                "entity_id": "000576",
                "entity_name": "甘化科工",
                "is_current_holding": False,
                "existing_engine_action": "RESEARCH:RESEARCH_GAP",
                "route": "DEEP_RESEARCH",
                "route_confidence": 0.70,
                "attention_priority": "HIGH",
                "evidence_state": "INSUFFICIENT",
                "triage_context": {
                    "research_priority": "P1",
                    "urgent_research": True,
                },
            },
            {
                "entity_id": "000001",
                "entity_name": "平安银行",
                "is_current_holding": False,
                "existing_engine_action": "RESEARCH:RESEARCH_GAP",
                "route": "EVIDENCE_REFRESH",
                "route_confidence": 0.82,
                "attention_priority": "HIGH",
                "evidence_state": "INSUFFICIENT",
                "triage_context": {
                    "research_priority": "",
                    "urgent_research": False,
                },
            },
            {
                "entity_id": "601318",
                "entity_name": "中国平安",
                "is_current_holding": True,
                "existing_engine_action": "FORMAL:HOLD",
                "route": "HUMAN_REVIEW",
                "route_confidence": 0.44,
                "attention_priority": "HIGH",
                "evidence_state": "CONFLICTED",
                "triage_context": {
                    "research_priority": "P0",
                    "urgent_research": True,
                },
            },
            {
                "entity_id": "000420",
                "entity_name": "吉林化纤",
                "is_current_holding": False,
                "existing_engine_action": "RESEARCH:REJECT",
                "route": "EVIDENCE_REFRESH",
                "route_confidence": 0.64,
                "attention_priority": "LOW",
                "evidence_state": "INSUFFICIENT",
                "triage_context": {
                    "research_priority": "P3",
                    "urgent_research": False,
                },
            },
        ],
    }


def test_plan_requires_jev_and_deterministic_triage_agreement():
    plan = build_orchestration_plan(_routing(), max_dispatch=12)
    assert plan["contract"] == CONTRACT
    assert plan["execution_status"] == "READY"
    assert plan["should_dispatch"] is True
    assert plan["requested_codes"] == ["600406", "000576"]
    assert [row["entity_id"] for row in plan["human_review"]] == ["601318"]
    assert plan["min_auto_route_confidence"] == 0.5
    assert {row["entity_id"] for row in plan["skipped"]} == {"000001", "000420"}
    assert plan["jev_direct_dispatch_allowed"] is False
    assert plan["automatic_research_dispatch_allowed"] is True
    assert plan["formal_trading_authority"] is False
    assert plan["no_auto_trade"] is True


def test_plan_is_bounded_and_holding_stays_first():
    payload = _routing()
    payload["routing_queue"].insert(
        1,
        {
            "entity_id": "603055",
            "entity_name": "台华新材",
            "is_current_holding": False,
            "existing_engine_action": "RESEARCH:RESEARCH_GAP",
            "route": "DEEP_RESEARCH",
            "route_confidence": 0.95,
            "attention_priority": "HIGH",
            "evidence_state": "INSUFFICIENT",
            "triage_context": {"research_priority": "P1", "urgent_research": True},
        },
    )
    plan = build_orchestration_plan(payload, max_dispatch=2)
    assert plan["requested_codes"][0] == "600406"
    assert len(plan["requested_codes"]) == 2
    assert any(row["reason"] == "MAX_DISPATCH_BOUND" for row in plan["skipped"])


def test_plan_refuses_authority_drift():
    payload = _routing()
    payload["formal_trading_authority"] = True
    plan = build_orchestration_plan(payload)
    assert plan["execution_status"] == "REFUSED_ROUTING_GUARDRAIL_MISMATCH"
    assert plan["should_dispatch"] is False
    assert plan["requested_codes"] == []


def test_no_eligible_rows_is_healthy_noop():
    payload = _routing()
    for row in payload["routing_queue"]:
        row["route"] = "NO_ESCALATION"
    plan = build_orchestration_plan(payload)
    assert plan["execution_status"] == "NOOP"
    assert plan["should_dispatch"] is False
    assert plan["requested_codes_csv"] == ""


def test_workflow_auto_chains_research_without_trading_authority():
    from pathlib import Path

    workflow = Path(".github/workflows/genge-jev-research-orchestrator.yml").read_text(
        encoding="utf-8"
    )
    assert '"GenGe Jev Shadow Evaluation"' in workflow
    assert "actions: write" in workflow
    assert "gh workflow run genge-v31-deep-calculation-lambda.yml" in workflow
    assert "JEV_ORCHESTRATOR_" in workflow
    assert "ORCHESTRATION_PENDING" in workflow
    assert "DEEP_DISPATCH_ACCEPTED" in workflow
    assert "Formal trading authority=false" in workflow
    assert "no_auto_trade=true" in workflow


def test_low_or_missing_route_confidence_falls_back_for_ruleable_evidence_refresh():
    payload = _routing()
    payload["routing_queue"][0]["route_confidence"] = 0.49
    payload["routing_queue"][1].pop("route_confidence", None)

    plan = build_orchestration_plan(payload, max_dispatch=12)

    assert plan["requested_codes"] == ["600406", "000576"]
    selected = {row["entity_id"]: row for row in plan["selected"]}
    assert selected["600406"]["dispatch_mode"] == "DETERMINISTIC_SAFE_FALLBACK"
    assert selected["600406"]["fallback_reason"] == "LOW_OR_MISSING_JEV_ROUTE_CONFIDENCE"
    assert selected["000576"]["dispatch_mode"] == "DETERMINISTIC_SAFE_FALLBACK"
    assert plan["summary"]["deterministic_fallback_count"] == 2
    reviews = {row["entity_id"]: row for row in plan["human_review"]}
    assert reviews["601318"]["review_reason"] == "JEV_ROUTE_HUMAN_REVIEW"
    assert plan["formal_trading_authority"] is False
    assert plan["no_auto_trade"] is True


def test_ruleable_insufficient_human_review_route_uses_safe_deterministic_fallback():
    payload = _routing()
    review = payload["routing_queue"][3]
    review["evidence_state"] = "INSUFFICIENT"
    review["needs_more_evidence"] = True

    plan = build_orchestration_plan(payload, max_dispatch=12)

    selected = {row["entity_id"]: row for row in plan["selected"]}
    row = selected["601318"]
    assert row["jev_route"] == "HUMAN_REVIEW"
    assert row["route"] == "EVIDENCE_REFRESH"
    assert row["dispatch_mode"] == "DETERMINISTIC_SAFE_FALLBACK"
    assert (
        row["fallback_reason"]
        == "RULEABLE_INSUFFICIENT_EVIDENCE_DOES_NOT_REQUIRE_HUMAN_STOP"
    )
    assert "601318" not in {row["entity_id"] for row in plan["human_review"]}


def test_conflicted_human_review_route_remains_human_review():
    plan = build_orchestration_plan(_routing(), max_dispatch=12)

    reviews = {row["entity_id"]: row for row in plan["human_review"]}
    assert reviews["601318"]["evidence_state"] == "CONFLICTED"
    assert reviews["601318"]["review_reason"] == "JEV_ROUTE_HUMAN_REVIEW"
    assert "601318" not in plan["requested_codes"]

def _scoped_routing(*, fingerprint="fp-1", source_run="200", deep_run=""):
    payload = _routing()
    payload["source_workflow_run_id"] = source_run
    row = payload["routing_queue"][1]
    row["research_evidence_fingerprint"] = fingerprint
    row["research_context"] = {
        "deep_lambda_run_id": deep_run,
        "unresolved_gates": [
            {
                "gate": "predictability",
                "reason": "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
            }
        ],
    }
    return payload


def test_strategy_ledger_suppresses_same_strategy_in_same_evidence_epoch():
    first = build_orchestration_plan(_scoped_routing(), max_dispatch=12)
    assert "000576" in first["requested_codes"]
    assert first["summary"]["strategy_attempt_count"] == 1

    ledger = first["strategy_ledger"]
    prior_predictability_epoch = next(
        entry["evidence_fingerprint"]
        for entry in ledger["entries"]
        if entry["code"] == "000576" and entry["hard_gate"] == "predictability"
    )
    for entry in ledger["entries"]:
        if entry["code"] == "000576":
            entry["attempt_status"] = "DISPATCH_ACCEPTED"
            entry["deep_run_id"] = "900"

    later_payload = _scoped_routing(source_run="201", deep_run="900")
    later = build_orchestration_plan(
        later_payload,
        max_dispatch=12,
        strategy_ledger=ledger,
    )

    assert "000576" not in later["requested_codes"]
    assert any(
        row.get("entity_id") == "000576"
        and row.get("reason") == "NO_NOVEL_RESEARCH_STRATEGY_IN_EVIDENCE_EPOCH"
        for row in later["skipped"]
    )
    exhausted = [
        entry
        for entry in later["strategy_ledger"]["entries"]
        if entry["code"] == "000576"
    ]
    assert exhausted
    assert all(entry["attempt_status"] == "EXHAUSTED_NO_PROGRESS" for entry in exhausted)


def test_new_evidence_epoch_reopens_same_supported_strategy():
    first = build_orchestration_plan(_scoped_routing(), max_dispatch=12)
    ledger = first["strategy_ledger"]
    for entry in ledger["entries"]:
        if entry["code"] == "000576":
            entry["attempt_status"] = "DISPATCH_ACCEPTED"
            entry["deep_run_id"] = "900"

    changed_payload = _scoped_routing(
        fingerprint="fp-2",
        source_run="202",
        deep_run="900",
    )
    changed_payload["routing_queue"][1]["research_context"]["unresolved_gates"][0][
        "reason"
    ] = "MULTI_YEAR_POSITIVITY_NOT_PROVEN"
    changed = build_orchestration_plan(
        changed_payload,
        max_dispatch=12,
        strategy_ledger=ledger,
    )

    assert "000576" in changed["requested_codes"]
    attempts = [
        attempt
        for row in changed["selected"]
        if row["entity_id"] == "000576"
        for attempt in row.get("strategy_attempts") or []
    ]
    assert len(attempts) == 1
    assert attempts[0]["evidence_fingerprint"] != prior_predictability_epoch
    assert attempts[0]["stock_evidence_fingerprint"] == "fp-2"
    assert attempts[0]["hard_gate"] == "predictability"


def test_workflow_persists_strategy_ledger_only_after_deep_acceptance():
    from pathlib import Path

    workflow = Path(".github/workflows/genge-jev-research-orchestrator.yml").read_text(
        encoding="utf-8"
    )
    assert "--strategy-ledger-json data/jev_shadow/research_strategy_ledger.json" in workflow
    assert 'plan.pop("strategy_ledger", None)' in workflow
    assert 'entry["attempt_status"] = "DISPATCH_ACCEPTED"' in workflow
    assert "data/jev_shadow/research_strategy_ledger.json" in workflow

