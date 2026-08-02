"""Pure, JSON-persistable live evaluation for the balanced-v7 exit policy.

The evaluator follows a *reference* entry after the market has objectively
traded through a frozen entry plan.  It never claims that the user placed an
order or owns a position.  Callers must keep any emitted exit conditional on
manual execution/position confirmation.

One complete daily bar is advanced at a time.  The policy is deliberately
capped at 60 reference holding sessions because the opportunity-discovery
exit profile currently validates a 60-session horizon; the backtest's optional
strong-trend extension is therefore not enabled here.

The reference entry, frozen stop, OHLC and moving averages must all use the
same corporate-action-adjusted price basis.  Trading-calendar gap detection
and raw-price display conversion remain responsibilities of the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import (
    BALANCED_EXIT_POLICY_NAME,
    DEFAULT_BALANCED_EXIT_PARAMS,
    max_drawdown_from_values,
    net_return_from_raw,
)


LIVE_BALANCED_EXIT_POLICY_VERSION = "balanced_v7_double_close_stop_live_60d_v3_execution"
REFERENCE_EXECUTION_STATUS = "UNCONFIRMED_REFERENCE_ENTRY"
MAX_REFERENCE_HOLDING_SESSIONS = 60
DAILY_SIGNAL_EXECUTION_TIMING = "NEXT_TRADE_SESSION_OPEN"

_POLICY_PARAMS = dict(DEFAULT_BALANCED_EXIT_PARAMS)
_POLICY_PARAMS_HASH = "sha256:" + hashlib.sha256(
    json.dumps(_POLICY_PARAMS, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def _number(value: Any, *, field: str, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{field} must be a finite {qualifier}number")
    return result


def is_one_price_bar(
    *, opening: Any, high: Any, low: Any, close: Any, tolerance: float = 1e-9,
) -> bool:
    """Return whether daily OHLC cannot prove queue execution at one price."""

    try:
        values = [
            _number(opening, field="bar.open", positive=True),
            _number(high, field="bar.high", positive=True),
            _number(low, field="bar.low", positive=True),
            _number(close, field="bar.close", positive=True),
        ]
    except ValueError:
        return False
    return max(values) - min(values) <= max(0.0, float(tolerance))


def raw_tick_round(value: Any) -> float:
    """Round a positive tradable A-share price to one fen, half-up."""

    number = _number(value, field="raw_price", positive=True)
    return float(
        Decimal(str(number)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _trade_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("bar.date must be an ISO trade date") from exc


def _trend_rank(level: str) -> int:
    normalized = str(level or "").strip().upper()
    ranks = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}
    if normalized not in ranks:
        raise ValueError(f"unsupported trend_confirmation_level: {level}")
    return ranks[normalized]


def _effective_stop(entry_price: float, stop_loss: float, trend_rank: int) -> float:
    params = dict(_POLICY_PARAMS)
    if trend_rank >= 3:
        params["stop_loss_min_pct"] = params.get("strong_stop_loss_min_pct")
        params["stop_loss_max_pct"] = params.get("strong_stop_loss_max_pct")

    # Mirror backtest._balanced_policy_stop_loss, including its ordering.
    stop = min(stop_loss, entry_price * 0.995)
    maximum_distance_pct = float(params.get("stop_loss_max_pct") or 0.0)
    if maximum_distance_pct > 0:
        stop = max(stop, entry_price * (1.0 - maximum_distance_pct / 100.0))
    minimum_distance_pct = float(params.get("stop_loss_min_pct") or 0.0)
    if minimum_distance_pct > maximum_distance_pct > 0:
        minimum_distance_pct = maximum_distance_pct
    if minimum_distance_pct > 0:
        stop = min(stop, entry_price * (1.0 - minimum_distance_pct / 100.0))
    if maximum_distance_pct > 0:
        stop = max(stop, entry_price * (1.0 - maximum_distance_pct / 100.0))
    return round(stop, 4)


def _normalized_bar(bar: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {
        "date": _trade_date(bar.get("date")),
        "open": _number(bar.get("open"), field="bar.open", positive=True),
        "high": _number(bar.get("high"), field="bar.high", positive=True),
        "low": _number(bar.get("low"), field="bar.low", positive=True),
        "close": _number(bar.get("close"), field="bar.close", positive=True),
        "volume": _number(bar.get("volume"), field="bar.volume"),
        "ma20": _number(bar.get("ma20"), field="bar.ma20", positive=True),
        "ma60": _number(bar.get("ma60"), field="bar.ma60", positive=True),
    }
    if normalized["volume"] < 0:
        raise ValueError("bar.volume must be non-negative")
    if normalized["low"] > min(normalized["open"], normalized["high"], normalized["close"]):
        raise ValueError("bar.low is inconsistent with OHLC")
    if normalized["high"] < max(normalized["open"], normalized["low"], normalized["close"]):
        raise ValueError("bar.high is inconsistent with OHLC")
    return normalized


def _bar_digest(bar: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(bar), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": state,
        "triggered": bool(state.get("exit_triggered")),
        "exit_reason": state.get("exit_reason"),
        "exit_reference_price": state.get("exit_reference_price"),
    }


def _validate_previous_state(
    previous_state: Mapping[str, Any], *, entry_price: float, stop_loss: float,
    logic_invalidation_price: float | None, trend_level: str, effective_stop: float,
) -> None:
    if previous_state.get("policy_name") != BALANCED_EXIT_POLICY_NAME:
        raise ValueError("previous_state policy_name is incompatible")
    if previous_state.get("policy_version") != LIVE_BALANCED_EXIT_POLICY_VERSION:
        raise ValueError("previous_state policy_version is incompatible")
    if previous_state.get("policy_params_hash") != _POLICY_PARAMS_HASH:
        raise ValueError("previous_state policy parameters are incompatible")
    comparisons = (
        ("reference_entry_price", entry_price),
        ("frozen_stop_loss", stop_loss),
        ("effective_stop_price", effective_stop),
    )
    for field, expected in comparisons:
        actual = _number(previous_state.get(field), field=f"previous_state.{field}", positive=True)
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"previous_state {field} does not match the frozen plan")
    stored_invalidation = previous_state.get("frozen_logic_invalidation_price")
    if logic_invalidation_price is None:
        if stored_invalidation not in {None, ""}:
            raise ValueError("previous_state logic invalidation does not match the frozen plan")
    else:
        actual_invalidation = _number(
            stored_invalidation,
            field="previous_state.frozen_logic_invalidation_price",
            positive=True,
        )
        if not math.isclose(
            actual_invalidation, logic_invalidation_price, rel_tol=0.0, abs_tol=1e-9,
        ):
            raise ValueError("previous_state logic invalidation does not match the frozen plan")
    if str(previous_state.get("entry_trend_confirmation_level") or "").upper() != trend_level:
        raise ValueError("previous_state trend level does not match the frozen plan")


def evaluate_live_balanced_v7_exit(
    *, entry_price: float, stop_loss: float, trend_confirmation_level: str,
    previous_state: Mapping[str, Any] | None, bar: Mapping[str, Any],
    logic_invalidation_price: float | None = None,
) -> dict[str, Any]:
    """Advance balanced-v7 by one complete daily bar.

    Args:
        entry_price: Deterministic reference fill from the frozen entry plan.
        stop_loss: Frozen technical stop supplied with that plan.
        logic_invalidation_price: Optional frozen close-based invalidation level
            from the same entry plan and adjusted price basis.
        trend_confirmation_level: Trend level frozen at setup/entry observation.
        previous_state: Prior returned ``state`` or ``None`` on the entry bar.
        bar: Mapping with date/open/high/low/close/volume/ma20/ma60.
            Price fields must share the reference entry's adjusted basis.

    Returns:
        A dict containing a JSON-serializable ``state`` plus ``triggered``,
        ``exit_reason`` and ``exit_reference_price``.  A trigger always means
        "exit if the user actually entered and still holds", never a position
        or execution assertion.
    """

    frozen_entry = _number(entry_price, field="entry_price", positive=True)
    frozen_stop = _number(stop_loss, field="stop_loss", positive=True)
    frozen_invalidation = (
        None
        if logic_invalidation_price in {None, ""}
        else _number(
            logic_invalidation_price,
            field="logic_invalidation_price",
            positive=True,
        )
    )
    trend_level = str(trend_confirmation_level or "").strip().upper()
    trend_rank = _trend_rank(trend_level)
    effective_stop = _effective_stop(frozen_entry, frozen_stop, trend_rank)
    current = _normalized_bar(bar)
    current_digest = _bar_digest(current)

    before = dict(previous_state or {})
    if before:
        _validate_previous_state(
            before, entry_price=frozen_entry, stop_loss=frozen_stop,
            logic_invalidation_price=frozen_invalidation,
            trend_level=trend_level, effective_stop=effective_stop,
        )
        previous_date = _trade_date(before.get("last_processed_trade_date"))
        if current["date"] < previous_date:
            raise ValueError("bar.date precedes the last processed trade date")
        if current["date"] == previous_date:
            if before.get("last_bar_digest") != current_digest:
                raise ValueError("same-date bar differs from the already processed bar")
            return _result(before)
        if bool(before.get("exit_triggered")):
            return _result(before)

    prior_count = int(before.get("reference_holding_session_count") or 0)
    day_number = prior_count + 1
    if day_number > MAX_REFERENCE_HOLDING_SESSIONS:
        raise ValueError("active state advanced beyond the fixed 60-session horizon")

    close = float(current["close"])
    low = float(current["low"])
    ma20 = float(current["ma20"])
    ma60 = float(current["ma60"])
    volume = float(current["volume"])
    previous_close = (
        _number(before.get("previous_close"), field="previous_state.previous_close", positive=True)
        if before.get("previous_close") is not None else None
    )
    previous_ma20 = (
        _number(before.get("previous_ma20"), field="previous_state.previous_ma20", positive=True)
        if before.get("previous_ma20") is not None else None
    )
    recent_volumes = [
        _number(value, field="previous_state.recent_volumes")
        for value in (before.get("recent_volumes") or [])
    ][-5:]
    positive_recent_volumes = [value for value in recent_volumes if value > 0]

    highest_close = max(
        frozen_entry,
        _number(
            before.get("highest_close_since_entry", frozen_entry),
            field="previous_state.highest_close_since_entry", positive=True,
        ),
        close,
    )
    highest_return = (highest_close - frozen_entry) / frozen_entry * 100.0
    current_return = (close - frozen_entry) / frozen_entry * 100.0
    below_ma20 = close < ma20
    below_ma60 = close < ma60
    below_ma20_count = (
        int(before.get("consecutive_close_below_ma20") or 0) + 1 if below_ma20 else 0
    )
    below_ma60_count = (
        int(before.get("consecutive_close_below_ma60") or 0) + 1 if below_ma60 else 0
    )
    ma20_turns_down = previous_ma20 is not None and ma20 < previous_ma20
    heavy_selloff = bool(
        previous_close is not None
        and close < previous_close
        and positive_recent_volumes
        and volume >= (sum(positive_recent_volumes) / len(positive_recent_volumes)) * 1.35
    )

    stop_close_count = int(before.get("consecutive_close_below_stop") or 0)
    reason: str | None = None
    exit_reference_price: float | None = None
    hard_intraday_pct = float(_POLICY_PARAMS.get("stop_hard_intraday_pct") or 0.0)
    hard_stop = (
        effective_stop * (1.0 - hard_intraday_pct / 100.0)
        if hard_intraday_pct > 0 else None
    )
    stop_confirm_by_close = bool(_POLICY_PARAMS.get("stop_confirm_by_close", False))
    stop_confirm_days = max(1, int(_POLICY_PARAMS.get("stop_confirm_close_days") or 1))
    stop_confirm_min_rank = int(_POLICY_PARAMS.get("stop_confirm_min_trend_rank") or 99)

    # Priority 1: balanced-v7 stop, including hard intraday penetration and
    # the medium/strong double-close confirmation rule.
    if low <= effective_stop:
        hard_stop_hit = hard_stop is not None and low <= hard_stop
        if stop_confirm_by_close and close > effective_stop and not hard_stop_hit:
            stop_close_count = 0
        elif (
            stop_confirm_by_close
            and trend_rank >= stop_confirm_min_rank
            and not hard_stop_hit
            and close <= effective_stop
            and stop_close_count + 1 < stop_confirm_days
        ):
            stop_close_count += 1
        else:
            reason = "STOP_LOSS"
            exit_reference_price = effective_stop
    elif close > effective_stop:
        stop_close_count = 0

    # Priority 2: the frozen setup's close-based logic invalidation.
    if reason is None and frozen_invalidation is not None and close <= frozen_invalidation:
        reason = "LOGIC_INVALIDATION"
        exit_reference_price = close

    # Priority 3: confirmed trend loss from session 45 onward.
    material_trend_loss = current_return <= -1.0
    trend_break_min_days = int(_POLICY_PARAMS.get("trend_break_min_days") or 20)
    if reason is None and material_trend_loss and day_number >= trend_break_min_days and (
        below_ma20_count >= 3
        or (below_ma20_count >= 2 and ma20_turns_down)
        or (below_ma60 and (below_ma60_count >= 2 or heavy_selloff))
    ):
        reason = "TREND_BREAK_CONFIRMED"
        exit_reference_price = close

    # Priority 4: profit trailing, using only closes observed through today.
    trail_start = float(_POLICY_PARAMS.get("trail_start_pct") or 10.0)
    trail_drawdown = float(_POLICY_PARAMS.get("trail_drawdown_pct") or 7.0)
    profit_high = float(_POLICY_PARAMS.get("profit_high_pct") or 18.0)
    high_profit_trail = float(
        _POLICY_PARAMS.get("profit_high_trail_drawdown_pct") or 5.5
    )
    active_trail: float | None = None
    if reason is None and highest_return >= trail_start:
        active_trail = high_profit_trail if highest_return >= profit_high else trail_drawdown
        close_drawdown = (close - highest_close) / highest_close * 100.0
        if close_drawdown <= -active_trail:
            reason = "TAKE_PROFIT_TRAIL"
            exit_reference_price = close

    # Priority 5: no repair from session 55 onward.
    no_repair_days = int(_POLICY_PARAMS.get("no_repair_days") or 40)
    if reason is None and day_number >= no_repair_days:
        weak_or_none = trend_rank <= 1
        no_repair = current_return <= -0.2 and highest_return < 5.0
        if no_repair and (weak_or_none or below_ma20):
            reason = "NO_REPAIR_40D"
            exit_reference_price = close

    # Priority 6: fixed 60-session exit.  No strong-trend extension is allowed.
    if reason is None and day_number >= MAX_REFERENCE_HOLDING_SESSIONS:
        reason = "TIME_EXIT_60D"
        exit_reference_price = close

    updated_recent_volumes = [*recent_volumes, volume][-5:]
    state = {
        "policy_name": BALANCED_EXIT_POLICY_NAME,
        "policy_version": LIVE_BALANCED_EXIT_POLICY_VERSION,
        "policy_params_hash": _POLICY_PARAMS_HASH,
        "maximum_reference_holding_sessions": MAX_REFERENCE_HOLDING_SESSIONS,
        "execution_status": REFERENCE_EXECUTION_STATUS,
        "execution_confirmation_required": True,
        "reference_entry_price": frozen_entry,
        "reference_entry_trade_date": (
            before.get("reference_entry_trade_date") or current["date"]
        ),
        "frozen_stop_loss": frozen_stop,
        "frozen_logic_invalidation_price": frozen_invalidation,
        "effective_stop_price": effective_stop,
        "hard_intraday_stop_price": hard_stop,
        "entry_trend_confirmation_level": trend_level,
        "reference_holding_session_count": day_number,
        "last_processed_trade_date": current["date"],
        "last_bar_digest": current_digest,
        "highest_close_since_entry": highest_close,
        "highest_return_pct": highest_return,
        "current_return_pct": current_return,
        "consecutive_close_below_stop": stop_close_count,
        "consecutive_close_below_ma20": below_ma20_count,
        "consecutive_close_below_ma60": below_ma60_count,
        "previous_close": close,
        "previous_ma20": ma20,
        "recent_volumes": updated_recent_volumes,
        "active_trail_drawdown_pct": active_trail,
        "exit_triggered": reason is not None,
        "exit_reason": reason,
        "exit_trigger_trade_date": current["date"] if reason is not None else None,
        "exit_reference_price": exit_reference_price,
    }
    return _result(state)


def _daily_signal_exit_result(
    *, reason: str, trigger_row: Mapping[str, Any] | None,
    execution_row: Mapping[str, Any] | None, entry_price: float,
    exit_price: float | None, holding_days: int | None,
    max_drawdown: float | None, fee_bps: float, slippage_bps: float,
) -> dict[str, Any]:
    """Return the legacy profile column names with explicit signal timing."""

    prefix = f"{BALANCED_EXIT_POLICY_NAME}_"
    raw_return = (
        round((exit_price - entry_price) / entry_price * 100.0, 4)
        if exit_price is not None and entry_price > 0 else None
    )

    def trade_date(row: Mapping[str, Any] | None) -> str | None:
        if row is None:
            return None
        value = row.get("date")
        return _trade_date(value) if value not in {None, ""} else None

    return {
        f"{prefix}exit_trigger_date_60d": trade_date(trigger_row),
        f"{prefix}exit_date_60d": trade_date(execution_row),
        f"{prefix}exit_reason_60d": reason,
        f"{prefix}exit_price_60d": round(exit_price, 4) if exit_price is not None else None,
        f"{prefix}exit_adjusted_raw_return_60d": raw_return,
        f"{prefix}exit_adjusted_net_return_60d": net_return_from_raw(
            raw_return, fee_bps, slippage_bps,
        ),
        f"{prefix}exit_adjusted_max_drawdown_60d": max_drawdown,
        f"{prefix}exit_holding_days_60d": holding_days,
        f"{prefix}exit_execution_timing_60d": DAILY_SIGNAL_EXECUTION_TIMING,
    }


def simulate_daily_signal_balanced_v7_exit(
    *, entry_price: float, stop_loss: float, logic_invalidation_price: float,
    trend_confirmation_level: str, future_rows: pd.DataFrame,
    fee_bps: float = 5.0, slippage_bps: float = 10.0,
) -> dict[str, Any]:
    """Replay the production end-of-day exit signal with A-share T+1 timing.

    The first row is the reference entry session. Every exit condition is
    learned from a completed daily bar, so the historical profile executes the
    resulting signal at the *next* trade session's open. This prevents same-day
    exits after an A-share purchase, impossible fills at a breached stop, and
    use of the execution day's post-sale low in drawdown. Sixty holding bars
    therefore require a 61st bar for executable next-open evidence.
    """

    frozen_entry = _number(entry_price, field="entry_price", positive=True)
    frozen_stop = _number(stop_loss, field="stop_loss", positive=True)
    frozen_invalidation = _number(
        logic_invalidation_price, field="logic_invalidation_price", positive=True,
    )
    if future_rows is None or len(future_rows) < MAX_REFERENCE_HOLDING_SESSIONS + 1:
        return _daily_signal_exit_result(
            reason="INSUFFICIENT_NEXT_OPEN_DATA", trigger_row=None,
            execution_row=None, entry_price=frozen_entry, exit_price=None,
            holding_days=None, max_drawdown=None,
            fee_bps=fee_bps, slippage_bps=slippage_bps,
        )

    # Keep rows beyond the mandatory day-61 execution bar.  A lower one-price
    # session cannot prove that a sell order filled, so an already-triggered
    # exit must remain pending until the first later executable opening.
    window = future_rows.copy().reset_index(drop=True)
    state: Mapping[str, Any] | None = None
    held_lows: list[float] = []
    trigger_index: int | None = None
    trigger_reason = ""
    for index in range(MAX_REFERENCE_HOLDING_SESSIONS):
        row = window.iloc[index]
        evaluation = evaluate_live_balanced_v7_exit(
            entry_price=frozen_entry,
            stop_loss=frozen_stop,
            logic_invalidation_price=frozen_invalidation,
            trend_confirmation_level=trend_confirmation_level,
            previous_state=state,
            bar={
                "date": row.get("date"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "ma20": row.get("ma20_post"),
                "ma60": row.get("ma60_post"),
            },
        )
        state = evaluation["state"]
        held_lows.append(_number(row.get("low"), field="bar.low", positive=True))
        if evaluation["triggered"]:
            trigger_index = index
            trigger_reason = str(evaluation.get("exit_reason") or "")
            break

    if trigger_index is None:  # pragma: no cover - day 60 is a mandatory exit
        return _daily_signal_exit_result(
            reason="INTERNAL_NO_EXIT_TRIGGER", trigger_row=None,
            execution_row=None, entry_price=frozen_entry, exit_price=None,
            holding_days=None, max_drawdown=None,
            fee_bps=fee_bps, slippage_bps=slippage_bps,
        )

    trigger_row = window.iloc[trigger_index]
    execution_index = trigger_index + 1
    execution_row: Mapping[str, Any] | None = None
    execution_open: float | None = None
    while execution_index < len(window):
        candidate = window.iloc[execution_index]
        candidate_open = _number(
            candidate.get("open"), field="execution_bar.open", positive=True,
        )
        candidate_high = _number(
            candidate.get("high"), field="execution_bar.high", positive=True,
        )
        candidate_low = _number(
            candidate.get("low"), field="execution_bar.low", positive=True,
        )
        candidate_close = _number(
            candidate.get("close"), field="execution_bar.close", positive=True,
        )
        previous_close = _number(
            window.iloc[execution_index - 1].get("close"),
            field="previous_bar.close", positive=True,
        )
        locked_lower = bool(
            is_one_price_bar(
                opening=candidate_open, high=candidate_high,
                low=candidate_low, close=candidate_close,
            )
            and candidate_open <= previous_close + 1e-9
        )
        if not locked_lower:
            execution_row = candidate
            execution_open = candidate_open
            break
        # The position is still exposed for the entire locked session.
        held_lows.append(candidate_low)
        execution_index += 1

    if execution_row is None or execution_open is None:
        return _daily_signal_exit_result(
            reason="UNEXECUTABLE_LOCKED_LIMIT_REVIEW",
            trigger_row=trigger_row,
            execution_row=None,
            entry_price=frozen_entry,
            exit_price=None,
            holding_days=len(window),
            max_drawdown=None,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
    # The next session's low occurs after the modeled opening sale and must not
    # contaminate drawdown. The opening gap itself remains part of risk.
    max_drawdown = max_drawdown_from_values(
        frozen_entry, [*held_lows, execution_open],
    )
    return _daily_signal_exit_result(
        reason=trigger_reason,
        trigger_row=trigger_row,
        execution_row=execution_row,
        entry_price=frozen_entry,
        exit_price=execution_open,
        holding_days=execution_index,
        max_drawdown=max_drawdown,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )


__all__ = [
    "LIVE_BALANCED_EXIT_POLICY_VERSION",
    "MAX_REFERENCE_HOLDING_SESSIONS",
    "REFERENCE_EXECUTION_STATUS",
    "DAILY_SIGNAL_EXECUTION_TIMING",
    "is_one_price_bar",
    "raw_tick_round",
    "evaluate_live_balanced_v7_exit",
    "simulate_daily_signal_balanced_v7_exit",
]
