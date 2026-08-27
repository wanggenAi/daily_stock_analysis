from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.price_observation_verifier import (
    verify_price_observation,
)


def _history(**_kwargs):
    return pd.DataFrame(
        {
            "日期": ["2026-08-25", "2026-08-26"],
            "收盘": [22.90, 23.10],
        }
    )


def test_akshare_price_returns_actual_observation_date() -> None:
    observed, error = verify_price_observation(
        "600406",
        23.10,
        "AKSHARE_QFQ_DAILY",
        as_of=date(2026, 8, 27),
        akshare_history_loader=_history,
    )

    assert observed == date(2026, 8, 26)
    assert error == ""


def test_akshare_price_value_change_fails_closed() -> None:
    observed, error = verify_price_observation(
        "600406",
        23.11,
        "AKSHARE_QFQ_DAILY",
        as_of=date(2026, 8, 27),
        akshare_history_loader=_history,
    )

    assert observed is None
    assert error == "PRICE_VALUE_CHANGED_DURING_VERIFICATION"


def test_unknown_price_source_is_not_authorized() -> None:
    observed, error = verify_price_observation(
        "600406",
        23.10,
        "SOME_PROVIDER",
        as_of=date(2026, 8, 27),
    )

    assert observed is None
    assert error == "PRICE_SOURCE_NOT_VERIFIABLE:SOME_PROVIDER"


def test_future_rows_are_not_selected() -> None:
    def history(**_kwargs):
        return pd.DataFrame(
            {
                "日期": ["2026-08-26", "2026-08-28"],
                "收盘": [23.10, 25.00],
            }
        )

    observed, error = verify_price_observation(
        "600406",
        23.10,
        "AKSHARE_QFQ_DAILY",
        as_of=date(2026, 8, 27),
        akshare_history_loader=history,
    )

    assert observed == date(2026, 8, 26)
    assert error == ""
