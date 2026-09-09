import pytest

from src.strategies.genge_opportunity_discovery.production_model import (
    _apply_neutral_semantics_guard,
    _holding_add_assessment,
    production_payload,
)
from src.strategies.genge_opportunity_discovery.selection_framework_v311 import (
    V311Decision,
    ValuationConfidence,
)
from src.strategies.genge_opportunity_discovery.v311_valuation_audit import (
    ROUND6_POLICY_SOURCE,
    STRICT_EPS_METHOD,
    UNCALIBRATED_SINGLE_POINT,
    VALIDATED_BASE,
    VALIDATED_BASE_EVIDENCE_MISSING,
    build_valuation_audit,
    neutral_value_semantic_status,
)


PRICE = 22.41
MODEL_POINT = 17.457807170543802
RATIO = PRICE / MODEL_POINT


def _strict_data(**overrides):
    data = {
        "code": "600406",
        "v311_has_position": True,
        "v311_expectation_input_status": "READY",
        "v311_expectation_policy_source": ROUND6_POLICY_SOURCE,
        "v31_normalized_profit_method": STRICT_EPS_METHOD,
        "eps_growth_3y_round6": 0.12,
        "revenue_growth_3y_round6": 0.05,
    }
    data.update(overrides)
    return data


def _decision(action="REDUCE_25", target=0.75, ratio=RATIO):
    return V311Decision(
        action=action,
        target_position_fraction=target,
        valuation_confidence=ValuationConfidence.HIGH,
        reason_codes=("V31_IMMEDIATE_VALUATION_SELL", action),
        normalized_earnings=1.5,
        realistic_growth=0.10,
        market_implied_growth=0.15,
        expectation_gap=-0.05,
        neutral_value=MODEL_POINT,
        current_price=PRICE,
        price_to_neutral=ratio,
    )


def test_round6_single_point_is_audited_not_silently_promoted_to_base():
    audit = build_valuation_audit(
        _strict_data(),
        current_price=PRICE,
        neutral_value=MODEL_POINT,
        normalized_earnings=1.5,
        realistic_growth=0.10,
        price_to_neutral=RATIO,
    )

    assert audit["v311_neutral_value_semantic_status"] == UNCALIBRATED_SINGLE_POINT
    assert audit["v311_neutral_value_role"] == "ROUND6_EARNING_POWER_SINGLE_POINT"
    assert audit["v311_neutral_value_semantic_guard_required"] is True
    assert audit["v311_formal_valuation_action_authorized"] is False
    assert audit["v311_mechanical_valuation_action"] == "REDUCE_25"
    assert audit["v311_normalized_earnings_semantics"] == "EPS_PER_SHARE"
    assert audit["v311_normalized_eps"] == pytest.approx(1.5)
    assert audit["v311_effective_pe"] == pytest.approx(MODEL_POINT / 1.5)
    assert audit["v311_fair_pe_is_explicit_input"] is False
    assert audit["v311_growth_binding_constraint"] == "REVENUE_CAGR_PLUS_5PP"
    assert audit["v311_realistic_growth_used"] == pytest.approx(0.10)
    assert audit["v311_discount_rate"] == pytest.approx(0.10)
    assert audit["v311_terminal_growth"] == pytest.approx(0.03)
    assert audit["v311_horizon_years"] == 10
    assert audit["v311_terminal_multiple"] == pytest.approx(1.0 / 0.07)


def test_validated_base_label_without_evidence_cannot_bypass_guard():
    data = _strict_data(v311_neutral_value_semantic_status=VALIDATED_BASE)
    assert neutral_value_semantic_status(data) == VALIDATED_BASE_EVIDENCE_MISSING

    audit = build_valuation_audit(
        data,
        current_price=PRICE,
        neutral_value=MODEL_POINT,
        normalized_earnings=1.5,
        realistic_growth=0.10,
        price_to_neutral=RATIO,
    )
    assert audit["v311_neutral_value_semantic_guard_required"] is True
    assert audit["v311_neutral_value_scenario_calibrated"] is False


