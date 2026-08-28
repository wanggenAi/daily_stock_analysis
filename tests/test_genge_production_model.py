from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery import holding_valuation_continuity
from src.strategies.genge_opportunity_discovery.production_decision_scan import (
    build_decisions,
    read_holdings_markdown,
)
from src.strategies.genge_opportunity_discovery.production_model import (
    ALLOWED_ACTIONS,
    PRODUCTION_MODEL_VERSION,
    PRODUCTION_POLICY_SOURCE,
    SELL_CONTRACT,
    V32_SELL_CONFIRMATION_ENABLED,
    production_payload,
)
from tests.test_genge_opportunity_discovery_selection_framework_v311 import complete_v311_row


def _install_stable_sell_baseline(monkeypatch, *, code: str = "600000", neutral: float = 100.0, normalized: float = 10.0) -> None:
    """Give sell tests the trustworthy prior valuation basis required by production."""
    monkeypatch.setattr(
        holding_valuation_continuity,
        "load_state",
        lambda path=holding_valuation_continuity.STATE_PATH: {
            "contract_version": "V311_HOLDING_SELL_RATIONALE_V3",
            "holdings": {
                code: {
                    "action": "HOLD",
                    "neutral_value": neutral,
                    "normalized_earnings": normalized,
                    "valuation_confidence": "HIGH",
                    "canonical_snapshot_id": "prior-snapshot",
                    "canonical_source_run_id": 1,
                }
            },
        },
    )


def test_production_is_gate_only_with_explicit_v31_sell_rationale(monkeypatch) -> None:
    _install_stable_sell_baseline(monkeypatch)
    row = complete_v311_row(current=150.0)
    payload = production_payload(row)
    assert payload["production_model_version"] == PRODUCTION_MODEL_VERSION
    assert payload["production_action"] == "REDUCE_50"
    assert payload["production_sell_contract"] == SELL_CONTRACT
    assert "SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION" in payload["reason_codes"]
    assert payload["formal_sell_requires_explicit_rationale"] is True
    assert payload["formal_sell_mechanical_valuation_only_forbidden"] is True
    assert payload["production_policy_source"] == PRODUCTION_POLICY_SOURCE
    assert payload["v32_sell_confirmation_enabled"] is False
    assert V32_SELL_CONFIRMATION_ENABLED is False


def test_production_action_vocabulary_is_complete_and_frozen() -> None:
    assert ALLOWED_ACTIONS == {
        "BUY", "WAIT", "HOLD", "HOLD_NO_ADD", "HOLD_REVIEW",
        "REDUCE_25", "REDUCE_50", "CORE_ONLY", "EXIT",
    }


def test_production_can_emit_every_frozen_action(monkeypatch) -> None:
    _install_stable_sell_baseline(monkeypatch)
    cases = {
        "BUY": (70.0, False),
        "WAIT": (90.0, False),
        "HOLD": (90.0, True),
        "HOLD_NO_ADD": (110.0, True),
        "REDUCE_25": (125.0, True),
        "REDUCE_50": (145.0, True),
        "CORE_ONLY": (180.0, True),
    }
    observed = set()
    for expected, (price, held) in cases.items():
        row = complete_v311_row(current=price)
        row["v32_has_position"] = held
        action = production_payload(row)["production_action"]
        assert action == expected
        observed.add(action)

    review = complete_v311_row(current=90.0)
    review["cash_conversion_ratio"] = -0.1
    observed.add(production_payload(review)["production_action"])
    failed = complete_v311_row(current=90.0)
    failed["v31_moat_status"] = "FAIL"
    observed.add(production_payload(failed)["production_action"])
    assert observed == ALLOWED_ACTIONS


def test_production_low_confidence_is_hold_review() -> None:
    row = complete_v311_row(current=150.0)
    row["cash_conversion_ratio"] = -0.1
    assert production_payload(row)["production_action"] == "HOLD_REVIEW"


def test_sell_without_trustworthy_prior_baseline_fails_closed() -> None:
    row = complete_v311_row(current=150.0)
    payload = production_payload(row)
    assert payload["production_action"] == "HOLD_REVIEW"
    assert "SELL_RATIONALE_REVIEW_REQUIRED" in payload["reason_codes"]
    assert "SELL_RATIONALE_BASELINE_MISSING" in payload["reason_codes"]


