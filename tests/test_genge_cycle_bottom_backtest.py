from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BALANCED_EXIT_POLICY_NAME
from src.strategies.genge_cycle_bottom.backtest import evaluate_signal_forward
from src.strategies.genge_cycle_bottom.backtest import simulate_exit_policy
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


def _signal_with_trend(as_of_date: str, trend_level: str, stop_loss: float = 50.0) -> StrategySignal:
    signal = _signal(as_of_date)
    signal.trend_confirmation_level = trend_level
    signal.stop_loss = stop_loss
    return signal


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


def test_exit_policy_fields_exist_and_use_net_return_costs() -> None:
    price_df = _price_frame([100.0] + [100.0] * 80)

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df, fee_bps=5, slippage_bps=10)

    assert result["exit_policy_name"] == "hybrid_60d_repair_exit"
    assert result["balanced_exit_policy_name"] == BALANCED_EXIT_POLICY_NAME
    assert result["exit_reason_20d"] == "TIME_EXIT"
    assert result["exit_adjusted_raw_return_20d"] == 0.0
    assert result["exit_adjusted_net_return_20d"] == -0.3
    assert result["exit_adjusted_max_drawdown_20d"] <= result["low_max_drawdown_20d"]
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "TIME_EXIT_60D"
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d"] == -0.3


def test_fixed_60d_time_exit_caps_long_horizon_at_60_days() -> None:
    closes = [100.0, 100.0] + [101.0] * 58 + [120.0] + [140.0] * 220
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(_signal("2024-01-01"), price_df)

    assert result["fixed_60d_time_exit_exit_reason_120d"] == "TIME_EXIT"
    assert result["fixed_60d_time_exit_exit_holding_days_120d"] == 60
    assert result["fixed_60d_time_exit_exit_adjusted_raw_return_120d"] == 20.0


def test_exit_policy_stop_loss_has_priority_over_time_exit() -> None:
    signal = _signal("2024-01-01")
    signal.stop_loss = 93.0
    closes = [100.0, 100.0, 80.0] + [120.0] * 260
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result["exit_reason_60d"] == "STOP_LOSS"
    assert result["exit_adjusted_raw_return_60d"] == -7.0
    assert result["exit_holding_days_60d"] == 2


def test_trend_break_exit_triggers_after_two_closes_below_ma20() -> None:
    signal = _signal("2024-01-01")
    signal.stop_loss = 50.0
    closes = [100.0, 100.0] + [100.0] * 7 + [96.0, 95.0] + [95.0] * 80
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result["trend_break_exit_exit_reason_60d"] == "MA20_LOSS"
    assert result["trend_break_exit_exit_holding_days_60d"] == 10


def test_profit_trailing_exit_does_not_peek_at_future_high() -> None:
    signal = _signal("2024-01-01")
    signal.stop_loss = 50.0
    closes = [100.0, 100.0, 104.0, 109.0, 103.0] + [150.0] * 80
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result["profit_trailing_exit_exit_reason_60d"] == "TAKE_PROFIT_TRAIL"
    assert result["profit_trailing_exit_exit_price_60d"] == 103.0
    assert result["profit_trailing_exit_exit_adjusted_raw_return_60d"] == 3.0


def test_same_day_exit_conditions_use_conservative_priority() -> None:
    signal = _signal("2024-01-01")
    signal.stop_loss = 93.0
    price_df = _price_frame([100.0] + [120.0] * 80)
    price_df.loc[1, "open"] = 100.0
    price_df.loc[1, "low"] = 90.0
    price_df.loc[1, "high"] = 130.0
    price_df.loc[1, "close"] = 120.0

    result = evaluate_signal_forward(signal, price_df)

    assert result["exit_reason_20d"] == "STOP_LOSS"
    assert result["exit_adjusted_raw_return_20d"] == -7.0


def test_balanced_exit_keeps_old_hybrid_fields_separate() -> None:
    closes = [100.0, 100.0] + [101.0] * 80
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(_signal_with_trend("2024-01-01", "MEDIUM"), price_df)

    assert result["exit_policy_name"] == "hybrid_60d_repair_exit"
    assert result["exit_reason_60d"] is not None
    assert result[f"hybrid_60d_repair_exit_exit_reason_60d"] == result["exit_reason_60d"]
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] is not None
    assert f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d" in result


def test_balanced_trend_break_requires_three_closes_below_ma20() -> None:
    signal = _signal_with_trend("2024-01-01", "MEDIUM")
    closes = [100.0, 100.0] + [100.0] * 22 + [99.0, 98.0, 97.0] + [97.0] * 80
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "TREND_BREAK_CONFIRMED"
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_holding_days_60d"] >= 20


