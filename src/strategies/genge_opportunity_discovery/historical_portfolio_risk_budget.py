"""Single-account historical portfolio replay with point-in-time risk budgets.

The underlying hard-logic + reverse-valuation entry/exit opportunities are
frozen from ``hard_logic_historical_backtest``.  This module changes only
portfolio construction: several individually valid entries compete for one cash
balance and one aggregate risk ledger.

Risk geometry is constructed on the signal date from the same live
``build_price_plan`` machinery used by the All-A production scan.  No future
bar, future drawdown or realized outcome is used to size an entry.  Winners are
not mechanically rebalanced down after they appreciate; their drift merely
consumes capacity for new positions.

The named famous-stock panel is still ex-post selected and therefore diagnostic
only.  It cannot authorize production deployment.  A survivorship-aware
point-in-time All-A portfolio walk-forward remains mandatory.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.all_a_full_scan import (
    BoardRule,
    build_price_plan,
    load_board_rules,
)
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    DEFAULT_DRAWDOWN_POLICY,
    DrawdownRiskPolicy,
    StrategyMetrics,
    cagr_pct,
    evaluate_candidate,
    max_drawdown_pct,
    position_fraction,
    select_drawdown_optimized,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    HistoricalCompanyData,
    fetch_case_data,
    load_cases,
    simulate_company,
)
from src.strategies.genge_opportunity_discovery.shenzhen_full_scan import (
    _atr,
    _support_candidates,
)

RULE_VERSION = "historical_portfolio_risk_budget_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


@dataclass(frozen=True)
class PortfolioConstructionPolicy:
    name: str
    mode: str = "risk_budget"
    fixed_entry_fraction: float = 0.20
    risk_per_trade_pct: float = 1.25
    max_single_name_fraction: float = 0.20
    max_total_gross_fraction: float = 0.90
    max_total_open_risk_pct: float = 6.0


POLICY_GRID: tuple[PortfolioConstructionPolicy, ...] = (
    PortfolioConstructionPolicy(
        name="naive_fixed20_fullgross",
        mode="fixed",
        fixed_entry_fraction=0.20,
        max_total_gross_fraction=1.00,
        max_total_open_risk_pct=100.0,
    ),
    PortfolioConstructionPolicy(
        name="risk075_open4",
        risk_per_trade_pct=0.75,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=4.0,
    ),
    PortfolioConstructionPolicy(
        name="risk100_open5",
        risk_per_trade_pct=1.00,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=5.0,
    ),
    PortfolioConstructionPolicy(
        name="risk125_open6",
        risk_per_trade_pct=1.25,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=6.0,
    ),
    PortfolioConstructionPolicy(
        name="risk150_open7",
        risk_per_trade_pct=1.50,
        max_total_gross_fraction=0.90,
        max_total_open_risk_pct=7.0,
    ),
    PortfolioConstructionPolicy(
        name="risk150_open6_gross85",
        risk_per_trade_pct=1.50,
        max_total_gross_fraction=0.85,
        max_total_open_risk_pct=6.0,
    ),
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def infer_board(code: str) -> str:
    normalized = str(code or "").strip().split(".", 1)[0].zfill(6)
    if normalized.startswith("688"):
        return "STAR"
    if normalized.startswith(("300", "301")):
        return "CHINEXT"
    if normalized.startswith(("600", "601", "603", "605")):
        return "SSE_MAIN"
    return "SZSE_MAIN"


def _board_rule(code: str, rules: Mapping[str, BoardRule]) -> BoardRule:
    board = infer_board(code)
    if board not in rules:
        raise KeyError(f"board rule unavailable: {board}")
    return rules[board]


def _signal_rank(signal: Mapping[str, Any], code: str) -> tuple[float, float, float, float, str]:
    decision_rank = {
        "BUY_DEEP_VALUE": 3.0,
        "BUYABLE": 2.0,
        "BUYABLE_WITH_SUPPORTED_GROWTH": 1.0,
    }.get(str(signal.get("reason") or ""), 0.0)
    logic = _finite(signal.get("hard_logic_score")) or 0.0
    headroom = _finite(signal.get("expectation_headroom_pct")) or -1e9
    pe_percentile = _finite(signal.get("historical_pe_percentile"))
    pe_score = -(pe_percentile if pe_percentile is not None else 1e9)
    return decision_rank, logic, headroom, pe_score, str(code)


def _structural_stop_from_live_components(
    history: pd.DataFrame,
    *,
    reference_entry: float,
) -> float | None:
    """Recover the live pullback stop even when a target/resistance is absent.

    ``build_price_plan`` only publishes a pullback stop after a valid resistance
    target exists.  Position sizing only needs the risk boundary, so the same
    support + ATR formula is reproduced here without consulting future prices.
    """

    prepared = prepare_price_frame(history)
    if prepared.empty or reference_entry <= 0:
        return None
    close = _finite(prepared.iloc[-1].get("close"))
    if close is None or close <= 0:
        return None
    atr14 = _atr(prepared) or max(0.01, close * 0.03)
    supports = _support_candidates(prepared, atr14, close)
    if not supports:
        return None
    support = float(supports[0][0])
    entry_low = support - 0.30 * atr14
    stop = min(entry_low - 0.01, support - 0.75 * atr14)
    return round(stop, 4) if stop > 0 and stop < reference_entry else None


def point_in_time_risk_geometry(
    data: HistoricalCompanyData,
    *,
    signal_date: date,
    reference_entry: float,
    board_rules: Mapping[str, BoardRule],
) -> dict[str, Any]:
    history = prepare_price_frame(data.price_df)
    history = history[history["date"] <= signal_date].copy()
    if history.empty or reference_entry <= 0:
        return {
            "status": "UNAVAILABLE",
            "stop_price": None,
            "stop_distance_pct": None,
            "source": "no_signal_date_history",
        }

    rule = _board_rule(data.code, board_rules)
    plan = build_price_plan(
        {"code": data.code, "stock_name": data.stock_name},
        history,
        rule,
        [],
        adjusted_history=history,
    )
    preferred = str(plan.get("preferred_plan") or "")
    candidates: list[tuple[str, float]] = []
    preferred_stop = _finite(plan.get(f"{preferred}_stop_price")) if preferred else None
    if preferred_stop is not None and 0 < preferred_stop < reference_entry:
        candidates.append((f"live_preferred_{preferred}", preferred_stop))

    structural = _structural_stop_from_live_components(
        history,
        reference_entry=reference_entry,
    )
    if structural is not None:
        candidates.append(("live_support_atr_structural", structural))

    for mode in ("pullback", "breakout"):
        stop = _finite(plan.get(f"{mode}_stop_price"))
        if stop is not None and 0 < stop < reference_entry:
            candidates.append((f"live_{mode}", stop))

    if not candidates:
        return {
            "status": "UNAVAILABLE",
            "stop_price": None,
            "stop_distance_pct": None,
            "source": "no_live_stop_below_reference_entry",
            "preferred_plan": preferred,
        }

    # Prefer the production preferred-plan stop.  Otherwise use the closest
    # valid live-derived boundary below the reference entry.  This is known at
    # signal close and does not use the next opening price.
    preferred_candidates = [item for item in candidates if item[0].startswith("live_preferred_")]
    source, stop = preferred_candidates[0] if preferred_candidates else max(candidates, key=lambda item: item[1])
    distance = (reference_entry - stop) / reference_entry * 100.0
    return {
        "status": "OK",
        "stop_price": round(stop, 4),
        "stop_distance_pct": round(distance, 6),
        "source": source,
        "preferred_plan": preferred,
    }


def collect_frozen_events(
    ready: Sequence[HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
    evaluation_stride: int,
    cost_bps_per_side: float,
    board_rules: Mapping[str, BoardRule],
) -> tuple[list[dict[str, Any]], dict[str, HistoricalCompanyData], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    data_map = {data.code: data for data in ready}
    geometry_ok = 0
    geometry_missing = 0

    for data in ready:
        trades, signals, _ = simulate_company(
            data,
            start_date=start_date,
            end_date=end_date,
            evaluation_stride=evaluation_stride,
            cost_bps_per_side=cost_bps_per_side,
        )
        buy_signals = {
            _day(signal.get("signal_date")): signal
            for signal in signals
            if str(signal.get("signal_action") or "") == "BUY" and _day(signal.get("signal_date")) is not None
        }
        for trade_index, trade in enumerate(trades):
            signal_date = _day(trade.get("entry_signal_date"))
            entry_date = _day(trade.get("entry_date"))
            exit_date = _day(trade.get("exit_date"))
            if signal_date is None or entry_date is None or exit_date is None:
                continue
            signal = dict(buy_signals.get(signal_date, {}))
            reference_entry = _finite(signal.get("current_price"))
            if reference_entry is None or reference_entry <= 0:
                history = prepare_price_frame(data.price_df)
                visible = history[history["date"] <= signal_date]
                reference_entry = _finite(visible.iloc[-1].get("close")) if not visible.empty else None
            geometry = (
                point_in_time_risk_geometry(
                    data,
                    signal_date=signal_date,
                    reference_entry=float(reference_entry),
                    board_rules=board_rules,
                )
                if reference_entry is not None and reference_entry > 0
                else {
                    "status": "UNAVAILABLE",
                    "stop_price": None,
                    "stop_distance_pct": None,
                    "source": "reference_entry_unavailable",
                }
            )
            if geometry.get("status") == "OK":
                geometry_ok += 1
            else:
                geometry_missing += 1
            event_id = f"{data.code}:{trade_index}:{signal_date.isoformat()}"
            events.append(
                {
                    "event_id": event_id,
                    "code": data.code,
                    "stock_name": data.stock_name,
                    "signal_date": signal_date,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": _finite(trade.get("entry_price")),
                    "exit_price": _finite(trade.get("exit_price")),
                    "exit_reason": trade.get("exit_reason"),
                    "signal": signal,
                    "signal_rank": _signal_rank(signal, data.code),
                    "reference_entry": reference_entry,
                    "risk_geometry": geometry,
                }
            )

    events.sort(key=lambda item: (item["signal_date"], tuple(-x if isinstance(x, (int, float)) else x for x in item["signal_rank"][:-1]), item["code"]))
    audit = {
        "event_count": len(events),
        "risk_geometry_ok_count": geometry_ok,
        "risk_geometry_missing_count": geometry_missing,
        "risk_geometry_coverage_ratio": round(geometry_ok / len(events), 6) if events else 0.0,
    }
    return events, data_map, audit


def _price_lookup(data_map: Mapping[str, HistoricalCompanyData]) -> tuple[list[date], dict[str, dict[date, float]]]:
    all_dates: set[date] = set()
    closes: dict[str, dict[date, float]] = {}
    for code, data in data_map.items():
        history = prepare_price_frame(data.price_df)
        mapping: dict[date, float] = {}
        for _, row in history.iterrows():
            day = _day(row.get("date"))
            close = _finite(row.get("close"))
            if day is not None and close is not None and close > 0:
                mapping[day] = close
                all_dates.add(day)
        closes[code] = mapping
    return sorted(all_dates), closes


def _position_mark(
    position: Mapping[str, Any],
    *,
    day: date,
    closes: Mapping[str, Mapping[date, float]],
) -> float:
    code = str(position["code"])
    close = closes.get(code, {}).get(day)
    if close is None:
        close = _finite(position.get("last_close")) or _finite(position.get("entry_price")) or 0.0
    return float(position["shares"]) * float(close)


def _portfolio_snapshot(
    positions: Mapping[str, Mapping[str, Any]],
    *,
    cash: float,
    day: date,
    closes: Mapping[str, Mapping[date, float]],
    reserved_fraction: float = 0.0,
    reserved_open_risk_pct: float = 0.0,
) -> dict[str, float]:
    marks = {code: _position_mark(position, day=day, closes=closes) for code, position in positions.items()}
    equity = cash + sum(marks.values())
    if equity <= 0:
        return {"equity": 0.0, "gross_fraction": 1.0, "open_risk_pct": math.inf}
    gross = sum(marks.values()) / equity + reserved_fraction
    open_risk_dollars = sum(float(position.get("initial_risk_dollars") or 0.0) for position in positions.values())
    open_risk_pct = open_risk_dollars / equity * 100.0 + reserved_open_risk_pct
    return {
        "equity": equity,
        "gross_fraction": gross,
        "open_risk_pct": open_risk_pct,
    }


def _policy_to_risk_policy(policy: PortfolioConstructionPolicy) -> DrawdownRiskPolicy:
    return replace(
        DEFAULT_DRAWDOWN_POLICY,
        risk_per_trade_pct=policy.risk_per_trade_pct,
        max_single_name_fraction=policy.max_single_name_fraction,
        max_total_gross_fraction=policy.max_total_gross_fraction,
        max_total_open_risk_pct=policy.max_total_open_risk_pct,
        # This replay isolates entry-time portfolio construction.  Portfolio-NAV
        # drawdown scaling is tested separately in portfolio_nav_risk_overlay.
        dd_5_exposure_multiplier=1.0,
        dd_10_exposure_multiplier=1.0,
        dd_15_exposure_multiplier=1.0,
        dd_20_exposure_multiplier=1.0,
        hard_max_drawdown_pct=100.0,
    )


def replay_single_account(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
    policy: PortfolioConstructionPolicy,
) -> tuple[pd.Series, list[dict[str, Any]], dict[str, Any]]:
    dates, closes = _price_lookup(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
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
    nav_values: list[float] = []
    nav_dates: list[date] = []
    allocation_rows: list[dict[str, Any]] = []
    blocked_counts: dict[str, int] = {}

    for day in dates:
        # Execute baseline exits first at the frozen next-open price.  If a risk
        # policy never allocated this event, there is simply no position to exit.
        for event in exits_by_day.get(day, []):
            event_id = str(event["event_id"])
            position = positions.pop(event_id, None)
            if position is None:
                continue
            exit_price = _finite(event.get("exit_price"))
            if exit_price is None or exit_price <= 0:
                positions[event_id] = position
                continue
            cash += float(position["shares"]) * exit_price

        # Execute allocations that were sized after the previous signal close.
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
            risk_dollars = 0.0
            if stop is not None and stop > 0:
                risk_dollars = shares * max(0.0, entry_price - stop)
            positions[event_id] = {
                "event_id": event_id,
                "code": event["code"],
                "stock_name": event["stock_name"],
                "shares": shares,
                "entry_price": entry_price,
                "stop_price": stop,
                "initial_risk_dollars": risk_dollars,
                "entry_date": day,
                "last_close": entry_price,
            }

        # Mark positions at the current close before making next-session sizing
        # decisions.  No future open is used here.
        for position in positions.values():
            close = closes.get(str(position["code"]), {}).get(day)
            if close is not None:
                position["last_close"] = close

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
            status = "BLOCKED"
            fraction = 0.0
            reason = ""

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

            if policy.mode == "fixed":
                room = max(0.0, policy.max_total_gross_fraction - current_gross)
                fraction = min(policy.fixed_entry_fraction, room)
                status = "ALLOCATED" if fraction > 0 else "NO_GROSS_CAPACITY"
                reason = "fixed_fraction_baseline"
            elif stop_distance is None or stop_distance <= 0:
                status = "RISK_GEOMETRY_UNAVAILABLE"
                reason = str(geometry.get("source") or "risk_geometry_unavailable")
            else:
                risk_policy = _policy_to_risk_policy(policy)
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
                    "policy": policy.name,
                    "event_id": event_id,
                    "signal_date": day,
                    "entry_date": event["entry_date"],
                    "code": event["code"],
                    "stock_name": event["stock_name"],
                    "status": status,
                    "reason": reason,
                    "allocated_fraction": round(fraction, 8),
                    "allocated_pct": round(fraction * 100.0, 4),
                    "signal_reference_entry": event.get("reference_entry"),
                    "stop_price": geometry.get("stop_price"),
                    "stop_distance_pct": stop_distance,
                    "risk_geometry_source": geometry.get("source"),
                    "gross_fraction_before": round(current_gross, 8),
                    "open_risk_pct_before": round(current_open_risk, 6),
                }
            )

        end_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        nav_dates.append(day)
        nav_values.append(float(end_snapshot["equity"]))

    curve = pd.Series(nav_values, index=pd.Index(nav_dates, name="date"), dtype=float)
    audit = {
        "policy": policy.name,
        "allocated_event_count": sum(float(row.get("allocated_fraction") or 0.0) > 0 for row in allocation_rows),
        "blocked_event_count": sum(float(row.get("allocated_fraction") or 0.0) <= 0 for row in allocation_rows),
        "blocked_reason_counts": blocked_counts,
        "ending_cash": round(cash, 8),
        "ending_open_position_count": len(positions),
    }
    return curve, allocation_rows, audit


def _metrics(name: str, curve: pd.Series) -> StrategyMetrics:
    if curve.empty:
        return StrategyMetrics(name=name, cagr_pct=0.0, max_drawdown_pct=100.0)
    years = max(1.0 / 365.25, (curve.index[-1] - curve.index[0]).days / 365.25)
    growth = cagr_pct(float(curve.iloc[0]), float(curve.iloc[-1]), years) or 0.0
    mdd = max_drawdown_pct(curve.tolist()) or 0.0
    return StrategyMetrics(name=name, cagr_pct=round(growth, 6), max_drawdown_pct=round(float(mdd), 6))


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
    policies: Sequence[PortfolioConstructionPolicy] = POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    board_rules = load_board_rules(board_rules_file)
    events, data_map, geometry_audit = collect_frozen_events(
        ready,
        start_date=start_date,
        end_date=end_date,
        evaluation_stride=evaluation_stride,
        cost_bps_per_side=cost_bps_per_side,
        board_rules=board_rules,
    )

    naive_policy = next(policy for policy in policies if policy.mode == "fixed")
    naive_curve, naive_allocations, naive_audit = replay_single_account(
        events,
        data_map,
        start_date=start_date,
        end_date=end_date,
        policy=naive_policy,
    )
    baseline = _metrics(naive_policy.name, naive_curve)

    comparison_rows: list[dict[str, Any]] = []
    all_allocations = list(naive_allocations)
    audits = {naive_policy.name: naive_audit}
    candidate_metrics: list[StrategyMetrics] = []

    comparison_rows.append(
        {
            **asdict(naive_policy),
            "cagr_pct": baseline.cagr_pct,
            "max_drawdown_pct": baseline.max_drawdown_pct,
            "calmar_ratio": baseline.cagr_pct / baseline.max_drawdown_pct if baseline.max_drawdown_pct > 0 else None,
            "drawdown_improvement_pct": 0.0,
            "cagr_retention_pct": 100.0,
            "accepted": True,
            "deployment_allowed": False,
            **naive_audit,
        }
    )

    for policy in policies:
        if policy.mode == "fixed":
            continue
        curve, allocations, audit = replay_single_account(
            events,
            data_map,
            start_date=start_date,
            end_date=end_date,
            policy=policy,
        )
        metrics = _metrics(policy.name, curve)
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
                "accepted": evaluation.accepted,
                "deployment_allowed": evaluation.deployment_allowed,
                "reasons": ";".join(evaluation.reasons),
                **audit,
            }
        )
        all_allocations.extend(allocations)
        audits[policy.name] = audit

    selected = select_drawdown_optimized(baseline, candidate_metrics)
    selected_policy = next(
        (policy for policy in policies if selected and policy.name == selected.metrics.name),
        None,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "portfolio_policy_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "portfolio_allocations.csv", all_allocations, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    _write_csv(
        output_dir / "risk_geometry_audit.csv",
        [
            {
                "event_id": event["event_id"],
                "code": event["code"],
                "stock_name": event["stock_name"],
                "signal_date": event["signal_date"],
                "reference_entry": event["reference_entry"],
                **dict(event["risk_geometry"]),
            }
            for event in events
        ],
        ["event_id", "code", "status"],
    )

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "baseline_policy": asdict(naive_policy),
        "baseline_metrics": asdict(baseline),
        "selected_policy": asdict(selected_policy) if selected_policy else None,
        "selected_metrics": asdict(selected.metrics) if selected else None,
        "risk_gate_passed_on_diagnostic_panel": bool(selected and selected.accepted),
        "selected_drawdown_improvement_pct": selected.drawdown_improvement_pct if selected else None,
        "selected_cagr_retention_pct": selected.cagr_retention_pct if selected else None,
        "selected_calmar_ratio": selected.calmar_ratio if selected else None,
        "selected_reasons": list(selected.reasons) if selected else ["no_candidate_policy"],
        "single_account_cash_competition": True,
        "entry_signal_set_frozen": True,
        "exit_signal_set_frozen": True,
        "risk_geometry_point_in_time": True,
        "risk_geometry_source_same_as_live_all_a_plan": True,
        "winner_drift_rebalanced_down": False,
        "industry_cap_applied_in_diagnostic_panel": False,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_portfolio_risk_budget_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Historical Single-Account Portfolio Risk Budget",
        "",
        f"- period: {start_date} to {end_date}",
        f"- data-ready cases: {len(ready)}",
        f"- frozen entry events: {len(events)}",
        f"- point-in-time risk geometry coverage: {geometry_audit['risk_geometry_coverage_ratio'] * 100:.2f}%",
        f"- naive fixed-20 CAGR: {baseline.cagr_pct:.4f}%",
        f"- naive fixed-20 MDD: {baseline.max_drawdown_pct:.4f}%",
        "- all candidates compete for one cash/risk ledger",
        "- stock entry/exit events are frozen; only sizing differs",
        "- winners are not mechanically trimmed after appreciation",
        "- industry cap is intentionally omitted on this ex-post panel to avoid current-industry lookahead",
        "- production deployment remains blocked pending survivorship-aware All-A validation",
        "",
        "## Policy comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_pct')}% | allocated={row.get('allocated_event_count')} | "
            f"accepted={row.get('accepted')}"
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
        ]
    (output_dir / "historical_portfolio_risk_budget.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
