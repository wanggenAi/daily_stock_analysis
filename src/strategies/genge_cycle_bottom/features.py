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


PRICE_MIN_OBSERVATIONS = 120
TRADING_DAYS_PER_YEAR = 250


@dataclass
class FeatureSet:
    as_of_date: date
    close: Optional[float]
    price_percentile_score: float = 0.0
    valuation_score: float = 0.0
    financial_safety_score: float = 0.0
    trend_stabilization_score: float = 0.0
    market_environment_score: float = 0.0
    price_percentile_3y: Optional[float] = None
    price_percentile_5y: Optional[float] = None
    price_percentile_10y: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma120: Optional[float] = None
    ma250: Optional[float] = None
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


def compute_price_percentile_score(history: pd.DataFrame, current_close: float) -> Tuple[float, Dict[str, Optional[float]], List[str]]:
    percentiles: Dict[str, Optional[float]] = {}
    missing: List[str] = []

    for years in (3, 5, 10):
        window = history.tail(years * TRADING_DAYS_PER_YEAR)
        key = f"price_percentile_{years}y"
        if len(window) < PRICE_MIN_OBSERVATIONS:
            percentiles[key] = None
            missing.append(key)
            continue
        percentiles[key] = percentile_rank(window["close"], current_close)

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


def compute_valuation_score(valuation_df: Optional[pd.DataFrame], as_of_date: date) -> Tuple[float, List[str], Dict[str, Any]]:
    missing: List[str] = []
    diagnostics: Dict[str, Any] = {}
    row = _latest_row_as_of(valuation_df, as_of_date)
    if row is None:
        return 35.0, ["valuation"], diagnostics

    scores: List[float] = []
    for field_name in ("pb", "pe", "ps", "market_cap"):
        if field_name not in row.index:
            missing.append(field_name)
            continue
        value = finite_float(row.get(field_name))
        if value is None or value <= 0:
            missing.append(field_name)
            continue
        diagnostics[field_name] = value
        if field_name == "pb":
            scores.append(90.0 if value <= 1.2 else 75.0 if value <= 2.0 else 50.0 if value <= 4.0 else 25.0)
        elif field_name == "pe":
            scores.append(85.0 if value <= 15 else 70.0 if value <= 30 else 45.0 if value <= 60 else 20.0)
        elif field_name == "ps":
            scores.append(80.0 if value <= 1.5 else 65.0 if value <= 3.0 else 45.0 if value <= 6.0 else 20.0)
        else:
            scores.append(50.0)

    if not scores:
        return 35.0, missing or ["valuation"], diagnostics
    penalty = min(15.0, len(missing) * 3.0)
    return max(0.0, float(np.mean(scores)) - penalty), missing, diagnostics


def compute_financial_safety_score(financial_df: Optional[pd.DataFrame], as_of_date: date) -> Tuple[float, List[str], List[str], Dict[str, Any]]:
    missing: List[str] = []
    risk_flags: List[str] = []
    diagnostics: Dict[str, Any] = {}
    row = _latest_row_as_of(financial_df, as_of_date, date_column="report_date")
    if row is None:
        return 45.0, ["financial"], risk_flags, diagnostics

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
        return 50.0, ["benchmark"], {}
    history = slice_as_of(benchmark_history, as_of_date)
    if history.empty:
        return 50.0, ["benchmark"], {}
    close = finite_float(history.iloc[-1].get("close"))
    ma20 = _moving_average(history, 20)
    ma60 = _moving_average(history, 60)
    ma120 = _moving_average(history, 120)
    diagnostics = {"benchmark_ma20": ma20, "benchmark_ma60": ma60, "benchmark_ma120": ma120}
    if close is None or ma20 is None or ma60 is None:
        return 50.0, ["benchmark_ma"], diagnostics

    score = 45.0
    if close >= ma20:
        score += 15
    if close >= ma60:
        score += 20
    if ma120 is not None and close >= ma120:
        score += 10
    if close < ma20 and close < ma60:
        score -= 20
    return max(0.0, min(100.0, score)), [], diagnostics


def build_feature_set(
    price_df: pd.DataFrame,
    as_of_date: Any,
    valuation_df: Optional[pd.DataFrame] = None,
    financial_df: Optional[pd.DataFrame] = None,
    benchmark_df: Optional[pd.DataFrame] = None,
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
    valuation_score, valuation_missing, valuation_diag = compute_valuation_score(valuation_df, target)
    financial_score, financial_missing, financial_risks, financial_diag = compute_financial_safety_score(financial_df, target)
    trend_score, trend_diag, trend_missing, trend_risks = compute_trend_stabilization_score(history)
    market_score, market_missing, market_diag = compute_market_environment_score(benchmark_df, target)

    features.price_percentile_score = price_score
    features.valuation_score = valuation_score
    features.financial_safety_score = financial_score
    features.trend_stabilization_score = trend_score
    features.market_environment_score = market_score
    features.price_percentile_3y = percentiles.get("price_percentile_3y")
    features.price_percentile_5y = percentiles.get("price_percentile_5y")
    features.price_percentile_10y = percentiles.get("price_percentile_10y")
    features.ma20 = trend_diag.get("ma20")
    features.ma60 = trend_diag.get("ma60")
    features.ma120 = trend_diag.get("ma120")
    features.ma250 = trend_diag.get("ma250")
    features.missing_fields = sorted(set(price_missing + valuation_missing + financial_missing + trend_missing + market_missing))
    features.risk_flags = sorted(set(financial_risks + trend_risks))
    features.diagnostics.update(valuation_diag)
    features.diagnostics.update(financial_diag)
    features.diagnostics.update(trend_diag)
    features.diagnostics.update(market_diag)
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

