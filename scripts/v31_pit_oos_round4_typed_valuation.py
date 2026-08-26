from __future__ import annotations

"""Round-4 untouched OOS test of a pre-declared typed valuation router.

IMPORTANT:
- The router specification is frozen in docs/V31_TYPED_VALUATION_DRAFT.md before
  this script's results are observed.
- Production V3.1 is NOT modified by this experiment.
- BUY/SELL thresholds, 756d past-only anchor, month-end cadence and 0.10% one-way
  cost remain frozen.
- The universe contains only Shanghai/Shenzhen main-board A shares and excludes
  every security used in rounds 1 and 2.
- The headline engine uses the round-3 corrected cash-constrained execution rule.
"""

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport

OUT = Path("artifacts/v31_pit_oos_round4_typed")

LOCKED_GROUPS = {
    "resource_asset": ["600362", "000807", "600547", "600988"],
    "stable_cashflow": ["600900", "600886", "600025", "000333"],
    "growth_tech": ["600183", "002463", "002916", "603160"],
    "combined": [
        "600362", "000807", "600547", "600988",
        "600900", "600886", "600025", "000333",
        "600183", "002463", "002916", "603160",
    ],
}

LOCKED_NAMES = {
    "600362": "江西铜业",
    "000807": "云铝股份",
    "600547": "山东黄金",
    "600988": "赤峰黄金",
    "600900": "长江电力",
    "600886": "国投电力",
    "600025": "华能水电",
    "000333": "美的集团",
    "600183": "生益科技",
    "002463": "沪电股份",
    "002916": "深南电路",
    "603160": "汇顶科技",
}

VALUATION_TYPE = {
    **{c: "RESOURCE_ASSET" for c in LOCKED_GROUPS["resource_asset"]},
    **{c: "STABLE_CASHFLOW" for c in LOCKED_GROUPS["stable_cashflow"]},
    **{c: "GROWTH_TECH_CONSENSUS" for c in LOCKED_GROUPS["growth_tech"]},
}


def _positive_relative(series: pd.Series, window: int = core.ANCHOR_WINDOW) -> tuple[pd.Series, pd.Series]:
    positive = series.where(series > 0)
    anchor = positive.shift(1).rolling(window, min_periods=core.ANCHOR_MIN).median()
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


def _typed_ratio(code: str, pe_rel: pd.Series, pb_rel: pd.Series) -> pd.Series:
    kind = VALUATION_TYPE[code]
    if kind == "RESOURCE_ASSET":
        return pb_rel.where((pb_rel > 0) & pb_rel.notna())
    if kind == "STABLE_CASHFLOW":
        return _universal_ratio(pe_rel, pb_rel)
    if kind == "GROWTH_TECH_CONSENSUS":
        out = pd.Series(np.nan, index=pe_rel.index, dtype=float)
        valid = pe_rel.notna() & pb_rel.notna() & (pe_rel > 0) & (pb_rel > 0)
        both_cheap = valid & (pe_rel < 1.0) & (pb_rel < 1.0)
        both_expensive = valid & (pe_rel > 1.0) & (pb_rel > 1.0)
        disagree = valid & ~(both_cheap | both_expensive)
        # BUY requires both components to be cheap; SELL requires both expensive.
        out.loc[both_cheap] = pd.concat([pe_rel, pb_rel], axis=1).max(axis=1).loc[both_cheap]
        out.loc[both_expensive] = pd.concat([pe_rel, pb_rel], axis=1).min(axis=1).loc[both_expensive]
        # Direction disagreement is uncertainty: do not manufacture a valuation action.
        out.loc[disagree] = 1.0
        return out
    raise ValueError(f"unknown valuation type for {code}: {kind}")


