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
