from __future__ import annotations

"""Frozen broad-sample stress audit for the V3.1 valuation/execution layer.

IMPORTANT: The universe and every V3.1 decision threshold are declared before
this script is executed. Do not change symbols or thresholds after observing
results. This audit broadens the original five-stock test; it does not claim a
point-in-time reconstruction of qualitative moat selection and therefore still
has survivorship/selection limitations explicitly reported below.
"""

from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

import v31_pit_sector_backtest as core
from v31_pit_sector_backtest_resilient import (
    resilient_fetch_csi300,
    resilient_fetch_price,
    resilient_fetch_valuation,
)

OUT = Path("artifacts/v31_pit_stress_48")
MIN_VALID_NAMES = 40

# Pre-declared before first execution. Shanghai/Shenzhen A shares only.
GROUPS: dict[str, list[str]] = {
    "bank": ["600036", "601166", "601398"],
    "insurance": ["601318", "601601", "601628"],
    "liquor": ["600519", "000858", "000568"],
    "appliance": ["000333", "000651", "600690"],
    "utility": ["600900", "600886", "601985"],
    "machinery": ["600031", "000425", "601100"],
    "chemicals": ["600309", "600426", "002648"],
    "metals_mining": ["601899", "603993", "600547"],
    "auto": ["600104", "000625", "601633"],
    "pharma": ["600276", "000538", "600436"],
    "semiconductor": ["002371", "600584", "603986"],
    "electronics_telecom": ["002475", "000725", "600050"],
    "property_construction": ["000002", "601668", "600048"],
    "traditional_energy": ["601857", "600028", "601088"],
    "rare_earth": ["600111", "000831", "600392"],
    "aerospace": ["600118", "600879", "600893"],
}

NAMES = {
    "600036": "招商银行", "601166": "兴业银行", "601398": "工商银行",
    "601318": "中国平安", "601601": "中国太保", "601628": "中国人寿",
    "600519": "贵州茅台", "000858": "五粮液", "000568": "泸州老窖",
    "000333": "美的集团", "000651": "格力电器", "600690": "海尔智家",
    "600900": "长江电力", "600886": "国投电力", "601985": "中国核电",
    "600031": "三一重工", "000425": "徐工机械", "601100": "恒立液压",
    "600309": "万华化学", "600426": "华鲁恒升", "002648": "卫星化学",
    "601899": "紫金矿业", "603993": "洛阳钼业", "600547": "山东黄金",
    "600104": "上汽集团", "000625": "长安汽车", "601633": "长城汽车",
    "600276": "恒瑞医药", "000538": "云南白药", "600436": "片仔癀",
    "002371": "北方华创", "600584": "长电科技", "603986": "兆易创新",
    "002475": "立讯精密", "000725": "京东方A", "600050": "中国联通",
    "000002": "万科A", "601668": "中国建筑", "600048": "保利发展",
    "601857": "中国石油", "600028": "中国石化", "601088": "中国神华",
    "600111": "北方稀土", "000831": "中国稀土", "600392": "盛和资源",
    "600118": "中国卫星", "600879": "航天电子", "600893": "航发动力",
}

REGIMES = {
    "2018_2020": ("2018-01-01", "2020-12-31"),
    "2021_2023": ("2021-01-01", "2023-12-31"),
    "2024_2026": ("2024-01-01", "2026-08-24"),
}


