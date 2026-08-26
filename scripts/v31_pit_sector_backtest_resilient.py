from __future__ import annotations

"""Resilient runner for the locked V3.1 PIT audit.

This file changes DATA TRANSPORT only. It does not change any V3.1 thresholds,
valuation anchors, rebalance cadence, universe, or transaction-cost assumptions.
Price source fallback order:
1) AkShare Eastmoney A-share history (original source)
2) AkShare Sina A-share daily history
3) yfinance Yahoo adjusted history

Historical valuation remains delegated to the locked audit module's existing
Eastmoney -> Legulegu PE(TTM)/PB fallback, so valuation semantics are unchanged.
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


def _market_symbol(code: str) -> str:
    return ("sh" if code.startswith(("5", "6", "9")) else "sz") + code


def _yahoo_symbol(code: str) -> str:
    return code + (".SS" if code.startswith(("5", "6", "9")) else ".SZ")


def resilient_fetch_price(code: str) -> pd.DataFrame:
    errors: list[str] = []

    # 1) Original Eastmoney route, but with shorter bounded retries.
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=core.START,
                end_date=core.END,
                adjust="qfq",
            )
            out = _normalise(df)
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} eastmoney rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"eastmoney:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)

    # 2) Sina route exposed by AkShare. qfq preserves comparability with the
    # locked script's original total-return-like arithmetic.
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_daily(
                symbol=_market_symbol(code),
                start_date=core.START,
                end_date=core.END,
                adjust="qfq",
            )
            out = _normalise(df)
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} sina rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"sina:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)

    # 3) Yahoo fallback. auto_adjust=True yields a split/dividend adjusted close,
    # used only if both Chinese public routes fail.
    for attempt in range(2):
        try:
            df = yf.download(
                _yahoo_symbol(code),
                start="2018-01-01",
                end="2026-08-25",
                auto_adjust=True,
                progress=False,
                threads=False,
                timeout=30,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            df = df.reset_index()
            out = _normalise(df)
            if len(out) >= 200:
                print(f"PRICE_SOURCE {code} yahoo rows={len(out)}")
                return out
            raise RuntimeError(f"too few rows={len(out)}")
        except Exception as exc:
            errors.append(f"yahoo:{type(exc).__name__}:{exc}")
            time.sleep(1 + attempt)

    raise RuntimeError(f"all price sources failed for {code}: {' | '.join(errors)}")


if __name__ == "__main__":
    # Monkeypatch data transport only; all decision logic stays in the locked core.
    core.fetch_price = resilient_fetch_price
    core.main()
