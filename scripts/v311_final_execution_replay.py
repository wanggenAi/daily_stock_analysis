from __future__ import annotations

"""Final execution-semantics replay for frozen Round-8/9 PIT panels.

This is NOT a new model round and performs no parameter tuning.  It reuses the
already-persisted Round-8/9 panels and the exact frozen V3.1/V3.1.1/V3.2 signal
logic, changing only two simulator semantics:

1. sparse-symbol ``ret`` is never forward-filled;
2. a symbol cannot trade on a date without an observed valid close.

The old artifacts are retained untouched for auditability.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import v31_pit_oos_round7_cross_industry as r7
import v31_pit_sector_backtest as core
import v32_pit_oos_round8_round9 as frozen
from v31_pit_execution_utils import align_execution_panel, cash_constrained_targets


SOURCE_DIRS = {
    8: Path("backtests/v32_pit_oos_round8_discovery"),
    9: Path("backtests/v32_pit_oos_round9_untouched_confirmation"),
}
FIELDS = [
    "ret",
    "close",
    "ratio_expectation",
    "neutral_value_round6",
    "valuation_confidence",
    "normalized_eps_round6",
    "realistic_growth_round6",
    "market_implied_growth_round6",
    "expectation_gap_round6",
]


def load_frozen_panels(round_number: int) -> dict[str, pd.DataFrame]:
    source = SOURCE_DIRS[round_number]
    panels: dict[str, pd.DataFrame] = {}
    for code in frozen.UNIVERSES[round_number]:
        path = source / f"panel_{code}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Frozen PIT panel missing: {path}")
        panel = pd.read_csv(path)
        panel["date"] = pd.to_datetime(panel["date"])
        panels[code] = panel
    return panels


def _month_ends(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    values = pd.Series(index=index, data=index)
    return set(values.groupby(index.to_period("M")).max().tolist())


def run_variant_fixed(
    panels: dict[str, pd.DataFrame],
    names: dict[str, str],
    variant: str,
) -> core.Result:
    """Replay one frozen variant with corrected sparse-date execution only."""

    codes = list(names)
    panel = align_execution_panel(
        panels,
        codes,
        FIELDS,
        start=core.START_TS,
        end=core.END_TS,
    )
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
            stock_returns = {
                code: float(panel.loc[dt, (code, "ret")])
                if pd.notna(panel.loc[dt, (code, "ret")])
                else 0.0
                for code in codes
            }
            daily_return = sum(weights[code] * stock_returns[code] for code in codes)
            nav *= 1.0 + daily_return
            if 1.0 + daily_return != 0:
                for code in codes:
                    weights[code] = weights[code] * (1.0 + stock_returns[code]) / (1.0 + daily_return)

        turnover = 0.0
        if dt in rebalance_dates:
            raw_targets = dict(weights)
            actions: dict[str, str] = {}
            executable = {
                code: bool(panel.loc[dt, (code, "tradable_today")])
                for code in codes
            }

            for code in codes:
                ratio = panel.loc[dt, (code, "ratio_expectation")]
                confidence = str(panel.loc[dt, (code, "valuation_confidence")])
                valid_ratio = pd.notna(ratio) and np.isfinite(ratio) and float(ratio) > 0
                blocked = not executable[code]

                # A stale quote may remain visible for marking/research, but it
                # may not generate a signal transition or a synthetic trade.
                if blocked:
                    desired = weights[code]
                    base_action = "HOLD_REVIEW"
                    action = "HOLD_REVIEW"
                else:
                    desired, base_action = (
                        core.desired_weight(float(ratio), weights[code], cap)
                        if valid_ratio
                        else (weights[code], "HOLD_REVIEW")
                    )
                    action = base_action
                    if variant != "current_v31_baseline" and confidence in {"LOW", "INVALID"}:
                        desired, action, confirmation[code] = weights[code], "HOLD_REVIEW", 0
                    elif variant == "v32_candidate" and base_action in frozen.SELL_ACTIONS:
                        if confirmation[code] < 1:
                            desired, action, confirmation[code] = weights[code], "HOLD_REVIEW", 1
                        else:
                            confirmation[code] = 2
                    elif base_action not in frozen.SELL_ACTIONS:
                        confirmation[code] = 0

                raw_targets[code] = desired
                actions[code] = action
                decisions.append(
                    {
                        "variant": variant,
                        "date": dt,
                        "code": code,
                        "name": names[code],
                        "action": action,
                        "underlying_v31_action": base_action,
                        "valuation_confidence": confidence,
                        "tradable_today": executable[code],
                        "execution_blocked_not_tradable": blocked,
                        "sell_confirmation_count": confirmation[code],
                        "price_to_neutral": float(ratio) if valid_ratio else np.nan,
                        "neutral_value": panel.loc[dt, (code, "neutral_value_round6")],
                        "normalized_earnings": panel.loc[dt, (code, "normalized_eps_round6")],
                        "realistic_growth": panel.loc[dt, (code, "realistic_growth_round6")],
                        "market_implied_growth": panel.loc[dt, (code, "market_implied_growth_round6")],
                        "expectation_gap": panel.loc[dt, (code, "expectation_gap_round6")],
                    }
                )

            targets = cash_constrained_targets(weights, raw_targets, executable)
            turnover = sum(abs(targets[code] - weights[code]) for code in codes)
            nav *= 1.0 - turnover * core.ONE_WAY_COST

            for code in codes:
                delta = targets[code] - weights[code]
                if abs(delta) <= 1e-8:
                    continue
                if not executable[code]:
                    raise AssertionError(f"Synthetic stale-date trade escaped guard: {dt} {code}")
                ratio = panel.loc[dt, (code, "ratio_expectation")]
                trades.append(
                    {
                        "strategy": variant,
                        "date": dt,
                        "code": code,
                        "name": names[code],
                        "action": actions[code],
                        "valuation_confidence": panel.loc[dt, (code, "valuation_confidence")],
                        "tradable_today": True,
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
    low_invalid = decisions_frame["valuation_confidence"].isin(["LOW", "INVALID"])
    mechanical = (
        decisions_frame["action"].str.startswith("BUY")
        | decisions_frame["action"].isin(frozen.SELL_ACTIONS)
    )
    summary.update(
        {
            "trades": len(trades_frame),
            "avg_cash_weight": float(equity["cash_weight"].mean()),
            "total_turnover": float(equity["turnover"].sum()),
            "low_invalid_decisions": int(low_invalid.sum()),
            "mechanical_low_invalid_actions": int((low_invalid & mechanical).sum()),
            "blocked_nontradable_rebalance_decisions": int(
                decisions_frame["execution_blocked_not_tradable"].sum()
            ),
        }
    )
    result = core.Result(equity, trades_frame, summary)
    result.decisions = decisions_frame  # type: ignore[attr-defined]
    return result


def alignment_audit(panels: dict[str, pd.DataFrame], names: dict[str, str]) -> pd.DataFrame:
    codes = list(names)
    aligned = align_execution_panel(
        panels,
        codes,
        FIELDS,
        start=core.START_TS,
        end=core.END_TS,
    )
    month_ends = _month_ends(aligned.index)
    rows = []
    for code in codes:
        original = panels[code].copy()
        original["date"] = pd.to_datetime(original["date"])
        original = original.set_index("date").sort_index()
        original = original[(original.index >= core.START_TS) & (original.index <= core.END_TS)]
        old_ffilled_ret = original["ret"].reindex(aligned.index).ffill()
        missing_quote = ~aligned[(code, "tradable_today")].astype(bool)
        rows.append(
            {
                "code": code,
                "name": names[code],
                "union_calendar_days": len(aligned),
                "observed_quote_days": int((~missing_quote).sum()),
                "missing_quote_days": int(missing_quote.sum()),
                "phantom_nonzero_return_days_prevented": int(
                    (missing_quote & old_ffilled_ret.fillna(0.0).ne(0.0)).sum()
                ),
                "nontradable_union_month_ends": int(
                    sum(bool(missing_quote.loc[dt]) for dt in month_ends)
                ),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, choices=(8, 9), required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    round_number = args.round
    names = frozen.UNIVERSES[round_number]
    source = SOURCE_DIRS[round_number]
    out = args.output_dir or Path(f"artifacts/v311_final_execution_replay_round{round_number}")
    out.mkdir(parents=True, exist_ok=True)

    panels = load_frozen_panels(round_number)
    audit = alignment_audit(panels, names)
    audit.to_csv(out / "alignment_audit.csv", index=False)

    rows = []
    results: dict[str, core.Result] = {}
    for variant in frozen.VARIANTS:
        result = run_variant_fixed(panels, names, variant)
        results[variant] = result
        result.equity.to_csv(out / f"equity_{variant}.csv")
        result.trades.to_csv(out / f"trades_{variant}.csv", index=False)
        result.decisions.to_csv(out / f"decisions_{variant}.csv", index=False)  # type: ignore[attr-defined]
        rows.append({**result.summary, "variant": variant})

    true_buyhold = r7.true_buyhold_with_explicit_initial(panels, list(names), "true_buyhold")
    true_buyhold.to_csv(out / "true_buyhold.csv")
    rows.append({**r7.metrics_with_explicit_initial(true_buyhold, "true_buyhold"), "variant": "true_buyhold"})

    fixed_summary = pd.DataFrame(rows)
    fixed_summary.to_csv(out / "summary.csv", index=False)

    old_summary = pd.read_csv(source / "summary.csv")
    compare_variants = set(frozen.VARIANTS) | {"true_buyhold"}
    old_small = old_summary[old_summary["variant"].isin(compare_variants)].copy()
    fixed_small = fixed_summary[fixed_summary["variant"].isin(compare_variants)].copy()
    compare = old_small.merge(fixed_small, on="variant", how="outer", suffixes=("_old", "_fixed"))
    for metric in ("final_nav", "cagr", "max_drawdown", "sharpe", "avg_cash_weight", "total_turnover"):
        old_col, fixed_col = f"{metric}_old", f"{metric}_fixed"
        if old_col in compare.columns and fixed_col in compare.columns:
            compare[f"{metric}_delta"] = compare[fixed_col] - compare[old_col]
    compare.to_csv(out / "old_vs_fixed.csv", index=False)

    integrity = {
        "round": round_number,
        "source_dir": str(source),
        "model_thresholds_changed": False,
        "universe_changed": False,
        "valuation_logic_changed": False,
        "confidence_gate_changed": False,
        "sell_confirmation_logic_changed": False,
        "cost_basis_used_by_sell": False,
        "execution_fixes": [
            "missing union-date return is zero; ret is never forward-filled",
            "month-end execution requires an observed valid close on that exact date",
            "non-tradable weights are preserved and excluded from buy cash scaling",
        ],
        "phantom_nonzero_return_days_prevented": int(
            audit["phantom_nonzero_return_days_prevented"].sum()
        ),
        "nontradable_union_month_ends": int(audit["nontradable_union_month_ends"].sum()),
        "synthetic_stale_trades_after_fix": 0,
    }
    (out / "integrity.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")

    report = [
        f"# V3.1.1 Final Execution Replay — Frozen Round {round_number}",
        "",
        "This is an execution-only replay of the already persisted PIT panels; no model parameters or universe members were changed.",
        "",
        "## Corrected results",
        "",
        fixed_summary.to_markdown(index=False),
        "",
        "## Old simulator vs corrected simulator",
        "",
        compare.to_markdown(index=False),
        "",
        "## Execution integrity",
        "",
        f"- Phantom non-zero return days prevented: {integrity['phantom_nonzero_return_days_prevented']}",
        f"- Non-tradable symbol/month-end observations: {integrity['nontradable_union_month_ends']}",
        "- Synthetic stale-date trades after fix: 0",
        "- Cost basis used by SELL: false",
        "- Qualitative hard-gate history reconstructed: false",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
