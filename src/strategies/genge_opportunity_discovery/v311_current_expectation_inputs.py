"""Current-date strict-PIT inputs for the validated GenGe V3.1.1 policy.

This is an engineering extraction of the economic formula frozen before the
successful Round-6/7/8/9 expectation-gap tests.  It does not invent a new
valuation model and it does not fill qualitative V3.1 judgements.

Financial availability contract:
- profit and cash-flow statements are fetched by report period;
- availability is the later NOTICE_DATE of the statements used;
- UPDATE_DATE is deliberately ignored;
- Q1/H1/Q3 TTM = current cumulative + prior FY - prior-year same period;
- annual TTM = the annual cumulative value.

Valuation contract (unchanged from Round 6):
- normalized clean EPS = rolling median of the latest four positive
  ``TTM basic EPS * clip(deduct_quality, 0, 1)`` observations, min 2;
- realistic growth = clip(min(~3y normalized-EPS CAGR,
  ~3y TTM-revenue CAGR + 5pp), 0%, 30%);
- ten-year earning-power value at 10% discount rate, growth fading linearly to
  3%, terminal multiple 1/(10%-3%);
- market-implied starting growth is reverse-solved on 0%-100% with the same
  equation;
- expectation gap = realistic growth - market-implied growth.

The module emits only evidence-backed numeric inputs and confidence diagnostics.
It never fabricates moat/demand gates, scenario valuation, expectation-gap
thesis, risk-adjusted CAGR or other qualitative V3.1 BUY evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


POLICY_SOURCE = "round6_expectation_gap_10y_strict_pit_frozen"
DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON_YEARS = 10
REALISTIC_GROWTH_CAP = 0.30
REVENUE_GROWTH_ALLOWANCE = 0.05
IMPLIED_GROWTH_MAX = 1.00

PROFIT_COLUMNS = [
    "PARENT_NETPROFIT",
    "DEDUCT_PARENT_NETPROFIT",
    "BASIC_EPS",
    "TOTAL_OPERATE_INCOME",
]
CASH_COLUMNS = ["NETCASH_OPERATE"]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_observed_trade_date(value: Any) -> date | None:
    """Normalize a provider/source observation date without inventing one."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "nat", "none"}:
        return None
    # Common vendor integer/string format: YYYYMMDD.
    digits = raw.split(".", 1)[0]
    if len(digits) == 8 and digits.isdigit():
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    try:
        return pd.Timestamp(parsed).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _normalize_code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _em_symbol(code: str) -> str:
    return ("SH" if code.startswith("6") else "SZ") + code


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_holdings_codes(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    result: list[str] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Code | Name | Quantity |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("| ---"):
            continue
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells:
            code = _normalize_code(cells[0])
            if code:
                result.append(code)
    return result


def _prepare_statement(
    frame: pd.DataFrame,
    value_columns: Iterable[str],
    prefix: str,
) -> pd.DataFrame:
    required = ["REPORT_DATE", "NOTICE_DATE"]
    if frame is None or frame.empty or any(column not in frame.columns for column in required):
        return pd.DataFrame(columns=["REPORT_DATE", "NOTICE_DATE"])
    value_columns = [column for column in value_columns if column in frame.columns]
    local = frame[required + value_columns].copy()
    local["REPORT_DATE"] = pd.to_datetime(local["REPORT_DATE"], errors="coerce").dt.normalize()
    local["NOTICE_DATE"] = pd.to_datetime(local["NOTICE_DATE"], errors="coerce").dt.normalize()
    local = local.dropna(subset=["REPORT_DATE", "NOTICE_DATE"])
    local = local.sort_values(["REPORT_DATE", "NOTICE_DATE"])
    # A later database revision must never move the historical availability
    # boundary. Keep the earliest notice for a duplicated report period.
    local = local.drop_duplicates("REPORT_DATE", keep="first")
    renamed = {column: f"{prefix}{column}" for column in value_columns}
    local = local.rename(columns=renamed)
    for column in renamed.values():
        local[column] = pd.to_numeric(local[column], errors="coerce")
    return local


def _ttm_from_cumulative(frame: pd.DataFrame, column: str) -> pd.Series:
    by_date = {
        pd.Timestamp(report_date): value
        for report_date, value in zip(frame["report_date"], frame[column])
    }
    result: list[float] = []
    for report_date, current in zip(frame["report_date"], frame[column]):
        report_date = pd.Timestamp(report_date)
        if pd.isna(current):
            result.append(np.nan)
            continue
        if report_date.month == 12 and report_date.day == 31:
            result.append(float(current))
            continue
        prior_fy = pd.Timestamp(year=report_date.year - 1, month=12, day=31)
        prior_same = pd.Timestamp(
            year=report_date.year - 1,
            month=report_date.month,
            day=report_date.day,
        )
        fy_value = by_date.get(prior_fy, np.nan)
        same_value = by_date.get(prior_same, np.nan)
        if pd.isna(fy_value) or pd.isna(same_value):
            result.append(np.nan)
        else:
            result.append(float(current) + float(fy_value) - float(same_value))
    return pd.Series(result, index=frame.index, dtype=float)


def build_strict_pit_financial_panel(
    profit_raw: pd.DataFrame,
    cash_raw: pd.DataFrame,
) -> pd.DataFrame:
    """Build the exact strict-PIT financial state used by Round 6+."""
    profit = _prepare_statement(profit_raw, PROFIT_COLUMNS, "p_")
    cash = _prepare_statement(cash_raw, CASH_COLUMNS, "c_")
    if profit.empty and cash.empty:
        return pd.DataFrame()

    frame = profit.merge(
        cash,
        on="REPORT_DATE",
        how="outer",
        suffixes=("_profit", "_cash"),
    ).sort_values("REPORT_DATE")
    frame["profit_notice_date"] = pd.to_datetime(
        frame.get("NOTICE_DATE_profit"), errors="coerce"
    ).dt.normalize()
    frame["cash_notice_date"] = pd.to_datetime(
        frame.get("NOTICE_DATE_cash"), errors="coerce"
    ).dt.normalize()
    frame["available_date"] = frame[["profit_notice_date", "cash_notice_date"]].max(axis=1)
    frame = frame.rename(columns={"REPORT_DATE": "report_date"})

    numeric_columns = [
        "p_PARENT_NETPROFIT",
        "p_DEDUCT_PARENT_NETPROFIT",
        "p_BASIC_EPS",
        "p_TOTAL_OPERATE_INCOME",
        "c_NETCASH_OPERATE",
    ]
    for column in numeric_columns:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["ttm_parent_netprofit"] = _ttm_from_cumulative(frame, "p_PARENT_NETPROFIT")
    frame["ttm_deduct_netprofit"] = _ttm_from_cumulative(frame, "p_DEDUCT_PARENT_NETPROFIT")
    frame["ttm_basic_eps_approx"] = _ttm_from_cumulative(frame, "p_BASIC_EPS")
    frame["ttm_revenue"] = _ttm_from_cumulative(frame, "p_TOTAL_OPERATE_INCOME")
    frame["ttm_operating_cashflow"] = _ttm_from_cumulative(frame, "c_NETCASH_OPERATE")
    frame["deduct_quality"] = frame["ttm_deduct_netprofit"] / frame[
        "ttm_parent_netprofit"
    ].replace(0, np.nan)
    frame["cash_conversion"] = frame["ttm_operating_cashflow"] / frame[
        "ttm_parent_netprofit"
    ].replace(0, np.nan)

    eps = pd.to_numeric(frame["ttm_basic_eps_approx"], errors="coerce")
    parent_np = pd.to_numeric(frame["ttm_parent_netprofit"], errors="coerce")
    deduct_quality = pd.to_numeric(frame["deduct_quality"], errors="coerce")
    valid = (eps > 0) & (parent_np > 0) & (deduct_quality > 0)
    frame["deduct_factor_round6"] = deduct_quality.clip(0.0, 1.0).where(valid)
    frame["clean_eps_round6"] = (eps * frame["deduct_factor_round6"]).where(valid)
    positive_clean = frame["clean_eps_round6"].where(frame["clean_eps_round6"] > 0)
    frame["normalized_eps_round6"] = positive_clean.rolling(4, min_periods=2).median()
    frame["normalized_earnings_observation_count"] = positive_clean.notna().rolling(
        4, min_periods=1
    ).sum()

    eps_growth, revenue_growth, realistic_growth = _round6_growth_series(frame)
    frame["eps_growth_3y_round6"] = eps_growth
    frame["revenue_growth_3y_round6"] = revenue_growth
    frame["realistic_growth_round6"] = realistic_growth
    growth = pd.to_numeric(frame["realistic_growth_round6"], errors="coerce")
    frame["realistic_growth_four_report_range"] = (
        growth.rolling(4, min_periods=3).max()
        - growth.rolling(4, min_periods=3).min()
    )
    frame["neutral_value_round6"] = [
        value_expectation_10y(eps_value, growth_value)
        for eps_value, growth_value in zip(
            frame["normalized_eps_round6"], frame["realistic_growth_round6"]
        )
    ]
    return frame.sort_values("report_date").reset_index(drop=True)


def _cagr(current: float, past: float, years: float) -> float:
    if (
        not np.isfinite(current)
        or not np.isfinite(past)
        or current <= 0
        or past <= 0
        or years <= 0
    ):
        return np.nan
    return float((current / past) ** (1.0 / years) - 1.0)


def _round6_growth_series(frame: pd.DataFrame) -> tuple[list[float], list[float], list[float]]:
    report_dates = pd.to_datetime(frame["report_date"], errors="coerce")
    available_dates = pd.to_datetime(frame["available_date"], errors="coerce")
    normalized = pd.to_numeric(frame["normalized_eps_round6"], errors="coerce")
    revenue = pd.to_numeric(frame["ttm_revenue"], errors="coerce")
    eps_growth: list[float] = []
    revenue_growth: list[float] = []
    realistic_growth: list[float] = []

    for i, (report_date, available_date, current_eps, current_revenue) in enumerate(
        zip(report_dates, available_dates, normalized, revenue)
    ):
        if (
            pd.isna(report_date)
            or pd.isna(available_date)
            or pd.isna(current_eps)
            or pd.isna(current_revenue)
            or current_eps <= 0
            or current_revenue <= 0
        ):
            eps_growth.append(np.nan)
            revenue_growth.append(np.nan)
            realistic_growth.append(np.nan)
            continue
        cutoff = report_date - pd.DateOffset(years=3)
        candidates = [
            j
            for j in range(i)
            if pd.notna(report_dates.iloc[j])
            and pd.notna(available_dates.iloc[j])
            and report_dates.iloc[j] <= cutoff
            and available_dates.iloc[j] <= available_date
            and pd.notna(normalized.iloc[j])
            and normalized.iloc[j] > 0
            and pd.notna(revenue.iloc[j])
            and revenue.iloc[j] > 0
        ]
        if not candidates:
            eps_growth.append(np.nan)
            revenue_growth.append(np.nan)
            realistic_growth.append(np.nan)
            continue
        j = candidates[-1]
        years = max((report_date - report_dates.iloc[j]).days / 365.25, 0.01)
        eps_cagr = _cagr(float(current_eps), float(normalized.iloc[j]), years)
        revenue_cagr = _cagr(float(current_revenue), float(revenue.iloc[j]), years)
        eps_growth.append(eps_cagr)
        revenue_growth.append(revenue_cagr)
        if np.isfinite(eps_cagr) and np.isfinite(revenue_cagr):
            supportable = min(eps_cagr, revenue_cagr + REVENUE_GROWTH_ALLOWANCE)
            realistic_growth.append(
                float(np.clip(supportable, 0.0, REALISTIC_GROWTH_CAP))
            )
        else:
            realistic_growth.append(np.nan)
    return eps_growth, revenue_growth, realistic_growth


def value_expectation_10y(normalized_eps: float, start_growth: float) -> float:
    """Exact Round-6 ten-year earning-power valuation equation."""
    if not np.isfinite(normalized_eps) or normalized_eps <= 0:
        return np.nan
    if not np.isfinite(start_growth):
        return np.nan
    growth = float(np.clip(start_growth, 0.0, IMPLIED_GROWTH_MAX))
    earnings = float(normalized_eps)
    present_value = 0.0
    for year in range(1, HORIZON_YEARS + 1):
        if year == 1:
            year_growth = growth
        else:
            fraction = (year - 1) / (HORIZON_YEARS - 1)
            year_growth = growth + (TERMINAL_GROWTH - growth) * fraction
        earnings *= 1.0 + year_growth
        present_value += earnings / ((1.0 + DISCOUNT_RATE) ** year)
    terminal_multiple = 1.0 / (DISCOUNT_RATE - TERMINAL_GROWTH)
    present_value += (
        terminal_multiple
        * earnings
        / ((1.0 + DISCOUNT_RATE) ** HORIZON_YEARS)
    )
    return float(present_value)


def solve_market_implied_growth(price: float, normalized_eps: float) -> tuple[float, str]:
    if (
        not np.isfinite(price)
        or price <= 0
        or not np.isfinite(normalized_eps)
        or normalized_eps <= 0
    ):
        return np.nan, "INPUT_INCOMPLETE"
    zero_growth_value = value_expectation_10y(normalized_eps, 0.0)
    max_growth_value = value_expectation_10y(normalized_eps, IMPLIED_GROWTH_MAX)
    if not np.isfinite(zero_growth_value) or not np.isfinite(max_growth_value):
        return np.nan, "INPUT_INCOMPLETE"
    if price <= zero_growth_value:
        return 0.0, "BELOW_ZERO_GROWTH_VALUE"
    if price > max_growth_value:
        return np.nan, "IMPLIED_ABOVE_SEARCH_RANGE"
    low, high = 0.0, IMPLIED_GROWTH_MAX
    for _ in range(60):
        midpoint = (low + high) / 2.0
        if value_expectation_10y(normalized_eps, midpoint) < price:
            low = midpoint
        else:
            high = midpoint
    return float((low + high) / 2.0), "SOLVED"


def current_inputs_from_panel(
    code: str,
    panel: pd.DataFrame,
    *,
    current_price: float | None,
    as_of: date,
    price_source: str,
    price_date: Any = None,
) -> dict[str, Any]:
    code = _normalize_code(code)
    observed_price_date = _parse_observed_trade_date(price_date)
    as_of_ts = pd.Timestamp(as_of)
    if panel is None or panel.empty:
        return _invalid_row(
            code,
            current_price,
            as_of,
            price_source,
            "FINANCIAL_DATA_UNAVAILABLE",
            price_date=observed_price_date,
        )
    local = panel.copy()
    local["available_date"] = pd.to_datetime(local["available_date"], errors="coerce").dt.normalize()
    local = local[local["available_date"].notna() & (local["available_date"] <= as_of_ts)]
    if local.empty:
        return _invalid_row(
            code,
            current_price,
            as_of,
            price_source,
            "NO_FINANCIAL_REPORT_AVAILABLE_AS_OF_DATE",
            price_date=observed_price_date,
        )
    latest = local.sort_values(["available_date", "report_date"]).iloc[-1]
    normalized = _finite(latest.get("normalized_eps_round6"))
    realistic = _finite(latest.get("realistic_growth_round6"))
    neutral = _finite(latest.get("neutral_value_round6"))
    price = _finite(current_price)
    if price is None or price <= 0:
        implied, implied_status = np.nan, "INPUT_INCOMPLETE"
    else:
        implied, implied_status = solve_market_implied_growth(
            float(price), float(normalized) if normalized is not None else np.nan
        )
    expectation_gap = (
        float(realistic - implied)
        if realistic is not None and np.isfinite(implied)
        else np.nan
    )
    ratio = (
        float(price / neutral)
        if price is not None and neutral is not None and price > 0 and neutral > 0
        else np.nan
    )
    report_date = pd.to_datetime(latest.get("report_date"), errors="coerce")
    available_date = pd.to_datetime(latest.get("available_date"), errors="coerce")

    price_error = ""
    if observed_price_date is None:
        price_error = "PRICE_DATE_UNVERIFIED"
    elif observed_price_date > as_of:
        price_error = "PRICE_DATE_AFTER_DECISION_DATE"
    elif price is None or price <= 0:
        price_error = "PRICE_INPUT_INCOMPLETE"

    numeric_ready = (
        all(value is not None for value in (price, normalized, realistic, neutral))
        and np.isfinite(implied)
    )
    input_error = price_error
    if not input_error and implied_status == "INPUT_INCOMPLETE":
        input_error = "IMPLIED_GROWTH_INPUT_INCOMPLETE"
    ready = numeric_ready and not input_error

    return {
        "code": code,
        "v311_expectation_input_status": "READY" if ready else "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_expectation_policy_source": POLICY_SOURCE,
        "decision_date": as_of.isoformat(),
        # Price freshness is evidence, not an alias for the decision date.
        "price_date": observed_price_date.isoformat() if observed_price_date is not None else "",
        "fund_available_date": available_date.date().isoformat()
        if not pd.isna(available_date)
        else "",
        "financial_report_date": report_date.date().isoformat()
        if not pd.isna(report_date)
        else "",
        "current_price_source": price_source,
        "v31_current_price": price,
        "v31_normalized_profit": normalized,
        "v31_normalized_profit_method": "STRICT_PIT_NORMALIZED_CLEAN_EPS_ROUND6",
        "v31_neutral_value": neutral,
        "v31_realistic_profit_cagr": realistic,
        "v31_market_implied_profit_cagr": implied if np.isfinite(implied) else None,
        "v31_expectation_gap_pct": expectation_gap if np.isfinite(expectation_gap) else None,
        "normalized_earnings": normalized,
        "realistic_growth": realistic,
        "market_implied_growth": implied if np.isfinite(implied) else None,
        "expectation_gap": expectation_gap if np.isfinite(expectation_gap) else None,
        "neutral_value": neutral,
        "price_to_neutral": ratio if np.isfinite(ratio) else None,
        "normalized_earnings_observation_count": _finite(
            latest.get("normalized_earnings_observation_count")
        ),
        "deduct_profit_quality_factor": _finite(latest.get("deduct_factor_round6")),
        "cash_conversion_ratio": _finite(latest.get("cash_conversion")),
        "realistic_growth_four_report_range": _finite(
            latest.get("realistic_growth_four_report_range")
        ),
        "implied_growth_status": implied_status,
        "eps_growth_3y_round6": _finite(latest.get("eps_growth_3y_round6")),
        "revenue_growth_3y_round6": _finite(latest.get("revenue_growth_3y_round6")),
        "v311_input_error": input_error,
    }


def _invalid_row(
    code: str,
    current_price: float | None,
    as_of: date,
    price_source: str,
    error: str,
    *,
    price_date: Any = None,
) -> dict[str, Any]:
    observed_price_date = _parse_observed_trade_date(price_date)
    return {
        "code": _normalize_code(code),
        "v311_expectation_input_status": "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_expectation_policy_source": POLICY_SOURCE,
        "decision_date": as_of.isoformat(),
        "price_date": observed_price_date.isoformat() if observed_price_date is not None else "",
        "fund_available_date": "",
        "financial_report_date": "",
        "current_price_source": price_source,
        "v31_current_price": current_price,
        "v31_normalized_profit": None,
        "v31_normalized_profit_method": "",
        "v31_neutral_value": None,
        "v31_realistic_profit_cagr": None,
        "v31_market_implied_profit_cagr": None,
        "v31_expectation_gap_pct": None,
        "normalized_earnings": None,
        "realistic_growth": None,
        "market_implied_growth": None,
        "expectation_gap": None,
        "neutral_value": None,
        "price_to_neutral": None,
        "normalized_earnings_observation_count": None,
        "deduct_profit_quality_factor": None,
        "cash_conversion_ratio": None,
        "realistic_growth_four_report_range": None,
        "implied_growth_status": "INPUT_INCOMPLETE",
        "eps_growth_3y_round6": None,
        "revenue_growth_3y_round6": None,
        "v311_input_error": error,
    }


def _fetch_with_retry(function, *, symbol: str, tries: int = 3) -> pd.DataFrame:
    errors: list[str] = []
    for attempt in range(tries):
        try:
            frame = function(symbol=symbol)
            if frame is None or frame.empty:
                raise RuntimeError("empty dataframe")
            return frame
        except Exception as exc:  # network/provider boundary
            errors.append(f"{type(exc).__name__}: {exc}")
            time.sleep(1 + attempt)
    raise RuntimeError(" | ".join(errors))


def fetch_financial_panel(code: str) -> pd.DataFrame:
    import akshare as ak

    symbol = _em_symbol(_normalize_code(code))
    profit = _fetch_with_retry(ak.stock_profit_sheet_by_report_em, symbol=symbol)
    cash = _fetch_with_retry(ak.stock_cash_flow_sheet_by_report_em, symbol=symbol)
    return build_strict_pit_financial_panel(profit, cash)


def fetch_latest_close(code: str, *, as_of: date) -> tuple[float | None, str, str]:
    import akshare as ak

    start = (as_of - timedelta(days=30)).strftime("%Y%m%d")
    end = as_of.strftime("%Y%m%d")
    try:
        frame = ak.stock_zh_a_hist(
            symbol=_normalize_code(code),
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        if frame is None or frame.empty:
            return None, "AKSHARE_QFQ_EMPTY", ""
        date_column = "日期" if "日期" in frame.columns else "date"
        close_column = "收盘" if "收盘" in frame.columns else "close"
        if date_column not in frame.columns or close_column not in frame.columns:
            return None, "AKSHARE_QFQ_SCHEMA_MISMATCH", ""
        local = frame[[date_column, close_column]].copy()
        local[date_column] = pd.to_datetime(local[date_column], errors="coerce").dt.date
        local[close_column] = pd.to_numeric(local[close_column], errors="coerce")
        local = local.dropna().loc[lambda x: x[date_column] <= as_of]
        if local.empty:
            return None, "AKSHARE_QFQ_NO_ASOF_PRICE", ""
        latest = local.sort_values(date_column).iloc[-1]
        observed = _parse_observed_trade_date(latest[date_column])
        return (
            float(latest[close_column]),
            "AKSHARE_QFQ_DAILY",
            observed.isoformat() if observed is not None else "",
        )
    except Exception as exc:  # network/provider boundary
        return None, f"AKSHARE_QFQ_ERROR:{type(exc).__name__}", ""


def _source_price_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[float, str]]:
    price_fields = (
        ("raw_latest_close", ("raw_latest_trade_date", "latest_trade_date", "price_date")),
        ("v31_current_price", ("price_date", "latest_trade_date", "raw_latest_trade_date")),
        ("current_price", ("price_date", "latest_trade_date", "raw_latest_trade_date")),
        ("close", ("trade_date", "price_date", "latest_trade_date")),
        ("latest_close", ("latest_trade_date", "price_date", "trade_date")),
    )
    result: dict[str, tuple[float, str]] = {}
    for row in rows:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        for price_field, date_fields in price_fields:
            value = _finite(row.get(price_field))
            if value is None or value <= 0:
                continue
            observed: date | None = None
            for date_field in date_fields:
                observed = _parse_observed_trade_date(row.get(date_field))
                if observed is not None:
                    break
            result[code] = (value, observed.isoformat() if observed is not None else "")
            break
    return result


def _normalize_price_loader_result(value: Any) -> tuple[float | None, str, str]:
    """Accept legacy 2-tuples but never infer a missing observation date."""
    if not isinstance(value, (tuple, list)):
        raise ValueError("price loader must return (price, source[, observed_date])")
    if len(value) == 2:
        price, source = value
        observed = ""
    elif len(value) == 3:
        price, source, observed = value
    else:
        raise ValueError("price loader must return 2 or 3 values")
    numeric = _finite(price)
    parsed = _parse_observed_trade_date(observed)
    return numeric, _text(source), parsed.isoformat() if parsed is not None else ""


def build_current_expectation_rows(
    codes: Iterable[str],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    as_of: date,
    financial_loader=fetch_financial_panel,
    price_loader=fetch_latest_close,
) -> list[dict[str, Any]]:
    source_rows = list(source_rows)
    price_map = _source_price_map(source_rows)
    rows: list[dict[str, Any]] = []
    for code in dict.fromkeys(_normalize_code(value) for value in codes if _normalize_code(value)):
        upstream_price = price_map.get(code)
        price: float | None = upstream_price[0] if upstream_price is not None else None
        price_date = upstream_price[1] if upstream_price is not None else ""
        price_source = "UPSTREAM_RAW_LATEST_CLOSE" if price is not None else ""

        # An upstream price without an observed trade date is not production-safe.
        # Prefer an independently dated provider observation when available.
        if price is None or not price_date:
            try:
                fetched_price, fetched_source, fetched_date = _normalize_price_loader_result(
                    price_loader(code, as_of=as_of)
                )
                if fetched_price is not None and fetched_price > 0:
                    price = fetched_price
                    price_source = fetched_source
                    price_date = fetched_date
                elif price is None:
                    price_source = fetched_source
            except Exception as exc:
                if price is None:
                    price_source = f"PRICE_FETCH_ERROR:{type(exc).__name__}"

        try:
            panel = financial_loader(code)
            row = current_inputs_from_panel(
                code,
                panel,
                current_price=price,
                as_of=as_of,
                price_source=price_source,
                price_date=price_date,
            )
        except Exception as exc:  # provider failures are safe HOLD_REVIEW inputs
            row = _invalid_row(
                code,
                price,
                as_of,
                price_source,
                f"FINANCIAL_FETCH_ERROR:{type(exc).__name__}:{exc}",
                price_date=price_date,
            )
        rows.append(row)
    return rows


def write_current_expectation_inputs(
    source_csv: Path,
    output_dir: Path,
    *,
    codes_csv: Path | None = None,
    holdings_md: Path | None = None,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    source_rows = _read_csv(source_csv)
    code_rows = _read_csv(codes_csv) if codes_csv else source_rows
    codes = [_normalize_code(row.get("code")) for row in code_rows]
    codes.extend(_read_holdings_codes(holdings_md))
    as_of = as_of or date.today()
    rows = build_current_expectation_rows(codes, source_rows=source_rows, as_of=as_of)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    output_csv = output_dir / "v311_current_expectation_inputs.csv"
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "policy_source": POLICY_SOURCE,
        "as_of": as_of.isoformat(),
        "row_count": len(rows),
        "ready_count": sum(row["v311_expectation_input_status"] == "READY" for row in rows),
        "hold_review_input_count": sum(
            row["v311_expectation_input_status"] != "READY" for row in rows
        ),
        "implied_status_counts": {
            status: sum(row.get("implied_growth_status") == status for row in rows)
            for status in sorted({str(row.get("implied_growth_status") or "") for row in rows})
        },
        "economic_parameters": {
            "discount_rate": DISCOUNT_RATE,
            "terminal_growth": TERMINAL_GROWTH,
            "horizon_years": HORIZON_YEARS,
            "realistic_growth_cap": REALISTIC_GROWTH_CAP,
            "revenue_growth_allowance": REVENUE_GROWTH_ALLOWANCE,
            "implied_growth_max": IMPLIED_GROWTH_MAX,
        },
        "qualitative_v31_fields_fabricated": False,
        "scenario_valuation_fabricated": False,
    }
    (output_dir / "v311_current_expectation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--codes-csv", type=Path)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    rows = write_current_expectation_inputs(
        args.source_csv,
        args.output_dir,
        codes_csv=args.codes_csv,
        holdings_md=args.holdings_md,
        as_of=as_of,
    )
    print(f"v311_current_expectation_inputs={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
