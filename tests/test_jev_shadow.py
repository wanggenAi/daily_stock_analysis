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
