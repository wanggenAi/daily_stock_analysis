from copy import deepcopy

from src.strategies.genge_opportunity_discovery.jev_shadow import (
    CONTRACT,
    JevShadowConfig,
    build_stock_shadow_states,
    evaluate_stock_shadow,
    render_shadow_markdown,
)


def _dashboard():
    return {
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "stock_portfolio": {
            "rows": [
                {
                    "code": "600406",
                    "name": "国电南瑞",
                    "canonical_formal_action": "HOLD",
                    "formal_action_currently_usable": True,
                    "price_value_zone": "FAIR_VALUE",
                    "valuation_confidence": "HIGH",
                    "valuation_change": "STABLE",
                    "holding_add_authorized": False,
                    "reason_codes": "TEST",
                }
            ]
        },
    }


def _status():
    return {
        "execution_status": "SUCCESS",
        "research_terminal_state": "EVIDENCE_EXHAUSTED",
        "lambda_run_id": "123",
        "deep_code_epoch_sha": "abc",
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "unresolved_reasons": {
            "600406": {"predictability": "INSUFFICIENT_HISTORY"},
            "000001": {"moat": "NO_STRICT_MACHINE_RULE"},
        },
    }


def _profiles():
    return {
        "profiles": {
            "600406": {
                "gates": {
                    "financial_safety": {
                        "status": "PASS",
                        "confidence": "HIGH",
                        "source": "AUTOMATIC_MACHINE",
                    },
                    "predictability": {"status": "UNKNOWN"},
                }
            }
        }
    }


class FakeProvider:
    def __init__(self, *, fail_times=0):
        self.fail_times = fail_times
        self.calls = 0

    def evaluate(self, state, *, model, timeout_seconds):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError("simulated timeout")
        return {
            "model": "jev-1.13.0",
            "usage": {"input_tokens": 120, "output_tokens": 20},
            "decisions": {
                "needs_more_evidence": {
                    "type": "noul",
                    "probability": 0.93,
                    "answer": True,
                    "confidence": 0.86,
                },
                "needs_deep_research": {
                    "type": "noul",
                    "probability": 0.71,
                    "answer": True,
                    "confidence": 0.42,
                },
                "research_route": {
                    "type": "choice",
                    "choice": "EVIDENCE_REFRESH",
                    "confidence": 0.81,
                },
                "attention_priority": {
                    "type": "choice",
                    "choice": "HIGH",
                    "confidence": 0.77,
                },
                "evidence_state": {
                    "type": "choice",
                    "choice": "INSUFFICIENT",
                    "confidence": 0.91,
                },
            },
        }


def test_build_states_is_compact_and_does_not_mutate_authoritative_inputs():
    dashboard = _dashboard()
    status = _status()
    before_dashboard = deepcopy(dashboard)
    before_status = deepcopy(status)

    states = build_stock_shadow_states(
        dashboard=dashboard,
        deep_status=status,
        profiles=_profiles(),
        scope="combined",
        max_entities=10,
    )

    assert dashboard == before_dashboard
    assert status == before_status
    assert [row["entity"]["code"] for row in states] == ["600406", "000001"]
    holding = states[0]
    assert holding["existing_engine_action"] == "FORMAL:HOLD"
    assert holding["existing_needs_more_evidence"] is True
    assert holding["guardrails"]["jev_authority"] == "SHADOW_ONLY"
    assert holding["guardrails"]["no_auto_trade"] is True
    assert (
        holding["research_context"]["profile_gate_statuses"]["predictability"]["status"]
        == "UNKNOWN"
    )


def test_disabled_layer_is_a_clean_noop():
    payload = evaluate_stock_shadow(
        states=[],
        config=JevShadowConfig(enabled=False),
        provider=FakeProvider(),
    )
    assert payload["contract"] == CONTRACT
    assert payload["execution_status"] == "SKIPPED_DISABLED"
    assert payload["mutates_authoritative_decision"] is False
    assert payload["formal_trading_authority"] is False
    assert payload["no_auto_trade"] is True


def test_non_shadow_authority_is_refused():
    payload = evaluate_stock_shadow(
        states=[],
        config=JevShadowConfig(enabled=True, shadow_mode=False),
        provider=FakeProvider(),
    )
    assert payload["execution_status"] == "REFUSED_NON_SHADOW"
    assert payload["formal_trading_authority"] is False


