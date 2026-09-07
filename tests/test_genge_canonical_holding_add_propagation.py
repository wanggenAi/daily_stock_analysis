import pytest

from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
    validate_snapshot,
)
from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import _holdings


def _row(**overrides):
    row = {
        "code": "603993",
        "stock_name": "洛阳钼业",
        "decision_scope": "HOLDING",
        "production_action": "HOLD",
        "production_model_version": PRODUCTION_VERSION,
        "v311_production_bridge": PRODUCTION_BRIDGE,
        "strict_pit_refresh_applied": True,
        "v311_expectation_input_status": "READY",
        "decision_date": "2026-09-07",
        "price_date": "2026-09-04",
        "current_price": "18.48",
        "neutral_value": "28.12766979232306",
        "valuation_confidence": "HIGH",
        "v311_input_error": "",
        "hard_gate_failures": "",
        "upstream_policy_reused": False,
        "no_auto_trade": True,
        "confirmed_quantity": "900",
        "display_only_average_cost": "18.9114",
        "holding_add_authorization_reason_codes": "EXISTING_HOLDING_STAGED_ADD_AUTHORIZED;STAGED_ADD_CAP_ONE_LOT;STAGED_ADD_NOT_FORMAL_BUY;FORMAL_ACTION_UNCHANGED;HARD_GATE_UNKNOWNS_RETAINED:predictability,moat",
        "holding_add_authorized": True,
        "holding_add_existing_position_only": True,
        "holding_add_formal_action_unchanged": True,
        "holding_add_hard_gate_unknowns": "predictability;moat",
        "holding_add_is_formal_buy": False,
        "holding_add_max_lots": "1",
        "holding_add_max_price_to_neutral": "0.75",
        "holding_add_no_auto_trade": True,
        "holding_add_policy_version": "EXISTING_HOLDING_STAGED_ADD_V1",
        "holding_add_requires_high_confidence": True,
        "holding_add_unknown_is_pass": False,
    }
    row.update(overrides)
    return row


def _snapshot(row=None):
    return build_snapshot(
        discovery_rows=[],
        deep_review_rows=[],
        production_rows=[row or _row()],
        source_kind="test",
        source_run_id="holding-add-1",
        generated_at="2026-09-07T09:00:00+00:00",
    )


def test_staged_add_survives_canonical_without_mutating_formal_action():
    snapshot = _snapshot()
    validate_snapshot(snapshot, expected_source_run_id="holding-add-1")
    decision = snapshot["production"]["holding_decisions"][0]
    assert decision["action"] == "HOLD"
    assert decision["holding_add_authorized"] is True
    assert decision["holding_add_existing_position_only"] is True
    assert decision["holding_add_formal_action_unchanged"] is True
    assert decision["holding_add_is_formal_buy"] is False
    assert decision["holding_add_no_auto_trade"] is True
    assert decision["holding_add_unknown_is_pass"] is False
    assert decision["holding_add_max_lots"] == 1
    assert decision["holding_add_hard_gate_unknowns"] == "predictability;moat"
    assert snapshot["architecture_contract"]["holding_staged_add_advisory_preserved"] is True
    assert snapshot["architecture_contract"]["holding_staged_add_may_mutate_formal_action"] is False


def test_dashboard_consumes_only_canonical_staged_add_advisory():
    snapshot = _snapshot()
    rows = _holdings(snapshot, {
        "603993": {"code": "603993", "name": "洛阳钼业", "quantity": 900, "average_cost": 18.9114}
    })
    assert len(rows) == 1
    assert rows[0]["formal_action"] == "HOLD"
    assert rows[0]["holding_add_authorized"] is True
    assert rows[0]["holding_add_max_lots"] == 1
    assert rows[0]["investor_action"] == "继续持有；可分批加仓1手"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"decision_scope": "CANDIDATE"}, "not an existing holding"),
        ({"production_action": "ADD"}, "must preserve Formal HOLD"),
        ({"holding_add_is_formal_buy": True}, "invalid holding_add_is_formal_buy"),
        ({"holding_add_unknown_is_pass": True}, "invalid holding_add_unknown_is_pass"),
        ({"holding_add_max_lots": "2"}, "capped at exactly one lot"),
        ({"valuation_confidence": "MEDIUM"}, "requires HIGH valuation confidence"),
        ({"price_date": ""}, "price date is unverified"),
        ({"hard_gate_failures": "financial_safety"}, "known hard-gate failure"),
        ({"confirmed_quantity": "0"}, "positive confirmed holding quantity"),
        ({"current_price": "22.0", "neutral_value": "28.0", "holding_add_max_price_to_neutral": "0.75"}, "exceeds authorized valuation ceiling"),
    ],
)
def test_invalid_staged_add_fails_closed(overrides, message):
    with pytest.raises(ValueError, match=message):
        _snapshot(_row(**overrides))
