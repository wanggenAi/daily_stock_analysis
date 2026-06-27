from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.features import build_feature_set, compute_price_percentile_score


def _price_frame(closes: list[float], start: date = date(2020, 1, 1)) -> pd.DataFrame:
    rows = []
    for offset, close in enumerate(closes):
        current_date = start + timedelta(days=offset)
        rows.append(
            {
                "date": current_date.isoformat(),
                "open": close,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": 1_000_000 + offset * 1000,
            }
        )
    return pd.DataFrame(rows)


def test_price_percentile_low_price_scores_higher_than_high_price() -> None:
    low_history = _price_frame([100 + index for index in range(199)] + [110])
    high_history = _price_frame([100 + index for index in range(199)] + [295])

    low_score, low_percentiles, low_missing = compute_price_percentile_score(low_history, 110)
    high_score, high_percentiles, high_missing = compute_price_percentile_score(high_history, 295)

    assert low_score > high_score
    assert low_percentiles["price_percentile_5y"] < 0.2
    assert high_percentiles["price_percentile_5y"] > 0.7
    assert low_missing == []
    assert high_missing == []


def test_price_percentile_marks_missing_when_history_is_short() -> None:
    history = _price_frame([10 + index for index in range(50)])

    score, percentiles, missing = compute_price_percentile_score(history, 59)

    assert score == 20.0
    assert percentiles["price_percentile_3y"] is None
    assert "price_percentile_3y" in missing
    assert "price_percentile_5y" in missing
    assert "price_percentile_10y" in missing


def test_missing_valuation_and_financial_data_do_not_crash_and_are_recorded() -> None:
    price_df = _price_frame([20 - index * 0.02 for index in range(140)])

    features = build_feature_set(price_df=price_df, as_of_date=price_df.iloc[-1]["date"])

    assert features.valuation_score == 35.0
    assert features.financial_safety_score == 45.0
    assert "valuation" in features.missing_fields
    assert "financial" in features.missing_fields
    assert "benchmark" in features.missing_fields
