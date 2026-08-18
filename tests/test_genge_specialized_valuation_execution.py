from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.specialized_valuation_execution import (
    SPECIALIZED_CACHE_NAMESPACE,
    _annual_roe_history,
    _dedicated_cache_dir,
    execute_specialized_rows,
)


class FakeLoader:
    def __init__(self, valuation_df, financial_df):
        self.valuation_df = valuation_df
        self.financial_df = financial_df
        self.calls = []

    def load(self, code, *, years, fetch_valuation, fetch_financial):
        self.calls.append((code, years, fetch_valuation, fetch_financial))
        return SimpleNamespace(
            valuation_df=self.valuation_df.copy(),
            financial_df=self.financial_df.copy(),
        )


class RefreshingDedicatedLoader:
    def __init__(self, cache_dir: Path, valuation_df, refreshed_financial_df):
        self.cache_dir = cache_dir
        self.valuation_df = valuation_df
        self.refreshed_financial_df = refreshed_financial_df
        self.calls = 0

    def load(self, code, *, years, fetch_valuation, fetch_financial):
        self.calls += 1
        if self.calls == 1:
            financial_df = pd.DataFrame(
                {
                    "report_date": ["2024-12-31"],
                    "disclosure_date": [None],
                    "roe": [None],
                }
            )
            cache_hits = {"financial": True, "valuation": True}
        else:
            financial_df = self.refreshed_financial_df.copy()
            cache_hits = {"financial": False, "valuation": True}
        return SimpleNamespace(
            valuation_df=self.valuation_df.copy(),
            financial_df=financial_df,
            cache_hits=cache_hits,
        )


def _broker_row(code="600109"):
    return {
        "valuation_research_rank": "28",
        "code": code,
        "stock_name": "国金证券",
        "valuation_primary_strategy_id": "capital_markets_cycle",
        "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        "formal_signal_eligible": "False",
        "automatic_promotion_allowed": "False",
        "no_auto_trade": "True",
    }


def _valuation_frame():
    return pd.DataFrame(
        {
            "date": ["2025-08-15", "2025-08-18", "2026-01-01"],
            "pb": [0.80, 0.82, 9.99],
        }
    )


def _financial_frame():
    return pd.DataFrame(
        {
            "report_date": [
                "2021-12-31",
                "2022-12-31",
                "2023-12-31",
                "2024-12-31",
                "2025-03-31",
                "2025-12-31",
            ],
            "disclosure_date": [None, None, None, "2025-03-28", "2025-04-28", None],
            "roe": [6.0, 8.0, 10.0, 12.0, 99.0, 88.0],
        }
    )


