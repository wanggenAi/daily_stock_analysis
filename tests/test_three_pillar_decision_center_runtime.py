from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.three_pillar_decision_center_runtime import (
    build_runtime_decision_center,
    choose_deep_review_config,
    normalize_runtime,
    normalize_terminal_research,
    render_runtime_markdown,
    select_latest_deep_calculation_status,
    summarize_era_evidence,
    summarize_candidate_lifecycle,
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


def _era_evidence():
    return {
        "schema_version": "ERA_RADAR_EVIDENCE_BUNDLE_V1",
        "records": [
            {"family": "POLICY_CAPITAL"},
            {"family": "REAL_DEMAND"},
            {"family": "REAL_DEMAND"},
            {"family": "GLOBAL_STRUCTURE"},
        ],
    }


def _automatic_profiles():
    return {
        "contract": "GEN_GE_V31_AUTOMATIC_DEEP_CALC_V1",
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "lambda_run_id": "987654",
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


def _partial_status():
    return {
        "contract": "GEN_GE_V31_DEEP_PARTIAL_CHECKPOINT_V1",
        "execution_status": "PARTIAL",
        "research_terminal_state": "NOT_COMPLETED",
        "research_outcome": "INITIAL_PASS_PRESERVED",
        "generated_at": "2026-09-19T02:39:24+00:00",
        "lambda_run_id": "1000001",
        "source_run_id": "123456",
        "trigger_source": "EVIDENCE_LAYER_CHANGE",
        "initial_pass_complete": True,
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
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


def _terminal_research(lambda_run_id="999999"):
    row = {
        "code": "600406",
        "name": "国电南瑞",
        "industry": "I65软件和信息技术服务业",
        "research_decision": "RESEARCH_GAP",
        "research_reason": "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY",
        "research_authority": "RESEARCH_ONLY",
        "formal_buy_authorized": False,
        "no_auto_trade": True,
        "hard_gate_pass_count": 2,
        "hard_gate_failures": [],
        "hard_gate_unknowns": ["predictability", "moat"],
        "reopen_on_new_evidence": True,
        "quant_score": 75.0,
        "screening_attractiveness": "HIGH",
        "valuation": {"pe_to_history_ratio": 0.7},
    }
    return {
        "contract": "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1",
        "generated_at": "2026-09-09T00:00:00+00:00",
        "source_deep_lambda_run_id": lambda_run_id,
        "source_every_industry_run_id": "123456",
        "requested_count": 1,
        "decision_counts": {"BUY": 0, "WAIT_PRICE": 0, "RESEARCH_GAP": 1, "REJECT": 0},
        "all_requested_terminal": True,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "terminal_rows": [row],
        "urgent_research_queue": [row],
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


def test_handoff_incomplete_is_terminal_but_not_research_complete():
    status = _terminal_status()
    status.update(
        {
            "research_outcome": "HANDOFF_INCOMPLETE",
            "research_terminal_state": "HANDOFF_INCOMPLETE",
            "requested_count": 2,
            "profile_count": 1,
            "requested_profile_count": 1,
            "processed_requested_count": 1,
            "partial_requested_count": 1,
            "evidence_exhausted_requested_count": 1,
            "handoff_incomplete_requested_count": 1,
            "missing_requested_codes": ["600406"],
            "workset_coverage_known": True,
            "workset_coverage_complete": False,
        }
    )
    runtime = normalize_runtime(status)

    assert runtime["execution_succeeded"] is True
    assert runtime["research_process_terminal"] is True
    assert runtime["research_complete"] is False
    assert runtime["research_terminal_state"] == "HANDOFF_INCOMPLETE"
    assert runtime["manual_next_round_required"] is False
    assert runtime["requested_count"] == 2
    assert runtime["processed_requested_count"] == 1
    assert runtime["evidence_exhausted_requested_count"] == 1
    assert runtime["handoff_incomplete_requested_count"] == 1
    assert runtime["missing_requested_codes"] == ["600406"]
    assert runtime["workset_coverage_complete"] is False


def test_terminal_research_contract_preserves_authority_separation():
    terminal = normalize_terminal_research(_terminal_research())
    assert terminal["available"] is True
    assert terminal["requested_count"] == 1
    assert terminal["decision_counts"] == {"BUY": 0, "WAIT_PRICE": 0, "RESEARCH_GAP": 1, "REJECT": 0}
    assert terminal["research_gap_count"] == 1
    assert terminal["research_reject_count"] == 0
    assert terminal["formal_trading_authority"] is False
    assert terminal["automatic_formal_buy_allowed"] is False
    assert terminal["unknown_is_pass"] is False
    assert terminal["no_auto_trade"] is True


def test_terminal_research_rejects_formal_buy_escalation():
    payload = _terminal_research()
    payload["terminal_rows"][0]["formal_buy_authorized"] = True
    with pytest.raises(ValueError, match="Formal BUY"):
        normalize_terminal_research(payload)


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
    assert out["deep_review_profile_current_for_runtime"] is True
    assert out["deep_review_profile_lineage_state"] == "CURRENT"
    deep = out["pillar_1_holdings_deep_analysis"]["rows"][0]["deep_review"]
    assert deep["status"] == "DEEP_REVIEW_PARTIAL"
    assert deep["pass_count"] == 2
    assert deep["unknown_count"] == 3


def test_matching_terminal_research_is_exposed_separately_from_formal_actions():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        terminal_research_decisions=_terminal_research(),
        industry_links={},
        era_handoff={},
    )
    pillar = out["pillar_3_deep_opportunities"]
    terminal = pillar["terminal_research_snapshot"]
    assert terminal["available"] is True
    assert terminal["current_for_deep_runtime"] is True
    assert pillar["research_terminal_current"] is True
    assert pillar["research_buy"] == []
    assert pillar["research_wait_price"] == []
    assert pillar["research_gap_count"] == 1
    assert pillar["research_reject_count"] == 0
    assert len(pillar["urgent_evidence_queue"]) == 1
    assert pillar["canonical_formal_buy_now"] == []
    assert pillar["canonical_formal_wait_price"] == []
    assert out["executive_summary"]["research_terminal_requested_count"] == 1
    assert out["executive_summary"]["research_gap_count"] == 1
    assert out["executive_summary"]["research_reject_count"] == 0
    assert out["decision_readiness"]["terminal_research_current_for_deep_runtime"] is True
    assert pillar["research_gap"][0]["account_action"] == "DO_NOT_BUY_YET"
    assert "暂不买" in pillar["research_gap"][0]["investor_action"]
    assert "predictability" in pillar["research_gap"][0]["investor_action"]
    assert out["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert out["no_auto_trade"] is True



def test_current_terminal_probe_is_exposed_as_manual_risk_budget_not_formal_buy():
    terminal = _terminal_research()
    capital = {
        "model_version": "GEN_GE_RISK_BUDGET_CAPITAL_V1",
        "action": "PROBE",
        "reason": "BOUNDED_UNCERTAINTY_WITH_VALUATION_MARGIN",
        "authority": "ADVISORY_ONLY",
        "automatic_execution_allowed": False,
        "formal_buy_authorized": False,
        "no_auto_trade": True,
        "capital_conviction_score": 0.71,
        "suggested_max_portfolio_pct": 1.1,
    }
    terminal["terminal_rows"][0]["capital_allocation"] = capital
    terminal["urgent_research_queue"][0]["capital_allocation"] = capital
    terminal["capital_model_version"] = "GEN_GE_RISK_BUDGET_CAPITAL_V1"
    terminal["capital_action_counts"] = {"BUILD": 0, "PROBE": 1, "WATCH": 0, "BLOCK": 0}
    terminal["capital_probe_queue"] = [terminal["terminal_rows"][0]]
    terminal["capital_advisory_authority"] = "ADVISORY_ONLY"
    terminal["capital_advisory_automatic_execution_allowed"] = False

    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        terminal_research_decisions=terminal,
        industry_links={},
        era_handoff={},
    )
    pillar = out["pillar_3_deep_opportunities"]
    assert pillar["research_gap_count"] == 1
    assert pillar["research_capital_probe_count"] == 1
    assert pillar["research_capital_probe"][0]["account_action"] == "MANUAL_PROBE_ADVISORY"
    assert "1.10%" in pillar["research_capital_probe"][0]["investor_action"]
    assert pillar["research_capital_probe"][0]["formal_buy_authorized"] is False
    assert out["executive_summary"]["research_capital_probe_count"] == 1
    assert out["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert out["no_auto_trade"] is True

    md = render_runtime_markdown(out)
    assert "风险预算层 BUILD/PROBE 候选：**1**" in md
    assert "建议账户上限=1.1%" in md


def test_capital_advisory_cannot_escalate_execution_authority():
    terminal = _terminal_research()
    terminal["terminal_rows"][0]["capital_allocation"] = {
        "action": "PROBE",
        "authority": "ADVISORY_ONLY",
        "automatic_execution_allowed": True,
        "formal_buy_authorized": False,
        "no_auto_trade": True,
    }
    terminal["capital_action_counts"] = {"BUILD": 0, "PROBE": 1, "WATCH": 0, "BLOCK": 0}

    with pytest.raises(ValueError, match="automatic execution"):
        normalize_terminal_research(terminal)

def test_stale_terminal_research_is_not_exposed_as_current_actionable_research():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        terminal_research_decisions=_terminal_research(lambda_run_id="888888"),
        industry_links={},
        era_handoff={},
    )
    pillar = out["pillar_3_deep_opportunities"]
    terminal = pillar["terminal_research_snapshot"]
    assert terminal["available"] is True
    assert terminal["stale_for_deep_runtime"] is True
    assert terminal["current_for_deep_runtime"] is False
    assert pillar["research_buy"] == []
    assert pillar["research_wait_price"] == []
    assert pillar["research_gap_count"] == 0
    assert pillar["research_reject_count"] == 0
    assert pillar["urgent_evidence_queue"] == []
    assert out["decision_readiness"]["terminal_research_snapshot_available"] is True
    assert out["decision_readiness"]["terminal_research_current_for_deep_runtime"] is False


def test_terminal_runtime_is_visible_in_markdown_with_unresolved_reasons():
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        terminal_research_decisions=_terminal_research(),
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
    assert "## 深算终态研究决策" in md
    assert "与当前 Deep Lambda 一致：**True**" in md
    assert "研究 RESEARCH_GAP：**1**" in md
    assert "研究 REJECT：**0**" in md
    assert "600406 国电南瑞" in md
    assert "Formal/Production 权限严格分离" in md


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
    assert "## 深算终态研究决策" in md
    assert "终态快照存在：**False**" in md



def test_newer_partial_checkpoint_overrides_older_terminal_status_for_current_runtime():
    terminal = _terminal_status()
    terminal["generated_at"] = "2026-09-19T01:49:27+00:00"
    selected, source = select_latest_deep_calculation_status(terminal, _partial_status())
    assert source == "PARTIAL_CHECKPOINT"
    assert selected["lambda_run_id"] == "1000001"

    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=terminal,
        partial_deep_calculation_status=_partial_status(),
        terminal_research_decisions=_terminal_research(),
        industry_links={},
        era_handoff={},
    )
    runtime = out["deep_calculation_runtime"]
    assert runtime["lambda_run_id"] == "1000001"
    assert runtime["execution_status"] == "PARTIAL"
    assert runtime["run_state"] == "PARTIAL_CHECKPOINT"
    assert runtime["status_source"] == "PARTIAL_CHECKPOINT"
    assert runtime["last_terminal_run_id"] == "999999"
    assert out["decision_readiness"]["deep_calculation_last_run_successful"] is False
    assert out["deep_review_profile_current_for_runtime"] is False
    assert out["deep_review_profile_lineage_state"] == "STALE_LAST_TERMINAL"
    holdings = out["pillar_1_holdings_deep_analysis"]
    assert holdings["explicit_deep_review_count"] == 0
    assert holdings["complete_deep_review_count"] == 0
    assert holdings["deep_review_gap_count"] == 1
    deep = holdings["rows"][0]["deep_review"]
    assert deep["status"] == "STALE_PROFILE_LAST_TERMINAL"
    assert deep["last_profile_status"] == "DEEP_REVIEW_PARTIAL"
    assert out["decision_readiness"]["all_holdings_explicit_deep_review_complete"] is False
    assert out["pillar_3_deep_opportunities"]["terminal_research_snapshot"]["current_for_deep_runtime"] is False
    assert out["investor_report_readiness"]["action_complete"] is True
    assert "TERMINAL_RESEARCH_NOT_CURRENT_FOR_ACTIVE_DEEP" in out["investor_report_readiness"]["limitations"]

    md = render_runtime_markdown(out)
    assert "顶部持仓/机会的深算完整度已按当前 runtime 视为未完成" in md
    assert "当前运行状态来源：**PARTIAL_CHECKPOINT**" in md
    assert "1000001" in md
    assert "上一次完整终态 run：`999999`" in md


def test_unresolved_markdown_is_bounded_summary_not_full_dump():
    terminal = _terminal_status()
    terminal["unresolved_reasons"] = {
        f"{i:06d}": {
            "moat": "NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE",
            "predictability": "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS",
        }
        for i in range(20)
    }
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=terminal,
        industry_links={},
        era_handoff={},
    )
    md = render_runtime_markdown(out)
    assert "涉及 20 只" in md
    assert "Top原因" in md
    assert "NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE×20" in md
    assert "000019[" not in md

def test_partial_checkpoint_without_workset_metrics_does_not_claim_zero() -> None:
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        partial_deep_calculation_status=_partial_status(),
        industry_links={},
        era_handoff={},
    )
    runtime = out["deep_calculation_runtime"]
    assert runtime["requested_count_available"] is False
    assert runtime["profile_count_available"] is False
    assert runtime["missing_requested_codes_available"] is False
    md = render_runtime_markdown(out)
    assert "请求深算：**未携带**" in md
    assert "Workset profile：总数 **未携带**" in md
    assert "请求但未进入本次研究工件：**未携带**" in md
    assert "请求深算：**0**" not in md


