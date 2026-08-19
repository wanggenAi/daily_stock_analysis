"""Low-frequency concentration guard on the historical single-account replay.

This experiment starts from the same point-in-time hard-logic + reverse-valuation
signals and the same entry-time portfolio risk budget as
``historical_portfolio_risk_budget``.  It changes only one thing after entry:
when a winner naturally grows into an excessive share of account NAV, a fixed
number of shares is scheduled for sale at the next observed session open.

No stock is sold merely because it is profitable.  A trim requires a high
single-name weight, a minimum holding age, and a cooldown since the previous
trim.  The decision uses only the current close and current account NAV; the
number of shares to sell is frozen before the next open.  Extra turnover pays a
one-way friction cost.

The named famous-stock panel is ex-post selected and remains diagnostic only.
This module cannot authorize production deployment; survivorship-aware All-A
walk-forward validation remains mandatory.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    StrategyMetrics,
    evaluate_candidate,
    position_fraction,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    HistoricalCompanyData,
    fetch_case_data,
    load_cases,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    _day,
    _finite,
    _metrics,
    _policy_to_risk_policy,
    _portfolio_snapshot,
    collect_frozen_events,
    replay_single_account,
)
from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules

RULE_VERSION = "historical_concentration_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


BASE_ENTRY_POLICY = PortfolioConstructionPolicy(
    name="risk075_open4",
    mode="risk_budget",
    risk_per_trade_pct=0.75,
    max_single_name_fraction=0.20,
    max_total_gross_fraction=0.90,
    max_total_open_risk_pct=4.0,
)


@dataclass(frozen=True)
class ConcentrationGuardPolicy:
    name: str
    trigger_fraction: float
    target_fraction: float
    min_holding_sessions: int = 20
    cooldown_sessions: int = 20
    trim_cost_bps: float = 15.0

    def __post_init__(self) -> None:
        if not 0 < self.target_fraction < self.trigger_fraction < 1:
            raise ValueError("require 0 < target_fraction < trigger_fraction < 1")
        if self.min_holding_sessions < 0 or self.cooldown_sessions < 0:
            raise ValueError("holding/cooldown sessions must be non-negative")
        if self.trim_cost_bps < 0:
            raise ValueError("trim_cost_bps must be non-negative")


GUARD_GRID: tuple[ConcentrationGuardPolicy, ...] = (
    ConcentrationGuardPolicy("conc35_to25_cd20", 0.35, 0.25, 20, 20),
    ConcentrationGuardPolicy("conc40_to30_cd20", 0.40, 0.30, 20, 20),
    ConcentrationGuardPolicy("conc45_to30_cd20", 0.45, 0.30, 20, 20),
    ConcentrationGuardPolicy("conc40_to25_cd40", 0.40, 0.25, 30, 40),
)


def _price_lookups(
    data_map: Mapping[str, HistoricalCompanyData],
) -> tuple[list[date], dict[str, dict[date, float]], dict[str, dict[date, float]]]:
    all_dates: set[date] = set()
    closes: dict[str, dict[date, float]] = {}
    opens: dict[str, dict[date, float]] = {}
    for code, data in data_map.items():
        history = prepare_price_frame(data.price_df)
        close_map: dict[date, float] = {}
        open_map: dict[date, float] = {}
        for _, row in history.iterrows():
            day = _day(row.get("date"))
            close = _finite(row.get("close"))
            open_price = _finite(row.get("open"))
            if day is None:
                continue
            if close is not None and close > 0:
                close_map[day] = close
                all_dates.add(day)
            if open_price is not None and open_price > 0:
                open_map[day] = open_price
        closes[code] = close_map
        opens[code] = open_map
    return sorted(all_dates), closes, opens


def _weight_snapshot(
    positions: Mapping[str, Mapping[str, Any]],
    *,
    cash: float,
    day: date,
    closes: Mapping[str, Mapping[date, float]],
) -> tuple[float, dict[str, float]]:
    marks: dict[str, float] = {}
    for event_id, position in positions.items():
        code = str(position["code"])
        close = closes.get(code, {}).get(day)
        if close is None:
            close = _finite(position.get("last_close")) or _finite(position.get("entry_price")) or 0.0
        marks[event_id] = float(position["shares"]) * float(close)
    equity = cash + sum(marks.values())
    weights = {
        event_id: (mark / equity if equity > 0 else 0.0)
        for event_id, mark in marks.items()
    }
    return equity, weights


def replay_with_concentration_guard(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
    entry_policy: PortfolioConstructionPolicy,
    guard_policy: ConcentrationGuardPolicy,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    dates, closes, opens = _price_lookups(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
    date_index = {day: index for index, day in enumerate(dates)}

    signals_by_day: dict[date, list[Mapping[str, Any]]] = {}
    entries_by_day: dict[date, list[Mapping[str, Any]]] = {}
    exits_by_day: dict[date, list[Mapping[str, Any]]] = {}
    for event in events:
        signals_by_day.setdefault(event["signal_date"], []).append(event)
        entries_by_day.setdefault(event["entry_date"], []).append(event)
        exits_by_day.setdefault(event["exit_date"], []).append(event)
    for day_events in signals_by_day.values():
        day_events.sort(key=lambda item: item["signal_rank"], reverse=True)

    cash = 1.0
    positions: dict[str, dict[str, Any]] = {}
    reservations: dict[str, dict[str, Any]] = {}
    pending_trims: dict[str, dict[str, Any]] = {}
    nav_values: list[float] = []
    nav_dates: list[date] = []
    allocation_rows: list[dict[str, Any]] = []
    trim_rows: list[dict[str, Any]] = []
    blocked_counts: dict[str, int] = {}
    trim_turnover_dollars = 0.0
    trim_cost_dollars = 0.0
    max_name_weight_observed = 0.0

    for day in dates:
        day_i = date_index[day]

        # Frozen strategy exits take precedence over concentration trims.
        for event in exits_by_day.get(day, []):
            event_id = str(event["event_id"])
            pending_trims.pop(event_id, None)
            position = positions.pop(event_id, None)
            if position is None:
                continue
            exit_price = _finite(event.get("exit_price"))
            if exit_price is None or exit_price <= 0:
                positions[event_id] = position
                continue
            cash += float(position["shares"]) * exit_price

        # Execute yesterday's (or latest prior session's) fixed-share trim at
        # today's observable open.  Never recompute shares from the future open.
        for event_id, order in list(pending_trims.items()):
            position = positions.get(event_id)
            if position is None:
                pending_trims.pop(event_id, None)
                continue
            code = str(position["code"])
            open_price = opens.get(code, {}).get(day)
            if open_price is None or open_price <= 0:
                continue
            shares_to_sell = min(float(position["shares"]), float(order["shares_to_sell"]))
            if shares_to_sell <= 0:
                pending_trims.pop(event_id, None)
                continue
            gross_proceeds = shares_to_sell * open_price
            cost = gross_proceeds * guard_policy.trim_cost_bps / 10_000.0
            cash += gross_proceeds - cost
            position["shares"] = float(position["shares"]) - shares_to_sell
            position["last_trim_index"] = day_i
            trim_turnover_dollars += gross_proceeds
            trim_cost_dollars += cost
            pending_trims.pop(event_id, None)
            trim_rows.append(
                {
                    "policy": guard_policy.name,
                    "event_id": event_id,
                    "code": code,
                    "stock_name": position.get("stock_name"),
                    "decision_date": order["decision_date"],
                    "execution_date": day,
                    "execution_open": round(open_price, 6),
                    "shares_sold": shares_to_sell,
                    "gross_proceeds": gross_proceeds,
                    "friction_cost": cost,
                    "trigger_weight": order["trigger_weight"],
                    "target_fraction": guard_policy.target_fraction,
                    "shares_frozen_before_open": True,
                }
            )
            if float(position["shares"]) <= 1e-12:
                positions.pop(event_id, None)

        # Execute entries sized after the prior signal close.
        for event in entries_by_day.get(day, []):
            event_id = str(event["event_id"])
            reservation = reservations.pop(event_id, None)
            if reservation is None:
                continue
            entry_price = _finite(event.get("entry_price"))
            if entry_price is None or entry_price <= 0:
                continue
            stop = _finite(event.get("risk_geometry", {}).get("stop_price"))
            if stop is not None and entry_price <= stop:
                blocked_counts["open_at_or_below_stop"] = blocked_counts.get("open_at_or_below_stop", 0) + 1
                continue
            amount = min(cash, float(reservation["planned_dollars"]))
            if amount <= 0:
                blocked_counts["cash_unavailable_at_execution"] = blocked_counts.get("cash_unavailable_at_execution", 0) + 1
                continue
            shares = amount / entry_price
            cash -= amount
            risk_dollars = shares * max(0.0, entry_price - stop) if stop is not None and stop > 0 else 0.0
            positions[event_id] = {
                "event_id": event_id,
                "code": event["code"],
                "stock_name": event["stock_name"],
                "shares": shares,
                "entry_price": entry_price,
                "stop_price": stop,
                "initial_risk_dollars": risk_dollars,
                "entry_date": day,
                "entry_index": day_i,
                "last_trim_index": -10**9,
                "last_close": entry_price,
            }

        for position in positions.values():
            close = closes.get(str(position["code"]), {}).get(day)
            if close is not None:
                position["last_close"] = close

        # High-water single-name concentration check.  Only actual weight drift
        # can trigger; profit magnitude itself is not a sell signal.
        equity_before_trim_decisions, weights = _weight_snapshot(
            positions, cash=cash, day=day, closes=closes
        )
        if weights:
            max_name_weight_observed = max(max_name_weight_observed, max(weights.values()))
        if equity_before_trim_decisions > 0:
            for event_id, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True):
                if weight <= guard_policy.trigger_fraction or event_id in pending_trims:
                    continue
                position = positions.get(event_id)
                if position is None:
                    continue
                entry_i = int(position.get("entry_index", day_i))
                last_trim_i = int(position.get("last_trim_index", -10**9))
                if day_i - entry_i < guard_policy.min_holding_sessions:
                    continue
                if day_i - last_trim_i < guard_policy.cooldown_sessions:
                    continue
                close = closes.get(str(position["code"]), {}).get(day)
                if close is None or close <= 0:
                    continue
                current_mark = float(position["shares"]) * close
                target_mark = equity_before_trim_decisions * guard_policy.target_fraction
                shares_to_sell = max(0.0, (current_mark - target_mark) / close)
                shares_to_sell = min(shares_to_sell, float(position["shares"]))
                if shares_to_sell <= 1e-12:
                    continue
                pending_trims[event_id] = {
                    "decision_date": day,
                    "shares_to_sell": shares_to_sell,
                    "trigger_weight": round(weight, 8),
                    "decision_close": close,
                }

        # Entry sizing uses the same point-in-time risk policy as the prior
        # single-account experiment.  A trim scheduled for tomorrow is NOT
        # treated as freed capacity today; that is deliberately conservative.
        base_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        equity = float(base_snapshot["equity"])
        if equity <= 0:
            break
        reserved_fraction = 0.0
        reserved_open_risk_pct = 0.0
        for event in signals_by_day.get(day, []):
            event_id = str(event["event_id"])
            geometry = dict(event.get("risk_geometry") or {})
            stop_distance = _finite(geometry.get("stop_distance_pct"))
            snapshot = _portfolio_snapshot(
                positions,
                cash=cash,
                day=day,
                closes=closes,
                reserved_fraction=reserved_fraction,
                reserved_open_risk_pct=reserved_open_risk_pct,
            )
            current_gross = float(snapshot["gross_fraction"])
            current_open_risk = float(snapshot["open_risk_pct"])
            fraction = 0.0
            status = "BLOCKED"
            reason = ""
            if stop_distance is None or stop_distance <= 0:
                status = "RISK_GEOMETRY_UNAVAILABLE"
                reason = str(geometry.get("source") or "risk_geometry_unavailable")
            else:
                risk_policy = _policy_to_risk_policy(entry_policy)
                fraction = position_fraction(
                    stop_distance_pct=stop_distance,
                    portfolio_drawdown_pct=0.0,
                    current_name_fraction=0.0,
                    current_industry_fraction=0.0,
                    current_total_fraction=current_gross,
                    current_open_risk_pct=current_open_risk,
                    policy=risk_policy,
                )
                status = "ALLOCATED" if fraction > 0 else "NO_RISK_CAPACITY"
                reason = "point_in_time_stop_risk_budget"

            fraction = round(max(0.0, float(fraction)), 8)
            planned_dollars = equity * fraction
            if planned_dollars > cash - equity * reserved_fraction:
                planned_dollars = max(0.0, cash - equity * reserved_fraction)
                fraction = planned_dollars / equity if equity > 0 else 0.0
            if fraction > 0 and planned_dollars > 0:
                reservations[event_id] = {
                    "planned_fraction": fraction,
                    "planned_dollars": planned_dollars,
                }
                reserved_fraction += fraction
                if stop_distance is not None:
                    reserved_open_risk_pct += fraction * stop_distance
            else:
                blocked_counts[status] = blocked_counts.get(status, 0) + 1

            allocation_rows.append(
                {
                    "policy": guard_policy.name,
                    "entry_policy": entry_policy.name,
                    "event_id": event_id,
                    "signal_date": day,
                    "entry_date": event["entry_date"],
                    "code": event["code"],
                    "stock_name": event["stock_name"],
                    "status": status,
                    "reason": reason,
                    "allocated_fraction": round(fraction, 8),
                    "allocated_pct": round(fraction * 100.0, 4),
                    "stop_distance_pct": stop_distance,
                    "gross_fraction_before": round(current_gross, 8),
                    "open_risk_pct_before": round(current_open_risk, 6),
                }
            )

        end_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        nav_dates.append(day)
        nav_values.append(float(end_snapshot["equity"]))

    curve = pd.Series(nav_values, index=pd.Index(nav_dates, name="date"), dtype=float)
    audit = {
        "entry_policy": entry_policy.name,
        "guard_policy": guard_policy.name,
        "allocated_event_count": sum(float(row.get("allocated_fraction") or 0.0) > 0 for row in allocation_rows),
        "blocked_event_count": sum(float(row.get("allocated_fraction") or 0.0) <= 0 for row in allocation_rows),
        "blocked_reason_counts": blocked_counts,
        "trim_count": len(trim_rows),
        "trim_turnover_dollars": round(trim_turnover_dollars, 8),
        "trim_friction_cost_dollars": round(trim_cost_dollars, 8),
        "max_single_name_weight_observed_pct": round(max_name_weight_observed * 100.0, 6),
        "ending_cash": round(cash, 8),
        "ending_open_position_count": len(positions),
        "pending_trim_count": len(pending_trims),
    }
    return curve, allocation_rows, trim_rows, audit


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fallback_fields: Sequence[str]) -> None:
    values = [dict(row) for row in rows]
    fields = sorted({key for row in values for key in row}) if values else list(fallback_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def run_suite(
    cases: Sequence[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    board_rules_file: Path,
    evaluation_stride: int = 5,
    cost_bps_per_side: float = 15.0,
    entry_policy: PortfolioConstructionPolicy = BASE_ENTRY_POLICY,
    guards: Sequence[ConcentrationGuardPolicy] = GUARD_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    events, data_map, geometry_audit = collect_frozen_events(
        ready,
        start_date=start_date,
        end_date=end_date,
        evaluation_stride=evaluation_stride,
        cost_bps_per_side=cost_bps_per_side,
        board_rules=load_board_rules(board_rules_file),
    )

    naive_policy = PortfolioConstructionPolicy(
        name="naive_fixed20_fullgross",
        mode="fixed",
        fixed_entry_fraction=0.20,
        max_total_gross_fraction=1.00,
        max_total_open_risk_pct=100.0,
    )
    naive_curve, _, _ = replay_single_account(
        events, data_map, start_date=start_date, end_date=end_date, policy=naive_policy
    )
    naive_metrics = _metrics(naive_policy.name, naive_curve)

    base_curve, _, base_audit = replay_single_account(
        events, data_map, start_date=start_date, end_date=end_date, policy=entry_policy
    )
    base_metrics = _metrics(entry_policy.name, base_curve)

    comparison_rows: list[dict[str, Any]] = []
    all_allocations: list[dict[str, Any]] = []
    all_trims: list[dict[str, Any]] = []
    candidate_metrics: list[StrategyMetrics] = []
    guard_results: dict[str, dict[str, Any]] = {}

    comparison_rows.append(
        {
            "name": naive_policy.name,
            "kind": "naive_baseline",
            "cagr_pct": naive_metrics.cagr_pct,
            "max_drawdown_pct": naive_metrics.max_drawdown_pct,
            "calmar_ratio": naive_metrics.cagr_pct / naive_metrics.max_drawdown_pct if naive_metrics.max_drawdown_pct else None,
            "cagr_retention_vs_naive_pct": 100.0,
            "drawdown_improvement_vs_naive_pct": 0.0,
            "accepted": True,
        }
    )
    base_eval = evaluate_candidate(naive_metrics, base_metrics)
    comparison_rows.append(
        {
            "name": entry_policy.name,
            "kind": "entry_risk_budget_baseline",
            "cagr_pct": base_metrics.cagr_pct,
            "max_drawdown_pct": base_metrics.max_drawdown_pct,
            "calmar_ratio": base_eval.calmar_ratio,
            "cagr_retention_vs_naive_pct": base_eval.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": base_eval.drawdown_improvement_pct,
            "accepted": base_eval.accepted,
            **base_audit,
        }
    )

    for guard in guards:
        curve, allocations, trims, audit = replay_with_concentration_guard(
            events,
            data_map,
            start_date=start_date,
            end_date=end_date,
            entry_policy=entry_policy,
            guard_policy=guard,
        )
        metrics = _metrics(guard.name, curve)
        candidate_metrics.append(metrics)
        vs_naive = evaluate_candidate(naive_metrics, metrics)
        base_dd_improvement = (
            (base_metrics.max_drawdown_pct - metrics.max_drawdown_pct) / base_metrics.max_drawdown_pct * 100.0
            if base_metrics.max_drawdown_pct > 0 else 0.0
        )
        base_cagr_retention = (
            metrics.cagr_pct / base_metrics.cagr_pct * 100.0 if base_metrics.cagr_pct > 0 else 0.0
        )
        row = {
            **asdict(guard),
            "kind": "concentration_guard",
            "cagr_pct": metrics.cagr_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "calmar_ratio": vs_naive.calmar_ratio,
            "cagr_retention_vs_naive_pct": vs_naive.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": vs_naive.drawdown_improvement_pct,
            "cagr_retention_vs_entry_budget_pct": round(base_cagr_retention, 6),
            "drawdown_improvement_vs_entry_budget_pct": round(base_dd_improvement, 6),
            "accepted": vs_naive.accepted,
            "reasons": ";".join(vs_naive.reasons),
            **audit,
        }
        comparison_rows.append(row)
        all_allocations.extend(allocations)
        all_trims.extend(trims)
        guard_results[guard.name] = row

    # Selection is intentionally strict: use the same overall risk gate against
    # the naive single-account benchmark, then maximize Calmar among survivors.
    accepted = [row for row in comparison_rows if row.get("kind") == "concentration_guard" and row.get("accepted")]
    selected_row = max(accepted, key=lambda row: float(row.get("calmar_ratio") or -math.inf)) if accepted else None

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "concentration_guard_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "concentration_guard_allocations.csv", all_allocations, ["policy", "event_id"])
    _write_csv(output_dir / "concentration_guard_trims.csv", all_trims, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "naive_metrics": asdict(naive_metrics),
        "entry_budget_policy": asdict(entry_policy),
        "entry_budget_metrics": asdict(base_metrics),
        "selected_guard": selected_row,
        "risk_gate_passed_on_diagnostic_panel": selected_row is not None,
        "guard_result_count": len(guard_results),
        "entry_signal_set_frozen": True,
        "exit_signal_set_frozen": True,
        "trim_decision_after_close_for_next_open": True,
        "trim_shares_frozen_before_next_open": True,
        "profit_alone_never_triggers_trim": True,
        "industry_cap_applied_in_diagnostic_panel": False,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_concentration_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Historical Winner Concentration Guard",
        "",
        f"- period: {start_date} to {end_date}",
        f"- frozen events: {len(events)}",
        f"- risk geometry coverage: {geometry_audit['risk_geometry_coverage_ratio'] * 100:.2f}%",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        f"- entry-risk-budget CAGR/MDD: {base_metrics.cagr_pct:.4f}% / {base_metrics.max_drawdown_pct:.4f}%",
        "- concentration decisions use close; fixed shares execute next observed open",
        "- trims are high-threshold and cooldown-limited; profit itself is not a sell trigger",
        "- production deployment remains blocked pending survivorship-aware All-A validation",
        "",
        "## Guard comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | naive retention={row.get('cagr_retention_vs_naive_pct')}% | "
            f"naive DD improvement={row.get('drawdown_improvement_vs_naive_pct')}% | "
            f"trims={row.get('trim_count', 0)} | accepted={row.get('accepted')}"
        )
    (output_dir / "historical_concentration_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--board-rules-file", type=Path, default=Path("config/board_risk_rules.yaml"))
    parser.add_argument("--evaluation-stride", type=int, default=5)
    parser.add_argument("--cost-bps-per-side", type=float, default=15.0)
    args = parser.parse_args(argv)
    summary = run_suite(
        load_cases(args.cases_file),
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        board_rules_file=args.board_rules_file,
        evaluation_stride=max(1, args.evaluation_stride),
        cost_bps_per_side=max(0.0, args.cost_bps_per_side),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary["data_ready_case_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
