"""Low-frequency trend protection for large profitable winners.

The experiment keeps the point-in-time hard-logic + reverse-valuation entry and
exit events frozen. It also keeps the validated entry risk budget and winner
concentration cap. The only additional action is a partial trim when an already
profitable position has grown into a material share of NAV and then closes
below a long-horizon moving average by a defined margin.

The trend decision is formed after the close. The exact number of shares to
trim is frozen at that close and executes at the next observed session open.
No next-open price is used to size the order. Partial trims proportionally
reduce the position's frozen initial-risk dollars so later portfolio capacity
is not conservatively overstated.

This remains a biased named-stock diagnostic and cannot authorize deployment.
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
from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules
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
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import (
    BASE_ENTRY_POLICY,
    BASE_ENTRY_POLICY as DEFAULT_ENTRY_POLICY,
    ConcentrationGuardPolicy,
    _price_lookups,
    _weight_snapshot,
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

RULE_VERSION = "historical_winner_trend_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

BASE_CONCENTRATION_GUARD = ConcentrationGuardPolicy(
    "conc40_to30_cd20",
    trigger_fraction=0.40,
    target_fraction=0.30,
    min_holding_sessions=20,
    cooldown_sessions=20,
    trim_cost_bps=15.0,
)


@dataclass(frozen=True)
class WinnerTrendPolicy:
    name: str
    minimum_weight_fraction: float
    minimum_gain_pct: float
    moving_average_sessions: int
    break_below_ma_pct: float
    target_fraction: float
    minimum_holding_sessions: int = 60
    cooldown_sessions: int = 40
    trim_cost_bps: float = 15.0

    def __post_init__(self) -> None:
        if not 0 < self.target_fraction < self.minimum_weight_fraction < 1:
            raise ValueError("require target < minimum weight < 1")
        if self.minimum_gain_pct < 0:
            raise ValueError("minimum gain must be non-negative")
        if self.moving_average_sessions < 20:
            raise ValueError("winner trend MA must be long-horizon")
        if not 0 <= self.break_below_ma_pct < 25:
            raise ValueError("break-below-MA margin is invalid")
        if self.minimum_holding_sessions < 0 or self.cooldown_sessions < 0:
            raise ValueError("holding/cooldown sessions must be non-negative")
        if self.trim_cost_bps < 0:
            raise ValueError("trim cost must be non-negative")


POLICY_GRID: tuple[WinnerTrendPolicy, ...] = (
    WinnerTrendPolicy("winner20_gain50_ma120_to12", 0.20, 50.0, 120, 3.0, 0.12),
    WinnerTrendPolicy("winner25_gain75_ma120_to15", 0.25, 75.0, 120, 3.0, 0.15),
    WinnerTrendPolicy("winner20_gain100_ma200_to15", 0.20, 100.0, 200, 3.0, 0.15),
    WinnerTrendPolicy("winner25_gain50_ma200_to15", 0.25, 50.0, 200, 3.0, 0.15),
)


def _trend_maps(
    data_map: Mapping[str, HistoricalCompanyData], ma_windows: Iterable[int],
) -> dict[int, dict[str, dict[date, float]]]:
    windows = sorted(set(int(value) for value in ma_windows))
    result: dict[int, dict[str, dict[date, float]]] = {window: {} for window in windows}
    for code, data in data_map.items():
        history = prepare_price_frame(data.price_df).copy()
        if history.empty:
            continue
        close = pd.to_numeric(history["close"], errors="coerce")
        for window in windows:
            ma = close.rolling(window, min_periods=max(20, int(window * 0.75))).mean()
            mapping: dict[date, float] = {}
            for raw_day, raw_ma in zip(history["date"], ma):
                day = _day(raw_day)
                value = _finite(raw_ma)
                if day is not None and value is not None and value > 0:
                    mapping[day] = value
            result[window][str(code)] = mapping
    return result


def replay_with_winner_trend_guard(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
    entry_policy: PortfolioConstructionPolicy,
    concentration_policy: ConcentrationGuardPolicy,
    winner_policy: WinnerTrendPolicy,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    dates, closes, opens = _price_lookups(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
    date_index = {day: index for index, day in enumerate(dates)}
    ma_maps = _trend_maps(data_map, [winner_policy.moving_average_sessions])

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
    winner_trend_trim_count = 0
    concentration_trim_count = 0

    for day in dates:
        day_i = date_index[day]

        # Frozen strategy exits have first priority.
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

        # Execute fixed-share trims at today's observable open.
        for event_id, order in list(pending_trims.items()):
            position = positions.get(event_id)
            if position is None:
                pending_trims.pop(event_id, None)
                continue
            code = str(position["code"])
            open_price = opens.get(code, {}).get(day)
            if open_price is None or open_price <= 0:
                continue
            old_shares = float(position["shares"])
            shares_to_sell = min(old_shares, float(order["shares_to_sell"]))
            if shares_to_sell <= 0:
                pending_trims.pop(event_id, None)
                continue
            gross_proceeds = shares_to_sell * open_price
            cost = gross_proceeds * winner_policy.trim_cost_bps / 10_000.0
            cash += gross_proceeds - cost
            new_shares = max(0.0, old_shares - shares_to_sell)
            position["shares"] = new_shares
            # Frozen stop-risk dollars represent the currently held shares.
            # A partial trim must release the same fraction of open-risk budget.
            if old_shares > 0:
                position["initial_risk_dollars"] = float(position.get("initial_risk_dollars") or 0.0) * (new_shares / old_shares)
            position["last_trim_index"] = day_i
            trim_turnover_dollars += gross_proceeds
            trim_cost_dollars += cost
            pending_trims.pop(event_id, None)
            reason = str(order["reason"])
            if reason == "WINNER_TREND_BREAK":
                winner_trend_trim_count += 1
            else:
                concentration_trim_count += 1
            trim_rows.append(
                {
                    "policy": winner_policy.name,
                    "event_id": event_id,
                    "code": code,
                    "stock_name": position.get("stock_name"),
                    "reason": reason,
                    "decision_date": order["decision_date"],
                    "execution_date": day,
                    "execution_open": round(open_price, 6),
                    "shares_sold": shares_to_sell,
                    "gross_proceeds": gross_proceeds,
                    "friction_cost": cost,
                    "trigger_weight": order["trigger_weight"],
                    "trigger_gain_pct": order.get("trigger_gain_pct"),
                    "decision_close": order.get("decision_close"),
                    "moving_average": order.get("moving_average"),
                    "target_fraction": order["target_fraction"],
                    "shares_frozen_before_open": True,
                    "risk_budget_released_proportionally": True,
                }
            )
            if new_shares <= 1e-12:
                positions.pop(event_id, None)

        # Execute entries sized at the prior signal close.
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

        equity_before_trim, weights = _weight_snapshot(positions, cash=cash, day=day, closes=closes)
        if weights:
            max_name_weight_observed = max(max_name_weight_observed, max(weights.values()))

        # Decide tomorrow's fixed-share trim using only today's close/history.
        if equity_before_trim > 0:
            for event_id, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True):
                if event_id in pending_trims:
                    continue
                position = positions.get(event_id)
                if position is None:
                    continue
                entry_i = int(position.get("entry_index", day_i))
                last_trim_i = int(position.get("last_trim_index", -10**9))
                if day_i - last_trim_i < min(concentration_policy.cooldown_sessions, winner_policy.cooldown_sessions):
                    continue
                code = str(position["code"])
                close = closes.get(code, {}).get(day)
                entry_price = _finite(position.get("entry_price"))
                if close is None or close <= 0 or entry_price is None or entry_price <= 0:
                    continue

                reason = ""
                target_fraction: float | None = None
                gain_pct = (close / entry_price - 1.0) * 100.0
                ma_value = ma_maps[winner_policy.moving_average_sessions].get(code, {}).get(day)
                concentration_ready = (
                    weight > concentration_policy.trigger_fraction
                    and day_i - entry_i >= concentration_policy.min_holding_sessions
                )
                trend_ready = (
                    weight >= winner_policy.minimum_weight_fraction
                    and gain_pct >= winner_policy.minimum_gain_pct
                    and day_i - entry_i >= winner_policy.minimum_holding_sessions
                    and ma_value is not None
                    and close <= ma_value * (1.0 - winner_policy.break_below_ma_pct / 100.0)
                )
                if concentration_ready:
                    reason = "CONCENTRATION_CAP"
                    target_fraction = concentration_policy.target_fraction
                if trend_ready:
                    # If both fire, use the lower/risk-reducing target.
                    reason = "WINNER_TREND_BREAK"
                    target_fraction = min(
                        target_fraction if target_fraction is not None else 1.0,
                        winner_policy.target_fraction,
                    )
                if target_fraction is None:
                    continue

                current_mark = float(position["shares"]) * close
                target_mark = equity_before_trim * target_fraction
                shares_to_sell = max(0.0, (current_mark - target_mark) / close)
                shares_to_sell = min(shares_to_sell, float(position["shares"]))
                if shares_to_sell <= 1e-12:
                    continue
                pending_trims[event_id] = {
                    "decision_date": day,
                    "shares_to_sell": shares_to_sell,
                    "trigger_weight": round(weight, 8),
                    "trigger_gain_pct": round(gain_pct, 6),
                    "decision_close": close,
                    "moving_average": ma_value,
                    "target_fraction": target_fraction,
                    "reason": reason,
                }

        # Existing entry risk budget; scheduled trims are not pre-counted as cash.
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
                    "policy": winner_policy.name,
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
        "concentration_policy": concentration_policy.name,
        "winner_policy": winner_policy.name,
        "allocated_event_count": sum(float(row.get("allocated_fraction") or 0.0) > 0 for row in allocation_rows),
        "blocked_event_count": sum(float(row.get("allocated_fraction") or 0.0) <= 0 for row in allocation_rows),
        "blocked_reason_counts": blocked_counts,
        "trim_count": len(trim_rows),
        "winner_trend_trim_count": winner_trend_trim_count,
        "concentration_trim_count": concentration_trim_count,
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
    policies: Sequence[WinnerTrendPolicy] = POLICY_GRID,
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
        name="naive_fixed20_fullgross", mode="fixed", fixed_entry_fraction=0.20,
        max_total_gross_fraction=1.00, max_total_open_risk_pct=100.0,
    )
    naive_curve, _, _ = replay_single_account(
        events, data_map, start_date=start_date, end_date=end_date, policy=naive_policy
    )
    naive_metrics = _metrics(naive_policy.name, naive_curve)

    comparison_rows: list[dict[str, Any]] = []
    all_allocations: list[dict[str, Any]] = []
    all_trims: list[dict[str, Any]] = []
    candidate_metrics: list[StrategyMetrics] = []
    selected_row: dict[str, Any] | None = None

    for policy in policies:
        curve, allocations, trims, audit = replay_with_winner_trend_guard(
            events,
            data_map,
            start_date=start_date,
            end_date=end_date,
            entry_policy=DEFAULT_ENTRY_POLICY,
            concentration_policy=BASE_CONCENTRATION_GUARD,
            winner_policy=policy,
        )
        metrics = _metrics(policy.name, curve)
        candidate_metrics.append(metrics)
        evaluation = evaluate_candidate(naive_metrics, metrics)
        row = {
            **asdict(policy),
            "cagr_pct": metrics.cagr_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "calmar_ratio": evaluation.calmar_ratio,
            "cagr_retention_vs_naive_pct": evaluation.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": evaluation.drawdown_improvement_pct,
            "accepted": evaluation.accepted,
            "reasons": ";".join(evaluation.reasons),
            **audit,
        }
        comparison_rows.append(row)
        all_allocations.extend(allocations)
        all_trims.extend(trims)
        if evaluation.accepted and (
            selected_row is None or float(row.get("calmar_ratio") or -math.inf) > float(selected_row.get("calmar_ratio") or -math.inf)
        ):
            selected_row = row

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "winner_trend_guard_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "winner_trend_guard_allocations.csv", all_allocations, ["policy", "event_id"])
    _write_csv(output_dir / "winner_trend_guard_trims.csv", all_trims, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "naive_metrics": asdict(naive_metrics),
        "entry_budget_policy": asdict(BASE_ENTRY_POLICY),
        "concentration_guard": asdict(BASE_CONCENTRATION_GUARD),
        "selected_policy": selected_row,
        "risk_gate_passed_on_diagnostic_panel": selected_row is not None,
        "stock_entry_signal_set_frozen": True,
        "stock_exit_signal_set_frozen": True,
        "winner_requires_profit_and_material_weight": True,
        "trend_decision_after_close_for_next_open": True,
        "trim_shares_frozen_before_next_open": True,
        "partial_trim_releases_open_risk_budget": True,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_winner_trend_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Historical Winner Trend Guard",
        "",
        f"- period: {start_date} to {end_date}",
        f"- frozen events: {len(events)}",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        "- only profitable, material-weight winners can trigger trend protection",
        "- close decision freezes exact shares; next observed open executes with friction",
        "- partial trims release frozen open-risk budget proportionally",
        "- production deployment remains blocked pending survivorship-aware All-A validation",
        "",
        "## Comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_vs_naive_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_vs_naive_pct')}% | "
            f"winner trims={row.get('winner_trend_trim_count')} | concentration trims={row.get('concentration_trim_count')} | "
            f"accepted={row.get('accepted')}"
        )
    (output_dir / "historical_winner_trend_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
