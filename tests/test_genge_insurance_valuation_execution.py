from datetime import date
from pathlib import Path

import pandas as pd

from src.strategies.genge_opportunity_discovery.insurance_embedded_value_inputs import (
    load_insurance_embedded_value_input_repository,
)
from src.strategies.genge_opportunity_discovery.insurance_valuation_execution import (
    MARKET_CAP_INPUT_BASIS,
    execute_insurance_rows,
)


class FakeLoader:
    def __init__(self, frames):
        self.frames = frames

    def load_valuation(self, code, *, years):
        return self.frames.get(code), "fake.baidu", [], False


def _row(code, name):
    return {
        "valuation_research_rank": "1",
        "code": code,
        "stock_name": name,
        "valuation_primary_strategy_id": "insurance_embedded_value",
        "formal_signal_eligible": "False",
        "automatic_promotion_allowed": "False",
        "no_auto_trade": "True",
    }


def test_checked_in_insurance_inputs_execute_reverse_appraisal_without_fair_multiple():
    repository = load_insurance_embedded_value_input_repository()
    loader = FakeLoader(
        {
            "601628": pd.DataFrame(
                [
                    {"date": date(2026, 8, 18), "market_cap": 99999.0},
                    {"date": date(2026, 8, 17), "market_cap": 10627.53},
                ]
            ),
            "601601": pd.DataFrame(
                [{"date": date(2026, 8, 17), "market_cap": 2900.53}]
            ),
        }
    )

    rows = execute_insurance_rows(
        [
            _row("601628", "中国人寿"),
            _row("601601", "中国太保"),
            _row("601319", "中国人保"),
        ],
        as_of=date(2026, 8, 17),
        loader=loader,
        input_repository=repository,
    )
    by_code = {row["code"]: row for row in rows}

    life = by_code["601628"]
    assert life["insurance_model_executed"] is True
    assert life["insurance_model_execution_state"] == "INSURANCE_MODEL_EXECUTED_RESEARCH_ONLY"
    assert life["insurance_market_cap_raw_cny_100m"] == 10627.53
    assert life["insurance_market_cap_cny_million"] == 1062753.0
    assert life["insurance_market_cap_date"] == "2026-08-17"
    assert life["insurance_market_cap_input_basis"] == MARKET_CAP_INPUT_BASIS
    assert life["insurance_implied_nbv_franchise_multiple"] < 0
    assert round(life["insurance_implied_nbv_franchise_multiple"], 2) == -8.85

    cpic = by_code["601601"]
    assert cpic["insurance_model_executed"] is True
    assert cpic["insurance_market_cap_cny_million"] == 290053.0
    assert cpic["insurance_implied_nbv_franchise_multiple"] < 0
    assert round(cpic["insurance_implied_nbv_franchise_multiple"], 2) == -17.37

    picc = by_code["601319"]
    assert picc["insurance_model_executed"] is False
    assert picc["insurance_model_execution_state"] == "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED"
    assert picc["insurance_model_status"] == "INSURANCE_GROUP_EV_NBV_SCOPE_REQUIRED"

    for row in rows:
        assert row["insurance_model_formal_buy_eligible"] is False
        assert row["formal_signal_eligible"] is False
        assert row["automatic_promotion_allowed"] is False
        assert row["no_auto_trade"] is True


def test_missing_point_in_time_market_cap_fails_closed():
    repository = load_insurance_embedded_value_input_repository()
    loader = FakeLoader(
        {
            "601628": pd.DataFrame(
                [{"date": date(2026, 8, 18), "market_cap": 10627.53}]
            )
        }
    )

    row = execute_insurance_rows(
        [_row("601628", "中国人寿")],
        as_of=date(2026, 8, 17),
        loader=loader,
        input_repository=repository,
    )[0]

    assert row["insurance_model_executed"] is False
    assert row["insurance_model_execution_state"] == "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED"
    assert row["insurance_model_status"] == "POINT_IN_TIME_MARKET_CAP_UNAVAILABLE"


def test_non_insurance_route_is_untouched_except_research_locks():
    repository = load_insurance_embedded_value_input_repository()
    row = {
        "code": "600109",
        "stock_name": "国金证券",
        "valuation_primary_strategy_id": "capital_markets_cycle",
    }
    result = execute_insurance_rows(
        [row],
        as_of=date(2026, 8, 17),
        loader=FakeLoader({}),
        input_repository=repository,
    )[0]
    assert result["insurance_model_execution_state"] == "NOT_INSURANCE_ROUTE"
    assert result["formal_signal_eligible"] is False
    assert result["automatic_promotion_allowed"] is False
    assert result["no_auto_trade"] is True
