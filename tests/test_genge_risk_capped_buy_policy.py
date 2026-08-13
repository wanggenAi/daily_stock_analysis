from __future__ import annotations

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as policy


def board_rule() -> core.BoardRule:
    return core.BoardRule(
        daily_price_limit=0.10,
        max_gap_open_pct=0.08,
        max_5d_return_pct=0.25,
        max_10d_return_pct=0.40,
        breakout_volume_ratio=1.20,
        max_chase_atr_multiple=0.50,
        minimum_turnover=1_000_000,
        minimum_history_rows=250,
        valuation_mode="standard",
        volatility_multiplier=1.0,
        abnormal_move_threshold=0.08,
    )


def base_row() -> dict:
    return {
        "quant_status": "PRIORITY_RESEARCH",
        "hard_blockers": "",
        "hard_reject_blockers": "",
        "risk_flags": "",
        "soft_blockers": "",
        "price_percentile_5y": 0.20,
        "trend_confirmation_level": "MEDIUM",
        "adjusted_latest_close": 12.0,
        "ma60": 10.0,
        "ma60_slope_pct": 0.10,
        "financial_safety_score": 90.0,
        "valuation_score": 90.0,
        "industry_evidence_status": "VERIFIED",
        "company_evidence_status": "VERIFIED",
        "hard_logic_level": "MEDIUM",
        "strict_official_evidence_passed": True,
        "market_regime_status": "GREEN",
        "industry_regime_status": "STRONG",
        "industry_regime_sample_count": 20,
        "event_scan_status": "OK",
        "event_risk_level": "LOW",
        "price_volume_state": "HEALTHY",
        "execution_risk_quality": "LOW",
        "value_trap_flag": False,
        "price_mapping_status": "OK",
    }


def base_plan() -> dict:
    return {
        "preferred_plan": "pullback",
        "pullback_status": "READY",
        "breakout_status": "NOT_READY",
        "real_reward_risk_ratio": 2.2,
        "pullback_entry_high": 12.0,
        "pullback_stop_price": 11.0,
    }


def missing_profile() -> dict:
    return {
        "exit_profile_status": "NOT_AVAILABLE",
        "exit_profile_sample_count": 0,
        "recent_2y_sample_count": 0,
        "exit_profile_confidence": "LOW",
        "exit_profile_entry_mode": "pullback",
        "exit_profile_freshness_passed": True,
        "exit_profile_rule_version_match": True,
        "exit_profile_data_traceable": True,
        "exit_profile_validation_scope_valid": True,
        "stock_profile_status": "NOT_AVAILABLE",
        "stock_negative_veto_clear": True,
        "stock_hard_veto_outcome_count": 0,
    }


def test_missing_exit_history_can_be_formal_but_risk_capped():
    row, plan, profile = base_row(), base_plan(), missing_profile()

    assert policy.risk_capped_eligible(row, plan, profile, board_rule=board_rule())
    level, missing = policy.classify_candidate(
        row, plan, profile, [], board_rule=board_rule(),
    )

    assert level == "STRICT_REVIEW_READY"
    assert set(missing) == {
        "exit_profile_passed",
        "exit_profile_sample_count",
        "exit_profile_recent_2y_samples",
        "exit_profile_confidence",
    }
    assert policy.risk_capped_profile_multiplier(profile) == 0.25


def test_explicit_failed_exit_profile_is_never_relaxed():
    row, plan, profile = base_row(), base_plan(), missing_profile()
    profile.update({
        "exit_profile_status": "FAILED",
        "stock_profile_status": "FAILED",
        "stock_negative_veto_clear": False,
        "exit_profile_sample_count": 6,
    })

    assert not policy.risk_capped_eligible(row, plan, profile, board_rule=board_rule())
    assert policy.risk_capped_profile_multiplier(profile) == 0.0
    level, _ = policy.classify_candidate(row, plan, profile, [], board_rule=board_rule())
    assert level != "STRICT_REVIEW_READY"


