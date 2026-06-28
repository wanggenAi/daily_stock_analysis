from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import evaluate_signal_forward
from src.strategies.genge_cycle_bottom.signals import SignalType, StrategySignal


def _price_frame(closes: list[float], start: date = date(2024, 1, 1)) -> pd.DataFrame:
    rows = []
    for offset, close in enumerate(closes):
        rows.append(
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def _signal(as_of_date: str) -> StrategySignal:
    return StrategySignal(
        code="000001",
        stock_name="测试股票",
        as_of_date=as_of_date,
        signal_type=SignalType.LEFT_SMALL_BUY,
        total_score=70.0,
        price_percentile_score=80.0,
        valuation_score=70.0,
        financial_safety_score=70.0,
        trend_stabilization_score=70.0,
        market_environment_score=60.0,
        industry_cycle_score=50.0,
        stop_loss=93.0,
        max_position_pct=5.0,
    )


def test_forward_returns_drawdown_and_benchmark_are_calculated() -> None:
    closes = [100.0, 100.0] + [95.0] + [100.0] * 17 + [110.0] + [112.0] * 40 + [120.0] * 60 + [130.0] * 130
    benchmark_closes = [100.0] + [100.0] * 19 + [105.0] + [106.0] * 230
    price_df = _price_frame(closes)
    benchmark_df = _price_frame(benchmark_closes)

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df, benchmark_df, fee_bps=5, slippage_bps=10)

    assert result["entry_date"] == "2024-01-02"
    assert result["entry_mode"] == "next_open"
    assert result["raw_return_20d"] == 12.0
    assert result["net_return_20d"] == 11.7
    assert result["future_return_20d"] == 12.0
    assert result["close_max_drawdown_20d"] == -5.0
    assert result["low_max_drawdown_20d"] < result["close_max_drawdown_20d"]
    assert result["benchmark_return_20d"] == 5.0
    assert result["outperform_benchmark_20d"] is True
    assert result["hit_stop_loss_20d"] is False
    assert result["stop_adjusted_return_20d"] == result["raw_return_20d"]
    assert result["stop_adjusted_net_return_20d"] == result["net_return_20d"]


def test_forward_metrics_return_none_when_future_window_is_missing() -> None:
    price_df = _price_frame([100.0, 101.0, 102.0])

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["raw_return_20d"] is None
    assert result["net_return_20d"] is None
    assert result["low_max_drawdown_20d"] is None
    assert result["benchmark_return_20d"] is None
    assert result["outperform_benchmark_20d"] is None


def test_entry_falls_back_to_next_close_when_next_open_missing() -> None:
    price_df = _price_frame([100.0] + [110.0] * 300)
    price_df.loc[1, "open"] = None

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["entry_date"] == "2024-01-02"
    assert result["entry_price"] == 110.0
    assert result["entry_mode"] == "next_close"
    assert result["executable_entry_quality"] == "degraded"


def test_stop_loss_is_calculated_per_future_window() -> None:
    closes = [100.0, 100.0] + [101.0] * 24 + [80.0] + [100.0] * 260
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["hit_stop_loss_20d"] is False
    assert result["hit_stop_loss_60d"] is True
    assert result["hit_stop_loss_120d"] is True
    assert result["hit_stop_loss_250d"] is True
    assert result["stop_triggered_60d"] is True
    assert result["stop_adjusted_return_60d"] < result["raw_return_60d"]
    assert result["post_entry_adverse_excursion_pct"] is not None


def test_limit_up_entry_and_low_liquidity_are_recorded() -> None:
    price_df = _price_frame([100.0] + [110.0] * 300)
    price_df.loc[1, "open"] = 110.0
    price_df.loc[1, "volume"] = 50_000

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["limit_up_entry_risk"] is True
    assert result["abnormal_gap_open"] is True
    assert result["low_liquidity_risk"] is True
    assert result["executable_entry_quality"] == "risky"
    assert result["execution_risk_score"] >= 60
    assert "limit_up_entry_risk" in result["risk_flags"]
    assert "low_liquidity_risk" in result["risk_flags"]


def test_missing_next_bar_is_recorded_as_non_executable() -> None:
    price_df = _price_frame([100.0])

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["entry_price"] is None
    assert result["suspended_or_missing_bar"] is True
    assert result["executable_entry_quality"] == "unavailable"
    assert result["low_liquidity_risk"] is True
    assert "insufficient_entry_data" in result["risk_flags"]


def test_dynamic_stop_loss_is_never_above_entry_price() -> None:
    signal = _signal("2024-01-01")
    signal.stop_loss = 120.0
    price_df = _price_frame([100.0] + [105.0] * 300)

    result = evaluate_signal_forward(signal, price_df)

    assert result["dynamic_stop_loss"] <= result["entry_price"]
    assert result["stop_loss_distance_pct"] >= 0
