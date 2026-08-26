from __future__ import annotations

"""Round-6 untouched OOS: strict-PIT expectation-gap valuation for growth companies.

Research-only. Formula and universe are frozen in
`docs/V31_EXPECTATION_GAP_ROUND6_DRAFT.md` before the first successful result.
Production V3.1 remains unchanged.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd

import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport
import v31_pit_normalized_earnings_panel as fincore

OUT = Path("artifacts/v31_pit_oos_round6_expectation_gap")

NAMES = {
    "002179": "中航光电",
    "002138": "顺络电子",
    "002241": "歌尔股份",
    "002815": "崇达技术",
    "603019": "中科曙光",
    "600570": "恒生电子",
}
ALL_CODES = list(NAMES)
GROUPS = {"growth6": ALL_CODES, **{f"single_{c}": [c] for c in ALL_CODES}}

DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON_YEARS = 10
REALISTIC_GROWTH_CAP = 0.30
REVENUE_GROWTH_ALLOWANCE = 0.05
IMPLIED_GROWTH_MAX = 1.00

ROUND5_GROWTH_HAIRCUT = 0.50
ROUND5_GROWTH_CAP = 0.15
ROUND5_TERMINAL_PE = 15.0
ROUND5_HORIZON = 5


def _positive_relative(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    positive = series.where(series > 0)
    anchor = positive.shift(1).rolling(core.ANCHOR_WINDOW, min_periods=core.ANCHOR_MIN).median()
    return positive / anchor, anchor


def _universal_ratio(pe_rel: pd.Series, pb_rel: pd.Series) -> pd.Series:
    both = pe_rel.notna() & pb_rel.notna() & (pe_rel > 0) & (pb_rel > 0)
    ratio = pd.Series(np.nan, index=pe_rel.index, dtype=float)
    ratio.loc[both] = np.sqrt(pe_rel.loc[both] * pb_rel.loc[both])
    pb_only = ~both & pb_rel.notna() & (pb_rel > 0)
    ratio.loc[pb_only] = pb_rel.loc[pb_only]
    pe_only = ~both & ratio.isna() & pe_rel.notna() & (pe_rel > 0)
    ratio.loc[pe_only] = pe_rel.loc[pe_only]
    return ratio


def value_round6(normalized_eps: float, start_growth: float) -> float:
    """Ten-year earning-power value with Gordon-derived terminal multiple."""
    if not np.isfinite(normalized_eps) or normalized_eps <= 0:
        return np.nan
    if not np.isfinite(start_growth):
        return np.nan
    start_growth = float(np.clip(start_growth, 0.0, IMPLIED_GROWTH_MAX))
    earnings = float(normalized_eps)
    pv = 0.0
    for year in range(1, HORIZON_YEARS + 1):
        if year == 1:
            g = start_growth
        else:
            frac = (year - 1) / (HORIZON_YEARS - 1)
            g = start_growth + (TERMINAL_GROWTH - start_growth) * frac
        earnings *= 1.0 + g
        pv += earnings / ((1.0 + DISCOUNT_RATE) ** year)
    terminal_multiple = 1.0 / (DISCOUNT_RATE - TERMINAL_GROWTH)
    pv += terminal_multiple * earnings / ((1.0 + DISCOUNT_RATE) ** HORIZON_YEARS)
    return float(pv)


def value_round5(normalized_owner_eps: float, start_growth: float) -> float:
    """Exact frozen Round-5 five-year/15x comparator."""
    if not np.isfinite(normalized_owner_eps) or normalized_owner_eps <= 0:
        return np.nan
    start_growth = float(np.clip(start_growth, 0.0, ROUND5_GROWTH_CAP))
    end_growth = min(start_growth, TERMINAL_GROWTH)
    earnings = float(normalized_owner_eps)
    pv = 0.0
    for year in range(1, ROUND5_HORIZON + 1):
        if year == 1:
            g = start_growth
        else:
            frac = (year - 1) / (ROUND5_HORIZON - 1)
            g = start_growth + (end_growth - start_growth) * frac
        earnings *= 1.0 + g
        pv += earnings / ((1.0 + DISCOUNT_RATE) ** year)
    pv += ROUND5_TERMINAL_PE * earnings / ((1.0 + DISCOUNT_RATE) ** ROUND5_HORIZON)
    return float(pv)


def _cagr(cur: float, past: float, years: float) -> float:
    if not np.isfinite(cur) or not np.isfinite(past) or cur <= 0 or past <= 0 or years <= 0:
        return np.nan
    return float((cur / past) ** (1.0 / years) - 1.0)


def _round5_growth_series(f: pd.DataFrame, norm_col: str) -> tuple[list[float], list[float]]:
    report_dates = pd.to_datetime(f["report_date"], errors="coerce")
    norm = pd.to_numeric(f[norm_col], errors="coerce")
    hist_growth: list[float] = []
    assumed: list[float] = []
    for i, (d, cur) in enumerate(zip(report_dates, norm)):
        if pd.isna(d) or pd.isna(cur) or cur <= 0:
            hist_growth.append(np.nan)
            assumed.append(0.0)
            continue
        cutoff = d - pd.DateOffset(years=3)
        candidates = [
            j for j in range(i)
            if pd.notna(report_dates.iloc[j])
            and report_dates.iloc[j] <= cutoff
            and pd.notna(norm.iloc[j])
            and norm.iloc[j] > 0
        ]
        if not candidates:
            hist_growth.append(np.nan)
            assumed.append(0.0)
            continue
        j = candidates[-1]
        years = max((d - report_dates.iloc[j]).days / 365.25, 0.01)
        g = _cagr(float(cur), float(norm.iloc[j]), years)
        hist_growth.append(g)
        assumed.append(float(np.clip(max(0.0, ROUND5_GROWTH_HAIRCUT * g) if np.isfinite(g) else 0.0, 0.0, ROUND5_GROWTH_CAP)))
    return hist_growth, assumed


def _round6_growth_series(f: pd.DataFrame, norm_col: str) -> tuple[list[float], list[float], list[float]]:
    report_dates = pd.to_datetime(f["report_date"], errors="coerce")
    available_dates = pd.to_datetime(f["available_date"], errors="coerce")
    norm = pd.to_numeric(f[norm_col], errors="coerce")
    revenue = pd.to_numeric(f["ttm_revenue"], errors="coerce")

    eps_growth: list[float] = []
    revenue_growth: list[float] = []
    realistic_growth: list[float] = []

    for i, (d, avail, cur_eps, cur_rev) in enumerate(zip(report_dates, available_dates, norm, revenue)):
        if pd.isna(d) or pd.isna(avail) or pd.isna(cur_eps) or pd.isna(cur_rev) or cur_eps <= 0 or cur_rev <= 0:
            eps_growth.append(np.nan)
            revenue_growth.append(np.nan)
            realistic_growth.append(np.nan)
            continue

        cutoff = d - pd.DateOffset(years=3)
        candidates = [
            j for j in range(i)
            if pd.notna(report_dates.iloc[j])
            and pd.notna(available_dates.iloc[j])
            and report_dates.iloc[j] <= cutoff
            and available_dates.iloc[j] <= avail
            and pd.notna(norm.iloc[j]) and norm.iloc[j] > 0
            and pd.notna(revenue.iloc[j]) and revenue.iloc[j] > 0
        ]
        if not candidates:
            eps_growth.append(np.nan)
            revenue_growth.append(np.nan)
            realistic_growth.append(np.nan)
            continue

        j = candidates[-1]
        years = max((d - report_dates.iloc[j]).days / 365.25, 0.01)
        eg = _cagr(float(cur_eps), float(norm.iloc[j]), years)
        rg = _cagr(float(cur_rev), float(revenue.iloc[j]), years)
        eps_growth.append(eg)
        revenue_growth.append(rg)
        if np.isfinite(eg) and np.isfinite(rg):
            supportable = min(eg, rg + REVENUE_GROWTH_ALLOWANCE)
            realistic_growth.append(float(np.clip(supportable, 0.0, REALISTIC_GROWTH_CAP)))
        else:
            realistic_growth.append(np.nan)

    return eps_growth, revenue_growth, realistic_growth


def enrich_financials(code: str) -> pd.DataFrame:
    f = fincore.build_company(code).copy()
    eps = pd.to_numeric(f["ttm_basic_eps_approx"], errors="coerce")
    parent_np = pd.to_numeric(f["ttm_parent_netprofit"], errors="coerce")
    dq = pd.to_numeric(f["deduct_quality"], errors="coerce")
    cc = pd.to_numeric(f["cash_conversion"], errors="coerce")

    # Round-6 normalized clean EPS: deduct-profit quality affects earning power;
    # TTM cash conversion remains a diagnostic rather than a direct multiplier.
    valid6 = (eps > 0) & (parent_np > 0) & (dq > 0)
    deduct_factor = dq.clip(lower=0.0, upper=1.0).where(valid6)
    f["deduct_factor_round6"] = deduct_factor
    f["clean_eps_round6"] = (eps * deduct_factor).where(valid6)
    positive_clean = f["clean_eps_round6"].where(f["clean_eps_round6"] > 0)
    f["normalized_eps_round6"] = positive_clean.rolling(4, min_periods=2).median()

    eps_g, rev_g, realistic = _round6_growth_series(f, "normalized_eps_round6")
    f["eps_growth_3y_round6"] = eps_g
    f["revenue_growth_3y_round6"] = rev_g
    f["realistic_growth_round6"] = realistic
    f["neutral_value_round6"] = [
        value_round6(e, g)
        for e, g in zip(f["normalized_eps_round6"], f["realistic_growth_round6"])
    ]

    # Exact Round-5 comparator on the fresh Round-6 universe.
    valid5 = (eps > 0) & (parent_np > 0) & (dq > 0) & (cc > 0)
    q5 = pd.concat([pd.Series(1.0, index=f.index), dq, cc], axis=1).min(axis=1).where(valid5)
    f["quality_factor_round5"] = q5
    f["quality_adjusted_eps_round5"] = (eps * q5).where(valid5)
    positive5 = f["quality_adjusted_eps_round5"].where(f["quality_adjusted_eps_round5"] > 0)
    f["normalized_owner_eps_round5"] = positive5.rolling(4, min_periods=2).median()
    hist5, assumed5 = _round5_growth_series(f, "normalized_owner_eps_round5")
    f["historical_growth_round5"] = hist5
    f["assumed_growth_round5"] = assumed5
    f["neutral_value_round5"] = [
        value_round5(e, g)
        for e, g in zip(f["normalized_owner_eps_round5"], f["assumed_growth_round5"])
    ]

    f["code"] = code
    f["name"] = NAMES[code]
    return f


def solve_implied_growth(price: float, normalized_eps: float) -> tuple[float, str]:
    if not np.isfinite(price) or price <= 0 or not np.isfinite(normalized_eps) or normalized_eps <= 0:
        return np.nan, "INPUT_INCOMPLETE"
    low_value = value_round6(normalized_eps, 0.0)
    high_value = value_round6(normalized_eps, IMPLIED_GROWTH_MAX)
    if not np.isfinite(low_value) or not np.isfinite(high_value):
        return np.nan, "INPUT_INCOMPLETE"
    if price <= low_value:
        return 0.0, "BELOW_ZERO_GROWTH_VALUE"
    if price > high_value:
        return np.nan, "IMPLIED_ABOVE_SEARCH_RANGE"

    lo, hi = 0.0, IMPLIED_GROWTH_MAX
    for _ in range(60):
        mid = (lo + hi) / 2.0
        value = value_round6(normalized_eps, mid)
        if value < price:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2.0), "SOLVED"


def build_daily_panel(code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    price = transport.resilient_fetch_price(code).copy().sort_values("date")
    val = transport.resilient_fetch_valuation(code).copy().sort_values("date")
    d = price.merge(val, on="date", how="left").sort_values("date")
    d[["pe_ttm", "pb"]] = d[["pe_ttm", "pb"]].ffill()

    pe_rel, pe_anchor = _positive_relative(d["pe_ttm"])
    pb_rel, pb_anchor = _positive_relative(d["pb"])
    d["pe_anchor"] = pe_anchor
    d["pb_anchor"] = pb_anchor
    d["ratio_universal"] = _universal_ratio(pe_rel, pb_rel)
    d["neutral_universal"] = d["close"] / d["ratio_universal"]

    f = enrich_financials(code)
    signal_cols = [
        "report_date", "available_date",
        "normalized_eps_round6", "eps_growth_3y_round6", "revenue_growth_3y_round6",
        "realistic_growth_round6", "neutral_value_round6", "deduct_factor_round6",
        "cash_conversion",
        "normalized_owner_eps_round5", "assumed_growth_round5", "neutral_value_round5",
        "quality_factor_round5",
    ]
    signals = f[signal_cols].copy()
    signals["available_date"] = pd.to_datetime(signals["available_date"], errors="coerce").dt.normalize()
    signals = signals.dropna(subset=["available_date"]).sort_values(["available_date", "report_date"])
    signals = signals.drop_duplicates("available_date", keep="last")

    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    d = pd.merge_asof(
        d.sort_values("date"),
        signals.rename(columns={"available_date": "fund_available_date"}).sort_values("fund_available_date"),
        left_on="date",
        right_on="fund_available_date",
        direction="backward",
    )

    d["ratio_expectation"] = d["close"] / d["neutral_value_round6"]
    bad6 = (d["neutral_value_round6"] <= 0) | ~np.isfinite(d["neutral_value_round6"])
    d.loc[bad6, "ratio_expectation"] = np.nan

    d["ratio_round5"] = d["close"] / d["neutral_value_round5"]
    bad5 = (d["neutral_value_round5"] <= 0) | ~np.isfinite(d["neutral_value_round5"])
    d.loc[bad5, "ratio_round5"] = np.nan

    implied = [solve_implied_growth(float(p), float(e) if pd.notna(e) else np.nan)
               for p, e in zip(d["close"], d["normalized_eps_round6"])]
    d["market_implied_growth_round6"] = [x[0] for x in implied]
    d["implied_growth_status"] = [x[1] for x in implied]
    d["expectation_gap_round6"] = d["realistic_growth_round6"] - d["market_implied_growth_round6"]

    d["ret"] = d["close"].pct_change().fillna(0.0)
    d["code"] = code
    d = d[(d["date"] >= core.START_TS) & (d["date"] <= core.END_TS)].reset_index(drop=True)
    return d, f


def _month_ends(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.to_period("M")).max().tolist())


def run_cash_constrained(
    panels: dict[str, pd.DataFrame],
    codes: list[str],
    label: str,
    ratio_col: str,
    neutral_col: str,
) -> core.Result:
    frames = []
    for code in codes:
        x = panels[code].set_index("date")[["ret", "close", ratio_col, neutral_col]].copy()
        x.columns = pd.MultiIndex.from_product([[code], ["ret", "close", "ratio", "neutral"]])
        frames.append(x)
    panel = pd.concat(frames, axis=1).sort_index()
    panel = panel[(panel.index >= core.START_TS) & (panel.index <= core.END_TS)].ffill()
    rebalance_dates = _month_ends(panel.index)
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
            denom = 1.0 + daily
            if denom != 0:
                for c in codes:
                    r = panel.loc[dt, (c, "ret")]
                    rr = float(r) if pd.notna(r) else 0.0
                    weights[c] = weights[c] * (1.0 + rr) / denom

        turnover = 0.0
        if dt in rebalance_dates:
            raw_targets, actions = dict(weights), {}
            for c in codes:
                ratio = panel.loc[dt, (c, "ratio")]
                if pd.isna(ratio) or not np.isfinite(ratio) or ratio <= 0:
                    raw_targets[c], actions[c] = weights[c], "HOLD_REVIEW"
                else:
                    raw_targets[c], actions[c] = core.desired_weight(float(ratio), weights[c], cap)

            # Corrected execution: execute desired reductions first; only scale
            # incremental BUY requests if remaining cash cannot fund all buys.
            targets = dict(weights)
            for c in codes:
                if raw_targets[c] < weights[c]:
                    targets[c] = raw_targets[c]
            available_cash = max(0.0, 1.0 - sum(targets.values()))
            requests = {c: max(0.0, raw_targets[c] - targets[c]) for c in codes}
            total_req = sum(requests.values())
            scale = min(1.0, available_cash / total_req) if total_req > 0 else 0.0
            for c in codes:
                targets[c] += requests[c] * scale

            turnover = sum(abs(targets[c] - weights[c]) for c in codes)
            nav *= 1.0 - turnover * core.ONE_WAY_COST
            for c in codes:
                delta = targets[c] - weights[c]
                if abs(delta) > 1e-8:
                    ratio = panel.loc[dt, (c, "ratio")]
                    trades.append({
                        "strategy": label,
                        "date": dt,
                        "code": c,
                        "name": NAMES[c],
                        "action": actions[c],
                        "price_to_neutral": float(ratio) if pd.notna(ratio) else np.nan,
                        "neutral_value": panel.loc[dt, (c, "neutral")],
                        "close_qfq": panel.loc[dt, (c, "close")],
                        "weight_before": weights[c],
                        "weight_after": targets[c],
                        "weight_change": delta,
                        "cost_fraction": abs(delta) * core.ONE_WAY_COST,
                    })
            weights = targets

        records.append({
            "date": dt,
            "nav": nav,
            "cash_weight": max(0.0, 1.0 - sum(weights.values())),
            "turnover": turnover,
            **{f"w_{c}": weights[c] for c in codes},
        })

    equity = pd.DataFrame(records).set_index("date")
    trades_df = pd.DataFrame(trades)
    summary = core.metrics(equity["nav"], label)
    summary["trades"] = int(len(trades_df))
    summary["avg_cash_weight"] = float(equity["cash_weight"].mean())
    summary["total_turnover"] = float(equity["turnover"].sum())
    return core.Result(equity, trades_df, summary)


def true_buyhold(panels: dict[str, pd.DataFrame], codes: list[str], label: str) -> pd.Series:
    closes = pd.concat({c: panels[c].set_index("date")["close"] for c in codes}, axis=1).sort_index()
    closes = closes[(closes.index >= core.START_TS) & (closes.index <= core.END_TS)].dropna(how="any")
    indexed = closes / closes.iloc[0]
    nav = indexed.mean(axis=1) * (1.0 - core.ONE_WAY_COST)
    nav.name = label
    return nav


def decorate(x: dict, group: str, variant: str) -> dict:
    out = dict(x)
    out["group"] = group
    out["variant"] = variant
    return out


def expectation_diagnostics(panel: pd.DataFrame, code: str) -> dict:
    x = panel.copy().sort_values("date")
    ready = x[
        x["realistic_growth_round6"].notna()
        & x["market_implied_growth_round6"].notna()
        & x["expectation_gap_round6"].notna()
    ].copy()
    latest = x.iloc[-1]
    return {
        "code": code,
        "name": NAMES[code],
        "ready_days": int(len(ready)),
        "median_realistic_growth": float(ready["realistic_growth_round6"].median()) if not ready.empty else np.nan,
        "median_implied_growth": float(ready["market_implied_growth_round6"].median()) if not ready.empty else np.nan,
        "median_expectation_gap": float(ready["expectation_gap_round6"].median()) if not ready.empty else np.nan,
        "positive_gap_fraction": float((ready["expectation_gap_round6"] > 0).mean()) if not ready.empty else np.nan,
        "min_price_to_neutral": float(x["ratio_expectation"].min()) if x["ratio_expectation"].notna().any() else np.nan,
        "days_buy_staged_or_better": int((x["ratio_expectation"] <= 0.85).sum()),
        "latest_price": float(latest["close"]),
        "latest_neutral_round6": float(latest["neutral_value_round6"]) if pd.notna(latest["neutral_value_round6"]) else np.nan,
        "latest_ratio_round6": float(latest["ratio_expectation"]) if pd.notna(latest["ratio_expectation"]) else np.nan,
        "latest_realistic_growth": float(latest["realistic_growth_round6"]) if pd.notna(latest["realistic_growth_round6"]) else np.nan,
        "latest_implied_growth": float(latest["market_implied_growth_round6"]) if pd.notna(latest["market_implied_growth_round6"]) else np.nan,
        "latest_expectation_gap": float(latest["expectation_gap_round6"]) if pd.notna(latest["expectation_gap_round6"]) else np.nan,
        "latest_implied_status": str(latest["implied_growth_status"]),
        "latest_cash_conversion": float(latest["cash_conversion"]) if pd.notna(latest["cash_conversion"]) else np.nan,
        "latest_deduct_factor": float(latest["deduct_factor_round6"]) if pd.notna(latest["deduct_factor_round6"]) else np.nan,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panels: dict[str, pd.DataFrame] = {}
    financials: dict[str, pd.DataFrame] = {}
    diagnostics: list[dict] = []

    for code, name in NAMES.items():
        print(f"FETCH ROUND6 {code} {name}", flush=True)
        panel, fin = build_daily_panel(code)
        panels[code], financials[code] = panel, fin
        panel.to_csv(OUT / f"panel_{code}.csv", index=False)
        fin.to_csv(OUT / f"financial_{code}.csv", index=False)
        diagnostics.append(expectation_diagnostics(panel, code))
        print(
            f"  daily={len(panel)} expectation_ready={panel['ratio_expectation'].notna().sum()} "
            f"round5_ready={panel['ratio_round5'].notna().sum()} universal_ready={panel['ratio_universal'].notna().sum()}",
            flush=True,
        )

    diag_df = pd.DataFrame(diagnostics)
    diag_df.to_csv(OUT / "expectation_diagnostics.csv", index=False)

    summaries: list[dict] = []
    for group, codes in GROUPS.items():
        exp = run_cash_constrained(panels, codes, f"EXPECTATION_GAP_10Y_{group}", "ratio_expectation", "neutral_value_round6")
        r5 = run_cash_constrained(panels, codes, f"ROUND5_5Y_15X_{group}", "ratio_round5", "neutral_value_round5")
        universal = run_cash_constrained(panels, codes, f"UNIVERSAL_GEOMEAN_{group}", "ratio_universal", "neutral_universal")
        bh = true_buyhold(panels, codes, f"TRUE_BUYHOLD_{group}")

        exp.equity.to_csv(OUT / f"equity_expectation_{group}.csv")
        exp.trades.to_csv(OUT / f"trades_expectation_{group}.csv", index=False)
        r5.equity.to_csv(OUT / f"equity_round5_{group}.csv")
        r5.trades.to_csv(OUT / f"trades_round5_{group}.csv", index=False)
        universal.equity.to_csv(OUT / f"equity_universal_{group}.csv")
        universal.trades.to_csv(OUT / f"trades_universal_{group}.csv", index=False)
        bh.to_csv(OUT / f"true_buyhold_{group}.csv")

        summaries.extend([
            decorate(exp.summary, group, "expectation_gap_10y"),
            decorate(r5.summary, group, "round5_5y_15x"),
            decorate(universal.summary, group, "universal_geomean"),
            decorate(core.metrics(bh, f"TRUE_BUYHOLD_{group}"), group, "true_buyhold"),
        ])

    csi = transport.resilient_fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    summaries.append(decorate(core.metrics(csi, "CSI300"), "benchmark", "csi300"))

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "summary.csv", index=False)
    headline = summary_df[summary_df["group"] == "growth6"].copy()
    headline.to_csv(OUT / "headline.csv", index=False)

    assumptions = {
        "status": "research only; production V3.1 unchanged",
        "universe": NAMES,
        "period": [str(core.START_TS.date()), str(core.END_TS.date())],
        "strict_pit": "financial metrics become usable from fincore available_date based on NOTICE_DATE; UPDATE_DATE ignored",
        "round6_normalization": "median latest 4 positive (TTM basic EPS * clipped deduct-profit quality), min 2; TTM cash conversion diagnostic only",
        "realistic_growth": "clip(min(~3y normalized-EPS CAGR, ~3y revenue CAGR + 5pp), 0, 30%)",
        "round6_valuation": {
            "horizon_years": HORIZON_YEARS,
            "discount_rate": DISCOUNT_RATE,
            "terminal_growth": TERMINAL_GROWTH,
            "terminal_multiple_formula": "1/(r-g)",
        },
        "implied_growth_search": [0.0, IMPLIED_GROWTH_MAX],
        "execution_thresholds": {"buy": [0.85, 0.75, 0.65], "sell": [1.20, 1.40, 1.70]},
        "one_way_cost": core.ONE_WAY_COST,
        "rebalance": "month-end",
        "comparators": ["round5_5y_15x", "universal_geomean", "true_buyhold", "CSI300"],
        "scope_limit": "fixed-universe valuation/execution OOS; not historical qualitative hard-gate reconstruction",
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# V3.1 Round-6 untouched OOS — expectation gap / ten-year earning power",
        "",
        "> Research-only falsification. Production V3.1 remains unchanged.",
        "",
        "## Frozen model",
        "",
        "- Strict PIT financial availability uses NOTICE_DATE; mutable UPDATE_DATE is ignored.",
        "- Normalized EPS uses deduct-profit quality but does not mechanically multiply by current TTM cash conversion.",
        "- Realistic growth = min(~3y normalized-EPS CAGR, ~3y revenue CAGR + 5pp), clipped to 0..30%.",
        "- Ten-year earning-power value discounts at 10%, fades growth toward 3%, and uses Gordon-derived terminal multiple 1/(10%-3%).",
        "- Market-implied starting growth is solved with the same equation over 0..100%.",
        "- Existing V3.1 BUY/SELL bands, month-end cadence, 0.10% friction and cost-basis-independent SELL are unchanged.",
        "",
        "## Fresh OOS universe",
        "",
        pd.DataFrame([{"code": c, "name": n} for c, n in NAMES.items()]).to_markdown(index=False),
        "",
        "## Headline six-stock result",
        "",
        headline[["variant", "final_capital_rmb", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]].to_markdown(index=False),
        "",
        "## Expectation-gap diagnostics",
        "",
        diag_df.to_markdown(index=False),
        "",
        "## Individual strategy diagnostics",
        "",
        summary_df[summary_df["group"].str.startswith("single_")][["group", "variant", "final_capital_rmb", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]].to_markdown(index=False),
        "",
        "## Anti-overfit contract",
        "",
        "- Formula and six-stock universe were committed before this first successful output.",
        "- No Round-1..5 security appears in the Round-6 OOS universe.",
        "- All six securities were listed before the 2018 test start so the literal buy-and-hold comparison window is aligned.",
        "- No result-driven parameter tuning is performed in this run.",
        "- Any formula change after this report requires another untouched OOS universe.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n" + "\n".join(report), flush=True)


if __name__ == "__main__":
    main()
