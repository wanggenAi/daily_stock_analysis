"""Deterministic balanced-exit profile generation for opportunity discovery."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean, median, stdev
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BALANCED_EXIT_POLICY_NAME
from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.live_exit_policy import (
    is_one_price_bar,
    raw_tick_round,
    simulate_daily_signal_balanced_v7_exit,
)
from src.strategies.genge_opportunity_discovery.real_world_signals import (
    history_snapshot,
    price_volume_state,
)


PROFILE_RULE_VERSION = "genge_opportunity_discovery_v9_outcome_replay_quality"
REPORT_AGGREGATE_RULE_VERSION = "genge_opportunity_discovery_v1_report_aggregate"
PROFILE_RETURN_HORIZON_SESSIONS = 60
PROFILE_EXIT_EXECUTION_LAG_SESSIONS = 1
PROFILE_SAMPLE_SPACING_SESSIONS = (
    PROFILE_RETURN_HORIZON_SESSIONS + PROFILE_EXIT_EXECUTION_LAG_SESSIONS
)
MIN_PROFILE_SAMPLE_COUNT = 12
MIN_RECENT_2Y_SAMPLE_COUNT = 3
HIGH_CONFIDENCE_SAMPLE_COUNT = 30
MIN_DEGRADED_SAMPLE_COUNT = 6
MIN_OUTCOME_REPLAY_COVERAGE_RATIO = .80
MAX_RUN_GAP_OUTCOME_RATIO = .05
COHORT_FORMATION_WINDOW_SESSIONS = 10
MIN_COHORT_CODES_PER_PERIOD = 3
MIN_COHORT_UNIQUE_CODE_COUNT = 8
MIN_COHORT_RECENT_UNIQUE_CODE_COUNT = 5
COHORT_RETURN_LOWER_BOUND_Z = 1.2816
COHORT_MIN_MEAN_RETURN_PCT = 0.5
COHORT_MIN_POSITIVE_PERIOD_RATE_PCT = 45.0
COHORT_MIN_RECENT_MEAN_RETURN_PCT = 0.0
COHORT_MIN_AVG_DRAWDOWN_PCT = -12.0
COHORT_MIN_TAIL_DRAWDOWN_PCT = -18.0
COHORT_MIN_MEMBER_WIN_RATE_PCT = 45.0
COHORT_MIN_MEMBER_TAIL_RETURN_PCT = -15.0
COHORT_MIN_MEMBER_TAIL_DRAWDOWN_PCT = -18.0
COHORT_MAX_CODE_PERIOD_SHARE = .50
HISTORY_CACHE_SCHEMA_VERSION = 4
HISTORY_CACHE_MIN_ROWS = 350
HISTORY_CACHE_MAX_AGE_DAYS = 7
HISTORY_PRICE_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")
HISTORY_CACHE_COLUMNS = (
    *HISTORY_PRICE_COLUMNS,
    "raw_open", "raw_high", "raw_low", "raw_close", "adjustment_ratio",
)


EXIT_PROFILE_COLUMNS = [
    "code",
    "stock_name",
    "exit_profile_entry_mode",
    "balanced_exit_historical_profile",
    "signal_count",
    "avg_balanced_exit_net_return_60d",
    "win_rate_balanced_exit_60d",
    "avg_balanced_exit_max_drawdown_60d",
    "avg_balanced_exit_max_drawdown_250d",
    "source_signal_details",
    "profile_data_end_date",
    "profile_rule_version",
    "profile_data_version",
    "profile_confidence",
    "recent_2y_sample_count",
    "profile_validation_scope",
    "profile_position_multiplier",
    "stock_profile_status",
    "stock_signal_count",
    "stock_incomplete_outcome_count",
    "stock_outcome_attempt_count",
    "stock_replayable_outcome_count",
    "stock_replay_excluded_outcome_count",
    "stock_hard_veto_outcome_count",
    "stock_corporate_action_excluded_count",
    "stock_run_gap_excluded_count",
    "stock_right_censored_count",
    "stock_outcome_replay_coverage_ratio",
    "stock_run_gap_outcome_ratio",
    "stock_replay_quality_passed",
    "stock_recent_2y_sample_count",
    "stock_avg_net_return_60d",
    "stock_recent_avg_net_return_60d",
    "stock_win_rate_60d",
    "stock_avg_drawdown_60d",
    "stock_recent_stability_passed",
    "cohort_key",
    "cohort_profile_status",
    "cohort_period_count",
    "cohort_recent_2y_period_count",
    "cohort_unique_code_count",
    "cohort_recent_2y_unique_code_count",
    "cohort_member_sample_count",
    "cohort_avg_net_return_60d",
    "cohort_return_lower_bound_60d",
    "cohort_positive_period_rate_60d",
    "cohort_avg_drawdown_60d",
    "cohort_tail_drawdown_60d",
    "cohort_member_win_rate_60d",
    "cohort_member_tail_return_60d",
    "cohort_member_tail_drawdown_60d",
    "cohort_max_code_period_share",
    "cohort_code_concentration_passed",
    "cohort_outcome_end_complete",
    "cohort_invalid_outcome_end_count",
    "cohort_outcome_attempt_count",
    "cohort_replayable_outcome_count",
    "cohort_replay_excluded_outcome_count",
    "cohort_hard_veto_outcome_count",
    "cohort_corporate_action_excluded_count",
    "cohort_run_gap_excluded_count",
    "cohort_right_censored_count",
    "cohort_outcome_replay_coverage_ratio",
    "cohort_run_gap_outcome_ratio",
    "cohort_replay_quality_passed",
    "cohort_excluded_target_code",
    "cohort_recent_avg_net_return_60d",
    "cohort_independence_passed",
    "cohort_recent_stability_passed",
    "stock_negative_veto_clear",
    "pullback_profile_status",
    "pullback_signal_count",
    "pullback_incomplete_outcome_count",
    "pullback_avg_net_return_60d",
    "pullback_win_rate_60d",
    "pullback_avg_drawdown_60d",
    "pullback_avg_drawdown_250d",
    "pullback_recent_2y_sample_count",
    "breakout_profile_status",
    "breakout_signal_count",
    "breakout_incomplete_outcome_count",
    "breakout_avg_net_return_60d",
    "breakout_win_rate_60d",
    "breakout_avg_drawdown_60d",
    "breakout_avg_drawdown_250d",
    "breakout_recent_2y_sample_count",
    "generated_at",
    "rule",
]


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


_REPLAY_EXCLUDED_OUTCOME_REASONS = {
    "CORPORATE_ACTION_REVIEW": "corporate_action",
    "RUN_GAP_POSITION_REVIEW": "run_gap",
    "INSUFFICIENT_NEXT_OPEN_DATA": "right_censored",
    "RIGHT_CENSORED_60D": "right_censored",
}
_HARD_VETO_OUTCOME_REASONS = {
    "OUTCOME_EXECUTION_DATE_UNMAPPED",
    "UNEXECUTABLE_LOCKED_LIMIT_REVIEW",
}


def _outcome_replay_quality(
    samples: Iterable[Mapping[str, Any]], *, as_of: date | None = None,
    require_outcome_end: bool = False,
) -> dict[str, Any]:
    """Separate replay coverage gaps from adverse unexecutable outcomes.

    Corporate-action basis changes, known history gaps and normal right
    censoring cannot contribute returns or drawdowns, but remain in the
    denominator so selectively missing outcomes cannot improve validation.
    Locked-limit non-execution and unknown incomplete reasons are hard vetoes.
    """

    rows = list(samples)
    replayable_count = 0
    excluded_counts: Counter[str] = Counter()
    hard_veto_count = 0
    hard_veto_reasons: Counter[str] = Counter()
    for item in rows:
        net_return = _number(item.get("return"))
        drawdown = _number(item.get("drawdown"))
        if item.get("outcome_complete") is not False and (
            net_return is not None and drawdown is not None
        ):
            if require_outcome_end:
                sample_date = _parse_date(item.get("as_of_date"))
                outcome_end_date = _parse_date(item.get("outcome_end_date"))
                if (
                    as_of is None or not _normalize_code(item.get("code"))
                    or sample_date is None or sample_date > as_of
                    or outcome_end_date is None or outcome_end_date < sample_date
                    or outcome_end_date > as_of
                ):
                    hard_veto_count += 1
                    hard_veto_reasons["INVALID_OUTCOME_EXECUTION_DATE"] += 1
                    continue
            replayable_count += 1
            continue
        reason = str(item.get("exit_reason") or "").strip().upper()
        excluded_category = _REPLAY_EXCLUDED_OUTCOME_REASONS.get(reason)
        if item.get("outcome_complete") is False and excluded_category:
            excluded_counts[excluded_category] += 1
            continue
        hard_veto_count += 1
        hard_veto_reasons[reason or "UNKNOWN_INCOMPLETE_OUTCOME"] += 1

    attempt_count = len(rows)
    excluded_count = sum(excluded_counts.values())
    replay_coverage = replayable_count / attempt_count if attempt_count else 0.0
    run_gap_ratio = excluded_counts["run_gap"] / attempt_count if attempt_count else 0.0
    quality_passed = bool(
        attempt_count
        and hard_veto_count == 0
        and replay_coverage >= MIN_OUTCOME_REPLAY_COVERAGE_RATIO
        and run_gap_ratio <= MAX_RUN_GAP_OUTCOME_RATIO
    )
    return {
        "outcome_attempt_count": attempt_count,
        "replayable_outcome_count": replayable_count,
        "replay_excluded_outcome_count": excluded_count,
        "hard_veto_outcome_count": hard_veto_count,
        "corporate_action_excluded_count": excluded_counts["corporate_action"],
        "run_gap_excluded_count": excluded_counts["run_gap"],
        "right_censored_count": excluded_counts["right_censored"],
        "outcome_replay_coverage_ratio": replay_coverage,
        "run_gap_outcome_ratio": run_gap_ratio,
        "replay_quality_passed": quality_passed,
        "hard_veto_reasons": dict(hard_veto_reasons),
    }


def _status_with_replay_quality(
    values: list[float], drawdowns: list[float], replay_quality: Mapping[str, Any],
) -> str:
    """Apply replay-quality gates without relabeling missing data as a loss."""

    if int(replay_quality.get("hard_veto_outcome_count") or 0):
        return "FAILED"
    performance_status = _status_for(values, drawdowns)
    if performance_status == "PASSED" and not replay_quality.get("replay_quality_passed"):
        return "DEGRADED"
    return performance_status


def _setup_adjustment_ratio(frame: pd.DataFrame, setup_index: int) -> float | None:
    """Return the exact-date raw/qfq close mapping used by the live plan."""

    if "adjustment_ratio" not in frame.columns:
        return None
    ratio = _number(frame.iloc[setup_index].get("adjustment_ratio"))
    if ratio is None or ratio <= 0:
        return None
    return ratio if math.isfinite(ratio) and ratio > 0 else None


def _price_mapping_regime_stable(
    frame: pd.DataFrame, *, start_index: int, end_index: int,
) -> bool:
    """Reject windows that the live lifecycle would stop for a basis rewrite."""

    if "adjustment_ratio" not in frame.columns:
        return False
    ratios = pd.to_numeric(
        frame.iloc[start_index : end_index + 1]["adjustment_ratio"], errors="coerce",
    )
    if ratios.empty or ratios.isna().any() or (ratios <= 0).any():
        return False
    # Match the production anchor comparison. Exact Sina factors are piecewise
    # constant; a Baostock rounded fallback that cannot prove the same mapping
    # is deliberately excluded rather than allowed to validate an exit edge.
    return bool(ratios.pct_change().abs().fillna(0.0).max() <= 1e-5)


def _candidate_signal_files(source_dirs: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for source_dir in source_dirs:
        root = Path(source_dir)
        if not root.exists():
            continue
        files.extend(root.glob("**/signal_details.csv"))
    return sorted(set(files), key=lambda path: path.stat().st_mtime, reverse=True)


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _exchange_session_continuity(dates: Iterable[Any]) -> list[bool]:
    """Mark whether each row immediately follows the prior XSHG session."""

    normalized = [_parse_date(value) for value in dates]
    if not normalized:
        return []
    flags = [True]
    try:
        import exchange_calendars as xcals

        valid_dates = [value for value in normalized if value is not None]
        if not valid_dates:
            return [False] * len(normalized)
        calendar = xcals.get_calendar(
            "XSHG", start=min(valid_dates), end=max(valid_dates),
        )
        sessions = calendar.sessions_in_range(min(valid_dates), max(valid_dates))
        positions = {session.date(): index for index, session in enumerate(sessions)}
        for previous, current in zip(normalized, normalized[1:]):
            flags.append(bool(
                previous in positions and current in positions
                and positions[current] - positions[previous] == 1
            ))
    except Exception:
        # A Western weekday calendar misclassifies long Chinese exchange
        # holidays as missing stock observations. If the authoritative calendar
        # is unavailable, fail closed instead of inventing continuity.
        flags.extend(False for _ in normalized[1:])
    return flags


def _session_window_contiguous(
    frame: pd.DataFrame, *, start_index: int, end_index: int,
) -> bool:
    if start_index < 0 or end_index < start_index or end_index >= len(frame):
        return False
    if end_index == start_index:
        return True
    column = frame.get("session_contiguous_from_previous")
    flags = (
        list(pd.Series(column).fillna(False).astype(bool))
        if column is not None else _exchange_session_continuity(frame["date"])
    )
    return all(flags[start_index + 1 : end_index + 1])


def _file_version(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _status_for(values: list[float], drawdowns: list[float]) -> str:
    sample_count = len(values)
    if sample_count < MIN_DEGRADED_SAMPLE_COUNT:
        return "NOT_AVAILABLE"
    # A return-only profile cannot establish that the exit policy controlled
    # downside. Treat incomplete risk outcomes as a failed validation instead
    # of silently allowing them through.
    if len(drawdowns) != sample_count:
        return "FAILED"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns)
    if sample_count >= MIN_PROFILE_SAMPLE_COUNT and avg_return >= 0 and win_rate >= 45 and avg_drawdown >= -12:
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and avg_drawdown >= -18:
        return "DEGRADED"
    return "FAILED"


def _report_status_for(values: list[float], drawdowns: list[float]) -> str:
    """Preserve the legacy report-aggregation policy outside strict live refresh."""
    if len(values) < 10:
        return "NOT_AVAILABLE"
    if len(drawdowns) != len(values):
        return "FAILED"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
    if len(values) >= 20 and avg_return >= 0 and win_rate >= 45 and (avg_drawdown is None or avg_drawdown >= -12):
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and (avg_drawdown is None or avg_drawdown >= -18):
        return "DEGRADED"
    return "FAILED"


def _atr_at(history: pd.DataFrame, days: int = 14) -> float | None:
    if len(history) < days + 1:
        return None
    high = pd.to_numeric(history["high"], errors="coerce")
    low = pd.to_numeric(history["low"], errors="coerce")
    close = pd.to_numeric(history["close"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1,
    ).max(axis=1)
    value = _number(true_range.tail(days).mean())
    return value if value is not None and value > 0 else None


def _cluster_levels(values: list[float], tolerance: float) -> list[tuple[float, int]]:
    levels: list[list[float]] = []
    for value in sorted(item for item in values if item > 0):
        for group in levels:
            center = sum(group) / len(group)
            if abs(value - center) <= tolerance:
                group.append(value)
                break
        else:
            levels.append([value])
    return [(sum(group) / len(group), len(group)) for group in levels]


def _support_at(history: pd.DataFrame, atr14: float, close: float) -> float | None:
    """Match the live plan's support selection using only prior rows."""
    recent = history.tail(120)
    lows = pd.to_numeric(recent["low"], errors="coerce").dropna().tolist()
    tolerance = max(atr14 * .45, close * .015)
    candidates = [
        (level, touches)
        for level, touches in _cluster_levels(lows, tolerance)
        if touches >= 2 and level <= close * 1.02
    ]
    for days in (20, 60):
        if len(history) < days:
            continue
        moving_average = _number(pd.to_numeric(history["close"], errors="coerce").tail(days).mean())
        if moving_average is None or moving_average > close * 1.02:
            continue
        touches = int((pd.to_numeric(recent["low"], errors="coerce").sub(moving_average).abs() <= tolerance).sum())
        if touches >= 2:
            candidates.append((moving_average, touches))
    candidates.sort(key=lambda item: (abs(close - item[0]), -item[1]))
    return candidates[0][0] if candidates else None


