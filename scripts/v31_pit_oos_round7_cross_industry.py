from __future__ import annotations

"""Round-7 untouched OOS: cross-industry replication of Round-6.

Research-only. The unchanged economic model, execution contract and fresh
universe are frozen in docs/V31_EXPECTATION_GAP_ROUND7_CROSS_INDUSTRY_DRAFT.md.
"""

from pathlib import Path
import json

import pandas as pd

import v31_pit_oos_round6_expectation_gap as r6
import v31_pit_oos_round6_diagnose as diagnose
import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport


OUT = Path("artifacts/v31_pit_oos_round7_cross_industry")

NAMES = {
    "601100": "恒立液压",
    "002747": "埃斯顿",
    "002050": "三花智控",
    "600845": "宝信软件",
    "002027": "分众传媒",
    "600489": "中金黄金",
    "600089": "特变电工",
    "600887": "伊利股份",
}
ALL_CODES = list(NAMES)
GROUP = "cross_industry8"
GROUPS = {GROUP: ALL_CODES, **{f"single_{code}": [code] for code in ALL_CODES}}


def metrics_with_explicit_initial(nav: pd.Series, label: str) -> dict:
    """Keep original capital visible so first-day friction cannot normalize away."""
    x = nav.copy().sort_index()
    if x.index[0] > core.START_TS:
        x = pd.concat([pd.Series([1.0], index=[core.START_TS]), x])
    return core.metrics(x, label)


def result_summary(result: core.Result, label: str) -> dict:
    summary = metrics_with_explicit_initial(result.equity["nav"], label)
    summary["trades"] = int(len(result.trades))
    summary["avg_cash_weight"] = float(result.equity["cash_weight"].mean())
    summary["total_turnover"] = float(result.equity["turnover"].sum())
    return summary


def true_buyhold_with_explicit_initial(
    panels: dict[str, pd.DataFrame],
    codes: list[str],
    label: str,
) -> pd.Series:
    nav = r6.true_buyhold(panels, codes, label)
    if nav.index[0] > core.START_TS:
        nav = pd.concat([pd.Series([1.0], index=[core.START_TS], name=label), nav])
    return nav


