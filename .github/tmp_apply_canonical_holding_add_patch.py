from pathlib import Path

canonical = Path("src/strategies/genge_opportunity_discovery/canonical_snapshot.py")
text = canonical.read_text(encoding="utf-8")

marker = '''    "specialized_fair_pb",\n)\n\n\ndef _code'''
replacement = '''    "specialized_fair_pb",\n)\n\nHOLDING_ADD_CANONICAL_FIELDS = (\n    "holding_add_authorization_reason_codes",\n    "holding_add_authorized",\n    "holding_add_existing_position_only",\n    "holding_add_formal_action_unchanged",\n    "holding_add_hard_gate_unknowns",\n    "holding_add_is_formal_buy",\n    "holding_add_max_lots",\n    "holding_add_max_price_to_neutral",\n    "holding_add_no_auto_trade",\n    "holding_add_policy_version",\n    "holding_add_requires_high_confidence",\n    "holding_add_unknown_is_pass",\n)\nHOLDING_ADD_BOOLEAN_FIELDS = {\n    "holding_add_authorized",\n    "holding_add_existing_position_only",\n    "holding_add_formal_action_unchanged",\n    "holding_add_is_formal_buy",\n    "holding_add_no_auto_trade",\n    "holding_add_requires_high_confidence",\n    "holding_add_unknown_is_pass",\n}\n\n\ndef _code'''
if marker not in text:
    raise SystemExit("canonical constant insertion marker not found")
text = text.replace(marker, replacement, 1)

marker = '''def _compact_research(row: Mapping[str, Any], rank: int) -> dict[str, Any]:'''
helpers = '''def _holding_add_payload(row: Mapping[str, Any]) -> dict[str, Any]:\n    payload: dict[str, Any] = {}\n    for field in HOLDING_ADD_CANONICAL_FIELDS:\n        value = row.get(field)\n        if value is None or str(value).strip() == "":\n            continue\n        if field in HOLDING_ADD_BOOLEAN_FIELDS:\n            payload[field] = _bool(value)\n        elif field == "holding_add_max_lots":\n            payload[field] = _int(value, default=0)\n        else:\n            payload[field] = value\n    return payload\n\n\ndef _required_holding_add_bool(row: Mapping[str, Any], field: str, expected: bool, code: str) -> None:\n    raw = row.get(field)\n    if raw is None or str(raw).strip() == "":\n        raise ValueError(f"canonical staged-add missing {field} for {code}")\n    if _bool(raw) is not expected:\n        raise ValueError(f"canonical staged-add invalid {field} for {code}")\n\n\ndef _validate_holding_add_contract(row: Mapping[str, Any]) -> None:\n    if not _bool(row.get("holding_add_authorized")):\n        return\n    code = _code(row.get("code"))\n    scope = str(row.get("decision_scope") or row.get("scope") or "").strip().upper()\n    action = str(row.get("production_action") or row.get("action") or "").strip().upper()\n    if scope != "HOLDING":\n        raise ValueError(f"canonical staged-add is not an existing holding for {code}")\n    if action != "HOLD":\n        raise ValueError(f"canonical staged-add must preserve Formal HOLD for {code}")\n    if _float(row.get("confirmed_quantity"), default=0.0) <= 0:\n        raise ValueError(f"canonical staged-add requires positive confirmed holding quantity for {code}")\n    _required_holding_add_bool(row, "holding_add_existing_position_only", True, code)\n    _required_holding_add_bool(row, "holding_add_formal_action_unchanged", True, code)\n    _required_holding_add_bool(row, "holding_add_is_formal_buy", False, code)\n    _required_holding_add_bool(row, "holding_add_no_auto_trade", True, code)\n    _required_holding_add_bool(row, "holding_add_requires_high_confidence", True, code)\n    _required_holding_add_bool(row, "holding_add_unknown_is_pass", False, code)\n    if _int(row.get("holding_add_max_lots"), default=0) != 1:\n        raise ValueError(f"canonical staged-add must be capped at exactly one lot for {code}")\n    if not str(row.get("holding_add_policy_version") or "").strip():\n        raise ValueError(f"canonical staged-add policy version missing for {code}")\n    if not str(row.get("holding_add_authorization_reason_codes") or "").strip():\n        raise ValueError(f"canonical staged-add reason codes missing for {code}")\n    if str(row.get("valuation_confidence") or "").strip().upper() != "HIGH":\n        raise ValueError(f"canonical staged-add requires HIGH valuation confidence for {code}")\n    if str(row.get("v311_expectation_input_status") or "").strip() != "READY":\n        raise ValueError(f"canonical staged-add lacks READY strict-PIT input for {code}")\n    if str(row.get("v311_input_error") or "").strip():\n        raise ValueError(f"canonical staged-add has strict-PIT input error for {code}")\n    if str(row.get("hard_gate_failures") or "").strip():\n        raise ValueError(f"canonical staged-add has known hard-gate failure for {code}")\n    price_date = _date(row.get("price_date"))\n    decision_date = _date(row.get("decision_date"))\n    if price_date is None or decision_date is None or price_date > decision_date:\n        raise ValueError(f"canonical staged-add price date is unverified for {code}")\n    current_price = _float(row.get("current_price") or row.get("source_current_price"), default=0.0)\n    neutral_value = _float(row.get("neutral_value") or row.get("source_neutral_value"), default=0.0)\n    max_ratio = _float(row.get("holding_add_max_price_to_neutral"), default=0.0)\n    if current_price <= 0 or neutral_value <= 0 or max_ratio <= 0:\n        raise ValueError(f"canonical staged-add valuation inputs missing for {code}")\n    if current_price / neutral_value > max_ratio + 1e-12:\n        raise ValueError(f"canonical staged-add price exceeds authorized valuation ceiling for {code}")\n\n\n'''
if marker not in text:
    raise SystemExit("canonical helper insertion marker not found")