def _resistance_pivots(
    history: pd.DataFrame, *, atr14: float, pivot_window: int = 3,
    history_is_prepared: bool = False,
) -> list[tuple[float, float]]:
    """Return point-in-time resistance pivots shared by both entry plans."""

    prepared = history if history_is_prepared else prepare_price_frame(history)
    local = prepared.tail(500).reset_index(drop=True)
    highs = pd.to_numeric(local["high"], errors="coerce")
    lows = pd.to_numeric(local["low"], errors="coerce")
    pivots: list[tuple[float, float]] = []
    for index in range(pivot_window, len(local) - pivot_window):
        price = float(highs.iloc[index])
        local_highs = highs.iloc[index - pivot_window : index + pivot_window + 1]
        if not math.isfinite(price) or price < float(local_highs.max()):
            continue
        shoulders = pd.concat([
            lows.iloc[index - pivot_window : index],
            lows.iloc[index + 1 : index + pivot_window + 1],
        ]).dropna()
        if shoulders.empty:
            continue
        prominence = price - float(shoulders.mean())
        if prominence >= max(atr14 * .35, price * .008):
            pivots.append((price, prominence))
    return pivots


def _eligible_resistance_prices(
    history: pd.DataFrame, *, atr14: float, entry: float, pivot_window: int = 3,
    history_is_prepared: bool = False,
    pivots: list[tuple[float, float]] | None = None,
) -> list[float]:
    """Mirror the production plan's point-in-time real-resistance selector."""

    if pivots is None:
        pivots = _resistance_pivots(
            history, atr14=atr14, pivot_window=pivot_window,
            history_is_prepared=history_is_prepared,
        )
    tolerance = max(atr14 * .35, entry * .01)
    groups: list[list[tuple[float, float]]] = []
    for price, prominence in sorted(pivots):
        for group in groups:
            center = sum(item[0] for item in group) / len(group)
            if abs(price - center) <= tolerance:
                group.append((price, prominence))
                break
        else:
            groups.append([(price, prominence)])
    above = sorted(
        (
            {
                "price": sum(item[0] for item in group) / len(group),
                "touches": len(group),
            }
            for group in groups
        ),
        key=lambda item: float(item["price"]),
    )
    minimum_distance = max(atr14, entry * .02)
    return [
        float(item["price"])
        for item in above
        if item["touches"] >= 2
        and float(item["price"]) > entry
        and float(item["price"]) - entry >= minimum_distance
    ]


def _strict_point_in_time_plan_mode(
    *, setup_history: pd.DataFrame, adjustment_ratio: float,
    max_chase_atr_multiple: float, volatility_multiplier: float,
    history_is_prepared: bool = False,
) -> str:
    """Return the production-preferred mode only when its raw-tick RR is ready."""

    current = _number(setup_history.iloc[-1].get("close"))
    atr14 = _atr_at(setup_history)
    if current is None or current <= 0 or atr14 is None or adjustment_ratio <= 0:
        return ""
    adjusted_tick = .01 / adjustment_ratio
    resistance_pivots = _resistance_pivots(
        setup_history, atr14=atr14,
        history_is_prepared=history_is_prepared,
    )
    pullback_rr: float | None = None
    support = _support_at(setup_history, atr14, current)
    if support is not None:
        entry_low = support - .30 * atr14
        entry_high = min(current, support + .20 * atr14)
        stop = min(entry_low - adjusted_tick, support - .75 * atr14)
        targets = _eligible_resistance_prices(
            setup_history, atr14=atr14, entry=entry_high,
            history_is_prepared=history_is_prepared,
            pivots=resistance_pivots,
        )
        if targets:
            entry_low_raw, entry_high_raw, stop_raw, target_raw = [
                raw_tick_round(value * adjustment_ratio)
                for value in (entry_low, entry_high, stop, targets[0])
            ]
            if stop_raw < entry_low_raw <= entry_high_raw < target_raw:
                pullback_rr = round(
                    (target_raw - entry_high_raw) / (entry_high_raw - stop_raw), 2,
                )

    recent_high = _number(
        pd.to_numeric(setup_history.tail(20)["high"], errors="coerce").max(),
    )
    breakout_rr: float | None = None
    if recent_high is not None:
        trigger = recent_high + .10 * atr14
        confirmation = trigger + .20 * atr14
        max_chase = confirmation + max_chase_atr_multiple * atr14
        stop = trigger - max(
            1.20 * atr14 * volatility_multiplier, trigger * .025,
        )
        targets = _eligible_resistance_prices(
            setup_history, atr14=atr14, entry=max_chase,
            history_is_prepared=history_is_prepared,
            pivots=resistance_pivots,
        )
        if targets:
            trigger_raw, max_chase_raw, stop_raw, target_raw = [
                raw_tick_round(value * adjustment_ratio)
                for value in (trigger, max_chase, stop, targets[0])
            ]
            if stop_raw < trigger_raw <= max_chase_raw < target_raw:
                breakout_rr = round(
                    (target_raw - max_chase_raw) / (max_chase_raw - stop_raw), 2,
                )

    if breakout_rr is not None and (pullback_rr is None or breakout_rr >= pullback_rr):
        preferred, reward_risk = "breakout", breakout_rr
    elif pullback_rr is not None:
        preferred, reward_risk = "pullback", pullback_rr
    else:
        return ""
    return preferred if reward_risk >= 1.8 else ""


def _observable_setup_gates_pass(
    frame: pd.DataFrame, *, index: int, minimum_history_rows: int,
    minimum_turnover: float, max_5d_return_pct: float,
    max_10d_return_pct: float,
) -> bool:
    """Replay strict point-in-time gates derivable from the cached OHLCV data."""

    history = frame.iloc[: index + 1].copy()
    if len(history) < max(1, int(minimum_history_rows)):
        return False
    close = pd.to_numeric(history["close"], errors="coerce")
    current = _number(close.iloc[-1])
    if current is None or current <= 0:
        return False
    historical = close.tail(1250).dropna()
    percentile = (
        float((historical <= current).sum() / len(historical))
        if not historical.empty else None
    )
    ma20 = _number(close.tail(20).mean()) if len(close) >= 20 else None
    ma60 = _number(close.tail(60).mean()) if len(close) >= 60 else None
    prior_ma20 = _number(close.iloc[-25:-5].mean()) if len(close) >= 25 else None
    prior_ma60 = _number(close.iloc[-65:-5].mean()) if len(close) >= 65 else None
    ma20_slope = (
        (ma20 / prior_ma20 - 1.0) * 100.0
        if ma20 is not None and prior_ma20 not in {None, 0.0} else None
    )
    ma60_slope = (
        (ma60 / prior_ma60 - 1.0) * 100.0
        if ma60 is not None and prior_ma60 not in {None, 0.0} else None
    )
    ma250 = _number(close.tail(250).mean()) if len(close) >= 250 else None
    if not (
        percentile is not None and percentile <= .35
        and ma20 is not None and current >= ma20
        and ma20_slope is not None and ma20_slope >= -.2
        and ma60 is not None and current >= ma60
        and ma60_slope is not None and ma60_slope >= -.2
        and not (
            ma250 is not None and current < ma250 * .82 and ma20_slope < 0
        )
    ):
        return False
    if len(close) >= 6:
        base = _number(close.iloc[-6])
        if base and (current / base - 1.0) * 100.0 > max_5d_return_pct:
            return False
    if len(close) >= 11:
        base = _number(close.iloc[-11])
        if base and (current / base - 1.0) * 100.0 > max_10d_return_pct:
            return False
    amount = pd.to_numeric(history.get("amount"), errors="coerce")
    avg_amount = _number(amount.tail(20).mean()) if amount is not None else None
    if avg_amount is None or avg_amount < max(0.0, float(minimum_turnover)):
        return False

    raw = history[list(HISTORY_PRICE_COLUMNS)].copy()
    for column in ("open", "high", "low", "close"):
        raw[column] = pd.to_numeric(
            history[f"raw_{column}"], errors="coerce",
        )
    observation_date = history.iloc[-1]["date"]
    adjusted_daily = history_snapshot(history, as_of=observation_date)
    raw_daily = history_snapshot(raw, as_of=observation_date)
    state = price_volume_state({
        "return_1d_pct": adjusted_daily.get("return_1d_pct"),
        "gap_open_pct": adjusted_daily.get("gap_open_pct"),
        "volume_ratio_20": raw_daily.get("volume_ratio_20"),
        "amount_ratio_20": raw_daily.get("amount_ratio_20"),
        "close_location": raw_daily.get("close_location"),
    }).get("price_volume_state")
    return state not in {"DISTRIBUTION", "CAPITULATION_RISK"}