def test_partial_checkpoint_exposes_workset_coverage_when_persisted() -> None:
    partial = _partial_status()
    partial.update(
        {
            "requested_count": 850,
            "profile_count": 850,
            "requested_profile_count": 850,
            "missing_requested_codes": [],
            "workset_coverage_known": True,
            "workset_coverage_complete": True,
        }
    )
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_terminal_status(),
        partial_deep_calculation_status=partial,
        industry_links={},
        era_handoff={},
    )
    runtime = out["deep_calculation_runtime"]
    assert runtime["requested_count"] == 850
    assert runtime["requested_count_available"] is True
    assert runtime["profile_count"] == 850
    assert runtime["requested_profile_count"] == 850
    assert runtime["processed_requested_count"] == 850
    assert runtime["workset_coverage_known"] is True
    assert runtime["workset_coverage_complete"] is True
    assert runtime["missing_requested_codes"] == []
    md = render_runtime_markdown(out)
    assert "请求深算：**850**；已处理：**850**" in md
    assert "Workset profile：总数 **850**；请求代码已落 profile **850**" in md
    assert "覆盖可审计：**True**；完整覆盖：**True**" in md
    assert "请求但未进入本次研究工件：**无**" in md



def test_era_evidence_coverage_is_explicit_and_does_not_fake_fund_flow():
    coverage = summarize_era_evidence(_era_evidence())
    assert coverage["status"] == "PARTIAL"
    assert coverage["family_counts"]["POLICY_CAPITAL"] == 1
    assert coverage["family_counts"]["REAL_DEMAND"] == 2
    assert coverage["family_counts"]["FINANCIAL_CAPITAL"] == 0
    assert coverage["financial_capital_evidence_available"] is False
    assert coverage["direct_stock_fund_flow_claimed"] is False

    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        era_evidence_bundle=_era_evidence(),
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=_status(),
        industry_links={},
        era_handoff={},
    )
    capital = out["pillar_2_world_social_market_capital_map"]
    assert capital["capital_evidence_coverage"]["status"] == "PARTIAL"
    assert capital["direct_financial_capital_evidence_available"] is False
    assert out["decision_readiness"]["financial_capital_evidence_available"] is False
    md = render_runtime_markdown(out)
    assert "## 4. 今日账户资金怎么处理" in md
    assert "金融资本 live 证据尚未覆盖" in md
    assert out["investor_report_readiness"]["action_complete"] is True
    assert out["investor_report_readiness"]["evidence_complete"] is False
    assert "FINANCIAL_CAPITAL_LIVE_EVIDENCE_MISSING" in out["investor_report_readiness"]["limitations"]
    assert "## 今日汇报可执行性" in md
    assert "行动结论完整：**True**" in md


