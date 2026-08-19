"""Dynamic point-in-time correlated-cluster de-risking.

Entry-time correlation caps cannot catch positions that become the same factor
trade only after they are already owned. This diagnostic rebuilds trailing
correlation clusters every close. A cluster is trimmed only when all three are
true: it contains multiple holdings, its aggregate NAV weight is excessive,
and the cluster is showing objective price weakness. The weakest members are
trimmed first; strong members are left untouched when possible.

All correlations, moving averages and returns use data through the current
close only. Exact trim shares are frozen at that close and execute at the next
observed session open with friction. The frozen stock-selection and strategy
exit events are unchanged.

The named famous-stock panel remains biased and this module cannot authorize
production deployment.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import evaluate_candidate, position_fraction
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase, HistoricalCompanyData, fetch_case_data, load_cases,
)
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import (
    BASE_ENTRY_POLICY, ConcentrationGuardPolicy, _price_lookups, _weight_snapshot,
)
from src.strategies.genge_opportunity_discovery.historical_correlation_cluster_guard import (
    CorrelationClusterPolicy, _return_maps, correlated_fraction_for_candidate,
    point_in_time_correlation,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy, _day, _finite, _metrics, _policy_to_risk_policy,
    _portfolio_snapshot, collect_frozen_events, replay_single_account,
)

RULE_VERSION = "historical_dynamic_cluster_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

BASE_CONCENTRATION_GUARD = ConcentrationGuardPolicy(
    "conc40_to30_cd20", 0.40, 0.30, 20, 20, 15.0,
)
BASE_ENTRY_CORRELATION_POLICY = CorrelationClusterPolicy(
    "corr65_cluster35", 0.65, 0.35, 120, 60,
)


@dataclass(frozen=True)
class DynamicClusterPolicy:
    name: str
    correlation_threshold: float
    trigger_cluster_fraction: float
    target_cluster_fraction: float
    lookback_sessions: int = 120
    minimum_observations: int = 60
    trend_sessions: int = 60
    below_trend_ratio_trigger: float = 0.50
    median_return_20d_trigger_pct: float = -3.0
    minimum_name_fraction_after_trim: float = 0.05
    minimum_holding_sessions: int = 20
    cooldown_sessions: int = 20
    trim_cost_bps: float = 15.0

    def __post_init__(self) -> None:
        if not -1 < self.correlation_threshold < 1:
            raise ValueError("invalid correlation threshold")
        if not 0 < self.target_cluster_fraction < self.trigger_cluster_fraction <= 1:
            raise ValueError("require target cluster < trigger cluster <= 1")
        if self.lookback_sessions < 20 or not 10 <= self.minimum_observations <= self.lookback_sessions:
            raise ValueError("invalid correlation history")
        if self.trend_sessions < 20:
            raise ValueError("trend window too short")
        if not 0 <= self.below_trend_ratio_trigger <= 1:
            raise ValueError("invalid below-trend ratio")
        if not 0 <= self.minimum_name_fraction_after_trim < self.target_cluster_fraction:
            raise ValueError("invalid post-trim name floor")
        if self.minimum_holding_sessions < 0 or self.cooldown_sessions < 0:
            raise ValueError("invalid holding/cooldown")
        if self.trim_cost_bps < 0:
            raise ValueError("trim cost must be non-negative")


POLICY_GRID: tuple[DynamicClusterPolicy, ...] = (
    DynamicClusterPolicy("dyn_corr60_50to40", 0.60, 0.50, 0.40),
    DynamicClusterPolicy("dyn_corr65_50to40", 0.65, 0.50, 0.40),
    DynamicClusterPolicy("dyn_corr65_45to35", 0.65, 0.45, 0.35),
    DynamicClusterPolicy("dyn_corr70_50to40", 0.70, 0.50, 0.40),
)


def _price_features(
    data_map: Mapping[str, HistoricalCompanyData], trend_sessions: int,
) -> dict[str, dict[date, dict[str, float | bool]]]:
    result: dict[str, dict[date, dict[str, float | bool]]] = {}
    for code, data in data_map.items():
        frame = prepare_price_frame(data.price_df).copy()
        if frame.empty:
            continue
        close = pd.to_numeric(frame["close"], errors="coerce")
        ma = close.rolling(trend_sessions, min_periods=max(20, int(trend_sessions * 0.75))).mean()
        ret20 = close.pct_change(20) * 100.0
        mapping: dict[date, dict[str, float | bool]] = {}
        for raw_day, raw_close, raw_ma, raw_ret in zip(frame["date"], close, ma, ret20):
            day = _day(raw_day)
            current = _finite(raw_close)
            ma_value = _finite(raw_ma)
            ret_value = _finite(raw_ret)
            if day is None or current is None:
                continue
            mapping[day] = {
                "close": current,
                "ma": ma_value if ma_value is not None else math.nan,
                "below_ma": bool(ma_value is not None and current < ma_value),
                "return_20d_pct": ret_value if ret_value is not None else math.nan,
            }
        result[str(code)] = mapping
    return result


def _connected_components(codes: Sequence[str], edges: Mapping[str, set[str]]) -> list[list[str]]:
    remaining = set(codes)
    components: list[list[str]] = []
    while remaining:
        root = remaining.pop()
        stack = [root]
        component = [root]
        while stack:
            node = stack.pop()
            for neighbor in edges.get(node, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
                    component.append(neighbor)
        components.append(sorted(component))
    return components


def dynamic_clusters(
    codes: Sequence[str], *, as_of: date,
    return_maps: Mapping[str, pd.Series], price_features: Mapping[str, Mapping[date, Mapping[str, Any]]],
    policy: DynamicClusterPolicy,
) -> list[dict[str, Any]]:
    unique = sorted(set(str(code) for code in codes))
    edges: dict[str, set[str]] = {code: set() for code in unique}
    pair_rows: list[dict[str, Any]] = []
    for i, left in enumerate(unique):
        for right in unique[i + 1:]:
            corr = point_in_time_correlation(
                return_maps, left, right, as_of=as_of,
                lookback_sessions=policy.lookback_sessions,
                minimum_observations=policy.minimum_observations,
            )
            if corr is None:
                continue
            linked = corr >= policy.correlation_threshold
            if linked:
                edges[left].add(right)
                edges[right].add(left)
            pair_rows.append({"left": left, "right": right, "correlation": round(corr, 6), "linked": linked})

    result: list[dict[str, Any]] = []
    for component in _connected_components(unique, edges):
        if len(component) < 2:
            continue
        below_values: list[bool] = []
        returns: list[float] = []
        member_features: dict[str, dict[str, Any]] = {}
        for code in component:
            feature = dict(price_features.get(code, {}).get(as_of, {}))
            below = bool(feature.get("below_ma"))
            ret20 = _finite(feature.get("return_20d_pct"))
            below_values.append(below)
            if ret20 is not None:
                returns.append(ret20)
            member_features[code] = {"below_ma": below, "return_20d_pct": ret20}
        below_ratio = sum(below_values) / len(below_values) if below_values else 0.0
        median_ret = median(returns) if returns else None
        stressed = bool(
            below_ratio >= policy.below_trend_ratio_trigger
            or (median_ret is not None and median_ret <= policy.median_return_20d_trigger_pct)
        )
        result.append({
            "codes": component, "below_trend_ratio": round(below_ratio, 6),
            "median_return_20d_pct": round(median_ret, 6) if median_ret is not None else None,
            "stressed": stressed, "member_features": member_features,
            "pair_rows": [row for row in pair_rows if row["left"] in component and row["right"] in component],
        })
    return result


def replay_with_dynamic_cluster_guard(
    events: Sequence[Mapping[str, Any]], data_map: Mapping[str, HistoricalCompanyData], *,
    start_date: date, end_date: date, entry_policy: PortfolioConstructionPolicy,
    concentration_policy: ConcentrationGuardPolicy,
    entry_correlation_policy: CorrelationClusterPolicy,
    dynamic_policy: DynamicClusterPolicy,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    dates, closes, opens = _price_lookups(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
    date_index = {day: index for index, day in enumerate(dates)}
    return_maps = _return_maps(data_map)
    features = _price_features(data_map, dynamic_policy.trend_sessions)

    signals_by_day: dict[date, list[Mapping[str, Any]]] = {}
    entries_by_day: dict[date, list[Mapping[str, Any]]] = {}
    exits_by_day: dict[date, list[Mapping[str, Any]]] = {}
    for event in events:
        signals_by_day.setdefault(event["signal_date"], []).append(event)
        entries_by_day.setdefault(event["entry_date"], []).append(event)
        exits_by_day.setdefault(event["exit_date"], []).append(event)
    for rows in signals_by_day.values():
        rows.sort(key=lambda item: item["signal_rank"], reverse=True)

    cash = 1.0
    positions: dict[str, dict[str, Any]] = {}
    reservations: dict[str, dict[str, Any]] = {}
    pending_trims: dict[str, dict[str, Any]] = {}
    nav_values: list[float] = []
    nav_dates: list[date] = []
    allocation_rows: list[dict[str, Any]] = []
    trim_rows: list[dict[str, Any]] = []
    dynamic_trigger_count = 0
    dynamic_trim_order_count = 0
    entry_corr_reduced_count = 0
    entry_corr_blocked_count = 0
    trim_turnover = 0.0
    trim_cost = 0.0

    for day in dates:
        day_i = date_index[day]
        for event in exits_by_day.get(day, []):
            event_id = str(event["event_id"])
            pending_trims.pop(event_id, None)
            position = positions.pop(event_id, None)
            if position is None:
                continue
            price = _finite(event.get("exit_price"))
            if price is None or price <= 0:
                positions[event_id] = position
                continue
            cash += float(position["shares"]) * price

        for event_id, order in list(pending_trims.items()):
            position = positions.get(event_id)
            if position is None:
                pending_trims.pop(event_id, None)
                continue
            code = str(position["code"])
            price = opens.get(code, {}).get(day)
            if price is None or price <= 0:
                continue
            old_shares = float(position["shares"])
            shares = min(old_shares, float(order["shares_to_sell"]))
            if shares <= 0:
                pending_trims.pop(event_id, None)
                continue
            proceeds = shares * price
            cost = proceeds * dynamic_policy.trim_cost_bps / 10_000.0
            cash += proceeds - cost
            new_shares = max(0.0, old_shares - shares)
            position["shares"] = new_shares
            if old_shares > 0:
                position["initial_risk_dollars"] = float(position.get("initial_risk_dollars") or 0.0) * (new_shares / old_shares)
            position["last_trim_index"] = day_i
            trim_turnover += proceeds
            trim_cost += cost
            pending_trims.pop(event_id, None)
            trim_rows.append({
                "policy": dynamic_policy.name, "event_id": event_id, "code": code,
                "stock_name": position.get("stock_name"), "reason": order["reason"],
                "decision_date": order["decision_date"], "execution_date": day,
                "execution_open": round(price, 6), "shares_sold": shares,
                "gross_proceeds": proceeds, "friction_cost": cost,
                "cluster_codes": order.get("cluster_codes"),
                "cluster_weight_before": order.get("cluster_weight_before"),
                "member_weight_before": order.get("member_weight_before"),
                "member_return_20d_pct": order.get("member_return_20d_pct"),
                "shares_frozen_before_open": True, "risk_budget_released_proportionally": True,
            })
            if new_shares <= 1e-12:
                positions.pop(event_id, None)

        for event in entries_by_day.get(day, []):
            event_id = str(event["event_id"])
            reservation = reservations.pop(event_id, None)
            if reservation is None:
                continue
            price = _finite(event.get("entry_price"))
            if price is None or price <= 0:
                continue
            stop = _finite(event.get("risk_geometry", {}).get("stop_price"))
            if stop is not None and price <= stop:
                continue
            amount = min(cash, float(reservation["planned_dollars"]))
            if amount <= 0:
                continue
            shares = amount / price
            cash -= amount
            positions[event_id] = {
                "event_id": event_id, "code": event["code"], "stock_name": event["stock_name"],
                "shares": shares, "entry_price": price, "stop_price": stop,
                "initial_risk_dollars": shares * max(0.0, price - stop) if stop is not None and stop > 0 else 0.0,
                "entry_index": day_i, "last_trim_index": -10**9, "last_close": price,
            }

        for position in positions.values():
            close = closes.get(str(position["code"]), {}).get(day)
            if close is not None:
                position["last_close"] = close

        equity, event_weights = _weight_snapshot(positions, cash=cash, day=day, closes=closes)
        code_weights: dict[str, float] = {}
        code_events: dict[str, list[str]] = {}
        for event_id, weight in event_weights.items():
            position = positions.get(event_id)
            if position is None:
                continue
            code = str(position["code"])
            code_weights[code] = code_weights.get(code, 0.0) + float(weight)
            code_events.setdefault(code, []).append(event_id)

        # Ordinary single-name concentration trim remains available.
        if equity > 0:
            for event_id, weight in sorted(event_weights.items(), key=lambda item: item[1], reverse=True):
                if event_id in pending_trims or weight <= concentration_policy.trigger_fraction:
                    continue
                position = positions.get(event_id)
                if position is None:
                    continue
                entry_i = int(position.get("entry_index", day_i))
                last_trim_i = int(position.get("last_trim_index", -10**9))
                if day_i - entry_i < concentration_policy.min_holding_sessions or day_i - last_trim_i < concentration_policy.cooldown_sessions:
                    continue
                close = closes.get(str(position["code"]), {}).get(day)
                if close is None or close <= 0:
                    continue
                shares_to_sell = max(0.0, (float(position["shares"]) * close - equity * concentration_policy.target_fraction) / close)
                if shares_to_sell > 1e-12:
                    pending_trims[event_id] = {
                        "decision_date": day, "shares_to_sell": min(shares_to_sell, float(position["shares"])),
                        "reason": "CONCENTRATION_CAP", "member_weight_before": weight,
                    }

        # Dynamic multi-name cluster trim. Pending single-name trims are not
        # counted as already freed capacity: this intentionally errs conservative.
        clusters = dynamic_clusters(
            list(code_weights), as_of=day, return_maps=return_maps,
            price_features=features, policy=dynamic_policy,
        )
        for cluster in clusters:
            cluster_weight = sum(code_weights.get(code, 0.0) for code in cluster["codes"])
            if not cluster["stressed"] or cluster_weight <= dynamic_policy.trigger_cluster_fraction:
                continue
            dynamic_trigger_count += 1
            excess = cluster_weight - dynamic_policy.target_cluster_fraction
            if excess <= 0:
                continue
            candidates: list[tuple[float, bool, float, str, str]] = []
            for code in cluster["codes"]:
                feature = cluster["member_features"].get(code, {})
                ret20 = _finite(feature.get("return_20d_pct"))
                weak_ret = ret20 if ret20 is not None else 999.0
                below = bool(feature.get("below_ma"))
                for event_id in code_events.get(code, []):
                    position = positions.get(event_id)
                    if position is None or event_id in pending_trims:
                        continue
                    entry_i = int(position.get("entry_index", day_i))
                    last_trim_i = int(position.get("last_trim_index", -10**9))
                    if day_i - entry_i < dynamic_policy.minimum_holding_sessions or day_i - last_trim_i < dynamic_policy.cooldown_sessions:
                        continue
                    # below-MA members first, then weakest 20d return, then larger weight.
                    candidates.append((0.0 if below else 1.0, weak_ret, -event_weights.get(event_id, 0.0), code, event_id))
            for _, ret20, _, code, event_id in sorted(candidates):
                if excess <= 1e-10:
                    break
                position = positions[event_id]
                member_weight = float(event_weights.get(event_id, 0.0))
                reducible = max(0.0, member_weight - dynamic_policy.minimum_name_fraction_after_trim)
                reduce_fraction = min(excess, reducible)
                close = closes.get(code, {}).get(day)
                if reduce_fraction <= 0 or close is None or close <= 0:
                    continue
                shares_to_sell = min(float(position["shares"]), equity * reduce_fraction / close)
                if shares_to_sell <= 1e-12:
                    continue
                pending_trims[event_id] = {
                    "decision_date": day, "shares_to_sell": shares_to_sell,
                    "reason": "DYNAMIC_CORRELATED_CLUSTER_STRESS",
                    "cluster_codes": ";".join(cluster["codes"]),
                    "cluster_weight_before": round(cluster_weight, 8),
                    "member_weight_before": round(member_weight, 8),
                    "member_return_20d_pct": None if ret20 == 999.0 else ret20,
                }
                dynamic_trim_order_count += 1
                excess -= reduce_fraction

        snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        equity = float(snapshot["equity"])
        if equity <= 0:
            break
        reserved_fraction = 0.0
        reserved_open_risk_pct = 0.0
        reserved_candidates: list[dict[str, Any]] = []
        current_code_weights = code_weights
        for event in signals_by_day.get(day, []):
            event_id = str(event["event_id"])
            code = str(event["code"])
            stop_distance = _finite(dict(event.get("risk_geometry") or {}).get("stop_distance_pct"))
            current = _portfolio_snapshot(
                positions, cash=cash, day=day, closes=closes,
                reserved_fraction=reserved_fraction, reserved_open_risk_pct=reserved_open_risk_pct,
            )
            base_fraction = 0.0
            status = "BLOCKED"
            if stop_distance is not None and stop_distance > 0:
                base_fraction = position_fraction(
                    stop_distance_pct=stop_distance, portfolio_drawdown_pct=0.0,
                    current_name_fraction=0.0, current_industry_fraction=0.0,
                    current_total_fraction=float(current["gross_fraction"]),
                    current_open_risk_pct=float(current["open_risk_pct"]),
                    policy=_policy_to_risk_policy(entry_policy),
                )
                status = "ALLOCATED" if base_fraction > 0 else "NO_RISK_CAPACITY"
            else:
                status = "RISK_GEOMETRY_UNAVAILABLE"
            corr_fraction, corr_audit, missing_pairs = correlated_fraction_for_candidate(
                code, as_of=day, current_code_weights=current_code_weights,
                reserved_candidates=reserved_candidates, return_maps=return_maps,
                policy=entry_correlation_policy,
            )
            room = max(0.0, entry_correlation_policy.max_cluster_fraction - corr_fraction)
            fraction = min(float(base_fraction), room)
            if base_fraction > 0 and fraction <= 0:
                status = "CORRELATION_CLUSTER_CAP"
                entry_corr_blocked_count += 1
            elif 0 < fraction + 1e-12 < base_fraction:
                status = "ALLOCATED_CORRELATION_REDUCED"
                entry_corr_reduced_count += 1
            fraction = round(max(0.0, fraction), 8)
            planned = equity * fraction
            if planned > cash - equity * reserved_fraction:
                planned = max(0.0, cash - equity * reserved_fraction)
                fraction = planned / equity if equity > 0 else 0.0
            if fraction > 0 and planned > 0:
                reservations[event_id] = {"planned_fraction": fraction, "planned_dollars": planned}
                reserved_fraction += fraction
                if stop_distance is not None:
                    reserved_open_risk_pct += fraction * stop_distance
                reserved_candidates.append({"code": code, "fraction": fraction})
            allocation_rows.append({
                "policy": dynamic_policy.name, "event_id": event_id, "signal_date": day,
                "entry_date": event["entry_date"], "code": code, "stock_name": event["stock_name"],
                "status": status, "base_allocated_pct_before_correlation": round(float(base_fraction) * 100.0, 4),
                "allocated_pct": round(fraction * 100.0, 4), "correlated_pct_before": round(corr_fraction * 100.0, 4),
                "correlation_pair_count": len(corr_audit), "correlation_missing_pair_count": missing_pairs,
            })

        end = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        nav_dates.append(day)
        nav_values.append(float(end["equity"]))

    curve = pd.Series(nav_values, index=pd.Index(nav_dates, name="date"), dtype=float)
    return curve, allocation_rows, trim_rows, {
        "dynamic_cluster_trigger_count": dynamic_trigger_count,
        "dynamic_cluster_trim_order_count": dynamic_trim_order_count,
        "entry_correlation_reduced_count": entry_corr_reduced_count,
        "entry_correlation_blocked_count": entry_corr_blocked_count,
        "trim_count": len(trim_rows), "trim_turnover_dollars": round(trim_turnover, 8),
        "trim_friction_cost_dollars": round(trim_cost, 8), "ending_cash": round(cash, 8),
        "ending_open_position_count": len(positions),
    }


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fallback_fields: Sequence[str]) -> None:
    values = [dict(row) for row in rows]
    fields = sorted({key for row in values for key in row}) if values else list(fallback_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(values)


def run_suite(
    cases: Sequence[FamousCase], *, start_date: date, end_date: date,
    output_dir: Path, cache_dir: Path, board_rules_file: Path,
    evaluation_stride: int = 5, cost_bps_per_side: float = 15.0,
    policies: Sequence[DynamicClusterPolicy] = POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    events, data_map, geometry_audit = collect_frozen_events(
        ready, start_date=start_date, end_date=end_date, evaluation_stride=evaluation_stride,
        cost_bps_per_side=cost_bps_per_side, board_rules=load_board_rules(board_rules_file),
    )
    naive = PortfolioConstructionPolicy(
        name="naive_fixed20_fullgross", mode="fixed", fixed_entry_fraction=0.20,
        max_total_gross_fraction=1.0, max_total_open_risk_pct=100.0,
    )
    naive_curve, _, _ = replay_single_account(events, data_map, start_date=start_date, end_date=end_date, policy=naive)
    naive_metrics = _metrics(naive.name, naive_curve)
    comparison: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    trims: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for policy in policies:
        curve, alloc, trim, audit = replay_with_dynamic_cluster_guard(
            events, data_map, start_date=start_date, end_date=end_date,
            entry_policy=BASE_ENTRY_POLICY, concentration_policy=BASE_CONCENTRATION_GUARD,
            entry_correlation_policy=BASE_ENTRY_CORRELATION_POLICY, dynamic_policy=policy,
        )
        metric = _metrics(policy.name, curve)
        evaluation = evaluate_candidate(naive_metrics, metric)
        row = {
            **asdict(policy), "cagr_pct": metric.cagr_pct, "max_drawdown_pct": metric.max_drawdown_pct,
            "calmar_ratio": evaluation.calmar_ratio, "cagr_retention_vs_naive_pct": evaluation.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": evaluation.drawdown_improvement_pct,
            "accepted": evaluation.accepted, "reasons": ";".join(evaluation.reasons), **audit,
        }
        comparison.append(row); allocations.extend(alloc); trims.extend(trim)
        if evaluation.accepted and (selected is None or row["calmar_ratio"] > selected["calmar_ratio"]):
            selected = row
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "dynamic_cluster_comparison.csv", comparison, ["name"])
    _write_csv(output_dir / "dynamic_cluster_allocations.csv", allocations, ["policy", "event_id"])
    _write_csv(output_dir / "dynamic_cluster_trims.csv", trims, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    summary = {
        "rule_version": RULE_VERSION, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready), "frozen_event_count": len(events), "risk_geometry_audit": geometry_audit,
        "naive_metrics": asdict(naive_metrics), "entry_risk_policy": asdict(BASE_ENTRY_POLICY),
        "entry_correlation_policy": asdict(BASE_ENTRY_CORRELATION_POLICY),
        "concentration_policy": asdict(BASE_CONCENTRATION_GUARD), "selected_policy": selected,
        "risk_gate_passed_on_diagnostic_panel": selected is not None,
        "stock_entry_exit_signal_set_frozen": True, "dynamic_cluster_uses_only_history_through_close": True,
        "dynamic_cluster_requires_weight_and_stress": True, "weakest_members_trimmed_first": True,
        "trim_decision_after_close_for_next_open": True, "trim_shares_frozen_before_next_open": True,
        "partial_trim_releases_open_risk_budget": True, "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True, "production_deployment_allowed": False,
        "no_auto_trade": True, "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_dynamic_cluster_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = ["# Historical Dynamic Correlation Cluster Guard", "",
             f"- period: {start_date} to {end_date}", f"- frozen events: {len(events)}",
             f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
             "- dynamic clusters require excessive aggregate weight plus objective cluster stress",
             "- weakest members are trimmed first; decisions execute next observed open",
             "- deployment remains blocked pending survivorship-aware All-A validation", "", "## Comparison"]
    for row in comparison:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row['calmar_ratio']} | retention={row['cagr_retention_vs_naive_pct']}% | "
            f"DD improvement={row['drawdown_improvement_vs_naive_pct']}% | "
            f"cluster triggers={row['dynamic_cluster_trigger_count']} | trim orders={row['dynamic_cluster_trim_order_count']} | accepted={row['accepted']}"
        )
    (output_dir / "historical_dynamic_cluster_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
