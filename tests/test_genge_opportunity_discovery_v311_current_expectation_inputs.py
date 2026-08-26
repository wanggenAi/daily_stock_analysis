from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.selection_framework_v311 import (
    ValuationConfidence,
    assess_valuation_confidence_v311,
)
from src.strategies.genge_opportunity_discovery.v311_current_expectation_inputs import (
    build_strict_pit_financial_panel,
    current_inputs_from_panel,
    solve_market_implied_growth,
    value_expectation_10y,
)


def _annual_statements() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = [
        "2021-12-31",
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
        "2025-12-31",
    ]
    notices = [
        "2022-03-20",
        "2023-03-20",
        "2024-03-20",
        "2025-03-20",
        "2026-03-20",
    ]
    eps = [1.0, 1.10, 1.21, 1.331, 1.4641]
    revenue = [100.0, 110.0, 121.0, 133.1, 146.41]
    parent = [10.0, 11.0, 12.1, 13.31, 14.641]
    deduct = [9.0, 9.9, 10.89, 11.979, 13.1769]
    cash = [9.5, 10.45, 11.495, 12.6445, 13.90895]
    profit = pd.DataFrame(
        {
            "REPORT_DATE": dates,
            "NOTICE_DATE": notices,
            "PARENT_NETPROFIT": parent,
            "DEDUCT_PARENT_NETPROFIT": deduct,
            "BASIC_EPS": eps,
            "TOTAL_OPERATE_INCOME": revenue,
        }
    )
    cashflow = pd.DataFrame(
        {
            "REPORT_DATE": dates,
            "NOTICE_DATE": notices,
            "NETCASH_OPERATE": cash,
        }
    )
    return profit, cashflow


def test_value_and_reverse_solver_are_round6_formula_parity() -> None:
    normalized_eps = 2.0
    growth = 0.12
    price = value_expectation_10y(normalized_eps, growth)
    implied, status = solve_market_implied_growth(price, normalized_eps)
    assert status == "SOLVED"
    assert implied == pytest.approx(growth, abs=1e-9)


def test_strict_pit_uses_notice_date_and_never_update_date() -> None:
    profit, cash = _annual_statements()
    profit["UPDATE_DATE"] = "2099-01-01"
    cash["UPDATE_DATE"] = "2099-01-01"
    panel = build_strict_pit_financial_panel(profit, cash)
    assert "UPDATE_DATE" not in panel.columns
    assert panel.iloc[-1]["available_date"] == pd.Timestamp("2026-03-20")
    assert panel.iloc[-1]["report_date"] == pd.Timestamp("2025-12-31")


def test_duplicate_report_period_keeps_earliest_notice_revision() -> None:
    profit, cash = _annual_statements()
    duplicate = profit.iloc[[-1]].copy()
    duplicate["NOTICE_DATE"] = "2026-08-20"
    duplicate["BASIC_EPS"] = 99.0
    profit = pd.concat([profit, duplicate], ignore_index=True)
    panel = build_strict_pit_financial_panel(profit, cash)
    latest = panel.loc[panel["report_date"] == pd.Timestamp("2025-12-31")].iloc[-1]
    assert latest["p_BASIC_EPS"] == pytest.approx(1.4641)


def test_current_sidecar_emits_validated_numeric_inputs_without_fake_qualitative_fields() -> None:
    profit, cash = _annual_statements()
    panel = build_strict_pit_financial_panel(profit, cash)
    latest = panel.iloc[-1]
    neutral = float(latest["neutral_value_round6"])
    row = current_inputs_from_panel(
        "600000",
        panel,
        current_price=neutral * 0.90,
        as_of=date(2026, 8, 26),
        price_source="FIXTURE",
    )
    assert row["v311_expectation_input_status"] == "READY"
    assert row["v31_normalized_profit"] > 0
    assert 0 < row["v31_realistic_profit_cagr"] < 0.30
    assert row["v31_market_implied_profit_cagr"] >= 0
    assert row["v31_expectation_gap_pct"] == pytest.approx(
        row["v31_realistic_profit_cagr"] - row["v31_market_implied_profit_cagr"]
    )
    assert row["v31_neutral_value"] == pytest.approx(neutral)
    assert row["price_to_neutral"] == pytest.approx(0.90)
    assert "v31_expectation_gap_thesis" not in row
    assert "v31_moat_status" not in row
    assert "v31_pessimistic_value" not in row
    assert "v31_optimistic_value" not in row


def test_generated_confidence_inputs_can_reach_high_or_medium_instead_of_all_invalid() -> None:
    profit, cash = _annual_statements()
    panel = build_strict_pit_financial_panel(profit, cash)
    neutral = float(panel.iloc[-1]["neutral_value_round6"])
    row = current_inputs_from_panel(
        "600000",
        panel,
        current_price=neutral,
        as_of=date(2026, 8, 26),
        price_source="FIXTURE",
    )
    assessment = assess_valuation_confidence_v311(row)
    assert assessment.level in {ValuationConfidence.HIGH, ValuationConfidence.MEDIUM}
    assert assessment.level is not ValuationConfidence.INVALID


def test_asof_before_latest_notice_cannot_use_future_financial_row() -> None:
    profit, cash = _annual_statements()
    panel = build_strict_pit_financial_panel(profit, cash)
    row = current_inputs_from_panel(
        "600000",
        panel,
        current_price=30.0,
        as_of=date(2025, 12, 31),
        price_source="FIXTURE",
    )
    assert row["fund_available_date"] <= "2025-12-31"
    assert row["financial_report_date"] != "2025-12-31"


def test_above_100pct_implied_growth_remains_unavailable_not_fabricated() -> None:
    implied, status = solve_market_implied_growth(
        value_expectation_10y(1.0, 1.0) * 1.01,
        1.0,
    )
    assert np.isnan(implied)
    assert status == "IMPLIED_ABOVE_SEARCH_RANGE"