def test_sell_with_unexplained_value_discontinuity_fails_closed(monkeypatch) -> None:
    _install_stable_sell_baseline(monkeypatch, neutral=140.0)
    row = complete_v311_row(current=150.0, neutral=100.0)
    payload = production_payload(row)
    assert payload["production_action"] == "HOLD_REVIEW"
    assert "NEUTRAL_VALUE_DISCONTINUITY" in payload["reason_codes"]
    assert "SELL_RATIONALE_NOT_PROVEN" in payload["reason_codes"]


def test_material_thesis_linked_evidence_can_justify_reunderwrite(monkeypatch) -> None:
    _install_stable_sell_baseline(monkeypatch, neutral=140.0)
    row = complete_v311_row(current=150.0, neutral=100.0)
    row.update(
        {
            "valuation_continuity_evidence_id": "report-2026q2-guidance-cut",
            "valuation_continuity_evidence_observed_at": "2026-08-28T08:30:00+08:00",
            "valuation_continuity_evidence_reason": "Management materially cut forward earnings guidance, invalidating the prior normalized earnings trajectory.",
            "valuation_continuity_evidence_type": "GUIDANCE_CUT",
            "valuation_continuity_evidence_material": True,
            "valuation_continuity_thesis_link": "The original holding thesis depended on durable earnings growth that the new guidance directly impairs.",
        }
    )
    payload = production_payload(row)
    assert payload["production_action"] == "REDUCE_50"
    assert "SELL_RATIONALE_MATERIAL_REUNDERWRITE_EVIDENCE" in payload["reason_codes"]


def test_holding_cost_is_display_only(monkeypatch) -> None:
    _install_stable_sell_baseline(monkeypatch)
    candidate = complete_v311_row(current=180.0)
    candidate["code"] = "600000"
    low_cost = {"code": "600000", "display_only_average_cost": "10", "confirmed_quantity": "100"}
    high_cost = {"code": "600000", "display_only_average_cost": "300", "confirmed_quantity": "100"}
    first = build_decisions([candidate], [low_cost])[0]
    second = build_decisions([candidate], [high_cost])[0]
    assert first["production_action"] == second["production_action"] == "CORE_ONLY"
    assert first["cost_basis_used_by_decision"] is False


def test_missing_holding_valuation_is_safe_review() -> None:
    row = build_decisions([], [{"code": "600000", "stock_name": "test", "confirmed_quantity": "100"}])[0]
    assert row["production_action"] == "HOLD_REVIEW"
    assert row["valuation_confidence"] == "INVALID"


def test_parse_current_holdings_contract() -> None:
    path = Path(__file__).resolve().parents[1] / "CURRENT_HOLDINGS.md"
    holdings = read_holdings_markdown(path)
    assert {row["code"] for row in holdings} >= {"603369", "001316", "600276", "600406"}


def test_scanner_recomputes_candidate_even_with_exact_policy_source() -> None:
    # Exact policy labels are audit metadata only.  The scanner must recompute
    # the production decision from complete evidence and never reuse upstream
    # production_action / confidence fields as authority.
    row = complete_v311_row(current=70.0)
    row.update(
        {
            "code": "600000",
            "production_model_version": PRODUCTION_MODEL_VERSION,
            "production_policy_source": PRODUCTION_POLICY_SOURCE,
            "production_action": "WAIT",
            "valuation_confidence": "LOW",
            "reason_codes": "STALE_UPSTREAM_DECISION_FIELDS",
        }
    )
    decision = build_decisions([row])[0]
    assert decision["production_action"] == "BUY"
    assert decision["valuation_confidence"] == "HIGH"
    assert decision["upstream_policy_matches"] is True
    assert decision["upstream_policy_reused"] is False


def test_same_version_legacy_policy_is_not_trusted() -> None:
    # This reproduces the old name-only V3.1.1 ambiguity: a stale upstream row
    # may carry the current version label but not the validated policy source.
    row = {
        "code": "600000",
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "production_action": "BUY",
        "valuation_confidence": "HIGH",
        "reason_codes": "STALE_OLD_IMPLEMENTATION",
    }
    decision = build_decisions([row])[0]
    assert decision["upstream_policy_reused"] is False
    assert decision["production_action"] == "HOLD_REVIEW"
    assert decision["valuation_confidence"] == "INVALID"


def test_research_only_market_never_enters_production_candidate_output() -> None:
    research_only = {
        "code": "688001",
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "production_policy_source": PRODUCTION_POLICY_SOURCE,
        "production_action": "BUY",
        "valuation_confidence": "HIGH",
    }
    assert build_decisions([research_only]) == []