def _cached_strict_plan_mode(
    *, setup_history: pd.DataFrame, setup_index: int,
    adjustment_ratio: float, max_chase_atr_multiple: float,
    volatility_multiplier: float,
    cache: dict[tuple[int, float, float, float], str] | None,
    history_is_prepared: bool,
) -> str:
    """Reuse a pure point-in-time plan decision within one stock history."""

    key = (
        int(setup_index), float(adjustment_ratio),
        float(max_chase_atr_multiple), float(volatility_multiplier),
    )
    if cache is not None and key in cache:
        return cache[key]
    mode = _strict_point_in_time_plan_mode(
        setup_history=setup_history,
        adjustment_ratio=adjustment_ratio,
        max_chase_atr_multiple=max_chase_atr_multiple,
        volatility_multiplier=volatility_multiplier,
        history_is_prepared=history_is_prepared,
    )
    if cache is not None:
        cache[key] = mode
    return mode


def _cached_observable_setup_gate(
    *, frame: pd.DataFrame, index: int, minimum_history_rows: int,
    minimum_turnover: float, max_5d_return_pct: float,
    max_10d_return_pct: float,
    cache: dict[tuple[int, int, float, float, float], bool] | None,
) -> bool:
    """Reuse an OHLCV-only gate decision within one stock history."""

    key = (
        int(index), int(minimum_history_rows), float(minimum_turnover),
        float(max_5d_return_pct), float(max_10d_return_pct),
    )
    if cache is not None and key in cache:
        return cache[key]
    passed = _observable_setup_gates_pass(
        frame, index=index,
        minimum_history_rows=minimum_history_rows,
        minimum_turnover=minimum_turnover,
        max_5d_return_pct=max_5d_return_pct,
        max_10d_return_pct=max_10d_return_pct,
    )
    if cache is not None:
        cache[key] = passed
    return passed


def _triggered_entry(
    *, frame: pd.DataFrame, setup_index: int, entry_mode: str,
    breakout_volume_ratio: float, max_chase_atr_multiple: float,
    volatility_multiplier: float, trigger_window_days: int = 10,
    minimum_history_rows: int = 255, minimum_turnover: float = 0.0,
    max_5d_return_pct: float = math.inf,
    max_10d_return_pct: float = math.inf,
    enforce_strict_setup_gates: bool = False,
    strict_mode_cache: dict[tuple[int, float, float, float], str] | None = None,
    observable_gate_cache: (
        dict[tuple[int, int, float, float, float], bool] | None
    ) = None,
    frame_is_prepared: bool = False,
) -> tuple[int, float, float, float] | None:
    """Return entry/fill/stop/invalidation after the raw-tick live plan triggers."""
    setup_history = frame.iloc[: setup_index + 1]
    current = _number(setup_history.iloc[-1].get("close"))
    atr14 = _atr_at(setup_history)
    adjustment_ratio = _setup_adjustment_ratio(frame, setup_index)
    if (
        current is None or current <= 0 or atr14 is None
        or adjustment_ratio is None
    ):
        return None
    if enforce_strict_setup_gates:
        if _cached_strict_plan_mode(
            setup_history=setup_history,
            setup_index=setup_index,
            adjustment_ratio=adjustment_ratio,
            max_chase_atr_multiple=max_chase_atr_multiple,
            volatility_multiplier=volatility_multiplier,
            cache=strict_mode_cache,
            history_is_prepared=frame_is_prepared,
        ) != entry_mode:
            return None
        if not _cached_observable_setup_gate(
            frame=frame, index=setup_index,
            minimum_history_rows=minimum_history_rows,
            minimum_turnover=minimum_turnover,
            max_5d_return_pct=max_5d_return_pct,
            max_10d_return_pct=max_10d_return_pct,
            cache=observable_gate_cache,
        ):
            return None
    adjusted_tick = .01 / adjustment_ratio
    end = min(len(frame), setup_index + 1 + max(1, int(trigger_window_days)))
    if entry_mode == "pullback":
        support = _support_at(setup_history, atr14, current)
        if support is None:
            return None
        raw_entry_low = support - .30 * atr14
        raw_entry_high = min(current, support + .20 * atr14)
        raw_stop = min(raw_entry_low - adjusted_tick, support - .75 * atr14)
        raw_invalidation = min(raw_stop, support - 1.05 * atr14)
        entry_low_raw = raw_tick_round(raw_entry_low * adjustment_ratio)
        entry_high_raw = raw_tick_round(raw_entry_high * adjustment_ratio)
        stop_raw = raw_tick_round(raw_stop * adjustment_ratio)
        invalidation_raw = raw_tick_round(raw_invalidation * adjustment_ratio)
        for entry_index in range(setup_index + 1, end):
            if not _price_mapping_regime_stable(
                frame, start_index=setup_index, end_index=entry_index,
            ) or (enforce_strict_setup_gates and not _session_window_contiguous(
                frame, start_index=setup_index, end_index=entry_index,
            )):
                return None
            row = frame.iloc[entry_index]
            opening = _number(row.get("raw_open"))
            low = _number(row.get("raw_low"))
            high = _number(row.get("raw_high"))
            closing = _number(row.get("raw_close"))
            if opening is None or low is None or high is None or closing is None:
                continue
            # A gap below the planned band cancels the unfilled order. Once the
            # session trades through the band, however, a later same-day stop
            # is a real adverse outcome and must remain in the sample. Daily
            # OHLC cannot prove that the stop happened before the fill.
            if opening < entry_low_raw:
                return None
            entry_observed = bool(
                opening <= entry_high_raw
                or (low <= entry_high_raw and high >= entry_low_raw)
            )
            entry_ratio = _setup_adjustment_ratio(frame, entry_index)
            if entry_ratio is None:
                return None
            if entry_observed and is_one_price_bar(
                opening=opening, high=high, low=low, close=closing,
            ):
                return None
            if enforce_strict_setup_gates and not entry_observed:
                current_history = frame.iloc[: entry_index + 1]
                if _cached_strict_plan_mode(
                    setup_history=current_history,
                    setup_index=entry_index,
                    adjustment_ratio=entry_ratio,
                    max_chase_atr_multiple=max_chase_atr_multiple,
                    volatility_multiplier=volatility_multiplier,
                    cache=strict_mode_cache,
                    history_is_prepared=frame_is_prepared,
                ) != entry_mode:
                    return None
                if not _cached_observable_setup_gate(
                    frame=frame, index=entry_index,
                    minimum_history_rows=minimum_history_rows,
                    minimum_turnover=minimum_turnover,
                    max_5d_return_pct=max_5d_return_pct,
                    max_10d_return_pct=max_10d_return_pct,
                    cache=observable_gate_cache,
                ):
                    return None
            if opening <= entry_high_raw:
                return (
                    entry_index, opening / entry_ratio,
                    stop_raw / entry_ratio, invalidation_raw / entry_ratio,
                )
            if low <= entry_high_raw and high >= entry_low_raw:
                return (
                    entry_index, entry_high_raw / entry_ratio,
                    stop_raw / entry_ratio, invalidation_raw / entry_ratio,
                )
        return None
    if entry_mode != "breakout":
        raise ValueError(f"unsupported entry_mode: {entry_mode}")
    recent_high = _number(pd.to_numeric(setup_history.tail(20)["high"], errors="coerce").max())
    avg_volume_20 = _number(pd.to_numeric(setup_history.tail(20)["volume"], errors="coerce").mean())
    if recent_high is None or avg_volume_20 is None:
        return None
    raw_trigger = recent_high + .10 * atr14
    raw_confirmation = raw_trigger + .20 * atr14
    raw_max_chase = raw_confirmation + max_chase_atr_multiple * atr14
    raw_stop = raw_trigger - max(
        1.20 * atr14 * volatility_multiplier, raw_trigger * .025,
    )
    raw_invalidation = min(raw_stop, recent_high - .30 * atr14)
    trigger_raw = raw_tick_round(raw_trigger * adjustment_ratio)
    max_chase_raw = raw_tick_round(raw_max_chase * adjustment_ratio)
    stop_raw = raw_tick_round(raw_stop * adjustment_ratio)
    invalidation_raw = raw_tick_round(raw_invalidation * adjustment_ratio)
    required_volume = round(avg_volume_20 * breakout_volume_ratio, 0)
    # Full-day volume is known only after the close. Confirm on the close, then
    # enter at the following open; never use a completed day's volume to claim
    # an earlier intraday fill at the trigger price.
    last_confirmation_index = min(len(frame) - 2, setup_index + max(1, int(trigger_window_days)))
    for confirmation_index in range(setup_index + 1, last_confirmation_index + 1):
        if not _price_mapping_regime_stable(
            frame, start_index=setup_index, end_index=confirmation_index,
        ) or (enforce_strict_setup_gates and not _session_window_contiguous(
            frame, start_index=setup_index, end_index=confirmation_index,
        )):
            return None
        row = frame.iloc[confirmation_index]
        confirmation_ratio = _setup_adjustment_ratio(frame, confirmation_index)
        if confirmation_ratio is None:
            return None
        if enforce_strict_setup_gates and (
            _cached_strict_plan_mode(
                setup_history=frame.iloc[: confirmation_index + 1],
                setup_index=confirmation_index,
                adjustment_ratio=confirmation_ratio,
                max_chase_atr_multiple=max_chase_atr_multiple,
                volatility_multiplier=volatility_multiplier,
                cache=strict_mode_cache,
                history_is_prepared=frame_is_prepared,
            ) != entry_mode or not _cached_observable_setup_gate(
                frame=frame, index=confirmation_index,
                minimum_history_rows=minimum_history_rows,
                minimum_turnover=minimum_turnover,
                max_5d_return_pct=max_5d_return_pct,
                max_10d_return_pct=max_10d_return_pct,
                cache=observable_gate_cache,
            )
        ):
            return None
        low = _number(row.get("raw_low"))
        close = _number(row.get("raw_close"))
        volume = _number(row.get("volume"))
        # The live frozen plan is cancelled as soon as either protective
        # threshold is breached, even if this same close would otherwise
        # qualify as the breakout confirmation.  A later rebound must not turn
        # an already-invalidated plan into a historical fill.
        if (low is not None and low <= stop_raw) or (
            close is not None and close <= invalidation_raw
        ):
            return None
        if close is None or volume is None:
            continue
        if close < trigger_raw or volume < required_volume:
            continue
        entry_index = confirmation_index + 1
        if not _price_mapping_regime_stable(
            frame, start_index=setup_index, end_index=entry_index,
        ) or (enforce_strict_setup_gates and not _session_window_contiguous(
            frame, start_index=setup_index, end_index=entry_index,
        )):
            return None
        entry_row = frame.iloc[entry_index]
        opening = _number(entry_row.get("raw_open"))
        opening_high = _number(entry_row.get("raw_high"))
        opening_low = _number(entry_row.get("raw_low"))
        opening_close = _number(entry_row.get("raw_close"))
        entry_ratio = _setup_adjustment_ratio(frame, entry_index)
        if (
            opening is None or opening_high is None or opening_low is None
            or opening_close is None or entry_ratio is None
            or opening < trigger_raw or opening > max_chase_raw
        ):
            return None
        if is_one_price_bar(
            opening=opening, high=opening_high, low=opening_low,
            close=opening_close,
        ):
            return None
        return (
            entry_index, opening / entry_ratio,
            stop_raw / entry_ratio, invalidation_raw / entry_ratio,
        )
    return None