def test_broker_executes_in_normalized_book_units_with_pit_safe_annual_roe():
    loader = FakeLoader(_valuation_frame(), _financial_frame())
    rows = execute_specialized_rows(
        [_broker_row()],
        as_of=date(2025, 8, 17),
        loader=loader,
        minimum_annual_roe_samples=3,
        maximum_annual_roe_samples=5,
        cost_of_equity=0.11,
        long_term_growth=0.03,
    )

    row = rows[0]
    assert row["specialized_model_input_report_years"] == "2021;2022;2023;2024"
    assert row["specialized_model_roe_sample_count"] == 4
    assert row["specialized_normalized_mid_cycle_roe"] == pytest.approx(0.09)
    assert row["specialized_current_pb"] == pytest.approx(0.80)
    assert row["specialized_current_pb_date"] == "2025-08-15"

    expected_fair_pb = (0.09 - 0.03) / (0.11 - 0.03)
    expected_implied_roe = 0.80 * (0.11 - 0.03) + 0.03
    assert row["specialized_fair_pb"] == pytest.approx(expected_fair_pb)
    assert row["specialized_implied_mid_cycle_roe"] == pytest.approx(expected_implied_roe)
    assert row["specialized_expectation_gap_roe"] == pytest.approx(0.09 - expected_implied_roe)
    assert row["specialized_margin_of_safety"] == pytest.approx(expected_fair_pb / 0.80 - 1.0)
    assert row["specialized_model_executed"] is True
    assert row["specialized_model_execution_state"] == "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY"
    assert row["specialized_model_status"] == "OK"

    assert row["valuation_model_execution_state"] == "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
    assert row["specialized_model_formal_buy_eligible"] is False
    assert row["formal_signal_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["no_auto_trade"] is True
    assert loader.calls == [("600109", 7, True, True)]


def test_annual_roe_history_uses_actual_disclosure_when_known_and_deadline_when_missing():
    frame = pd.DataFrame(
        {
            "report_date": ["2022-12-31", "2023-12-31", "2024-12-31"],
            "disclosure_date": ["2023-03-20", None, "2026-01-01"],
            "roe": [8.0, 10.0, 12.0],
        }
    )
    history = _annual_roe_history(frame, as_of=date(2025, 5, 1), max_samples=5)

    assert history.years == (2022, 2023)
    assert history.values == pytest.approx((0.08, 0.10))


def test_undated_annual_row_is_not_used_before_statutory_deadline():
    frame = pd.DataFrame(
        {
            "report_date": ["2025-12-31"],
            "disclosure_date": [None],
            "roe": [10.0],
        }
    )
    before = _annual_roe_history(frame, as_of=date(2026, 4, 29), max_samples=5)
    after = _annual_roe_history(frame, as_of=date(2026, 4, 30), max_samples=5)

    assert before.values == ()
    assert after.values == pytest.approx((0.10,))


def test_broker_remains_inputs_required_when_annual_roe_history_is_too_short():
    loader = FakeLoader(
        pd.DataFrame({"date": ["2025-08-15"], "pb": [0.8]}),
        pd.DataFrame(
            {
                "report_date": ["2023-12-31", "2024-12-31"],
                "disclosure_date": [None, None],
                "roe": [8.0, 10.0],
            }
        ),
    )
    row = execute_specialized_rows(
        [_broker_row()],
        as_of=date(2025, 8, 17),
        loader=loader,
        minimum_annual_roe_samples=3,
    )[0]

    assert row["specialized_model_executed"] is False
    assert row["specialized_model_execution_state"] == "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
    assert row["specialized_model_status"] == "BROKER_INPUTS_INCOMPLETE"
    assert "insufficient_pit_safe_annual_roe_history" in row["specialized_model_execution_reason"]
    assert row["specialized_model_formal_buy_eligible"] is False


def test_dedicated_specialized_cache_is_versioned_under_generic_cache_root():
    root = Path("data/cache/valuation_research_fundamentals")
    assert _dedicated_cache_dir(root) == root / SPECIALIZED_CACHE_NAMESPACE
    already = root / SPECIALIZED_CACHE_NAMESPACE
    assert _dedicated_cache_dir(already) == already


def test_dedicated_cached_financial_without_roe_is_refreshed_once(tmp_path):
    cache_dir = tmp_path / SPECIALIZED_CACHE_NAMESPACE
    loader = RefreshingDedicatedLoader(cache_dir, _valuation_frame(), _financial_frame())

    row = execute_specialized_rows(
        [_broker_row()],
        as_of=date(2025, 8, 17),
        loader=loader,
        minimum_annual_roe_samples=3,
    )[0]

    assert loader.calls == 2
    assert row["specialized_model_executed"] is True
    assert row["specialized_model_roe_sample_count"] == 4
    assert row["specialized_model_execution_state"] == "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY"


def test_unimplemented_specialized_families_remain_explicitly_inputs_required_without_fetching():
    loader = FakeLoader(_valuation_frame(), _financial_frame())
    inputs = [
        {
            "code": "601628",
            "stock_name": "中国人寿",
            "valuation_primary_strategy_id": "insurance_embedded_value",
            "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        },
        {
            "code": "601111",
            "stock_name": "中国国航",
            "valuation_primary_strategy_id": "transport_cycle",
            "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        },
        {
            "code": "600903",
            "stock_name": "贵州燃气",
            "valuation_primary_strategy_id": "yield_asset",
            "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        },
    ]

    rows = execute_specialized_rows(inputs, as_of=date(2025, 8, 17), loader=loader)

    assert [row["specialized_model_status"] for row in rows] == [
        "DISCLOSED_EV_NBV_INPUTS_REQUIRED",
        "THROUGH_CYCLE_EBITDA_AND_LEASE_CONSISTENT_NET_DEBT_REQUIRED",
        "NORMALIZED_FCFE_INPUTS_REQUIRED",
    ]
    assert all(
        row["specialized_model_execution_state"] == "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
        for row in rows
    )
    assert all(row["specialized_model_executed"] is False for row in rows)
    assert all(row["no_auto_trade"] is True for row in rows)
    assert loader.calls == []


def test_generic_reverse_route_is_untouched_by_specialized_execution_sidecar():
    loader = FakeLoader(_valuation_frame(), _financial_frame())
    row = execute_specialized_rows(
        [
            {
                "code": "603369",
                "valuation_primary_strategy_id": "general_reverse_earnings",
                "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
            }
        ],
        as_of=date(2025, 8, 17),
        loader=loader,
    )[0]

    assert row["specialized_model_execution_state"] == "NOT_SPECIALIZED_ROUTE"
    assert row["valuation_model_execution_state"] == "GENERIC_REVERSE_DIAGNOSTIC_READY"
    assert row["specialized_model_executed"] is False
    assert row["no_auto_trade"] is True
    assert loader.calls == []
