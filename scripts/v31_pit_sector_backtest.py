from __future__ import annotations

"""Locked point-in-time backtest for the V3.1 valuation execution layer.

This is intentionally NOT a full historical reconstruction of qualitative moat
judgements. It conditions on a fixed, pre-declared five-stock research universe
and tests whether the frozen V3.1 valuation buy ladder + dynamic-value sell ladder
would have added value without look-ahead.

Rules are locked before seeing output:
- Window: 2018-01-01 .. 2026-08-24
- Universe: rare earth 600111/000831/600392; aerospace 600118/600879
- Data: AkShare public historical prices + historical PE(TTM)/PB
- Valuation anchor: trailing 756 trading-day median, shifted one day (past only)
- If positive PE and PB both exist, price/neutral is geometric mean of relative
  PE and relative PB. If PE is non-positive/unavailable, PB alone is used.
- Minimum anchor history: 252 trading days
- Rebalance: month-end only, to avoid threshold-churn/data-mining
- One-way trading friction: 0.10% of turnover
- Buy ladder (fraction of per-name cap): <=0.85 50%, <=0.75 75%, <=0.65 100%
- Sell ladder: >=1.20 max 75%, >=1.40 max 50%, >=1.70 max 25%
- 1.00..1.20: HOLD_NO_ADD; 0.85..1.00: HOLD; no forced buying

The neutral value is dynamic: current_price / price_to_neutral. Entry cost is
never an input to the exit decision.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import math
import time

import akshare as ak
import numpy as np
import pandas as pd

START = "20180101"
END = "20260824"
START_TS = pd.Timestamp("2018-01-01")
END_TS = pd.Timestamp("2026-08-24")
ONE_WAY_COST = 0.001
ANCHOR_WINDOW = 756
ANCHOR_MIN = 252
INITIAL_CAPITAL = 1_000_000.0
OUT = Path("artifacts/v31_pit_backtest")

GROUPS = {
    "rare_earth": ["600111", "000831", "600392"],
    "aerospace": ["600118", "600879"],
    "combined": ["600111", "000831", "600392", "600118", "600879"],
}
NAMES = {
    "600111": "北方稀土",
    "000831": "中国稀土",
    "600392": "盛和资源",
    "600118": "中国卫星",
    "600879": "航天电子",
}


def _pick(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"none of columns found: {candidates}; got={list(df.columns)}")


def _date_col(df: pd.DataFrame) -> str:
    return _pick(df, ["日期", "date", "trade_date", "交易日期"])


def fetch_price(code: str) -> pd.DataFrame:
    # qfq is used only for total-return-like portfolio return arithmetic.
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=START,
                end_date=END,
                adjust="qfq",
            )
            dcol = _date_col(df)
            ccol = _pick(df, ["收盘", "close", "收盘价"])
            out = df[[dcol, ccol]].copy()
            out.columns = ["date", "close"]
            out["date"] = pd.to_datetime(out["date"])
            out["close"] = pd.to_numeric(out["close"], errors="coerce")
            return out.dropna().drop_duplicates("date").sort_values("date")
        except Exception as exc:  # pragma: no cover - network fallback
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"price fetch failed for {code}: {last_error}")


def fetch_valuation(code: str) -> pd.DataFrame:
    """Fetch historical PE/PB with Eastmoney first and Legulegu fallback."""
    errors: list[str] = []
    for attempt in range(3):
        try:
            df = ak.stock_value_em(symbol=code)
            dcol = _date_col(df)
            pecol = _pick(df, ["PE(TTM)", "市盈率(TTM)", "pe_ttm"])
            pbcol = _pick(df, ["市净率", "PB", "pb"])
            out = df[[dcol, pecol, pbcol]].copy()
            out.columns = ["date", "pe_ttm", "pb"]
            out["date"] = pd.to_datetime(out["date"])
            out["pe_ttm"] = pd.to_numeric(out["pe_ttm"], errors="coerce")
            out["pb"] = pd.to_numeric(out["pb"], errors="coerce")
            return out.drop_duplicates("date").sort_values("date")
        except Exception as exc:  # pragma: no cover
            errors.append(f"stock_value_em:{exc}")
            time.sleep(2 ** attempt)
    for attempt in range(3):
        try:
            df = ak.stock_a_indicator_lg(symbol=code)
            dcol = _date_col(df)
            pecol = _pick(df, ["pe_ttm", "pe", "市盈率(TTM)"])
            pbcol = _pick(df, ["pb", "市净率"])
            out = df[[dcol, pecol, pbcol]].copy()
            out.columns = ["date", "pe_ttm", "pb"]
            out["date"] = pd.to_datetime(out["date"])
            out["pe_ttm"] = pd.to_numeric(out["pe_ttm"], errors="coerce")
            out["pb"] = pd.to_numeric(out["pb"], errors="coerce")
            return out.drop_duplicates("date").sort_values("date")
        except Exception as exc:  # pragma: no cover
            errors.append(f"stock_a_indicator_lg:{exc}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"valuation fetch failed for {code}: {' | '.join(errors)}")


def build_panel(code: str) -> pd.DataFrame:
    price = fetch_price(code)
    val = fetch_valuation(code)
    df = price.merge(val, on="date", how="left").sort_values("date")
    # A valuation source may have occasional holes. Forward-fill only previously
    # observed values; this cannot introduce future information.
    df[["pe_ttm", "pb"]] = df[["pe_ttm", "pb"]].ffill()
    pe_positive = df["pe_ttm"].where(df["pe_ttm"] > 0)
    pb_positive = df["pb"].where(df["pb"] > 0)
    df["pe_anchor"] = pe_positive.shift(1).rolling(ANCHOR_WINDOW, min_periods=ANCHOR_MIN).median()
    df["pb_anchor"] = pb_positive.shift(1).rolling(ANCHOR_WINDOW, min_periods=ANCHOR_MIN).median()
    pe_rel = pe_positive / df["pe_anchor"]
    pb_rel = pb_positive / df["pb_anchor"]
    both = pe_rel.notna() & pb_rel.notna() & (pe_rel > 0) & (pb_rel > 0)
    ratio = pd.Series(np.nan, index=df.index, dtype=float)
    ratio.loc[both] = np.sqrt(pe_rel.loc[both] * pb_rel.loc[both])
    ratio.loc[~both & pb_rel.notna() & (pb_rel > 0)] = pb_rel.loc[~both & pb_rel.notna() & (pb_rel > 0)]
    ratio.loc[~both & ratio.isna() & pe_rel.notna() & (pe_rel > 0)] = pe_rel.loc[
        ~both & ratio.isna() & pe_rel.notna() & (pe_rel > 0)
    ]
    df["price_to_neutral"] = ratio
    df["neutral_value"] = df["close"] / df["price_to_neutral"]
    df["ret"] = df["close"].pct_change().fillna(0.0)
    df["code"] = code
    return df[(df["date"] >= START_TS) & (df["date"] <= END_TS)].reset_index(drop=True)


def desired_weight(ratio: float, current_weight: float, cap: float) -> tuple[float, str]:
    if not math.isfinite(ratio) or ratio <= 0:
        return current_weight, "HOLD_REVIEW"
    # Sell/derisk is evaluated first at expensive ratios.
    if ratio >= 1.70:
        return min(current_weight, 0.25 * cap), "CORE_ONLY"
    if ratio >= 1.40:
        return min(current_weight, 0.50 * cap), "REDUCE_50"
    if ratio >= 1.20:
        return min(current_weight, 0.75 * cap), "REDUCE_25"
    if ratio >= 1.00:
        return current_weight, "HOLD_NO_ADD"
    # Below neutral, existing positions are held; new/additional capital is only
    # deployed when the frozen margin-of-safety bands are reached.
    if ratio <= 0.65:
        return max(current_weight, 1.00 * cap), "BUY_FULL_MARGIN"
    if ratio <= 0.75:
        return max(current_weight, 0.75 * cap), "BUY_A_LEVEL"
    if ratio <= 0.85:
        return max(current_weight, 0.50 * cap), "BUY_STAGED"
    return current_weight, "HOLD"


@dataclass
class Result:
    equity: pd.DataFrame
    trades: pd.DataFrame
    summary: dict


def _month_end_dates(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.to_period("M")).max().tolist())


def run_strategy(panels: dict[str, pd.DataFrame], codes: list[str], label: str) -> Result:
    frames = []
    for code in codes:
        x = panels[code].set_index("date")[["ret", "close", "price_to_neutral", "neutral_value"]].copy()
        x.columns = pd.MultiIndex.from_product([[code], x.columns])
        frames.append(x)
    panel = pd.concat(frames, axis=1).sort_index()
    panel = panel[(panel.index >= START_TS) & (panel.index <= END_TS)]
    panel = panel.ffill()
    rebalance_dates = _month_end_dates(panel.index)
    cap = 1.0 / len(codes)
    weights = {c: 0.0 for c in codes}
    nav = 1.0
    records: list[dict] = []
    trades: list[dict] = []

    for i, dt in enumerate(panel.index):
        if i > 0:
            daily = 0.0
            for c in codes:
                r = panel.loc[dt, (c, "ret")]
                if pd.notna(r):
                    daily += weights[c] * float(r)
            nav *= 1.0 + daily
            # Let weights drift after returns, preserving cash as zero-return.
            denom = 1.0 + daily
            if denom != 0:
                for c in codes:
                    r = panel.loc[dt, (c, "ret")]
                    rr = float(r) if pd.notna(r) else 0.0
                    weights[c] = weights[c] * (1.0 + rr) / denom

        turnover = 0.0
        if dt in rebalance_dates:
            targets = dict(weights)
            actions: dict[str, str] = {}
            for c in codes:
                ratio = panel.loc[dt, (c, "price_to_neutral")]
                if pd.isna(ratio):
                    targets[c], actions[c] = weights[c], "HOLD_REVIEW"
                else:
                    targets[c], actions[c] = desired_weight(float(ratio), weights[c], cap)
            # Safety normalization only if numerical drift ever pushes targets >100%.
            total_target = sum(targets.values())
            if total_target > 1.0 + 1e-12:
                targets = {c: w / total_target for c, w in targets.items()}
            turnover = sum(abs(targets[c] - weights[c]) for c in codes)
            cost = turnover * ONE_WAY_COST
            nav *= 1.0 - cost
            for c in codes:
                delta = targets[c] - weights[c]
                if abs(delta) > 1e-8:
                    ratio = panel.loc[dt, (c, "price_to_neutral")]
                    trades.append(
                        {
                            "strategy": label,
                            "date": dt,
                            "code": c,
                            "name": NAMES[c],
                            "action": actions[c],
                            "price_to_neutral": float(ratio) if pd.notna(ratio) else np.nan,
                            "neutral_value": panel.loc[dt, (c, "neutral_value")],
                            "close_qfq": panel.loc[dt, (c, "close")],
                            "weight_before": weights[c],
                            "weight_after": targets[c],
                            "weight_change": delta,
                            "cost_fraction": abs(delta) * ONE_WAY_COST,
                        }
                    )
            weights = targets

        records.append(
            {
                "date": dt,
                "nav": nav,
                "cash_weight": max(0.0, 1.0 - sum(weights.values())),
                "turnover": turnover,
                **{f"w_{c}": weights[c] for c in codes},
            }
        )

    equity = pd.DataFrame(records).set_index("date")
    trades_df = pd.DataFrame(trades)
    summary = metrics(equity["nav"], label)
    summary["trades"] = int(len(trades_df))
    summary["avg_cash_weight"] = float(equity["cash_weight"].mean())
    summary["total_turnover"] = float(equity["turnover"].sum())
    return Result(equity, trades_df, summary)


def run_buy_hold(panels: dict[str, pd.DataFrame], codes: list[str], label: str) -> pd.Series:
    rets = pd.concat({c: panels[c].set_index("date")["ret"] for c in codes}, axis=1).sort_index()
    rets = rets[(rets.index >= START_TS) & (rets.index <= END_TS)].fillna(0.0)
    w = np.repeat(1.0 / len(codes), len(codes))
    nav = (1.0 + rets.dot(w)).cumprod()
    # Charge a single initial purchase friction.
    nav *= 1.0 - ONE_WAY_COST
    nav.name = label
    return nav


def fetch_csi300() -> pd.Series:
    errors: list[str] = []
    try:
        df = ak.stock_zh_index_daily_em(symbol="sh000300")
        dcol = _date_col(df)
        ccol = _pick(df, ["close", "收盘", "收盘价"])
        x = df[[dcol, ccol]].copy()
    except Exception as exc:  # pragma: no cover
        errors.append(str(exc))
        df = ak.index_zh_a_hist(symbol="000300", period="daily", start_date=START, end_date=END)
        dcol = _date_col(df)
        ccol = _pick(df, ["收盘", "close", "收盘价"])
        x = df[[dcol, ccol]].copy()
    x.columns = ["date", "close"]
    x["date"] = pd.to_datetime(x["date"])
    x["close"] = pd.to_numeric(x["close"], errors="coerce")
    x = x.dropna().drop_duplicates("date").sort_values("date")
    x = x[(x["date"] >= START_TS) & (x["date"] <= END_TS)].set_index("date")
    s = x["close"] / x["close"].iloc[0]
    s.name = "CSI300"
    return s


def metrics(nav: pd.Series, label: str) -> dict:
    nav = nav.dropna()
    if nav.empty:
        return {"label": label}
    total = float(nav.iloc[-1] / nav.iloc[0] - 1.0)
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1 / 365.25)
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1.0)
    dd = nav / nav.cummax() - 1.0
    daily = nav.pct_change().dropna()
    sharpe = float(np.sqrt(252) * daily.mean() / daily.std()) if daily.std() > 0 else np.nan
    yearly = nav.resample("YE").last().pct_change().dropna()
    return {
        "label": label,
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "final_multiple": float(nav.iloc[-1] / nav.iloc[0]),
        "final_capital_rmb": float(INITIAL_CAPITAL * nav.iloc[-1] / nav.iloc[0]),
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": float(dd.min()),
        "sharpe": sharpe,
        "worst_calendar_year": float(yearly.min()) if not yearly.empty else np.nan,
        "best_calendar_year": float(yearly.max()) if not yearly.empty else np.nan,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_codes = GROUPS["combined"]
    panels: dict[str, pd.DataFrame] = {}
    for code in all_codes:
        print(f"FETCH {code} {NAMES[code]}", flush=True)
        panels[code] = build_panel(code)
        panels[code].to_csv(OUT / f"panel_{code}.csv", index=False)
        print(
            f"  rows={len(panels[code])} valuation_ready={panels[code]['price_to_neutral'].notna().sum()}",
            flush=True,
        )

    summaries: list[dict] = []
    strategy_results: dict[str, Result] = {}
    for label, codes in GROUPS.items():
        result = run_strategy(panels, codes, f"V31_{label}")
        strategy_results[label] = result
        result.equity.to_csv(OUT / f"equity_{label}.csv")
        result.trades.to_csv(OUT / f"trades_{label}.csv", index=False)
        summaries.append(result.summary)
        bh = run_buy_hold(panels, codes, f"BUYHOLD_{label}")
        bh.to_csv(OUT / f"buyhold_{label}.csv")
        summaries.append(metrics(bh, f"BUYHOLD_{label}"))

    csi = fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    summaries.append(metrics(csi, "CSI300"))
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "summary.csv", index=False)

    assumptions = {
        "window": [str(START_TS.date()), str(END_TS.date())],
        "groups": GROUPS,
        "one_way_cost": ONE_WAY_COST,
        "anchor_window_trading_days": ANCHOR_WINDOW,
        "anchor_min_history": ANCHOR_MIN,
        "valuation_ratio": "geomean(PE_TTM / trailing-past-only median PE, PB / trailing-past-only median PB); PB-only when PE<=0",
        "rebalance": "month-end",
        "buy_ladder": {"<=0.85": 0.50, "<=0.75": 0.75, "<=0.65": 1.00},
        "sell_ladder": {">=1.20": 0.75, ">=1.40": 0.50, ">=1.70": 0.25},
        "important_limit": "tests V3.1 valuation/execution layer conditional on fixed research universe; not a full PIT reconstruction of qualitative moat gates",
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    cols = ["label", "final_capital_rmb", "total_return", "cagr", "max_drawdown", "sharpe", "worst_calendar_year", "trades", "avg_cash_weight"]
    printable = summary_df.reindex(columns=cols)
    md = [
        "# V3.1 PIT sector backtest (locked rules)",
        "",
        "> This tests the valuation/execution layer on a fixed five-stock research universe. It is not a retrospective reconstruction of qualitative moat gates.",
        "",
        "## Locked assumptions",
        "",
        f"- Period: {START_TS.date()} to {END_TS.date()}",
        f"- One-way friction: {ONE_WAY_COST:.2%}",
        f"- Valuation anchor: {ANCHOR_WINDOW} prior trading days, shifted by one day; minimum {ANCHOR_MIN}",
        "- Rebalance: month-end",
        "- Exit decisions use dynamic price/latest-neutral-value only; entry cost is ignored.",
        "",
        "## Results",
        "",
        printable.to_markdown(index=False),
        "",
        "## Anti-cheating checks",
        "",
        "- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.",
        "- No future prices or future valuation observations are used.",
        "- Rules and symbols are hard-coded in this script before execution.",
        "- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    main()
