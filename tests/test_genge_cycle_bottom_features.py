from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.strategies.genge_cycle_bottom.features import (
    build_feature_set,
    compute_financial_safety_score,
    compute_industry_cycle_score,
    compute_price_percentile_score,
    compute_valuation_score,
)


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
    low_history = _price_frame([100 + index * 0.05 for index in range(899)] + [105])
    high_history = _price_frame([100 + index * 0.05 for index in range(899)] + [180])

    low_score, low_percentiles, low_missing = compute_price_percentile_score(low_history, 105)
    high_score, high_percentiles, high_missing = compute_price_percentile_score(high_history, 295)

    assert low_score > high_score
    assert low_percentiles["price_percentile_5y"] < 0.2
    assert high_percentiles["price_percentile_5y"] > 0.7
    assert "price_percentile_3y" not in low_missing
    assert "price_percentile_5y" not in low_missing
    assert "price_percentile_10y" in low_missing
    assert "price_percentile_3y" not in high_missing
    assert "price_percentile_5y" not in high_missing
    assert "price_percentile_10y" in high_missing
    assert low_percentiles["distance_from_5y_low_pct"] is not None
    assert low_percentiles["distance_from_5y_high_pct"] is not None


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


def test_financial_disclosure_date_blocks_future_data() -> None:
    financial_df = pd.DataFrame(
        [
            {
                "report_date": "2023-12-31",
                "disclosure_date": "2024-04-30",
                "debt_ratio": 40,
                "net_profit": 100,
                "operating_cash_flow": 80,
                "roe": 10,
            }
        ]
    )

    early_score, early_missing, _, _ = compute_financial_safety_score(financial_df, date(2024, 4, 1))
    late_score, late_missing, _, late_diag = compute_financial_safety_score(financial_df, date(2024, 5, 1))

    assert early_score == 45.0
    assert "financial" in early_missing
    assert late_score > early_score
    assert late_missing == []
    assert late_diag["financial_available_date"] == "2024-04-30"


def test_financial_report_date_uses_conservative_lag_when_no_disclosure_date() -> None:
    financial_df = pd.DataFrame(
        [
            {
                "report_date": "2023-12-31",
                "debt_ratio": 40,
                "net_profit": 100,
                "operating_cash_flow": 80,
                "roe": 10,
            }
        ]
    )

    early_score, early_missing, _, _ = compute_financial_safety_score(financial_df, date(2024, 4, 20))
    late_score, late_missing, _, late_diag = compute_financial_safety_score(financial_df, date(2024, 5, 1))

    assert early_score == 45.0
    assert "financial" in early_missing
    assert late_score > early_score
    assert late_missing == []
    assert late_diag["financial_available_date"] == "2024-04-29"


def test_valuation_historical_percentile_scores_low_pb_higher_than_high_pb() -> None:
    valuation_df = pd.DataFrame(
        {
            "date": [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(1400)],
            "pb": [1 + i / 700 for i in range(1400)],
            "pe": [10 + i / 50 for i in range(1400)],
            "ps": [1 + i / 500 for i in range(1400)],
        }
    )
    low_tail = valuation_df.copy()
    low_tail.loc[1399, ["pb", "pe", "ps"]] = [1.05, 11, 1.05]
    high_tail = valuation_df.copy()
    high_tail.loc[1399, ["pb", "pe", "ps"]] = [5.0, 90, 7.0]

    low_score, _, low_diag = compute_valuation_score(low_tail, date(2023, 10, 31))
    high_score, _, high_diag = compute_valuation_score(high_tail, date(2023, 10, 31))

    assert low_score > high_score
    assert low_diag["pb_percentile_3y"] < 0.2
    assert high_diag["pb_percentile_3y"] > 0.8


def test_valuation_future_rows_do_not_affect_as_of_percentile() -> None:
    rows = []
    for i in range(1300):
        rows.append({"date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(), "pb": 1 + i / 1000, "pe": 10, "ps": 1})
    as_of = date(2023, 1, 1)
    base_df = pd.DataFrame(rows)
    future_df = pd.concat(
        [
            base_df,
            pd.DataFrame([{"date": "2025-01-01", "pb": 99, "pe": 200, "ps": 30}]),
        ],
        ignore_index=True,
    )

    base_score, _, base_diag = compute_valuation_score(base_df, as_of)
    future_score, _, future_diag = compute_valuation_score(future_df, as_of)

    assert base_score == future_score
    assert base_diag["pb_percentile_3y"] == future_diag["pb_percentile_3y"]


def test_industry_cycle_missing_degrades_to_neutral_score() -> None:
    score, missing, diag = compute_industry_cycle_score(None, None, date(2024, 1, 1))

    assert score == 50.0
    assert "stock_industry_map" in missing
    assert diag["industry"] is None