def test_three_pillar_does_not_race_investor_or_terminal_workflows():
    workflow = Path(".github/workflows/genge-three-pillar-decision-center.yml").read_text(encoding="utf-8")
    workflow_run = workflow.split("  workflow_run:", 1)[1].split("  pull_request:", 1)[0]

    assert "Era Capital Trend Radar Live" in workflow_run
    assert "GenGe Investor Decision Brief" not in workflow_run
    assert "GenGe V3.1 Terminal Research Decision" not in workflow_run


def test_candidate_lifecycle_and_system_capabilities_are_visible_in_final_report():
    lifecycle = {
        "contract_version": "GEN_GE_V31_CANDIDATE_LIFECYCLE_V1",
        "latest_applied_snapshot_id": "snap-life",
        "latest_research_as_of": "2026-09-20T13:30:04Z",
        "candidates": {
            "600406": {
                "code": "600406",
                "stock_name": "国电南瑞",
                "lifecycle_state": "ACTIVE",
                "research_tier": "PENDING",
                "seen_count": 176,
                "last_event": "RESEEN",
                "last_event_at": "2026-09-20T13:30:04Z",
                "history": [{"event": "RESEEN"}, {"event": "RESEEN"}],
            },
            "001316": {
                "code": "001316",
                "stock_name": "润贝航科",
                "lifecycle_state": "ACTIVE",
                "research_tier": "PENDING",
                "seen_count": 178,
                "last_event": "RESEEN",
                "history": [{"event": "RESEEN"}],
            },
        },
    }
    summary = summarize_candidate_lifecycle(lifecycle, ["600406"])
    assert summary["active_candidate_count"] == 2
    assert summary["lifecycle_event_count"] == 3
    assert summary["focus_candidates"][0]["seen_count"] == 176
    assert summary["formal_authority_granted"] is False

    status = _status()
    status.update({
        "verified_pass_gate_count": 217,
        "unverified_pass_gate_count": 0,
        "hard_gate_count": 4265,
        "provenance_audit_complete": True,
        "provenance_audit_run_id": "audit-1",
    })
    valuation_continuity = {
        "contract_version": "V311_HOLDING_SELL_RATIONALE_V3",
        "latest_applied_snapshot_id": "snap-value",
        "holdings": {
            "600406": {
                "action": "REDUCE_25",
                "value_low": "12.83",
                "neutral_value": "24.0",
                "value_high": "26.09",
                "current_price": "22.5",
                "valuation_confidence": "HIGH",
                "valuation_change": "STABLE",
                "price_value_zone": "UPPER_VALUE",
                "reason_codes": "SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION",
                "decision_date": "2026-09-20",
            }
        },
        "no_auto_trade": True,
    }
    out = build_runtime_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        era_evidence_bundle=_era_evidence(),
        candidate_lifecycle_state=lifecycle,
        holding_valuation_continuity_state=valuation_continuity,
        automatic_profiles=_automatic_profiles(),
        static_profiles={},
        deep_calculation_status=status,
        industry_links={},
        era_handoff={},
    )
    holding = out["pillar_1_holdings_deep_analysis"]["rows"][0]
    assert holding["candidate_lifecycle"]["lifecycle_state"] == "ACTIVE"
    assert holding["candidate_lifecycle"]["seen_count"] == 176
    assert out["candidate_lifecycle"]["active_candidate_count"] == 2
    caps = {row["capability"]: row for row in out["system_capability_visibility"]["capabilities"]}
    assert caps["持仓估值连续性 / 价值区间"]["status"] == "ACTIVE"
    assert caps["Candidate Lifecycle 持续研究记忆"]["status"] == "ACTIVE"
    assert caps["Deep Provenance 证据审计"]["status"] == "ACTIVE"
    assert holding["valuation_continuity"]["price_value_zone"] == "UPPER_VALUE"
    assert holding["valuation_continuity"]["value_low"] == 12.83
    assert out["holding_valuation_continuity"]["formal_action_recomputed"] is False
    assert "verified-pass=217" in caps["Deep 五类硬门槛 + 官方证据"]["result"]
    md = render_runtime_markdown(out)
    assert "## 本次汇报真正用了哪些系统能力" in md
    assert "Candidate Lifecycle 持续研究记忆" in md
    assert "当前 ACTIVE **2**；累计生命周期事件 **3**" in md
    assert "国电南瑞 600406：ACTIVE / tier=PENDING / 历史被系统重新看见 176 次" in md
    assert "价值区间 12.83–26.09" in md
    assert "区位 **UPPER_VALUE**" in md


