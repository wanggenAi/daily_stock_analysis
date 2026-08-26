from __future__ import annotations

"""Round-3 diagnosis for the locked V3.1 PIT execution layer.

This is a falsification / implementation-audit experiment, NOT a parameter-
optimization run. It consumes the already-persisted round-2 PIT panels and asks:

1) Is the old benchmark really buy-and-hold?
2) Does the core target-normalization step create trades not implied by V3.1?
3) After removing those simulation artifacts, how much return drag comes from the
   valuation SELL ladder versus delayed / partial entry?
4) How fragile is the PE/PB historical-relative neutral-value proxy?
5) What happened after genuine SELL and BUY events over the next 12/24 months?

No diagnostic variant becomes a recommendation and no production threshold is
changed here.
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
        path = BASE / f"panel_{code}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing persisted round-2 panel: {path}")
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])
        for col in [
            "close", "pe_ttm", "pb", "pe_anchor", "pb_anchor",
            "price_to_neutral", "neutral_value", "ret",
        ]:
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
    """Diagnostic only: preserve frozen BUY ladder but never valuation-de-risk."""
    if not math.isfinite(ratio) or ratio <= 0:
        return current_weight, "HOLD_REVIEW"
    if ratio <= 0.65:
        return max(current_weight, 1.00 * cap), "BUY_FULL_MARGIN"
    if ratio <= 0.75:
        return max(current_weight, 0.75 * cap), "BUY_A_LEVEL"
    if ratio <= 0.85:
        return max(current_weight, 0.50 * cap), "BUY_STAGED"
    return current_weight, "HOLD_NO_SELL_DIAG"


def _month_end_dates(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    s = pd.Series(index=index, data=index)
    return set(s.groupby(index.to_period("M")).max().tolist())


def run_cash_constrained_strategy(
    panels: dict[str, pd.DataFrame],
    codes: list[str],
    label: str,
    policy,
) -> core.Result:
    """Same V3.1 policy, but buys are cash-constrained without cross-normalizing holdings.

    Core v31_pit_sector_backtest normalizes *all* targets when raw targets sum above
    100%. That can reduce a HOLD or even a BUY-labelled position because another
    stock requested capital. This diagnostic engine instead executes explicit sells
    first, then scales only positive buy requests to available cash.
    """
    frames = []
    for code in codes:
        x = panels[code].set_index("date")[["ret", "close", "price_to_neutral", "neutral_value"]].copy()
        x.columns = pd.MultiIndex.from_product([[code], x.columns])
        frames.append(x)
    panel = pd.concat(frames, axis=1).sort_index()
    panel = panel[(panel.index >= core.START_TS) & (panel.index <= core.END_TS)].ffill()
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
                ratio = panel.loc[dt, (c, "price_to_neutral")]
                if pd.isna(ratio):
                    raw_targets[c], actions[c] = weights[c], "HOLD_REVIEW"
                else:
                    raw_targets[c], actions[c] = policy(float(ratio), weights[c], cap)

            # Execute direct de-risking first. Never sell an unrelated holding merely
            # because another stock requests a BUY allocation.
            targets = dict(weights)
            for c in codes:
                if raw_targets[c] < weights[c]:
                    targets[c] = raw_targets[c]

            available_cash = max(0.0, 1.0 - sum(targets.values()))
            buy_requests = {c: max(0.0, raw_targets[c] - targets[c]) for c in codes}
            total_request = sum(buy_requests.values())
            scale = min(1.0, available_cash / total_request) if total_request > 0 else 0.0
            for c in codes:
                targets[c] += buy_requests[c] * scale

            turnover = sum(abs(targets[c] - weights[c]) for c in codes)
            cost = turnover * core.ONE_WAY_COST
            nav *= 1.0 - cost
            for c in codes:
                delta = targets[c] - weights[c]
                if abs(delta) > 1e-8:
                    ratio = panel.loc[dt, (c, "price_to_neutral")]
                    trades.append({
                        "strategy": label,
                        "date": dt,
                        "code": c,
                        "name": LOCKED_NAMES[c],
                        "action": actions[c],
                        "price_to_neutral": float(ratio) if pd.notna(ratio) else np.nan,
                        "neutral_value": panel.loc[dt, (c, "neutral_value")],
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


def run_legacy_strategy(
    panels: dict[str, pd.DataFrame],
    codes: list[str],
    label: str,
    policy,
) -> core.Result:
    old = core.desired_weight
    core.NAMES = LOCKED_NAMES
    try:
        core.desired_weight = policy
        return core.run_strategy(panels, codes, label)
    finally:
        core.desired_weight = old


def _returns_matrix(panels: dict[str, pd.DataFrame], codes: list[str]) -> pd.DataFrame:
    rets = pd.concat({c: panels[c].set_index("date")["ret"] for c in codes}, axis=1).sort_index()
    return rets[(rets.index >= core.START_TS) & (rets.index <= core.END_TS)].fillna(0.0)


def _prepend_initial_one(nav: pd.Series) -> pd.Series:
    if nav.empty:
        return nav
    start = nav.index[0] - pd.Timedelta(days=1)
    out = pd.concat([pd.Series([1.0], index=[start]), nav])
    out.name = nav.name
    return out


def run_true_buy_hold(panels: dict[str, pd.DataFrame], codes: list[str], label: str) -> pd.Series:
    """Initial equal-dollar purchase; holdings then drift with zero rebalancing."""
    rets = _returns_matrix(panels, codes)
    growth = (1.0 + rets).cumprod()
    nav = growth.mean(axis=1) * (1.0 - core.ONE_WAY_COST)
    nav.name = label
    return _prepend_initial_one(nav)


def run_legacy_daily_equal_weight(panels: dict[str, pd.DataFrame], codes: list[str], label: str) -> pd.Series:
    """Replicate old 'BUYHOLD': fixed equal weights are effectively reset every day."""
    rets = _returns_matrix(panels, codes)
    nav = (1.0 + rets.mean(axis=1)).cumprod() * (1.0 - core.ONE_WAY_COST)
    nav.name = label
    return _prepend_initial_one(nav)


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
        return {"group": group, "sell_events": 0, "buy_events": 0}

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


def legacy_normalization_artifacts(group: str, result: core.Result) -> dict:
    if result.trades.empty:
        return {"group": group, "trade_rows": 0, "direction_mismatch_rows": 0, "mismatch_turnover": 0.0, "mismatch_share_of_turnover": 0.0}
    bad = []
    for _, tr in result.trades.iterrows():
        action = str(tr["action"])
        delta = float(tr["weight_change"])
        expected = 1 if action.startswith("BUY_") else -1 if action in {"REDUCE_25", "REDUCE_50", "CORE_ONLY"} else 0
        mismatch = (expected == 1 and delta < 0) or (expected == -1 and delta > 0) or (expected == 0 and abs(delta) > 1e-8)
        if mismatch:
            bad.append(abs(delta))
    total_turnover = float(result.summary.get("total_turnover", 0.0))
    mismatch_turnover = float(sum(bad))
    return {
        "group": group,
        "trade_rows": int(len(result.trades)),
        "direction_mismatch_rows": int(len(bad)),
        "mismatch_turnover": mismatch_turnover,
        "mismatch_share_of_turnover": mismatch_turnover / total_turnover if total_turnover > 0 else 0.0,
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
        return {"group": group, "observations": 0}
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

    # Pre-declared; the best row is never auto-promoted.
    ratio_specs = {
        "geomean_756": ("geomean", 756),
        "pb_only_756": ("pb_only", 756),
        "pe_only_756": ("pe_only", 756),
        "geomean_504": ("geomean", 504),
        "geomean_1260": ("geomean", 1260),
    }
    panel_cache = {
        name: {c: rebuild_ratio(raw[c], mode, window) for c in LOCKED_GROUPS["combined"]}
        for name, (mode, window) in ratio_specs.items()
    }

    summary_rows: list[dict] = []
    legacy_baseline: dict[str, core.Result] = {}
    corrected_baseline: dict[str, core.Result] = {}
    corrected_no_sell: dict[str, core.Result] = {}

    for group, codes in LOCKED_GROUPS.items():
        geo = panel_cache["geomean_756"]

        legacy = run_legacy_strategy(geo, codes, f"LEGACY_{group}", core.desired_weight)
        legacy_baseline[group] = legacy
        row = dict(legacy.summary)
        row.update({"group": group, "variant": "legacy_engine_geomean_756"})
        summary_rows.append(row)

        corrected = run_cash_constrained_strategy(geo, codes, f"CORRECTED_{group}", core.desired_weight)
        corrected_baseline[group] = corrected
        row = dict(corrected.summary)
        row.update({"group": group, "variant": "corrected_engine_geomean_756"})
        summary_rows.append(row)

        no_sell = run_cash_constrained_strategy(geo, codes, f"NOSELL_{group}", no_sell_policy)
        corrected_no_sell[group] = no_sell
        row = dict(no_sell.summary)
        row.update({"group": group, "variant": "corrected_same_buy_no_valuation_sell"})
        summary_rows.append(row)

        for spec in ["pb_only_756", "pe_only_756", "geomean_504", "geomean_1260"]:
            res = run_cash_constrained_strategy(panel_cache[spec], codes, f"DIAG_{group}_{spec}", core.desired_weight)
            row = dict(res.summary)
            row.update({"group": group, "variant": f"corrected_{spec}"})
            summary_rows.append(row)

        true_bh = run_true_buy_hold(raw, codes, f"TRUE_BUYHOLD_{group}")
        row = core.metrics(true_bh, f"TRUE_BUYHOLD_{group}")
        row.update({"group": group, "variant": "true_buyhold", "trades": np.nan, "avg_cash_weight": 0.0, "total_turnover": np.nan})
        summary_rows.append(row)

        old_bh = run_legacy_daily_equal_weight(raw, codes, f"LEGACY_DAILY_EQ_{group}")
        row = core.metrics(old_bh, f"LEGACY_DAILY_EQ_{group}")
        row.update({"group": group, "variant": "legacy_daily_equal_weight_benchmark", "trades": np.nan, "avg_cash_weight": 0.0, "total_turnover": np.nan})
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "diagnostic_summary.csv", index=False)

    # Reproduce the persisted strategy itself exactly before diagnosing it.
    stored = pd.read_csv(BASE / "summary.csv")
    repro_rows = []
    for group in LOCKED_GROUPS:
        got = legacy_baseline[group].summary
        want = stored[stored["label"] == f"V31_{group}"].iloc[0]
        rel_err = abs(float(got["final_multiple"]) - float(want["final_multiple"])) / max(abs(float(want["final_multiple"])), 1e-12)
        repro_rows.append({
            "group": group,
            "stored_final_multiple": float(want["final_multiple"]),
            "reproduced_final_multiple": float(got["final_multiple"]),
            "relative_error": rel_err,
        })
        if rel_err > 1e-10:
            raise AssertionError(f"baseline reproduction mismatch for {group}: {rel_err}")
    reproduction = pd.DataFrame(repro_rows)
    reproduction.to_csv(OUT / "baseline_reproduction_check.csv", index=False)

    implementation = pd.DataFrame([
        legacy_normalization_artifacts(group, legacy_baseline[group])
        for group in LOCKED_GROUPS
    ])
    implementation.to_csv(OUT / "legacy_normalization_artifacts.csv", index=False)

    # Approximate attribution after using the semantics-preserving cash-constrained engine.
    attribution_rows = []
    for group in LOCKED_GROUPS:
        legacy = summary[(summary["group"] == group) & (summary["variant"] == "legacy_engine_geomean_756")].iloc[0]
        base = summary[(summary["group"] == group) & (summary["variant"] == "corrected_engine_geomean_756")].iloc[0]
        ns = summary[(summary["group"] == group) & (summary["variant"] == "corrected_same_buy_no_valuation_sell")].iloc[0]
        bh = summary[(summary["group"] == group) & (summary["variant"] == "true_buyhold")].iloc[0]
        old_bh = summary[(summary["group"] == group) & (summary["variant"] == "legacy_daily_equal_weight_benchmark")].iloc[0]
        attribution_rows.append({
            "group": group,
            "engine_artifact_cagr_pp": float(base["cagr"] - legacy["cagr"]),
            "baseline_cagr_corrected_engine": float(base["cagr"]),
            "no_sell_cagr": float(ns["cagr"]),
            "true_buyhold_cagr": float(bh["cagr"]),
            "legacy_benchmark_cagr": float(old_bh["cagr"]),
            "benchmark_definition_gap_cagr_pp": float(bh["cagr"] - old_bh["cagr"]),
            "sell_drag_cagr_pp": float(ns["cagr"] - base["cagr"]),
            "entry_underexposure_gap_cagr_pp": float(bh["cagr"] - ns["cagr"]),
            "baseline_max_drawdown": float(base["max_drawdown"]),
            "no_sell_max_drawdown": float(ns["max_drawdown"]),
            "true_buyhold_max_drawdown": float(bh["max_drawdown"]),
            "baseline_avg_cash": float(base["avg_cash_weight"]),
            "no_sell_avg_cash": float(ns["avg_cash_weight"]),
        })
    attribution = pd.DataFrame(attribution_rows)
    attribution.to_csv(OUT / "attribution.csv", index=False)

    signal = pd.DataFrame([
        summarize_signal_outcomes(group, corrected_baseline[group], raw)
        for group in LOCKED_GROUPS
    ])
    signal.to_csv(OUT / "signal_forward_outcomes.csv", index=False)

    disagreement = pd.DataFrame([
        proxy_disagreement(group, panel_cache["geomean_756"], codes)
        for group, codes in LOCKED_GROUPS.items()
    ])
    disagreement.to_csv(OUT / "proxy_component_disagreement.csv", index=False)

    sensitivity_rows = []
    sens_variants = [
        "corrected_engine_geomean_756", "corrected_pb_only_756", "corrected_pe_only_756",
        "corrected_geomean_504", "corrected_geomean_1260",
    ]
    for group in LOCKED_GROUPS:
        x = summary[(summary["group"] == group) & (summary["variant"].isin(sens_variants))]
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

    verdicts = []
    for _, r in attribution.iterrows():
        group = r["group"]
        sell_drag = float(r["sell_drag_cagr_pp"])
        entry_gap = float(r["entry_underexposure_gap_cagr_pp"])
        sens = float(sensitivity[sensitivity["group"] == group].iloc[0]["cagr_range_pp"])
        if sell_drag >= 0.05:
            sell_text = "valuation SELL is materially costly"
        elif sell_drag >= 0.02:
            sell_text = "valuation SELL has a noticeable return cost"
        else:
            sell_text = "valuation SELL is not the dominant return drag"
        if entry_gap >= 0.05:
            entry_text = "delayed/partial entry remains a major underexposure drag"
        elif entry_gap >= 0.02:
            entry_text = "entry underexposure remains meaningful"
        else:
            entry_text = "entry underexposure is comparatively small"
        if sens >= 0.10:
            proxy_text = "valuation proxy is highly specification-sensitive"
        elif sens >= 0.05:
            proxy_text = "valuation proxy has meaningful specification sensitivity"
        else:
            proxy_text = "valuation proxy sensitivity is moderate/low"
        verdicts.append(f"- **{group}**: {sell_text}; {entry_text}; {proxy_text}.")

    assumptions = {
        "source": "persisted round-2 PIT panels only",
        "production_rules_changed": False,
        "no_best_variant_selection": True,
        "corrected_engine_change": "execute explicit sells first, then scale only positive BUY requests to available cash; no cross-normalization of unrelated holdings",
        "true_buyhold_definition": "initial equal-dollar purchase, zero subsequent rebalancing",
        "forward_horizons_trading_days": [252, 504],
        "proxy_windows": [504, 756, 1260],
        "limits": [
            "still conditional on the pre-declared research universe passing qualitative hard gates",
            "does not reconstruct historical moat/demand/predictability states",
            "no-sell attribution is path-dependent and not an exact causal decomposition",
            "PE/PB are historical-relative proxies, not intrinsic DCF/NAV values",
        ],
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    show_cols = ["group", "variant", "final_multiple", "cagr", "max_drawdown", "sharpe", "trades", "avg_cash_weight"]
    report = [
        "# V3.1 PIT round-3 diagnosis — implementation audit + attribution",
        "",
        "> Production V3.1 rules are unchanged. This run diagnoses the backtest and the valuation/execution layer; it does not optimize thresholds.",
        "",
        "## 1. Exact reproduction of the persisted V3.1 strategy",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## 2. Important benchmark audit",
        "",
        "The previous function named `run_buy_hold` used a fixed equal-weight return vector every day. That is a **daily equal-weight rebalanced portfolio**, not literal buy-and-hold. Round 3 therefore reports both the legacy benchmark and a true initial-equal-dollar / zero-rebalance buy-and-hold benchmark.",
        "",
        "## 3. Cross-normalization audit",
        "",
        implementation.to_markdown(index=False),
        "",
        "A direction mismatch is a recorded trade whose weight change contradicts its V3.1 action label (for example BUY with a negative delta, or HOLD with a non-zero delta). These can be created by the old all-target normalization step rather than by a stock-level V3.1 signal.",
        "",
        "## 4. All diagnostic variants",
        "",
        summary[show_cols].to_markdown(index=False),
        "",
        "## 5. Approximate return-drag attribution using the corrected execution engine",
        "",
        attribution.to_markdown(index=False),
        "",
        "`sell_drag_cagr_pp = no-sell CAGR - corrected-baseline CAGR`. `entry_underexposure_gap_cagr_pp = true-buyhold CAGR - no-sell CAGR`. The latter remains an approximate path-dependent diagnostic.",
        "",
        "## 6. What happened after genuine corrected-engine SELL / BUY events",
        "",
        signal.to_markdown(index=False),
        "",
        "Incomplete 12/24-month forward windows are excluded from corresponding forward statistics.",
        "",
        "## 7. PE vs PB disagreement",
        "",
        disagreement.to_markdown(index=False),
        "",
        "A 2x divergence means the PE-relative and PB-relative components differ by a factor of two at the same month-end. Large disagreement warns that the geometric mean is combining economically inconsistent signals.",
        "",
        "## 8. Proxy specification sensitivity",
        "",
        sensitivity.to_markdown(index=False),
        "",
        "The CAGR range spans pre-declared PE-only, PB-only and 504/756/1260-day geometric-mean variants. A wide range is evidence of fragility, not a reason to select the best row.",
        "",
        "## Mechanical diagnostic labels",
        "",
        *verdicts,
        "",
        "## Limits",
        "",
        "- This is still an execution-layer test conditional on a fixed research universe; it is not a full PIT reconstruction of qualitative V3.1 hard gates.",
        "- The current neutral-value proxy is historical relative PE/PB, not normalized-earnings DCF/NAV.",
        "- No production BUY/SELL threshold is changed by this diagnosis.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
