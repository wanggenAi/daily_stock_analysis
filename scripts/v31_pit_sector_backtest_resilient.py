from __future__ import annotations

"""Resilient runner for the locked V3.1 PIT audit.

This file changes DATA TRANSPORT only. It does not change any V3.1 thresholds,
valuation anchors, rebalance cadence, universe, or transaction-cost assumptions.
Price source fallback order:
1) AkShare Eastmoney A-share history (original source)
2) AkShare Sina A-share daily history
3) yfinance Yahoo adjusted history

Historical valuation semantics remain PE(TTM)/PB from the same public valuation
routes; this adapter only tolerates current AkShare column/API naming changes.
"""

import time
import pandas as pd
import akshare as ak
import yfinance as yf

import v31_pit_sector_backtest as core


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise RuntimeError("empty price frame")
    dcol = None
    for c in ["日期", "date", "trade_date", "交易日期"]:
        if c in df.columns:
            dcol = c
            break
    if dcol is None:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            dcol = df.columns[0]
        else:
            raise KeyError(f"no date column: {list(df.columns)}")
    ccol = None
    for c in ["收盘", "close", "收盘价", "Close"]:
        if c in df.columns:
            ccol = c
            break
    if ccol is None:
        raise KeyError(f"no close column: {list(df.columns)}")
    out = df[[dcol, ccol]].copy()
    out.columns = ["date", "close"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    return out.dropna().drop_duplicates("date").sort_values("date")


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"none of columns found: {candidates}; got={list(df.columns)}")


def _normalise_valuation(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise RuntimeError("empty valuation frame")
    dcol = _pick_column(df, ["日期", "数据日期", "date", "trade_date", "交易日期"])
    pecol = _pick_column(df, ["PE(TTM)", "市盈率(TTM)", "pe_ttm", "pe"])
    pbcol = _pick_column(df, ["市净率", "PB", "pb"])
    out = df[[dcol, pecol, pbcol]].copy()
    out.columns = ["date", "pe_ttm", "pb"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out["pe_ttm"] = pd.to_numeric(out["pe_ttm"], errors="coerce")
    out["pb"] = pd.to_numeric(out["pb"], errors="coerce")
    out = out.dropna(subset=["date"]).drop_duplicates("date").sort_values("date")
    if len(out) < 50:
        raise RuntimeError(f"too few valuation rows={len(out)}")
    return out


def _market_symbol(code: str) -> str:
    return ("sh" if code.startswith(("5", "6", "9")) else "sz") + code


def _yahoo_symbol(code: str) -> str:
    return code + (".SS" if code.startswith(("5", "6", "9")) else ".SZ")


def resilient_fetch_price(code: str) -> pd.DataFrame:
    errors: list[str] = []
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=core.START, end_date=core.END, adjust="qfq")
            out = _normalise(df)
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} eastmoney rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"eastmoney:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_daily(symbol=_market_symbol(code), start_date=core.START, end_date=core.END, adjust="qfq")
            out = _normalise(df)
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} sina rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"sina:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    for attempt in range(2):
        try:
            df = yf.download(_yahoo_symbol(code), start="2018-01-01", end="2026-08-25", auto_adjust=True, progress=False, threads=False, timeout=30)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            out = _normalise(df.reset_index())
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} yahoo rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"yahoo:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    raise RuntimeError(f"all price sources failed for {code}: {' | '.join(errors)}")


def resilient_fetch_valuation(code: str) -> pd.DataFrame:
    errors: list[str] = []
    for attempt in range(3):
        try:
            out = _normalise_valuation(ak.stock_value_em(symbol=code))
            print(f"VALUATION_SOURCE {code} eastmoney rows={len(out)}")
            return out
        except Exception as exc:
            errors.append(f"stock_value_em:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    legacy = getattr(ak, "stock_a_indicator_lg", None)
    if legacy is not None:
        for attempt in range(2):
            try:
                out = _normalise_valuation(legacy(symbol=code))
                print(f"VALUATION_SOURCE {code} legulegu rows={len(out)}")
                return out
            except Exception as exc:
                errors.append(f"stock_a_indicator_lg:{type(exc).__name__}:{exc}")
                time.sleep(1 + attempt)
    else:
        errors.append("stock_a_indicator_lg:unavailable_in_installed_akshare")
    raise RuntimeError(f"all valuation sources failed for {code}: {' | '.join(errors)}")


def _series_from_index_frame(df: pd.DataFrame, source: str) -> pd.Series:
    out = _normalise(df)
    out = out[(out["date"] >= core.START_TS) & (out["date"] <= core.END_TS)].set_index("date")
    if len(out) < 200:
        raise RuntimeError(f"too few CSI300 rows={len(out)} from {source}")
    s = out["close"] / out["close"].iloc[0]
    s.name = "CSI300"
    print(f"BENCHMARK_SOURCE CSI300 {source} rows={len(out)}")
    return s


def resilient_fetch_csi300() -> pd.Series:
    errors: list[str] = []
    for attempt in range(2):
        try:
            return _series_from_index_frame(ak.stock_zh_index_daily_em(symbol="sh000300"), "eastmoney")
        except Exception as exc:
            errors.append(f"eastmoney:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    for attempt in range(2):
        try:
            df = ak.stock_zh_index_daily(symbol="sh000300")
            return _series_from_index_frame(df, "sina")
        except Exception as exc:
            errors.append(f"sina:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    for attempt in range(2):
        try:
            df = yf.download("000300.SS", start="2018-01-01", end="2026-08-25", auto_adjust=True, progress=False, threads=False, timeout=30)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            return _series_from_index_frame(df.reset_index(), "yahoo")
        except Exception as exc:
            errors.append(f"yahoo:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)
    raise RuntimeError(f"all CSI300 sources failed: {' | '.join(errors)}")


if __name__ == "__main__":
    core.fetch_price = resilient_fetch_price
    core.fetch_valuation = resilient_fetch_valuation
    core.fetch_csi300 = resilient_fetch_csi300
    core.main()
