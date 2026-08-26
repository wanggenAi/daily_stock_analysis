from __future__ import annotations

"""Round-3 diagnosis for the locked V3.1 PIT execution layer.

This is a falsification/attribution experiment, NOT a parameter-optimization run.
It consumes the already-persisted round-2 point-in-time panels and asks three
separate questions without changing the production V3.1 contract:

1) SELL drag: with the same BUY ladder and same valuation proxy, what happens if
   valuation-based REDUCE/CORE actions are disabled after entry?
2) Proxy fragility: with the same BUY/SELL ladder, how sensitive are results to
   PE-only, PB-only, and fixed 504/756/1260-day past-only anchors?
3) Signal pathology: after actual baseline SELL and BUY events, what happened over
   the following 12/24 months, and how often did PE/PB components strongly disagree?

No variant becomes a recommendation. We do not select the best-performing variant.
The production thresholds remain untouched.
"""

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

import v31_pit_sector_backtest as core
from v31_pit_oos_round2 import LOCKED_GROUPS, LOCKED_NAMES

BASE = Path("backtests/v31_pit_oos_round2")
OUT = Path("artifacts/v31_pit_diagnostic_round3")
MIN_HISTORY = 252


def load_panels() -> dict[str, pd.DataFrame]:
    panels: dict[str, pd.DataFrame] = {}
    for code in LOCKED_GROUPS["combined"]:
        p = BASE / f"panel_{code}.csv"
        if not p.exists():
            raise FileNotFoundError(f"missing persisted round-2 panel: {p}")
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["date"])
        for col in ["close", "pe_ttm", "pb", "pe_anchor", "pb_anchor", "price_to_neutral", "neutral_value", "ret"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "ret" not in df.columns:
            df["ret"] = df["close"].pct_change().fillna(0.0)
        panels[code] = df.sort_values("date").reset_index(drop=True)
    return panels


def rebuild_ratio(df: pd.DataFrame, mode: str, window: int = 756) -> pd.DataFrame:
    x = df.copy().sort_values("date").reset_index(drop=True)
    pe_pos = x["pe_ttm"].where(x["pe_ttm"] > 0)
    pb_pos = x["pb"].where(x["pb"] > 0)
    pe_anchor = pe_pos.shift(1).rolling(window, min_periods=MIN_HISTORY).median()
    pb_anchor = pb_pos.shift(1).rolling(window, min_periods=MIN_HISTORY).median()
    pe_rel = pe_pos / pe_anchor
    pb_rel = pb_pos / pb_anchor

    ratio = pd.Series(np.nan, index=x.index, dtype=float)
    if mode == "geomean":
        both = pe_rel.notna() & pb_rel.notna() & (pe_rel > 0) & (pb_rel > 0)
        ratio.loc[both] = np.sqrt(pe_rel.loc[both] * pb_rel.loc[both])
        pb_only = ~both & pb_rel.notna() & (pb_rel > 0)
        ratio.loc[pb_only] = pb_rel.loc[pb_only]
        pe_only = ratio.isna() & pe_rel.notna() & (pe_rel > 0)
        ratio.loc[pe_only] = pe_rel.loc[pe_only]
    elif mode == "pb_only":
        ratio = pb_rel.where(pb_rel > 0)
    elif mode == "pe_only":
        ratio = pe_rel.where(pe_rel > 0)
    else:
        raise ValueError(f"unknown mode={mode}")

    x["pe_anchor"] = pe_anchor
    x["pb_anchor"] = pb_anchor
    x["pe_rel_diag"] = pe_rel
    x["pb_rel_diag"] = pb_rel
    x["price_to_neutral"] = ratio
    x["neutral_value"] = x["close"] / ratio
    return x


def no_sell_policy(ratio: float, current_weight: float, cap: float) -> tuple[float, str]:
    """Diagnostic only: preserve frozen BUY ladder but never de-risk on valuation."""
    if not math.isfinite(ratio) or ratio <= 0:
        return current_weight, "HOLD_REVIEW"
    if ratio <= 0.65:
        return max(current_weight, 1.00 * cap), "BUY_FULL_MARGIN"
    if ratio <= 0.75:
        return max(current_weight, 0.75 * cap), "BUY_A_LEVEL"
    if ratio <= 0.85:
        return max(current_weight, 0.50 * cap), "BUY_STAGED"
    return current_weight, "HOLD_NO_SELL_DIAG"


def run_policy(
    panels: dict[str, pd.DataFrame],
    codes: list[str],
    label: str,
    *,
    disable_sell: bool = False,
) -> core.Result:
    old = core.desired_weight
    core.NAMES = LOCKED_NAMES
    try:
        if disable_sell:
            core.desired_weight = no_sell_policy
        return core.run_strategy(panels, codes, label)
    finally:
        core.desired_weight = old


def month_end_rows(df: pd.DataFrame) -> pd.DataFrame:
    x = df.sort_values("date").copy()
    return x.groupby(x["date"].dt.to_period("M"), sort=True).tail(1)


def forward_stats(panel: pd.DataFrame, dt: pd.Timestamp, horizon: int) -> dict[str, float]:
    x = panel.sort_values("date").reset_index(drop=True)
    hits = x.index[x["date"] == dt].tolist()
    if not hits:
        return {"ret": np.nan, "max_gain": np.nan, "max_drawdown": np.nan}
    i = hits[0]
    future = x.iloc[i + 1 : i + 1 + horizon]
    if len(future) < horizon:
        return {"ret": np.nan, "max_gain": np.nan, "max_drawdown": np.nan}
    p0 = float(x.loc[i, "close"])
    close = pd.to_numeric(future["close"], errors="coerce").dropna()
    if close.empty or not math.isfinite(p0) or p0 <= 0:
        return {"ret": np.nan, "max_gain": np.nan, "max_drawdown": np.nan}
    return {
        "ret": float(close.iloc[-1] / p0 - 1.0),
        "max_gain": float(close.max() / p0 - 1.0),
        "max_drawdown": float(close.min() / p0 - 1.0),
    }


def summarize_signal_outcomes(group: str, result: core.Result, raw: dict[str, pd.DataFrame]) -> dict:
    sells: list[dict] = []
    buys: list[dict] = []
    if result.trades.empty:
        return {
            "group": group,
            "sell_events": 0,
            "sell_median_12m_return": np.nan,
            "sell_share_12m_return_gt20": np.nan,
            "sell_median_12m_max_gain": np.nan,
            "sell_median_24m_max_gain": np.nan,
            "buy_events": 0,
            "buy_median_12m_return": np.nan,
            "buy_median_12m_max_drawdown": np.nan,
            "buy_share_12m_drawdown_le_minus30": np.nan,
        }

    for _, tr in result.trades.iterrows():
        dt = pd.Timestamp(tr["date"])
        code = str(tr["code"]).zfill(6)
        delta = float(tr["weight_change"])
        action = str(tr["action"])
        if delta < -1e-8 and action in {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}:
            s12 = forward_stats(raw[code], dt, 252)
            s24 = forward_stats(raw[code], dt, 504)
            sells.append({"ret12": s12["ret"], "gain12": s12["max_gain"], "gain24": s24["max_gain"]})
        elif delta > 1e-8 and action.startswith("BUY_"):
            b12 = forward_stats(raw[code], dt, 252)
            buys.append({"ret12": b12["ret"], "dd12": b12["max_drawdown"]})

    s = pd.DataFrame(sells)
    b = pd.DataFrame(buys)
    return {
        "group": group,
        "sell_events": int(len(s)),
        "sell_median_12m_return": float(s["ret12"].median()) if not s.empty else np.nan,
        "sell_share_12m_return_gt20": float((s["ret12"] > 0.20).mean()) if not s.empty else np.nan,
        "sell_median_12m_max_gain": float(s["gain12"].median()) if not s.empty else np.nan,
        "sell_median_24m_max_gain": float(s["gain24"].median()) if not s.empty else np.nan,
        "buy_events": int(len(b)),
        "buy_median_12m_return": float(b["ret12"].median()) if not b.empty else np.nan,
        "buy_median_12m_max_drawdown": float(b["dd12"].median()) if not b.empty else np.nan,
        "buy_share_12m_drawdown_le_minus30": float((b["dd12"] <= -0.30).mean()) if not b.empty else np.nan,
    }


def proxy_disagreement(group: str, geomean_panels: dict[str, pd.DataFrame], codes: list[str]) -> dict:
    vals: list[float] = []
    for code in codes:
        x = month_end_rows(geomean_panels[code])
        pe = pd.to_numeric(x["pe_rel_diag"], errors="coerce")
        pb = pd.to_numeric(x["pb_rel_diag"], errors="coerce")
        good = pe.notna() & pb.notna() & (pe > 0) & (pb > 0)
        if good.any():
            d = np.exp(np.abs(np.log(pe[good] / pb[good])))
            vals.extend([float(v) for v in d if math.isfinite(float(v))])
    a = np.array(vals, dtype=float)
    if len(a) == 0:
        return {"group": group, "observations": 0, "median_divergence_factor": np.nan, "p90_divergence_factor": np.nan, "share_over_2x": np.nan, "share_over_3x": np.nan}
    return {
        "group": group,
        "observations": int(len(a)),
        "median_divergence_factor": float(np.median(a)),
        "p90_divergence_factor": float(np.quantile(a, 0.90)),
        "share_over_2x": float(np.mean(a >= 2.0)),
        "share_over_3x": float(np.mean(a >= 3.0)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_panels()
    core.NAMES = LOCKED_NAMES

    # Pre-declared variants. None is selected as a winner after seeing results.
    variants = [
        ("baseline_geomean_756", "geomean", 756, False),
        ("same_buy_no_valuation_sell", "geomean", 756, True),
        ("pb_only_756", "pb_only", 756, False),
        ("pe_only_756", "pe_only", 756, False),
        ("geomean_504", "geomean", 504, False),
        ("geomean_1260", "geomean", 1260, False),
    ]

    panel_cache: dict[tuple[str, int], dict[str, pd.DataFrame]] = {}
    for _, mode, window, _ in variants:
        key = (mode, window)
        if key not in panel_cache:
            panel_cache[key] = {c: rebuild_ratio(raw[c], mode, window) for c in LOCKED_GROUPS["combined"]}

    summary_rows: list[dict] = []
    baseline_results: dict[str, core.Result] = {}
    result_map: dict[tuple[str, str], core.Result] = {}

    for group, codes in LOCKED_GROUPS.items():
        for vname, mode, window, disable_sell in variants:
            panels = panel_cache[(mode, window)]
            result = run_policy(panels, codes, f"DIAG_{group}_{vname}", disable_sell=disable_sell)
            result_map[(group, vname)] = result
            if vname == "baseline_geomean_756":
                baseline_results[group] = result
            row = dict(result.summary)
            row.update({"group": group, "variant": vname, "mode": mode, "anchor_window": window, "sell_disabled": disable_sell})
            summary_rows.append(row)

        bh = core.run_buy_hold(raw, codes, f"BUYHOLD_{group}")
        brow = core.metrics(bh, f"BUYHOLD_{group}")
        brow.update({"group": group, "variant": "buyhold", "mode": "none", "anchor_window": np.nan, "sell_disabled": False, "trades": np.nan, "avg_cash_weight": 0.0, "total_turnover": np.nan})
        summary_rows.append(brow)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "diagnostic_summary.csv", index=False)

    # Exact baseline reproduction check against persisted round-2 summary.
    stored = pd.read_csv(BASE / "summary.csv")
    repro_rows = []
    for group in LOCKED_GROUPS:
        got = summary[(summary["group"] == group) & (summary["variant"] == "baseline_geomean_756")].iloc[0]
        want = stored[stored["label"] == f"V31_{group}"].iloc[0]
        rel_err = abs(float(got["final_multiple"]) - float(want["final_multiple"])) / max(abs(float(want["final_multiple"])), 1e-12)
        repro_rows.append({"group": group, "stored_final_multiple": float(want["final_multiple"]), "reproduced_final_multiple": float(got["final_multiple"]), "relative_error": rel_err})
        if rel_err > 1e-10:
            raise AssertionError(f"baseline reproduction mismatch for {group}: {rel_err}")
    reproduction = pd.DataFrame(repro_rows)
    reproduction.to_csv(OUT / "baseline_reproduction_check.csv", index=False)

    # Approximate attribution: baseline -> no-sell isolates valuation SELL effect;
    # no-sell -> buyhold captures delayed/partial entry plus any remaining path effects.
    attribution_rows = []
    for group in LOCKED_GROUPS:
        base = summary[(summary.group == group) & (summary.variant == "baseline_geomean_756")].iloc[0]
        ns = summary[(summary.group == group) & (summary.variant == "same_buy_no_valuation_sell")].iloc[0]
        bh = summary[(summary.group == group) & (summary.variant == "buyhold")].iloc[0]
        attribution_rows.append({
            "group": group,
            "baseline_cagr": float(base.cagr),
            "no_sell_cagr": float(ns.cagr),
            "buyhold_cagr": float(bh.cagr),
            "sell_drag_cagr_pp": float(ns.cagr - base.cagr),
            "entry_underexposure_gap_cagr_pp": float(bh.cagr - ns.cagr),
            "baseline_max_drawdown": float(base.max_drawdown),
            "no_sell_max_drawdown": float(ns.max_drawdown),
            "buyhold_max_drawdown": float(bh.max_drawdown),
            "drawdown_cost_of_no_sell_pp": float(ns.max_drawdown - base.max_drawdown),
            "baseline_avg_cash": float(base.avg_cash_weight),
            "no_sell_avg_cash": float(ns.avg_cash_weight),
            "cash_reduction_when_sell_disabled_pp": float(base.avg_cash_weight - ns.avg_cash_weight),
        })
    attribution = pd.DataFrame(attribution_rows)
    attribution.to_csv(OUT / "attribution.csv", index=False)

    signal = pd.DataFrame([
        summarize_signal_outcomes(group, baseline_results[group], raw)
        for group in LOCKED_GROUPS
    ])
    signal.to_csv(OUT / "signal_forward_outcomes.csv", index=False)

    geo756 = panel_cache[("geomean", 756)]
    disagreement = pd.DataFrame([
        proxy_disagreement(group, geo756, codes)
        for group, codes in LOCKED_GROUPS.items()
    ])
    disagreement.to_csv(OUT / "proxy_component_disagreement.csv", index=False)

    sensitivity_rows = []
    sensitivity_variants = ["baseline_geomean_756", "pb_only_756", "pe_only_756", "geomean_504", "geomean_1260"]
    for group in LOCKED_GROUPS:
        x = summary[(summary.group == group) & (summary.variant.isin(sensitivity_variants))]
        vals = pd.to_numeric(x["cagr"], errors="coerce").dropna()
        sensitivity_rows.append({
            "group": group,
            "cagr_min": float(vals.min()),
            "cagr_max": float(vals.max()),
            "cagr_range_pp": float(vals.max() - vals.min()),
            "variant_count": int(len(vals)),
        })
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(OUT / "proxy_sensitivity.csv", index=False)

    # Fixed diagnostic labels; they describe fragility, not a new trading rule.
    verdicts = []
    for _, r in attribution.iterrows():
        group = r["group"]
        if r["sell_drag_cagr_pp"] >= 0.05:
            sell_text = "valuation SELL appears materially costly"
        elif r["sell_drag_cagr_pp"] >= 0.02:
            sell_text = "valuation SELL has a noticeable return cost"
        else:
            sell_text = "valuation SELL is not the dominant return drag"
        if r["entry_underexposure_gap_cagr_pp"] >= 0.05:
            entry_text = "delayed/partial entry and underexposure remain a major drag even with SELL disabled"
        elif r["entry_underexposure_gap_cagr_pp"] >= 0.02:
            entry_text = "entry underexposure remains a meaningful drag"
        else:
            entry_text = "entry underexposure is comparatively small"
        sens = sensitivity[sensitivity.group == group].iloc[0]
        if sens["cagr_range_pp"] >= 0.10:
            proxy_text = "valuation proxy is highly specification-sensitive"
        elif sens["cagr_range_pp"] >= 0.05:
            proxy_text = "valuation proxy shows meaningful specification sensitivity"
        else:
            proxy_text = "valuation proxy sensitivity is moderate/low in this test"
        verdicts.append(f"- **{group}**: {sell_text}; {entry_text}; {proxy_text}.")

    assumptions = {
        "source": "persisted round-2 PIT panels only",
        "production_rules_changed": False,
        "selection_rule": "none; no best variant is promoted",
        "variants": [v[0] for v in variants],
        "forward_horizons_trading_days": [252, 504],
        "sensitivity_windows": [504, 756, 1260],
        "limits": [
            "still conditional on the pre-declared research universe passing qualitative hard gates",
            "does not reconstruct historical moat/demand/predictability gate states",
            "no-sell attribution is path-dependent and should be read as diagnostic, not an exact causal decomposition",
            "PE/PB are relative historical valuation proxies, not intrinsic DCF/NAV values",
        ],
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    show_cols = ["group", "variant", "final_multiple", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]
    report = [
        "# V3.1 PIT round-3 diagnosis — attribution, not tuning",
        "",
        "> Production V3.1 rules are unchanged. This run is designed to locate failure modes, not to pick a prettier parameter set.",
        "",
        "## Baseline reproduction check",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Counterfactual / proxy diagnostics",
        "",
        summary[show_cols].to_markdown(index=False),
        "",
        "## Approximate return-drag attribution",
        "",
        attribution.to_markdown(index=False),
        "",
        "Interpretation: `sell_drag_cagr_pp = no-sell CAGR - baseline CAGR`. `entry_underexposure_gap_cagr_pp = buyhold CAGR - no-sell CAGR`. The second quantity is only an approximate underexposure diagnostic because the paths differ.",
        "",
        "## What happened after actual baseline SELL / BUY events",
        "",
        signal.to_markdown(index=False),
        "",
        "SELL forward statistics use only genuine negative weight changes caused by REDUCE_25 / REDUCE_50 / CORE_ONLY. BUY statistics use only positive weight changes. Incomplete 12/24-month windows are excluded from the corresponding medians.",
        "",
        "## PE vs PB component disagreement at month-end",
        "",
        disagreement.to_markdown(index=False),
        "",
        "A divergence factor of 2x means the PE-relative and PB-relative valuation components differ by a factor of two at the same month-end. Large disagreement is a warning that the geometric-mean proxy is mixing incompatible signals.",
        "",
        "## Specification sensitivity",
        "",
        sensitivity.to_markdown(index=False),
        "",
        "CAGR range is across pre-declared PE-only, PB-only, and 504/756/1260-day geometric-mean variants. A wide range is evidence of model fragility, not a reason to choose the best row.",
        "",
        "## Mechanical diagnostic labels",
        "",
        *verdicts,
        "",
        "## Limits",
        "",
        "- This is still an execution-layer test conditional on a fixed research universe; it is not a full historical reconstruction of qualitative V3.1 hard gates.",
        "- The neutral-value proxy remains historical relative PE/PB, not a true normalized-earnings DCF/NAV engine.",
        "- No production threshold is changed by this diagnosis.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