def build_panel(code: str) -> pd.DataFrame:
    price = transport.resilient_fetch_price(code)
    val = transport.resilient_fetch_valuation(code)
    df = price.merge(val, on="date", how="left").sort_values("date")
    df[["pe_ttm", "pb"]] = df[["pe_ttm", "pb"]].ffill()
    pe_rel, pe_anchor = _positive_relative(df["pe_ttm"])
    pb_rel, pb_anchor = _positive_relative(df["pb"])
    df["pe_anchor"] = pe_anchor
    df["pb_anchor"] = pb_anchor
    df["pe_rel"] = pe_rel
    df["pb_rel"] = pb_rel
    df["ratio_universal"] = _universal_ratio(pe_rel, pb_rel)
    df["ratio_typed"] = _typed_ratio(code, pe_rel, pb_rel)
    df["neutral_universal"] = df["close"] / df["ratio_universal"]
    df["neutral_typed"] = df["close"] / df["ratio_typed"]
    df["ret"] = df["close"].pct_change().fillna(0.0)
    df["code"] = code
    df["valuation_type"] = VALUATION_TYPE[code]
    return df[(df["date"] >= core.START_TS) & (df["date"] <= core.END_TS)].reset_index(drop=True)


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
            raw_targets = dict(weights)
            actions: dict[str, str] = {}
            for c in codes:
                ratio = panel.loc[dt, (c, "ratio")]
                if pd.isna(ratio):
                    raw_targets[c], actions[c] = weights[c], "HOLD_REVIEW"
                else:
                    raw_targets[c], actions[c] = core.desired_weight(float(ratio), weights[c], cap)

            # Corrected round-3 execution: explicit sells first, then only scale
            # incremental BUY requests when cash is insufficient.
            targets = dict(weights)
            for c in codes:
                if raw_targets[c] < weights[c]:
                    targets[c] = raw_targets[c]
            available_cash = max(0.0, 1.0 - sum(targets.values()))
            buy_requests = {c: max(0.0, raw_targets[c] - targets[c]) for c in codes}
            total_request = sum(buy_requests.values())
            buy_scale = min(1.0, available_cash / total_request) if total_request > 0 else 0.0
            for c in codes:
                targets[c] += buy_requests[c] * buy_scale

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
                        "name": LOCKED_NAMES[c],
                        "valuation_type": VALUATION_TYPE[c],
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
    if closes.empty:
        raise RuntimeError(f"no common buy-and-hold window for {label}")
    indexed = closes / closes.iloc[0]
    nav = indexed.mean(axis=1) * (1.0 - core.ONE_WAY_COST)
    nav.name = label
    return nav


