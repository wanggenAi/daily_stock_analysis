"""Walk-forward backtest for GenGe Cycle Bottom Strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional

import pandas as pd

from .features import coerce_date, finite_float, prepare_price_frame, slice_as_of
from .signals import SignalType, StrategySignal
from .strategy import GenGeCycleBottomStrategy


EVAL_WINDOWS = (20, 60, 120, 250)
ENTRY_SIGNAL_TYPES = {SignalType.LEFT_SMALL_BUY, SignalType.CONFIRM_BUY, SignalType.ADD}


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
    evaluable_future = future.iloc[1:].sort_values("date") if entry_row is not None else pd.DataFrame()
    if entry_mode == "insufficient_entry_data":
        result["risk_flags"] = ";".join(sorted(set(str(signal.to_dict().get("risk_flags") or "").split(";") + ["insufficient_entry_data"]))).strip(";")

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
        result[f"max_drawdown_{days}d"] = result[f"low_max_drawdown_{days}d"]
        bench_ret = benchmark_return(benchmark_df, as_of, days)
        result[f"benchmark_return_{days}d"] = bench_ret
        result[f"outperform_benchmark_{days}d"] = (
            bool(result[f"net_return_{days}d"] > bench_ret) if result[f"net_return_{days}d"] is not None and bench_ret is not None else None
        )
        if signal.stop_loss is not None and entry_price is not None and len(evaluable_future) >= days and "low" in evaluable_future.columns:
            lows = pd.to_numeric(evaluable_future.head(days)["low"], errors="coerce")
            result[f"hit_stop_loss_{days}d"] = bool((lows <= signal.stop_loss).any()) if not lows.empty else None
        else:
            result[f"hit_stop_loss_{days}d"] = None
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
