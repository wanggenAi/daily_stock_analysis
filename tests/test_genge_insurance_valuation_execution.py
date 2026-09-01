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


def test_checked_in_insurance_inputs_execute_reverse_appraisal_with_reference_anchor():
    repository = load_insurance_embedded_value_input_repository()
    loader = FakeLoader(
        {
            "601318": pd.DataFrame([{"date": date(2026, 8, 17), "market_cap": 10400.0}]),
            "601628": pd.DataFrame([{"date": date(2026, 8, 17), "market_cap": 10627.53}]),
            "601601": pd.DataFrame([{"date": date(2026, 8, 17), "market_cap": 2900.53}]),
        }
    )

    rows = execute_insurance_rows(
        [
            _row("601318", "中国平安"),
            _row("601628", "中国人寿"),
            _row("601601", "中国太保"),
            _row("601319", "中国人保"),
        ],
        as_of=date(2026, 8, 17),
        loader=loader,
        input_repository=repository,
    )
    by_code = {row["code"]: row for row in rows}

    pingan = by_code["601318"]
    assert pingan["insurance_model_executed"] is True
    assert pingan["valuation_evidence_status"] == "VALID"
    assert pingan["valuation_model_status"] == "EXECUTED"
    assert pingan["valuation_anchor_status"] == "REFERENCE_AVAILABLE"
    assert pingan["valuation_completion_status"] == "COMPLETED_WITH_REFERENCE_ANCHOR"
    assert pingan["insurance_embedded_value_cny_million"] == 1504288.0
    assert pingan["insurance_embedded_value_per_share"] == 83.07
    assert pingan["insurance_normalized_annual_nbv_cny_million"] == 36897.0
    assert pingan["insurance_evidence_source_url"].startswith("https://")
    assert pingan["insurance_market_cap_input_basis"] == MARKET_CAP_INPUT_BASIS

    life = by_code["601628"]
    assert life["insurance_model_executed"] is True
    assert life["insurance_market_cap_cny_million"] == 1062753.0
    assert round(life["insurance_implied_nbv_franchise_multiple"], 2) == -8.85

    cpic = by_code["601601"]
    assert cpic["insurance_model_executed"] is True
    assert round(cpic["insurance_implied_nbv_franchise_multiple"], 2) == -17.37

    picc = by_code["601319"]
    assert picc["insurance_model_executed"] is False
    assert picc["insurance_model_execution_state"] == "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED"
    assert picc["insurance_model_status"] == "DISCLOSED_EV_NBV_INPUTS_NOT_FOUND"
    assert "601319" not in picc["insurance_model_status"]
    assert picc["valuation_evidence_status"] == "MISSING"
    assert picc["valuation_model_status"] == "NOT_EXECUTED"
    assert picc["valuation_completion_status"] == "UNFINISHED"

    for row in rows:
        assert row["insurance_model_formal_buy_eligible"] is False
        assert row["formal_signal_eligible"] is False
        assert row["automatic_promotion_allowed"] is False
        assert row["no_auto_trade"] is True


def test_missing_point_in_time_market_cap_keeps_valid_evidence_but_model_unfinished():
    repository = load_insurance_embedded_value_input_repository()
    loader = FakeLoader({"601318": pd.DataFrame([{"date": date(2026, 8, 18), "market_cap": 10400.0}])})
    row = execute_insurance_rows(
        [_row("601318", "中国平安")],
        as_of=date(2026, 8, 17),
        loader=loader,
        input_repository=repository,
    )[0]
    assert row["valuation_evidence_status"] == "VALID"
    assert row["valuation_anchor_status"] == "REFERENCE_AVAILABLE"
    assert row["insurance_model_executed"] is False
    assert row["valuation_model_status"] == "NOT_EXECUTED"
    assert row["valuation_completion_status"] == "UNFINISHED"
    assert row["insurance_model_status"] == "POINT_IN_TIME_MARKET_CAP_UNAVAILABLE"


def test_stale_disclosure_is_distinct_from_missing(tmp_path: Path):
    config = tmp_path / "insurance.yaml"
    config.write_text(
        """version: 2
default_max_age_days: 30
inputs:
  - input_id: test-insurer
    code: '600000'
    stock_name: 测试保险
    known_at: '2026-01-02'
    evidence_as_of: '2025-12-31'
    report_year: 2025
    currency: CNY
    unit: million
    embedded_value: 1000
    normalized_annual_nbv: 100
    embedded_value_scope: insurance_group
    nbv_scope: life_new_business
    confidence: HIGH
""",
        encoding="utf-8",
    )
    repository = load_insurance_embedded_value_input_repository(config)
    row = execute_insurance_rows(
        [_row("600000", "测试保险")],
        as_of=date(2026, 3, 1),
        loader=FakeLoader({}),
        input_repository=repository,
    )[0]
    assert row["valuation_evidence_status"] == "STALE"
    assert row["valuation_model_status"] == "NOT_EXECUTED"
    assert row["valuation_completion_status"] == "UNFINISHED"
    assert row["insurance_model_status"] == "DISCLOSED_EV_NBV_INPUTS_STALE"


def test_non_insurance_route_is_untouched_except_research_locks():
    repository = load_insurance_embedded_value_input_repository()
    row = {"code": "600109", "stock_name": "国金证券", "valuation_primary_strategy_id": "capital_markets_cycle"}
    result = execute_insurance_rows(
        [row], as_of=date(2026, 8, 17), loader=FakeLoader({}), input_repository=repository
    )[0]
    assert result["insurance_model_execution_state"] == "NOT_INSURANCE_ROUTE"
    assert result["valuation_completion_status"] == "NOT_APPLICABLE"
    assert result["formal_signal_eligible"] is False
    assert result["automatic_promotion_allowed"] is False
    assert result["no_auto_trade"] is True
