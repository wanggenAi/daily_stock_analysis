from __future__ import annotations

from src.strategies.genge_opportunity_discovery import candidate_recovery_report as report


def _row(**overrides):
    row = {
        "code": "600001",
        "strict_gate_failed": "event_risk_known;exit_profile_passed",
        "exit_profile_status": "NOT_AVAILABLE",
        "stock_hard_veto_outcome_count": 0,
        "stock_negative_veto_clear": True,
        "factor_validity_status": "UNKNOWN",
        "actionability_score": 70,
    }
    row.update(overrides)
    return row


def test_data_recovery_candidate_is_prioritized_but_never_promoted():
    result = report.build_recovery_rows([_row()], [])
    assert len(result) == 1
    assert result[0]["recovery_class"] == "DATA_RECOVERY_NOW"
    assert result[0]["formal_signal_eligible"] is False
    assert result[0]["automatic_promotion_allowed"] is False


def test_engine_gate_is_recoverable_when_factor_is_not_adverse():
    classified = report.classify_recovery_candidate(
        _row(strict_gate_failed="opportunity_engine_eligible;exit_profile_passed")
    )
    assert classified is not None
    assert classified[0] == "MARKET_TRIGGER_WATCH"


def test_explicit_adverse_factor_is_excluded():
    assert report.classify_recovery_candidate(
        _row(
            strict_gate_failed="opportunity_engine_eligible;exit_profile_passed",
            factor_validity_status="INVALID",
        )
    ) is None


def test_failed_or_negative_exit_profile_is_excluded():
    assert report.classify_recovery_candidate(_row(exit_profile_status="FAILED")) is None
    assert report.classify_recovery_candidate(
        _row(exit_profile_status="DEGRADED", stock_negative_veto_clear=False)
    ) is None


def test_hard_non_exit_failure_is_excluded():
    assert report.classify_recovery_candidate(
        _row(strict_gate_failed="financial_passed;exit_profile_passed")
    ) is None
