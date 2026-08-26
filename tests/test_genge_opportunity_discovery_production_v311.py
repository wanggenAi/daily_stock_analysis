from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery.production_model import (
    PRODUCTION_MODEL_VERSION,
    PRODUCTION_POLICY_SOURCE,
    V32_SELL_CONFIRMATION_ENABLED,
    production_payload,
)
from tests.test_genge_opportunity_discovery_selection_framework_v311 import complete_v311_row


def test_existing_genge_ci_covers_v311_production_wiring() -> None:
    payload = production_payload(complete_v311_row(current=150.0))
    assert PRODUCTION_MODEL_VERSION == "GEN_GE_V3_1_1_PRODUCTION"
    assert payload["production_action"] == "REDUCE_50"
    assert payload["production_sell_contract"] == "V31_IMMEDIATE_VALUATION_LADDER"
    assert payload["production_policy_source"] == PRODUCTION_POLICY_SOURCE
    assert payload["v32_sell_confirmation_enabled"] is False
    assert V32_SELL_CONFIRMATION_ENABLED is False


def test_production_module_has_no_v32_import() -> None:
    path = Path(__file__).resolve().parents[1] / "src/strategies/genge_opportunity_discovery/production_model.py"
    text = path.read_text(encoding="utf-8")
    assert "selection_framework_v311" in text
    assert "selection_framework_v32" not in text


def test_production_hard_gate_still_overrides_invalid_confidence() -> None:
    row = complete_v311_row(current=90.0)
    row["v31_neutral_value"] = None
    row["v31_moat_status"] = "FAIL"
    payload = production_payload(row)
    assert payload["valuation_confidence"] == "INVALID"
    assert payload["production_action"] == "EXIT"
    assert payload["production_target_position_fraction"] == 0.0


def test_production_cost_basis_never_changes_sell() -> None:
    first = complete_v311_row(current=180.0)
    first["personal_cost_basis"] = 10.0
    second = dict(first)
    second["personal_cost_basis"] = 300.0
    assert production_payload(first)["production_action"] == "CORE_ONLY"
    assert production_payload(second)["production_action"] == "CORE_ONLY"
