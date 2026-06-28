"""Feature calculation for the GenGe Cycle Bottom Strategy.

All feature helpers accept an explicit ``as_of_date`` and only inspect rows
whose ``date`` is less than or equal to that date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 250
PRICE_MIN_OBSERVATIONS_BY_YEARS = {3: 500, 5: 800, 10: 1200}
VALUATION_MIN_OBSERVATIONS = 120
DISCLOSURE_DATE_COLUMNS = ("disclosure_date", "publish_date", "ann_date", "announcement_date")


@dataclass
class FeatureSet:
    as_of_date: date
    close: Optional[float]
    price_percentile_score: float = 0.0
    valuation_score: float = 0.0
    financial_safety_score: float = 0.0
    trend_stabilization_score: float = 0.0
    market_environment_score: float = 0.0
    industry_cycle_score: float = 50.0
    price_percentile_3y: Optional[float] = None
    price_percentile_5y: Optional[float] = None
    price_percentile_10y: Optional[float] = None
    distance_from_5y_low_pct: Optional[float] = None
    distance_from_5y_high_pct: Optional[float] = None
    distance_from_10y_low_pct: Optional[float] = None
    distance_from_10y_high_pct: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma120: Optional[float] = None
    ma250: Optional[float] = None
    stabilization_days: int = 0
    downtrend_exhaustion_score: float = 0.0
    reclaim_ma_score: float = 0.0
    no_falling_knife_filter: bool = False
    second_low_confirmation: bool = False
    trend_confirmation_level: str = "NONE"
    dynamic_stop_loss: Optional[float] = None
    stop_loss_distance_pct: Optional[float] = None
    invalidation_level: Optional[float] = None
    value_trap_score: float = 0.0
    value_trap_flag: bool = False
    valuation_repair_signal: bool = False
    industry: Optional[str] = None
    industry_cycle_phase: Optional[str] = None
    industry_cycle_quality: str = "missing"
    market_environment_state: Optional[str] = None
    execution_risk_score: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return pd.to_datetime(value).date()


def prepare_price_frame(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    df = price_df.copy()
    if "date" not in df.columns:
        raise ValueError("price data must include a date column")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ("open", "high", "low", "close", "volume", "amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def slice_as_of(df: pd.DataFrame, as_of_date: Any) -> pd.DataFrame:
    prepared = prepare_price_frame(df)
    target = coerce_date(as_of_date)
    return prepared[prepared["date"] <= target].copy().reset_index(drop=True)


def _prepare_date_frame(df: Optional[pd.DataFrame], date_column: str = "date") -> pd.DataFrame:
    if df is None or df.empty or date_column not in df.columns:
        return pd.DataFrame()
    local = df.copy()
    local[date_column] = pd.to_datetime(local[date_column], errors="coerce").dt.date
    local = local.dropna(subset=[date_column]).sort_values(date_column).reset_index(drop=True)
    return local


def finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def percentile_rank(values: Iterable[float], current: float) -> Optional[float]:
    series = pd.Series(list(values), dtype="float64").dropna()
    current_value = finite_float(current)
    if current_value is None or series.empty:
        return None
    return float((series <= current_value).sum() / len(series))


def score_from_low_percentile(percentile: Optional[float]) -> float:
    if percentile is None:
        return 0.0
    if percentile <= 0.2:
        return 90.0
    if percentile <= 0.35:
        return 75.0
    if percentile <= 0.5:
        return 55.0
    if percentile <= 0.7:
        return 35.0
    return 15.0


def _window_for_years(history: pd.DataFrame, years: int) -> pd.DataFrame:
    if history.empty:
        return history
    local = history.copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local = local.dropna(subset=["date"]).sort_values("date")
    if local.empty:
        return local
    as_of = coerce_date(local.iloc[-1]["date"])
    cutoff = as_of - timedelta(days=int(years * 365.25))
    return local[local["date"] >= cutoff].copy()


def _distance_from_extreme(current_close: float, extreme: Optional[float]) -> Optional[float]:
    value = finite_float(extreme)
    current = finite_float(current_close)
    if value is None or current is None or value <= 0:
        return None
    return round((current - value) / value * 100.0, 4)


def compute_price_percentile_score(history: pd.DataFrame, current_close: float) -> Tuple[float, Dict[str, Optional[float]], List[str]]:
    percentiles: Dict[str, Optional[float]] = {}
    missing: List[str] = []

    for years in (3, 5, 10):
        window = _window_for_years(history, years).tail(years * TRADING_DAYS_PER_YEAR)
        key = f"price_percentile_{years}y"
        if len(window) < PRICE_MIN_OBSERVATIONS_BY_YEARS[years]:
            percentiles[key] = None
            missing.append(key)
            continue
        percentiles[key] = percentile_rank(window["close"], current_close)

        if years in (5, 10):
            low = finite_float(window["close"].min())
            high = finite_float(window["close"].max())
            percentiles[f"distance_from_{years}y_low_pct"] = _distance_from_extreme(current_close, low)
            percentiles[f"distance_from_{years}y_high_pct"] = _distance_from_extreme(current_close, high)

    for years in (5, 10):
        percentiles.setdefault(f"distance_from_{years}y_low_pct", None)
        percentiles.setdefault(f"distance_from_{years}y_high_pct", None)
        if percentiles[f"distance_from_{years}y_low_pct"] is None:
            missing.append(f"distance_from_{years}y_low_pct")
        if percentiles[f"distance_from_{years}y_high_pct"] is None:
            missing.append(f"distance_from_{years}y_high_pct")

    preferred = percentiles.get("price_percentile_5y")
    if preferred is None:
        preferred = percentiles.get("price_percentile_3y")
    score = score_from_low_percentile(preferred)
    if preferred is None:
        score = 20.0
    return score, percentiles, missing


def _latest_row_as_of(df: Optional[pd.DataFrame], as_of_date: date, date_column: str = "date") -> Optional[pd.Series]:
    if df is None or df.empty or date_column not in df.columns:
        return None
    local = df.copy()
    local[date_column] = pd.to_datetime(local[date_column]).dt.date
    local = local[local[date_column] <= as_of_date].sort_values(date_column)
    if local.empty:
        return None
    return local.iloc[-1]


def _clean_valuation_series(values: pd.Series, field_name: str) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").dropna()
    series = series[series > 0]
    max_reasonable = {"pe": 300.0, "pb": 50.0, "ps": 100.0}.get(field_name, float("inf"))
    return series[series <= max_reasonable]


def _valuation_percentile(history: pd.DataFrame, field_name: str, current_value: float, as_of_date: date, years: int) -> Optional[float]:
    cutoff = as_of_date - timedelta(days=int(years * 365.25))
    window = history[history["date"] >= cutoff]
    series = _clean_valuation_series(window[field_name], field_name) if field_name in window.columns else pd.Series(dtype="float64")
    if len(series) < VALUATION_MIN_OBSERVATIONS:
        return None
    return percentile_rank(series, current_value)


def _is_cycle_industry(industry: Optional[str]) -> bool:
    if not industry:
        return False
    keywords = ("钢铁", "煤炭", "有色", "化工", "养殖", "猪", "航运", "航空", "地产", "建材", "半导体", "面板")
    return any(keyword in industry for keyword in keywords)


def compute_valuation_score(
    valuation_df: Optional[pd.DataFrame],
    as_of_date: date,
    industry: Optional[str] = None,
) -> Tuple[float, List[str], Dict[str, Any]]:
    missing: List[str] = []
    diagnostics: Dict[str, Any] = {}
    history = _prepare_date_frame(valuation_df, "date")
    if history.empty:
        return 35.0, ["valuation"], diagnostics
    history = history[history["date"] <= as_of_date].copy()
    if history.empty:
        return 35.0, ["valuation"], diagnostics
    row = history.iloc[-1]

    field_scores: Dict[str, float] = {}
    for field_name in ("pb", "pe", "ps"):
        if field_name not in row.index:
            missing.append(field_name)
            continue
        value = finite_float(row.get(field_name))
        if value is None or value <= 0:
            missing.append(field_name)
            continue
        if _clean_valuation_series(pd.Series([value]), field_name).empty:
            missing.append(field_name)
            continue
        diagnostics[field_name] = value
        percentiles = {
            years: _valuation_percentile(history, field_name, value, as_of_date, years)
            for years in (3, 5, 10)
        }
        for years, percentile in percentiles.items():
            diagnostics[f"{field_name}_percentile_{years}y"] = percentile
            if percentile is None:
                missing.append(f"{field_name}_percentile_{years}y")
        preferred = percentiles.get(5) if percentiles.get(5) is not None else percentiles.get(3)
        if preferred is None:
            preferred = percentiles.get(10)
        if preferred is None:
            continue
        field_scores[field_name] = score_from_low_percentile(preferred)

    if not field_scores:
        return 35.0, missing or ["valuation"], diagnostics

    if _is_cycle_industry(industry):
        weights = {"pb": 0.55, "ps": 0.35, "pe": 0.10}
    else:
        weights = {"pb": 0.40, "pe": 0.40, "ps": 0.20}
    weighted_total = 0.0
    weight_total = 0.0
    for field_name, score in field_scores.items():
        weight = weights.get(field_name, 0.0)
        weighted_total += score * weight
        weight_total += weight
    if weight_total <= 0:
        return 35.0, missing or ["valuation"], diagnostics
    penalty = min(10.0, len([item for item in missing if item in ("pb", "pe", "ps")]) * 3.0)
    return max(0.0, min(100.0, weighted_total / weight_total - penalty)), sorted(set(missing)), diagnostics


def compute_value_trap_diagnostics(
    *,
    valuation_diagnostics: Dict[str, Any],
    financial_diagnostics: Dict[str, Any],
    financial_missing: List[str],
    financial_risks: List[str],
    price_percentile_5y: Optional[float],
    valuation_score: float,
) -> Dict[str, Any]:
    score = 0.0
    repair_score = 0.0
    pb = finite_float(valuation_diagnostics.get("pb"))
    pe = finite_float(valuation_diagnostics.get("pe"))
    pb_percentile = finite_float(valuation_diagnostics.get("pb_percentile_5y"))
    pe_percentile = finite_float(valuation_diagnostics.get("pe_percentile_5y"))
    debt_ratio = finite_float(financial_diagnostics.get("debt_ratio"))
    net_profit = finite_float(financial_diagnostics.get("net_profit"))
    operating_cash_flow = finite_float(financial_diagnostics.get("operating_cash_flow"))
    roe = finite_float(financial_diagnostics.get("roe"))

    looks_cheap = bool(
        valuation_score >= 70
        or (pb is not None and pb <= 1.2)
        or (pb_percentile is not None and pb_percentile <= 0.25)
        or (pe_percentile is not None and pe_percentile <= 0.25)
        or (price_percentile_5y is not None and price_percentile_5y <= 0.25)
    )
    if looks_cheap:
        score += 15
        repair_score += 10
    if "financial" in financial_missing:
        score += 35
    elif financial_missing:
        score += min(25.0, len(financial_missing) * 6.0)
    if "loss_making" in financial_risks or (net_profit is not None and net_profit < 0):
        score += 35
    if "negative_operating_cash_flow" in financial_risks or (operating_cash_flow is not None and operating_cash_flow < 0):
        score += 25
    if "debt_ratio_extreme" in financial_risks:
        score += 35
    elif "debt_ratio_high" in financial_risks:
        score += 22
    if "negative_roe" in financial_risks or (roe is not None and roe < 0):
        score += 18
    if debt_ratio is not None and debt_ratio <= 55:
        repair_score += 20
    if net_profit is not None and net_profit > 0:
        repair_score += 20
    if operating_cash_flow is not None and operating_cash_flow > 0:
        repair_score += 20
    if roe is not None and roe >= 6:
        repair_score += 15
    if pe is not None and pe <= 0:
        score += 10
    if looks_cheap and repair_score >= 45 and score < 55:
        repair_signal = True
    else:
        repair_signal = False
    return {
        "value_trap_score": round(max(0.0, min(100.0, score)), 2),
        "value_trap_flag": bool(score >= 60),
        "valuation_repair_signal": repair_signal,
    }


def _report_lag_days(report_date: date) -> int:
    month_day = (report_date.month, report_date.day)
    if month_day == (12, 31):
        return 120
    if month_day == (6, 30):
        return 90
    if month_day in {(3, 31), (9, 30)}:
        return 60
    return 90


def _financial_available_date(row: pd.Series, has_disclosure_columns: bool) -> Optional[date]:
    for column in DISCLOSURE_DATE_COLUMNS:
        if column in row.index and pd.notna(row.get(column)):
            try:
                return coerce_date(row.get(column))
            except Exception:
                return None
    if has_disclosure_columns:
        return None
    if "report_date" not in row.index or pd.isna(row.get("report_date")):
        return None
    report_date = coerce_date(row.get("report_date"))
    return report_date + timedelta(days=_report_lag_days(report_date))


def _available_financial_rows(financial_df: Optional[pd.DataFrame], as_of_date: date) -> pd.DataFrame:
    if financial_df is None or financial_df.empty or "report_date" not in financial_df.columns:
        return pd.DataFrame()
    local = financial_df.copy()
    local["report_date"] = pd.to_datetime(local["report_date"], errors="coerce").dt.date
    local = local.dropna(subset=["report_date"]).copy()
    has_disclosure_columns = any(column in local.columns and local[column].notna().any() for column in DISCLOSURE_DATE_COLUMNS)
    local["available_date"] = local.apply(
        lambda row: _financial_available_date(row, has_disclosure_columns),
        axis=1,
    )
    local = local.dropna(subset=["available_date"])
    return local[local["available_date"] <= as_of_date].sort_values(["available_date", "report_date"])


def compute_financial_safety_score(financial_df: Optional[pd.DataFrame], as_of_date: date) -> Tuple[float, List[str], List[str], Dict[str, Any]]:
    missing: List[str] = []
    risk_flags: List[str] = []
    diagnostics: Dict[str, Any] = {}
    available = _available_financial_rows(financial_df, as_of_date)
    if available.empty:
        return 45.0, ["financial"], risk_flags, diagnostics
    row = available.iloc[-1]
    diagnostics["financial_report_date"] = row.get("report_date").isoformat() if hasattr(row.get("report_date"), "isoformat") else row.get("report_date")
    diagnostics["financial_available_date"] = row.get("available_date").isoformat() if hasattr(row.get("available_date"), "isoformat") else row.get("available_date")

    score = 70.0
    debt_ratio = finite_float(row.get("debt_ratio")) if "debt_ratio" in row.index else None
    net_profit = finite_float(row.get("net_profit")) if "net_profit" in row.index else None
    operating_cash_flow = finite_float(row.get("operating_cash_flow")) if "operating_cash_flow" in row.index else None
    roe = finite_float(row.get("roe")) if "roe" in row.index else None

    if debt_ratio is None:
        missing.append("debt_ratio")
    else:
        diagnostics["debt_ratio"] = debt_ratio
        if debt_ratio >= 85:
            score -= 35
            risk_flags.append("debt_ratio_extreme")
        elif debt_ratio >= 70:
            score -= 20
            risk_flags.append("debt_ratio_high")
        elif debt_ratio <= 45:
            score += 8

    if net_profit is None:
        missing.append("net_profit")
    else:
        diagnostics["net_profit"] = net_profit
        if net_profit < 0:
            score -= 30
            risk_flags.append("loss_making")
        elif net_profit > 0:
            score += 6

    if operating_cash_flow is None:
        missing.append("operating_cash_flow")
    else:
        diagnostics["operating_cash_flow"] = operating_cash_flow
        if operating_cash_flow < 0:
            score -= 18
            risk_flags.append("negative_operating_cash_flow")
        elif operating_cash_flow > 0:
            score += 6

    if roe is None:
        missing.append("roe")
    else:
        diagnostics["roe"] = roe
        if roe < 0:
            score -= 15
            risk_flags.append("negative_roe")
        elif roe >= 8:
            score += 5

    return max(0.0, min(100.0, score)), missing, risk_flags, diagnostics


def _moving_average(history: pd.DataFrame, window: int) -> Optional[float]:
    if len(history) < window:
        return None
    value = history["close"].tail(window).mean()
    return finite_float(value)


def _pct_change_value(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / previous * 100.0


def _trailing_stabilization_days(history: pd.DataFrame, ma20: Optional[float]) -> int:
    if len(history) < 6 or "close" not in history.columns:
        return 0
    closes = pd.to_numeric(history["close"], errors="coerce")
    returns = closes.pct_change()
    rolling_low = closes.rolling(20, min_periods=5).min()
    days = 0
    for idx in range(len(history) - 1, max(-1, len(history) - 31), -1):
        close = finite_float(closes.iloc[idx])
        low = finite_float(rolling_low.iloc[idx])
        daily_return = finite_float(returns.iloc[idx])
        if close is None or low is None:
            break
        floor_ok = close >= low * 1.01
        ma_ok = ma20 is None or close >= ma20 * 0.96
        daily_ok = daily_return is None or daily_return >= -0.045
        if floor_ok and ma_ok and daily_ok:
            days += 1
        else:
            break
    return days


def _second_low_confirmation(history: pd.DataFrame) -> bool:
    if len(history) < 80 or "close" not in history.columns:
        return False
    closes = pd.to_numeric(history["close"], errors="coerce")
    recent = closes.tail(25).dropna()
    previous = closes.tail(90).head(65).dropna()
    if recent.empty or previous.empty:
        return False
    recent_low = finite_float(recent.min())
    previous_low = finite_float(previous.min())
    close = finite_float(closes.iloc[-1])
    if recent_low is None or previous_low is None or close is None or previous_low <= 0:
        return False
    low_not_broken = recent_low >= previous_low * 0.94
    bounced_from_low = close >= recent_low * 1.025
    return bool(low_not_broken and bounced_from_low)


def _trend_confirmation_level(
    *,
    close: float,
    ma20: Optional[float],
    ma60: Optional[float],
    ma120: Optional[float],
    ma20_slope_pct: Optional[float],
    stabilization_days: int,
    downtrend_exhaustion_score: float,
    reclaim_ma_score: float,
    no_falling_knife_filter: bool,
    second_low_confirmation: bool,
) -> str:
    if not no_falling_knife_filter:
        return "NONE"
    above_ma20 = bool(ma20 is not None and close >= ma20)
    near_or_above_ma60 = bool(ma60 is not None and close >= ma60 * 0.98)
    above_ma60 = bool(ma60 is not None and close >= ma60)
    ma20_turning = bool(ma20_slope_pct is not None and ma20_slope_pct >= -0.5)
    ma20_rising = bool(ma20_slope_pct is not None and ma20_slope_pct > 0)
    above_ma120 = bool(ma120 is None or close >= ma120 * 0.97)

    if above_ma20 and above_ma60 and above_ma120 and ma20_rising and second_low_confirmation and stabilization_days >= 8:
        return "STRONG"
    if above_ma20 and near_or_above_ma60 and ma20_turning and stabilization_days >= 5 and downtrend_exhaustion_score >= 50:
        return "MEDIUM"
    if (above_ma20 or reclaim_ma_score >= 45) and stabilization_days >= 3:
        return "WEAK"
    return "NONE"


def compute_trend_stabilization_score(history: pd.DataFrame) -> Tuple[float, Dict[str, Any], List[str], List[str]]:
    missing: List[str] = []
    risk_flags: List[str] = []
    diagnostics: Dict[str, Any] = {}
    if history.empty or "close" not in history.columns:
        return 0.0, diagnostics, ["daily_price"], ["missing_daily_price"]

    close = finite_float(history.iloc[-1].get("close"))
    if close is None:
        return 0.0, diagnostics, ["close"], ["missing_close"]

    ma20 = _moving_average(history, 20)
    ma60 = _moving_average(history, 60)
    ma120 = _moving_average(history, 120)
    ma250 = _moving_average(history, 250)
    diagnostics.update({"ma20": ma20, "ma60": ma60, "ma120": ma120, "ma250": ma250})
    ma20_slope_pct = None
    if len(history) >= 25 and ma20 is not None:
        previous_ma20 = history["close"].tail(25).head(20).mean()
        ma20_slope_pct = _pct_change_value(ma20, finite_float(previous_ma20))
    diagnostics["ma20_slope_pct"] = round(ma20_slope_pct, 4) if ma20_slope_pct is not None else None

    score = 35.0
    for name, value in (("ma20", ma20), ("ma60", ma60), ("ma120", ma120), ("ma250", ma250)):
        if value is None:
            missing.append(name)

    if ma20 is not None and close >= ma20:
        score += 25
    elif ma20 is not None:
        score -= 10

    if ma60 is not None and close >= ma60:
        score += 20
    elif ma60 is not None and close >= ma60 * 0.97:
        score += 10

    if len(history) >= 15:
        recent = history.tail(15)
        recent_return = (recent.iloc[-1]["close"] - recent.iloc[0]["close"]) / recent.iloc[0]["close"]
        diagnostics["recent_15d_return"] = finite_float(recent_return)
        if recent_return < -0.12:
            score -= 25
            risk_flags.append("accelerating_downtrend")
        elif abs(recent_return) <= 0.08:
            score += 8
    else:
        recent_return = None

    volume_ratio = None
    if "volume" in history.columns and len(history) >= 40:
        recent_vol = history["volume"].tail(5).mean()
        base_vol = history["volume"].tail(40).head(35).mean()
        if finite_float(recent_vol) is not None and finite_float(base_vol) is not None and base_vol > 0:
            volume_ratio = float(recent_vol / base_vol)
            diagnostics["volume_ratio_5d_vs_35d"] = volume_ratio
            if 1.05 <= volume_ratio <= 1.8:
                score += 10
            elif volume_ratio > 2.5:
                risk_flags.append("volume_spike")
                score -= 5
        else:
            missing.append("volume")

    stabilization_days = _trailing_stabilization_days(history, ma20)
    second_low = _second_low_confirmation(history)
    closes = pd.to_numeric(history["close"], errors="coerce")
    recent_20_low = finite_float(closes.tail(20).min()) if len(history) >= 20 else None
    recent_60_low = finite_float(closes.tail(60).min()) if len(history) >= 60 else recent_20_low
    last_5d_return = None
    if len(history) >= 6:
        last_5d_return = _pct_change_value(finite_float(closes.iloc[-1]), finite_float(closes.iloc[-6]))

    downtrend_exhaustion_score = 20.0
    if recent_return is not None:
        if recent_return >= -0.03:
            downtrend_exhaustion_score += 25
        elif recent_return >= -0.08:
            downtrend_exhaustion_score += 12
        elif recent_return < -0.12:
            downtrend_exhaustion_score -= 25
    if recent_20_low is not None and close >= recent_20_low * 1.03:
        downtrend_exhaustion_score += 20
    if recent_20_low is not None and recent_60_low is not None and recent_60_low > 0 and recent_20_low >= recent_60_low * 0.96:
        downtrend_exhaustion_score += 20
    if second_low:
        downtrend_exhaustion_score += 15
    if volume_ratio is not None and 0.8 <= volume_ratio <= 1.8:
        downtrend_exhaustion_score += 10
    downtrend_exhaustion_score = max(0.0, min(100.0, downtrend_exhaustion_score))

    reclaim_ma_score = 0.0
    if ma20 is not None and close >= ma20:
        reclaim_ma_score += 45
    if ma60 is not None and close >= ma60 * 0.98:
        reclaim_ma_score += 25
    if ma60 is not None and close >= ma60:
        reclaim_ma_score += 10
    if ma20_slope_pct is not None and ma20_slope_pct > 0:
        reclaim_ma_score += 15
    if volume_ratio is not None and 1.0 <= volume_ratio <= 1.8:
        reclaim_ma_score += 5
    reclaim_ma_score = max(0.0, min(100.0, reclaim_ma_score))

    no_falling_knife_filter = bool(
        stabilization_days >= 3
        and downtrend_exhaustion_score >= 42
        and (last_5d_return is None or last_5d_return >= -6.0)
        and (recent_20_low is None or close >= recent_20_low * 1.015)
    )
    if not no_falling_knife_filter:
        risk_flags.append("falling_knife_risk")

    trend_confirmation_level = _trend_confirmation_level(
        close=close,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        ma20_slope_pct=ma20_slope_pct,
        stabilization_days=stabilization_days,
        downtrend_exhaustion_score=downtrend_exhaustion_score,
        reclaim_ma_score=reclaim_ma_score,
        no_falling_knife_filter=no_falling_knife_filter,
        second_low_confirmation=second_low,
    )
    if trend_confirmation_level == "NONE":
        score -= 10
    elif trend_confirmation_level == "WEAK":
        score += 4
    elif trend_confirmation_level == "MEDIUM":
        score += 8
    elif trend_confirmation_level == "STRONG":
        score += 12

    diagnostics.update(
        {
            "stabilization_days": stabilization_days,
            "downtrend_exhaustion_score": round(downtrend_exhaustion_score, 2),
            "reclaim_ma_score": round(reclaim_ma_score, 2),
            "no_falling_knife_filter": no_falling_knife_filter,
            "second_low_confirmation": second_low,
            "trend_confirmation_level": trend_confirmation_level,
            "last_5d_return_pct": round(last_5d_return, 4) if last_5d_return is not None else None,
        }
    )
    return max(0.0, min(100.0, score)), diagnostics, missing, risk_flags


def compute_market_environment_score(benchmark_history: Optional[pd.DataFrame], as_of_date: date) -> Tuple[float, List[str], Dict[str, Any]]:
    if benchmark_history is None or benchmark_history.empty:
        return 50.0, ["benchmark"], {"market_environment_state": "unknown"}
    history = slice_as_of(benchmark_history, as_of_date)
    if history.empty:
        return 50.0, ["benchmark"], {"market_environment_state": "unknown"}
    close = finite_float(history.iloc[-1].get("close"))
    ma20 = _moving_average(history, 20)
    ma60 = _moving_average(history, 60)
    ma120 = _moving_average(history, 120)
    diagnostics = {"benchmark_ma20": ma20, "benchmark_ma60": ma60, "benchmark_ma120": ma120}
    if close is None or ma20 is None or ma60 is None:
        diagnostics["market_environment_state"] = "unknown"
        return 50.0, ["benchmark_ma"], diagnostics

    score = 45.0
    state = "neutral"
    if close >= ma20:
        score += 15
    if close >= ma60:
        score += 20
    if ma120 is not None and close >= ma120:
        score += 10
    if close < ma20 and close < ma60:
        score -= 20
        state = "weak"
    elif close >= ma20 and close >= ma60 and (ma120 is None or close >= ma120):
        state = "strong"
    diagnostics["market_environment_state"] = state
    return max(0.0, min(100.0, score)), [], diagnostics


def compute_industry_cycle_score(
    industry_cycle_df: Optional[pd.DataFrame],
    industry: Optional[str],
    as_of_date: date,
) -> Tuple[float, List[str], Dict[str, Any]]:
    diagnostics: Dict[str, Any] = {"industry": industry, "industry_cycle_quality": "missing"}
    if not industry:
        return 50.0, ["stock_industry_map"], diagnostics
    if industry_cycle_df is None or industry_cycle_df.empty:
        return 50.0, ["industry_cycle"], diagnostics
    history = _prepare_date_frame(industry_cycle_df, "date")
    if history.empty:
        return 50.0, ["industry_cycle"], diagnostics
    if "industry" in history.columns:
        history = history[history["industry"].astype(str) == str(industry)]
    history = history[history["date"] <= as_of_date].sort_values("date")
    if history.empty:
        return 50.0, ["industry_cycle"], diagnostics
    row = history.iloc[-1]
    phase = str(row.get("cycle_phase") or "unknown").strip().lower()
    raw_score = finite_float(row.get("cycle_score")) if "cycle_score" in row.index else None
    raw_quality = str(row.get("cycle_quality") or row.get("quality") or "").strip().lower()
    if raw_quality in {"manual_template", "user_supplied", "provider_derived", "verified"}:
        quality = raw_quality
    elif str(row.get("source") or "").strip().lower() in {"manual_template", "template", "example"}:
        quality = "manual_template"
    else:
        quality = "user_supplied"
    phase_defaults = {
        "bottom": 82.0,
        "recovering": 72.0,
        "neutral": 50.0,
        "unknown": 50.0,
        "overheating": 35.0,
        "declining": 28.0,
    }
    score = raw_score if raw_score is not None else phase_defaults.get(phase, 50.0)
    if phase == "bottom":
        score = max(score, 80.0)
    elif phase == "recovering":
        score = max(score, 70.0)
    elif phase == "overheating":
        score = min(score, 40.0)
    elif phase == "declining":
        score = min(score, 35.0)
    diagnostics.update(
        {
            "industry_cycle_date": row.get("date").isoformat() if hasattr(row.get("date"), "isoformat") else row.get("date"),
            "industry_cycle_phase": phase,
            "industry_cycle_raw_score": raw_score,
            "industry_cycle_quality": quality,
        }
    )
    return max(0.0, min(100.0, score)), [], diagnostics


def build_feature_set(
    price_df: pd.DataFrame,
    as_of_date: Any,
    valuation_df: Optional[pd.DataFrame] = None,
    financial_df: Optional[pd.DataFrame] = None,
    benchmark_df: Optional[pd.DataFrame] = None,
    industry_cycle_df: Optional[pd.DataFrame] = None,
    industry: Optional[str] = None,
) -> FeatureSet:
    target = coerce_date(as_of_date)
    history = slice_as_of(price_df, target)
    close = finite_float(history.iloc[-1].get("close")) if not history.empty else None
    features = FeatureSet(as_of_date=target, close=close)

    if close is None:
        features.missing_fields.append("close")
        features.risk_flags.append("missing_close")
        return features

    price_score, percentiles, price_missing = compute_price_percentile_score(history, close)
    industry_score, industry_missing, industry_diag = compute_industry_cycle_score(industry_cycle_df, industry, target)
    valuation_score, valuation_missing, valuation_diag = compute_valuation_score(valuation_df, target, industry=industry)
    financial_score, financial_missing, financial_risks, financial_diag = compute_financial_safety_score(financial_df, target)
    trend_score, trend_diag, trend_missing, trend_risks = compute_trend_stabilization_score(history)
    market_score, market_missing, market_diag = compute_market_environment_score(benchmark_df, target)
    value_trap_diag = compute_value_trap_diagnostics(
        valuation_diagnostics=valuation_diag,
        financial_diagnostics=financial_diag,
        financial_missing=financial_missing,
        financial_risks=financial_risks,
        price_percentile_5y=percentiles.get("price_percentile_5y"),
        valuation_score=valuation_score,
    )

    features.price_percentile_score = price_score
    features.valuation_score = valuation_score
    features.financial_safety_score = financial_score
    features.trend_stabilization_score = trend_score
    features.market_environment_score = market_score
    features.industry_cycle_score = industry_score
    features.price_percentile_3y = percentiles.get("price_percentile_3y")
    features.price_percentile_5y = percentiles.get("price_percentile_5y")
    features.price_percentile_10y = percentiles.get("price_percentile_10y")
    features.distance_from_5y_low_pct = percentiles.get("distance_from_5y_low_pct")
    features.distance_from_5y_high_pct = percentiles.get("distance_from_5y_high_pct")
    features.distance_from_10y_low_pct = percentiles.get("distance_from_10y_low_pct")
    features.distance_from_10y_high_pct = percentiles.get("distance_from_10y_high_pct")
    features.ma20 = trend_diag.get("ma20")
    features.ma60 = trend_diag.get("ma60")
    features.ma120 = trend_diag.get("ma120")
    features.ma250 = trend_diag.get("ma250")
    features.stabilization_days = int(trend_diag.get("stabilization_days") or 0)
    features.downtrend_exhaustion_score = float(trend_diag.get("downtrend_exhaustion_score") or 0.0)
    features.reclaim_ma_score = float(trend_diag.get("reclaim_ma_score") or 0.0)
    features.no_falling_knife_filter = bool(trend_diag.get("no_falling_knife_filter"))
    features.second_low_confirmation = bool(trend_diag.get("second_low_confirmation"))
    features.trend_confirmation_level = str(trend_diag.get("trend_confirmation_level") or "NONE")
    features.dynamic_stop_loss = estimate_stop_loss(close, features.ma60)
    features.invalidation_level = features.dynamic_stop_loss
    if features.dynamic_stop_loss is not None and close > 0:
        features.stop_loss_distance_pct = round((close - features.dynamic_stop_loss) / close * 100.0, 4)
    features.value_trap_score = float(value_trap_diag.get("value_trap_score") or 0.0)
    features.value_trap_flag = bool(value_trap_diag.get("value_trap_flag"))
    features.valuation_repair_signal = bool(value_trap_diag.get("valuation_repair_signal"))
    features.industry = industry
    features.industry_cycle_phase = industry_diag.get("industry_cycle_phase")
    features.industry_cycle_quality = str(industry_diag.get("industry_cycle_quality") or "missing")
    features.market_environment_state = market_diag.get("market_environment_state")
    features.execution_risk_score = 0.0
    features.missing_fields = sorted(set(price_missing + valuation_missing + financial_missing + trend_missing + market_missing + industry_missing))
    features.risk_flags = sorted(
        set(
            financial_risks
            + trend_risks
            + (["value_trap_risk"] if features.value_trap_flag else [])
            + (["missing_financial_uncertain"] if "financial" in financial_missing else [])
        )
    )
    features.diagnostics.update(valuation_diag)
    features.diagnostics.update(financial_diag)
    features.diagnostics.update(trend_diag)
    features.diagnostics.update(market_diag)
    features.diagnostics.update(industry_diag)
    features.diagnostics.update(value_trap_diag)
    features.diagnostics.update(
        {
            "dynamic_stop_loss": features.dynamic_stop_loss,
            "stop_loss_distance_pct": features.stop_loss_distance_pct,
            "invalidation_level": features.invalidation_level,
        }
    )
    return features


def estimate_stop_loss(close: Optional[float], ma60: Optional[float]) -> Optional[float]:
    close_value = finite_float(close)
    if close_value is None:
        return None
    ma_stop = ma60 * 0.97 if ma60 else close_value * 0.9
    return round(max(close_value * 0.88, ma_stop), 2)


def estimate_take_profit(close: Optional[float]) -> Optional[float]:
    close_value = finite_float(close)
    if close_value is None:
        return None
    return round(close_value * 1.25, 2)


def date_years_ago(end_date: date, years: int) -> date:
    return end_date - timedelta(days=int(years * 365.25))
