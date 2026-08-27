from datetime import date

from src.strategies.genge_opportunity_discovery.v311_production_bridge import (
    reconcile_current_price_provenance,
)


def _ready_row(source: str = "UPSTREAM_RAW_LATEST_CLOSE") -> dict:
    return {
        "code": "600406",
        "v311_expectation_input_status": "READY",
        "current_price_source": source,
        "v31_current_price": 23.10,
        "price_date": "2026-08-27",
        "v31_market_implied_profit_cagr": 0.04,
        "v31_expectation_gap_pct": 0.03,
        "market_implied_growth": 0.04,
        "expectation_gap": 0.03,
        "price_to_neutral": 0.80,
        "v311_input_error": "",
    }


def test_upstream_price_uses_real_source_trade_date_not_decision_date() -> None:
    rows = reconcile_current_price_provenance(
        [{"code": "600406", "raw_latest_trade_date": "2026-08-26"}],
        [_ready_row()],
        as_of=date(2026, 8, 27),
    )

    assert rows[0]["price_date"] == "2026-08-26"
    assert rows[0]["v311_expectation_input_status"] == "READY"
    assert rows[0]["v31_current_price"] == 23.10
    assert rows[0]["v311_input_error"] == ""


def test_upstream_price_without_real_trade_date_fails_closed() -> None:
    rows = reconcile_current_price_provenance(
        [{"code": "600406"}],
        [_ready_row()],
        as_of=date(2026, 8, 27),
    )

    assert rows[0]["price_date"] == ""
    assert rows[0]["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert rows[0]["v311_input_error"] == "PRICE_DATE_UNVERIFIED"
    assert rows[0]["v31_current_price"] is None
    assert rows[0]["expectation_gap"] is None


def test_price_loader_without_observation_date_fails_closed() -> None:
    rows = reconcile_current_price_provenance(
        [],
        [_ready_row("AKSHARE_QFQ_DAILY")],
        as_of=date(2026, 8, 27),
    )

    assert rows[0]["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert rows[0]["v311_input_error"] == "PRICE_DATE_UNVERIFIED"
    assert rows[0]["v31_current_price"] is None


def test_future_source_price_date_fails_closed() -> None:
    rows = reconcile_current_price_provenance(
        [{"code": "600406", "raw_latest_trade_date": "2026-08-28"}],
        [_ready_row()],
        as_of=date(2026, 8, 27),
    )

    assert rows[0]["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"
    assert rows[0]["v311_input_error"] == "PRICE_DATE_AFTER_DECISION_DATE"
    assert rows[0]["v31_current_price"] is None
