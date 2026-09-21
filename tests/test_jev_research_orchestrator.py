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