def test_missing_secret_skips_without_importing_sdk(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=_status(),
        max_entities=1,
    )
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig(enabled=True, shadow_mode=True),
    )
    assert payload["execution_status"] == "SKIPPED_NO_SECRET"
    assert payload["rows"] == []
    assert payload["no_auto_trade"] is True


def test_fake_live_run_records_model_metrics_and_agreement():
    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=_status(),
        profiles=_profiles(),
        max_entities=1,
    )
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig(
            enabled=True,
            shadow_mode=True,
            model="jev-latest",
            timeout_seconds=1.0,
            max_retries=0,
        ),
        provider=FakeProvider(),
    )

    assert payload["execution_status"] == "SUCCESS"
    assert payload["rows"][0]["served_model"] == "jev-1.13.0"
    assert payload["rows"][0]["evidence_need_agrees_with_existing"] is True
    assert payload["summary"]["judgments"] == 5
    assert payload["summary"]["evidence_agreement_rate"] == 1.0
    assert payload["summary"]["served_models"] == {"jev-1.13.0": 1}
    assert payload["mutates_authoritative_decision"] is False


def test_provider_failure_retries_and_remains_shadow_only():
    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=_status(),
        max_entities=1,
    )
    provider = FakeProvider(fail_times=1)
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig(
            enabled=True,
            shadow_mode=True,
            max_retries=1,
        ),
        provider=provider,
    )
    assert provider.calls == 2
    assert payload["execution_status"] == "SUCCESS"
    assert payload["rows"][0]["attempt_count"] == 2
    assert payload["rows"][0]["formal_trading_authority"] is False


def test_terminal_provider_failure_is_diagnostic_not_authoritative():
    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=_status(),
        max_entities=1,
    )
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig(
            enabled=True,
            shadow_mode=True,
            max_retries=1,
        ),
        provider=FakeProvider(fail_times=5),
    )
    assert payload["execution_status"] == "FAILED"
    assert payload["rows"][0]["status"] == "TIMEOUT"
    assert payload["rows"][0]["decisions"] == {}
    assert payload["rows"][0]["mutates_authoritative_decision"] is False
    assert payload["unknown_is_pass"] is False


def test_markdown_makes_shadow_authority_visible():
    payload = evaluate_stock_shadow(
        states=build_stock_shadow_states(
            dashboard=_dashboard(),
            deep_status=_status(),
            max_entities=1,
        ),
        config=JevShadowConfig(enabled=True, shadow_mode=True),
        provider=FakeProvider(),
    )
    rendered = render_shadow_markdown(payload)
    assert "SHADOW ONLY" in rendered
    assert "authoritative decision mutation: **False**" in rendered
    assert "UNKNOWN != PASS" in rendered


def test_unresolved_selection_prefers_urgent_priority_and_quant_context():
    status = {
        "execution_status": "SUCCESS",
        "research_terminal_state": "EVIDENCE_EXHAUSTED",
        "unresolved_reasons": {
            "000001": {"moat": "UNKNOWN"},
            "000002": {"moat": "UNKNOWN"},
            "000003": {"moat": "UNKNOWN"},
            "000004": {"moat": "UNKNOWN"},
        },
    }
    research_decisions = {
        "terminal_rows": [
            {
                "code": "000001",
                "name": "普通候选",
                "research_decision": "RESEARCH_GAP",
                "quant_score": 90.0,
                "screening_attractiveness": "HIGH",
                "urgent_research": False,
            },
            {
                "code": "000002",
                "name": "紧急P2",
                "research_decision": "RESEARCH_GAP",
                "research_priority": "P2",
                "quant_score": 60.0,
                "screening_attractiveness": "HIGH",
                "urgent_research": True,
                "urgent_research_reasons": ["QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED"],
            },
            {
                "code": "000003",
                "name": "紧急P1",
                "research_decision": "RESEARCH_GAP",
                "research_priority": "P1",
                "quant_score": 55.0,
                "screening_attractiveness": "NORMAL",
                "urgent_research": True,
            },
            {
                "code": "000004",
                "name": "P1非紧急",
                "research_decision": "RESEARCH_GAP",
                "research_priority": "P1",
                "quant_score": 99.0,
                "screening_attractiveness": "HIGH",
                "urgent_research": False,
                "valuation": {
                    "current_pe": 12.0,
                    "historical_median_pe_reference": 24.0,
                    "pe_to_history_ratio": 0.5,
                },
            },
        ]
    }

    states = build_stock_shadow_states(
        dashboard={},
        deep_status=status,
        research_decisions=research_decisions,
        scope="unresolved",
        max_entities=4,
    )

    assert [row["entity"]["code"] for row in states] == [
        "000003",
        "000002",
        "000004",
        "000001",
    ]
    assert states[0]["triage_context"]["urgent_research"] is True
    assert states[0]["triage_context"]["research_priority"] == "P1"
    assert states[2]["triage_context"]["valuation"]["pe_to_history_ratio"] == 0.5


