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


PROFILE_RULE_VERSION = "genge_opportunity_discovery_v1"


EXIT_PROFILE_COLUMNS = [
    "code",
    "stock_name",
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
    if sample_count < 10:
        return "NOT_AVAILABLE"
    avg_return = sum(values) / len(values)
    win_rate = sum(1 for value in values if value > 0) / len(values) * 100.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
    if sample_count >= 20 and avg_return >= 0 and win_rate >= 45 and (avg_drawdown is None or avg_drawdown >= -12):
        return "PASSED"
    if avg_return >= -4 and win_rate >= 30 and (avg_drawdown is None or avg_drawdown >= -18):
        return "DEGRADED"
    return "FAILED"


def _price_setup_samples(
    *, code: str, stock_name: str, history: pd.DataFrame, as_of: date, step_days: int = 5,
) -> list[dict[str, Any]]:
    """Replay the current technical setup without using future rows to select it."""
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
    last_sample_index = -10_000
    # Ninety complete post-entry sessions cover the balanced policy's strong-
    # trend extension. A five-session spacing avoids counting every day in one
    # continuous setup as an independent test.
    for index in range(254, len(frame) - 90):
        if index - last_sample_index < max(1, int(step_days)):
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
        entry_row = frame.iloc[index + 1]
        entry_price = _number(entry_row.get("open")) or _number(entry_row.get("close"))
        if entry_price is None or entry_price <= 0:
            continue
        recent_low = _number(pd.to_numeric(frame.iloc[max(0, index - 19) : index + 1]["low"], errors="coerce").min())
        stop_loss = entry_price * .92
        if recent_low is not None and recent_low > 0:
            stop_loss = max(entry_price * .88, min(entry_price * .97, recent_low * .995))
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
        future_rows = frame.iloc[index + 1 : index + 251].copy().reset_index(drop=True)
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
        samples.append({"as_of_date": signal_date, "return": net_return, "drawdown": drawdown})
        last_sample_index = index
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
    step_days: int = 5,
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
    for candidate in candidates:
        code = _normalize_code(candidate.get("code"))
        if not code:
            continue
        stock_name = str(candidate.get("stock_name") or "")
        history = histories.get(code, pd.DataFrame())
        samples = _price_setup_samples(
            code=code, stock_name=stock_name, history=history, as_of=as_of, step_days=step_days,
        )
        values = [float(item["return"]) for item in samples]
        drawdowns = [float(item["drawdown"]) for item in samples if item.get("drawdown") is not None]
        recent_cutoff = as_of - timedelta(days=730)
        status = _status_for(values, drawdowns)
        data_digest = hashlib.sha256()
        prepared = prepare_price_frame(history)
        for _, price_row in prepared[prepared["date"] <= as_of].iterrows():
            data_digest.update(
                f"{price_row.get('date')}|{price_row.get('open')}|{price_row.get('high')}|{price_row.get('low')}|{price_row.get('close')}\n".encode()
            )
        refreshed[code] = {
            "code": code,
            "stock_name": stock_name,
            "balanced_exit_historical_profile": status,
            "signal_count": len(values),
            "avg_balanced_exit_net_return_60d": round(sum(values) / len(values), 4) if values else "",
            "win_rate_balanced_exit_60d": round(sum(value > 0 for value in values) / len(values) * 100.0, 4) if values else "",
            "avg_balanced_exit_max_drawdown_250d": round(sum(drawdowns) / len(drawdowns), 4) if drawdowns else "",
            "source_signal_details": "rolling_price_setup_backtest",
            "profile_data_end_date": as_of.isoformat(),
            "profile_rule_version": PROFILE_RULE_VERSION,
            "profile_data_version": f"sha256:{data_digest.hexdigest()}",
            "profile_confidence": "HIGH" if len(values) >= 100 else "MEDIUM" if len(values) >= 30 else "LOW",
            "recent_2y_sample_count": sum(item["as_of_date"] >= recent_cutoff for item in samples),
            "generated_at": generated_at,
            "rule": "point-in-time technical setup (percentile<=35%, trend>=MEDIUM, no falling knife), next-open entry, 5-session sample spacing, balanced 60d exit; no future row used to select a setup",
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
    return path, {
        "generated": True,
        "method": "rolling_price_setup_backtest",
        "candidate_count": len(refreshed),
        "candidate_distribution": dict(distribution),
        "strict_metadata_eligible_count": sum(
            row["balanced_exit_historical_profile"] == "PASSED"
            and int(row["signal_count"]) >= 30
            and int(row["recent_2y_sample_count"]) >= 10
            and row["profile_confidence"] in {"MEDIUM", "HIGH"}
            for row in refreshed.values()
        ),
        "sample_spacing_sessions": step_days,
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
        status = _status_for(values, drawdowns)
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
                "profile_rule_version": PROFILE_RULE_VERSION,
                "profile_data_version": data_version_by_code.get(code, ""),
                "profile_confidence": profile_confidence,
                "recent_2y_sample_count": recent_2y_sample_count,
                "generated_at": generated_at,
                "rule": "signals<10 => NOT_AVAILABLE; signals 10-19 max DEGRADED; signals>=20 and avg_return>=0/win_rate>=45/drawdown>=-12 => PASSED; avg_return>=-4/win_rate>=30/drawdown>=-18 => DEGRADED; else FAILED",
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
            "profile_rule_version": PROFILE_RULE_VERSION,
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
        "profile_rule_version": PROFILE_RULE_VERSION,
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