def _decorate(summary: dict, group: str, variant: str) -> dict:
    x = dict(summary)
    x["group"] = group
    x["variant"] = variant
    return x


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panels: dict[str, pd.DataFrame] = {}
    for code in LOCKED_GROUPS["combined"]:
        print(f"FETCH {code} {LOCKED_NAMES[code]} type={VALUATION_TYPE[code]}", flush=True)
        panels[code] = build_panel(code)
        panels[code].to_csv(OUT / f"panel_{code}.csv", index=False)
        print(
            f"  rows={len(panels[code])} universal_ready={panels[code]['ratio_universal'].notna().sum()} typed_ready={panels[code]['ratio_typed'].notna().sum()}",
            flush=True,
        )

    summaries: list[dict] = []
    for group, codes in LOCKED_GROUPS.items():
        typed = run_cash_constrained(panels, codes, f"TYPED_{group}", "ratio_typed", "neutral_typed")
        universal = run_cash_constrained(panels, codes, f"UNIVERSAL_{group}", "ratio_universal", "neutral_universal")
        bh = true_buyhold(panels, codes, f"TRUE_BUYHOLD_{group}")

        typed.equity.to_csv(OUT / f"equity_typed_{group}.csv")
        typed.trades.to_csv(OUT / f"trades_typed_{group}.csv", index=False)
        universal.equity.to_csv(OUT / f"equity_universal_{group}.csv")
        universal.trades.to_csv(OUT / f"trades_universal_{group}.csv", index=False)
        bh.to_csv(OUT / f"true_buyhold_{group}.csv")

        summaries.append(_decorate(typed.summary, group, "typed_router"))
        summaries.append(_decorate(universal.summary, group, "universal_geomean"))
        summaries.append(_decorate(core.metrics(bh, f"TRUE_BUYHOLD_{group}"), group, "true_buyhold"))

    csi = transport.resilient_fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    summaries.append(_decorate(core.metrics(csi, "CSI300"), "benchmark", "csi300"))

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT / "summary.csv", index=False)

    comparisons = []
    for group in LOCKED_GROUPS:
        t = summary_df[(summary_df.group == group) & (summary_df.variant == "typed_router")].iloc[0]
        u = summary_df[(summary_df.group == group) & (summary_df.variant == "universal_geomean")].iloc[0]
        b = summary_df[(summary_df.group == group) & (summary_df.variant == "true_buyhold")].iloc[0]
        comparisons.append({
            "group": group,
            "typed_cagr": t.cagr,
            "universal_cagr": u.cagr,
            "true_buyhold_cagr": b.cagr,
            "typed_minus_universal_cagr_pp": t.cagr - u.cagr,
            "typed_minus_buyhold_cagr_pp": t.cagr - b.cagr,
            "typed_max_drawdown": t.max_drawdown,
            "universal_max_drawdown": u.max_drawdown,
            "true_buyhold_max_drawdown": b.max_drawdown,
            "typed_sharpe": t.sharpe,
            "universal_sharpe": u.sharpe,
            "true_buyhold_sharpe": b.sharpe,
            "typed_avg_cash": t.avg_cash_weight,
            "universal_avg_cash": u.avg_cash_weight,
        })
    comp_df = pd.DataFrame(comparisons)
    comp_df.to_csv(OUT / "comparison.csv", index=False)

    assumptions = {
        "status": "research-only typed valuation OOS; production V3.1 unchanged",
        "window": [str(core.START_TS.date()), str(core.END_TS.date())],
        "groups": LOCKED_GROUPS,
        "names": LOCKED_NAMES,
        "valuation_type": VALUATION_TYPE,
        "anchor_window": core.ANCHOR_WINDOW,
        "anchor_min": core.ANCHOR_MIN,
        "one_way_cost": core.ONE_WAY_COST,
        "rebalance": "month-end",
        "buy_ladder": {"<=0.85": 0.50, "<=0.75": 0.75, "<=0.65": 1.00},
        "sell_ladder": {">=1.20": 0.75, ">=1.40": 0.50, ">=1.70": 0.25},
        "typed_rules": {
            "RESOURCE_ASSET": "PB / shifted trailing-756d positive-PB median",
            "STABLE_CASHFLOW": "existing PE/PB relative geometric mean with one-component fallback",
            "GROWTH_TECH_CONSENSUS": "both cheap -> max(PErel,PBrel); both expensive -> min(PErel,PBrel); disagreement -> 1.0; missing component -> HOLD_REVIEW",
        },
        "execution": "cash-constrained corrected engine: sells first, scale only incremental buys",
        "important_limit": "valuation/execution-layer PIT test conditional on a fixed research universe; not a full historical hard-gate reconstruction",
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# V3.1 typed valuation — round-4 untouched OOS",
        "",
        "> Research-only falsification test. Production V3.1 remains unchanged.",
        "",
        "## Pre-declared economic router",
        "",
        "- RESOURCE_ASSET: PB-relative historical proxy (future production target: NAV + normalized cycle earnings).",
        "- STABLE_CASHFLOW: frozen PE/PB relative geometric mean.",
        "- GROWTH_TECH_CONSENSUS: PE and PB must agree in direction before valuation changes position size.",
        "- BUY/SELL thresholds, 756-day past-only anchor, month-end rebalance and 0.10% one-way friction are unchanged.",
        "- Corrected execution never creates a sale in one holding merely to fund another holding's BUY request.",
        "",
        "## Fresh locked universe",
        "",
        pd.DataFrame([
            {"code": c, "name": LOCKED_NAMES[c], "valuation_type": VALUATION_TYPE[c]}
            for c in LOCKED_GROUPS["combined"]
        ]).to_markdown(index=False),
        "",
        "## Results",
        "",
        summary_df[["group", "variant", "final_capital_rmb", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]].to_markdown(index=False),
        "",
        "## Typed vs universal vs literal buy-and-hold",
        "",
        comp_df.to_markdown(index=False),
        "",
        "## Anti-overfit checks",
        "",
        "- Router rules were committed in docs/V31_TYPED_VALUATION_DRAFT.md before this OOS run.",
        "- No security from rounds 1 or 2 appears in this 12-stock universe.",
        "- No threshold is tuned from round-4 output.",
        "- Rolling anchors are shifted one trading day and use only past observations.",
        "- True buy-and-hold is initial equal-dollar and zero-rebalance, not the old daily equal-weight benchmark.",
        "- Missing/invalid growth-tech valuation components produce HOLD_REVIEW rather than a fabricated target.",
        "",
        "## Interpretation rule",
        "",
        "A typed-router win is not sufficient to promote it to production. A loss is evidence against the draft. Any post-result rule change requires a new untouched universe.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n" + "\n".join(report), flush=True)


if __name__ == "__main__":
    main()
