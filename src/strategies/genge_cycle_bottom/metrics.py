"""Metrics aggregation for GenGe Cycle Bottom walk-forward backtests."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional

from .acceptance import evaluate_paper_trading_gate
from .backtest import EVAL_WINDOWS
from .features import coerce_date


BASELINE_PATH = Path(__file__).resolve().parents[3] / "config" / "genge_signal_quality_baseline.json"
BASELINE_METRIC_FIELDS = (
    "total_signals",
    "avg_net_return_20d",
    "avg_net_return_60d",
    "avg_net_return_120d",
    "avg_net_return_250d",
    "win_rate_60d",
    "outperform_benchmark_rate_60d",
    "avg_low_max_drawdown_250d",
)


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


def _data_gap_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        raw = row.get("missing_fields") or ""
        if isinstance(raw, (list, tuple, set)):
            missing = {str(part).strip() for part in raw if str(part).strip()}
        else:
            missing = {part.strip() for part in str(raw).split(";") if part.strip()}
        if "valuation" in missing:
            counter["pe_missing"] += 1
            counter["pb_missing"] += 1
        else:
            if "pe" in missing:
                counter["pe_missing"] += 1
            if "pb" in missing:
                counter["pb_missing"] += 1
        if "financial" in missing:
            counter["financial_missing"] += 1
        if "industry_cycle" in missing:
            counter["industry_cycle_missing"] += 1
        if "stock_industry_map" in missing:
            counter["stock_industry_map_missing"] += 1
    return dict(counter)


def _missing_tokens(row: Dict[str, Any]) -> set[str]:
    raw = row.get("missing_fields") or ""
    if isinstance(raw, (list, tuple, set)):
        return {str(part).strip() for part in raw if str(part).strip()}
    return {part.strip() for part in str(raw).split(";") if part.strip()}


def _coverage_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {
            "valuation_coverage_rate": 0.0,
            "financial_coverage_rate": 0.0,
            "industry_cycle_coverage_rate": 0.0,
            "pe_missing_count": 0,
            "pb_missing_count": 0,
            "financial_missing_count": 0,
            "industry_cycle_missing_count": 0,
        }

    pe_missing = 0
    pb_missing = 0
    valuation_covered = 0
    financial_covered = 0
    industry_cycle_covered = 0
    industry_cycle_missing = 0

    for row in rows:
        missing = _missing_tokens(row)
        missing_valuation = "valuation" in missing
        missing_pe = missing_valuation or "pe" in missing
        missing_pb = missing_valuation or "pb" in missing
        pe_missing += int(missing_pe)
        pb_missing += int(missing_pb)
        valuation_covered += int(not missing_valuation and not (missing_pe and missing_pb))
        financial_covered += int("financial" not in missing)
        industry_missing = "industry_cycle" in missing or "stock_industry_map" in missing
        industry_cycle_missing += int(industry_missing)
        industry_cycle_covered += int(not industry_missing)

    financial_missing = total - financial_covered
    return {
        "valuation_coverage_rate": round(valuation_covered / total * 100, 4),
        "financial_coverage_rate": round(financial_covered / total * 100, 4),
        "industry_cycle_coverage_rate": round(industry_cycle_covered / total * 100, 4),
        "pe_missing_count": pe_missing,
        "pb_missing_count": pb_missing,
        "financial_missing_count": financial_missing,
        "industry_cycle_missing_count": industry_cycle_missing,
    }


def _execution_diagnostics(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    unavailable_values = {"missing", "unavailable"}
    return {
        "limit_up_entry_count": sum(1 for row in rows if row.get("limit_up_entry_risk") is True),
        "limit_down_entry_count": sum(1 for row in rows if row.get("limit_down_entry_risk") is True),
        "missing_entry_count": sum(1 for row in rows if row.get("suspended_or_missing_bar") is True or row.get("executable_entry_quality") in unavailable_values),
        "degraded_entry_count": sum(1 for row in rows if row.get("executable_entry_quality") == "degraded"),
        "risky_entry_count": sum(1 for row in rows if row.get("executable_entry_quality") == "risky"),
        "low_liquidity_count": sum(1 for row in rows if row.get("low_liquidity_risk") is True),
        "abnormal_gap_open_count": sum(1 for row in rows if row.get("abnormal_gap_open") is True),
    }


def _max_consecutive_losses(rows: List[Dict[str, Any]], return_field: str = "net_return_60d") -> int:
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
        "entry_date": row.get("entry_date"),
        "entry_price": row.get("entry_price"),
        "entry_mode": row.get("entry_mode"),
        "signal_type": row.get("signal_type"),
        "total_score": row.get("total_score"),
        return_field: row.get(return_field),
        "low_max_drawdown_250d": row.get("low_max_drawdown_250d"),
        "risk_flags": row.get("risk_flags"),
    }


def _ranked_signals(rows: List[Dict[str, Any]], return_field: str = "net_return_60d") -> tuple[list[dict], list[dict]]:
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
        value = _finite_number(row.get("net_return_60d"))
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


def _verdict_for_group(total_signals: int, avg_60d: Optional[float], drawdown_250d: Optional[float]) -> str:
    if total_signals < 20:
        return "样本不足"
    if avg_60d is not None and avg_60d > 0 and (drawdown_250d is None or drawdown_250d >= -25):
        return "可继续研究"
    if avg_60d is not None and avg_60d <= 0:
        return "期望不足"
    if drawdown_250d is not None and drawdown_250d < -25:
        return "回撤偏大"
    return "需要补数据"


def _group_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"total_signals": len(rows)}
    for days in EVAL_WINDOWS:
        return_field = f"net_return_{days}d"
        result[f"win_rate_{days}d"] = _win_rate(rows, return_field)
        result[f"avg_net_return_{days}d"] = _avg(_numbers(rows, return_field))
        result[f"avg_stop_adjusted_net_return_{days}d"] = _avg(_numbers(rows, f"stop_adjusted_net_return_{days}d"))
    result["median_net_return_60d"] = _median(_numbers(rows, "net_return_60d"))
    result["low_max_drawdown_250d"] = _avg(_numbers(rows, "low_max_drawdown_250d"))
    result["outperform_benchmark_rate_60d"] = _ratio_true(rows, "outperform_benchmark_60d")
    result["best_signal_type"] = _best_signal_type(rows)
    result["verdict"] = _verdict_for_group(
        len(rows),
        result.get("avg_net_return_60d"),
        result.get("low_max_drawdown_250d"),
    )
    return result


def _group_summary(rows: List[Dict[str, Any]], field_name: str, fallback: str = "UNKNOWN") -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(field_name) or fallback)
        grouped.setdefault(key, []).append(row)
    return {
        key: _group_metrics(group_rows)
        for key, group_rows in sorted(grouped.items(), key=lambda item: item[0])
    }


def _count_token(rows: Iterable[Dict[str, Any]], field_name: str, token: str) -> int:
    return sum(1 for row in rows if _contains_token(row.get(field_name), token))


def _stop_policy_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for days in EVAL_WINDOWS:
        stop_field = f"stop_adjusted_net_return_{days}d"
        original_field = f"net_return_{days}d"
        stop_avg = _avg(_numbers(rows, stop_field))
        original_avg = _avg(_numbers(rows, original_field))
        result[f"avg_stop_adjusted_net_return_{days}d"] = stop_avg
        result[f"stop_trigger_rate_{days}d"] = _ratio_true(rows, f"stop_triggered_{days}d")
        result[f"avg_delta_vs_original_{days}d"] = (
            round(stop_avg - original_avg, 4)
            if stop_avg is not None and original_avg is not None
            else None
        )
    result["reduced_drawdown_proxy"] = bool(
        result.get("avg_delta_vs_original_250d") is not None
        and result.get("avg_delta_vs_original_250d") >= 0
    )
    result["may_cut_rebound_proxy"] = bool(
        result.get("avg_delta_vs_original_120d") is not None
        and result.get("avg_delta_vs_original_120d") < 0
    )
    result["avg_post_entry_adverse_excursion_pct"] = _avg(_numbers(rows, "post_entry_adverse_excursion_pct"))
    return result


def _load_baseline() -> Dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _baseline_group_from_diagnostics(diagnostics: Dict[str, Any]) -> Optional[str]:
    output_dir = str(diagnostics.get("output_dir") or "").lower()
    requested = [str(item) for item in diagnostics.get("requested_codes") or []]
    benchmark = str(diagnostics.get("benchmark") or "")
    if "signal_quality_broad" in output_dir or benchmark == "000905" or len(requested) >= 90:
        return "broad"
    if "signal_quality_cycle" in output_dir or len(requested) >= 50:
        return "cycle"
    if "signal_quality_core" in output_dir or requested:
        return "core"
    return None


def _baseline_comparison(summary: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    baseline = _load_baseline()
    group = _baseline_group_from_diagnostics(diagnostics)
    baseline_metrics = ((baseline.get("metrics") or {}).get(group or "") or {})
    if not group or not baseline_metrics:
        return {
            "baseline_commit": baseline.get("commit"),
            "baseline_group": group,
            "available": False,
            "overfit_warning": False,
            "metrics": {},
            "overall_improved": False,
        }
    metrics: Dict[str, Dict[str, Any]] = {}
    improved_count = 0
    comparable_count = 0
    for field_name in BASELINE_METRIC_FIELDS:
        current = summary.get(field_name)
        baseline_value = baseline_metrics.get(field_name)
        current_number = _finite_number(current)
        baseline_number = _finite_number(baseline_value)
        if current_number is None or baseline_number is None:
            metrics[field_name] = {
                "current": current,
                "baseline": baseline_value,
                "delta": None,
                "improved": None,
            }
            continue
        delta = round(current_number - baseline_number, 4)
        if field_name == "avg_low_max_drawdown_250d":
            improved = current_number >= baseline_number
        elif field_name == "total_signals":
            improved = current_number >= baseline_number * 0.5
        else:
            improved = current_number > baseline_number
        comparable_count += 1
        improved_count += int(improved)
        metrics[field_name] = {
            "current": current_number,
            "baseline": baseline_number,
            "delta": delta,
            "improved": improved,
        }
    baseline_total = _finite_number(baseline_metrics.get("total_signals"))
    current_total = _finite_number(summary.get("total_signals"))
    overfit_warning = bool(
        baseline_total is not None
        and current_total is not None
        and baseline_total > 0
        and current_total < baseline_total * 0.5
    )
    key_improved = [
        metrics.get("avg_net_return_60d", {}).get("improved") is True,
        metrics.get("win_rate_60d", {}).get("improved") is True,
        metrics.get("outperform_benchmark_rate_60d", {}).get("improved") is True,
        metrics.get("avg_low_max_drawdown_250d", {}).get("improved") is True,
    ]
    return {
        "baseline_commit": baseline.get("commit"),
        "baseline_group": group,
        "available": True,
        "overfit_warning": overfit_warning,
        "sample_count_change_pct": (
            round((current_total - baseline_total) / baseline_total * 100.0, 4)
            if baseline_total not in (None, 0) and current_total is not None
            else None
        ),
        "metrics": metrics,
        "improved_metric_count": improved_count,
        "comparable_metric_count": comparable_count,
        "overall_improved": bool(all(key_improved) and not overfit_warning),
    }


def _parameter_experiment_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    split = _time_split_summary(rows)
    _, end = _date_range(rows)
    recent_cutoff = end - timedelta(days=int(365.25 * 2)) if end is not None else None
    experiments = {
        "baseline_current": rows,
        "trend_medium_plus": [
            row for row in rows if str(row.get("trend_confirmation_level") or "") in {"MEDIUM", "STRONG"}
        ],
        "low_value_trap": [
            row for row in rows if (_finite_number(row.get("value_trap_score")) or 0.0) < 60
        ],
        "good_execution": [
            row for row in rows if str(row.get("executable_entry_quality") or "") in {"good", "normal"}
        ],
        "tight_stop_distance": [
            row for row in rows if (_finite_number(row.get("stop_loss_distance_pct")) is None or (_finite_number(row.get("stop_loss_distance_pct")) or 0.0) <= 12)
        ],
    }
    experiment_metrics = {
        name: {
            "train": split.get("first_half") if name == "baseline_current" else _group_metrics(group_rows[: max(1, len(group_rows) // 2)]),
            "validation": split.get("second_half") if name == "baseline_current" else _group_metrics(group_rows[max(1, len(group_rows) // 2):]),
            "recent_2y": split.get("recent_2y") if name == "baseline_current" else _group_metrics(
                [
                    row for row in group_rows
                    if row.get("as_of_date")
                    and recent_cutoff is not None
                    and coerce_date(row["as_of_date"]) >= recent_cutoff
                ]
            ),
        }
        for name, group_rows in experiments.items()
    }
    stable_candidates = [
        name
        for name, result in experiment_metrics.items()
        if (result.get("validation") or {}).get("avg_net_return_60d") is not None
        and (result.get("recent_2y") or {}).get("avg_net_return_60d") is not None
        and (result["validation"]["avg_net_return_60d"] or 0) > 0
        and (result["recent_2y"]["avg_net_return_60d"] or 0) > -2
    ]
    return {
        "experiments": experiment_metrics,
        "recommended": stable_candidates[0] if stable_candidates else None,
        "conclusion": "存在相对稳定的候选参数组合" if stable_candidates else "未发现稳定优于当前参数的组合",
    }


def _date_range(rows: List[Dict[str, Any]]) -> tuple[Optional[date], Optional[date]]:
    dates = []
    for row in rows:
        raw = row.get("as_of_date")
        if not raw:
            continue
        try:
            dates.append(coerce_date(raw))
        except Exception:
            continue
    if not dates:
        return None, None
    return min(dates), max(dates)


def _time_split_summary(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    start, end = _date_range(rows)
    if start is None or end is None:
        return {
            "first_half": _group_metrics([]),
            "second_half": _group_metrics([]),
            "recent_2y": _group_metrics([]),
        }
    midpoint = start + (end - start) / 2
    recent_cutoff = end - timedelta(days=int(365.25 * 2))
    dated_rows = []
    for row in rows:
        if not row.get("as_of_date"):
            continue
        try:
            dated_rows.append((row, coerce_date(row["as_of_date"])))
        except Exception:
            continue
    first_half = [row for row, row_date in dated_rows if row_date <= midpoint]
    second_half = [row for row, row_date in dated_rows if row_date > midpoint]
    recent_2y = [row for row, row_date in dated_rows if row_date >= recent_cutoff]
    return {
        "first_half": _group_metrics(first_half),
        "second_half": _group_metrics(second_half),
        "recent_2y": _group_metrics(recent_2y),
    }


def _contains_token(raw: Any, token: str) -> bool:
    if not raw:
        return False
    if isinstance(raw, (list, tuple, set)):
        return token in raw
    return token in {part.strip() for part in str(raw).split(";") if part.strip()}


def _failure_reasons_for_row(row: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    net_20d = _finite_number(row.get("net_return_20d"))
    net_60d = _finite_number(row.get("net_return_60d"))
    net_120d = _finite_number(row.get("net_return_120d"))
    net_250d = _finite_number(row.get("net_return_250d"))
    low_dd_60d = _finite_number(row.get("low_max_drawdown_60d"))
    low_dd_250d = _finite_number(row.get("low_max_drawdown_250d"))
    trend_score = _finite_number(row.get("trend_stabilization_score"))
    market_score = _finite_number(row.get("market_environment_score"))
    industry_score = _finite_number(row.get("industry_cycle_score"))
    valuation_score = _finite_number(row.get("valuation_score"))

    if (net_20d is not None and net_20d < 0) or (net_60d is not None and net_60d < 0 and low_dd_60d is not None and low_dd_60d < -8):
        reasons.append("买太早")
    if trend_score is not None and trend_score < 65:
        reasons.append("趋势未确认")
    if _contains_token(row.get("missing_fields"), "financial") or _contains_token(row.get("risk_flags"), "loss_making") or _contains_token(row.get("risk_flags"), "debt_ratio_high") or _contains_token(row.get("risk_flags"), "debt_ratio_extreme"):
        reasons.append("财务缺失或恶化")
    if valuation_score is not None and valuation_score >= 70 and ((net_120d is not None and net_120d < 0) or (net_250d is not None and net_250d < 0)):
        reasons.append("估值陷阱")
    if industry_score is None or industry_score <= 50 or _contains_token(row.get("missing_fields"), "industry_cycle") or _contains_token(row.get("missing_fields"), "stock_industry_map") or str(row.get("industry_cycle_phase") or "").lower() in ("", "unknown"):
        reasons.append("行业周期判断不足")
    if market_score is not None and market_score < 45:
        reasons.append("大盘环境差")
    if net_60d is not None and net_60d > 0 and ((net_120d is not None and net_120d < 0) or (net_250d is not None and net_250d < 0)):
        reasons.append("持有周期不适合")
    if row.get("hit_stop_loss_60d") is True or row.get("hit_stop_loss_120d") is True or (low_dd_250d is not None and low_dd_250d < -25):
        reasons.append("止损不够严格")
    return reasons or ["其他或样本噪声"]


def _failure_reason_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    losers = [
        row for row in rows
        if (_finite_number(row.get("net_return_60d")) is not None and _finite_number(row.get("net_return_60d")) < 0)
        or (_finite_number(row.get("net_return_120d")) is not None and _finite_number(row.get("net_return_120d")) < 0)
        or (_finite_number(row.get("net_return_250d")) is not None and _finite_number(row.get("net_return_250d")) < 0)
    ]
    counter: Counter[str] = Counter()
    by_industry: Dict[str, List[Dict[str, Any]]] = {}
    by_signal: Dict[str, List[Dict[str, Any]]] = {}
    for row in losers:
        for reason in _failure_reasons_for_row(row):
            counter[reason] += 1
        by_industry.setdefault(str(row.get("industry") or "UNKNOWN"), []).append(row)
        by_signal.setdefault(str(row.get("signal_type") or "UNKNOWN"), []).append(row)

    industry_drag = {
        key: {
            "losing_signals": len(group_rows),
            "avg_net_return_60d": _avg(_numbers(group_rows, "net_return_60d")),
            "avg_net_return_120d": _avg(_numbers(group_rows, "net_return_120d")),
            "avg_net_return_250d": _avg(_numbers(group_rows, "net_return_250d")),
            "low_max_drawdown_250d": _avg(_numbers(group_rows, "low_max_drawdown_250d")),
        }
        for key, group_rows in sorted(by_industry.items(), key=lambda item: len(item[1]), reverse=True)[:10]
    }
    signal_type_drag = {
        key: _group_metrics(group_rows)
        for key, group_rows in sorted(by_signal.items(), key=lambda item: item[0])
    }
    return {
        "losing_signal_count": len(losers),
        "reason_counts": dict(counter.most_common()),
        "industry_drag": industry_drag,
        "signal_type_drag": signal_type_drag,
    }


def _expectancy_diagnostics(summary: Dict[str, Any]) -> Dict[str, Any]:
    avg_20d = summary.get("avg_net_return_20d")
    avg_60d = summary.get("avg_net_return_60d")
    avg_120d = summary.get("avg_net_return_120d")
    avg_250d = summary.get("avg_net_return_250d")
    return {
        "short_horizon_better": bool(avg_20d is not None and avg_60d is not None and avg_120d is not None and avg_250d is not None and max(avg_20d, avg_60d) > max(avg_120d, avg_250d)),
        "long_horizon_negative": bool((avg_120d is not None and avg_120d < 0) or (avg_250d is not None and avg_250d < 0)),
        "suggestion": "优先观察 20/60 日，暂不把 120/250 日作为强持有依据",
    }


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
        return_field = f"net_return_{days}d"
        raw_return_field = f"raw_return_{days}d"
        drawdown_field = f"low_max_drawdown_{days}d"
        returns = _numbers(rows, return_field)
        summary[f"win_rate_{days}d"] = _win_rate(rows, return_field)
        summary[f"avg_return_{days}d"] = _avg(returns)
        summary[f"median_return_{days}d"] = _median(returns)
        summary[f"avg_raw_return_{days}d"] = _avg(_numbers(rows, raw_return_field))
        summary[f"median_raw_return_{days}d"] = _median(_numbers(rows, raw_return_field))
        summary[f"avg_net_return_{days}d"] = summary[f"avg_return_{days}d"]
        summary[f"median_net_return_{days}d"] = summary[f"median_return_{days}d"]
        summary[f"avg_stop_adjusted_return_{days}d"] = _avg(_numbers(rows, f"stop_adjusted_return_{days}d"))
        summary[f"avg_stop_adjusted_net_return_{days}d"] = _avg(_numbers(rows, f"stop_adjusted_net_return_{days}d"))
        summary[f"outperform_benchmark_rate_{days}d"] = _ratio_true(rows, f"outperform_benchmark_{days}d")
        summary[f"avg_max_drawdown_{days}d"] = _avg(_numbers(rows, drawdown_field))
        summary[f"avg_low_max_drawdown_{days}d"] = summary[f"avg_max_drawdown_{days}d"]
        summary[f"avg_close_max_drawdown_{days}d"] = _avg(_numbers(rows, f"close_max_drawdown_{days}d"))

    drawdowns = _numbers(rows, "low_max_drawdown_250d")
    if not drawdowns:
        for days in EVAL_WINDOWS:
            drawdowns.extend(_numbers(rows, f"low_max_drawdown_{days}d"))
    best_signals, worst_signals = _ranked_signals(rows)
    coverage = _coverage_metrics(rows)
    execution = _execution_diagnostics(rows)
    diagnostics = {
        "missing_fields": _split_flags(rows, "missing_fields"),
        "risk_flags": _split_flags(rows, "risk_flags"),
        "data_gap_counts": _data_gap_counts(rows),
        "coverage": coverage,
        "execution_diagnostics": execution,
        "best_signal_type_by_avg_60d_return": _best_signal_type(rows),
        "best_return_horizon_by_average": _best_horizon(summary),
    }
    if extra_diagnostics:
        diagnostics.update(extra_diagnostics)
    baseline_comparison = _baseline_comparison(summary, diagnostics)
    stop_policy = _stop_policy_summary(rows)
    parameter_experiment = _parameter_experiment_summary(rows)

    summary.update(
        {
            "avg_max_drawdown": _avg(drawdowns),
            "max_drawdown_worst": min(drawdowns) if drawdowns else None,
            "max_consecutive_losses": _max_consecutive_losses(rows),
            "best_signals": best_signals,
            "worst_signals": worst_signals,
            "wins": {
                f"{days}d": _win_record(rows, f"net_return_{days}d")
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
                "default_basis": "low_max_drawdown",
                "by_horizon_avg_pct": {
                    f"{days}d": summary.get(f"avg_max_drawdown_{days}d")
                    for days in EVAL_WINDOWS
                },
            },
            "benchmark_outperform": {
                f"{days}d": summary.get(f"outperform_benchmark_rate_{days}d")
                for days in EVAL_WINDOWS
            },
            **coverage,
            "execution_diagnostics": execution,
            "low_max_drawdown": {
                "avg_250d": summary.get("avg_low_max_drawdown_250d"),
                "worst": min(drawdowns) if drawdowns else None,
            },
            "industry_summary": _group_summary(rows, "industry"),
            "signal_type_summary": _group_summary(rows, "signal_type"),
            "market_environment_summary": _group_summary(rows, "market_environment_state"),
            "industry_cycle_phase_summary": _group_summary(rows, "industry_cycle_phase"),
            "trend_confirmation_summary": _group_summary(rows, "trend_confirmation_level"),
            "industry_cycle_quality_summary": _group_summary(rows, "industry_cycle_quality"),
            "execution_entry_quality_summary": _group_summary(rows, "executable_entry_quality"),
            "time_split_summary": _time_split_summary(rows),
            "drawdown_diagnostics": {
                "default_basis": "low_max_drawdown",
                "avg_20d": summary.get("avg_low_max_drawdown_20d"),
                "avg_60d": summary.get("avg_low_max_drawdown_60d"),
                "avg_120d": summary.get("avg_low_max_drawdown_120d"),
                "avg_250d": summary.get("avg_low_max_drawdown_250d"),
                "worst": min(drawdowns) if drawdowns else None,
            },
            "failure_reason_summary": _failure_reason_summary(rows),
            "stop_policy_summary": stop_policy,
            "quality_filter_summary": {
                "falling_knife_filtered_count": _count_token(rows, "risk_flags", "falling_knife_risk"),
                "value_trap_flagged_count": _count_token(rows, "risk_flags", "value_trap_risk"),
                "missing_financial_uncertain_count": _count_token(rows, "risk_flags", "missing_financial_uncertain"),
                "high_execution_risk_count": sum(1 for row in rows if (_finite_number(row.get("execution_risk_score")) or 0.0) >= 60),
            },
            "parameter_experiment": parameter_experiment,
            "baseline_comparison": baseline_comparison,
            "best": best_signals,
            "worst": worst_signals,
            "diagnostics": diagnostics,
        }
    )
    summary["expectancy_diagnostics"] = _expectancy_diagnostics(summary)
    gate_context = {
        key: diagnostics[key]
        for key in (
            "ci_passed",
            "fixture_smoke_passed",
            "real_5y_passed",
            "real_10y_passed",
            "real_10y_safely_degraded",
            "no_lookahead_risk",
            "no_auto_trade",
            "source_mode",
        )
        if key in diagnostics
    }
    summary["paper_trading_gate"] = evaluate_paper_trading_gate(summary, **gate_context)
    return summary
