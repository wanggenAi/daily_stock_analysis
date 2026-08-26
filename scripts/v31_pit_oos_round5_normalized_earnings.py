from __future__ import annotations

"""Round-5 untouched OOS: strict-PIT normalized-earnings neutral value vs old proxy.

Research-only. The valuation formula and universe are frozen in
`docs/V31_NORMALIZED_EARNINGS_VALUATION_DRAFT.md` before results.
Production V3.1 remains unchanged.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd

import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport
import v31_pit_normalized_earnings_panel as fincore

OUT = Path("artifacts/v31_pit_oos_round5_normalized_earnings")

NAMES = {
    "002371": "北方华创",
    "002475": "立讯精密",
    "002384": "东山精密",
    "600584": "长电科技",
    "603228": "景旺电子",
    "600703": "三安光电",
}
ALL_CODES = list(NAMES)
GROUPS = {"growth6": ALL_CODES, **{f"single_{c}": [c] for c in ALL_CODES}}

DISCOUNT_RATE = 0.10
GROWTH_HAIRCUT = 0.50
GROWTH_CAP = 0.15
TERMINAL_GROWTH_TARGET = 0.03
TERMINAL_PE = 15.0


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


def value_owner_earnings(owner_eps: float, start_growth: float) -> float:
    if not np.isfinite(owner_eps) or owner_eps <= 0:
        return np.nan
    start_growth = float(np.clip(start_growth, 0.0, GROWTH_CAP))
    end_growth = min(start_growth, TERMINAL_GROWTH_TARGET)
    earnings = float(owner_eps)
    pv = 0.0
    for year in range(1, 6):
        if year == 1:
            g = start_growth
        else:
            frac = (year - 1) / 4.0
            g = start_growth + (end_growth - start_growth) * frac
        earnings *= 1.0 + g
        pv += earnings / ((1.0 + DISCOUNT_RATE) ** year)
    pv += TERMINAL_PE * earnings / ((1.0 + DISCOUNT_RATE) ** 5)
    return float(pv)


def enrich_financials(code: str) -> pd.DataFrame:
    f = fincore.build_company(code).copy()
    eps = pd.to_numeric(f["ttm_basic_eps_approx"], errors="coerce")
    parent_np = pd.to_numeric(f["ttm_parent_netprofit"], errors="coerce")
    dq = pd.to_numeric(f["deduct_quality"], errors="coerce")
    cc = pd.to_numeric(f["cash_conversion"], errors="coerce")

    valid = (eps > 0) & (parent_np > 0) & (dq > 0) & (cc > 0)
    quality_factor = pd.concat(
        [pd.Series(1.0, index=f.index), dq, cc], axis=1
    ).min(axis=1)
    quality_factor = quality_factor.where(valid)
    f["quality_factor"] = quality_factor
    f["quality_adjusted_eps"] = (eps * quality_factor).where(valid)
    positive_qe = f["quality_adjusted_eps"].where(f["quality_adjusted_eps"] > 0)
    f["normalized_owner_eps"] = positive_qe.rolling(4, min_periods=2).median()

    hist_growth = []
    assumed_growth = []
    report_dates = pd.to_datetime(f["report_date"], errors="coerce")
    norm = pd.to_numeric(f["normalized_owner_eps"], errors="coerce")
    for i, (d, cur) in enumerate(zip(report_dates, norm)):
        if pd.isna(d) or pd.isna(cur) or cur <= 0:
            hist_growth.append(np.nan)
            assumed_growth.append(0.0)
            continue
        cutoff = d - pd.DateOffset(years=3)
        candidates = [j for j in range(i) if pd.notna(report_dates.iloc[j]) and report_dates.iloc[j] <= cutoff and pd.notna(norm.iloc[j]) and norm.iloc[j] > 0]
        if not candidates:
            hist_growth.append(np.nan)
            assumed_growth.append(0.0)
            continue
        j = candidates[-1]
        past = float(norm.iloc[j])
        years = max((d - report_dates.iloc[j]).days / 365.25, 0.01)
        g = (float(cur) / past) ** (1.0 / years) - 1.0 if past > 0 else np.nan
        hist_growth.append(g)
        assumed_growth.append(float(np.clip(max(0.0, GROWTH_HAIRCUT * g) if np.isfinite(g) else 0.0, 0.0, GROWTH_CAP)))
    f["historical_owner_eps_growth"] = hist_growth
    f["assumed_growth"] = assumed_growth
    f["neutral_value_fundamental"] = [
        value_owner_earnings(e, g)
        for e, g in zip(f["normalized_owner_eps"], f["assumed_growth"])
    ]
    f["code"] = code
    f["name"] = NAMES[code]
    return f


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
    signals = f[["report_date", "available_date", "normalized_owner_eps", "historical_owner_eps_growth", "assumed_growth", "neutral_value_fundamental", "quality_factor"]].copy()
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
    d["ratio_fundamental"] = d["close"] / d["neutral_value_fundamental"]
    d.loc[(d["neutral_value_fundamental"] <= 0) | ~np.isfinite(d["neutral_value_fundamental"]), "ratio_fundamental"] = np.nan
    d["ret"] = d["close"].pct_change().fillna(0.0)
    d["code"] = code
    d = d[(d["date"] >= core.START_TS) & (d["date"] <= core.END_TS)].reset_index(drop=True)
    return d, f


def _month_ends(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.to_period("M")).max().tolist())


def run_cash_constrained(panels: dict[str, pd.DataFrame], codes: list[str], label: str, ratio_col: str, neutral_col: str) -> core.Result:
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
    records, trades = [], []

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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panels, financials = {}, {}
    for code, name in NAMES.items():
        print(f"FETCH ROUND5 {code} {name}", flush=True)
        panel, fin = build_daily_panel(code)
        panels[code], financials[code] = panel, fin
        panel.to_csv(OUT / f"panel_{code}.csv", index=False)
        fin.to_csv(OUT / f"financial_{code}.csv", index=False)
        print(
            f"  daily={len(panel)} fundamental_ready={panel['ratio_fundamental'].notna().sum()} universal_ready={panel['ratio_universal'].notna().sum()}",
            flush=True,
        )

    summaries = []
    for group, codes in GROUPS.items():
        fundamental = run_cash_constrained(panels, codes, f"NORMALIZED_EARNINGS_{group}", "ratio_fundamental", "neutral_value_fundamental")
        universal = run_cash_constrained(panels, codes, f"UNIVERSAL_GEOMEAN_{group}", "ratio_universal", "neutral_universal")
        bh = true_buyhold(panels, codes, f"TRUE_BUYHOLD_{group}")

        fundamental.equity.to_csv(OUT / f"equity_fundamental_{group}.csv")
        fundamental.trades.to_csv(OUT / f"trades_fundamental_{group}.csv", index=False)
        universal.equity.to_csv(OUT / f"equity_universal_{group}.csv")
        universal.trades.to_csv(OUT / f"trades_universal_{group}.csv", index=False)
        bh.to_csv(OUT / f"true_buyhold_{group}.csv")

        summaries.extend([
            decorate(fundamental.summary, group, "normalized_earnings"),
            decorate(universal.summary, group, "universal_geomean"),
            decorate(core.metrics(bh, f"TRUE_BUYHOLD_{group}"), group, "true_buyhold"),
        ])

    csi = transport.resilient_fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    summaries.append(decorate(core.metrics(csi, "CSI300"), "benchmark", "csi300"))
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "summary.csv", index=False)

    headline = summary_df[summary_df["group"] == "growth6"].copy()
    comp = {}
    for variant in ["normalized_earnings", "universal_geomean", "true_buyhold"]:
        row = headline[headline["variant"] == variant].iloc[0]
        comp[variant] = {
            "final_capital_rmb": float(row["final_capital_rmb"]),
            "cagr": float(row["cagr"]),
            "max_drawdown": float(row["max_drawdown"]),
            "sharpe": float(row["sharpe"]),
            "trades": None if pd.isna(row.get("trades")) else float(row.get("trades")),
            "avg_cash_weight": None if pd.isna(row.get("avg_cash_weight")) else float(row.get("avg_cash_weight")),
        }
    (OUT / "headline.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")

    assumptions = {
        "status": "research only; production V3.1 unchanged",
        "universe": NAMES,
        "period": [str(core.START_TS.date()), str(core.END_TS.date())],
        "strict_pit": "financial metrics usable only from max(profit NOTICE_DATE, cashflow NOTICE_DATE); UPDATE_DATE ignored",
        "quality_factor": "min(1, deduct_quality, cash_conversion), requires positive EPS/NP/deduct/cash conversion",
        "normalization": "median latest 4 positive quality-adjusted TTM EPS, min 2",
        "growth": {"historical_window_years": 3, "haircut": GROWTH_HAIRCUT, "cap": GROWTH_CAP, "floor": 0.0},
        "valuation": {"discount_rate": DISCOUNT_RATE, "terminal_growth_target": TERMINAL_GROWTH_TARGET, "terminal_pe": TERMINAL_PE, "horizon_years": 5},
        "execution_thresholds": {"buy": [0.85, 0.75, 0.65], "sell": [1.20, 1.40, 1.70]},
        "one_way_cost": core.ONE_WAY_COST,
        "rebalance": "month-end",
        "scope_limit": "fixed-universe valuation/execution OOS; not historical qualitative hard-gate reconstruction",
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# V3.1 Round-5 untouched OOS — normalized earnings neutral value",
        "",
        "> Research-only falsification. Production V3.1 is unchanged.",
        "",
        "## Frozen model",
        "",
        "- Financials become usable only from NOTICE_DATE; UPDATE_DATE is ignored.",
        "- Quality-adjusted TTM EPS is haircutted by the weaker of deduct-profit quality and operating-cash conversion, never boosted above reported EPS.",
        "- Normalized earning power is the rolling median of the latest four positive quality-adjusted TTM EPS observations.",
        "- Starting growth = 50% of historical ~3y normalized-owner-EPS CAGR, floored at 0 and capped at 15%.",
        "- Five-year earnings-power value uses 10% discount rate, growth fade toward min(start growth,3%), and 15x terminal owner earnings.",
        "- Existing V3.1 BUY/SELL bands, month-end cadence, 0.10% friction and cost-basis-independent SELL remain unchanged.",
        "",
        "## Fresh OOS universe",
        "",
        pd.DataFrame([{"code": c, "name": n} for c, n in NAMES.items()]).to_markdown(index=False),
        "",
        "## Headline six-stock result",
        "",
        headline[["variant", "final_capital_rmb", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]].to_markdown(index=False),
        "",
        "## Individual diagnostics",
        "",
        summary_df[summary_df["group"].str.startswith("single_")][["group", "variant", "final_capital_rmb", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]].to_markdown(index=False),
        "",
        "## Anti-overfit contract",
        "",
        "- Formula and six-stock universe were committed before this output existed.",
        "- No Round-1..4 security appears in the Round-5 OOS universe.",
        "- No result-driven parameter tuning is performed in this run.",
        "- Any formula change after this report requires another untouched OOS universe.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n" + "\n".join(report), flush=True)


if __name__ == "__main__":
    main()
