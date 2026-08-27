"""Verify market-price observations before V3.1.1 production uses them.

The valuation extractor is allowed to obtain a numeric market price, but formal
production needs an independently auditable observation date.  This module is a
small provenance boundary: it resolves the provider's actual dated observation
and verifies that the value still matches the price used by the strict-PIT row.

No valuation, ranking or action policy lives here.  Failure to prove the price
observation returns an error so the production bridge can fail closed.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Callable

import pandas as pd


def _normalize_code(value: str) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def verify_akshare_qfq_daily_observation(
    code: str,
    expected_price: float,
    *,
    as_of: date,
    history_loader: Callable | None = None,
) -> tuple[date | None, str]:
    """Return the actual AKShare QFQ trade date when price provenance matches.

    The expected price must equal the provider's latest close available on or
    before ``as_of``. A changed value, missing date/schema or future observation
    is not silently accepted.
    """
    if history_loader is None:
        import akshare as ak

        history_loader = ak.stock_zh_a_hist

    expected = _finite(expected_price)
    if expected is None or expected <= 0:
        return None, "PRICE_VALUE_INVALID"

    start = (as_of - timedelta(days=30)).strftime("%Y%m%d")
    end = as_of.strftime("%Y%m%d")
    try:
        frame = history_loader(
            symbol=_normalize_code(code),
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
    except Exception as exc:  # provider boundary
        return None, f"PRICE_VERIFICATION_FETCH_ERROR:{type(exc).__name__}"

    if frame is None or frame.empty:
        return None, "PRICE_VERIFICATION_EMPTY"
    date_column = "日期" if "日期" in frame.columns else "date"
    close_column = "收盘" if "收盘" in frame.columns else "close"
    if date_column not in frame.columns or close_column not in frame.columns:
        return None, "PRICE_VERIFICATION_SCHEMA_MISMATCH"

    local = frame[[date_column, close_column]].copy()
    local[date_column] = pd.to_datetime(local[date_column], errors="coerce").dt.date
    local[close_column] = pd.to_numeric(local[close_column], errors="coerce")
    local = local.dropna().loc[lambda x: x[date_column] <= as_of]
    if local.empty:
        return None, "PRICE_VERIFICATION_NO_ASOF_OBSERVATION"

    latest = local.sort_values(date_column).iloc[-1]
    observed_date = latest[date_column]
    observed_price = _finite(latest[close_column])
    if observed_date is None or observed_date > as_of:
        return None, "PRICE_DATE_AFTER_DECISION_DATE"
    if observed_price is None or observed_price <= 0:
        return None, "PRICE_VERIFICATION_VALUE_INVALID"
    if not math.isclose(observed_price, expected, rel_tol=1e-7, abs_tol=1e-4):
        return None, "PRICE_VALUE_CHANGED_DURING_VERIFICATION"
    return observed_date, ""


def verify_price_observation(
    code: str,
    expected_price: float,
    source: str,
    *,
    as_of: date,
    akshare_history_loader: Callable | None = None,
) -> tuple[date | None, str]:
    """Dispatch provider-specific price provenance verification."""
    normalized_source = str(source or "").strip().upper()
    if normalized_source == "AKSHARE_QFQ_DAILY":
        return verify_akshare_qfq_daily_observation(
            code,
            expected_price,
            as_of=as_of,
            history_loader=akshare_history_loader,
        )
    return None, f"PRICE_SOURCE_NOT_VERIFIABLE:{normalized_source or 'UNKNOWN'}"
