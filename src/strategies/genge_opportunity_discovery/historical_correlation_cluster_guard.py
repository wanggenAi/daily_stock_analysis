"""Point-in-time correlation-cluster cap for the historical single account.

The production-style entry risk budget controls each position and total frozen
stop risk, but several individually sensible positions can still be the same
factor trade.  This diagnostic treats positions whose trailing daily returns
are highly correlated as one empirical risk cluster and caps new exposure to
that cluster.

Correlation is calculated only from sessions visible at the signal close. Same-
day reservations are included, so a batch of correlated candidates cannot each
pretend the other pending orders do not exist.  The cap changes position size,
not stock selection or the frozen entry/exit event set.  Existing winners are
not mechanically rebalanced; the separate low-frequency concentration guard
remains responsible for extreme single-name drift.

This remains an ex-post named-stock diagnostic and cannot authorize deployment.
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
    ConcentrationGuardPolicy,
    _price_lookups,
    _weight_snapshot,
    replay_with_concentration_guard,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    _finite,
    _metrics,
    _policy_to_risk_policy,
    _portfolio_snapshot,
    collect_frozen_events,
    replay_single_account,
)

RULE_VERSION = "historical_correlation_cluster_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

BASE_CONCENTRATION_GUARD = ConcentrationGuardPolicy(
    "conc40_to30_cd20", 0.40, 0.30, 20, 20, 15.0,
)


@dataclass(frozen=True)
class CorrelationClusterPolicy:
    name: str
    correlation_threshold: float
    max_cluster_fraction: float
    lookback_sessions: int = 120
    minimum_observations: int = 60

    def __post_init__(self) -> None:
        if not -1.0 < self.correlation_threshold < 1.0:
            raise ValueError("correlation threshold must be inside (-1, 1)")
        if not 0 < self.max_cluster_fraction <= 1.0:
            raise ValueError("cluster fraction must be in (0, 1]")
        if self.lookback_sessions < 20:
            raise ValueError("correlation lookback is too short")
        if not 10 <= self.minimum_observations <= self.lookback_sessions:
            raise ValueError("minimum observations are invalid")


POLICY_GRID: tuple[CorrelationClusterPolicy, ...] = (
    CorrelationClusterPolicy("corr55_cluster35", 0.55, 0.35),
    CorrelationClusterPolicy("corr65_cluster35", 0.65, 0.35),
    CorrelationClusterPolicy("corr65_cluster40", 0.65, 0.40),
    CorrelationClusterPolicy("corr70_cluster40", 0.70, 0.40),
)


def _return_maps(
    data_map: Mapping[str, HistoricalCompanyData],
) -> dict[str, pd.Series]:
    result: dict[str, pd.Series] = {}
    for code, data in data_map.items():
        frame = prepare_price_frame(data.price_df).copy()
        if frame.empty:
            continue
        close = pd.to_numeric(frame["close"], errors="coerce")
        series = pd.Series(close.pct_change().to_numpy(), index=pd.Index(frame["date"], name="date"), dtype=float)
        series = series.replace([math.inf, -math.inf], math.nan).dropna()
        if not series.empty:
            result[str(code)] = series
    return result


def point_in_time_correlation(
    return_maps: Mapping[str, pd.Series],
    code_a: str,
    code_b: str,
    *,
    as_of: date,
    lookback_sessions: int,
    minimum_observations: int,
) -> float | None:
    if code_a == code_b:
        return 1.0
    left = return_maps.get(str(code_a))
    right = return_maps.get(str(code_b))
    if left is None or right is None:
        return None
    left = left[left.index <= as_of]
    right = right[right.index <= as_of]
    joined = pd.concat([left.rename("a"), right.rename("b")], axis=1, join="inner").dropna().tail(lookback_sessions)
    if len(joined) < minimum_observations:
        return None
    value = _finite(joined["a"].corr(joined["b"]))
    return value


def _current_code_weights(
    positions: Mapping[str, Mapping[str, Any]],
    *,
    cash: float,
    day: date,
    closes: Mapping[str, Mapping[date, float]],
) -> tuple[float, dict[str, float]]:
    equity, event_weights = _weight_snapshot(positions, cash=cash, day=day, closes=closes)
    code_weights: dict[str, float] = {}
    for event_id, weight in event_weights.items():
        position = positions.get(event_id)
        if position is None:
            continue
        code = str(position["code"])
        code_weights[code] = code_weights.get(code, 0.0) + float(weight)
    return equity, code_weights


def correlated_fraction_for_candidate(
    candidate_code: str,
    *,
    as_of: date,
    current_code_weights: Mapping[str, float],
    reserved_candidates: Sequence[Mapping[str, Any]],
    return_maps: Mapping[str, pd.Series],
    policy: CorrelationClusterPolicy,
) -> tuple[float, list[dict[str, Any]], int]:
    total = 0.0
    audit: list[dict[str, Any]] = []
    missing_count = 0
    for code, fraction in current_code_weights.items():
        corr = point_in_time_correlation(
            return_maps, candidate_code, code, as_of=as_of,
            lookback_sessions=policy.lookback_sessions,
            minimum_observations=policy.minimum_observations,
        )
        if corr is None:
            missing_count += 1
            continue
        is_correlated = corr >= policy.correlation_threshold
        if is_correlated:
            total += float(fraction)
        audit.append({"other_code": code, "correlation": round(corr, 6), "fraction": float(fraction), "correlated": is_correlated, "source": "open_position"})
    for reserved in reserved_candidates:
        code = str(reserved["code"])
        fraction = float(reserved["fraction"])
        corr = point_in_time_correlation(
            return_maps, candidate_code, code, as_of=as_of,
            lookback_sessions=policy.lookback_sessions,
            minimum_observations=policy.minimum_observations,
        )
        if corr is None:
            missing_count += 1
            continue
        is_correlated = corr >= policy.correlation_threshold
        if is_correlated:
            total += fraction
        audit.append({"other_code": code, "correlation": round(corr, 6), "fraction": fraction, "correlated": is_correlated, "source": "same_day_reservation"})
    return total, audit, missing_count


def replay_with_correlation_cluster_cap(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
    entry_policy: PortfolioConstructionPolicy,
    concentration_policy: ConcentrationGuardPolicy,
    correlation_policy: CorrelationClusterPolicy,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    dates, closes, opens = _price_lookups(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
    date_index = {day: index for index, day in enumerate(dates)}
    return_maps = _return_maps(data_map)

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
    correlation_reduced_count = 0
    correlation_blocked_count = 0
    correlation_missing_pair_count = 0
    max_correlated_fraction_before = 0.0
    trim_turnover_dollars = 0.0
    trim_cost_dollars = 0.0

    for day in dates:
        day_i = date_index[day]

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
            proceeds = shares_to_sell * open_price
            cost = proceeds * concentration_policy.trim_cost_bps / 10_000.0
            cash += proceeds - cost
            new_shares = max(0.0, old_shares - shares_to_sell)
            position["shares"] = new_shares
            if old_shares > 0:
                position["initial_risk_dollars"] = float(position.get("initial_risk_dollars") or 0.0) * (new_shares / old_shares)
            position["last_trim_index"] = day_i
            trim_turnover_dollars += proceeds
            trim_cost_dollars += cost
            pending_trims.pop(event_id, None)
            trim_rows.append({
                "policy": correlation_policy.name, "event_id": event_id, "code": code,
                "stock_name": position.get("stock_name"), "decision_date": order["decision_date"],
                "execution_date": day, "execution_open": round(open_price, 6),
                "shares_sold": shares_to_sell, "gross_proceeds": proceeds,
                "friction_cost": cost, "trigger_weight": order["trigger_weight"],
                "target_fraction": concentration_policy.target_fraction,
                "shares_frozen_before_open": True, "risk_budget_released_proportionally": True,
            })
            if new_shares <= 1e-12:
                positions.pop(event_id, None)

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
                "event_id": event_id, "code": event["code"], "stock_name": event["stock_name"],
                "shares": shares, "entry_price": entry_price, "stop_price": stop,
                "initial_risk_dollars": risk_dollars, "entry_date": day,
                "entry_index": day_i, "last_trim_index": -10**9, "last_close": entry_price,
            }

        for position in positions.values():
            close = closes.get(str(position["code"]), {}).get(day)
            if close is not None:
                position["last_close"] = close

        equity_for_weights, event_weights = _weight_snapshot(positions, cash=cash, day=day, closes=closes)
        if equity_for_weights > 0:
            for event_id, weight in sorted(event_weights.items(), key=lambda item: item[1], reverse=True):
                if weight <= concentration_policy.trigger_fraction or event_id in pending_trims:
                    continue
                position = positions.get(event_id)
                if position is None:
                    continue
                entry_i = int(position.get("entry_index", day_i))
                last_trim_i = int(position.get("last_trim_index", -10**9))
                if day_i - entry_i < concentration_policy.min_holding_sessions:
                    continue
                if day_i - last_trim_i < concentration_policy.cooldown_sessions:
                    continue
                close = closes.get(str(position["code"]), {}).get(day)
                if close is None or close <= 0:
                    continue
                current_mark = float(position["shares"]) * close
                target_mark = equity_for_weights * concentration_policy.target_fraction
                shares_to_sell = max(0.0, (current_mark - target_mark) / close)
                shares_to_sell = min(shares_to_sell, float(position["shares"]))
                if shares_to_sell <= 1e-12:
                    continue
                pending_trims[event_id] = {
                    "decision_date": day, "shares_to_sell": shares_to_sell,
                    "trigger_weight": round(weight, 8),
                }

        base_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        equity = float(base_snapshot["equity"])
        if equity <= 0:
            break
        reserved_fraction = 0.0
        reserved_open_risk_pct = 0.0
        reserved_candidates: list[dict[str, Any]] = []
        _, current_code_weights = _current_code_weights(positions, cash=cash, day=day, closes=closes)

        for event in signals_by_day.get(day, []):
            event_id = str(event["event_id"])
            candidate_code = str(event["code"])
            geometry = dict(event.get("risk_geometry") or {})
            stop_distance = _finite(geometry.get("stop_distance_pct"))
            snapshot = _portfolio_snapshot(
                positions, cash=cash, day=day, closes=closes,
                reserved_fraction=reserved_fraction,
                reserved_open_risk_pct=reserved_open_risk_pct,
            )
            current_gross = float(snapshot["gross_fraction"])
            current_open_risk = float(snapshot["open_risk_pct"])
            base_fraction = 0.0
            status = "BLOCKED"
            reason = ""
            if stop_distance is None or stop_distance <= 0:
                status = "RISK_GEOMETRY_UNAVAILABLE"
                reason = str(geometry.get("source") or "risk_geometry_unavailable")
            else:
                base_fraction = position_fraction(
                    stop_distance_pct=stop_distance,
                    portfolio_drawdown_pct=0.0,
                    current_name_fraction=0.0,
                    current_industry_fraction=0.0,
                    current_total_fraction=current_gross,
                    current_open_risk_pct=current_open_risk,
                    policy=_policy_to_risk_policy(entry_policy),
                )
                status = "ALLOCATED" if base_fraction > 0 else "NO_RISK_CAPACITY"
                reason = "point_in_time_stop_risk_budget"

            correlated_fraction, corr_audit, missing_pairs = correlated_fraction_for_candidate(
                candidate_code,
                as_of=day,
                current_code_weights=current_code_weights,
                reserved_candidates=reserved_candidates,
                return_maps=return_maps,
                policy=correlation_policy,
            )
            correlation_missing_pair_count += missing_pairs
            max_correlated_fraction_before = max(max_correlated_fraction_before, correlated_fraction)
            cluster_room = max(0.0, correlation_policy.max_cluster_fraction - correlated_fraction)
            fraction = min(float(base_fraction), cluster_room)
            if base_fraction > 0 and fraction <= 0:
                correlation_blocked_count += 1
                status = "CORRELATION_CLUSTER_CAP"
                reason = "correlated_cluster_full"
            elif 0 < fraction + 1e-12 < base_fraction:
                correlation_reduced_count += 1
                status = "ALLOCATED_CORRELATION_REDUCED"
                reason = "point_in_time_correlation_cluster_cap"

            fraction = round(max(0.0, fraction), 8)
            planned_dollars = equity * fraction
            if planned_dollars > cash - equity * reserved_fraction:
                planned_dollars = max(0.0, cash - equity * reserved_fraction)
                fraction = planned_dollars / equity if equity > 0 else 0.0
            if fraction > 0 and planned_dollars > 0:
                reservations[event_id] = {"planned_fraction": fraction, "planned_dollars": planned_dollars}
                reserved_fraction += fraction
                if stop_distance is not None:
                    reserved_open_risk_pct += fraction * stop_distance
                reserved_candidates.append({"code": candidate_code, "fraction": fraction})
            else:
                blocked_counts[status] = blocked_counts.get(status, 0) + 1

            allocation_rows.append({
                "policy": correlation_policy.name, "entry_policy": entry_policy.name,
                "event_id": event_id, "signal_date": day, "entry_date": event["entry_date"],
                "code": candidate_code, "stock_name": event["stock_name"], "status": status,
                "reason": reason, "base_allocated_pct_before_correlation": round(float(base_fraction) * 100.0, 4),
                "allocated_fraction": round(fraction, 8), "allocated_pct": round(fraction * 100.0, 4),
                "stop_distance_pct": stop_distance, "gross_fraction_before": round(current_gross, 8),
                "open_risk_pct_before": round(current_open_risk, 6),
                "correlated_fraction_before": round(correlated_fraction, 8),
                "correlated_pct_before": round(correlated_fraction * 100.0, 4),
                "cluster_room_pct": round(cluster_room * 100.0, 4),
                "correlation_pair_count": len(corr_audit), "correlation_missing_pair_count": missing_pairs,
                "correlation_audit": json.dumps(corr_audit, ensure_ascii=False),
            })

        end_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        nav_dates.append(day)
        nav_values.append(float(end_snapshot["equity"]))

    curve = pd.Series(nav_values, index=pd.Index(nav_dates, name="date"), dtype=float)
    audit = {
        "entry_policy": entry_policy.name,
        "concentration_policy": concentration_policy.name,
        "correlation_policy": correlation_policy.name,
        "allocated_event_count": sum(float(row.get("allocated_fraction") or 0.0) > 0 for row in allocation_rows),
        "blocked_event_count": sum(float(row.get("allocated_fraction") or 0.0) <= 0 for row in allocation_rows),
        "blocked_reason_counts": blocked_counts,
        "correlation_reduced_count": correlation_reduced_count,
        "correlation_blocked_count": correlation_blocked_count,
        "correlation_missing_pair_count": correlation_missing_pair_count,
        "max_correlated_fraction_before_pct": round(max_correlated_fraction_before * 100.0, 6),
        "trim_count": len(trim_rows),
        "trim_turnover_dollars": round(trim_turnover_dollars, 8),
        "trim_friction_cost_dollars": round(trim_cost_dollars, 8),
        "ending_cash": round(cash, 8),
        "ending_open_position_count": len(positions),
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
    cases: Sequence[FamousCase], *, start_date: date, end_date: date,
    output_dir: Path, cache_dir: Path, board_rules_file: Path,
    evaluation_stride: int = 5, cost_bps_per_side: float = 15.0,
    policies: Sequence[CorrelationClusterPolicy] = POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    events, data_map, geometry_audit = collect_frozen_events(
        ready, start_date=start_date, end_date=end_date,
        evaluation_stride=evaluation_stride, cost_bps_per_side=cost_bps_per_side,
        board_rules=load_board_rules(board_rules_file),
    )
    naive_policy = PortfolioConstructionPolicy(
        name="naive_fixed20_fullgross", mode="fixed", fixed_entry_fraction=0.20,
        max_total_gross_fraction=1.00, max_total_open_risk_pct=100.0,
    )
    naive_curve, _, _ = replay_single_account(events, data_map, start_date=start_date, end_date=end_date, policy=naive_policy)
    naive_metrics = _metrics(naive_policy.name, naive_curve)
    concentration_curve, _, concentration_trims, concentration_audit = replay_with_concentration_guard(
        events, data_map, start_date=start_date, end_date=end_date,
        entry_policy=BASE_ENTRY_POLICY, guard_policy=BASE_CONCENTRATION_GUARD,
    )
    concentration_metrics = _metrics(BASE_CONCENTRATION_GUARD.name, concentration_curve)

    comparison_rows: list[dict[str, Any]] = []
    all_allocations: list[dict[str, Any]] = []
    all_trims: list[dict[str, Any]] = []
    selected_row: dict[str, Any] | None = None
    base_eval = evaluate_candidate(naive_metrics, concentration_metrics)
    comparison_rows.append({
        "name": BASE_CONCENTRATION_GUARD.name, "kind": "concentration_base",
        "cagr_pct": concentration_metrics.cagr_pct, "max_drawdown_pct": concentration_metrics.max_drawdown_pct,
        "calmar_ratio": base_eval.calmar_ratio, "cagr_retention_vs_naive_pct": base_eval.cagr_retention_pct,
        "drawdown_improvement_vs_naive_pct": base_eval.drawdown_improvement_pct,
        "accepted": base_eval.accepted, **concentration_audit,
    })

    for policy in policies:
        curve, allocations, trims, audit = replay_with_correlation_cluster_cap(
            events, data_map, start_date=start_date, end_date=end_date,
            entry_policy=BASE_ENTRY_POLICY, concentration_policy=BASE_CONCENTRATION_GUARD,
            correlation_policy=policy,
        )
        metrics = _metrics(policy.name, curve)
        evaluation = evaluate_candidate(naive_metrics, metrics)
        row = {
            **asdict(policy), "kind": "correlation_cluster_cap",
            "cagr_pct": metrics.cagr_pct, "max_drawdown_pct": metrics.max_drawdown_pct,
            "calmar_ratio": evaluation.calmar_ratio,
            "cagr_retention_vs_naive_pct": evaluation.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": evaluation.drawdown_improvement_pct,
            "accepted": evaluation.accepted, "reasons": ";".join(evaluation.reasons), **audit,
        }
        comparison_rows.append(row)
        all_allocations.extend(allocations)
        all_trims.extend(trims)
        if evaluation.accepted and (
            selected_row is None or float(row.get("calmar_ratio") or -math.inf) > float(selected_row.get("calmar_ratio") or -math.inf)
        ):
            selected_row = row

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "correlation_cluster_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "correlation_cluster_allocations.csv", all_allocations, ["policy", "event_id"])
    _write_csv(output_dir / "correlation_cluster_trims.csv", all_trims, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    summary = {
        "rule_version": RULE_VERSION, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready), "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit, "naive_metrics": asdict(naive_metrics),
        "concentration_base_metrics": asdict(concentration_metrics),
        "selected_policy": selected_row, "risk_gate_passed_on_diagnostic_panel": selected_row is not None,
        "stock_entry_signal_set_frozen": True, "stock_exit_signal_set_frozen": True,
        "correlation_uses_only_history_through_signal_close": True,
        "same_day_reservations_share_cluster_capacity": True,
        "partial_trim_releases_open_risk_budget": True,
        "famous_case_selection_bias_warning": True, "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False, "no_auto_trade": True, "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_correlation_cluster_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Historical Correlation Cluster Guard", "",
        f"- period: {start_date} to {end_date}", f"- frozen events: {len(events)}",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        f"- concentration base CAGR/MDD: {concentration_metrics.cagr_pct:.4f}% / {concentration_metrics.max_drawdown_pct:.4f}%",
        "- correlations use trailing returns visible at signal close only",
        "- same-day reservations consume cluster capacity before later candidates are sized",
        "- production deployment remains blocked pending survivorship-aware All-A validation", "", "## Comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_vs_naive_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_vs_naive_pct')}% | "
            f"corr reduced={row.get('correlation_reduced_count', 0)} | corr blocked={row.get('correlation_blocked_count', 0)} | "
            f"accepted={row.get('accepted')}"
        )
    (output_dir / "historical_correlation_cluster_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
        load_cases(args.cases_file), start_date=args.start_date, end_date=args.end_date,
        output_dir=args.output_dir, cache_dir=args.cache_dir, board_rules_file=args.board_rules_file,
        evaluation_stride=max(1, args.evaluation_stride), cost_bps_per_side=max(0.0, args.cost_bps_per_side),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary["data_ready_case_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
