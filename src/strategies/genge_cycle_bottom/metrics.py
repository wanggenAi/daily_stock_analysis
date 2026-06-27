"""Metrics aggregation for GenGe Cycle Bottom walk-forward backtests."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional

from .backtest import EVAL_WINDOWS


def _finite_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _numbers(rows: Iterable[Dict[str, Any]], field_name: str) -> List[float]:
    values: List[float] = []
    for row in rows:
        number = _finite_number(row.get(field_name))
        if number is not None:
            values.append(number)
    return values


def _ratio_true(rows: Iterable[Dict[str, Any]], field_name: str) -> Optional[float]:
    values = [row.get(field_name) for row in rows if row.get(field_name) is not None]
    if not values:
        return None
    return round(sum(1 for value in values if bool(value)) / len(values) * 100, 4)


def _win_rate(rows: Iterable[Dict[str, Any]], field_name: str) -> Optional[float]:
    values = _numbers(rows, field_name)
    if not values:
        return None
    return round(sum(1 for value in values if value > 0) / len(values) * 100, 4)


def _win_record(rows: Iterable[Dict[str, Any]], field_name: str) -> Dict[str, Optional[float]]:
    values = _numbers(rows, field_name)
    if not values:
        return {"count": 0, "total": 0, "rate_pct": None}
    win_count = sum(1 for value in values if value > 0)
    return {
        "count": win_count,
        "total": len(values),
        "rate_pct": round(win_count / len(values) * 100, 4),
    }


def _avg(values: List[float]) -> Optional[float]:
    return round(mean(values), 4) if values else None


def _median(values: List[float]) -> Optional[float]:
    return round(median(values), 4) if values else None


def _split_flags(rows: Iterable[Dict[str, Any]], field_name: str) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        raw = row.get(field_name) or ""
        if isinstance(raw, (list, tuple, set)):
            parts = raw
        else:
            parts = str(raw).split(";")
        for part in parts:
            name = str(part).strip()
            if name:
                counter[name] += 1
    return dict(counter.most_common())


def _max_consecutive_losses(rows: List[Dict[str, Any]], return_field: str = "future_return_60d") -> int:
    ordered = sorted(rows, key=lambda row: (str(row.get("as_of_date") or ""), str(row.get("code") or "")))
    worst_run = 0
    current_run = 0
    for row in ordered:
        value = _finite_number(row.get(return_field))
        if value is None:
            continue
        if value < 0:
            current_run += 1
            worst_run = max(worst_run, current_run)
        else:
            current_run = 0
    return worst_run


def _signal_snapshot(row: Dict[str, Any], return_field: str) -> Dict[str, Any]:
    return {
        "code": row.get("code"),
        "stock_name": row.get("stock_name"),
        "as_of_date": row.get("as_of_date"),
        "signal_type": row.get("signal_type"),
        "total_score": row.get("total_score"),
        return_field: row.get(return_field),
        "max_drawdown_250d": row.get("max_drawdown_250d"),
        "risk_flags": row.get("risk_flags"),
    }


def _ranked_signals(rows: List[Dict[str, Any]], return_field: str = "future_return_60d") -> tuple[list[dict], list[dict]]:
    available = [row for row in rows if _finite_number(row.get(return_field)) is not None]
    if not available:
        return [], []
    ordered = sorted(available, key=lambda row: float(row[return_field]))
    worst = [_signal_snapshot(row, return_field) for row in ordered[:5]]
    best = [_signal_snapshot(row, return_field) for row in reversed(ordered[-5:])]
    return best, worst


def _best_signal_type(rows: List[Dict[str, Any]]) -> Optional[str]:
    grouped: Dict[str, List[float]] = {}
    for row in rows:
        signal_type = str(row.get("signal_type") or "")
        value = _finite_number(row.get("future_return_60d"))
        if signal_type and value is not None:
            grouped.setdefault(signal_type, []).append(value)
    if not grouped:
        return None
    return max(grouped, key=lambda key: mean(grouped[key]))


def _best_horizon(summary: Dict[str, Any]) -> Optional[str]:
    candidates = {
        f"{days}d": summary.get(f"avg_return_{days}d")
        for days in EVAL_WINDOWS
        if summary.get(f"avg_return_{days}d") is not None
    }
    if not candidates:
        return None
    return max(candidates, key=lambda key: float(candidates[key]))


def compute_summary(
    rows: List[Dict[str, Any]],
    extra_diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate signal rows into the required summary.json contract."""

    summary: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_signals": len(rows),
        "signals_by_type": dict(Counter(str(row.get("signal_type") or "UNKNOWN") for row in rows)),
    }

    for days in EVAL_WINDOWS:
        return_field = f"future_return_{days}d"
        drawdown_field = f"max_drawdown_{days}d"
        returns = _numbers(rows, return_field)
        summary[f"win_rate_{days}d"] = _win_rate(rows, return_field)
        summary[f"avg_return_{days}d"] = _avg(returns)
        summary[f"median_return_{days}d"] = _median(returns)
        summary[f"outperform_benchmark_rate_{days}d"] = _ratio_true(rows, f"outperform_benchmark_{days}d")
        summary[f"avg_max_drawdown_{days}d"] = _avg(_numbers(rows, drawdown_field))

    drawdowns = _numbers(rows, "max_drawdown_250d")
    if not drawdowns:
        for days in EVAL_WINDOWS:
            drawdowns.extend(_numbers(rows, f"max_drawdown_{days}d"))
    best_signals, worst_signals = _ranked_signals(rows)
    diagnostics = {
        "missing_fields": _split_flags(rows, "missing_fields"),
        "risk_flags": _split_flags(rows, "risk_flags"),
        "best_signal_type_by_avg_60d_return": _best_signal_type(rows),
        "best_return_horizon_by_average": _best_horizon(summary),
    }
    if extra_diagnostics:
        diagnostics.update(extra_diagnostics)

    summary.update(
        {
            "avg_max_drawdown": _avg(drawdowns),
            "max_drawdown_worst": min(drawdowns) if drawdowns else None,
            "max_consecutive_losses": _max_consecutive_losses(rows),
            "best_signals": best_signals,
            "worst_signals": worst_signals,
            "wins": {
                f"{days}d": _win_record(rows, f"future_return_{days}d")
                for days in EVAL_WINDOWS
            },
            "avg_returns": {
                f"{days}d": summary.get(f"avg_return_{days}d")
                for days in EVAL_WINDOWS
            },
            "median_returns": {
                f"{days}d": summary.get(f"median_return_{days}d")
                for days in EVAL_WINDOWS
            },
            "drawdown": {
                "avg_max_drawdown_pct": _avg(drawdowns),
                "worst_max_drawdown_pct": min(drawdowns) if drawdowns else None,
                "by_horizon_avg_pct": {
                    f"{days}d": summary.get(f"avg_max_drawdown_{days}d")
                    for days in EVAL_WINDOWS
                },
            },
            "benchmark_outperform": {
                f"{days}d": summary.get(f"outperform_benchmark_rate_{days}d")
                for days in EVAL_WINDOWS
            },
            "best": best_signals,
            "worst": worst_signals,
            "diagnostics": diagnostics,
        }
    )
    return summary
