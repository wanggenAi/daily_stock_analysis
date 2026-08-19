from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

import src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget as module
from src.strategies.genge_opportunity_discovery.all_a_full_scan import BoardRule
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import HistoricalCompanyData
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    infer_board,
    point_in_time_risk_geometry,
    replay_single_account,
)


def _rule(volatility_multiplier: float = 1.0) -> BoardRule:
    return BoardRule(
        daily_price_limit=0.10,
        max_gap_open_pct=4.0,
        max_5d_return_pct=18.0,
        max_10d_return_pct=28.0,
        breakout_volume_ratio=1.20,
        max_chase_atr_multiple=0.45,
        minimum_turnover=20_000_000,
        minimum_history_rows=100,
        valuation_mode="absolute_and_percentile",
        volatility_multiplier=volatility_multiplier,
        abnormal_move_threshold=0.095,
    )


def _data(code: str, closes: list[float]) -> HistoricalCompanyData:
    start = date(2025, 1, 2)
    rows = []
    for i, close in enumerate(closes):
        rows.append(
            {
                "date": start + timedelta(days=i),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000,
                "amount": 20_000_000,
            }
        )
    return HistoricalCompanyData(
        code=code,
        stock_name=code,
        price_df=pd.DataFrame(rows),
        valuation_df=pd.DataFrame(),
        financial_df=pd.DataFrame(),
        warnings=[],
    )


def test_board_inference_matches_live_board_rule_families():
    assert infer_board("600000") == "SSE_MAIN"
    assert infer_board("000001") == "SZSE_MAIN"
    assert infer_board("688001") == "STAR"
    assert infer_board("300001") == "CHINEXT"


def test_risk_geometry_prefers_live_preferred_stop_without_next_open(monkeypatch):
    data = _data("600000", [100.0] * 40)

    def fake_plan(*args, **kwargs):
        return {
            "preferred_plan": "pullback",
            "pullback_stop_price": 92.0,
            "breakout_stop_price": 95.0,
        }

    monkeypatch.setattr(module, "build_price_plan", fake_plan)
    monkeypatch.setattr(module, "_structural_stop_from_live_components", lambda *args, **kwargs: 90.0)
    geometry = point_in_time_risk_geometry(
        data,
        signal_date=date(2025, 2, 1),
        reference_entry=100.0,
        board_rules={"SSE_MAIN": _rule()},
    )

    assert geometry["status"] == "OK"
    assert geometry["stop_price"] == 92.0
    assert geometry["stop_distance_pct"] == 8.0
    assert geometry["source"] == "live_preferred_pullback"


def test_single_account_risk_budget_shares_capacity_between_same_day_entries():
    start = date(2025, 1, 2)
    data_a = _data("600001", [100.0, 100.0, 110.0, 110.0])
    data_b = _data("600002", [100.0, 100.0, 110.0, 110.0])
    events = []
    for code in ("600001", "600002"):
        events.append(
            {
                "event_id": f"{code}:0",
                "code": code,
                "stock_name": code,
                "signal_date": start,
                "entry_date": start + timedelta(days=1),
                "exit_date": start + timedelta(days=3),
                "entry_price": 100.0,
                "exit_price": 110.0,
                "signal": {},
                "signal_rank": (1.0, 70.0, 10.0, -20.0, code),
                "reference_entry": 100.0,
                "risk_geometry": {
                    "status": "OK",
                    "stop_price": 90.0,
                    "stop_distance_pct": 10.0,
                    "source": "test",
                },
            }
        )
    policy = PortfolioConstructionPolicy(
        name="risk",
        mode="risk_budget",
        risk_per_trade_pct=1.25,
        max_single_name_fraction=0.20,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=6.0,
    )
    curve, allocations, audit = replay_single_account(
        events,
        {"600001": data_a, "600002": data_b},
        start_date=start,
        end_date=start + timedelta(days=3),
        policy=policy,
    )

    assert [round(float(row["allocated_pct"]), 4) for row in allocations] == [12.5, 12.5]
    assert audit["allocated_event_count"] == 2
    assert round(float(curve.iloc[-1]), 6) == 1.025


def test_open_risk_cap_blocks_later_same_day_entry():
    start = date(2025, 1, 2)
    data_map = {}
    events = []
    for i in range(6):
        code = f"6001{i:02d}"
        data_map[code] = _data(code, [100.0, 100.0, 100.0, 100.0])
        events.append(
            {
                "event_id": f"{code}:0",
                "code": code,
                "stock_name": code,
                "signal_date": start,
                "entry_date": start + timedelta(days=1),
                "exit_date": start + timedelta(days=3),
                "entry_price": 100.0,
                "exit_price": 100.0,
                "signal": {},
                "signal_rank": (1.0, 70.0 - i, 10.0, -20.0, code),
                "reference_entry": 100.0,
                "risk_geometry": {
                    "status": "OK",
                    "stop_price": 90.0,
                    "stop_distance_pct": 10.0,
                    "source": "test",
                },
            }
        )
    policy = PortfolioConstructionPolicy(
        name="risk",
        risk_per_trade_pct=1.25,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=6.0,
    )
    _, allocations, audit = replay_single_account(
        events,
        data_map,
        start_date=start,
        end_date=start + timedelta(days=3),
        policy=policy,
    )

    allocated = [float(row["allocated_pct"]) for row in allocations]
    assert allocated[:4] == [12.5, 12.5, 12.5, 12.5]
    assert allocated[4] == 10.0
    assert allocated[5] == 0.0
    assert audit["allocated_event_count"] == 5


def test_next_open_below_frozen_stop_cancels_instead_of_resizing_with_future_price():
    start = date(2025, 1, 2)
    data = _data("600200", [100.0, 85.0, 85.0])
    event = {
        "event_id": "600200:0",
        "code": "600200",
        "stock_name": "600200",
        "signal_date": start,
        "entry_date": start + timedelta(days=1),
        "exit_date": start + timedelta(days=2),
        "entry_price": 85.0,
        "exit_price": 85.0,
        "signal": {},
        "signal_rank": (1.0, 70.0, 10.0, -20.0, "600200"),
        "reference_entry": 100.0,
        "risk_geometry": {
            "status": "OK",
            "stop_price": 90.0,
            "stop_distance_pct": 10.0,
            "source": "test",
        },
    }
    policy = PortfolioConstructionPolicy(name="risk")
    curve, allocations, audit = replay_single_account(
        [event],
        {"600200": data},
        start_date=start,
        end_date=start + timedelta(days=2),
        policy=policy,
    )

    assert allocations[0]["allocated_pct"] == 12.5
    assert audit["blocked_reason_counts"]["open_at_or_below_stop"] == 1
    assert round(float(curve.iloc[-1]), 6) == 1.0
