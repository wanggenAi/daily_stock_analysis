from __future__ import annotations

from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.v311_current_expectation_inputs import (
    build_current_expectation_rows,
    current_inputs_from_panel,
)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_date": pd.Timestamp("2026-06-30"),
                "available_date": pd.Timestamp("2026-08-20"),
                "normalized_eps_round6": 1.0,
                "realistic_growth_round6": 0.10,
                "neutral_value_round6": 20.0,
                "normalized_earnings_observation_count": 4,
                "deduct_factor_round6": 0.9,
                "cash_conversion": 1.1,
                "realistic_growth_four_report_range": 0.02,
                "eps_growth_3y_round6": 0.12,
                "revenue_growth_3y_round6": 0.08,
            }
        ]
    )


def test_price_date_is_observed_trade_date_not_decision_date() -> None:
    row = current_inputs_from_panel(
        "600000",
        _panel(),
        current_price=10.0,
        as_of=date(2026, 8, 27),
        price_source="TEST_DAILY",
        price_date="2026-08-26",
    )

    assert row["decision_date"] == "2026-08-27"
    assert row["price_date"] == "2026-08-26"
    assert row["v311_expectation_input_status"] == "READY"
    assert row["v311_input_error"] == ""


def test_missing_price_date_fails_closed_instead_of_fabricating_decision_date() -> None:
    row = current_inputs_from_panel(
        "600000",
        _panel(),
        current_price=10.0,
        as_of=date(2026, 8, 27),
        price_source="UNDATED_SOURCE",
        price_date="",
    )

    assert row["decision_date"] == "2026-08-27"
    assert row["price_date"] == ""
    assert row["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert row["v311_input_error"] == "PRICE_DATE_UNVERIFIED"


def test_future_price_date_fails_closed() -> None:
    row = current_inputs_from_panel(
        "600000",
        _panel(),
        current_price=10.0,
        as_of=date(2026, 8, 27),
        price_source="BAD_FUTURE_SOURCE",
        price_date="2026-08-28",
    )

    assert row["price_date"] == "2026-08-28"
    assert row["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert row["v311_input_error"] == "PRICE_DATE_AFTER_DECISION_DATE"


def test_dated_upstream_price_keeps_its_own_trade_date() -> None:
    def should_not_fetch_price(*args, **kwargs):
        raise AssertionError("dated upstream price should not be replaced")

    rows = build_current_expectation_rows(
        ["600000"],
        source_rows=[
            {
                "code": "600000",
                "raw_latest_close": "10.0",
                "raw_latest_trade_date": "2026-08-26",
            }
        ],
        as_of=date(2026, 8, 27),
        financial_loader=lambda code: _panel(),
        price_loader=should_not_fetch_price,
    )

    assert rows[0]["price_date"] == "2026-08-26"
    assert rows[0]["current_price_source"] == "UPSTREAM_RAW_LATEST_CLOSE"
    assert rows[0]["v311_expectation_input_status"] == "READY"


def test_legacy_two_value_price_loader_is_accepted_but_never_declared_fresh() -> None:
    rows = build_current_expectation_rows(
        ["600000"],
        source_rows=[],
        as_of=date(2026, 8, 27),
        financial_loader=lambda code: _panel(),
        price_loader=lambda code, as_of: (10.0, "LEGACY_UNDATED"),
    )

    assert rows[0]["v31_current_price"] == 10.0
    assert rows[0]["price_date"] == ""
    assert rows[0]["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert rows[0]["v311_input_error"] == "PRICE_DATE_UNVERIFIED"
