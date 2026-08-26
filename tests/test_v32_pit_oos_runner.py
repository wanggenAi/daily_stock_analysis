from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import v32_pit_oos_round8_round9 as runner  # noqa: E402


def panel(confidence: str = "HIGH") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2018-01-31", "2018-02-28", "2018-03-30"]),
            "ret": [0.0, 0.0, 0.0],
            "close": [70.0, 150.0, 150.0],
            "ratio_expectation": [0.70, 1.50, 1.50],
            "neutral_value_round6": [100.0, 100.0, 100.0],
            "valuation_confidence": [confidence, confidence, confidence],
            "normalized_eps_round6": [5.0, 5.0, 5.0],
            "realistic_growth_round6": [0.10, 0.10, 0.10],
            "market_implied_growth_round6": [0.05, 0.20, 0.20],
            "expectation_gap_round6": [0.05, -0.10, -0.10],
        }
    )


def test_v32_sell_waits_for_second_consecutive_month() -> None:
    result = runner.run_variant({"600000": panel()}, {"600000": "test"}, "v32_candidate")
    assert result.trades["action"].tolist() == ["BUY_A_LEVEL", "REDUCE_50"]
    decisions = result.decisions
    february = decisions[decisions["date"] == pd.Timestamp("2018-02-28")].iloc[0]
    assert february["action"] == "HOLD_REVIEW"
    assert february["sell_confirmation_count"] == 1


def test_current_v31_sells_immediately() -> None:
    result = runner.run_variant({"600000": panel()}, {"600000": "test"}, "current_v31_baseline")
    assert result.trades["action"].tolist() == ["BUY_A_LEVEL", "REDUCE_50"]
    assert result.trades.iloc[1]["date"] == pd.Timestamp("2018-02-28")


def test_low_confidence_never_executes_mechanical_action() -> None:
    result = runner.run_variant(
        {"600000": panel("LOW")}, {"600000": "test"}, "v31_1_confidence_gate_only"
    )
    assert result.trades.empty
    assert set(result.decisions["action"]) == {"HOLD_REVIEW"}
    assert result.summary["mechanical_low_invalid_actions"] == 0


def test_confidence_merge_normalizes_datetime_units() -> None:
    daily = panel().iloc[:1].copy()
    daily["fund_available_date"] = pd.Series(
        [pd.Timestamp("2017-12-31")], dtype="datetime64[s]"
    )
    daily["date"] = pd.to_datetime(daily["date"]).astype("datetime64[ns]")
    financial = pd.DataFrame(
        {
            "available_date": pd.Series([pd.Timestamp("2017-12-31")], dtype="datetime64[us]"),
            "report_date": pd.to_datetime(["2017-09-30"]),
            "clean_eps_round6": [1.0],
            "realistic_growth_round6": [0.1],
        }
    )
    merged = runner.add_confidence_inputs(daily, financial)
    assert len(merged) == 1
    assert merged["normalized_earnings_observation_count"].iloc[0] == 1