text = text.replace(marker, helpers + marker, 1)

marker = '''        action = str(row.get("production_action") or "").strip().upper()\n        if action in BUY_ADD_ACTIONS:'''
replacement = '''        _validate_holding_add_contract(row)\n\n        action = str(row.get("production_action") or "").strip().upper()\n        if action in BUY_ADD_ACTIONS:'''
if marker not in text:
    raise SystemExit("production validation marker not found")
text = text.replace(marker, replacement, 1)

marker = '''        "display_only_average_cost": row.get("display_only_average_cost") or "",\n    }\n    compact.update(_specialized_payload(row))\n    return compact'''
replacement = '''        "display_only_average_cost": row.get("display_only_average_cost") or "",\n    }\n    compact.update(_specialized_payload(row))\n    compact.update(_holding_add_payload(row))\n    return compact'''
if marker not in text:
    raise SystemExit("compact decision marker not found")
text = text.replace(marker, replacement, 1)

marker = '''            "specialized_valuation_evidence_preserved": True,\n        },'''
replacement = '''            "specialized_valuation_evidence_preserved": True,\n            "holding_staged_add_advisory_preserved": True,\n            "holding_staged_add_may_mutate_formal_action": False,\n        },'''
if marker not in text:
    raise SystemExit("architecture contract marker not found")
text = text.replace(marker, replacement, 1)

marker = '''        action = str(row.get("action") or "").upper()\n        if action in BUY_ADD_ACTIONS:'''
replacement = '''        _validate_holding_add_contract(row)\n        action = str(row.get("action") or "").upper()\n        if action in BUY_ADD_ACTIONS:'''
if marker not in text:
    raise SystemExit("compact validation marker not found")
text = text.replace(marker, replacement, 1)

canonical.write_text(text, encoding="utf-8")

test = Path("tests/test_genge_canonical_holding_add_propagation.py")
test.write_text(r'''import pytest

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
''', encoding="utf-8")
