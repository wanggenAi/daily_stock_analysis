from pathlib import Path

from src.strategies.genge_opportunity_discovery.jev_routing_bridge import (
    CONTRACT,
    build_routing_bridge,
    render_routing_markdown,
)


def _shadow():
    return {
        "contract": "GEN_GE_JEV_SHADOW_DECISION_V1",
        "generated_at": "2026-09-21T00:00:00+00:00",
        "execution_status": "SUCCESS",
        "authority": "SHADOW_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "mutates_authoritative_decision": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "shadow_mode": True,
        "requested_model": "jev-latest",
        "rows": [
            {
                "entity_id": "600406",
                "entity_name": "国电南瑞",
                "is_current_holding": True,
                "existing_engine_action": "FORMAL:HOLD",
                "triage_context": {"research_priority": "P1", "urgent_research": True},
                "state_fingerprint": "abc",
                "status": "SUCCESS",
                "served_model": "jev-1.13.0",
                "formal_trading_authority": False,
                "mutates_authoritative_decision": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
                "decisions": {
                    "needs_more_evidence": {
                        "type": "noul",
                        "answer": True,
                        "confidence": 0.9,
                    },
                    "needs_deep_research": {
                        "type": "noul",
                        "answer": False,
                        "confidence": 0.7,
                    },
                    "research_route": {
                        "type": "choice",
                        "choice": "EVIDENCE_REFRESH",
                        "confidence": 0.82,
                        "probabilities": {
                            "NO_ESCALATION": 0.03,
                            "EVIDENCE_REFRESH": 0.72,
                            "DEEP_RESEARCH": 0.15,
                            "HUMAN_REVIEW": 0.10,
                        },
                    },
                    "attention_priority": {
                        "type": "choice",
                        "choice": "HIGH",
                        "confidence": 0.76,
                        "probabilities": {
                            "LOW": 0.04,
                            "MEDIUM": 0.16,
                            "HIGH": 0.80,
                        },
                    },
                    "evidence_state": {
                        "type": "choice",
                        "choice": "INSUFFICIENT",
                        "confidence": 0.91,
                        "probabilities": {
                            "ADEQUATE_FOR_CURRENT_RESEARCH_STATE": 0.02,
                            "INSUFFICIENT": 0.94,
                            "CONFLICTED": 0.03,
                            "STALE_OR_LINEAGE_UNCLEAR": 0.01,
                        },
                    },
                },
            },
            {
                "entity_id": "000001",
                "entity_name": "平安银行",
                "is_current_holding": False,
                "existing_engine_action": "RESEARCH_ONLY",
                "state_fingerprint": "def",
                "status": "SUCCESS",
                "served_model": "jev-1.13.0",
                "formal_trading_authority": False,
                "mutates_authoritative_decision": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
                "decisions": {
                    "needs_more_evidence": {
                        "type": "noul",
                        "answer": False,
                        "confidence": 0.8,
                    },
                    "needs_deep_research": {
                        "type": "noul",
                        "answer": True,
                        "confidence": 0.6,
                    },
                    "research_route": {
                        "type": "choice",
                        "choice": "DEEP_RESEARCH",
                        "confidence": 0.77,
                    },
                    "attention_priority": {
                        "type": "choice",
                        "choice": "MEDIUM",
                        "confidence": 0.71,
                    },
                    "evidence_state": {
                        "type": "choice",
                        "choice": "CONFLICTED",
                        "confidence": 0.66,
                    },
                },
            },
        ],
    }


def test_bridge_builds_sorted_advisory_queue_without_authority():
    payload = build_routing_bridge(_shadow())
    assert payload["contract"] == CONTRACT
    assert payload["execution_status"] == "SUCCESS"
    assert [row["entity_id"] for row in payload["routing_queue"]] == ["600406", "000001"]
    assert payload["routing_queue"][0]["route"] == "EVIDENCE_REFRESH"
    assert payload["routing_queue"][0]["triage_context"]["research_priority"] == "P1"
    assert payload["routing_queue"][0]["triage_context"]["urgent_research"] is True
    assert payload["routing_queue"][0]["route_probabilities"]["EVIDENCE_REFRESH"] == 0.72
    assert payload["routing_queue"][0]["attention_probabilities"]["HIGH"] == 0.8
    assert payload["routing_queue"][0]["evidence_state_probabilities"]["INSUFFICIENT"] == 0.94
    assert payload["summary"]["actionable_research_count"] == 2
    assert payload["automatic_dispatch_allowed"] is False
    assert payload["automatic_formal_buy_allowed"] is False
    assert payload["formal_trading_authority"] is False
    assert payload["may_suppress_existing_research"] is False
    assert payload["may_create_or_mutate_formal_action"] is False
    assert payload["unknown_is_pass"] is False
    assert payload["no_auto_trade"] is True


def test_bridge_refuses_non_success_shadow():
    shadow = _shadow()
    shadow["execution_status"] = "FAILED"
    payload = build_routing_bridge(shadow)
    assert payload["execution_status"] == "REFUSED_SHADOW_NOT_SUCCESS"
    assert payload["routing_queue"] == []


def test_bridge_refuses_global_guardrail_drift():
    shadow = _shadow()
    shadow["mutates_authoritative_decision"] = True
    payload = build_routing_bridge(shadow)
    assert payload["execution_status"] == "REFUSED_GUARDRAIL_MISMATCH"
    assert payload["routing_queue"] == []


def test_row_guardrail_drift_is_excluded_not_promoted():
    shadow = _shadow()
    shadow["rows"][0]["formal_trading_authority"] = True
    payload = build_routing_bridge(shadow)
    assert [row["entity_id"] for row in payload["routing_queue"]] == ["000001"]
    assert payload["invalid_rows"] == [
        {"entity_id": "600406", "reason": "ROW_GUARDRAIL_MISMATCH"}
    ]


def test_markdown_labels_advisory_authority():
    rendered = render_routing_markdown(build_routing_bridge(_shadow()))
    assert "ADVISORY RESEARCH ROUTING ONLY" in rendered
    assert "automatic dispatch: **False**" in rendered
    assert "may suppress deterministic research: **False**" in rendered


def test_workflow_keeps_write_permission_out_of_live_pr_job():
    workflow = Path(".github/workflows/genge-jev-shadow-evaluation.yml").read_text(
        encoding="utf-8"
    )
    assert "persist-routing-advisory:" in workflow
    live = workflow.split("  live-shadow:", 1)[1].split(
        "  persist-routing-advisory:", 1
    )[0]
    persist = workflow.split("  persist-routing-advisory:", 1)[1]
    assert "contents: read" in live
    assert "contents: write" not in live
    assert "if: github.event_name == 'workflow_dispatch'" in persist
    assert "contents: write" in persist
