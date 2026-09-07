from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery.insurer_typed_production import (
    assess_insurer_valuation_confidence_v311,
    is_insurer_typed_input,
    resolve_insurer_typed_evidence,
)
from src.strategies.genge_opportunity_discovery.production_model import production_payload


def _pingan(*, has_position: bool = True, decision_date: str = "2026-09-07") -> dict[str, object]:
    return {
        "code": "601318",
        "decision_date": decision_date,
        "price_date": "2026-09-04",
        "v31_current_price": 58.24,
        "v311_has_position": has_position,
        # Simulate the legacy generic Round-6 failure that used to strand the holding.
        "v311_expectation_input_status": "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_input_error": "GENERIC_EXPECTATION_MODEL_INCOMPLETE",
        "v31_neutral_value": None,
        "v31_realistic_profit_cagr": None,
        "normalized_earnings": None,
        "market_implied_growth": None,
        "v31_predictability_status": "PASS",
        "v31_long_term_demand_status": "PASS",
        "v31_moat_status": "PASS",
        "v31_financial_safety_status": "PASS",
        "v31_earnings_authenticity_status": "PASS",
    }


def test_current_holding_generic_invalid_recovers_typed_insurer_evidence() -> None:
    data = _pingan()
    assert is_insurer_typed_input(data) is True
    evidence = resolve_insurer_typed_evidence(data)
    assert evidence.ready is True
    assert evidence.neutral_value == 83.07
    assert evidence.realistic_growth == 0.083

    payload = production_payload(data)
    assert payload["valuation_confidence"] == "MEDIUM"
    assert payload["neutral_value"] == 83.07
    assert payload["realistic_growth"] == 0.083
    assert payload["production_action"] == "HOLD"
    assert payload["typed_valuation_status"] == "READY"
    assert payload["typed_formal_buy_eligible"] is False
    assert payload["typed_formal_action_recomputed"] is True
    assert payload["no_auto_trade"] is True


def test_insurer_candidate_never_gets_formal_buy_privilege() -> None:
    payload = production_payload(_pingan(has_position=False))
    assert payload["production_action"] == "WAIT"
    assert payload["valuation_confidence"] == "MEDIUM"
    assert payload["typed_formal_buy_eligible"] is False
    assert "TYPED_INSURER_FORMAL_BUY_NOT_PROMOTED" in payload["reason_codes"]


def test_stale_ev_evidence_fails_closed_with_specific_diagnostic() -> None:
    data = _pingan(decision_date="2027-05-01")
    data["price_date"] = "2027-04-30"
    evidence = resolve_insurer_typed_evidence(data)
    assert evidence.ready is False
    assert "INSURER_EMBEDDED_VALUE_STALE" in evidence.reason_codes
    confidence = assess_insurer_valuation_confidence_v311(data)
    assert confidence.level.value == "INVALID"
    assert "INSURER_EMBEDDED_VALUE_STALE" in confidence.reason_codes


def test_low_authority_growth_evidence_is_rejected(tmp_path: Path) -> None:
    growth = tmp_path / "growth.yaml"
    growth.write_text(
        """version: 1
inputs:
  - input_id: low-authority
    code: '601318'
    known_at: '2026-08-20'
    evidence_as_of: '2026-06-30'
    confidence: LOW
    max_age_days: 365
    nbv_growth_yoy: 0.112
    operating_profit_growth_yoy: 0.083
    source_name: test
    source_url: https://example.invalid/not-authoritative
""",
        encoding="utf-8",
    )
    evidence = resolve_insurer_typed_evidence(_pingan(), growth_config=growth)
    assert evidence.ready is False
    assert "INSURER_GROWTH_EVIDENCE_AUTHORITY_INSUFFICIENT" in evidence.reason_codes


def test_stale_growth_evidence_is_rejected(tmp_path: Path) -> None:
    growth = tmp_path / "growth.yaml"
    growth.write_text(
        """version: 1
inputs:
  - input_id: stale-growth
    code: '601318'
    known_at: '2026-06-01'
    evidence_as_of: '2026-03-31'
    confidence: HIGH
    max_age_days: 30
    nbv_growth_yoy: 0.10
    operating_profit_growth_yoy: 0.08
    source_name: test
    source_url: https://example.invalid/stale
""",
        encoding="utf-8",
    )
    evidence = resolve_insurer_typed_evidence(_pingan(), growth_config=growth)
    assert evidence.ready is False
    assert "INSURER_GROWTH_EVIDENCE_STALE" in evidence.reason_codes


def test_missing_price_date_remains_invalid_not_pass() -> None:
    data = _pingan()
    data["price_date"] = ""
    evidence = resolve_insurer_typed_evidence(data)
    assert evidence.ready is False
    assert "PRICE_DATE_UNVERIFIED" in evidence.reason_codes
    payload = production_payload(data)
    assert payload["valuation_confidence"] == "INVALID"
    assert payload["production_action"] == "HOLD_REVIEW"


def test_generic_non_insurer_path_is_not_reclassified() -> None:
    data = {
        "code": "600406",
        "decision_date": "2026-09-07",
        "price_date": "2026-09-04",
        "v31_current_price": 30.0,
    }
    assert is_insurer_typed_input(data) is False
    payload = production_payload(data)
    assert payload.get("typed_valuation_model") is None
