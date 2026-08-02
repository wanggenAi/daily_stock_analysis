from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from typing import Any, Callable

import pandas as pd
import pytest

from src.strategies.genge_cycle_bottom.backtest import (
    BALANCED_EXIT_POLICY_NAME,
    DEFAULT_BALANCED_EXIT_PARAMS,
    simulate_exit_policy,
)
from src.strategies.genge_cycle_bottom.signals import SignalType, StrategySignal
from src.strategies.genge_opportunity_discovery.live_exit_policy import (
    DAILY_SIGNAL_EXECUTION_TIMING,
    LIVE_BALANCED_EXIT_POLICY_VERSION,
    MAX_REFERENCE_HOLDING_SESSIONS,
    REFERENCE_EXECUTION_STATUS,
    evaluate_live_balanced_v7_exit,
    raw_tick_round,
    simulate_daily_signal_balanced_v7_exit,
)


RowMutator = Callable[[int, dict[str, Any]], None]


def test_raw_tick_round_is_half_up_at_half_fen_boundary() -> None:
    assert raw_tick_round(2.675) == 2.68
    assert raw_tick_round(2.6749) == 2.67


def _sixty_bars(mutator: RowMutator | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_close = 100.0
    start = date(2025, 1, 2)
    for day_number in range(1, 61):
        row: dict[str, Any] = {
            "date": start + timedelta(days=day_number - 1),
            "open": previous_close,
            "close": 100.0,
            "volume": 1_000.0,
            "ma20_post": 100.0,
            "ma60_post": 100.0,
        }
        if mutator is not None:
            mutator(day_number, row)
        row.setdefault("high", max(float(row["open"]), float(row["close"])) + 1.0)
        row.setdefault("low", min(float(row["open"]), float(row["close"])) - 1.0)
        previous_close = float(row["close"])
        rows.append(row)
    return rows


def _signal(trend_level: str) -> StrategySignal:
    return StrategySignal(
        code="000001",
        stock_name="测试股份",
        as_of_date="2025-01-01",
        signal_type=SignalType.CONFIRM_BUY,
        total_score=0.0,
        price_percentile_score=0.0,
        valuation_score=0.0,
        financial_safety_score=0.0,
        trend_stabilization_score=0.0,
        market_environment_score=0.0,
        industry_cycle_score=0.0,
        price_percentile_5y=0.2,
        trend_confirmation_level=trend_level,
        dynamic_stop_loss=80.0,
        stop_loss=80.0,
    )


def _profile_outcome(
    rows: list[dict[str, Any]], *, stop_loss: float = 80.0,
    logic_invalidation: float = 70.0, trend_level: str = "MEDIUM",
) -> dict[str, Any]:
    return simulate_daily_signal_balanced_v7_exit(
        entry_price=100.0,
        stop_loss=stop_loss,
        logic_invalidation_price=logic_invalidation,
        trend_confirmation_level=trend_level,
        future_rows=pd.DataFrame(rows),
    )


def _backtest_first_exit(
    rows: list[dict[str, Any]], *, stop_loss: float, trend_level: str,
) -> tuple[str, str]:
    outcome = simulate_exit_policy(
        signal=_signal(trend_level),
        entry_price=100.0,
        future_rows=pd.DataFrame(rows),
        horizon_days=60,
        stop_loss=stop_loss,
        policy_name=BALANCED_EXIT_POLICY_NAME,
        params=DEFAULT_BALANCED_EXIT_PARAMS,
    )
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"
    return (
        str(outcome[f"{prefix}exit_reason_60d"]),
        str(outcome[f"{prefix}exit_date_60d"]),
    )


def _live_first_exit(
    rows: list[dict[str, Any]], *, stop_loss: float, trend_level: str,
) -> tuple[str, str, dict[str, Any]]:
    state = None
    for row in rows:
        evaluation = evaluate_live_balanced_v7_exit(
            entry_price=100.0,
            stop_loss=stop_loss,
            trend_confirmation_level=trend_level,
            previous_state=state,
            bar={
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "ma20": row["ma20_post"],
                "ma60": row["ma60_post"],
            },
        )
        state = evaluation["state"]
        if evaluation["triggered"]:
            return (
                str(evaluation["exit_reason"]),
                str(state["exit_trigger_trade_date"]),
                state,
            )
    raise AssertionError("live evaluator did not emit an exit within 60 sessions")


def _assert_golden(
    rows: list[dict[str, Any]], *, stop_loss: float = 80.0,
    trend_level: str = "MEDIUM", expected_reason: str,
) -> dict[str, Any]:
    backtest_reason, backtest_date = _backtest_first_exit(
        rows, stop_loss=stop_loss, trend_level=trend_level,
    )
    live_reason, live_date, state = _live_first_exit(
        rows, stop_loss=stop_loss, trend_level=trend_level,
    )
    assert backtest_reason == expected_reason
    assert live_reason == backtest_reason
    assert live_date == backtest_date
    return state


def test_live_balanced_v7_hard_intraday_stop_matches_backtest() -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day == 1:
            row.update({"open": 100.0, "high": 101.0, "low": 91.0, "close": 100.0})

    state = _assert_golden(
        _sixty_bars(mutate), stop_loss=94.0, expected_reason="STOP_LOSS",
    )
    assert state["reference_holding_session_count"] == 1
    assert state["effective_stop_price"] == 94.0
    assert state["exit_reference_price"] == 94.0


def test_live_balanced_v7_double_close_stop_matches_backtest() -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day == 1:
            row.update({"open": 100.0, "high": 100.0, "low": 92.8, "close": 93.0})
        elif day == 2:
            row.update({"open": 93.0, "high": 94.0, "low": 92.0, "close": 92.5})

    state = _assert_golden(
        _sixty_bars(mutate), stop_loss=94.0, expected_reason="STOP_LOSS",
    )
    assert state["reference_holding_session_count"] == 2
    assert state["consecutive_close_below_stop"] == 1


def test_live_balanced_v7_stop_confirmation_reset_matches_backtest() -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day in {1, 3, 4}:
            row.update({"high": 100.0, "low": 92.8, "close": 93.0})
        elif day == 2:
            row.update({"high": 96.0, "low": 93.0, "close": 95.0})

    state = _assert_golden(
        _sixty_bars(mutate), stop_loss=94.0, expected_reason="STOP_LOSS",
    )
    assert state["reference_holding_session_count"] == 4


def test_live_balanced_v7_trend_break_matches_backtest() -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day >= 43:
            row["close"] = {43: 98.8, 44: 98.5, 45: 98.0}.get(day, 100.0)
            row["ma20_post"] = {43: 100.0, 44: 99.8, 45: 99.6}.get(day, 100.0)
            row["ma60_post"] = 97.0

    state = _assert_golden(
        _sixty_bars(mutate), expected_reason="TREND_BREAK_CONFIRMED",
    )
    assert state["reference_holding_session_count"] == 45


@pytest.mark.parametrize(
    ("peak_close", "pullback_close", "expected_trail"),
    [(120.0, 105.5, 12.0), (130.0, 119.0, 8.0)],
)
def test_live_balanced_v7_profit_trailing_tiers_match_backtest(
    peak_close: float, pullback_close: float, expected_trail: float,
) -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day == 1:
            row.update({"open": 100.0, "close": peak_close})
        elif day == 2:
            row.update({"open": peak_close, "close": pullback_close})

    state = _assert_golden(
        _sixty_bars(mutate), expected_reason="TAKE_PROFIT_TRAIL",
    )
    assert state["reference_holding_session_count"] == 2
    assert state["active_trail_drawdown_pct"] == expected_trail


def test_live_balanced_v7_no_repair_matches_backtest() -> None:
    def mutate(day: int, row: dict[str, Any]) -> None:
        if day == 55:
            row.update({"close": 99.0, "ma20_post": 100.0, "ma60_post": 98.0})

    state = _assert_golden(
        _sixty_bars(mutate), expected_reason="NO_REPAIR_40D",
    )
    assert state["reference_holding_session_count"] == 55


@pytest.mark.parametrize("trend_level", ["MEDIUM", "STRONG"])
def test_live_balanced_v7_fixed_60_session_exit_matches_backtest(
    trend_level: str,
) -> None:
    state = _assert_golden(
        _sixty_bars(), trend_level=trend_level, expected_reason="TIME_EXIT_60D",
    )
    assert state["reference_holding_session_count"] == MAX_REFERENCE_HOLDING_SESSIONS


def test_live_state_is_json_persistable_conditional_and_same_bar_idempotent() -> None:
    row = _sixty_bars()[0]
    bar = {
        "date": row["date"], "open": row["open"], "high": row["high"],
        "low": row["low"], "close": row["close"], "volume": row["volume"],
        "ma20": row["ma20_post"], "ma60": row["ma60_post"],
    }
    untouched_bar = copy.deepcopy(bar)
    first = evaluate_live_balanced_v7_exit(
        entry_price=100.0, stop_loss=80.0, trend_confirmation_level="MEDIUM",
        previous_state=None, bar=bar,
    )
    untouched_state = copy.deepcopy(first["state"])
    repeated = evaluate_live_balanced_v7_exit(
        entry_price=100.0, stop_loss=80.0, trend_confirmation_level="MEDIUM",
        previous_state=first["state"], bar=bar,
    )

    json.dumps(repeated["state"], ensure_ascii=False)
    assert repeated == first
    assert first["state"] == untouched_state
    assert bar == untouched_bar
    assert first["state"]["execution_status"] == REFERENCE_EXECUTION_STATUS
    assert first["state"]["execution_confirmation_required"] is True
    assert first["state"]["reference_entry_price"] == 100.0
    assert "entry_price" not in first["state"]
    assert first["state"]["policy_version"] == LIVE_BALANCED_EXIT_POLICY_VERSION
    assert first["state"]["reference_entry_trade_date"] == "2025-01-02"


def test_live_state_rejects_corrected_same_date_bar_instead_of_double_counting() -> None:
    row = _sixty_bars()[0]
    bar = {
        "date": row["date"], "open": row["open"], "high": row["high"],
        "low": row["low"], "close": row["close"], "volume": row["volume"],
        "ma20": row["ma20_post"], "ma60": row["ma60_post"],
    }
    first = evaluate_live_balanced_v7_exit(
        entry_price=100.0, stop_loss=80.0, trend_confirmation_level="MEDIUM",
        previous_state=None, bar=bar,
    )
    corrected = {**bar, "close": 99.5, "low": 98.5}
    with pytest.raises(ValueError, match="same-date bar differs"):
        evaluate_live_balanced_v7_exit(
            entry_price=100.0, stop_loss=80.0,
            trend_confirmation_level="MEDIUM",
            previous_state=first["state"], bar=corrected,
        )


def test_live_state_rejects_a_different_frozen_plan() -> None:
    row = _sixty_bars()[0]
    bar = {
        "date": row["date"], "open": row["open"], "high": row["high"],
        "low": row["low"], "close": row["close"], "volume": row["volume"],
        "ma20": row["ma20_post"], "ma60": row["ma60_post"],
    }
    first = evaluate_live_balanced_v7_exit(
        entry_price=100.0, stop_loss=80.0, trend_confirmation_level="MEDIUM",
        previous_state=None, bar=bar,
    )
    next_bar = {**bar, "date": date(2025, 1, 3)}
    with pytest.raises(ValueError, match="frozen plan"):
        evaluate_live_balanced_v7_exit(
            entry_price=100.0, stop_loss=81.0,
            trend_confirmation_level="MEDIUM",
            previous_state=first["state"], bar=next_bar,
        )


def test_profile_logic_invalidation_uses_next_open_and_excludes_post_sale_low() -> None:
    def mutate(day_number: int, row: dict[str, Any]) -> None:
        if day_number == 1:
            row.update(close=95.5, low=95.2)
        elif day_number == 2:
            row.update(open=90.0, high=91.0, low=80.0, close=89.0)

    rows = _sixty_bars(mutate)
    rows.append({**rows[-1], "date": rows[-1]["date"] + timedelta(days=1)})
    outcome = _profile_outcome(
        rows, stop_loss=97.0, logic_invalidation=95.8,
    )
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"

    assert outcome[f"{prefix}exit_reason_60d"] == "LOGIC_INVALIDATION"
    assert outcome[f"{prefix}exit_trigger_date_60d"] == str(rows[0]["date"])
    assert outcome[f"{prefix}exit_date_60d"] == str(rows[1]["date"])
    assert outcome[f"{prefix}exit_price_60d"] == 90.0
    assert outcome[f"{prefix}exit_adjusted_net_return_60d"] == pytest.approx(-10.3)
    assert outcome[f"{prefix}exit_adjusted_max_drawdown_60d"] == pytest.approx(-10.0)
    assert outcome[f"{prefix}exit_execution_timing_60d"] == DAILY_SIGNAL_EXECUTION_TIMING


def test_profile_entry_day_hard_stop_obeys_t1_and_gap_risk() -> None:
    def mutate(day_number: int, row: dict[str, Any]) -> None:
        if day_number == 1:
            row.update(close=100.0, low=90.0)
        elif day_number == 2:
            row.update(open=88.0, high=90.0, low=80.0, close=89.0)

    rows = _sixty_bars(mutate)
    rows.append({**rows[-1], "date": rows[-1]["date"] + timedelta(days=1)})
    outcome = _profile_outcome(
        rows, stop_loss=97.0, logic_invalidation=80.0,
    )
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"

    assert outcome[f"{prefix}exit_reason_60d"] == "STOP_LOSS"
    assert outcome[f"{prefix}exit_date_60d"] == str(rows[1]["date"])
    assert outcome[f"{prefix}exit_price_60d"] == 88.0
    assert outcome[f"{prefix}exit_adjusted_max_drawdown_60d"] == pytest.approx(-12.0)


def test_profile_day60_close_executes_at_day61_open() -> None:
    rows = _sixty_bars()
    day61 = {
        **rows[-1], "date": rows[-1]["date"] + timedelta(days=1),
        "open": 90.0, "high": 91.0, "low": 89.0, "close": 90.0,
    }
    rows.append(day61)
    outcome = _profile_outcome(rows)
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"

    assert outcome[f"{prefix}exit_reason_60d"] == "TIME_EXIT_60D"
    assert outcome[f"{prefix}exit_trigger_date_60d"] == str(rows[59]["date"])
    assert outcome[f"{prefix}exit_date_60d"] == str(day61["date"])
    assert outcome[f"{prefix}exit_price_60d"] == 90.0
    assert outcome[f"{prefix}exit_holding_days_60d"] == 60


def test_profile_locked_lower_open_waits_for_first_executable_open() -> None:
    def mutate(day_number: int, row: dict[str, Any]) -> None:
        if day_number == 1:
            row.update(close=95.5, low=95.2)
        elif day_number == 2:
            row.update(open=90.0, high=90.0, low=90.0, close=90.0)

    rows = _sixty_bars(mutate)
    rows.append({**rows[-1], "date": rows[-1]["date"] + timedelta(days=1)})
    outcome = _profile_outcome(
        rows, stop_loss=97.0, logic_invalidation=95.8,
    )
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"

    assert outcome[f"{prefix}exit_reason_60d"] == "LOGIC_INVALIDATION"
    assert outcome[f"{prefix}exit_date_60d"] == str(rows[2]["date"])
    assert outcome[f"{prefix}exit_price_60d"] == 90.0
    assert outcome[f"{prefix}exit_holding_days_60d"] == 2
    assert outcome[f"{prefix}exit_adjusted_max_drawdown_60d"] == pytest.approx(-10.0)


def test_profile_locked_lower_exit_unresolved_at_data_cutoff_is_incomplete() -> None:
    def mutate(day_number: int, row: dict[str, Any]) -> None:
        if day_number == 1:
            row.update(close=95.5, low=95.2)
        elif day_number >= 2:
            row.update(open=90.0, high=90.0, low=90.0, close=90.0)

    rows = _sixty_bars(mutate)
    rows.append({**rows[-1], "date": rows[-1]["date"] + timedelta(days=1)})
    outcome = _profile_outcome(
        rows, stop_loss=97.0, logic_invalidation=95.8,
    )
    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"

    assert outcome[f"{prefix}exit_reason_60d"] == "UNEXECUTABLE_LOCKED_LIMIT_REVIEW"
    assert outcome[f"{prefix}exit_date_60d"] is None
    assert outcome[f"{prefix}exit_adjusted_net_return_60d"] is None
