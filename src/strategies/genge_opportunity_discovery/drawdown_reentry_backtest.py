"""Signal-confirmed re-entry backtest for drawdown control.

Version 1 of the drawdown overlay deliberately froze the baseline entry set.
That is useful for causal exit-only auditing, but it imposes an unrealistic
permanent opportunity cost after a protective exit: a stock can become cheap
and pass the original point-in-time BUY rules again, yet the frozen-entry audit
must remain in cash.

This module tests a deployable *structure* without relaxing entry quality:

1. risk exits are learned from closes and execute next observed session open;
2. a risk exit starts a fixed cooldown;
3. after cooldown, re-entry is allowed only if the original point-in-time hard
   logic + reverse-valuation BUY rules independently fire again;
4. no automatic averaging down, no future data and no unconditional re-entry.

The famous-stock panel remains ex-post selected and therefore diagnostic only.
Production deployment still requires an unbiased point-in-time All-A portfolio
walk-forward test.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.drawdown_overlay_backtest import (
    equal_weight_portfolio,
    equity_curve_from_trades,
    risk_exit_reason,
)
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    StrategyMetrics,
    cagr_pct,
    evaluate_candidate,
    max_drawdown_pct,
    select_drawdown_optimized,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    BUY_DECISIONS,
    DEFAULT_STRIDE,
    MAX_ENTRY_PE_PERCENTILE,
    FamousCase,
    HistoricalCompanyData,
    _max_drawdown,
    _price_map,
    _price_percentile,
    _sell_reason,
    fetch_case_data,
    load_cases,
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
    point_in_time_valuation,
    simulate_company,
)

RULE_VERSION = "hard_logic_drawdown_reentry_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


@dataclass(frozen=True)
class ReentryRiskPolicy:
    name: str
    initial_stop_pct: float
    breakeven_activation_pct: float
    breakeven_floor_pct: float
    trailing_activation_pct: float
    trailing_drawdown_pct: float
    reentry_cooldown_sessions: int


POLICY_GRID: tuple[ReentryRiskPolicy, ...] = (
    ReentryRiskPolicy("reentry_balanced", 18.0, 50.0, 1.0, 80.0, 30.0, 10),
    ReentryRiskPolicy("reentry_growth", 22.0, 60.0, 1.0, 100.0, 35.0, 10),
    ReentryRiskPolicy("reentry_wide", 28.0, 80.0, 0.0, 120.0, 40.0, 15),
    ReentryRiskPolicy("tail_only", 35.0, 100.0, 0.0, 160.0, 45.0, 20),
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _signal(
    data: HistoricalCompanyData,
    *,
    day: date,
    action: str,
    reason: str,
    close: float,
    logic: Mapping[str, Any] | None = None,
    valuation: Mapping[str, Any] | None = None,
    pmap: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    logic = dict(logic or {})
    valuation = dict(valuation or {})
    pmap = dict(pmap or {})
    return {
        "code": data.code,
        "stock_name": data.stock_name,
        "signal_date": day,
        "signal_action": action,
        "reason": reason,
        "hard_logic_state": logic.get("state"),
        "hard_logic_score": logic.get("score"),
        "current_price": close,
        "current_pe": valuation.get("current_pe"),
        "historical_reference_pe": valuation.get("historical_reference_pe"),
        "historical_pe_percentile": valuation.get("historical_pe_percentile"),
        "required_profit_growth_pct": pmap.get("required_profit_growth_pct"),
        "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
        "expectation_headroom_pct": pmap.get("expectation_headroom_pct"),
        "buyable_price_ceiling": pmap.get("buyable_price_ceiling"),
        "deep_value_price_ceiling": pmap.get("deep_value_price_ceiling"),
    }


def _close_trade(
    *,
    data: HistoricalCompanyData,
    price: pd.DataFrame,
    position: Mapping[str, Any],
    pending: Mapping[str, Any],
    exit_index: int,
    exit_price: float,
) -> dict[str, Any]:
    window = price.iloc[int(position["entry_index"]): exit_index + 1]
    gross = (exit_price / float(position["entry_price"]) - 1.0) * 100.0
    highs = pd.to_numeric(window["high"], errors="coerce").dropna().tolist()
    max_runup = ((max(highs) / float(position["entry_price"]) - 1.0) * 100.0) if highs else gross
    exit_pct = _price_percentile(price.iloc[: exit_index + 1], exit_price)
    return {
        "code": data.code,
        "stock_name": data.stock_name,
        "entry_signal_date": position.get("signal_date"),
        "entry_date": position.get("entry_date"),
        "entry_price": round(float(position["entry_price"]), 4),
        "entry_decision": position.get("entry_decision"),
        "entry_required_profit_growth_pct": position.get("required_profit_growth_pct"),
        "entry_supported_growth_base_pct": position.get("supported_growth_base_pct"),
        "entry_expectation_headroom_pct": position.get("expectation_headroom_pct"),
        "entry_buyable_price_ceiling": position.get("buyable_price_ceiling"),
        "entry_deep_value_price_ceiling": position.get("deep_value_price_ceiling"),
        "entry_pe": position.get("current_pe"),
        "entry_reference_pe": position.get("historical_reference_pe"),
        "entry_pe_percentile": position.get("historical_pe_percentile"),
        "entry_price_percentile_2y": position.get("entry_price_percentile_2y"),
        "exit_signal_date": pending.get("signal_date"),
        "exit_date": price.iloc[exit_index]["date"],
        "exit_price": round(exit_price, 4),
        "exit_reason": pending.get("reason"),
        "exit_required_profit_growth_pct": pending.get("required_profit_growth_pct"),
        "exit_supported_growth_base_pct": pending.get("supported_growth_base_pct"),
        "exit_pe_percentile": pending.get("historical_pe_percentile"),
        "exit_price_percentile_2y": exit_pct,
        "gross_return_pct": round(gross, 4),
        "net_return_pct": round(gross, 4),
        "max_runup_pct": round(max_runup, 4),
        "max_drawdown_pct": _max_drawdown(
            [
                float(position["entry_price"]),
                *pd.to_numeric(window["close"], errors="coerce").dropna().tolist(),
            ]
        ),
        "capture_ratio_pct": round(gross / max_runup * 100.0, 4) if max_runup > 0 else None,
        "holding_sessions": len(window),
        "low_buy_high_sell": bool(
            (_finite(position.get("entry_price_percentile_2y")) or 101) <= 40
            and (_finite(exit_pct) or -1) >= 60
            and gross > 0
        ),
        "risk_reentry_policy": pending.get("risk_reentry_policy") or position.get("risk_reentry_policy"),
    }


def simulate_company_with_reentry(
    data: HistoricalCompanyData,
    *,
    start_date: date,
    end_date: date,
    policy: ReentryRiskPolicy,
    evaluation_stride: int = DEFAULT_STRIDE,
    cost_bps_per_side: float = 15.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], pd.Series, dict[str, Any]]:
    price = prepare_price_frame(data.price_df)
    price = price[(price["date"] >= start_date) & (price["date"] <= end_date)].reset_index(drop=True)
    financial = normalize_financial_point_in_time(data.financial_df)
    if len(price) < 122:
        return [], [], pd.Series(dtype=float), {
            "code": data.code,
            "stock_name": data.stock_name,
            "status": "INSUFFICIENT_PRICE_HISTORY",
            "trade_count": 0,
        }

    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    equity_values: list[float] = []
    equity_dates: list[date] = []
    cash = 1.0
    shares = 0.0
    position: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
    last_risk_exit_index: int | None = None
    risk_exit_count = 0
    reentry_count = 0
    entry_count = 0
    first_close = _finite(price.iloc[0].get("close"))
    last_close = _finite(price.iloc[-1].get("close"))

    for i, bar in price.iterrows():
        day = bar["date"]
        open_price = _finite(bar.get("open"))
        close = _finite(bar.get("close"))

        if pending and pending["execute_index"] == i and open_price and open_price > 0:
            if pending["action"] == "BUY" and position is None:
                ceiling = _finite(pending.get("buyable_price_ceiling"))
                if ceiling is None or open_price <= ceiling:
                    entry = open_price * (1.0 + cost_bps_per_side / 10000.0)
                    shares = cash / entry
                    cash = 0.0
                    entry_count += 1
                    if last_risk_exit_index is not None:
                        reentry_count += 1
                    position = {
                        **pending,
                        "entry_date": day,
                        "entry_price": entry,
                        "entry_index": i,
                        "highest_close_since_entry": entry,
                        "risk_reentry_policy": policy.name,
                    }
            elif pending["action"] == "SELL" and position is not None:
                exit_price = open_price * (1.0 - cost_bps_per_side / 10000.0)
                cash = shares * exit_price
                shares = 0.0
                trades.append(
                    _close_trade(
                        data=data,
                        price=price,
                        position=position,
                        pending=pending,
                        exit_index=i,
                        exit_price=exit_price,
                    )
                )
                if str(pending.get("reason") or "").startswith("SELL_RISK_"):
                    last_risk_exit_index = i
                    risk_exit_count += 1
                position = None
            pending = None

        if position is not None and close is not None and close > 0:
            position["highest_close_since_entry"] = max(
                float(position.get("highest_close_since_entry") or position["entry_price"]),
                close,
            )

        if close is not None and close > 0:
            equity_dates.append(day)
            equity_values.append(cash if position is None else shares * close)

        if i >= len(price) - 1 or pending is not None or close is None or close <= 0:
            continue

        # Risk controls are checked every completed session, independent of the
        # slower valuation/fundamental evaluation stride.  A trigger still
        # executes at the next observed open.
        if position is not None:
            reason = risk_exit_reason(
                entry_price=float(position["entry_price"]),
                peak_close=float(position.get("highest_close_since_entry") or position["entry_price"]),
                close=close,
                policy=policy,
            )
            if reason:
                pending = {
                    "action": "SELL",
                    "execute_index": i + 1,
                    "signal_date": day,
                    "reason": reason,
                    "risk_reentry_policy": policy.name,
                }
                signals.append(
                    _signal(data, day=day, action="SELL", reason=reason, close=close)
                )
                continue

        if i % max(1, evaluation_stride) != 0:
            continue

        valuation = point_in_time_valuation(data.valuation_df, day)
        logic = point_in_time_hard_logic(financial, day)
        if valuation is None:
            continue
        pmap = _price_map(data, day, close, valuation, logic)
        decision = str(pmap.get("price_decision") or "")
        pe_percentile = _finite(valuation.get("historical_pe_percentile"))
        low_zone_ok = bool(
            decision == "BUY_DEEP_VALUE"
            or (pe_percentile is not None and pe_percentile <= MAX_ENTRY_PE_PERCENTILE)
        )

        cooldown_clear = bool(
            last_risk_exit_index is None
            or i - last_risk_exit_index >= max(0, int(policy.reentry_cooldown_sessions))
        )
        if (
            position is None
            and cooldown_clear
            and logic["state"] == "PASS"
            and decision in BUY_DECISIONS
            and low_zone_ok
        ):
            ceiling = _finite(pmap.get("buyable_price_ceiling"))
            if ceiling is not None and close <= ceiling:
                pending = {
                    "action": "BUY",
                    "execute_index": i + 1,
                    "signal_date": day,
                    "entry_decision": pmap.get("price_decision"),
                    "required_profit_growth_pct": pmap.get("required_profit_growth_pct"),
                    "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
                    "expectation_headroom_pct": pmap.get("expectation_headroom_pct"),
                    "buyable_price_ceiling": ceiling,
                    "deep_value_price_ceiling": pmap.get("deep_value_price_ceiling"),
                    "current_pe": valuation.get("current_pe"),
                    "historical_reference_pe": valuation.get("historical_reference_pe"),
                    "historical_pe_percentile": valuation.get("historical_pe_percentile"),
                    "entry_price_percentile_2y": _price_percentile(price.iloc[: i + 1], close),
                    "risk_reentry_policy": policy.name,
                }
                signals.append(
                    _signal(
                        data,
                        day=day,
                        action="BUY",
                        reason=decision,
                        close=close,
                        logic=logic,
                        valuation=valuation,
                        pmap=pmap,
                    )
                )
        elif position is not None:
            reason = _sell_reason(pmap, logic)
            if reason:
                pending = {
                    "action": "SELL",
                    "execute_index": i + 1,
                    "signal_date": day,
                    "reason": reason,
                    "required_profit_growth_pct": pmap.get("required_profit_growth_pct"),
                    "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
                    "historical_pe_percentile": valuation.get("historical_pe_percentile"),
                    "risk_reentry_policy": policy.name,
                }
                signals.append(
                    _signal(
                        data,
                        day=day,
                        action="SELL",
                        reason=reason,
                        close=close,
                        logic=logic,
                        valuation=valuation,
                        pmap=pmap,
                    )
                )

    if position is not None and last_close and last_close > 0:
        exit_price = last_close * (1.0 - cost_bps_per_side / 10000.0)
        pending_end = {
            "signal_date": price.iloc[-1]["date"],
            "reason": "END_OF_TEST_MARK_TO_MARKET",
            "risk_reentry_policy": policy.name,
        }
        trades.append(
            _close_trade(
                data=data,
                price=price,
                position=position,
                pending=pending_end,
                exit_index=len(price) - 1,
                exit_price=exit_price,
            )
        )
        cash = shares * exit_price
        if equity_values:
            equity_values[-1] = cash

    curve = pd.Series(
        equity_values,
        index=pd.Index(equity_dates, name="date"),
        dtype=float,
    )
    strategy = (cash - 1.0) * 100.0
    buy_hold = (last_close / first_close - 1.0) * 100.0 if first_close and last_close else None
    case = {
        "code": data.code,
        "stock_name": data.stock_name,
        "policy": policy.name,
        "status": "OK" if trades else "NO_TRADE",
        "trade_count": len(trades),
        "entry_count": entry_count,
        "risk_exit_count": risk_exit_count,
        "signal_confirmed_reentry_count": reentry_count,
        "compounded_strategy_return_pct": round(strategy, 4),
        "buy_hold_return_pct": round(buy_hold, 4) if buy_hold is not None else None,
        "max_strategy_drawdown_pct": (
            -round(float(max_drawdown_pct(curve.tolist()) or 0.0), 4)
            if not curve.empty else None
        ),
    }
    return trades, signals, curve, case


def _metrics(name: str, curve: pd.Series) -> StrategyMetrics:
    if curve.empty:
        return StrategyMetrics(name=name, cagr_pct=0.0, max_drawdown_pct=100.0)
    years = max(1.0 / 365.25, (curve.index[-1] - curve.index[0]).days / 365.25)
    growth = cagr_pct(float(curve.iloc[0]), float(curve.iloc[-1]), years) or 0.0
    mdd = max_drawdown_pct(curve.tolist()) or 0.0
    return StrategyMetrics(name=name, cagr_pct=round(growth, 6), max_drawdown_pct=round(float(mdd), 6))


def _write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_suite(
    cases: Sequence[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    evaluation_stride: int = DEFAULT_STRIDE,
    cost_bps_per_side: float = 15.0,
    policies: Sequence[ReentryRiskPolicy] = POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)

    baseline_curves: list[pd.Series] = []
    baseline_trade_count = 0
    for data in ready:
        trades, _, _ = simulate_company(
            data,
            start_date=start_date,
            end_date=end_date,
            evaluation_stride=evaluation_stride,
            cost_bps_per_side=cost_bps_per_side,
        )
        baseline_trade_count += len(trades)
        baseline_curves.append(
            equity_curve_from_trades(data, trades, start_date=start_date, end_date=end_date)
        )
    baseline_curve = equal_weight_portfolio(baseline_curves)
    baseline = _metrics("baseline", baseline_curve)

    comparison_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    candidate_metrics: list[StrategyMetrics] = []

    for policy in policies:
        curves: list[pd.Series] = []
        total_risk_exits = 0
        total_reentries = 0
        total_trades = 0
        for data in ready:
            trades, _, curve, case = simulate_company_with_reentry(
                data,
                start_date=start_date,
                end_date=end_date,
                policy=policy,
                evaluation_stride=evaluation_stride,
                cost_bps_per_side=cost_bps_per_side,
            )
            curves.append(curve)
            case_rows.append(case)
            total_risk_exits += int(case.get("risk_exit_count") or 0)
            total_reentries += int(case.get("signal_confirmed_reentry_count") or 0)
            total_trades += len(trades)
            trade_rows.extend({"policy": policy.name, **trade} for trade in trades)

        portfolio = equal_weight_portfolio(curves)
        metrics = _metrics(policy.name, portfolio)
        candidate_metrics.append(metrics)
        evaluation = evaluate_candidate(baseline, metrics)
        comparison_rows.append(
            {
                **asdict(policy),
                "cagr_pct": metrics.cagr_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "calmar_ratio": evaluation.calmar_ratio,
                "drawdown_improvement_pct": evaluation.drawdown_improvement_pct,
                "cagr_retention_pct": evaluation.cagr_retention_pct,
                "trade_count": total_trades,
                "risk_exit_count": total_risk_exits,
                "signal_confirmed_reentry_count": total_reentries,
                "accepted": evaluation.accepted,
                "deployment_allowed": evaluation.deployment_allowed,
                "reasons": ";".join(evaluation.reasons),
            }
        )

    selected = select_drawdown_optimized(baseline, candidate_metrics)
    selected_policy = next(
        (policy for policy in policies if selected and policy.name == selected.metrics.name),
        None,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "reentry_policy_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "reentry_case_results.csv", case_rows, ["code", "stock_name", "policy"])
    _write_csv(output_dir / "reentry_trades.csv", trade_rows, ["policy", "code", "stock_name"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "baseline_trade_count": baseline_trade_count,
        "baseline_metrics": asdict(baseline),
        "selected_policy": asdict(selected_policy) if selected_policy else None,
        "selected_metrics": asdict(selected.metrics) if selected else None,
        "risk_gate_passed_on_diagnostic_panel": bool(selected and selected.accepted),
        "selected_drawdown_improvement_pct": selected.drawdown_improvement_pct if selected else None,
        "selected_cagr_retention_pct": selected.cagr_retention_pct if selected else None,
        "selected_calmar_ratio": selected.calmar_ratio if selected else None,
        "selected_reasons": list(selected.reasons) if selected else ["no_candidate_policy"],
        "same_point_in_time_entry_rule_as_baseline": True,
        "automatic_reentry_allowed": False,
        "reentry_requires_fresh_original_buy_signal": True,
        "reentry_cooldown_required": True,
        "risk_signals_observed_after_close_execute_next_open": True,
        "famous_case_selection_bias_warning": True,
        "production_deployment_allowed": False,
        "full_all_a_walk_forward_required": True,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "drawdown_reentry_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Signal-Confirmed Drawdown Re-entry Backtest",
        "",
        f"- period: {start_date} to {end_date}",
        f"- data-ready cases: {len(ready)}",
        f"- baseline CAGR: {baseline.cagr_pct:.4f}%",
        f"- baseline MDD: {baseline.max_drawdown_pct:.4f}%",
        "- all re-entries must pass the original point-in-time BUY rule again",
        "- no automatic averaging down or unconditional re-entry",
        "- famous-stock panel is diagnostic only",
        "",
        "## Policy comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row['calmar_ratio']} | retention={row['cagr_retention_pct']}% | "
            f"DD improvement={row['drawdown_improvement_pct']}% | trades={row['trade_count']} | "
            f"risk exits={row['risk_exit_count']} | confirmed reentries={row['signal_confirmed_reentry_count']} | "
            f"accepted={row['accepted']}"
        )
    if selected:
        lines += [
            "",
            "## Selected diagnostic policy",
            f"- policy: {selected.metrics.name}",
            f"- CAGR: {selected.metrics.cagr_pct:.4f}%",
            f"- MDD: {selected.metrics.max_drawdown_pct:.4f}%",
            f"- Calmar: {selected.calmar_ratio}",
            f"- drawdown improvement: {selected.drawdown_improvement_pct}%",
            f"- CAGR retention: {selected.cagr_retention_pct}%",
            f"- risk-gate accepted: {selected.accepted}",
            "- production deployment: BLOCKED until unbiased All-A walk-forward validation",
        ]
    (output_dir / "drawdown_reentry.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--evaluation-stride", type=int, default=DEFAULT_STRIDE)
    parser.add_argument("--cost-bps-per-side", type=float, default=15.0)
    args = parser.parse_args(argv)
    summary = run_suite(
        load_cases(args.cases_file),
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        evaluation_stride=max(1, args.evaluation_stride),
        cost_bps_per_side=max(0.0, args.cost_bps_per_side),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary["data_ready_case_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