def test_candidate_lifecycle_summary_distinguishes_dormant_from_archived():
    lifecycle = {
        "contract_version": "GEN_GE_V31_CANDIDATE_LIFECYCLE_V1",
        "candidates": {
            "600406": {
                "code": "600406",
                "stock_name": "国电南瑞",
                "lifecycle_state": "ACTIVE",
                "research_tier": "PENDING",
                "seen_count": 3,
                "history": [{"event": "RESEEN"}],
            },
            "000504": {
                "code": "000504",
                "stock_name": "南华生物",
                "lifecycle_state": "DORMANT",
                "research_tier": "PENDING",
                "seen_count": 2,
                "history": [{"event": "RESEARCH_EXHAUSTED_DORMANT"}],
            },
            "600000": {
                "code": "600000",
                "stock_name": "归档样例",
                "lifecycle_state": "ARCHIVED",
                "research_tier": "PENDING",
                "seen_count": 1,
                "history": [{"event": "ARCHIVED"}],
            },
            "600001": {
                "code": "600001",
                "stock_name": "失效样例",
                "lifecycle_state": "INVALIDATED",
                "research_tier": "PENDING",
                "seen_count": 1,
                "history": [{"event": "INVALIDATED"}],
            },
        },
    }

    summary = summarize_candidate_lifecycle(lifecycle, ["600406", "000504"])

    assert summary["active_candidate_count"] == 1
    assert summary["dormant_research_candidate_count"] == 1
    assert summary["archived_or_invalidated_count"] == 2
    assert summary["lifecycle_event_count"] == 4
    assert summary["focus_by_code"]["000504"]["lifecycle_state"] == "DORMANT"
