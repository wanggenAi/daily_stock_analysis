from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy as policy


def _plan(**overrides):
    plan = {
        "preferred_plan": "pullback",
        "pullback_status": "READY",
    }
    plan.update(overrides)
    return plan


def test_valley_repair_keeps_legacy_35pct_boundary():
    at_boundary = policy.evaluate_engine(
        {"price_percentile_5y": 0.35, "trend_confirmation_level": "MEDIUM"},
        _plan(),
    )
    above_boundary = policy.evaluate_engine(
        {
            "price_percentile_5y": 0.3501,
            "trend_confirmation_level": "MEDIUM",
            "industry_regime_status": "NEUTRAL",
        },
        _plan(pullback_status="WATCH"),
    )

    assert at_boundary.eligible is True
    assert at_boundary.engine == "VALLEY_REPAIR"
    assert above_boundary.eligible is False


def test_high_percentile_strong_trend_pullback_can_enter_engine():
    result = policy.evaluate_engine(
        {
            "price_percentile_5y": 0.72,
            "trend_confirmation_level": "STRONG",
            "industry_regime_status": "STRONG",
        },
        _plan(),
    )

    assert result.eligible is True
    assert result.engine == "STRONG_TREND_PULLBACK"


def test_earnings_engine_requires_real_profit_inflection_evidence():
    no_profit_fields = policy.evaluate_engine(
        {
            "price_percentile_5y": 0.60,
            "trend_confirmation_level": "MEDIUM",
            "industry_regime_status": "NEUTRAL",
            "financial_safety_score": 95,
        },
        _plan(pullback_status="WATCH"),
    )
    real_inflection = policy.evaluate_engine(
        {
            "price_percentile_5y": 0.60,
            "trend_confirmation_level": "MEDIUM",
            "industry_regime_status": "NEUTRAL",
            "net_profit_yoy": 18.0,
            "previous_net_profit_yoy": -4.0,
        },
        _plan(pullback_status="WATCH"),
    )

    assert no_profit_fields.eligible is False
    assert no_profit_fields.earnings_inflection_confirmed is False
    assert real_inflection.eligible is True
    assert real_inflection.engine == "EARNINGS_INFLECTION"


def test_explicitly_adverse_factor_evidence_blocks_every_engine():
    result = policy.evaluate_engine(
        {
            "price_percentile_5y": 0.10,
            "trend_confirmation_level": "STRONG",
            "industry_regime_status": "STRONG",
            "factor_validity_status": "INVALID",
            "earnings_inflection_confirmed": True,
        },
        _plan(),
    )

    assert result.eligible is False
    assert result.engine == "NONE"
    assert result.reason == "explicit_factor_evidence_adverse"


def test_missing_factor_evidence_is_unknown_not_fabricated_positive():
    assert policy.factor_validity_status({}) == "UNKNOWN"
    assert policy.factor_validity_status({"factor_ic": 0.03, "factor_ic_sample_count": 19}) == "UNKNOWN"
    assert policy.factor_validity_status({"factor_ic": 0.03, "factor_ic_sample_count": 20}) == "VALID"
    assert policy.factor_validity_status({"factor_ic": -0.03, "factor_ic_sample_count": 20}) == "INVALID"


def test_policy_replaces_only_price_gate_and_preserves_hard_failures(monkeypatch):
    def fake_legacy_checks(row, plan, profile, *, board_rule):
        return {
            "quant_research_queue": True,
            "no_hard_risk": True,
            "price_percentile_le_35": False,
            "financial_passed": False,
            "event_risk_not_high": False,
            "value_trap_not_high": False,
            "real_rr_1_8": True,
        }

    monkeypatch.setattr(policy, "_ORIGINAL_STRICT_CANDIDATE_CHECKS", fake_legacy_checks)
    row = {
        "price_percentile_5y": 0.70,
        "trend_confirmation_level": "STRONG",
        "industry_regime_status": "STRONG",
    }
    checks = policy.strict_candidate_checks(row, _plan(), {}, board_rule=object())

    assert "price_percentile_le_35" not in checks
    assert checks["opportunity_engine_eligible"] is True
    assert checks["financial_passed"] is False
    assert checks["event_risk_not_high"] is False
    assert checks["value_trap_not_high"] is False
    assert all(checks.values()) is False


def test_no_quota_path_exists_in_engine_policy():
    candidates = [
        policy.evaluate_engine(
            {
                "price_percentile_5y": 0.80,
                "trend_confirmation_level": "MEDIUM",
                "industry_regime_status": "NEUTRAL",
            },
            _plan(pullback_status="WATCH"),
        )
        for _ in range(3)
    ]

    assert not any(result.eligible for result in candidates)
