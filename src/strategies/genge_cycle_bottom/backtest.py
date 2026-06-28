"""Walk-forward backtest for GenGe Cycle Bottom Strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .features import coerce_date, finite_float, prepare_price_frame, slice_as_of
from .signals import SignalType, StrategySignal
from .strategy import GenGeCycleBottomStrategy


EVAL_WINDOWS = (20, 60, 120, 250)
ENTRY_SIGNAL_TYPES = {SignalType.LEFT_SMALL_BUY, SignalType.CONFIRM_BUY, SignalType.ADD}
LIMIT_MOVE_THRESHOLD = 9.5
ABNORMAL_GAP_THRESHOLD = 7.0
LOW_LIQUIDITY_AMOUNT = 5_000_000.0
LOW_LIQUIDITY_VOLUME = 100_000.0
EXIT_POLICY_NAME = "hybrid_60d_repair_exit"
EXIT_POLICY_NAMES = (
    "fixed_60d_time_exit",
    "trend_break_exit",
    "profit_trailing_exit",
    EXIT_POLICY_NAME,
)
EXIT_POLICY_EXPERIMENTS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "stop_loss_max_pct": 8.0,
        "trail_start_pct": 6.0,
        "trail_drawdown_pct": 4.0,
        "max_holding_days": 60,
        "allow_extension_if_strong_trend": False,
    },
    "balanced": {
        "stop_loss_max_pct": 10.0,
        "trail_start_pct": 8.0,
        "trail_drawdown_pct": 5.0,
        "max_holding_days": 60,
        "allow_extension_if_strong_trend": False,
    },
    "loose": {
        "stop_loss_max_pct": 12.0,
        "trail_start_pct": 10.0,
        "trail_drawdown_pct": 6.0,
        "max_holding_days": 90,
        "allow_extension_if_strong_trend": False,
    },
    "trend_extend": {
        "stop_loss_max_pct": 10.0,
        "trail_start_pct": 8.0,
        "trail_drawdown_pct": 6.0,
        "max_holding_days": 120,
        "allow_extension_if_strong_trend": True,
    },
}


@dataclass
class BacktestInput:
    code: str
    stock_name: str
    price_df: pd.DataFrame
    valuation_df: Optional[pd.DataFrame] = None
    financial_df: Optional[pd.DataFrame] = None
    industry: Optional[str] = None
    extra_risk_flags: Optional[List[str]] = None


def max_drawdown_from_values(start_price: float, values: Iterable[float]) -> Optional[float]:
    start = finite_float(start_price)
    if start is None or start <= 0:
        return None
    running_peak = start
    worst = 0.0
    for raw_value in values:
        value = finite_float(raw_value)
        if value is None:
            continue
        running_peak = max(running_peak, value)
        if running_peak > 0:
            worst = min(worst, (value - running_peak) / running_peak)
    return round(worst * 100, 4)


def max_drawdown_from_closes(start_price: float, closes: Iterable[float]) -> Optional[float]:
    return max_drawdown_from_values(start_price, closes)


def future_return(start_price: float, future_rows: pd.DataFrame, days: int) -> Optional[float]:
    start = finite_float(start_price)
    if start is None or start <= 0 or len(future_rows) < days:
        return None
    end_close = finite_float(future_rows.iloc[days - 1].get("close"))
    if end_close is None:
        return None
    return round((end_close - start) / start * 100, 4)


def net_return_from_raw(raw_return_pct: Optional[float], fee_bps: float, slippage_bps: float) -> Optional[float]:
    raw = finite_float(raw_return_pct)
    if raw is None:
        return None
    total_cost_pct = (float(fee_bps) + float(slippage_bps)) * 2.0 / 100.0
    return round(raw - total_cost_pct, 4)


def benchmark_return(benchmark_df: Optional[pd.DataFrame], as_of_date: date, days: int) -> Optional[float]:
    if benchmark_df is None or benchmark_df.empty:
        return None
    df = prepare_price_frame(benchmark_df)
    history = df[df["date"] <= as_of_date]
    future = df[df["date"] > as_of_date].sort_values("date")
    if history.empty or len(future) < days:
        return None
    start_close = finite_float(history.iloc[-1].get("close"))
    return future_return(start_close, future, days) if start_close is not None else None


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / previous * 100.0


def _execution_diagnostics(history: pd.DataFrame, entry_row: Optional[pd.Series], entry_mode: str) -> Dict[str, object]:
    previous_close = finite_float(history.iloc[-1].get("close")) if not history.empty else None
    if entry_row is None:
        return {
            "suspended_or_missing_bar": True,
            "limit_up_entry_risk": False,
            "limit_down_entry_risk": False,
            "limit_down_exit_risk": False,
            "abnormal_gap_open": False,
            "low_liquidity_risk": True,
            "executable_entry_quality": "unavailable",
            "execution_risk_score": 100.0,
        }

    next_open = finite_float(entry_row.get("open"))
    next_close = finite_float(entry_row.get("close"))
    open_change_pct = _pct_change(next_open, previous_close)
    amount = finite_float(entry_row.get("amount")) if "amount" in entry_row.index else None
    volume = finite_float(entry_row.get("volume")) if "volume" in entry_row.index else None
    low_liquidity = False
    if amount is not None:
        low_liquidity = amount < LOW_LIQUIDITY_AMOUNT
    elif volume is not None:
        low_liquidity = volume < LOW_LIQUIDITY_VOLUME
    else:
        low_liquidity = True

    limit_up = bool(open_change_pct is not None and open_change_pct >= LIMIT_MOVE_THRESHOLD)
    limit_down = bool(open_change_pct is not None and open_change_pct <= -LIMIT_MOVE_THRESHOLD)
    abnormal_gap = bool(open_change_pct is not None and abs(open_change_pct) >= ABNORMAL_GAP_THRESHOLD)
    if entry_mode == "insufficient_entry_data":
        quality = "unavailable"
    elif entry_mode != "next_open" or next_open is None or next_open <= 0:
        quality = "degraded"
    elif limit_up or limit_down:
        quality = "risky"
    elif low_liquidity or abnormal_gap:
        quality = "degraded"
    else:
        quality = "good"
    execution_risk_score = 0.0
    if quality == "unavailable":
        execution_risk_score = 100.0
    else:
        if limit_up:
            execution_risk_score += 45
        if limit_down:
            execution_risk_score += 45
        if abnormal_gap:
            execution_risk_score += 20
        if low_liquidity:
            execution_risk_score += 25
        if entry_mode != "next_open":
            execution_risk_score += 15

    return {
        "suspended_or_missing_bar": False,
        "limit_up_entry_risk": limit_up,
        "limit_down_entry_risk": limit_down,
        "limit_down_exit_risk": limit_down,
        "abnormal_gap_open": abnormal_gap,
        "low_liquidity_risk": low_liquidity,
        "executable_entry_quality": quality,
        "execution_risk_score": round(min(100.0, execution_risk_score), 2),
        "entry_open_change_pct": round(open_change_pct, 4) if open_change_pct is not None else None,
        "entry_close_available": bool(next_close is not None and next_close > 0),
    }


def _effective_stop_loss(stop_loss: Optional[float], entry_price: Optional[float]) -> Optional[float]:
    stop = finite_float(stop_loss)
    entry = finite_float(entry_price)
    if stop is None or entry is None or entry <= 0:
        return None
    return round(min(stop, entry * 0.995), 4)


def _stop_adjusted_return(entry_price: float, future_rows: pd.DataFrame, days: int, stop_loss: Optional[float]) -> tuple[Optional[float], bool, Optional[str]]:
    raw = future_return(entry_price, future_rows, days)
    stop = _effective_stop_loss(stop_loss, entry_price)
    if raw is None or stop is None or len(future_rows) < days or "low" not in future_rows.columns:
        return raw, False, None
    window = future_rows.head(days).copy()
    lows = pd.to_numeric(window["low"], errors="coerce")
    hit_mask = lows <= stop
    if not bool(hit_mask.any()):
        return raw, False, None
    hit_index = hit_mask[hit_mask].index[0]
    hit_date = window.loc[hit_index].get("date")
    adjusted = round((stop - entry_price) / entry_price * 100.0, 4)
    return adjusted, True, hit_date.isoformat() if hasattr(hit_date, "isoformat") else str(hit_date)


def _policy_stop_loss(entry_price: float, stop_loss: Optional[float], params: Optional[Dict[str, Any]] = None) -> Optional[float]:
    stop = _effective_stop_loss(stop_loss, entry_price)
    max_pct = finite_float((params or {}).get("stop_loss_max_pct"))
    if max_pct is not None and max_pct > 0:
        cap_stop = entry_price * (1.0 - max_pct / 100.0)
        stop = max(stop, cap_stop) if stop is not None else cap_stop
    return round(stop, 4) if stop is not None else None


def _max_policy_holding_days(policy_name: str, horizon_days: int, params: Optional[Dict[str, Any]], signal: StrategySignal) -> int:
    configured = int((params or {}).get("max_holding_days") or 0)
    if policy_name == "profit_trailing_exit":
        default_max = 120 if str(getattr(signal, "trend_confirmation_level", "") or "") == "STRONG" else 60
    elif policy_name in {"fixed_60d_time_exit", "trend_break_exit", EXIT_POLICY_NAME}:
        default_max = 60
    else:
        default_max = 60
    max_days = configured if configured > 0 else default_max
    if (params or {}).get("allow_extension_if_strong_trend") and str(getattr(signal, "trend_confirmation_level", "") or "") == "STRONG":
        max_days = max(max_days, 120)
    return max(1, min(int(horizon_days), int(max_days)))


def _exit_result(
    *,
    policy_name: str,
    horizon_days: int,
    entry_price: float,
    exit_row: Optional[pd.Series],
    reason: str,
    raw_return: Optional[float],
    net_return: Optional[float],
    max_drawdown: Optional[float],
    holding_days: Optional[int],
) -> Dict[str, object]:
    prefix = f"{policy_name}_"
    date_value = exit_row.get("date") if exit_row is not None else None
    exit_price = finite_float(exit_row.get("close")) if exit_row is not None else None
    return {
        f"{prefix}exit_date_{horizon_days}d": date_value.isoformat() if hasattr(date_value, "isoformat") else (str(date_value) if date_value is not None else None),
        f"{prefix}exit_reason_{horizon_days}d": reason,
        f"{prefix}exit_price_{horizon_days}d": round(exit_price, 4) if exit_price is not None else None,
        f"{prefix}exit_adjusted_raw_return_{horizon_days}d": raw_return,
        f"{prefix}exit_adjusted_net_return_{horizon_days}d": net_return,
        f"{prefix}exit_adjusted_max_drawdown_{horizon_days}d": max_drawdown,
        f"{prefix}exit_holding_days_{horizon_days}d": holding_days,
    }


def simulate_exit_policy(
    *,
    signal: StrategySignal,
    entry_price: float,
    future_rows: pd.DataFrame,
    horizon_days: int,
    stop_loss: Optional[float],
    policy_name: str = EXIT_POLICY_NAME,
    fee_bps: float = 5.0,
    slippage_bps: float = 10.0,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, object]:
    """Simulate a post-entry exit policy without feeding future data into the signal."""

    if entry_price <= 0:
        return _exit_result(
            policy_name=policy_name,
            horizon_days=horizon_days,
            entry_price=entry_price,
            exit_row=None,
            reason="INSUFFICIENT_DATA",
            raw_return=None,
            net_return=None,
            max_drawdown=None,
            holding_days=None,
        )
    max_days = _max_policy_holding_days(policy_name, horizon_days, params, signal)
    if future_rows.empty or len(future_rows) < max_days:
        return _exit_result(
            policy_name=policy_name,
            horizon_days=horizon_days,
            entry_price=entry_price,
            exit_row=None,
            reason="INSUFFICIENT_DATA",
            raw_return=None,
            net_return=None,
            max_drawdown=None,
            holding_days=None,
        )

    window = future_rows.head(max_days).copy().reset_index(drop=True)
    if "ma20_post" not in window.columns or "ma60_post" not in window.columns:
        close_series = pd.to_numeric(window.get("close"), errors="coerce")
        window["ma20_post"] = close_series.rolling(20, min_periods=5).mean()
        window["ma60_post"] = close_series.rolling(60, min_periods=20).mean()
    stop = _policy_stop_loss(entry_price, stop_loss, params)
    trail_start = float((params or {}).get("trail_start_pct") or 8.0)
    trail_drawdown = float((params or {}).get("trail_drawdown_pct") or 5.0)
    highest_close = entry_price
    highest_return = 0.0
    consecutive_below_ma20 = 0
    lows_seen: List[float] = []
    exit_row = None
    exit_reason = "TIME_EXIT"
    holding_days = max_days

    for idx, row in window.iterrows():
        day_number = int(idx) + 1
        close = finite_float(row.get("close"))
        low = finite_float(row.get("low")) or close
        if close is None:
            continue
        highest_close = max(highest_close, close)
        highest_return = max(highest_return, (highest_close - entry_price) / entry_price * 100.0)
        ma20 = finite_float(row.get("ma20_post"))
        ma60 = finite_float(row.get("ma60_post"))
        below_ma20 = ma20 is not None and close < ma20
        consecutive_below_ma20 = consecutive_below_ma20 + 1 if below_ma20 else 0
        platform_break = False
        if len(lows_seen) >= 10:
            platform_low = min(lows_seen[-10:])
            platform_break = close < platform_low * 0.995

        reason = None
        if stop is not None and low is not None and low <= stop:
            close = stop
            reason = "STOP_LOSS"
            row = row.copy()
            row["close"] = stop
        elif policy_name in {"trend_break_exit", EXIT_POLICY_NAME}:
            if ma60 is not None and day_number >= 20 and close < ma60:
                reason = "MA60_LOSS"
            elif day_number >= 10 and consecutive_below_ma20 >= 2:
                reason = "MA20_LOSS"
            elif platform_break:
                reason = "TREND_BREAK"
        if reason is None and policy_name in {"profit_trailing_exit", EXIT_POLICY_NAME}:
            active = highest_return >= trail_start
            tight_drawdown = 4.0 if highest_return >= 15.0 else trail_drawdown
            if active and highest_close > 0 and (close - highest_close) / highest_close * 100.0 <= -tight_drawdown:
                reason = "TAKE_PROFIT_TRAIL"
        if reason is None and policy_name == EXIT_POLICY_NAME and day_number >= min(20, max_days):
            current_return = (close - entry_price) / entry_price * 100.0
            if highest_return < 3.0 and current_return <= 0 and consecutive_below_ma20 >= 1:
                reason = "MAX_ADVERSE_EXCURSION"
        if reason is None and day_number >= max_days:
            reason = "TIME_EXIT"

        if low is not None:
            lows_seen.append(low)
        if reason is not None:
            exit_row = row
            exit_reason = reason
            holding_days = day_number
            break

    if exit_row is None:
        exit_row = window.iloc[-1]
        exit_reason = "TIME_EXIT"
        holding_days = max_days

    exit_price = finite_float(exit_row.get("close"))
    raw_return = round((exit_price - entry_price) / entry_price * 100.0, 4) if exit_price is not None else None
    max_drawdown = max_drawdown_from_values(entry_price, window.head(holding_days)["low"]) if holding_days else None
    return _exit_result(
        policy_name=policy_name,
        horizon_days=horizon_days,
        entry_price=entry_price,
        exit_row=exit_row,
        reason=exit_reason,
        raw_return=raw_return,
        net_return=net_return_from_raw(raw_return, fee_bps, slippage_bps),
        max_drawdown=max_drawdown,
        holding_days=holding_days,
    )


def _strip_policy_prefix(policy_result: Dict[str, object], policy_name: str) -> Dict[str, object]:
    prefix = f"{policy_name}_"
    return {
        key[len(prefix):] if key.startswith(prefix) else key: value
        for key, value in policy_result.items()
    }


def evaluate_signal_forward(
    signal: StrategySignal,
    price_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    *,
    fee_bps: float = 5.0,
    slippage_bps: float = 10.0,
) -> Dict[str, object]:
    df = prepare_price_frame(price_df)
    as_of = coerce_date(signal.as_of_date)
    history = df[df["date"] <= as_of].sort_values("date")
    future = df[df["date"] > as_of].sort_values("date")
    entry_row = future.iloc[0] if not future.empty else None

    entry_mode = "next_open"
    entry_price = None
    entry_date = None
    if entry_row is not None:
        entry_date = entry_row.get("date")
        entry_price = finite_float(entry_row.get("open"))
        if entry_price is None or entry_price <= 0:
            entry_price = finite_float(entry_row.get("close"))
            entry_mode = "next_close" if entry_price is not None and entry_price > 0 else "insufficient_entry_data"
    else:
        entry_mode = "insufficient_entry_data"

    signal.entry_price = round(entry_price, 4) if entry_price is not None else None
    signal.entry_date = entry_date.isoformat() if hasattr(entry_date, "isoformat") else None
    signal.entry_mode = entry_mode

    result: Dict[str, object] = {
        "entry_price": signal.entry_price,
        "entry_date": signal.entry_date,
        "entry_mode": signal.entry_mode,
    }
    result.update(_execution_diagnostics(history, entry_row, entry_mode))
    effective_stop = _effective_stop_loss(signal.stop_loss, entry_price)
    if effective_stop is not None:
        signal.stop_loss = effective_stop
        signal.dynamic_stop_loss = effective_stop
        signal.invalidation_level = effective_stop
    result["stop_loss"] = effective_stop
    result["dynamic_stop_loss"] = effective_stop
    result["invalidation_level"] = effective_stop
    if effective_stop is not None and entry_price is not None and entry_price > 0:
        result["stop_loss_distance_pct"] = round((entry_price - effective_stop) / entry_price * 100.0, 4)
    evaluable_future = future.iloc[1:].sort_values("date") if entry_row is not None else pd.DataFrame()
    execution_risk_flags = []
    if entry_mode == "insufficient_entry_data":
        execution_risk_flags.append("insufficient_entry_data")
    if result.get("limit_up_entry_risk"):
        execution_risk_flags.append("limit_up_entry_risk")
    if result.get("limit_down_entry_risk"):
        execution_risk_flags.append("limit_down_entry_risk")
    if result.get("low_liquidity_risk"):
        execution_risk_flags.append("low_liquidity_risk")
    if result.get("executable_entry_quality") in {"degraded", "risky"}:
        execution_risk_flags.append("degraded_entry_quality")
    if result.get("executable_entry_quality") == "unavailable":
        execution_risk_flags.append("unavailable_entry_quality")
    if execution_risk_flags:
        result["risk_flags"] = ";".join(
            sorted(set(str(signal.to_dict().get("risk_flags") or "").split(";") + execution_risk_flags))
        ).strip(";")

    adverse_excursions: list[float] = []
    result["exit_policy_name"] = EXIT_POLICY_NAME
    exit_future_rows = future.sort_values("date").copy() if entry_row is not None else pd.DataFrame()
    if not exit_future_rows.empty:
        close_series = pd.to_numeric(exit_future_rows.get("close"), errors="coerce")
        exit_future_rows["ma20_post"] = close_series.rolling(20, min_periods=5).mean()
        exit_future_rows["ma60_post"] = close_series.rolling(60, min_periods=20).mean()
    for days in EVAL_WINDOWS:
        stock_ret = future_return(entry_price, evaluable_future, days) if entry_price is not None else None
        result[f"raw_return_{days}d"] = stock_ret
        result[f"net_return_{days}d"] = net_return_from_raw(stock_ret, fee_bps, slippage_bps)
        result[f"future_return_{days}d"] = stock_ret
        result[f"close_max_drawdown_{days}d"] = (
            max_drawdown_from_values(entry_price, evaluable_future.head(days)["close"])
            if entry_price is not None and len(evaluable_future) >= days
            else None
        )
        result[f"low_max_drawdown_{days}d"] = (
            max_drawdown_from_values(entry_price, evaluable_future.head(days)["low"])
            if entry_price is not None and len(evaluable_future) >= days and "low" in evaluable_future.columns
            else None
        )
        if result[f"low_max_drawdown_{days}d"] is not None:
            adverse_excursions.append(float(result[f"low_max_drawdown_{days}d"]))
        result[f"max_drawdown_{days}d"] = result[f"low_max_drawdown_{days}d"]
        bench_ret = benchmark_return(benchmark_df, as_of, days)
        result[f"benchmark_return_{days}d"] = bench_ret
        result[f"outperform_benchmark_{days}d"] = (
            bool(result[f"net_return_{days}d"] > bench_ret) if result[f"net_return_{days}d"] is not None and bench_ret is not None else None
        )
        stop_adjusted, stop_triggered, stop_trigger_date = (
            _stop_adjusted_return(entry_price, evaluable_future, days, effective_stop)
            if entry_price is not None
            else (None, False, None)
        )
        result[f"stop_adjusted_return_{days}d"] = stop_adjusted
        result[f"stop_adjusted_net_return_{days}d"] = net_return_from_raw(stop_adjusted, fee_bps, slippage_bps)
        result[f"stop_triggered_{days}d"] = stop_triggered if stop_adjusted is not None else None
        result[f"stop_trigger_date_{days}d"] = stop_trigger_date
        if effective_stop is not None and entry_price is not None and len(evaluable_future) >= days and "low" in evaluable_future.columns:
            lows = pd.to_numeric(evaluable_future.head(days)["low"], errors="coerce")
            result[f"hit_stop_loss_{days}d"] = bool((lows <= effective_stop).any()) if not lows.empty else None
        else:
            result[f"hit_stop_loss_{days}d"] = None
        if entry_price is None:
            empty_exit = _exit_result(
                policy_name=EXIT_POLICY_NAME,
                horizon_days=days,
                entry_price=0.0,
                exit_row=None,
                reason="INSUFFICIENT_DATA",
                raw_return=None,
                net_return=None,
                max_drawdown=None,
                holding_days=None,
            )
            result.update(_strip_policy_prefix(empty_exit, EXIT_POLICY_NAME))
            continue

        hybrid_result = simulate_exit_policy(
            signal=signal,
            entry_price=entry_price,
            future_rows=exit_future_rows,
            horizon_days=days,
            stop_loss=effective_stop,
            policy_name=EXIT_POLICY_NAME,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        result.update(_strip_policy_prefix(hybrid_result, EXIT_POLICY_NAME))
        result.update(hybrid_result)
        for policy_name in EXIT_POLICY_NAMES:
            if policy_name == EXIT_POLICY_NAME:
                continue
            result.update(
                simulate_exit_policy(
                    signal=signal,
                    entry_price=entry_price,
                    future_rows=exit_future_rows,
                    horizon_days=days,
                    stop_loss=effective_stop,
                    policy_name=policy_name,
                    fee_bps=fee_bps,
                    slippage_bps=slippage_bps,
                )
            )
        for experiment_name, params in EXIT_POLICY_EXPERIMENTS.items():
            experiment_result = simulate_exit_policy(
                signal=signal,
                entry_price=entry_price,
                future_rows=exit_future_rows,
                horizon_days=days,
                stop_loss=effective_stop,
                policy_name=EXIT_POLICY_NAME,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                params=params,
            )
            stripped = _strip_policy_prefix(experiment_result, EXIT_POLICY_NAME)
            for key, value in stripped.items():
                result[f"exit_policy_experiment_{experiment_name}_{key}"] = value
    result["post_entry_adverse_excursion_pct"] = min(adverse_excursions) if adverse_excursions else None
    result["hit_stop_loss"] = result.get("hit_stop_loss_250d")
    return result


class WalkForwardBacktester:
    def __init__(self, strategy: Optional[GenGeCycleBottomStrategy] = None):
        self.strategy = strategy or GenGeCycleBottomStrategy()

    def run(
        self,
        *,
        inputs: List[BacktestInput],
        benchmark_df: Optional[pd.DataFrame],
        start_date,
        end_date,
        step_days: int = 1,
        fee_bps: float = 5.0,
        slippage_bps: float = 10.0,
        industry_cycle_df: Optional[pd.DataFrame] = None,
    ) -> List[Dict[str, object]]:
        start = coerce_date(start_date)
        end = coerce_date(end_date)
        rows: List[Dict[str, object]] = []

        for item in inputs:
            price_df = prepare_price_frame(item.price_df)
            dates = [
                d
                for d in price_df["date"].tolist()
                if start <= d <= end
            ]
            for index, as_of in enumerate(dates):
                if step_days > 1 and index % step_days != 0:
                    continue
                history = slice_as_of(price_df, as_of)
                if len(history) < 120:
                    continue

                signal = self.strategy.generate_signal(
                    code=item.code,
                    stock_name=item.stock_name,
                    as_of_date=as_of,
                    price_df=price_df,
                    valuation_df=item.valuation_df,
                    financial_df=item.financial_df,
                    benchmark_df=benchmark_df,
                    industry_cycle_df=industry_cycle_df,
                    industry=item.industry,
                    extra_risk_flags=item.extra_risk_flags,
                )
                if signal.signal_type not in ENTRY_SIGNAL_TYPES:
                    continue

                row = signal.to_dict()
                forward = evaluate_signal_forward(
                    signal,
                    price_df,
                    benchmark_df,
                    fee_bps=fee_bps,
                    slippage_bps=slippage_bps,
                )
                row.update(forward)
                if "risk_flags" in forward:
                    row["risk_flags"] = forward["risk_flags"]
                rows.append(row)

        return rows