def test_non_exit_strict_failure_still_blocks_formal_buy():
    row, plan, profile = base_row(), base_plan(), missing_profile()
    row["event_risk_level"] = "HIGH"

    failed = policy.failed_strict_gates(row, plan, profile, board_rule=board_rule())
    assert "event_risk_not_high" in failed
    assert not policy.risk_capped_eligible(row, plan, profile, board_rule=board_rule())


def test_degraded_profile_requires_negative_veto_clear():
    profile = missing_profile()
    profile["exit_profile_status"] = "DEGRADED"
    assert policy.risk_capped_profile_multiplier(profile) == 0.15

    profile["stock_negative_veto_clear"] = False
    assert policy.risk_capped_profile_multiplier(profile) == 0.0

    profile["stock_negative_veto_clear"] = "False"
    assert policy.risk_capped_profile_multiplier(profile) == 0.0


def test_position_budget_injects_cap_before_existing_sizer(monkeypatch):
    captured = {}

    def fake_sizer(row, plan, level):
        captured.update({
            "level": level,
            "multiplier": row.get("profile_position_multiplier"),
            "scope": row.get("profile_validation_scope"),
        })

    monkeypatch.setattr(policy, "_ORIGINAL_APPLY_POSITION_BUDGET", fake_sizer)
    row = {
        "strict_gate_failed": ";".join([
            "exit_profile_passed",
            "exit_profile_sample_count",
            "exit_profile_recent_2y_samples",
            "exit_profile_confidence",
        ]),
        "exit_profile_status": "NOT_AVAILABLE",
        "profile_position_multiplier": 0.0,
        "stock_negative_veto_clear": True,
        "stock_hard_veto_outcome_count": 0,
        "exit_profile_blocker_detail": "samples=0",
    }

    policy.apply_position_budget(row, base_plan(), "STRICT_REVIEW_READY")

    assert captured["level"] == "STRICT_REVIEW_READY"
    assert captured["multiplier"] == 0.25
    assert captured["scope"] == "RISK_CAPPED_NOT_AVAILABLE_EXIT_HISTORY"
    assert row["exit_profile_blocker_detail"].startswith("risk_capped_multiplier=0.25;")


