import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery import holding_valuation_continuity as hvc
from src.strategies.genge_opportunity_discovery import production_model
from src.strategies.genge_opportunity_discovery.holding_valuation_continuity import (
    assess_holding_valuation_state,
    sell_review_required,
)
from src.strategies.genge_opportunity_discovery.selection_framework_v311 import (
    V311Decision,
    ValuationConfidence,
)


def _write_state(path: Path, *, low=80.0, neutral=100.0, high=120.0, action="HOLD") -> None:
    path.write_text(
        json.dumps(
            {
                "contract_version": "V311_HOLDING_SELL_RATIONALE_V3",
                "latest_applied_snapshot_id": "snapshot-prev",
                "latest_applied_source_run_id": "100",
                "no_auto_trade": True,
                "holdings": {
                    "600000": {
                        "action": action,
                        "value_low": low,
                        "neutral_value": neutral,
                        "value_high": high,
                        "normalized_earnings": 10.0,
                        "current_price": 100.0,
                        "valuation_confidence": "HIGH",
                        "canonical_snapshot_id": "snapshot-prev",
                        "canonical_source_run_id": "100",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _row(**overrides):
    row = {
        "code": "600000",
        "v311_has_position": True,
        "v31_pessimistic_value": 80.0,
        "v31_neutral_value": 100.0,
        "v31_optimistic_value": 120.0,
        "v31_current_price": 100.0,
        "v31_normalized_profit": 10.0,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("profit_pct", [20.0, 30.0, 40.0, 50.0])
def test_profit_alone_cannot_authorize_reduce(tmp_path: Path, profit_pct: float):
    state = tmp_path / "state.json"
    _write_state(state)
    required, reasons = sell_review_required(
        _row(v31_current_price=110.0, unrealized_profit_pct=profit_pct),
        "REDUCE_25",
        path=state,
    )
    assert required is True
    assert "SELL_RATIONALE_NOT_MATERIAL" in reasons


def test_high_profit_raised_valuation_under_new_high_does_not_create_profit_reduce(tmp_path: Path):
    state = tmp_path / "state.json"
    _write_state(state, low=80.0, neutral=100.0, high=120.0)
    assessment = assess_holding_valuation_state(
        _row(
            v31_pessimistic_value=100.0,
            v31_neutral_value=130.0,
            v31_optimistic_value=160.0,
            v31_current_price=125.0,
            unrealized_profit_pct=50.0,
        ),
        path=state,
    )
    assert assessment["valuation_change"] == "RAISED"
    assert assessment["price_value_zone"] == "FAIR_VALUE"
    assert assessment["profit_protection_overlay_eligible"] is False
    assert assessment["profit_alone_is_sell_reason"] is False
    assert assessment["profit_used_by_formal_decision"] is False


def test_stable_value_near_high_plus_risk_can_support_reduce_with_sell_rationale(tmp_path: Path):
    state = tmp_path / "state.json"
    _write_state(state, low=80.0, neutral=100.0, high=130.0)
    data = _row(
        v31_pessimistic_value=80.0,
        v31_neutral_value=100.0,
        v31_optimistic_value=130.0,
        v31_current_price=125.0,
        unlock_window_active=True,
        unrealized_profit_pct=45.0,
    )
    assessment = assess_holding_valuation_state(data, path=state)
    required, reasons = sell_review_required(data, "REDUCE_25", path=state)
    assert assessment["valuation_change"] == "STABLE"
    assert assessment["price_value_zone"] == "UPPER_VALUE"
    assert assessment["profit_protection_overlay_eligible"] is True
    assert required is False
    assert reasons == ("SELL_RATIONALE_VALUE_RISK_PROTECTION",)


def test_sub_one_percent_valuation_change_is_stable_and_does_not_churn(tmp_path: Path):
    state = tmp_path / "state.json"
    _write_state(state, low=80.0, neutral=100.0, high=120.0)
    assessment = assess_holding_valuation_state(
        _row(
            v31_pessimistic_value=80.4,
            v31_neutral_value=100.5,
            v31_optimistic_value=120.6,
            v31_current_price=100.0,
        ),
        path=state,
    )
    assert assessment["valuation_change"] == "STABLE"
    assert assessment["valuation_change_materiality_threshold"] == 0.01


def _hold_decision(neutral: float, current: float) -> V311Decision:
    return V311Decision(
        action="HOLD",
        target_position_fraction=1.0,
        valuation_confidence=ValuationConfidence.HIGH,
        reason_codes=("FUNDAMENTALS_INTACT", "NO_ACTION_THRESHOLD"),
        normalized_earnings=10.0,
        realistic_growth=0.10,
        market_implied_growth=0.08,
        expectation_gap=0.02,
        neutral_value=neutral,
        current_price=current,
        price_to_neutral=current / neutral,
    )


def test_materially_lowered_valuation_reopens_sell_review_without_big_profit(tmp_path: Path, monkeypatch):
    state = tmp_path / "state.json"
    _write_state(state, low=80.0, neutral=100.0, high=120.0)
    monkeypatch.setattr(hvc, "STATE_PATH", state)
    monkeypatch.setattr(production_model, "decide_v311", lambda data: _hold_decision(80.0, 75.0))

    decision = production_model.decide_production(
        _row(v31_pessimistic_value=65.0, v31_neutral_value=80.0, v31_optimistic_value=95.0, v31_current_price=75.0)
    )
    assert decision.action == "HOLD_REVIEW"
    assert "VALUATION_LOWERED" in decision.reason_codes
    assert "MATERIAL_VALUATION_CHANGE_REQUIRES_SELL_REVIEW" in decision.reason_codes


def test_old_value_high_exceeded_but_new_valuation_raised_does_not_auto_sell(tmp_path: Path, monkeypatch):
    state = tmp_path / "state.json"
    _write_state(state, low=80.0, neutral=100.0, high=120.0)
    monkeypatch.setattr(hvc, "STATE_PATH", state)
    monkeypatch.setattr(production_model, "decide_v311", lambda data: _hold_decision(130.0, 125.0))

    decision = production_model.decide_production(
        _row(
            v31_pessimistic_value=100.0,
            v31_neutral_value=130.0,
            v31_optimistic_value=160.0,
            v31_current_price=125.0,
            unrealized_profit_pct=50.0,
        )
    )
    assert 125.0 > 120.0  # prior value_high
    assert decision.action == "HOLD"
    assert all(not reason.startswith("SELL_") for reason in decision.reason_codes)
