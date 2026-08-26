from __future__ import annotations

"""Deterministic post-run diagnostics for the frozen Round-6 OOS artifact.

This script reads only committed Round-6 CSV/JSON files. It does not fetch data,
change the valuation model, or rerun the backtest.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd


BASE = Path("backtests/v31_pit_oos_round6_expectation_gap")
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}
HORIZON_MONTHS = (6, 12, 24)


def _json_value(value):
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value):
        return None
    return value


def write_headline_json(
    base: Path,
    headline: pd.DataFrame,
    *,
    round_number: int = 6,
    status: str = "economically_falsified_research_only",
) -> None:
    by_variant = headline.set_index("variant")
    strategy = by_variant.loc["expectation_gap_10y"]
    comparisons = {}
    for variant in ("round5_5y_15x", "universal_geomean", "true_buyhold"):
        comparator = by_variant.loc[variant]
        comparisons[variant] = {
            field: strategy.get(field, np.nan) - comparator.get(field, np.nan)
            for field in (
                "final_capital_rmb",
                "total_return",
                "cagr",
                "max_drawdown",
                "sharpe",
                "avg_cash_weight",
            )
        }

    payload = {
        "round": round_number,
        "status": status,
        "source": "headline.csv",
        "rows": headline.to_dict(orient="records"),
        "expectation_gap_10y_minus_comparator": comparisons,
        "buyhold_cost_accounting_note": (
            "The saved true-buy-and-hold metrics normalize by the first post-cost NAV, "
            "so the 0.10% initial transaction cost cancels from its reported return."
        ),
    }
    (base / "headline.json").write_text(
        json.dumps(_json_value(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def audit_inputs(base: Path, codes: list[str], group: str = "growth6") -> dict:
    companies = []
    for code in codes:
        financial = pd.read_csv(
            base / f"financial_{code}.csv",
            parse_dates=["report_date", "profit_notice_date", "cash_notice_date", "available_date"],
        )
        panel = pd.read_csv(
            base / f"panel_{code}.csv",
            parse_dates=["date", "fund_available_date"],
        )
        expected_available = financial[["profit_notice_date", "cash_notice_date"]].max(axis=1)
        companies.append(
            {
                "code": code,
                "financial_rows": len(financial),
                "availability_before_report_errors": int(
                    (financial["available_date"] < financial["report_date"]).sum()
                ),
                "available_date_not_max_notice_errors": int(
                    (financial["available_date"] != expected_available).fillna(False).sum()
                ),
                "daily_rows": len(panel),
                "future_financial_merge_errors": int(
                    (panel["fund_available_date"] > panel["date"]).sum()
                ),
                "duplicate_daily_dates": int(panel["date"].duplicated().sum()),
                "start": str(panel["date"].min().date()),
                "end": str(panel["date"].max().date()),
            }
        )

    trades = pd.read_csv(base / f"trades_expectation_{group}.csv")
    buy_mask = trades["action"].str.startswith("BUY_")
    sell_mask = trades["action"].isin(SELL_ACTIONS)
    required = {
        "REPORT.md",
        "summary.csv",
        "headline.csv",
        "assumptions.json",
        *{f"panel_{code}.csv" for code in codes},
        *{f"financial_{code}.csv" for code in codes},
    }
    missing = sorted(name for name in required if not (base / name).exists())
    payload = {
        "round": 6 if group == "growth6" else 7,
        "companies": companies,
        "buy_wrong_sign_errors": int((buy_mask & (trades["weight_change"] <= 0)).sum()),
        "sell_wrong_sign_errors": int((sell_mask & (trades["weight_change"] >= 0)).sum()),
        "missing_required_source_outputs": missing,
        "strict_pit_basic_audit_passed": not missing
        and all(
            row["availability_before_report_errors"] == 0
            and row["available_date_not_max_notice_errors"] == 0
            and row["future_financial_merge_errors"] == 0
            and row["duplicate_daily_dates"] == 0
            for row in companies
        ),
    }
    return payload


def growth_diagnostics(base: Path, names: dict[str, str]) -> pd.DataFrame:
    rows = []
    for code, name in names.items():
        panel = pd.read_csv(base / f"panel_{code}.csv")
        realistic = pd.to_numeric(panel["realistic_growth_round6"], errors="coerce")
        eps_growth = pd.to_numeric(panel["eps_growth_3y_round6"], errors="coerce")
        revenue_growth = pd.to_numeric(panel["revenue_growth_3y_round6"], errors="coerce")
        rows.append(
            {
                "code": code,
                "name": name,
                "days": len(panel),
                "realistic_growth_ready_days": int(realistic.notna().sum()),
                "realistic_growth_zero_fraction": float((realistic == 0).mean()),
                "realistic_growth_cap_fraction": float((realistic == 0.30).mean()),
                "median_eps_growth_3y": float(eps_growth.median()),
                "median_revenue_growth_3y": float(revenue_growth.median()),
                "median_realistic_growth": float(realistic.median()),
                "solved_implied_days": int((panel["implied_growth_status"] == "SOLVED").sum()),
                "below_zero_growth_value_days": int(
                    (panel["implied_growth_status"] == "BELOW_ZERO_GROWTH_VALUE").sum()
                ),
                "above_search_range_days": int(
                    (panel["implied_growth_status"] == "IMPLIED_ABOVE_SEARCH_RANGE").sum()
                ),
                "buy_staged_or_better_days": int((panel["ratio_expectation"] <= 0.85).sum()),
            }
        )
    return pd.DataFrame(rows)


def include_first_calendar_year(base: Path, summary: pd.DataFrame) -> pd.DataFrame:
    """Correct the legacy metric that drops the first calendar-year return."""
    corrected = summary.copy()
    for idx, row in corrected.iterrows():
        group = str(row["group"])
        variant = row["variant"]
        if variant == "csi300":
            path, value_col = base / "csi300.csv", None
        elif variant == "expectation_gap_10y":
            path, value_col = base / f"equity_expectation_{group}.csv", "nav"
        elif variant == "round5_5y_15x":
            path, value_col = base / f"equity_round5_{group}.csv", "nav"
        elif variant == "universal_geomean":
            path, value_col = base / f"equity_universal_{group}.csv", "nav"
        elif variant == "true_buyhold":
            path, value_col = base / f"true_buyhold_{group}.csv", None
        else:
            continue

        data = pd.read_csv(path)
        dates = pd.to_datetime(data.iloc[:, 0], errors="coerce")
        values = pd.to_numeric(data[value_col] if value_col else data.iloc[:, 1], errors="coerce")
        nav = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
        if nav.index[0] > pd.Timestamp("2018-01-01"):
            nav = pd.concat([pd.Series([1.0], index=[pd.Timestamp("2018-01-01")]), nav])
        annual_nav = nav.resample("YE").last()
        annual_returns = annual_nav.pct_change()
        annual_returns.iloc[0] = annual_nav.iloc[0] / nav.iloc[0] - 1.0
        corrected.loc[idx, "worst_calendar_year"] = annual_returns.min()
        corrected.loc[idx, "best_calendar_year"] = annual_returns.max()
    return corrected


def _forward_observation(
    price: pd.DataFrame,
    sale_date: pd.Timestamp,
    sale_price: float,
    months: int,
) -> dict:
    target = sale_date + pd.DateOffset(months=months)
    endpoint = price[price["date"] >= target]
    complete = not endpoint.empty
    if not complete:
        return {
            f"complete_{months}m": False,
            f"observation_date_{months}m": None,
            f"return_{months}m": np.nan,
            f"max_upside_{months}m": np.nan,
        }
    observed = endpoint.iloc[0]
    window = price[(price["date"] > sale_date) & (price["date"] <= observed["date"])]
    return {
        f"complete_{months}m": True,
        f"observation_date_{months}m": observed["date"],
        f"return_{months}m": float(observed["close"] / sale_price - 1.0),
        f"max_upside_{months}m": float(window["close"].max() / sale_price - 1.0),
    }


def sell_forward_outcomes(base: Path, group: str = "growth6") -> pd.DataFrame:
    trades = pd.read_csv(
        base / f"trades_expectation_{group}.csv",
        dtype={"code": str},
        parse_dates=["date"],
    ).sort_values(["code", "date"])
    trades["is_valuation_sell"] = (
        trades["action"].isin(SELL_ACTIONS) & (trades["weight_change"] < 0)
    )

    regime_entries: set[int] = set()
    for _, group in trades.groupby("code", sort=False):
        state = "START"
        for idx, row in group.iterrows():
            if row["is_valuation_sell"]:
                if state != "SELL":
                    regime_entries.add(idx)
                state = "SELL"
            elif row["weight_change"] > 0 and str(row["action"]).startswith("BUY_"):
                state = "BUY"

    rows = []
    for idx, sale in trades[trades["is_valuation_sell"]].iterrows():
        price = pd.read_csv(
            base / f"panel_{sale['code']}.csv",
            usecols=["date", "close"],
            parse_dates=["date"],
        ).dropna().sort_values("date")
        row = {
            "date": sale["date"],
            "code": sale["code"],
            "name": sale["name"],
            "action": sale["action"],
            "sale_price": float(sale["close_qfq"]),
            "price_to_neutral": float(sale["price_to_neutral"]),
            "weight_change": float(sale["weight_change"]),
            "sell_regime_entry": idx in regime_entries,
        }
        for months in HORIZON_MONTHS:
            row.update(_forward_observation(price, sale["date"], row["sale_price"], months))
        rows.append(row)
    if not rows:
        columns = [
            "date",
            "code",
            "name",
            "action",
            "sale_price",
            "price_to_neutral",
            "weight_change",
            "sell_regime_entry",
        ]
        for months in HORIZON_MONTHS:
            columns.extend(
                [
                    f"complete_{months}m",
                    f"observation_date_{months}m",
                    f"return_{months}m",
                    f"max_upside_{months}m",
                ]
            )
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values(["date", "code"]).reset_index(drop=True)


def summarize_sells(outcomes: pd.DataFrame) -> pd.DataFrame:
    populations = [("all_sell_events", outcomes)]
    populations.append(("sell_regime_entries", outcomes[outcomes["sell_regime_entry"]]))
    populations.extend(
        (f"code_{code}", group) for code, group in outcomes.groupby("code", sort=True)
    )
    rows = []
    for population, group in populations:
        for months in HORIZON_MONTHS:
            complete = group[group[f"complete_{months}m"]].copy()
            returns = complete[f"return_{months}m"]
            upside = complete[f"max_upside_{months}m"]
            rows.append(
                {
                    "population": population,
                    "horizon_months": months,
                    "sell_events_total": len(group),
                    "complete_observations": len(complete),
                    "mean_forward_return": returns.mean(),
                    "median_forward_return": returns.median(),
                    "positive_forward_return_fraction": (returns > 0).mean(),
                    "mean_max_upside": upside.mean(),
                    "median_max_upside": upside.median(),
                    "maximum_max_upside": upside.max(),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    assumptions = json.loads((BASE / "assumptions.json").read_text(encoding="utf-8"))
    names = {str(code): name for code, name in assumptions["universe"].items()}
    summary = include_first_calendar_year(BASE, pd.read_csv(BASE / "summary.csv"))
    summary.to_csv(BASE / "summary.csv", index=False)
    headline = summary[summary["group"] == "growth6"].copy()
    headline.to_csv(BASE / "headline.csv", index=False)
    write_headline_json(BASE, headline)

    audit = audit_inputs(BASE, list(names), "growth6")
    (BASE / "diagnostic_audit.json").write_text(
        json.dumps(_json_value(audit), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    growth = growth_diagnostics(BASE, names)
    growth.to_csv(BASE / "growth_diagnostics.csv", index=False)

    outcomes = sell_forward_outcomes(BASE, "growth6")
    outcomes.to_csv(BASE / "sell_forward_outcomes.csv", index=False)
    outcomes[outcomes["sell_regime_entry"]].to_csv(
        BASE / "sell_regime_entries.csv", index=False
    )
    summarize_sells(outcomes).to_csv(BASE / "sell_forward_summary.csv", index=False)

    print(f"PIT audit passed: {audit['strict_pit_basic_audit_passed']}")
    print(f"Valuation sell events: {len(outcomes)}")
    print(f"Sell-regime entries: {int(outcomes['sell_regime_entry'].sum())}")


if __name__ == "__main__":
    main()
