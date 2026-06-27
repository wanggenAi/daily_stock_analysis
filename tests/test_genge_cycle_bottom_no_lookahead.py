from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.strategy import GenGeCycleBottomStrategy


def _price_frame(closes: list[float], start: date = date(2020, 1, 1)) -> pd.DataFrame:
    rows = []
    for offset, close in enumerate(closes):
        rows.append(
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "open": close,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": 1_000_000 + offset * 100,
            }
        )
    return pd.DataFrame(rows)


def test_signal_generation_does_not_use_future_price_bars() -> None:
    historical_closes = [20 - index * 0.03 for index in range(150)]
    future_spike = [40.0, 42.0, 44.0, 46.0, 48.0]
    truncated_df = _price_frame(historical_closes)
    with_future_df = _price_frame(historical_closes + future_spike)
    as_of_date = truncated_df.iloc[-1]["date"]
    strategy = GenGeCycleBottomStrategy()

    signal_without_future = strategy.generate_signal(
        code="000001",
        stock_name="测试股票",
        as_of_date=as_of_date,
        price_df=truncated_df,
    )
    signal_with_future = strategy.generate_signal(
        code="000001",
        stock_name="测试股票",
        as_of_date=as_of_date,
        price_df=with_future_df,
    )

    assert signal_without_future.signal_type == signal_with_future.signal_type
    assert signal_without_future.total_score == signal_with_future.total_score
    assert signal_without_future.price_percentile_score == signal_with_future.price_percentile_score
    assert signal_without_future.trend_stabilization_score == signal_with_future.trend_stabilization_score
