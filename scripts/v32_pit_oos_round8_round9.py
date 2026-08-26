from __future__ import annotations

"""Frozen Round-8/9 OOS runner for the GenGe V3.2 production decision."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import v31_pit_oos_round6_expectation_gap as r6
import v31_pit_oos_round6_diagnose as diagnose
import v31_pit_oos_round7_cross_industry as r7
import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport


UNIVERSES = {
    8: {
        "600031": "三一重工",
        "002008": "大族激光",
        "002920": "德赛西威",
        "600588": "用友网络",
        "600519": "贵州茅台",
        "601088": "中国神华",
        "601877": "正泰电器",
        "600276": "恒瑞医药",
    },
    9: {
        "601766": "中国中车",
        "002444": "巨星科技",
        "002415": "海康威视",
        "600536": "中国软件",
        "000895": "双汇发展",
        "600188": "兖矿能源",
        "600580": "卧龙电驱",
        "600809": "山西汾酒",
    },
}
ROUND_LABELS = {8: "discovery", 9: "untouched_confirmation"}
VARIANTS = (
    "current_v31_baseline",
    "v31_1_confidence_gate_only",
    "v32_candidate",
)
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}


def _json_value(value: Any) -> Any:
    return diagnose._json_value(value)


def add_confidence_inputs(panel: pd.DataFrame, financial: pd.DataFrame) -> pd.DataFrame:
    f = financial.copy().sort_values(["available_date", "report_date"])
    clean = pd.to_numeric(f["clean_eps_round6"], errors="coerce").where(lambda x: x > 0)
    f["normalized_earnings_observation_count"] = clean.notna().rolling(4, min_periods=1).sum()
    growth = pd.to_numeric(f["realistic_growth_round6"], errors="coerce")
    f["realistic_growth_four_report_range"] = (
        growth.rolling(4, min_periods=3).max() - growth.rolling(4, min_periods=3).min()
    )
    extra = f[
        [
            "available_date",
            "report_date",
            "normalized_earnings_observation_count",
            "realistic_growth_four_report_range",
        ]
    ].dropna(subset=["available_date"])
    extra = extra.drop_duplicates("available_date", keep="last").rename(
        columns={"available_date": "fund_available_date", "report_date": "confidence_report_date"}
    )
    result = panel.merge(extra, on="fund_available_date", how="left")
    result["valuation_confidence"] = result.apply(confidence_for_row, axis=1)
    return result


def confidence_for_row(row: pd.Series) -> str:
    required = (
        "close",
        "normalized_eps_round6",
        "realistic_growth_round6",
        "market_implied_growth_round6",
        "neutral_value_round6",
        "ratio_expectation",
    )
    if any(pd.isna(row.get(field)) or not np.isfinite(float(row.get(field))) for field in required):
        return "INVALID"
    if (
        float(row.get("close")) <= 0
        or float(row.get("normalized_eps_round6")) <= 0
        or float(row.get("neutral_value_round6")) <= 0
        or float(row.get("ratio_expectation")) <= 0
    ):
        return "INVALID"
    if pd.notna(row.get("fund_available_date")) and row.get("fund_available_date") > row.get("date"):
        return "INVALID"

    observations = float(row.get("normalized_earnings_observation_count") or 0.0)
    deduct = float(row.get("deduct_factor_round6")) if pd.notna(row.get("deduct_factor_round6")) else np.nan
    cash = float(row.get("cash_conversion")) if pd.notna(row.get("cash_conversion")) else np.nan
    growth_range = (
        float(row.get("realistic_growth_four_report_range"))
        if pd.notna(row.get("realistic_growth_four_report_range"))
        else 0.0
    )
    if (
        observations < 3
        or not np.isfinite(deduct)
        or deduct < 0.50
        or not np.isfinite(cash)
        or cash <= 0
        or growth_range > 0.15
        or str(row.get("implied_growth_status")) in {"INPUT_INCOMPLETE", "IMPLIED_ABOVE_SEARCH_RANGE"}
    ):
        return "LOW"
    realistic = float(row["realistic_growth_round6"])
    if observations < 4 or deduct < 0.80 or cash < 0.80 or growth_range > 0.10 or realistic <= 0 or realistic >= 0.30:
        return "MEDIUM"
    return "HIGH"


def _month_ends(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    values = pd.Series(index=index, data=index)
    return set(values.groupby(index.to_period("M")).max().tolist())


def run_variant(
    panels: dict[str, pd.DataFrame],
    names: dict[str, str],
    variant: str,
) -> core.Result:
    codes = list(names)
    frames = []
    fields = [
        "ret", "close", "ratio_expectation", "neutral_value_round6", "valuation_confidence",
        "normalized_eps_round6", "realistic_growth_round6", "market_implied_growth_round6",
        "expectation_gap_round6",
    ]
    for code in codes:
        x = panels[code].set_index("date")[fields].copy()
        x.columns = pd.MultiIndex.from_product([[code], fields])
        frames.append(x)
    panel = pd.concat(frames, axis=1).sort_index()
    panel = panel[(panel.index >= core.START_TS) & (panel.index <= core.END_TS)].ffill()
    rebalance_dates = _month_ends(panel.index)
    cap = 1.0 / len(codes)
    weights = {code: 0.0 for code in codes}
    confirmation = {code: 0 for code in codes}
    nav = 1.0
    records: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for i, dt in enumerate(panel.index):
        if i > 0:
            daily_return = sum(
                weights[code] * (float(panel.loc[dt, (code, "ret")]) if pd.notna(panel.loc[dt, (code, "ret")]) else 0.0)
                for code in codes
            )
            nav *= 1.0 + daily_return
            if 1.0 + daily_return != 0:
                for code in codes:
                    value = panel.loc[dt, (code, "ret")]
                    stock_return = float(value) if pd.notna(value) else 0.0
                    weights[code] = weights[code] * (1.0 + stock_return) / (1.0 + daily_return)

        turnover = 0.0
        if dt in rebalance_dates:
            raw_targets = dict(weights)
            actions: dict[str, str] = {}
            for code in codes:
                ratio = panel.loc[dt, (code, "ratio_expectation")]
                confidence = str(panel.loc[dt, (code, "valuation_confidence")])
                valid_ratio = pd.notna(ratio) and np.isfinite(ratio) and float(ratio) > 0
                desired, base_action = (
                    core.desired_weight(float(ratio), weights[code], cap)
                    if valid_ratio else (weights[code], "HOLD_REVIEW")
                )
                action = base_action
                if variant != "current_v31_baseline" and confidence in {"LOW", "INVALID"}:
                    desired, action, confirmation[code] = weights[code], "HOLD_REVIEW", 0
                elif variant == "v32_candidate" and base_action in SELL_ACTIONS:
                    if confirmation[code] < 1:
                        desired, action, confirmation[code] = weights[code], "HOLD_REVIEW", 1
                    else:
                        confirmation[code] = 2
                elif base_action not in SELL_ACTIONS:
                    confirmation[code] = 0
                raw_targets[code], actions[code] = desired, action
                decisions.append(
                    {
                        "variant": variant,
                        "date": dt,
                        "code": code,
                        "name": names[code],
                        "action": action,
                        "underlying_v31_action": base_action,
                        "valuation_confidence": confidence,
                        "sell_confirmation_count": confirmation[code],
                        "price_to_neutral": float(ratio) if valid_ratio else np.nan,
                        "neutral_value": panel.loc[dt, (code, "neutral_value_round6")],
                        "normalized_earnings": panel.loc[dt, (code, "normalized_eps_round6")],
                        "realistic_growth": panel.loc[dt, (code, "realistic_growth_round6")],
                        "market_implied_growth": panel.loc[dt, (code, "market_implied_growth_round6")],
                        "expectation_gap": panel.loc[dt, (code, "expectation_gap_round6")],
                    }
                )

            targets = dict(weights)
            for code in codes:
                if raw_targets[code] < weights[code]:
                    targets[code] = raw_targets[code]
            available_cash = max(0.0, 1.0 - sum(targets.values()))
            requests = {code: max(0.0, raw_targets[code] - targets[code]) for code in codes}
            total_requested = sum(requests.values())
            scale = min(1.0, available_cash / total_requested) if total_requested > 0 else 0.0
            for code in codes:
                targets[code] += requests[code] * scale

            turnover = sum(abs(targets[code] - weights[code]) for code in codes)
            nav *= 1.0 - turnover * core.ONE_WAY_COST
            for code in codes:
                delta = targets[code] - weights[code]
                if abs(delta) <= 1e-8:
                    continue
                ratio = panel.loc[dt, (code, "ratio_expectation")]
                trades.append(
                    {
                        "strategy": variant,
                        "date": dt,
                        "code": code,
                        "name": names[code],
                        "action": actions[code],
                        "valuation_confidence": panel.loc[dt, (code, "valuation_confidence")],
                        "sell_confirmation_count": confirmation[code],
                        "price_to_neutral": float(ratio) if pd.notna(ratio) else np.nan,
                        "neutral_value": panel.loc[dt, (code, "neutral_value_round6")],
                        "close_qfq": panel.loc[dt, (code, "close")],
                        "weight_before": weights[code],
                        "weight_after": targets[code],
                        "weight_change": delta,
                        "cost_fraction": abs(delta) * core.ONE_WAY_COST,
                    }
                )
            weights = targets

        records.append(
            {
                "date": dt,
                "nav": nav,
                "cash_weight": max(0.0, 1.0 - sum(weights.values())),
                "turnover": turnover,
                **{f"w_{code}": weights[code] for code in codes},
            }
        )

    equity = pd.DataFrame(records).set_index("date")
    trades_frame = pd.DataFrame(trades)
    decisions_frame = pd.DataFrame(decisions)
    summary = r7.metrics_with_explicit_initial(equity["nav"], variant)
    summary.update(
        {
            "trades": len(trades_frame),
            "avg_cash_weight": float(equity["cash_weight"].mean()),
            "total_turnover": float(equity["turnover"].sum()),
            "low_invalid_decisions": int(
                decisions_frame["valuation_confidence"].isin(["LOW", "INVALID"]).sum()
            ),
            "mechanical_low_invalid_actions": int(
                (
                    decisions_frame["valuation_confidence"].isin(["LOW", "INVALID"])
                    & (
                        decisions_frame["action"].str.startswith("BUY")
                        | decisions_frame["action"].isin(SELL_ACTIONS)
                    )
                ).sum()
            ),
        }
    )
    result = core.Result(equity, trades_frame, summary)
    result.decisions = decisions_frame  # type: ignore[attr-defined]
    return result


def sell_forward_outcomes(
    trades: pd.DataFrame, panels: dict[str, pd.DataFrame], variant: str
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    ordered = trades.sort_values(["code", "date"]).copy()
    sales = ordered[ordered["action"].isin(SELL_ACTIONS) & (ordered["weight_change"] < 0)].copy()
    if sales.empty:
        return pd.DataFrame()
    sales = sales.sort_values(["code", "date"])
    rows: list[dict[str, Any]] = []
    regime_entries: set[int] = set()
    for code, group in ordered.groupby("code", sort=False):
        in_sell_regime = False
        for index, trade in group.iterrows():
            is_sell = trade["action"] in SELL_ACTIONS and trade["weight_change"] < 0
            is_buy = str(trade["action"]).startswith("BUY") and trade["weight_change"] > 0
            if is_sell and not in_sell_regime:
                regime_entries.add(index)
            if is_sell:
                in_sell_regime = True
            elif is_buy:
                in_sell_regime = False
    for _, sale in sales.iterrows():
        code = str(sale["code"])
        date = pd.Timestamp(sale["date"])
        price = float(sale["close_qfq"])
        row = {
            "variant": variant,
            "date": date,
            "code": code,
            "name": sale["name"],
            "action": sale["action"],
            "sell_regime_entry": sale.name in regime_entries,
        }
        prices = panels[code][["date", "close"]].dropna().sort_values("date")
        for months in (12, 24):
            row.update(diagnose._forward_observation(prices, date, price, months))
        rows.append(row)
    return pd.DataFrame(rows)


def opportunity_cost_summary(outcomes: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "variant", "months", "completed_sell_events", "completed_regime_entries",
        "comparison_sample", "comparison_count", "median_forward_return", "median_max_upside",
    ]
    rows = []
    if outcomes.empty:
        return pd.DataFrame(rows, columns=columns)
    for variant, group in outcomes.groupby("variant"):
        for months in (12, 24):
            completed = group[group[f"complete_{months}m"]].copy()
            entries = completed[completed["sell_regime_entry"]]
            sample = entries if len(entries) >= 5 else completed
            rows.append(
                {
                    "variant": variant,
                    "months": months,
                    "completed_sell_events": len(completed),
                    "completed_regime_entries": len(entries),
                    "comparison_sample": "regime_entries" if len(entries) >= 5 else "all_sell_events",
                    "comparison_count": len(sample),
                    "median_forward_return": float(sample[f"return_{months}m"].median()) if len(sample) else np.nan,
                    "median_max_upside": float(sample[f"max_upside_{months}m"].median()) if len(sample) else np.nan,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def audit(out: Path, names: dict[str, str], results: dict[str, core.Result], round_number: int) -> dict:
    companies = []
    for code in names:
        financial = pd.read_csv(
            out / f"financial_{code}.csv",
            parse_dates=["report_date", "profit_notice_date", "cash_notice_date", "available_date"],
        )
        panel = pd.read_csv(out / f"panel_{code}.csv", parse_dates=["date", "fund_available_date"])
        expected = financial[["profit_notice_date", "cash_notice_date"]].max(axis=1)
        companies.append(
            {
                "code": code,
                "availability_before_report_errors": int((financial["available_date"] < financial["report_date"]).sum()),
                "available_date_not_max_notice_errors": int((financial["available_date"] != expected).fillna(False).sum()),
                "future_financial_merge_errors": int((panel["fund_available_date"] > panel["date"]).sum()),
                "duplicate_daily_dates": int(panel["date"].duplicated().sum()),
            }
        )
    signs = {}
    for variant, result in results.items():
        trades = result.trades
        if trades.empty:
            signs[variant] = {"buy_wrong_sign_errors": 0, "sell_wrong_sign_errors": 0}
            continue
        buy = trades["action"].str.startswith("BUY")
        sell = trades["action"].isin(SELL_ACTIONS)
        signs[variant] = {
            "buy_wrong_sign_errors": int((buy & (trades["weight_change"] <= 0)).sum()),
            "sell_wrong_sign_errors": int((sell & (trades["weight_change"] >= 0)).sum()),
        }
    passed = all(all(value == 0 for key, value in row.items() if key.endswith("errors")) for row in companies)
    passed = passed and all(all(value == 0 for value in row.values()) for row in signs.values())
    return {
        "round": round_number,
        "strict_pit_passed": passed,
        "companies": companies,
        "execution_sign_audit": signs,
        "future_financial_merge_total": sum(row["future_financial_merge_errors"] for row in companies),
        "cost_basis_used_by_sell": False,
    }


def promotion_check(summary: pd.DataFrame, sell_summary: pd.DataFrame, audit_payload: dict) -> dict:
    indexed = summary.set_index("variant")
    baseline = indexed.loc["current_v31_baseline"]
    candidate = indexed.loc["v32_candidate"]
    checks = {
        "strict_pit": bool(audit_payload["strict_pit_passed"]),
        "confidence_gate": int(candidate["mechanical_low_invalid_actions"]) == 0,
        "sharpe": float(candidate["sharpe"]) >= float(baseline["sharpe"]),
        "max_drawdown": float(candidate["max_drawdown"]) >= float(baseline["max_drawdown"]) - 0.05,
        "cagr": float(candidate["cagr"]) >= float(baseline["cagr"]) - 0.015,
        "average_cash": float(candidate["avg_cash_weight"]) < 0.80,
    }
    sell_checks = []
    for months in (12, 24):
        base_rows = sell_summary[
            (sell_summary["variant"] == "current_v31_baseline") & (sell_summary["months"] == months)
        ]
        candidate_rows = sell_summary[
            (sell_summary["variant"] == "v32_candidate") & (sell_summary["months"] == months)
        ]
        if base_rows.empty or candidate_rows.empty or int(candidate_rows.iloc[0]["comparison_count"]) == 0:
            sell_checks.append(True)
        else:
            sell_checks.append(
                float(candidate_rows.iloc[0]["median_max_upside"])
                <= float(base_rows.iloc[0]["median_max_upside"]) + 0.05
            )
    checks["sell_opportunity_cost"] = all(sell_checks)
    return {"checks": checks, "full_v32_thresholds_passed": all(checks.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, choices=(8, 9), required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    round_number = args.round
    names = UNIVERSES[round_number]
    label = ROUND_LABELS[round_number]
    out = args.output_dir or Path(f"artifacts/v32_pit_oos_round{round_number}_{label}")
    out.mkdir(parents=True, exist_ok=True)
    r6.NAMES = names

    panels: dict[str, pd.DataFrame] = {}
    diagnostics = []
    for code, name in names.items():
        print(f"FETCH ROUND{round_number} {code} {name}", flush=True)
        panel, financial = r6.build_daily_panel(code)
        panel = add_confidence_inputs(panel, financial)
        panels[code] = panel
        panel.to_csv(out / f"panel_{code}.csv", index=False)
        financial.to_csv(out / f"financial_{code}.csv", index=False)
        diagnostics.append(r6.expectation_diagnostics(panel, code))

    pd.DataFrame(diagnostics).to_csv(out / "expectation_diagnostics.csv", index=False)
    results: dict[str, core.Result] = {}
    rows = []
    all_outcomes = []
    for variant in VARIANTS:
        result = run_variant(panels, names, variant)
        results[variant] = result
        result.equity.to_csv(out / f"equity_{variant}.csv")
        result.trades.to_csv(out / f"trades_{variant}.csv", index=False)
        result.decisions.to_csv(out / f"decisions_{variant}.csv", index=False)  # type: ignore[attr-defined]
        rows.append({**result.summary, "variant": variant})
        outcomes = sell_forward_outcomes(result.trades, panels, variant)
        if not outcomes.empty:
            all_outcomes.append(outcomes)

    universal = r6.run_cash_constrained(
        panels, list(names), "UNIVERSAL_GEOMEAN", "ratio_universal", "neutral_universal"
    )
    universal.equity.to_csv(out / "equity_universal_geomean.csv")
    universal.trades.to_csv(out / "trades_universal_geomean.csv", index=False)
    rows.append({**r7.result_summary(universal, "universal_geomean"), "variant": "universal_geomean"})
    buyhold = r7.true_buyhold_with_explicit_initial(panels, list(names), "true_buyhold")
    buyhold.to_csv(out / "true_buyhold.csv")
    rows.append({**r7.metrics_with_explicit_initial(buyhold, "true_buyhold"), "variant": "true_buyhold"})
    csi = transport.resilient_fetch_csi300()
    if csi.index[0] > core.START_TS:
        csi = pd.concat([pd.Series([1.0], index=[core.START_TS]), csi])
    csi.to_csv(out / "csi300.csv")
    rows.append({**r7.metrics_with_explicit_initial(csi, "csi300"), "variant": "csi300"})

    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    outcomes = pd.concat(all_outcomes, ignore_index=True) if all_outcomes else pd.DataFrame()
    outcomes.to_csv(out / "sell_forward_outcomes.csv", index=False)
    sell_summary = opportunity_cost_summary(outcomes)
    sell_summary.to_csv(out / "sell_opportunity_cost_summary.csv", index=False)
    audit_payload = audit(out, names, results, round_number)
    (out / "audit.json").write_text(json.dumps(_json_value(audit_payload), indent=2), encoding="utf-8")
    promotion = promotion_check(summary, sell_summary, audit_payload)
    (out / "promotion_check.json").write_text(json.dumps(_json_value(promotion), indent=2), encoding="utf-8")

    assumptions = {
        "round": round_number,
        "purpose": label,
        "universe": names,
        "frozen_contract": "docs/V32_ROUND8_ROUND9_FROZEN_CONTRACT.md",
        "period": [str(core.START_TS.date()), str(core.END_TS.date())],
        "valuation_parameters": {"horizon": 10, "discount_rate": 0.10, "terminal_growth": 0.03},
        "execution_thresholds": {"buy": [0.85, 0.75, 0.65], "sell": [1.20, 1.40, 1.70]},
        "sell_confirmation_months": 2,
        "one_way_cost": core.ONE_WAY_COST,
        "cost_basis_sell_input": False,
        "round9_frozen_before_round8": True,
    }
    (out / "assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        f"# GenGe V3.2 Round {round_number} {label.replace('_', ' ').title()}",
        "",
        "Frozen strict-PIT OOS production-candidate evaluation.",
        "",
        "## Results",
        "",
        summary.to_markdown(index=False),
        "",
        "## SELL opportunity cost",
        "",
        sell_summary.to_markdown(index=False) if not sell_summary.empty else "No completed valuation SELL observations.",
        "",
        "## Integrity",
        "",
        f"- strict PIT: {audit_payload['strict_pit_passed']}",
        f"- future financial merges: {audit_payload['future_financial_merge_total']}",
        f"- full V3.2 frozen thresholds: {promotion['full_v32_thresholds_passed']}",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