def test_balanced_stop_loss_can_use_configured_minimum_distance() -> None:
    signal = _signal_with_trend("2024-01-01", "MEDIUM", stop_loss=98.0)
    closes = [100.0, 100.0] + [97.0] + [100.0] * 80
    price_df = _price_frame(closes)
    future_rows = price_df.iloc[1:].reset_index(drop=True)

    result = simulate_exit_policy(
        signal=signal,
        entry_price=100.0,
        future_rows=future_rows,
        horizon_days=60,
        stop_loss=98.0,
        policy_name=BALANCED_EXIT_POLICY_NAME,
        params={
            "stop_loss_min_pct": 10.0,
            "stop_loss_max_pct": 12.0,
            "trail_start_pct": 12.0,
            "trail_drawdown_pct": 8.0,
            "profit_high_pct": 20.0,
            "profit_high_trail_drawdown_pct": 6.0,
            "trend_break_min_days": 20,
            "no_repair_days": 40,
        },
    )

    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "TIME_EXIT_60D"
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_holding_days_60d"] == 60


def test_balanced_close_confirmed_stop_ignores_intraday_reclaim_but_keeps_hard_stop() -> None:
    signal = _signal_with_trend("2024-01-01", "MEDIUM", stop_loss=94.0)
    closes = [100.0] * 90
    price_df = _price_frame(closes)
    future_rows = price_df.iloc[1:].reset_index(drop=True)
    future_rows.loc[1, "low"] = 93.5
    future_rows.loc[1, "close"] = 96.0

    reclaimed = simulate_exit_policy(
        signal=signal,
        entry_price=100.0,
        future_rows=future_rows,
        horizon_days=60,
        stop_loss=94.0,
        policy_name=BALANCED_EXIT_POLICY_NAME,
        params={
            "stop_loss_min_pct": 6.0,
            "stop_loss_max_pct": 12.0,
            "stop_confirm_by_close": True,
            "stop_hard_intraday_pct": 2.5,
            "trail_start_pct": 18.0,
            "trail_drawdown_pct": 12.0,
            "profit_high_pct": 26.0,
            "profit_high_trail_drawdown_pct": 8.0,
            "trend_break_min_days": 45,
            "no_repair_days": 55,
        },
    )

    hard_stop_rows = future_rows.copy()
    hard_stop_rows.loc[1, "low"] = 91.0
    hard = simulate_exit_policy(
        signal=signal,
        entry_price=100.0,
        future_rows=hard_stop_rows,
        horizon_days=60,
        stop_loss=94.0,
        policy_name=BALANCED_EXIT_POLICY_NAME,
        params={
            "stop_loss_min_pct": 6.0,
            "stop_loss_max_pct": 12.0,
            "stop_confirm_by_close": True,
            "stop_hard_intraday_pct": 2.5,
            "trail_start_pct": 18.0,
            "trail_drawdown_pct": 12.0,
            "profit_high_pct": 26.0,
            "profit_high_trail_drawdown_pct": 8.0,
            "trend_break_min_days": 45,
            "no_repair_days": 55,
        },
    )

    assert reclaimed[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "TIME_EXIT_60D"
    assert hard[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "STOP_LOSS"


def test_balanced_profit_trailing_does_not_peek_at_future_high() -> None:
    signal = _signal_with_trend("2024-01-01", "STRONG")
    closes = [100.0, 100.0] + [108.0, 115.0, 126.0, 115.0] + [150.0] * 120
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "TAKE_PROFIT_TRAIL"
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_price_60d"] == 115.0
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_raw_return_60d"] == 15.0


def test_balanced_strong_trend_extends_but_weak_trend_exits_at_60d() -> None:
    closes = [100.0, 100.0] + [100.0 + offset * 0.3 for offset in range(1, 150)]
    price_df = _price_frame(closes)

    strong_result = evaluate_signal_forward(_signal_with_trend("2024-01-01", "STRONG"), price_df)
    weak_result = evaluate_signal_forward(_signal_with_trend("2024-01-01", "WEAK"), price_df)

    assert strong_result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_120d"] == "TREND_EXTENSION_90D"
    assert strong_result[f"{BALANCED_EXIT_POLICY_NAME}_exit_holding_days_120d"] == 90
    assert weak_result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_120d"] == "TIME_EXIT_60D"
    assert weak_result[f"{BALANCED_EXIT_POLICY_NAME}_exit_holding_days_120d"] == 60


def test_balanced_no_repair_55d_exits_without_early_20d_cut() -> None:
    signal = _signal_with_trend("2024-01-01", "WEAK")
    closes = [100.0, 100.0] + [99.5] * 80
    price_df = _price_frame(closes)

    result = evaluate_signal_forward(signal, price_df)

    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"] == "NO_REPAIR_40D"
    assert result[f"{BALANCED_EXIT_POLICY_NAME}_exit_holding_days_60d"] == 55
