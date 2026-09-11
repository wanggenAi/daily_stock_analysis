import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.holding_valuation_continuity import (
    ROUND6_POLICY_SOURCE,
    assess_holding_valuation_state,
)
from src.strategies.genge_opportunity_discovery.v311_current_expectation_inputs import (
    value_expectation_10y,
)


def _state(path: Path, neutral: float) -> None:
    path.write_text(
        json.dumps(
            {
                "contract_version": "V311_HOLDING_SELL_RATIONALE_V3",
                "latest_applied_snapshot_id": "prev",
                "latest_applied_source_run_id": "1",
                "no_auto_trade": True,
                "holdings": {
                    "600001": {
                        "action": "HOLD_REVIEW",
                        "value_low": None,
                        "neutral_value": neutral,
                        "value_high": None,
                        "normalized_earnings": 1.690347960868041,
                        "current_price": 29.73,
                        "valuation_confidence": "LOW",
                        "canonical_snapshot_id": "prev",
                        "canonical_source_run_id": "1",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _generic_row(**overrides):
    eps = 1.690347960868041
    growth = 0.20636294218718887
    row = {
        "code": "600001",
        "v311_has_position": True,
        "v311_expectation_input_status": "READY",
        "v311_expectation_policy_source": ROUND6_POLICY_SOURCE,
        "v31_normalized_profit": eps,
        "normalized_earnings": eps,
        "v31_realistic_profit_cagr": growth,
        "realistic_growth": growth,
        "v31_neutral_value": value_expectation_10y(eps, growth),
        "realistic_growth_four_report_range": growth,
        "eps_growth_3y_round6": growth,
        "revenue_growth_3y_round6": 0.2411362767737332,
        "v31_current_price": 29.73,
        "valuation_confidence": "LOW",
    }
    row.update(overrides)
    return row


def test_generic_strict_pit_holding_gets_auditable_low_neutral_high(tmp_path: Path):
    row = _generic_row()
    state = tmp_path / "state.json"
    _state(state, row["v31_neutral_value"])

    result = assess_holding_valuation_state(row, path=state)

    assert result["valuation_range_ready"] is True
    assert result["valuation_range_source"] == "V311_STRICT_PIT_GENERIC_RANGE"
    assert result["valuation_range_method"] == "ROUND6_10Y_EARNING_POWER_REALISTIC_GROWTH_UNCERTAINTY_BAND"
    assert result["valuation_range_neutral_roundtrip_verified"] is True
    assert result["value_low"] == pytest.approx(value_expectation_10y(row["normalized_earnings"], 0.0))
    assert result["neutral_value"] == pytest.approx(row["v31_neutral_value"])
    assert result["value_high"] == pytest.approx(value_expectation_10y(row["normalized_earnings"], 0.30))
    assert result["value_low"] < result["neutral_value"] < result["value_high"]
    assert result["valuation_change"] == "STABLE"
    assert result["price_value_zone"] == "FAIR_VALUE"
    assert result["profit_alone_is_sell_reason"] is False
    assert result["profit_used_by_formal_decision"] is False


def test_generic_range_does_not_use_price_cost_or_profit(tmp_path: Path):
    base = _generic_row()
    state = tmp_path / "state.json"
    _state(state, base["v31_neutral_value"])
    a = assess_holding_valuation_state(
        _generic_row(v31_current_price=20.0, average_cost=1.0, unrealized_profit_pct=1900.0),
        path=state,
    )
    b = assess_holding_valuation_state(
        _generic_row(v31_current_price=60.0, average_cost=100.0, unrealized_profit_pct=-40.0),
        path=state,
    )
    assert a["value_low"] == pytest.approx(b["value_low"])
    assert a["neutral_value"] == pytest.approx(b["neutral_value"])
    assert a["value_high"] == pytest.approx(b["value_high"])
    assert a["profit_alone_is_sell_reason"] is False
    assert b["profit_alone_is_sell_reason"] is False


def test_generic_range_fails_closed_when_neutral_does_not_match_frozen_formula(tmp_path: Path):
    row = _generic_row(v31_neutral_value=123.45)
    state = tmp_path / "state.json"
    _state(state, 123.45)
    result = assess_holding_valuation_state(row, path=state)
    assert result["valuation_range_ready"] is False
    assert result["value_low"] is None
    assert result["value_high"] is None
    assert result["price_value_zone"] == "UNKNOWN"


def test_generic_range_fails_closed_for_non_round6_or_non_ready_inputs(tmp_path: Path):
    row = _generic_row()
    state = tmp_path / "state.json"
    _state(state, row["v31_neutral_value"])
    wrong_policy = assess_holding_valuation_state(
        _generic_row(v311_expectation_policy_source="OTHER_POLICY"), path=state
    )
    not_ready = assess_holding_valuation_state(
        _generic_row(v311_expectation_input_status="HOLD_REVIEW_INPUT_INCOMPLETE"), path=state
    )
    assert wrong_policy["valuation_range_ready"] is False
    assert not_ready["valuation_range_ready"] is False
