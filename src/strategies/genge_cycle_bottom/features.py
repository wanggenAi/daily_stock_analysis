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
    industry: Optional[str] = None
    industry_cycle_phase: Optional[str] = None
    market_environment_state: Optional[str] = None
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
    has_disclosure_columns = any(column in local.columns for column in DISCLOSURE_DATE_COLUMNS)
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


def compute_trend_stabilization_score(history: pd.DataFrame) -> Tuple[float, Dict[str, Optional[float]], List[str], List[str]]:
    missing: List[str] = []
    risk_flags: List[str] = []
    diagnostics: Dict[str, Optional[float]] = {}
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
    diagnostics: Dict[str, Any] = {"industry": industry}
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
    features.industry = industry
    features.industry_cycle_phase = industry_diag.get("industry_cycle_phase")
    features.market_environment_state = market_diag.get("market_environment_state")
    features.missing_fields = sorted(set(price_missing + valuation_missing + financial_missing + trend_missing + market_missing + industry_missing))
    features.risk_flags = sorted(set(financial_risks + trend_risks))
    features.diagnostics.update(valuation_diag)
    features.diagnostics.update(financial_diag)
    features.diagnostics.update(trend_diag)
    features.diagnostics.update(market_diag)
    features.diagnostics.update(industry_diag)
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
