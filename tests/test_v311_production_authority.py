"""Regression tests for the V3.1.1 production authority boundary."""

from src.strategies.genge_opportunity_discovery.production_decision_scan import build_decisions
from src.strategies.genge_opportunity_discovery.production_model import (
    PRODUCTION_MODEL_VERSION,
    PRODUCTION_POLICY_SOURCE,
    production_payload,
)


PRODUCTION_OWNED_FIELDS = (
    "production_action",
    "production_target_position_fraction",
    "valuation_confidence",
    "valuation_confidence_reason_codes",
    "reason_codes",
    "normalized_earnings",
    "realistic_growth",
    "market_implied_growth",
    "expectation_gap",
    "neutral_value",
    "current_price",
    "price_to_neutral",
    "production_model_version",
    "production_policy_source",
    "production_model_frozen",
)


def _candidate() -> dict[str, object]:
    return {
        "code": "600000",
        "stock_name": "authority-regression-fixture",
        "v31_current_price": 80.0,
        "v31_neutral_value": 100.0,
        "v31_normalized_profit": 10.0,
        "v31_realistic_profit_cagr": 0.10,
        "v31_market_implied_profit_cagr": 0.05,
        "v31_expectation_gap_pct": 0.05,
        "normalized_earnings_observation_count": 4,
        "deduct_profit_quality_factor": 0.90,
        "cash_conversion_ratio": 1.00,
        "realistic_growth_four_report_range": 0.05,
        "implied_growth_status": "OK",
    }


def _fresh_expected(candidate: dict[str, object]) -> dict[str, object]:
    fresh_input = dict(candidate)
    fresh_input["v311_has_position"] = False
    fresh_input["v32_has_position"] = False
    return production_payload(fresh_input)


def test_same_policy_stale_artifact_cannot_override_fresh_gate_or_action() -> None:
    candidate = _candidate()
    expected = _fresh_expected(candidate)

    # Simulate a stale CSV emitted by an older run that still carries the exact
    # current version/policy labels. Labels alone must never grant authority.
    candidate.update(
        {
            "production_model_version": PRODUCTION_MODEL_VERSION,
            "production_policy_source": PRODUCTION_POLICY_SOURCE,
            "production_action": "EXIT" if expected["production_action"] != "EXIT" else "BUY",
            "valuation_confidence": "INVALID",
            "valuation_confidence_reason_codes": "STALE_ARTIFACT",
            "reason_codes": "STALE_ARTIFACT",
            "production_target_position_fraction": 0.123,
        }
    )

    row = build_decisions([candidate])[0]

    assert row["upstream_policy_matches"] is True
    assert row["upstream_policy_reused"] is False
    for field in PRODUCTION_OWNED_FIELDS:
        assert row[field] == expected[field], field


def test_tampered_production_fields_are_ignored_even_without_policy_labels() -> None:
    candidate = _candidate()
    expected = _fresh_expected(candidate)
    candidate.update(
        {
            "production_action": "CORE_ONLY",
            "valuation_confidence": "LOW",
            "valuation_confidence_reason_codes": "TAMPERED",
            "reason_codes": "TAMPERED",
            "neutral_value": 1.0,
            "current_price": 9999.0,
            "price_to_neutral": 9999.0,
            "production_model_frozen": False,
        }
    )

    row = build_decisions([candidate])[0]

    assert row["upstream_policy_matches"] is False
    assert row["upstream_policy_reused"] is False
    for field in PRODUCTION_OWNED_FIELDS:
        assert row[field] == expected[field], field