def test_live_row_carries_non_authoritative_triage_context():
    research_decisions = {
        "terminal_rows": [
            {
                "code": "600406",
                "name": "国电南瑞",
                "research_decision": "RESEARCH_GAP",
                "research_priority": "P1",
                "urgent_research": True,
                "urgent_research_reasons": ["TEST_URGENT"],
                "quant_status": "PRIORITY_RESEARCH",
                "quant_score": 88.0,
                "screening_attractiveness": "HIGH",
            }
        ]
    }
    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=_status(),
        research_decisions=research_decisions,
        max_entities=1,
    )
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig(enabled=True, shadow_mode=True),
        provider=FakeProvider(),
    )
    row = payload["rows"][0]
    assert row["triage_context"]["research_priority"] == "P1"
    assert row["triage_context"]["urgent_research"] is True
    assert row["triage_context"]["quant_score"] == 88.0
    assert row["mutates_authoritative_decision"] is False

def test_live_priority_queue_precedes_old_deep_unresolved_backlog():
    status = {
        "execution_status": "SUCCESS",
        "research_terminal_state": "EVIDENCE_EXHAUSTED",
        "unresolved_reasons": {
            "000099": {"moat": "OLD_DEEP_GAP"},
        },
    }
    priority = {
        "queue": [
            {
                "code": "600406",
                "name": "国电南瑞",
                "priority": "P0",
                "priority_score": 110,
            },
            {
                "code": "002042",
                "name": "华孚时尚",
                "priority": "P1",
                "priority_score": 50,
                "near_buy_evidence_recovery_tier": "B",
                "near_buy_missing_evidence_items": [
                    "hard_gate:predictability",
                    "hard_gate:moat",
                ],
                "reason_codes": ["NEAR_BUY_EVIDENCE_RECOVERY_B"],
            },
            {
                "code": "600916",
                "name": "中国黄金",
                "priority": "P1",
                "priority_score": 50,
                "near_buy_evidence_recovery_tier": "A",
                "near_buy_missing_evidence_items": ["hard_gate:long_term_demand"],
            },
        ]
    }

    states = build_stock_shadow_states(
        dashboard=_dashboard(),
        deep_status=status,
        research_priority=priority,
        scope="combined",
        max_entities=4,
    )

    assert [row["entity"]["code"] for row in states] == [
        "600406",
        "002042",
        "600916",
        "000099",
    ]
    huafu = states[1]
    assert huafu["existing_engine_action"] == "RESEARCH_PRIORITY:P1"
    assert huafu["existing_needs_more_evidence"] is True
    assert huafu["triage_context"]["research_priority"] == "P1"
    assert huafu["triage_context"]["research_priority_score"] == 50
    assert huafu["triage_context"]["near_buy_evidence_recovery_tier"] == "B"
    assert huafu["research_context"]["unresolved_gates"] == [
        {"gate": "moat", "reason": "RESEARCH_PRIORITY_MISSING_EVIDENCE"},
        {"gate": "predictability", "reason": "RESEARCH_PRIORITY_MISSING_EVIDENCE"},
    ]


def test_priority_queue_does_not_drop_deep_unresolved_continuity_when_capacity_allows():
    states = build_stock_shadow_states(
        dashboard={},
        deep_status={
            "unresolved_reasons": {
                "000001": {"moat": "UNKNOWN"},
                "000002": {"predictability": "UNKNOWN"},
            }
        },
        research_priority={
            "queue": [
                {"code": "000002", "name": "优先候选", "priority": "P1"},
            ]
        },
        scope="unresolved",
        max_entities=5,
    )

    assert [row["entity"]["code"] for row in states] == ["000002", "000001"]