def test_fresh_risk_capped_promotion_rebuilds_current_signal_plan(monkeypatch):
    row = {
        "code": "603883",
        "stock_name": "老百姓",
        "user_visible_level": "STRICT_REVIEW_READY",
        "strict_gate_failed": ";".join([
            "exit_profile_passed",
            "exit_profile_sample_count",
            "exit_profile_recent_2y_samples",
            "exit_profile_confidence",
        ]),
        "exit_profile_status": "NOT_AVAILABLE",
        "stock_negative_veto_clear": True,
        "stock_hard_veto_outcome_count": 0,
        "preferred_plan": "pullback",
        "real_reward_risk_ratio": 1.93,
        "risk_budget_initial_position_pct": 0.62,
        "risk_budget_max_position_pct": 1.0,
        "profile_validation_scope": "RISK_CAPPED_NOT_AVAILABLE_EXIT_HISTORY",
        "profile_position_multiplier": 0.25,
    }
    previous = {
        "603883": {
            "user_visible_level": "RESEARCH_WATCH",
            "signal_lifecycle_state": "NO_POSITION_SIGNAL",
            "preferred_plan": "breakout",
            "risk_budget_initial_position_pct": 0.0,
            "risk_budget_max_position_pct": 0.0,
        },
    }
    calls = []

    def fake_builder(**kwargs):
        calls.append(dict(kwargs.get("previous") or {}))
        if kwargs.get("previous"):
            return [{
                "code": "603883",
                "signal_action": "BUY_IF_TRIGGERED",
                "signal_label": "条件买入信号",
                "signal_reason": "all_strict_gates_passed",
                "preferred_plan": "breakout",
                "real_reward_risk_ratio": 0.77,
                "risk_budget_initial_position_pct": 0.0,
                "risk_budget_max_position_pct": 0.0,
                "profile_validation_scope": "STOCK_SPECIFIC_INSUFFICIENT",
                "profile_position_multiplier": 0.0,
            }]
        current = kwargs["current_rows"][0]
        return [{
            "code": "603883",
            "signal_action": "BUY_IF_TRIGGERED",
            "signal_label": "条件买入信号",
            "signal_reason": "all_strict_gates_passed",
            "preferred_plan": current["preferred_plan"],
            "real_reward_risk_ratio": current["real_reward_risk_ratio"],
            "risk_budget_initial_position_pct": current["risk_budget_initial_position_pct"],
            "risk_budget_max_position_pct": current["risk_budget_max_position_pct"],
            "profile_validation_scope": current["profile_validation_scope"],
            "profile_position_multiplier": current["profile_position_multiplier"],
            "previous_level": "",
            "previous_lifecycle_state": "NONE",
        }]

    monkeypatch.setattr(policy, "_ORIGINAL_BUILD_DAILY_SIGNALS", fake_builder)
    signals = policy.build_daily_signals(
        current_rows=[row], previous=previous, as_of=None, next_trade_date=None,
    )

    assert len(calls) == 2
    assert signals[0]["preferred_plan"] == "pullback"
    assert signals[0]["real_reward_risk_ratio"] == 1.93
    assert signals[0]["risk_budget_initial_position_pct"] == 0.62
    assert signals[0]["risk_budget_max_position_pct"] == 1.0
    assert signals[0]["profile_validation_scope"] == "RISK_CAPPED_NOT_AVAILABLE_EXIT_HISTORY"
    assert signals[0]["profile_position_multiplier"] == 0.25
    assert signals[0]["previous_level"] == "RESEARCH_WATCH"
    assert signals[0]["previous_lifecycle_state"] == "NO_POSITION_SIGNAL"
    assert signals[0]["signal_reason"] == "risk_capped_exit_uncertainty_formal_entry"


def test_active_risk_capped_plan_is_not_rebuilt(monkeypatch):
    row = {
        "code": "603883",
        "user_visible_level": "STRICT_REVIEW_READY",
        "strict_gate_failed": "exit_profile_passed",
        "exit_profile_status": "NOT_AVAILABLE",
        "stock_negative_veto_clear": True,
        "stock_hard_veto_outcome_count": 0,
    }
    previous = {
        "603883": {
            "user_visible_level": "RESEARCH_WATCH",
            "signal_lifecycle_state": "ENTRY_PENDING",
        },
    }
    calls = []

    def fake_builder(**kwargs):
        calls.append(dict(kwargs.get("previous") or {}))
        return [{
            "code": "603883",
            "signal_action": "BUY_IF_TRIGGERED",
            "preferred_plan": "breakout",
            "risk_budget_initial_position_pct": 0.5,
        }]

    monkeypatch.setattr(policy, "_ORIGINAL_BUILD_DAILY_SIGNALS", fake_builder)
    signals = policy.build_daily_signals(
        current_rows=[row], previous=previous, as_of=None, next_trade_date=None,
    )

    assert len(calls) == 1
    assert signals[0]["preferred_plan"] == "breakout"


def test_no_validated_exit_edge_health_matches_risk_capped_policy(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_EXIT_PROFILE_STRATEGY_HEALTH",
        lambda refresh: {
            "status": "NO_VALIDATED_EXIT_EDGE",
            "candidate_passed_count": 0,
            "cohort_passed_count": 0,
            "note": "new formal buys must remain disabled",
        },
    )

    health = policy.exit_profile_strategy_health({})

    assert health["status"] == "NO_VALIDATED_EXIT_EDGE"
    assert health["formal_buy_policy"] == "RISK_CAPPED_EXIT_UNCERTAINTY"
    assert health["risk_capped_profile_multipliers"] == {
        "NOT_AVAILABLE": 0.25,
        "DEGRADED": 0.15,
    }
    assert "globally suppressing formal buys" in health["note"]
    assert "Explicit FAILED profiles" in health["note"]