def universe_hash() -> str:
    raw = json.dumps(GROUPS, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def metric_delta(v31: dict, bh: dict) -> dict:
    return {
        "cagr_delta": v31.get("cagr", np.nan) - bh.get("cagr", np.nan),
        "drawdown_improvement": v31.get("max_drawdown", np.nan) - bh.get("max_drawdown", np.nan),
        "sharpe_delta": v31.get("sharpe", np.nan) - bh.get("sharpe", np.nan),
    }


def regime_rows(v31: pd.Series, bh: pd.Series, label: str) -> list[dict]:
    rows: list[dict] = []
    for regime, (start, end) in REGIMES.items():
        a = v31.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna()
        b = bh.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna()
        if len(a) < 20 or len(b) < 20:
            continue
        ma = core.metrics(a, f"V31_{label}_{regime}")
        mb = core.metrics(b, f"BUYHOLD_{label}_{regime}")
        rows.append({"group": label, "regime": regime, "side": "V31", **ma})
        rows.append({"group": label, "regime": regime, "side": "BUYHOLD", **mb})
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    core.fetch_price = resilient_fetch_price
    core.fetch_valuation = resilient_fetch_valuation
    core.fetch_csi300 = resilient_fetch_csi300
    core.NAMES.update(NAMES)

    declared_codes = [c for codes in GROUPS.values() for c in codes]
    assert len(declared_codes) == 48 and len(set(declared_codes)) == 48

    panels: dict[str, pd.DataFrame] = {}
    coverage_rows: list[dict] = []
    failures: list[dict] = []
    for code in declared_codes:
        print(f"FETCH {code} {NAMES[code]}", flush=True)
        try:
            p = core.build_panel(code)
            ready = int(p["price_to_neutral"].notna().sum())
            panels[code] = p
            p.to_csv(OUT / f"panel_{code}.csv", index=False)
            coverage_rows.append({"code": code, "name": NAMES[code], "rows": len(p), "valuation_ready": ready, "ok": True})
            print(f"  rows={len(p)} valuation_ready={ready}", flush=True)
        except Exception as exc:
            failures.append({"code": code, "name": NAMES[code], "error": f"{type(exc).__name__}: {exc}"})
            coverage_rows.append({"code": code, "name": NAMES[code], "rows": 0, "valuation_ready": 0, "ok": False})
            print(f"  FAILED {type(exc).__name__}: {exc}", flush=True)

    pd.DataFrame(coverage_rows).to_csv(OUT / "coverage.csv", index=False)
    pd.DataFrame(failures, columns=["code", "name", "error"]).to_csv(OUT / "failures.csv", index=False)

    valid_codes = [c for c in declared_codes if c in panels]
    sector_rows: list[dict] = []
    sector_pairs: list[dict] = []
    regime_all: list[dict] = []

    # Per-sector tests. Data failures are never performance-based removals.
    for group, declared in GROUPS.items():
        codes = [c for c in declared if c in panels]
        if len(codes) < 2:
            sector_rows.append({"label": f"INVALID_{group}", "available_names": len(codes)})
            continue
        r = core.run_strategy(panels, codes, f"V31_{group}")
        bh = core.run_buy_hold(panels, codes, f"BUYHOLD_{group}")
        r.equity.to_csv(OUT / f"equity_{group}.csv")
        r.trades.to_csv(OUT / f"trades_{group}.csv", index=False)
        bh.to_csv(OUT / f"buyhold_{group}.csv")
        vm = r.summary
        bm = core.metrics(bh, f"BUYHOLD_{group}")
        sector_rows.extend([vm, bm])
        sector_pairs.append({"group": group, "names": len(codes), **metric_delta(vm, bm), "v31_cagr": vm["cagr"], "bh_cagr": bm["cagr"], "v31_mdd": vm["max_drawdown"], "bh_mdd": bm["max_drawdown"], "v31_sharpe": vm["sharpe"], "bh_sharpe": bm["sharpe"]})
        regime_all.extend(regime_rows(r.equity["nav"], bh, group))

    # Broad combined portfolio.
    combined = core.run_strategy(panels, valid_codes, "V31_stress48_combined")
    combined_bh = core.run_buy_hold(panels, valid_codes, "BUYHOLD_stress48_combined")
    combined.equity.to_csv(OUT / "equity_combined.csv")
    combined.trades.to_csv(OUT / "trades_combined.csv", index=False)
    combined_bh.to_csv(OUT / "buyhold_combined.csv")
    sector_rows.extend([combined.summary, core.metrics(combined_bh, "BUYHOLD_stress48_combined")])
    regime_all.extend(regime_rows(combined.equity["nav"], combined_bh, "stress48_combined"))

    # Single-name breadth: does the same frozen rule help across many independent names?
    single_rows: list[dict] = []
    for code in valid_codes:
        r = core.run_strategy(panels, [code], f"V31_single_{code}")
        bh = core.run_buy_hold(panels, [code], f"BUYHOLD_single_{code}")
        vm = r.summary
        bm = core.metrics(bh, f"BUYHOLD_single_{code}")
        single_rows.append({"code": code, "name": NAMES[code], **metric_delta(vm, bm), "v31_cagr": vm["cagr"], "bh_cagr": bm["cagr"], "v31_mdd": vm["max_drawdown"], "bh_mdd": bm["max_drawdown"], "v31_sharpe": vm["sharpe"], "bh_sharpe": bm["sharpe"], "trades": vm.get("trades"), "avg_cash_weight": vm.get("avg_cash_weight")})

    sector_df = pd.DataFrame(sector_rows)
    pairs_df = pd.DataFrame(sector_pairs)
    single_df = pd.DataFrame(single_rows)
    regime_df = pd.DataFrame(regime_all)
    sector_df.to_csv(OUT / "summary.csv", index=False)
    pairs_df.to_csv(OUT / "sector_comparison.csv", index=False)
    single_df.to_csv(OUT / "single_name_comparison.csv", index=False)
    regime_df.to_csv(OUT / "regime_comparison.csv", index=False)

    csi = resilient_fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    csi_metrics = core.metrics(csi, "CSI300")
    pd.DataFrame([csi_metrics]).to_csv(OUT / "benchmark_summary.csv", index=False)

    def share(series: pd.Series) -> float:
        return float(series.mean()) if len(series) else np.nan

    verdict = {
        "declared_names": 48,
        "valid_names": len(valid_codes),
        "coverage_ratio": len(valid_codes) / 48,
        "minimum_valid_required": MIN_VALID_NAMES,
        "universe_sha256": universe_hash(),
        "single_name_v31_beats_bh_cagr_share": share(single_df["cagr_delta"] > 0),
        "single_name_v31_improves_drawdown_share": share(single_df["drawdown_improvement"] > 0),
        "single_name_v31_improves_sharpe_share": share(single_df["sharpe_delta"] > 0),
        "sector_v31_beats_bh_cagr_share": share(pairs_df["cagr_delta"] > 0),
        "sector_v31_improves_drawdown_share": share(pairs_df["drawdown_improvement"] > 0),
        "sector_v31_improves_sharpe_share": share(pairs_df["sharpe_delta"] > 0),
        "selection_limit": "Fixed present-day broad sample; not historical-constituent PIT. Survivorship/selection bias remains. The audit is for execution-layer robustness, not proof of full stock-selection alpha.",
    }
    (OUT / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
    assumptions = {
        "window": [str(core.START_TS.date()), str(core.END_TS.date())],
        "groups": GROUPS,
        "names": NAMES,
        "universe_sha256": universe_hash(),
        "strategy_parameters_inherited_without_change_from": "v31_pit_sector_backtest.py",
        "one_way_cost": core.ONE_WAY_COST,
        "anchor_window": core.ANCHOR_WINDOW,
        "anchor_min": core.ANCHOR_MIN,
        "rebalance": "month-end",
        "anti_tuning_rule": "Do not alter universe, thresholds, anchors, cadence or cost after observing first run.",
    }
    (OUT / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")

    c_vm = combined.summary
    c_bm = core.metrics(combined_bh, "BUYHOLD_stress48_combined")
    md = [
        "# V3.1 PIT 48-stock stress audit — frozen rules",
        "",
        f"- Declared universe: 48 Shanghai/Shenzhen A shares, 16 sectors × 3 names",
        f"- Valid data: {len(valid_codes)}/48 ({len(valid_codes)/48:.1%})",
        f"- Universe SHA256: `{universe_hash()}`",
        f"- Period: {core.START_TS.date()} to {core.END_TS.date()}",
        f"- Frozen V3.1: anchor={core.ANCHOR_WINDOW}, min={core.ANCHOR_MIN}, cost={core.ONE_WAY_COST:.2%}, month-end rebalance",
        "- No parameter or symbol tuning is allowed after first observed result.",
        "",
        "## Broad combined portfolio",
        "",
        f"- V3.1 CAGR: {c_vm['cagr']:.2%}; Buy&Hold CAGR: {c_bm['cagr']:.2%}",
        f"- V3.1 max drawdown: {c_vm['max_drawdown']:.2%}; Buy&Hold max drawdown: {c_bm['max_drawdown']:.2%}",
        f"- V3.1 Sharpe: {c_vm['sharpe']:.3f}; Buy&Hold Sharpe: {c_bm['sharpe']:.3f}",
        f"- V3.1 average cash weight: {c_vm.get('avg_cash_weight', np.nan):.2%}; trades: {c_vm.get('trades', 0)}",
        "",
        "## Breadth checks",
        "",
        f"- Single names with higher CAGR than Buy&Hold: {verdict['single_name_v31_beats_bh_cagr_share']:.1%}",
        f"- Single names with smaller max drawdown: {verdict['single_name_v31_improves_drawdown_share']:.1%}",
        f"- Single names with higher Sharpe: {verdict['single_name_v31_improves_sharpe_share']:.1%}",
        f"- Sectors with higher CAGR: {verdict['sector_v31_beats_bh_cagr_share']:.1%}",
        f"- Sectors with smaller max drawdown: {verdict['sector_v31_improves_drawdown_share']:.1%}",
        f"- Sectors with higher Sharpe: {verdict['sector_v31_improves_sharpe_share']:.1%}",
        "",
        "## Important limitation",
        "",
        "> This is a frozen broad present-day sample and a PIT valuation/execution test. It is not a historical-constituent universe reconstruction, so survivorship/selection bias is not eliminated. Do not interpret it as proof that the qualitative stock-selection layer had the same historical alpha.",
        "",
        "See `sector_comparison.csv`, `single_name_comparison.csv`, `regime_comparison.csv`, `coverage.csv`, and raw panels/trades for audit details.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("\n" + "\n".join(md), flush=True)

    if len(valid_codes) < MIN_VALID_NAMES:
        raise RuntimeError(f"stress audit invalid: only {len(valid_codes)}/48 names have valid data; require >= {MIN_VALID_NAMES}")


if __name__ == "__main__":
    main()
