"""Deterministic balanced-exit profile generation for opportunity discovery."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BALANCED_EXIT_POLICY_NAME, simulate_exit_policy
from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_cycle_bottom.signals import SignalType, StrategySignal


PROFILE_RULE_VERSION = "genge_opportunity_discovery_v3_non_overlapping"
REPORT_AGGREGATE_RULE_VERSION = "genge_opportunity_discovery_v1_report_aggregate"
PROFILE_RETURN_HORIZON_SESSIONS = 60
PROFILE_SAMPLE_SPACING_SESSIONS = PROFILE_RETURN_HORIZON_SESSIONS
MIN_PROFILE_SAMPLE_COUNT = 12
MIN_RECENT_2Y_SAMPLE_COUNT = 3
HIGH_CONFIDENCE_SAMPLE_COUNT = 30
MIN_DEGRADED_SAMPLE_COUNT = 6


EXIT_PROFILE_COLUMNS = [
    "code",
    "stock_name",
    "exit_profile_entry_mode",
    "balanced_exit_historical_profile",
    "signal_count",
    "avg_balanced_exit_net_return_60d",
    "win_rate_balanced_exit_60d",
    "avg_balanced_exit_max_drawdown_250d",
    "source_signal_details",
    "profile_data_end_date",
    "profile_rule_version",
    "profile_data_version",
    "profile_confidence",
    "recent_2y_sample_count",
    "pullback_profile_status",
    "pullback_signal_count",
    "pullback_avg_net_return_60d",
    "pullback_win_rate_60d",
    "pullback_avg_drawdown_250d",
    "pullback_recent_2y_sample_count",
    "breakout_profile_status",
    "breakout_signal_count",
    "breakout_avg_net_return_60d",
    "breakout_win_rate_60d",
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


def _file_version(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _report_data_end_date(path: Path) -> date | None:
    summary_path = path.parent / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    diagnostics = summary.get("diagnostics") if isinstance(summary, Mapping) else None
    return _parse_date((diagnostics or {}).get("end_date")) or _parse_date(summary.get("end_date"))


def _status_for(values: list[float], drawdowns: list[float]) -> str:
    sample_count = len(values)
    if sample_count < MIN_DEGRADED_SAMPLE_COUNT:
        return "NOT_AVAILABLE"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
    if sample_count >= MIN_PROFILE_SAMPLE_COUNT and avg_return >= 0 and win_rate >= 45 and (avg_drawdown is None or avg_drawdown >= -12):
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and (avg_drawdown is None or avg_drawdown >= -18):
        return "DEGRADED"
    return "FAILED"


def _report_status_for(values: list[float], drawdowns: list[float]) -> str:
    """Preserve the legacy report-aggregation policy outside strict live refresh."""
    if len(values) < 10:
        return "NOT_AVAILABLE"
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


def _triggered_entry(
    *, frame: pd.DataFrame, setup_index: int, entry_mode: str,
    breakout_volume_ratio: float, max_chase_atr_multiple: float,
    volatility_multiplier: float, trigger_window_days: int = 10,
) -> tuple[int, float, float] | None:
    """Return (entry row, fill price, stop) only after the live plan triggers."""
    setup_history = frame.iloc[: setup_index + 1]
    current = _number(setup_history.iloc[-1].get("close"))
    atr14 = _atr_at(setup_history)
    if current is None or current <= 0 or atr14 is None:
        return None
    end = min(len(frame), setup_index + 1 + max(1, int(trigger_window_days)))
    if entry_mode == "pullback":
        support = _support_at(setup_history, atr14, current)
        if support is None:
            return None
        entry_low = support - .30 * atr14
        entry_high = min(current, support + .20 * atr14)
        stop = min(entry_low - .01, support - .75 * atr14)
        for entry_index in range(setup_index + 1, end):
            row = frame.iloc[entry_index]
            opening = _number(row.get("open"))
            low = _number(row.get("low"))
            high = _number(row.get("high"))
            if opening is None or low is None or high is None:
                continue
            if low <= stop or opening < entry_low:
                return None
            if opening <= entry_high:
                return entry_index, opening, stop
            if low <= entry_high and high >= entry_low:
                return entry_index, entry_high, stop
        return None
    if entry_mode != "breakout":
        raise ValueError(f"unsupported entry_mode: {entry_mode}")
    recent_high = _number(pd.to_numeric(setup_history.tail(20)["high"], errors="coerce").max())
    avg_volume_20 = _number(pd.to_numeric(setup_history.tail(20)["volume"], errors="coerce").mean())
    if recent_high is None or avg_volume_20 is None:
        return None
    trigger = recent_high + .10 * atr14
    confirmation = trigger + .20 * atr14
    max_chase = confirmation + max_chase_atr_multiple * atr14
    stop = trigger - max(1.20 * atr14 * volatility_multiplier, trigger * .025)
    required_volume = avg_volume_20 * breakout_volume_ratio
    for entry_index in range(setup_index + 1, end):
        row = frame.iloc[entry_index]
        opening = _number(row.get("open"))
        high = _number(row.get("high"))
        volume = _number(row.get("volume"))
        if opening is None or high is None or volume is None:
            continue
        if opening > max_chase:
            return None
        if high >= trigger and volume >= required_volume:
            fill = opening if opening >= trigger else trigger
            if fill <= max_chase:
                return entry_index, fill, stop
    return None


def _price_setup_samples(
    *, code: str, stock_name: str, history: pd.DataFrame, as_of: date,
    entry_mode: str = "pullback", breakout_volume_ratio: float = 1.2,
    max_chase_atr_multiple: float = .35, volatility_multiplier: float = 1.0,
    trigger_window_days: int = 10, step_days: int = PROFILE_SAMPLE_SPACING_SESSIONS,
) -> list[dict[str, Any]]:
    """Replay a setup and count only fills that satisfy its live entry plan."""
    frame = prepare_price_frame(history)
    frame = frame[frame["date"] <= as_of].copy().reset_index(drop=True)
    if len(frame) < 350:
        return []
    close = pd.to_numeric(frame["close"], errors="coerce")
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()
    ma250 = close.rolling(250).mean()
    samples: list[dict[str, Any]] = []
    last_entry_index = -10_000
    # Ninety complete post-entry sessions cover the balanced policy's strong-
    # trend extension. Sixty-session spacing prevents overlapping 60-session
    # return windows from being counted as independent validation samples.
    for index in range(254, len(frame) - 90):
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
        )
        if triggered is None:
            continue
        entry_index, entry_price, stop_loss = triggered
        if entry_index - last_entry_index < max(1, int(step_days)):
            continue
        signal_date = frame.iloc[index]["date"]
        signal = StrategySignal(
            code=code,
            stock_name=stock_name,
            as_of_date=signal_date.isoformat(),
            signal_type=SignalType.CONFIRM_BUY,
            total_score=0.0,
            price_percentile_score=0.0,
            valuation_score=0.0,
            financial_safety_score=0.0,
            trend_stabilization_score=0.0,
            market_environment_score=0.0,
            industry_cycle_score=0.0,
            price_percentile_5y=percentile,
            trend_confirmation_level="STRONG" if strong else "MEDIUM",
            dynamic_stop_loss=round(stop_loss, 4),
            stop_loss=round(stop_loss, 4),
        )
        future_rows = frame.iloc[entry_index : entry_index + 250].copy().reset_index(drop=True)
        outcome_60d = simulate_exit_policy(
            signal=signal,
            entry_price=entry_price,
            future_rows=future_rows.head(60),
            horizon_days=60,
            stop_loss=stop_loss,
            policy_name=BALANCED_EXIT_POLICY_NAME,
        )
        outcome_250d = simulate_exit_policy(
            signal=signal,
            entry_price=entry_price,
            future_rows=future_rows,
            horizon_days=250,
            stop_loss=stop_loss,
            policy_name=BALANCED_EXIT_POLICY_NAME,
        )
        net_return = _number(outcome_60d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d"))
        drawdown = _number(outcome_250d.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_max_drawdown_250d"))
        if net_return is None:
            continue
        samples.append({
            "as_of_date": frame.iloc[entry_index]["date"], "setup_date": signal_date,
            "entry_mode": entry_mode, "entry_price": entry_price,
            "return": net_return, "drawdown": drawdown,
        })
        last_entry_index = entry_index
    return samples


def fetch_extended_adjusted_histories(
    *, candidates: Iterable[Mapping[str, Any]], as_of: date,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Fetch long qfq history for exit validation, with a second provider.

    The daily Tencent feed is intentionally retained for the live price scan,
    but it currently exposes only about 640 sessions. Exit validation needs a
    much longer window to reach its independently-spaced sample requirement.
    """
    import akshare as ak

    candidate_rows = [dict(item) for item in candidates]
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    source_counts: Counter[str] = Counter()
    for candidate in candidate_rows:
        code = _normalize_code(candidate.get("code"))
        if not code:
            continue
        exchange = str(candidate.get("exchange") or "").upper()
        prefix = "sh" if exchange == "SSE" or code.startswith(("5", "6", "9")) else "sz"
        try:
            frame = ak.stock_zh_a_daily(
                symbol=f"{prefix}{code}",
                start_date="20000101",
                end_date=as_of.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if frame is None or frame.empty:
                raise RuntimeError("empty_history")
            frame = frame.reset_index(drop=True)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
            required = ["date", "open", "high", "low", "close", "volume", "amount"]
            for column in required[1:]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame = frame[required].dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
            if len(frame) < 350:
                raise RuntimeError(f"insufficient_history:{len(frame)}")
            histories[code] = frame
            source_counts["akshare_sina_qfq"] += 1
        except Exception as exc:
            errors[code] = f"akshare_sina_qfq:{type(exc).__name__}:{exc}"

    missing = [item for item in candidate_rows if _normalize_code(item.get("code")) not in histories]
    if missing:
        import baostock as bs

        login = bs.login()
        if str(login.error_code) != "0":
            errors["baostock_login"] = str(login.error_msg)
        else:
            fields = "date,open,high,low,close,volume,amount,tradestatus"
            for candidate in missing:
                code = _normalize_code(candidate.get("code"))
                exchange = str(candidate.get("exchange") or "").upper()
                prefix = "sh" if exchange == "SSE" or code.startswith(("5", "6", "9")) else "sz"
                try:
                    result = bs.query_history_k_data_plus(
                        f"{prefix}.{code}",
                        fields,
                        start_date="2000-01-01",
                        end_date=as_of.isoformat(),
                        frequency="d",
                        adjustflag="2",
                    )
                    rows: list[list[str]] = []
                    while str(result.error_code) == "0" and result.next():
                        rows.append(result.get_row_data())
                    if str(result.error_code) != "0":
                        raise RuntimeError(str(result.error_msg))
                    frame = pd.DataFrame(rows, columns=fields.split(","))
                    frame = frame[frame["tradestatus"] == "1"].drop(columns=["tradestatus"])
                    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
                    for column in ("open", "high", "low", "close", "volume", "amount"):
                        frame[column] = pd.to_numeric(frame[column], errors="coerce")
                    frame = frame.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
                    if len(frame) < 350:
                        raise RuntimeError(f"insufficient_history:{len(frame)}")
                    histories[code] = frame
                    errors.pop(code, None)
                    source_counts["baostock_qfq"] += 1
                except Exception as exc:
                    errors[code] = f"{errors.get(code, '')};baostock_qfq:{type(exc).__name__}:{exc}".strip(";")
            bs.logout()
    return histories, {
        "source": "akshare_sina_qfq_with_baostock_fallback",
        "source_counts": dict(source_counts),
        "requested_count": len(candidate_rows),
        "success_count": len(histories),
        "errors": errors,
    }


def refresh_exit_profiles_from_price_history(
    *,
    output_file: str | Path,
    candidates: Iterable[Mapping[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    as_of: date,
    entry_plan_specs: Mapping[str, Mapping[str, Any]] | None = None,
    step_days: int = PROFILE_SAMPLE_SPACING_SESSIONS,
) -> tuple[Path, dict[str, Any]]:
    """Refresh current candidates using point-in-time, setup-conditioned exits.

    Existing rows for non-candidates are retained for cache continuity. Current
    candidates are always replaced, including NOT_AVAILABLE/FAILED results, so
    an old seed row can never silently qualify today's stock.
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
    refreshed: dict[str, dict[str, Any]] = {}
    entry_plan_specs = entry_plan_specs or {}
    for candidate in candidates:
        code = _normalize_code(candidate.get("code"))
        if not code:
            continue
        stock_name = str(candidate.get("stock_name") or "")
        history = histories.get(code, pd.DataFrame())
        spec = dict(entry_plan_specs.get(code) or {})
        selected_mode = str(spec.get("entry_mode") or "pullback").lower()
        if selected_mode not in {"pullback", "breakout"}:
            selected_mode = "pullback"
        mode_samples = {
            mode: _price_setup_samples(
                code=code, stock_name=stock_name, history=history, as_of=as_of,
                entry_mode=mode,
                breakout_volume_ratio=float(spec.get("breakout_volume_ratio") or 1.2),
                max_chase_atr_multiple=float(spec.get("max_chase_atr_multiple") or .35),
                volatility_multiplier=float(spec.get("volatility_multiplier") or 1.0),
                trigger_window_days=int(spec.get("trigger_window_days") or 10),
                step_days=step_days,
            )
            for mode in ("pullback", "breakout")
        }
        samples = mode_samples[selected_mode]
        values = [float(item["return"]) for item in samples]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        recent_cutoff = as_of - timedelta(days=730)
        status = _status_for(values, drawdowns)
        mode_stats: dict[str, Any] = {}
        for mode, selected_samples in mode_samples.items():
            mode_values = [float(item["return"]) for item in selected_samples]
            mode_drawdowns = [
                float(item["drawdown"]) for item in selected_samples if item.get("drawdown") is not None
            ]
            mode_stats.update({
                f"{mode}_profile_status": _status_for(mode_values, mode_drawdowns),
                f"{mode}_signal_count": len(mode_values),
                f"{mode}_avg_net_return_60d": round(sum(mode_values) / len(mode_values), 4) if mode_values else "",
                f"{mode}_win_rate_60d": round(sum(value > 0 for value in mode_values) / len(mode_values) * 100.0, 4) if mode_values else "",
                f"{mode}_avg_drawdown_250d": round(sum(mode_drawdowns) / len(mode_drawdowns), 4) if mode_drawdowns else "",
                f"{mode}_recent_2y_sample_count": sum(
                    item["as_of_date"] >= recent_cutoff for item in selected_samples
                ),
            })
        data_digest = hashlib.sha256()
        prepared = prepare_price_frame(history)
        for _, price_row in prepared[prepared["date"] <= as_of].iterrows():
            data_digest.update(
                f"{price_row.get('date')}|{price_row.get('open')}|{price_row.get('high')}|{price_row.get('low')}|{price_row.get('close')}\n".encode()
            )
        refreshed[code] = {
            "code": code,
            "stock_name": stock_name,
            "exit_profile_entry_mode": selected_mode,
            "balanced_exit_historical_profile": status,
            "signal_count": len(values),
            "avg_balanced_exit_net_return_60d": round(sum(values) / len(values), 4) if values else "",
            "win_rate_balanced_exit_60d": round(sum(value > 0 for value in values) / len(values) * 100.0, 4) if values else "",
            "avg_balanced_exit_max_drawdown_250d": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else "",
            "source_signal_details": "rolling_price_setup_backtest",
            "profile_data_end_date": as_of.isoformat(),
            "profile_rule_version": PROFILE_RULE_VERSION,
            "profile_data_version": f"sha256:{data_digest.hexdigest()}",
            "profile_confidence": "HIGH" if len(values) >= HIGH_CONFIDENCE_SAMPLE_COUNT else "MEDIUM" if len(values) >= MIN_PROFILE_SAMPLE_COUNT else "LOW",
            "recent_2y_sample_count": sum(item["as_of_date"] >= recent_cutoff for item in samples),
            **mode_stats,
            "generated_at": generated_at,
            "rule": "point-in-time technical setup (percentile<=35%, trend>=MEDIUM, no falling knife); separately replay pullback-band and volume-confirmed breakout fills within 10 sessions; select today's predeclared entry mode; non-overlapping 60-session filled-entry spacing; balanced 60d exit; no future row selects setup or mode",
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
    return path, {
        "generated": True,
        "method": "trigger_aligned_rolling_price_setup_backtest",
        "candidate_count": len(refreshed),
        "candidate_distribution": dict(distribution),
        "entry_mode_distribution": dict(entry_mode_distribution),
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
        "primary_return_horizon_sessions": PROFILE_RETURN_HORIZON_SESSIONS,
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
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_by_code: dict[str, str] = {}
    data_version_by_code: dict[str, str] = {}
    data_end_by_code: dict[str, date] = {}
    for path in files:
        try:
            data_version = _file_version(path)
            report_data_end_date = _report_data_end_date(path)
            with path.open(encoding="utf-8") as file:
                reader = csv.DictReader(file)
                fields = set(reader.fieldnames or [])
                return_column = "balanced_hybrid_60d_exit_exit_adjusted_net_return_60d"
                drawdown_column = "balanced_hybrid_60d_exit_exit_adjusted_max_drawdown_250d"
                if return_column not in fields:
                    return_column = "exit_adjusted_net_return_60d"
                if drawdown_column not in fields:
                    drawdown_column = "exit_adjusted_max_drawdown_250d"
                for row in reader:
                    code = _normalize_code(row.get("code"))
                    if not code:
                        continue
                    value = _number(row.get(return_column))
                    if value is None:
                        continue
                    by_code[code].append(
                        {
                            "stock_name": row.get("stock_name") or "",
                            "return": value,
                            "drawdown": _number(row.get(drawdown_column)),
                            "as_of_date": _parse_date(row.get("as_of_date")),
                        }
                    )
                    source_by_code.setdefault(code, str(path))
                    data_version_by_code.setdefault(code, data_version)
                    if report_data_end_date is not None:
                        data_end_by_code.setdefault(code, report_data_end_date)
        except OSError:
            continue

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for code, samples in sorted(by_code.items()):
        values = [float(item["return"]) for item in samples if item.get("return") is not None]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        sample_dates = [item["as_of_date"] for item in samples if item.get("as_of_date") is not None]
        profile_data_end_date = data_end_by_code.get(code) or (max(sample_dates) if sample_dates else None)
        recent_cutoff = profile_data_end_date - timedelta(days=730) if profile_data_end_date else None
        recent_2y_sample_count = (
            sum(1 for item in samples if item.get("as_of_date") and item["as_of_date"] >= recent_cutoff)
            if recent_cutoff else 0
        )
        status = _report_status_for(values, drawdowns)
        profile_confidence = "HIGH" if len(values) >= 100 else "MEDIUM" if len(values) >= 30 else "LOW"
        rows.append(
            {
                "code": code,
                "stock_name": next((item.get("stock_name") for item in samples if item.get("stock_name")), ""),
                "balanced_exit_historical_profile": status,
                "signal_count": len(values),
                "avg_balanced_exit_net_return_60d": round(sum(values) / len(values), 4) if values else "",
                "win_rate_balanced_exit_60d": round(sum(1 for value in values if value > 0) / len(values) * 100.0, 4) if values else "",
                "avg_balanced_exit_max_drawdown_250d": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else "",
                "source_signal_details": source_by_code.get(code, ""),
                "profile_data_end_date": profile_data_end_date.isoformat() if profile_data_end_date else "",
                "profile_rule_version": REPORT_AGGREGATE_RULE_VERSION,
                "profile_data_version": data_version_by_code.get(code, ""),
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