def decorate(summary: dict, group: str, variant: str) -> dict:
    return {**summary, "group": group, "variant": variant}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # Reuse the frozen Round-6 engine while providing the pre-declared fresh
    # display-name map used by its panel and trade-output helpers.
    r6.NAMES = NAMES

    panels: dict[str, pd.DataFrame] = {}
    diagnostics = []
    for code, name in NAMES.items():
        print(f"FETCH ROUND7 {code} {name}", flush=True)
        panel, financial = r6.build_daily_panel(code)
        panels[code] = panel
        panel.to_csv(OUT / f"panel_{code}.csv", index=False)
        financial.to_csv(OUT / f"financial_{code}.csv", index=False)
        diagnostics.append(r6.expectation_diagnostics(panel, code))
        print(
            f"  daily={len(panel)} expectation_ready={panel['ratio_expectation'].notna().sum()} "
            f"round5_ready={panel['ratio_round5'].notna().sum()} "
            f"universal_ready={panel['ratio_universal'].notna().sum()}",
            flush=True,
        )

    diagnostic_frame = pd.DataFrame(diagnostics)
    diagnostic_frame.to_csv(OUT / "expectation_diagnostics.csv", index=False)

    summaries = []
    for group, codes in GROUPS.items():
        expectation_label = f"EXPECTATION_GAP_10Y_{group}"
        round5_label = f"ROUND5_5Y_15X_{group}"
        universal_label = f"UNIVERSAL_GEOMEAN_{group}"
        buyhold_label = f"TRUE_BUYHOLD_{group}"

        expectation = r6.run_cash_constrained(
            panels, codes, expectation_label, "ratio_expectation", "neutral_value_round6"
        )
        round5 = r6.run_cash_constrained(
            panels, codes, round5_label, "ratio_round5", "neutral_value_round5"
        )
        universal = r6.run_cash_constrained(
            panels, codes, universal_label, "ratio_universal", "neutral_universal"
        )
        buyhold = true_buyhold_with_explicit_initial(panels, codes, buyhold_label)

        expectation.equity.to_csv(OUT / f"equity_expectation_{group}.csv")
        expectation.trades.to_csv(OUT / f"trades_expectation_{group}.csv", index=False)
        round5.equity.to_csv(OUT / f"equity_round5_{group}.csv")
        round5.trades.to_csv(OUT / f"trades_round5_{group}.csv", index=False)
        universal.equity.to_csv(OUT / f"equity_universal_{group}.csv")
        universal.trades.to_csv(OUT / f"trades_universal_{group}.csv", index=False)
        buyhold.to_csv(OUT / f"true_buyhold_{group}.csv")

        summaries.extend(
            [
                decorate(result_summary(expectation, expectation_label), group, "expectation_gap_10y"),
                decorate(result_summary(round5, round5_label), group, "round5_5y_15x"),
                decorate(result_summary(universal, universal_label), group, "universal_geomean"),
                decorate(metrics_with_explicit_initial(buyhold, buyhold_label), group, "true_buyhold"),
            ]
        )

    csi = transport.resilient_fetch_csi300()
    csi.to_csv(OUT / "csi300.csv")
    summaries.append(
        decorate(metrics_with_explicit_initial(csi, "CSI300"), "benchmark", "csi300")
    )

    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(OUT / "summary.csv", index=False)
    headline = summary_frame[summary_frame["group"] == GROUP].copy()
    headline.to_csv(OUT / "headline.csv", index=False)

    assumptions = {
        "status": "research only; production V3.1 unchanged",
        "round7_purpose": "cross-industry replication of the unchanged Round-6 economic model",
        "universe": NAMES,
        "period": [str(core.START_TS.date()), str(core.END_TS.date())],
        "strict_pit": (
            "financial metrics become usable from the later profit/cash-flow NOTICE_DATE; "
            "UPDATE_DATE ignored"
        ),
        "round6_normalization_unchanged": (
            "median latest 4 positive (TTM basic EPS * clipped deduct-profit quality), min 2; "
            "TTM cash conversion diagnostic only"
        ),
        "realistic_growth_unchanged": (
            "clip(min(~3y normalized-EPS CAGR, ~3y revenue CAGR + 5pp), 0, 30%)"
        ),
        "valuation_unchanged": {
            "horizon_years": r6.HORIZON_YEARS,
            "discount_rate": r6.DISCOUNT_RATE,
            "terminal_growth": r6.TERMINAL_GROWTH,
            "terminal_multiple_formula": "1/(r-g)",
            "implied_growth_search": [0.0, r6.IMPLIED_GROWTH_MAX],
        },
        "execution_thresholds": {"buy": [0.85, 0.75, 0.65], "sell": [1.20, 1.40, 1.70]},
        "one_way_cost": core.ONE_WAY_COST,
        "rebalance": "month-end",
        "buyhold_cost_accounting": "explicit original-capital observation retained before first-day purchase",
        "comparators": ["round5_5y_15x", "universal_geomean", "true_buyhold", "CSI300"],
        "scope_limit": (
            "fixed-universe valuation/execution OOS; not historical qualitative hard-gate reconstruction"
        ),
    }
    (OUT / "assumptions.json").write_text(
        json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = [
        "# V3.1 Round-7 untouched OOS - cross-industry replication",
        "",
        "> Research-only falsification. Production V3.1 remains unchanged.",
        "",
        "## Frozen contract",
        "",
        "- The Round-6 economic formula and V3.1 execution thresholds are unchanged.",
        "- The eight-stock cross-industry universe was frozen before this output.",
        "- Strict PIT availability uses NOTICE_DATE and ignores mutable UPDATE_DATE.",
        "- Buy-and-hold retains the original-capital observation so initial friction cannot cancel.",
        "",
        "## Fresh OOS universe",
        "",
        pd.DataFrame([{"code": code, "name": name} for code, name in NAMES.items()]).to_markdown(index=False),
        "",
        "## Headline result",
        "",
        headline[
            [
                "variant",
                "final_capital_rmb",
                "total_return",
                "cagr",
                "max_drawdown",
                "sharpe",
                "worst_calendar_year",
                "best_calendar_year",
                "trades",
                "total_turnover",
                "avg_cash_weight",
            ]
        ].to_markdown(index=False),
        "",
        "## Expectation diagnostics",
        "",
        diagnostic_frame.to_markdown(index=False),
        "",
        "## Anti-overfit contract",
        "",
        "- No Round-7 result was available when the formula, parameters and universe were committed.",
        "- No Round-1..6 valuation-OOS security appears in this universe.",
        "- No result-driven economic parameter tuning is performed in this run.",
        "- Any later formula change requires another untouched OOS universe.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")

    diagnose.write_headline_json(
        OUT,
        headline,
        round_number=7,
        status="research_only_pending_diagnosis",
    )
    audit = diagnose.audit_inputs(OUT, ALL_CODES, GROUP)
    (OUT / "diagnostic_audit.json").write_text(
        json.dumps(diagnose._json_value(audit), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    diagnose.growth_diagnostics(OUT, NAMES).to_csv(
        OUT / "growth_diagnostics.csv", index=False
    )
    sell_outcomes = diagnose.sell_forward_outcomes(OUT, GROUP)
    sell_outcomes.to_csv(OUT / "sell_forward_outcomes.csv", index=False)
    sell_outcomes[sell_outcomes["sell_regime_entry"]].to_csv(
        OUT / "sell_regime_entries.csv", index=False
    )
    diagnose.summarize_sells(sell_outcomes).to_csv(
        OUT / "sell_forward_summary.csv", index=False
    )

    print("\n" + "\n".join(report), flush=True)


if __name__ == "__main__":
    main()