def test_validated_base_requires_method_and_evidence_and_then_authorizes_ladder():
    data = _strict_data(
        v311_neutral_value_semantic_status=VALIDATED_BASE,
        v311_neutral_value_validation_method="THREE_SCENARIO_CALIBRATION",
        v311_neutral_value_validation_evidence="fixture:bear-base-bull-v1",
    )
    assert neutral_value_semantic_status(data) == VALIDATED_BASE

    guarded = _apply_neutral_semantics_guard(data, _decision())
    assert guarded.action == "REDUCE_25"


def test_fresh_unvalidated_round6_reduce25_is_fail_closed_to_hold_review():
    guarded = _apply_neutral_semantics_guard(_strict_data(), _decision())

    assert guarded.action == "HOLD_REVIEW"
    assert guarded.target_position_fraction is None
    assert "NEUTRAL_VALUE_SEMANTICS_UNVERIFIED" in guarded.reason_codes
    assert "MECHANICAL_ACTION_SUPPRESSED:REDUCE_25" in guarded.reason_codes


def test_semantic_guard_never_suppresses_hard_logic_exit():
    guarded = _apply_neutral_semantics_guard(
        _strict_data(),
        _decision(action="EXIT", target=0.0),
    )
    assert guarded.action == "EXIT"
    assert guarded.target_position_fraction == 0.0


def test_fresh_unvalidated_round6_candidate_buy_is_fail_closed_to_wait():
    data = _strict_data(v311_has_position=False)
    guarded = _apply_neutral_semantics_guard(
        data,
        _decision(action="BUY", target=1.0, ratio=0.70),
    )
    assert guarded.action == "WAIT"
    assert guarded.target_position_fraction == 0.0


def test_unvalidated_model_point_cannot_authorize_staged_holding_add():
    data = _strict_data(
        price_date_verification_status="VERIFIED",
        price_mapping_status="OK",
        v31_predictability_status="PASS",
        v31_long_term_demand_status="PASS",
        v31_moat_status="PASS",
        v31_financial_safety_status="PASS",
        v31_earnings_authenticity_status="PASS",
    )
    hold = _decision(action="HOLD", target=1.0, ratio=0.70)
    hold = V311Decision(
        **{**hold.__dict__, "current_price": 12.22, "price_to_neutral": 0.70}
    )

    authorized, reasons = _holding_add_assessment(data, hold, typed_insurer=False)
    assert authorized is False
    assert "NEUTRAL_VALUE_SEMANTICS_UNVERIFIED" in reasons


def test_full_production_payload_persists_chain_and_suppresses_600406_mechanical_sell():
    data = _strict_data(
        v31_current_price=PRICE,
        v31_neutral_value=MODEL_POINT,
        v31_normalized_profit=1.5,
        v31_realistic_profit_cagr=0.10,
        v31_market_implied_profit_cagr=0.15,
        v31_expectation_gap_pct=-0.05,
        normalized_earnings_observation_count=4,
        deduct_profit_quality_factor=0.90,
        cash_conversion_ratio=1.00,
        realistic_growth_four_report_range=0.05,
        implied_growth_status="OK",
    )

    payload = production_payload(data)

    assert payload["valuation_confidence"] == "HIGH"
    assert payload["production_action"] == "HOLD_REVIEW"
    assert payload["v311_final_production_action"] == "HOLD_REVIEW"
    assert payload["v311_mechanical_valuation_action"] == "REDUCE_25"
    assert payload["v311_neutral_value_semantic_guard_required"] is True
    assert payload["v311_formal_valuation_action_authorized"] is False
    assert payload["v311_normalized_eps"] == pytest.approx(1.5)
    assert payload["v311_effective_pe"] == pytest.approx(MODEL_POINT / 1.5)
    assert "NEUTRAL_VALUE_SEMANTICS_UNVERIFIED" in payload["reason_codes"]


def test_legacy_replay_without_fresh_strict_pit_provenance_is_not_rewritten():
    legacy = {"v311_has_position": True}
    guarded = _apply_neutral_semantics_guard(legacy, _decision())
    assert guarded.action == "REDUCE_25"
