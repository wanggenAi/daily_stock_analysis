from src.strategies.genge_opportunity_discovery.three_pillar_decision_center_runtime import (
    build_runtime_decision_center,
    choose_deep_review_config,
    normalize_runtime,
    render_runtime_markdown,
)


def _dashboard():
    return {
        "no_auto_trade": True,
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "latest_trade_date": "2026-09-07",
        "canonical_snapshot_id": "snap-1",
        "stock_portfolio": {
            "status": "CONFIRMED",
            "rows": [
                {
                    "code": "600406",
                    "name": "国电南瑞",
                    "quantity": 200,
                    "average_cost": 23.1,
                    "current_price": 22.5,
                    "pnl_pct": -2.6,
                    "formal_action": "HOLD",
                    "investor_action": "继续持有",
                    "neutral_value": 24.0,
                    "valuation_confidence": "HIGH",
                    "reason_codes": "TEST",
                    "holding_add_authorized": False,
                }
            ],
        },
        "capital_direction": {"strongest_industries": []},
        "terminal_opportunities": {
            "available": True,
            "buy_now": [],
            "wait_price": [],
            "reject_count": 1,
            "invalid_unauthorized_buy_count": 0,
        },
    }


def _era():
    return {
        "formal_trading_authority": False,
        "no_auto_trade": True,
        "research_as_of": "2026-09-08T00:00:00Z",
        "trends": [],
    }


def _automatic_profiles():
    return {
        "contract": "GEN_GE_V31_AUTOMATIC_DEEP_CALC_V1",
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "profiles": {
            "600406": {
                "gates": {
                    "predictability": {"status": "UNKNOWN", "rationale": "needs evidence", "evidence": []},
                    "long_term_demand": {"status": "UNKNOWN", "rationale": "needs evidence", "evidence": []},
                    "moat": {"status": "UNKNOWN", "rationale": "needs evidence", "evidence": []},
                    "financial_safety": {"status": "PASS", "rationale": "PIT machine", "evidence": [{"source_type": "SAME_RUN_PIT_MACHINE"}]},
                    "earnings_authenticity": {"status": "PASS", "rationale": "PIT machine", "evidence": [{"source_type": "SAME_RUN_PIT_MACHINE"}]},
                }
            }
        },
    }


def _status():
    return {
        "execution_status": "SUCCESS",
        "research_outcome": "PARTIAL_GAPS_REMAIN",
        "run_state": "COMPLETED",
        "lambda_run_id": "987654",
        "source_run_id": "123456",
        "trigger_source": "HOLDINGS_CHANGE",
        "requested_count": 1,
        "processed_requested_count": 1,
        "complete_requested_count": 0,
        "partial_requested_count": 1,
        "unresolved_requested_gate_count": 3,
        "missing_requested_codes": [],
    }


def _terminal_status():
    return {
        "execution_status": "SUCCESS",
        "research_outcome": "EVIDENCE_EXHAUSTED",
        "research_terminal_state": "EVIDENCE_EXHAUSTED",
        "run_state": "COMPLETED",
        "lambda_run_id": "999999",
        "requested_count": 1,
        "complete_requested_count": 0,
        "evidence_exhausted_requested_count": 1,
        "unresolved_requested_gate_count": 2,
        "unresolved_reasons": {
            "600406": {
                "predictability": "NO_STRICT_MULTI_YEAR_PREDICTABILITY_RULE_PROVEN",
                "moat": "NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE",
            }
        },
        "gap_closure_attempt_count": 2,
        "new_evidence_count": 3,
        "progressed_gate_count": 1,
        "immediate_retry_required": False,
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
    }


def test_automatic_profiles_take_precedence_over_static_bootstrap():
    selected, source = choose_deep_review_config(
        _automatic_profiles(),
        {"profiles": {"600406": {"gates": {"predictability": {"status": "PASS"}}}}},
    )
    assert source == "AUTOMATIC_DEEP_CALCULATION"
    assert selected["profiles"]["600406"]["gates"]["predictability"]["status"] == "UNKNOWN"


def test_execution_success_and_research_completeness_are_separate():
    runtime = normalize_runtime(_status())
    assert runtime["execution_completed"] is True
    assert runtime["execution_succeeded"] is True
    assert runtime["research_complete"] is False
    assert runtime["unresolved_requested_gate_count"] == 3
    assert runtime["unknown_is_pass"] is False


def test_evidence_exhausted_is_terminal_without_requiring_manual_next_round():
    runtime = normalize_runtime(_terminal_status())
    assert runtime["execution_succeeded"] is True
    assert runtime["research_process_terminal"] is True
    assert runtime["research_complete"] is False
    assert runtime["research_terminal_state"] == "EVIDENCE_EXHAUSTED"
    assert runtime["manual_next_round_required"] is False
    assert runtime["processed_requested_count"] == 1
    assert runtime["partial_requested_count"] == 1
    assert runtime["gap_closure_attempt_count"] == 2
    assert runtime["new_evidence_count"] == 3
    assert runtime["progressed_gate_count"] == 1
    assert "600406" in runtime["unresolved_reasons"]


def test_runtime_is_exposed_in_final_decision_center():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_status(),
        industry_links={},
        era_handoff={},
        generated_at="2026-09-08T05:00:00Z",
    )
    assert out["deep_review_profile_source"] == "AUTOMATIC_DEEP_CALCULATION"
    assert out["deep_calculation_runtime"]["lambda_run_id"] == "987654"
    assert out["deep_calculation_runtime"]["execution_status"] == "SUCCESS"
    assert out["deep_calculation_runtime"]["research_outcome"] == "PARTIAL_GAPS_REMAIN"
    assert out["decision_readiness"]["deep_calculation_last_run_successful"] is True
    assert out["decision_readiness"]["deep_calculation_requested_research_complete"] is False
    deep = out["pillar_1_holdings_deep_analysis"]["rows"][0]["deep_review"]
    assert deep["status"] == "DEEP_REVIEW_PARTIAL"
    assert deep["pass_count"] == 2
    assert deep["unknown_count"] == 3


def test_terminal_runtime_is_visible_in_markdown_with_unresolved_reasons():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        industry_links={},
        era_handoff={},
    )
    md = render_runtime_markdown(out)
    assert "## 自动深算运行状态" in md
    assert "999999" in md
    assert "SUCCESS" in md
    assert "EVIDENCE_EXHAUSTED" in md
    assert "NO_STRICT_MULTI_YEAR_PREDICTABILITY_RULE_PROVEN" in md
    assert "是否需要你手工开启下一轮：**False**" in md
    assert "执行 SUCCESS 不等于研究 COMPLETE" in md


def test_runtime_markdown_makes_finished_but_partial_obvious():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_status(),
        industry_links={},
        era_handoff={},
    )
    md = render_runtime_markdown(out)
    assert "## 自动深算运行状态" in md
    assert "987654" in md
    assert "SUCCESS" in md
    assert "PARTIAL_GAPS_REMAIN" in md
    assert "执行 SUCCESS 不等于研究 COMPLETE" in md