def _price_setup_samples(
    *, code: str, stock_name: str, history: pd.DataFrame, as_of: date,
    entry_mode: str = "pullback", breakout_volume_ratio: float = 1.2,
    max_chase_atr_multiple: float = .35, volatility_multiplier: float = 1.0,
    trigger_window_days: int = 10, step_days: int = PROFILE_SAMPLE_SPACING_SESSIONS,
    minimum_history_rows: int = 255, minimum_turnover: float = 0.0,
    max_5d_return_pct: float = math.inf,
    max_10d_return_pct: float = math.inf,
    strict_mode_cache: dict[tuple[int, float, float, float], str] | None = None,
    observable_gate_cache: (
        dict[tuple[int, int, float, float, float], bool] | None
    ) = None,
) -> list[dict[str, Any]]:
    """Replay a setup and count only fills that satisfy its live entry plan."""
    frame = prepare_price_frame(history)
    frame = frame[frame["date"] <= as_of].copy().reset_index(drop=True)
    if len(frame) < max(350, int(minimum_history_rows)) or not {
        "raw_open", "raw_high", "raw_low", "raw_close", "adjustment_ratio",
    }.issubset(frame.columns):
        return []
    frame["session_contiguous_from_previous"] = _exchange_session_continuity(
        frame["date"],
    )
    close = pd.to_numeric(frame["close"], errors="coerce")
    # Compute each exit bar's moving averages from all information available
    # through that bar before slicing the 60-session outcome window.  Computing
    # them inside the sliced window discards pre-entry closes and diverges from
    # the live scanner, especially for the day-45 trend-break guardrail.
    frame["ma20_post"] = close.rolling(20, min_periods=20).mean()
    frame["ma60_post"] = close.rolling(60, min_periods=60).mean()
    ma20 = frame["ma20_post"]
    ma60 = frame["ma60_post"]
    ma120 = close.rolling(120).mean()
    ma250 = close.rolling(250).mean()
    samples: list[dict[str, Any]] = []
    last_entry_index = -10_000
    last_outcome_end_index = -10_000
    # The profile evaluates 60 completed holding bars and then executes the
    # daily exit signal at the following open. Filled entries remain at least
    # 61 sessions apart so neither return nor drawdown windows overlap.
    first_setup_index = max(254, int(minimum_history_rows) - 1)
    for index in range(first_setup_index, len(frame) - PROFILE_RETURN_HORIZON_SESSIONS):
        if index + trigger_window_days - last_entry_index < max(1, int(step_days)):
            continue
        current = _number(close.iloc[index])
        current_ma20 = _number(ma20.iloc[index])
        current_ma60 = _number(ma60.iloc[index])
        current_ma120 = _number(ma120.iloc[index])
        current_ma250 = _number(ma250.iloc[index])
        prior_ma20 = _number(ma20.iloc[index - 5])
        prior_ma60 = _number(ma60.iloc[index - 5])
        if not all(value is not None and value > 0 for value in (current, current_ma20, current_ma60, prior_ma20, prior_ma60)):
            continue
        ma20_slope = (current_ma20 / prior_ma20 - 1.0) * 100.0
        ma60_slope = (current_ma60 / prior_ma60 - 1.0) * 100.0
        historical = close.iloc[max(0, index - 1249) : index + 1].dropna()
        if historical.empty:
            continue
        percentile = float((historical <= current).sum() / len(historical))
        falling_knife = bool(current_ma250 and current < current_ma250 * .82 and ma20_slope < 0)
        medium = current >= current_ma60 and ma60_slope >= -.2
        if percentile > .35 or current < current_ma20 or ma20_slope < -.2 or not medium or falling_knife:
            continue
        strong = bool(
            current_ma120
            and current >= current_ma60
            and current_ma20 >= current_ma60 >= current_ma120
            and ma60_slope > 0
        )
        triggered = _triggered_entry(
            frame=frame, setup_index=index, entry_mode=entry_mode,
            breakout_volume_ratio=breakout_volume_ratio,
            max_chase_atr_multiple=max_chase_atr_multiple,
            volatility_multiplier=volatility_multiplier,
            trigger_window_days=trigger_window_days,
            minimum_history_rows=minimum_history_rows,
            minimum_turnover=minimum_turnover,
            max_5d_return_pct=max_5d_return_pct,
            max_10d_return_pct=max_10d_return_pct,
            enforce_strict_setup_gates=True,
            strict_mode_cache=strict_mode_cache,
            observable_gate_cache=observable_gate_cache,
            frame_is_prepared=True,
        )
        if triggered is None:
            continue
        entry_index, entry_price, stop_loss, logic_invalidation = triggered
        if entry_index - last_entry_index < max(1, int(step_days)):
            continue
        if entry_index <= last_outcome_end_index:
            continue
        signal_date = frame.iloc[index]["date"]
        if len(frame) - entry_index < (
            PROFILE_RETURN_HORIZON_SESSIONS + PROFILE_EXIT_EXECUTION_LAG_SESSIONS
        ):
            samples.append({
                "code": code,
                "as_of_date": frame.iloc[entry_index]["date"],
                "setup_date": signal_date,
                "outcome_end_date": None,
                "entry_mode": entry_mode,
                "entry_price": entry_price,
                "stop_price": stop_loss,
                "logic_invalidation_price": logic_invalidation,
                "exit_reason": "RIGHT_CENSORED_60D",
                "return": None,
                "drawdown": None,
                "outcome_complete": False,
            })
            # No later setup can have a mature, non-overlapping outcome yet.
            return samples
        future_rows = frame.iloc[entry_index:].copy().reset_index(drop=True)
        outcome_60d = simulate_daily_signal_balanced_v7_exit(
            entry_price=entry_price,
            trend_confirmation_level="STRONG" if strong else "MEDIUM",
            future_rows=future_rows,
            stop_loss=stop_loss,
            logic_invalidation_price=logic_invalidation,
        )
        net_return = _number(outcome_60d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d"))
        drawdown = _number(outcome_60d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_max_drawdown_60d"))
        outcome_end_date = _parse_date(
            outcome_60d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_date_60d"),
        )
        sample = {
            "code": code, "as_of_date": frame.iloc[entry_index]["date"], "setup_date": signal_date,
            "outcome_end_date": outcome_end_date,
            "entry_mode": entry_mode, "entry_price": entry_price,
            "stop_price": stop_loss,
            "logic_invalidation_price": logic_invalidation,
            "exit_reason": outcome_60d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d"),
            "return": net_return, "drawdown": drawdown,
        }
        if net_return is None or drawdown is None or outcome_end_date is None:
            sample["outcome_complete"] = False
            samples.append(sample)
            # The reference position is still unresolved at the data cutoff;
            # later setups for this stock/mode would overlap an open position.
            return samples
        matching_indices = frame.index[frame["date"] == outcome_end_date].tolist()
        if not matching_indices:
            sample.update({
                "outcome_complete": False,
                "outcome_end_date": None,
                "return": None,
                "drawdown": None,
                "exit_reason": "OUTCOME_EXECUTION_DATE_UNMAPPED",
            })
            samples.append(sample)
            return samples
        outcome_end_index = int(matching_indices[-1])
        mapping_stable = _price_mapping_regime_stable(
            frame, start_index=entry_index, end_index=outcome_end_index,
        )
        session_contiguous = _session_window_contiguous(
            frame, start_index=entry_index, end_index=outcome_end_index,
        )
        if not mapping_stable or not session_contiguous:
            # Production sends a held reference position to corporate-action
            # review.  Do not turn the later qfq path into a validated exit.
            sample.update({
                "outcome_complete": False,
                "outcome_end_date": None,
                "return": None,
                "drawdown": None,
                "exit_reason": (
                    "CORPORATE_ACTION_REVIEW" if not mapping_stable
                    else "RUN_GAP_POSITION_REVIEW"
                ),
            })
            samples.append(sample)
            return samples
        sample["outcome_complete"] = True
        samples.append(sample)
        last_entry_index = entry_index
        last_outcome_end_index = outcome_end_index
    return samples


def _normalize_price_history(
    frame: pd.DataFrame, *, as_of: date, columns: tuple[str, ...] = HISTORY_PRICE_COLUMNS,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise RuntimeError("empty_history")
    normalized = frame.reset_index(drop=True).copy()
    missing_columns = [column for column in columns if column not in normalized.columns]
    if missing_columns:
        raise RuntimeError(f"missing_columns:{','.join(missing_columns)}")
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.date
    for column in columns[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = (
        normalized[list(columns)]
        .dropna(subset=["date", "open", "high", "low", "close"])
        .loc[lambda rows: rows["date"] <= as_of]
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )
    if len(normalized) < HISTORY_CACHE_MIN_ROWS:
        raise RuntimeError(f"insufficient_history:{len(normalized)}")
    return normalized


def _normalize_adjusted_history(frame: pd.DataFrame, *, as_of: date) -> pd.DataFrame:
    normalized = _normalize_price_history(
        frame, as_of=as_of, columns=HISTORY_CACHE_COLUMNS,
    )
    for column in ("raw_open", "raw_high", "raw_low", "raw_close"):
        if normalized[column].isna().any() or (normalized[column] <= 0).any():
            raise RuntimeError(f"invalid_{column}_mapping")
    if (
        normalized["adjustment_ratio"].isna().any()
        or (normalized["adjustment_ratio"] <= 0).any()
    ):
        raise RuntimeError("invalid_adjustment_ratio_mapping")
    return normalized


def _combine_adjusted_and_raw_history(
    adjusted: pd.DataFrame, raw: pd.DataFrame, *, as_of: date,
    factor: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach exact-date raw closes to a qfq history for tick-safe plans."""

    qfq = _normalize_price_history(adjusted, as_of=as_of)
    unadjusted = _normalize_price_history(raw, as_of=as_of)
    combined = qfq.merge(
        unadjusted[["date", "open", "high", "low", "close"]].rename(columns={
            "open": "raw_open", "high": "raw_high",
            "low": "raw_low", "close": "raw_close",
        }),
        on="date", how="inner", validate="one_to_one",
    )
    if factor is not None and not factor.empty:
        factors = factor.reset_index(drop=True).copy()
        if "date" not in factors.columns or "qfq_factor" not in factors.columns:
            raise RuntimeError("qfq_factor_columns_missing")
        factors["date"] = pd.to_datetime(factors["date"], errors="coerce").dt.date
        factors["qfq_factor"] = pd.to_numeric(
            factors["qfq_factor"], errors="coerce",
        )
        factors = (
            factors.dropna(subset=["date", "qfq_factor"])
            .loc[lambda rows: rows["qfq_factor"] > 0]
            .sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
        )
        combined["mapping_date"] = pd.to_datetime(combined["date"], errors="coerce")
        factors["mapping_date"] = pd.to_datetime(factors["date"], errors="coerce")
        combined = pd.merge_asof(
            combined.sort_values("mapping_date"),
            factors[["mapping_date", "qfq_factor"]].sort_values("mapping_date"),
            on="mapping_date", direction="backward",
        ).drop(columns=["mapping_date"])
        combined["adjustment_ratio"] = combined["qfq_factor"]
        combined = combined.drop(columns=["qfq_factor"])
    else:
        combined["adjustment_ratio"] = (
            combined["raw_close"]
            / pd.to_numeric(combined["close"], errors="coerce").replace(0, pd.NA)
        )
    return _normalize_adjusted_history(combined, as_of=as_of)


def _adjusted_history_from_raw_and_factor(
    raw: pd.DataFrame, factor: pd.DataFrame, *, as_of: date,
) -> pd.DataFrame:
    """Reproduce Sina qfq without its destructive two-decimal qfq rounding."""

    combined = _combine_adjusted_and_raw_history(
        raw, raw, factor=factor, as_of=as_of,
    )
    for column in ("open", "high", "low", "close"):
        combined[column] = combined[f"raw_{column}"] / combined["adjustment_ratio"]
    return _normalize_adjusted_history(combined, as_of=as_of)


def _history_cache_paths(cache_dir: Path, code: str) -> tuple[Path, Path]:
    return cache_dir / f"{code}.csv", cache_dir / f"{code}.metadata.json"


def _write_history_cache(
    *, cache_dir: Path, code: str, frame: pd.DataFrame, source: str, as_of: date,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path, metadata_path = _history_cache_paths(cache_dir, code)
    csv_temporary = csv_path.with_suffix(".csv.tmp")
    metadata_temporary = metadata_path.with_suffix(".json.tmp")
    frame.to_csv(csv_temporary, index=False)
    digest = hashlib.sha256(csv_temporary.read_bytes()).hexdigest()
    metadata = {
        "schema_version": HISTORY_CACHE_SCHEMA_VERSION,
        "code": code,
        "adjustment": "qfq_with_exact_raw_close",
        "source": source,
        "requested_as_of": as_of.isoformat(),
        "data_start_date": frame.iloc[0]["date"].isoformat(),
        "data_end_date": frame.iloc[-1]["date"].isoformat(),
        "row_count": len(frame),
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "csv_sha256": digest,
    }
    metadata_temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    csv_temporary.replace(csv_path)
    metadata_temporary.replace(metadata_path)


def _read_history_cache(
    *, cache_dir: Path, code: str, as_of: date, max_age_days: int,
) -> tuple[pd.DataFrame | None, str]:
    csv_path, metadata_path = _history_cache_paths(cache_dir, code)
    if not csv_path.is_file() or not metadata_path.is_file():
        return None, "missing"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, Mapping):
            raise RuntimeError("invalid_metadata")
        if int(metadata.get("schema_version") or 0) != HISTORY_CACHE_SCHEMA_VERSION:
            raise RuntimeError("schema_mismatch")
        if (
            _normalize_code(metadata.get("code")) != code
            or metadata.get("adjustment") != "qfq_with_exact_raw_close"
        ):
            raise RuntimeError("identity_mismatch")
        if str(metadata.get("requested_as_of") or "") != as_of.isoformat():
            raise RuntimeError("requested_as_of_mismatch")
        if str(metadata.get("data_end_date") or "") != as_of.isoformat():
            raise RuntimeError("data_end_date_mismatch")
        cached_at = datetime.fromisoformat(str(metadata.get("cached_at") or "").replace("Z", "+00:00"))
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - cached_at.astimezone(timezone.utc)
        if age < timedelta(minutes=-5) or age > timedelta(days=max(0, int(max_age_days))):
            raise RuntimeError("stale")
        payload = csv_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != str(metadata.get("csv_sha256") or ""):
            raise RuntimeError("checksum_mismatch")
        frame = _normalize_adjusted_history(pd.read_csv(csv_path), as_of=as_of)
        if frame.iloc[-1]["date"] != as_of:
            raise RuntimeError("cached_latest_trade_date_mismatch")
        return frame, "ok"
    except Exception as exc:
        return None, f"{type(exc).__name__}:{exc}"


def fetch_extended_adjusted_histories(
    *, candidates: Iterable[Mapping[str, Any]], as_of: date,
    cache_dir: str | Path | None = None,
    cache_max_age_days: int = HISTORY_CACHE_MAX_AGE_DAYS,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Fetch long qfq plus exact-date raw mapping, with a second provider.

    The daily Tencent feed is intentionally retained for the live price scan,
    but it currently exposes only about 640 sessions. Exit validation needs a
    much longer window to reach its independently-spaced sample requirement.
    """
    import akshare as ak

    candidate_rows = [dict(item) for item in candidates]
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    source_counts: Counter[str] = Counter()
    cache_root = Path(cache_dir) if cache_dir is not None else None
    cache_write_errors: dict[str, str] = {}
    cache_read_errors: dict[str, str] = {}
    cache_fallback_reasons: dict[str, str] = {}
    fresh_fetch_count = 0
    cache_hit_count = 0
    cache_write_count = 0

    def store_fresh_history(code: str, frame: pd.DataFrame, source: str) -> None:
        nonlocal cache_write_count
        if cache_root is None:
            return
        try:
            _write_history_cache(
                cache_dir=cache_root, code=code, frame=frame, source=source, as_of=as_of,
            )
            cache_write_count += 1
        except Exception as exc:
            cache_write_errors[code] = f"{type(exc).__name__}:{exc}"

    cache_statuses: dict[str, str] = {}
    if cache_root is not None:
        for candidate in candidate_rows:
            code = _normalize_code(candidate.get("code"))
            if not code or code in histories:
                continue
            cached_frame, cache_status = _read_history_cache(
                cache_dir=cache_root,
                code=code,
                as_of=as_of,
                max_age_days=cache_max_age_days,
            )
            cache_statuses[code] = cache_status
            if cached_frame is None:
                continue
            histories[code] = cached_frame
            source_counts["validated_cache_qfq_with_raw_mapping"] += 1
            cache_hit_count += 1

    provider_rows = [
        item for item in candidate_rows
        if _normalize_code(item.get("code")) not in histories
    ]
    for candidate in provider_rows:
        code = _normalize_code(candidate.get("code"))
        if not code:
            continue
        exchange = str(candidate.get("exchange") or "").upper()
        prefix = "sh" if exchange == "SSE" or code.startswith(("5", "6", "9")) else "sz"
        try:
            raw_frame = ak.stock_zh_a_daily(
                symbol=f"{prefix}{code}",
                start_date="20000101",
                end_date=as_of.strftime("%Y%m%d"),
                adjust="",
            )
            factor_frame = ak.stock_zh_a_daily(
                symbol=f"{prefix}{code}",
                adjust="qfq-factor",
            )
            frame = _adjusted_history_from_raw_and_factor(
                raw_frame, factor_frame, as_of=as_of,
            )
            if frame.iloc[-1]["date"] != as_of:
                raise RuntimeError("latest_trade_date_mismatch")
            histories[code] = frame
            source_counts["akshare_sina_qfq_with_raw_mapping"] += 1
            fresh_fetch_count += 1
            store_fresh_history(code, frame, "akshare_sina_qfq_with_raw_mapping")
        except Exception as exc:
            errors[code] = f"akshare_sina_qfq_raw:{type(exc).__name__}:{exc}"

    missing = [item for item in provider_rows if _normalize_code(item.get("code")) not in histories]
    if missing:
        import baostock as bs

        try:
            login = bs.login()
        except Exception as exc:
            login = None
            errors["baostock_login"] = f"{type(exc).__name__}:{exc}"
        if login is None:
            pass
        elif str(login.error_code) != "0":
            errors["baostock_login"] = str(login.error_msg)
        else:
            fields = "date,open,high,low,close,volume,amount,tradestatus"

            def query_history(symbol: str, *, adjustflag: str) -> pd.DataFrame:
                result = bs.query_history_k_data_plus(
                    symbol,
                    fields,
                    start_date="2000-01-01",
                    end_date=as_of.isoformat(),
                    frequency="d",
                    adjustflag=adjustflag,
                )
                rows: list[list[str]] = []
                while str(result.error_code) == "0" and result.next():
                    rows.append(result.get_row_data())
                if str(result.error_code) != "0":
                    raise RuntimeError(str(result.error_msg))
                frame = pd.DataFrame(rows, columns=fields.split(","))
                return frame[frame["tradestatus"] == "1"].drop(columns=["tradestatus"])

            for candidate in missing:
                code = _normalize_code(candidate.get("code"))
                exchange = str(candidate.get("exchange") or "").upper()
                prefix = "sh" if exchange == "SSE" or code.startswith(("5", "6", "9")) else "sz"
                try:
                    symbol = f"{prefix}.{code}"
                    adjusted_frame = query_history(symbol, adjustflag="2")
                    raw_frame = query_history(symbol, adjustflag="3")
                    frame = _combine_adjusted_and_raw_history(
                        adjusted_frame, raw_frame, as_of=as_of,
                    )
                    if frame.iloc[-1]["date"] != as_of:
                        raise RuntimeError("latest_trade_date_mismatch")
                    histories[code] = frame
                    errors.pop(code, None)
                    source_counts["baostock_qfq_with_raw_mapping"] += 1
                    fresh_fetch_count += 1
                    store_fresh_history(code, frame, "baostock_qfq_with_raw_mapping")
                except Exception as exc:
                    errors[code] = f"{errors.get(code, '')};baostock_qfq_raw:{type(exc).__name__}:{exc}".strip(";")
            try:
                bs.logout()
            except Exception as exc:
                errors["baostock_logout"] = f"{type(exc).__name__}:{exc}"
    cache_fallback_count = 0
    if cache_root is not None:
        for candidate in candidate_rows:
            code = _normalize_code(candidate.get("code"))
            if not code or code in histories:
                continue
            cache_status = cache_statuses.get(code, "missing")
            cache_read_errors[code] = cache_status
            errors[code] = f"{errors.get(code, '')};validated_cache:{cache_status}".strip(";")
    return histories, {
        "source": "akshare_sina_qfq_raw_mapping_with_baostock_fallback",
        "source_counts": dict(source_counts),
        "requested_count": len(candidate_rows),
        "success_count": len(histories),
        "fresh_fetch_count": fresh_fetch_count,
        "cache_hit_count": cache_hit_count,
        "cache_fallback_count": cache_fallback_count,
        "cache_write_count": cache_write_count,
        "cache_enabled": cache_root is not None,
        "cache_max_age_days": max(0, int(cache_max_age_days)),
        "cache_write_errors": cache_write_errors,
        "cache_read_errors": cache_read_errors,
        "cache_fallback_reasons": cache_fallback_reasons,
        "errors": errors,
    }


def _board_family(value: Any) -> str:
    board = str(value or "").upper()
    if board in {"SSE_MAIN", "SZSE_MAIN"}:
        return "MAIN"
    if board in {"STAR", "CHINEXT"}:
        return "GROWTH"
    return board or "UNKNOWN"


def _history_data_end_date(history: pd.DataFrame, *, as_of: date) -> date | None:
    if history.empty or "date" not in history.columns:
        return None
    values = pd.to_datetime(history["date"], errors="coerce").dt.date
    values = values[values <= as_of].dropna()
    return max(values) if not values.empty else None


def _history_digest(
    history: pd.DataFrame, *, as_of: date, spec: Mapping[str, Any], code: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(f"{PROFILE_RULE_VERSION}|{code}|".encode())
    digest.update(json.dumps(dict(spec), ensure_ascii=False, sort_keys=True, default=str).encode())
    prepared = prepare_price_frame(history)
    columns = HISTORY_CACHE_COLUMNS
    for _, price_row in prepared[prepared["date"] <= as_of].iterrows():
        digest.update(
            ("|".join(str(price_row.get(column, "")) for column in columns) + "\n").encode()
        )
    return f"sha256:{digest.hexdigest()}"


def _sample_statistics(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(samples)
    values = [float(item["return"]) for item in rows if _number(item.get("return")) is not None]
    drawdowns = [float(item["drawdown"]) for item in rows if _number(item.get("drawdown")) is not None]
    complete = len(values) == len(rows) == len(drawdowns) and bool(rows)
    return {
        "count": len(values),
        "avg_return": fmean(values) if values else None,
        "median_return": median(values) if values else None,
        "win_rate": sum(value > 0 for value in values) / len(values) * 100.0 if values else None,
        "avg_drawdown": fmean(drawdowns) if drawdowns else None,
        "complete": complete,
    }


def _trimmed_mean(values: Iterable[float], *, proportion: float = .10) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("trimmed mean requires at least one value")
    trim = int(len(ordered) * max(0.0, min(.4, proportion)))
    selected = ordered[trim : len(ordered) - trim] if trim and len(ordered) > trim * 2 else ordered
    return fmean(selected)


def _cohort_period_samples(
    samples: Iterable[Mapping[str, Any]], *, as_of: date,
) -> list[dict[str, Any]]:
    """Collapse correlated cross-sectional trades into non-overlapping eras."""

    rows: list[dict[str, Any]] = []
    for item in samples:
        sample_date = _parse_date(item.get("as_of_date"))
        outcome_end_date = _parse_date(item.get("outcome_end_date"))
        code = _normalize_code(item.get("code"))
        net_return = _number(item.get("return"))
        drawdown = _number(item.get("drawdown"))
        if (
            item.get("outcome_complete") is False
            or not code or sample_date is None or sample_date > as_of
            or outcome_end_date is None or outcome_end_date < sample_date or outcome_end_date > as_of
            or net_return is None or drawdown is None
        ):
            continue
        rows.append({
            **dict(item), "code": code, "as_of_date": sample_date,
            "outcome_end_date": outcome_end_date,
            "return": net_return, "drawdown": drawdown,
        })
    rows.sort(key=lambda item: (item["as_of_date"], item["code"]))
    periods: list[dict[str, Any]] = []
    position = 0
    while position < len(rows):
        anchor = rows[position]["as_of_date"]
        window_end = (pd.Timestamp(anchor) + pd.offsets.BDay(COHORT_FORMATION_WINDOW_SESSIONS - 1)).date()
        window_rows: list[dict[str, Any]] = []
        cursor = position
        while cursor < len(rows) and rows[cursor]["as_of_date"] <= window_end:
            window_rows.append(rows[cursor])
            cursor += 1
        # One outcome per stock per era prevents a malformed ledger from
        # allowing one ticker to dominate a cross-sectional period.
        by_code: dict[str, dict[str, Any]] = {}
        for item in window_rows:
            by_code.setdefault(item["code"], item)
        members = list(by_code.values())
        if len(members) < MIN_COHORT_CODES_PER_PERIOD:
            while position < len(rows) and rows[position]["as_of_date"] <= anchor:
                position += 1
            continue
        member_dates = [item["as_of_date"] for item in members]
        member_outcome_ends = [item["outcome_end_date"] for item in members]
        member_returns = [float(item["return"]) for item in members]
        member_drawdowns = sorted(float(item["drawdown"]) for item in members)
        period_date = max(member_dates)
        period_outcome_end_date = max(member_outcome_ends)
        periods.append({
            "as_of_date": period_date,
            # The period remains the effective independent observation, but its
            # return is the cross-sectional median rather than a basket mean.
            # Member-level tails are validated separately below.
            "return": median(member_returns),
            # A lower-quartile cross-sectional drawdown is deliberately more
            # conservative than the period average without treating one bad
            # print as if every stock experienced it.
            "drawdown": float(pd.Series(member_drawdowns).quantile(.25)),
            "outcome_end_date": period_outcome_end_date,
            "member_count": len(members),
            "member_codes": sorted(by_code),
            "members": members,
        })
        # Actual observed outcome dates, not weekday offsets, define
        # independence. This remains correct across exchange holidays and
        # stock-specific suspensions.
        while position < len(rows) and rows[position]["as_of_date"] <= period_outcome_end_date:
            position += 1
    return periods


def _cohort_validation(
    samples: Iterable[Mapping[str, Any]], *, as_of: date, cohort_key: str,
    data_end_by_code: Mapping[str, date | None],
    data_version_by_code: Mapping[str, str] | None = None,
    excluded_code: str = "",
) -> dict[str, Any]:
    raw_samples = list(samples)
    replay_quality = _outcome_replay_quality(
        raw_samples, as_of=as_of, require_outcome_end=True,
    )
    invalid_outcome_end_count = 0
    for item in raw_samples:
        sample_date = _parse_date(item.get("as_of_date"))
        if item.get("outcome_complete") is False:
            invalid_outcome_end_count += 1
            continue
        if (
            not _normalize_code(item.get("code")) or sample_date is None or sample_date > as_of
            or _number(item.get("return")) is None or _number(item.get("drawdown")) is None
        ):
            continue
        outcome_end_date = _parse_date(item.get("outcome_end_date"))
        if outcome_end_date is None or outcome_end_date < sample_date or outcome_end_date > as_of:
            invalid_outcome_end_count += 1
    periods = _cohort_period_samples(raw_samples, as_of=as_of)
    cutoff = as_of - timedelta(days=730)
    recent = [item for item in periods if item["as_of_date"] >= cutoff]
    values = [float(item["return"]) for item in periods]
    drawdowns = [float(item["drawdown"]) for item in periods]
    unique_codes = sorted({code for item in periods for code in item["member_codes"]})
    recent_unique_codes = sorted({code for item in recent for code in item["member_codes"]})
    members = [member for period in periods for member in period["members"]]
    member_returns = [float(item["return"]) for item in members]
    member_drawdowns = [float(item["drawdown"]) for item in members]
    member_win_rate = (
        sum(value > 0 for value in member_returns) / len(member_returns) * 100.0
        if member_returns else None
    )
    member_tail_return = (
        float(pd.Series(member_returns).quantile(.10)) if member_returns else None
    )
    member_tail_drawdown = (
        float(pd.Series(member_drawdowns).quantile(.10)) if member_drawdowns else None
    )
    code_period_counts: Counter[str] = Counter(
        code for period in periods for code in set(period["member_codes"])
    )
    max_code_period_share = (
        max(code_period_counts.values()) / len(periods) if periods and code_period_counts else None
    )
    code_concentration_passed = (
        max_code_period_share is not None
        and max_code_period_share <= COHORT_MAX_CODE_PERIOD_SHARE
    )
    outcome_end_complete = invalid_outcome_end_count == 0
    mean_return = fmean(values) if values else None
    return_lcb = None
    if len(values) >= 2 and mean_return is not None:
        return_lcb = mean_return - COHORT_RETURN_LOWER_BOUND_Z * stdev(values) / math.sqrt(len(values))
    positive_rate = sum(value > 0 for value in values) / len(values) * 100.0 if values else None
    avg_drawdown = fmean(drawdowns) if drawdowns else None
    tail_drawdown = float(pd.Series(drawdowns).quantile(.10)) if drawdowns else None
    recent_mean = fmean(float(item["return"]) for item in recent) if recent else None
    independence_passed = (
        len(periods) >= MIN_PROFILE_SAMPLE_COUNT
        and len(unique_codes) >= MIN_COHORT_UNIQUE_CODE_COUNT
        and all(int(item["member_count"]) >= MIN_COHORT_CODES_PER_PERIOD for item in periods)
        and code_concentration_passed
        and replay_quality["replay_quality_passed"]
    )
    recent_stability_passed = (
        len(recent) >= MIN_RECENT_2Y_SAMPLE_COUNT
        and len(recent_unique_codes) >= MIN_COHORT_RECENT_UNIQUE_CODE_COUNT
        and recent_mean is not None
        and recent_mean >= COHORT_MIN_RECENT_MEAN_RETURN_PCT
    )
    performance_passed = (
        mean_return is not None and mean_return >= COHORT_MIN_MEAN_RETURN_PCT
        and return_lcb is not None and return_lcb >= 0.0
        and positive_rate is not None and positive_rate >= COHORT_MIN_POSITIVE_PERIOD_RATE_PCT
        and avg_drawdown is not None and avg_drawdown >= COHORT_MIN_AVG_DRAWDOWN_PCT
        and tail_drawdown is not None and tail_drawdown >= COHORT_MIN_TAIL_DRAWDOWN_PCT
    )
    member_performance_passed = (
        member_win_rate is not None and member_win_rate >= COHORT_MIN_MEMBER_WIN_RATE_PCT
        and member_tail_return is not None
        and member_tail_return >= COHORT_MIN_MEMBER_TAIL_RETURN_PCT
        and member_tail_drawdown is not None
        and member_tail_drawdown >= COHORT_MIN_MEMBER_TAIL_DRAWDOWN_PCT
    )
    status = "FAILED" if replay_quality["hard_veto_outcome_count"] else "PASSED" if (
        independence_passed and recent_stability_passed
        and performance_passed and member_performance_passed
    ) else (
        "DEGRADED" if len(periods) >= MIN_DEGRADED_SAMPLE_COUNT else "NOT_AVAILABLE"
    )
    contributing_ends = [
        data_end_by_code.get(code) for code in unique_codes if data_end_by_code.get(code) is not None
    ]
    data_end = min(contributing_ends) if contributing_ends else None
    digest = hashlib.sha256()
    normalized_excluded_code = _normalize_code(excluded_code)
    digest.update(
        f"{PROFILE_RULE_VERSION}|{cohort_key}|exclude={normalized_excluded_code}|".encode()
    )
    for code in unique_codes:
        digest.update(f"{code}|{(data_version_by_code or {}).get(code, '')}\n".encode())
    for item in sorted(raw_samples, key=lambda row: (_parse_date(row.get("as_of_date")) or date.min, _normalize_code(row.get("code")))):
        digest.update(
            f"{_normalize_code(item.get('code'))}|{item.get('as_of_date')}|{item.get('outcome_end_date')}|{item.get('entry_mode')}|{item.get('return')}|{item.get('drawdown')}|{item.get('outcome_complete')}|{item.get('exit_reason')}\n".encode()
        )
    return {
        "status": status,
        "period_count": len(periods),
        "recent_period_count": len(recent),
        "unique_code_count": len(unique_codes),
        "recent_unique_code_count": len(recent_unique_codes),
        "member_sample_count": sum(int(item["member_count"]) for item in periods),
        "member_win_rate": member_win_rate,
        "member_tail_return": member_tail_return,
        "member_tail_drawdown": member_tail_drawdown,
        "max_code_period_share": max_code_period_share,
        "code_concentration_passed": code_concentration_passed,
        "outcome_end_complete": outcome_end_complete,
        "invalid_outcome_end_count": invalid_outcome_end_count,
        **replay_quality,
        "excluded_target_code": normalized_excluded_code,
        "avg_return": mean_return,
        "return_lower_bound": return_lcb,
        "positive_period_rate": positive_rate,
        "avg_drawdown": avg_drawdown,
        "tail_drawdown": tail_drawdown,
        "recent_avg_return": recent_mean,
        "independence_passed": independence_passed,
        "recent_stability_passed": recent_stability_passed,
        "performance_passed": performance_passed,
        "member_performance_passed": member_performance_passed,
        "data_end_date": data_end,
        "data_version": f"sha256:{digest.hexdigest()}",
    }


def refresh_exit_profiles_from_price_history(
    *,
    output_file: str | Path,
    candidates: Iterable[Mapping[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    as_of: date,
    entry_plan_specs: Mapping[str, Mapping[str, Any]] | None = None,
    validation_candidates: Iterable[Mapping[str, Any]] = (),
    step_days: int = PROFILE_SAMPLE_SPACING_SESSIONS,
) -> tuple[Path, dict[str, Any]]:
    """Refresh candidates with direct or independent cohort exit validation.

    Existing rows for non-candidates are retained for cache continuity. Current
    candidates are always replaced, including NOT_AVAILABLE/FAILED results, so
    an old seed row can never silently qualify today's stock. Cohort fallback
    uses only the explicitly selected reference set, grouped by board risk
    family and entry mode. If a candidate is also a selected reference, its own
    samples are removed before its fallback cohort is evaluated (leave-one-out).
    """
    path = Path(output_file)
    existing: dict[str, dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                code = _normalize_code(row.get("code"))
                if code:
                    existing[code] = dict(row)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    candidate_rows = [dict(item) for item in candidates]
    reference_by_code: dict[str, dict[str, Any]] = {}
    for item in validation_candidates:
        reference = dict(item)
        reference_code = _normalize_code(reference.get("code"))
        if reference_code and reference_code not in reference_by_code:
            reference_by_code[reference_code] = reference
    reference_rows = list(reference_by_code.values())
    entry_plan_specs = entry_plan_specs or {}
    sample_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    data_end_by_code: dict[str, date | None] = {}
    data_version_by_code: dict[str, str] = {}
    row_by_code: dict[str, dict[str, Any]] = {}
    for item in (*candidate_rows, *reference_rows):
        code = _normalize_code(item.get("code"))
        if not code or code in row_by_code:
            continue
        row_by_code[code] = item
        history = histories.get(code, pd.DataFrame())
        spec = dict(entry_plan_specs.get(code) or {})
        data_end_by_code[code] = _history_data_end_date(history, as_of=as_of)
        if history.empty:
            sample_rows[code] = {"pullback": [], "breakout": []}
            continue
        data_version_by_code[code] = _history_digest(
            history, as_of=as_of, spec=spec, code=code,
        )
        # Both historical entry modes inspect the same point-in-time history.
        # These decisions are pure for a fixed spec, so share them across modes
        # and overlapping trigger windows instead of rebuilding long slices.
        strict_mode_cache: dict[tuple[int, float, float, float], str] = {}
        observable_gate_cache: dict[
            tuple[int, int, float, float, float], bool
        ] = {}
        sample_rows[code] = {
            mode: _price_setup_samples(
                code=code,
                stock_name=str(item.get("stock_name") or ""),
                history=history,
                as_of=as_of,
                entry_mode=mode,
                breakout_volume_ratio=float(spec.get("breakout_volume_ratio") or 1.2),
                max_chase_atr_multiple=float(spec.get("max_chase_atr_multiple") or .35),
                volatility_multiplier=float(spec.get("volatility_multiplier") or 1.0),
                trigger_window_days=int(spec.get("trigger_window_days") or 10),
                minimum_history_rows=int(spec.get("minimum_history_rows") or 255),
                minimum_turnover=float(spec.get("minimum_turnover") or 0.0),
                max_5d_return_pct=float(spec.get("max_5d_return_pct") or math.inf),
                max_10d_return_pct=float(spec.get("max_10d_return_pct") or math.inf),
                step_days=step_days,
                strict_mode_cache=strict_mode_cache,
                observable_gate_cache=observable_gate_cache,
            )
            for mode in ("pullback", "breakout")
        }

    cohort_raw_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cohort_reference_codes: dict[str, set[str]] = defaultdict(set)
    for reference in reference_rows:
        code = _normalize_code(reference.get("code"))
        family = _board_family(reference.get("board"))
        for mode in ("pullback", "breakout"):
            key = f"{family}|{mode}"
            cohort_reference_codes[key].add(code)
            cohort_raw_samples[key].extend(sample_rows.get(code, {}).get(mode, []))
    cohort_validations = {
        key: _cohort_validation(
            rows, as_of=as_of, cohort_key=key, data_end_by_code=data_end_by_code,
            data_version_by_code=data_version_by_code,
        )
        for key, rows in sorted(cohort_raw_samples.items())
    }

    refreshed: dict[str, dict[str, Any]] = {}
    leave_one_out_validations: dict[tuple[str, str], dict[str, Any]] = {}
    leave_one_out_candidate_codes: set[str] = set()
    recent_cutoff = as_of - timedelta(days=730)
    for candidate in candidate_rows:
        code = _normalize_code(candidate.get("code"))
        if not code:
            continue
        stock_name = str(candidate.get("stock_name") or "")
        history = histories.get(code, pd.DataFrame())
        spec = dict(entry_plan_specs.get(code) or {})
        selected_mode = str(spec.get("entry_mode") or "pullback").lower()
        if selected_mode not in {"pullback", "breakout"}:
            selected_mode = "pullback"
        mode_samples = sample_rows.get(code, {"pullback": [], "breakout": []})
        samples = mode_samples[selected_mode]
        stock_replay_quality = _outcome_replay_quality(samples)
        incomplete_count = sum(item.get("outcome_complete") is False for item in samples)
        completed_samples = [
            item for item in samples
            if item.get("outcome_complete") is not False
            and _number(item.get("return")) is not None
            and _number(item.get("drawdown")) is not None
        ]
        values = [float(item["return"]) for item in completed_samples]
        drawdowns = [float(item["drawdown"]) for item in completed_samples]
        recent_samples = [
            item for item in completed_samples if item["as_of_date"] >= recent_cutoff
        ]
        recent_values = [float(item["return"]) for item in recent_samples]
        stock_status = _status_with_replay_quality(
            values, drawdowns, stock_replay_quality,
        )
        stock_avg_return = fmean(values) if values else None
        stock_recent_mean = fmean(recent_values) if recent_values else None
        stock_recent_stable = (
            len(recent_values) >= MIN_RECENT_2Y_SAMPLE_COUNT
            and stock_recent_mean is not None
            and stock_recent_mean >= 0.0
        )
        stock_negative_veto_clear = (
            stock_status != "FAILED"
            and not (
                len(values) >= MIN_DEGRADED_SAMPLE_COUNT
                and stock_avg_return is not None
                and stock_avg_return < 0.0
            )
            and not (
                len(recent_values) >= MIN_RECENT_2Y_SAMPLE_COUNT
                and stock_recent_mean is not None
                and stock_recent_mean < 0.0
            )
        )
        direct_eligible = (
            stock_status == "PASSED"
            and len(values) >= MIN_PROFILE_SAMPLE_COUNT
            and stock_recent_stable
            and stock_replay_quality["replay_quality_passed"]
        )
        cohort_key = f"{_board_family(candidate.get('board'))}|{selected_mode}"
        if code in cohort_reference_codes.get(cohort_key, set()):
            leave_one_out_candidate_codes.add(code)
            validation_key = (cohort_key, code)
            if validation_key not in leave_one_out_validations:
                leave_one_out_validations[validation_key] = _cohort_validation(
                    [
                        item for item in cohort_raw_samples.get(cohort_key, [])
                        if _normalize_code(item.get("code")) != code
                    ],
                    as_of=as_of,
                    cohort_key=cohort_key,
                    data_end_by_code=data_end_by_code,
                    data_version_by_code=data_version_by_code,
                    excluded_code=code,
                )
            cohort = leave_one_out_validations[validation_key]
        else:
            cohort = cohort_validations.get(cohort_key, {})
        use_cohort = (
            not direct_eligible
            and stock_negative_veto_clear
            and str(cohort.get("status") or "NOT_AVAILABLE") == "PASSED"
        )
        if direct_eligible:
            validation_scope = "STOCK_SPECIFIC"
            status = "PASSED"
            effective_count = len(values)
            effective_recent_count = len(recent_values)
            effective_avg_return = fmean(values)
            effective_win_rate = sum(value > 0 for value in values) / len(values) * 100.0
            effective_avg_drawdown = fmean(drawdowns)
            effective_data_end = data_end_by_code.get(code)
            effective_data_version = data_version_by_code.get(code, "")
            position_multiplier = 1.0
        elif use_cohort:
            validation_scope = "ENTRY_MODE_COHORT_INDEPENDENT_REFERENCE"
            status = "PASSED"
            effective_count = int(cohort.get("period_count") or 0)
            effective_recent_count = int(cohort.get("recent_period_count") or 0)
            effective_avg_return = _number(cohort.get("avg_return"))
            effective_win_rate = _number(cohort.get("positive_period_rate"))
            effective_avg_drawdown = _number(cohort.get("avg_drawdown"))
            effective_data_end = cohort.get("data_end_date")
            effective_data_version = str(cohort.get("data_version") or "")
            position_multiplier = .5
        else:
            validation_scope = "STOCK_SPECIFIC_INSUFFICIENT"
            status = "DEGRADED" if stock_status == "PASSED" and not stock_recent_stable else stock_status
            effective_count = len(values)
            effective_recent_count = len(recent_values)
            effective_avg_return = fmean(values) if values else None
            effective_win_rate = (
                sum(value > 0 for value in values) / len(values) * 100.0 if values else None
            )
            effective_avg_drawdown = fmean(drawdowns) if drawdowns else None
            effective_data_end = data_end_by_code.get(code)
            effective_data_version = (
                data_version_by_code.get(code, "")
            )
            position_multiplier = 0.0
        mode_stats: dict[str, Any] = {}
        for mode, selected_samples in mode_samples.items():
            mode_replay_quality = _outcome_replay_quality(selected_samples)
            mode_incomplete_count = sum(
                item.get("outcome_complete") is False for item in selected_samples
            )
            completed_mode_samples = [
                item for item in selected_samples
                if item.get("outcome_complete") is not False
                and _number(item.get("return")) is not None
                and _number(item.get("drawdown")) is not None
            ]
            mode_summary = _sample_statistics(completed_mode_samples)
            mode_values = [float(item["return"]) for item in completed_mode_samples]
            mode_drawdowns = [float(item["drawdown"]) for item in completed_mode_samples]
            mode_avg_drawdown = mode_summary["avg_drawdown"]
            mode_stats.update({
                f"{mode}_profile_status": _status_with_replay_quality(
                    mode_values, mode_drawdowns, mode_replay_quality,
                ),
                f"{mode}_signal_count": len(mode_values),
                f"{mode}_incomplete_outcome_count": mode_incomplete_count,
                f"{mode}_avg_net_return_60d": round(float(mode_summary["avg_return"]), 4) if mode_summary["avg_return"] is not None else "",
                f"{mode}_win_rate_60d": round(float(mode_summary["win_rate"]), 4) if mode_summary["win_rate"] is not None else "",
                f"{mode}_avg_drawdown_60d": round(float(mode_avg_drawdown), 4) if mode_avg_drawdown is not None else "",
                # Retain the old column for downstream compatibility; the
                # profile rule/version identifies that its value is a 60d alias.
                f"{mode}_avg_drawdown_250d": round(float(mode_avg_drawdown), 4) if mode_avg_drawdown is not None else "",
                f"{mode}_recent_2y_sample_count": sum(
                    item["as_of_date"] >= recent_cutoff
                    for item in completed_mode_samples
                ),
            })
        stock_summary = _sample_statistics(completed_samples)
        refreshed[code] = {
            "code": code,
            "stock_name": stock_name,
            "exit_profile_entry_mode": selected_mode,
            "balanced_exit_historical_profile": status,
            "signal_count": effective_count,
            "avg_balanced_exit_net_return_60d": round(float(effective_avg_return), 4) if effective_avg_return is not None else "",
            "win_rate_balanced_exit_60d": round(float(effective_win_rate), 4) if effective_win_rate is not None else "",
            "avg_balanced_exit_max_drawdown_60d": round(float(effective_avg_drawdown), 4) if effective_avg_drawdown is not None else "",
            "avg_balanced_exit_max_drawdown_250d": round(float(effective_avg_drawdown), 4) if effective_avg_drawdown is not None else "",
            "source_signal_details": (
                "independent_reference_entry_mode_cohort" if use_cohort
                else "rolling_price_setup_backtest"
            ),
            "profile_data_end_date": effective_data_end.isoformat() if isinstance(effective_data_end, date) else "",
            "profile_rule_version": PROFILE_RULE_VERSION,
            "profile_data_version": effective_data_version,
            "profile_confidence": "HIGH" if effective_count >= HIGH_CONFIDENCE_SAMPLE_COUNT else "MEDIUM" if effective_count >= MIN_PROFILE_SAMPLE_COUNT else "LOW",
            "recent_2y_sample_count": effective_recent_count,
            "profile_validation_scope": validation_scope,
            "profile_position_multiplier": position_multiplier,
            "stock_profile_status": stock_status,
            "stock_signal_count": len(values),
            "stock_incomplete_outcome_count": incomplete_count,
            "stock_outcome_attempt_count": stock_replay_quality["outcome_attempt_count"],
            "stock_replayable_outcome_count": stock_replay_quality["replayable_outcome_count"],
            "stock_replay_excluded_outcome_count": stock_replay_quality["replay_excluded_outcome_count"],
            "stock_hard_veto_outcome_count": stock_replay_quality["hard_veto_outcome_count"],
            "stock_corporate_action_excluded_count": stock_replay_quality["corporate_action_excluded_count"],
            "stock_run_gap_excluded_count": stock_replay_quality["run_gap_excluded_count"],
            "stock_right_censored_count": stock_replay_quality["right_censored_count"],
            "stock_outcome_replay_coverage_ratio": round(
                float(stock_replay_quality["outcome_replay_coverage_ratio"]), 6,
            ),
            "stock_run_gap_outcome_ratio": round(
                float(stock_replay_quality["run_gap_outcome_ratio"]), 6,
            ),
            "stock_replay_quality_passed": bool(
                stock_replay_quality["replay_quality_passed"],
            ),
            "stock_recent_2y_sample_count": len(recent_values),
            "stock_avg_net_return_60d": round(float(stock_summary["avg_return"]), 4) if stock_summary["avg_return"] is not None else "",
            "stock_recent_avg_net_return_60d": round(stock_recent_mean, 4) if stock_recent_mean is not None else "",
            "stock_win_rate_60d": round(float(stock_summary["win_rate"]), 4) if stock_summary["win_rate"] is not None else "",
            "stock_avg_drawdown_60d": round(float(stock_summary["avg_drawdown"]), 4) if stock_summary["avg_drawdown"] is not None else "",
            "stock_recent_stability_passed": stock_recent_stable,
            "cohort_key": cohort_key,
            "cohort_profile_status": cohort.get("status") or "NOT_AVAILABLE",
            "cohort_period_count": cohort.get("period_count") or 0,
            "cohort_recent_2y_period_count": cohort.get("recent_period_count") or 0,
            "cohort_unique_code_count": cohort.get("unique_code_count") or 0,
            "cohort_recent_2y_unique_code_count": cohort.get("recent_unique_code_count") or 0,
            "cohort_member_sample_count": cohort.get("member_sample_count") or 0,
            "cohort_avg_net_return_60d": round(float(cohort["avg_return"]), 4) if cohort.get("avg_return") is not None else "",
            "cohort_return_lower_bound_60d": round(float(cohort["return_lower_bound"]), 4) if cohort.get("return_lower_bound") is not None else "",
            "cohort_positive_period_rate_60d": round(float(cohort["positive_period_rate"]), 4) if cohort.get("positive_period_rate") is not None else "",
            "cohort_avg_drawdown_60d": round(float(cohort["avg_drawdown"]), 4) if cohort.get("avg_drawdown") is not None else "",
            "cohort_tail_drawdown_60d": round(float(cohort["tail_drawdown"]), 4) if cohort.get("tail_drawdown") is not None else "",
            "cohort_member_win_rate_60d": round(float(cohort["member_win_rate"]), 4) if cohort.get("member_win_rate") is not None else "",
            "cohort_member_tail_return_60d": round(float(cohort["member_tail_return"]), 4) if cohort.get("member_tail_return") is not None else "",
            "cohort_member_tail_drawdown_60d": round(float(cohort["member_tail_drawdown"]), 4) if cohort.get("member_tail_drawdown") is not None else "",
            "cohort_max_code_period_share": round(float(cohort["max_code_period_share"]), 4) if cohort.get("max_code_period_share") is not None else "",
            "cohort_code_concentration_passed": bool(cohort.get("code_concentration_passed")),
            "cohort_outcome_end_complete": bool(cohort.get("outcome_end_complete")),
            "cohort_invalid_outcome_end_count": int(cohort.get("invalid_outcome_end_count") or 0),
            "cohort_outcome_attempt_count": int(cohort.get("outcome_attempt_count") or 0),
            "cohort_replayable_outcome_count": int(cohort.get("replayable_outcome_count") or 0),
            "cohort_replay_excluded_outcome_count": int(cohort.get("replay_excluded_outcome_count") or 0),
            "cohort_hard_veto_outcome_count": int(cohort.get("hard_veto_outcome_count") or 0),
            "cohort_corporate_action_excluded_count": int(cohort.get("corporate_action_excluded_count") or 0),
            "cohort_run_gap_excluded_count": int(cohort.get("run_gap_excluded_count") or 0),
            "cohort_right_censored_count": int(cohort.get("right_censored_count") or 0),
            "cohort_outcome_replay_coverage_ratio": round(
                float(cohort.get("outcome_replay_coverage_ratio") or 0.0), 6,
            ),
            "cohort_run_gap_outcome_ratio": round(
                float(cohort.get("run_gap_outcome_ratio") or 0.0), 6,
            ),
            "cohort_replay_quality_passed": bool(cohort.get("replay_quality_passed")),
            "cohort_excluded_target_code": str(cohort.get("excluded_target_code") or ""),
            "cohort_recent_avg_net_return_60d": round(float(cohort["recent_avg_return"]), 4) if cohort.get("recent_avg_return") is not None else "",
            "cohort_independence_passed": bool(cohort.get("independence_passed")),
            "cohort_recent_stability_passed": bool(cohort.get("recent_stability_passed")),
            "stock_negative_veto_clear": stock_negative_veto_clear,
            **mode_stats,
            "generated_at": generated_at,
            "rule": "point-in-time qfq setup geometry mapped through the exact-date raw/qfq factor and rounded on the raw one-fen tick; corporate-action, known run-gap and normal right-censored outcomes are excluded from performance but remain in the replay-coverage denominator (minimum 80%, run-gap maximum 5%); unresolved locked-limit, unmapped execution-date and unknown incomplete outcomes hard-veto validation; pullback and breakout replay their frozen stop plus logic invalidation; breakout confirms on close/full volume and enters next open below max chase; all completed-bar exits obey A-share T+1 and execute at the following session open with gap risk and costs; full-history point-in-time moving averages feed balanced-v7; actual execution dates define 61-session non-overlap; direct validation first; otherwise deterministic reference cohort by board-risk-family and identical entry mode with target-code leave-one-out, period medians, member win/tail risk, code-concentration, breadth, lower-confidence-bound, recent-stability and stock-negative-veto checks; cohort-qualified positions capped at 50%; no future row selects setup, cohort or mode",
        }
    existing.update(refreshed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXIT_PROFILE_COLUMNS)
        writer.writeheader()
        for code in sorted(existing):
            writer.writerow({column: existing[code].get(column, "") for column in EXIT_PROFILE_COLUMNS})
    distribution = Counter(
        str(row.get("balanced_exit_historical_profile") or "NOT_AVAILABLE") for row in refreshed.values()
    )
    entry_mode_distribution = Counter(str(row.get("exit_profile_entry_mode") or "unknown") for row in refreshed.values())
    validation_scope_distribution = Counter(
        str(row.get("profile_validation_scope") or "unknown") for row in refreshed.values()
    )
    serializable_cohorts = {
        key: {
            subkey: (value.isoformat() if isinstance(value, date) else value)
            for subkey, value in details.items()
            if subkey != "data_version" or value
        }
        for key, details in cohort_validations.items()
    }
    return path, {
        "generated": True,
        "method": "hierarchical_trigger_aligned_exit_validation",
        "candidate_count": len(refreshed),
        "validation_reference_count": len(reference_rows),
        "cohort_leave_one_out_candidate_count": len(leave_one_out_candidate_codes),
        "candidate_distribution": dict(distribution),
        "entry_mode_distribution": dict(entry_mode_distribution),
        "validation_scope_distribution": dict(validation_scope_distribution),
        "cohort_validations": serializable_cohorts,
        "pullback_distribution": dict(Counter(str(row.get("pullback_profile_status")) for row in refreshed.values())),
        "breakout_distribution": dict(Counter(str(row.get("breakout_profile_status")) for row in refreshed.values())),
        "strict_metadata_eligible_count": sum(
            row["balanced_exit_historical_profile"] == "PASSED"
            and int(row["signal_count"]) >= MIN_PROFILE_SAMPLE_COUNT
            and int(row["recent_2y_sample_count"]) >= MIN_RECENT_2Y_SAMPLE_COUNT
            and row["profile_confidence"] in {"MEDIUM", "HIGH"}
            for row in refreshed.values()
        ),
        "sample_spacing_sessions": step_days,
        "minimum_profile_sample_count": MIN_PROFILE_SAMPLE_COUNT,
        "minimum_recent_2y_sample_count": MIN_RECENT_2Y_SAMPLE_COUNT,
        "minimum_cohort_codes_per_period": MIN_COHORT_CODES_PER_PERIOD,
        "minimum_cohort_unique_code_count": MIN_COHORT_UNIQUE_CODE_COUNT,
        "minimum_cohort_recent_unique_code_count": MIN_COHORT_RECENT_UNIQUE_CODE_COUNT,
        "cohort_formation_window_sessions": COHORT_FORMATION_WINDOW_SESSIONS,
        "minimum_cohort_member_win_rate_pct": COHORT_MIN_MEMBER_WIN_RATE_PCT,
        "minimum_cohort_member_tail_return_pct": COHORT_MIN_MEMBER_TAIL_RETURN_PCT,
        "minimum_cohort_member_tail_drawdown_pct": COHORT_MIN_MEMBER_TAIL_DRAWDOWN_PCT,
        "maximum_cohort_code_period_share": COHORT_MAX_CODE_PERIOD_SHARE,
        "minimum_outcome_replay_coverage_ratio": MIN_OUTCOME_REPLAY_COVERAGE_RATIO,
        "maximum_run_gap_outcome_ratio": MAX_RUN_GAP_OUTCOME_RATIO,
        "primary_return_horizon_sessions": PROFILE_RETURN_HORIZON_SESSIONS,
        "exit_execution_lag_sessions": PROFILE_EXIT_EXECUTION_LAG_SESSIONS,
        "exit_execution_timing": "NEXT_TRADE_SESSION_OPEN",
        "price_plan_basis": "QFQ_GEOMETRY_EXACT_DATE_RAW_FACTOR_ONE_FEN_TICK",
        "corporate_action_window_policy": "EXCLUDE_WITH_REPLAY_COVERAGE_DENOMINATOR",
        "trigger_window_sessions": 10,
        "profile_rule_version": PROFILE_RULE_VERSION,
    }


def generate_exit_profile_from_reports(
    *,
    output_file: str | Path,
    source_dirs: Iterable[str | Path] = ("reports",),
    max_files: int = 3,
    seed_file: str | Path | None = "data/opportunity_snapshots/exit_profile_seed.csv",
) -> tuple[Path, dict[str, Any]]:
    """Generate a per-stock exit profile from existing historical signal files.

    This only aggregates already-produced historical walk-forward rows. It does
    not rerun backtests, optimize parameters, or inspect current opportunity
    signals.
    """

    files = _candidate_signal_files(source_dirs)[: max(0, int(max_files))]
    by_code: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    sources_by_code: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for path in files:
        try:
            data_version = _file_version(path)
            with path.open(encoding="utf-8") as file:
                reader = csv.DictReader(file)
                fields = set(reader.fieldnames or [])
                return_column = "balanced_hybrid_60d_exit_exit_adjusted_net_return_60d"
                drawdown_column = "balanced_hybrid_60d_exit_exit_adjusted_max_drawdown_250d"
                if return_column not in fields:
                    return_column = "exit_adjusted_net_return_60d"
                if drawdown_column not in fields:
                    drawdown_column = "exit_adjusted_max_drawdown_250d"
                for row_index, row in enumerate(reader, 1):
                    code = _normalize_code(row.get("code"))
                    if not code:
                        continue
                    value = _number(row.get(return_column))
                    if value is None:
                        continue
                    sample_date = _parse_date(row.get("as_of_date"))
                    # The same report can be copied into multiple run folders.
                    # A stock/date is one historical observation, never one per
                    # file copy. Undated legacy rows remain file-local and can
                    # never satisfy the current strict v4 rule version.
                    sample_key = sample_date.isoformat() if sample_date else f"{path}:{row_index}"
                    if sample_key in by_code[code]:
                        continue
                    by_code[code][sample_key] = {
                        "stock_name": row.get("stock_name") or "",
                        "return": value,
                        "drawdown": _number(row.get(drawdown_column)),
                        "as_of_date": sample_date,
                    }
                    sources_by_code[code].add((str(path), data_version))
        except OSError:
            continue

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for code, sample_map in sorted(by_code.items()):
        samples = list(sample_map.values())
        values = [float(item["return"]) for item in samples if item.get("return") is not None]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        sample_dates = [item["as_of_date"] for item in samples if item.get("as_of_date") is not None]
        profile_data_end_date = max(sample_dates) if sample_dates else None
        recent_cutoff = profile_data_end_date - timedelta(days=730) if profile_data_end_date else None
        recent_2y_sample_count = (
            sum(1 for item in samples if item.get("as_of_date") and item["as_of_date"] >= recent_cutoff)
            if recent_cutoff else 0
        )
        status = _report_status_for(values, drawdowns)
        profile_confidence = "HIGH" if len(values) >= 100 else "MEDIUM" if len(values) >= 30 else "LOW"
        data_digest = hashlib.sha256()
        for source_path, source_version in sorted(sources_by_code.get(code, set())):
            data_digest.update(f"{source_path}|{source_version}\n".encode())
        for sample_key, item in sorted(sample_map.items()):
            data_digest.update(
                f"{sample_key}|{item.get('return')}|{item.get('drawdown')}\n".encode()
            )
        rows.append(
            {
                "code": code,
                "stock_name": next((item.get("stock_name") for item in samples if item.get("stock_name")), ""),
                "balanced_exit_historical_profile": status,
                "signal_count": len(values),
                "avg_balanced_exit_net_return_60d": round(sum(values) / len(values), 4) if values else "",
                "win_rate_balanced_exit_60d": round(sum(1 for value in values if value > 0) / len(values) * 100.0, 4) if values else "",
                "avg_balanced_exit_max_drawdown_250d": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else "",
                "source_signal_details": ";".join(
                    source_path for source_path, _ in sorted(sources_by_code.get(code, set()))
                ),
                "profile_data_end_date": profile_data_end_date.isoformat() if profile_data_end_date else "",
                "profile_rule_version": REPORT_AGGREGATE_RULE_VERSION,
                "profile_data_version": f"sha256:{data_digest.hexdigest()}",
                "profile_confidence": profile_confidence,
                "recent_2y_sample_count": recent_2y_sample_count,
                "generated_at": generated_at,
                "rule": "report aggregate only (not trigger-aligned strict metadata): signals<10 => NOT_AVAILABLE; signals>=20 and avg_return>=0/win_rate>=45/drawdown>=-12 => PASSED; avg_return>=-4/win_rate>=30/drawdown>=-18 => DEGRADED; else FAILED",
            }
        )

    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and seed_file and Path(seed_file).exists():
        shutil.copyfile(seed_file, path)
        with path.open(encoding="utf-8") as file:
            row_count = max(0, sum(1 for _ in file) - 1)
        return path, {
            "exit_profile_file": str(path),
            "source_signal_detail_files": [str(path) for path in files],
            "seed_file": str(seed_file),
            "generated": False,
            "seed_used": True,
            "profile_rule_version": REPORT_AGGREGATE_RULE_VERSION,
            "row_count": row_count,
            "distribution": load_exit_profile_distribution(path),
        }
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXIT_PROFILE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    distribution = Counter(row["balanced_exit_historical_profile"] for row in rows)
    summary = {
        "exit_profile_file": str(path),
        "source_signal_detail_files": [str(path) for path in files],
        "generated": True,
        "profile_rule_version": REPORT_AGGREGATE_RULE_VERSION,
        "row_count": len(rows),
        "distribution": dict(distribution),
    }
    return path, summary


def load_exit_profile_distribution(path: str | Path | None) -> dict[str, int]:
    if not path or not Path(path).exists():
        return {"NOT_AVAILABLE": 0}
    counts: Counter[str] = Counter()
    with Path(path).open(encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            status = str(row.get("balanced_exit_historical_profile") or row.get("exit_profile_status") or "NOT_AVAILABLE").strip().upper()
            counts[status or "NOT_AVAILABLE"] += 1
    for status in ("PASSED", "DEGRADED", "NOT_AVAILABLE", "FAILED"):
        counts.setdefault(status, 0)
    return dict(counts)
