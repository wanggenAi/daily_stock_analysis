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
    extra_risk_flags: Optional[List[str]] = None


def max_drawdown_from_closes(start_price: float, closes: Iterable[float]) -> Optional[float]:
    start = finite_float(start_price)
    if start is None or start <= 0:
        return None
    running_peak = start
    worst = 0.0
    for close in closes:
        value = finite_float(close)
        if value is None:
            continue
        running_peak = max(running_peak, value)
        if running_peak > 0:
            worst = min(worst, (value - running_peak) / running_peak)
    return round(worst * 100, 4)


def future_return(start_price: float, future_rows: pd.DataFrame, days: int) -> Optional[float]:
    start = finite_float(start_price)
    if start is None or start <= 0 or len(future_rows) < days:
        return None
    end_close = finite_float(future_rows.iloc[days - 1].get("close"))
    if end_close is None:
        return None
    return round((end_close - start) / start * 100, 4)


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
) -> Dict[str, object]:
    df = prepare_price_frame(price_df)
    as_of = coerce_date(signal.as_of_date)
    history = df[df["date"] <= as_of].sort_values("date")
    future = df[df["date"] > as_of].sort_values("date")
    start_close = finite_float(history.iloc[-1].get("close")) if not history.empty else None

    result: Dict[str, object] = {}
    for days in EVAL_WINDOWS:
        stock_ret = future_return(start_close, future, days) if start_close is not None else None
        result[f"future_return_{days}d"] = stock_ret
        result[f"max_drawdown_{days}d"] = (
            max_drawdown_from_closes(start_close, future.head(days)["close"]) if start_close is not None and len(future) >= days else None
        )
        bench_ret = benchmark_return(benchmark_df, as_of, days)
        result[f"benchmark_return_{days}d"] = bench_ret
        result[f"outperform_benchmark_{days}d"] = (
            bool(stock_ret > bench_ret) if stock_ret is not None and bench_ret is not None else None
        )

    if signal.stop_loss is not None and start_close is not None:
        lows = pd.to_numeric(future["low"], errors="coerce") if "low" in future.columns else pd.Series(dtype="float64")
        result["hit_stop_loss"] = bool((lows <= signal.stop_loss).any()) if not lows.empty else None
    else:
        result["hit_stop_loss"] = None
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
        step_days: int = 20,
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
                    extra_risk_flags=item.extra_risk_flags,
                )
                if signal.signal_type not in ENTRY_SIGNAL_TYPES:
                    continue

                row = signal.to_dict()
                row.update(evaluate_signal_forward(signal, price_df, benchmark_df))
                rows.append(row)

        return rows

