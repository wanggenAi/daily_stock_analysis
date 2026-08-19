"""Low-frequency winner-concentration trim overlay for the single-account replay.

This diagnostic keeps the same frozen hard-logic/reverse-valuation entry and exit
opportunities and the same point-in-time entry risk geometry used by
``historical_portfolio_risk_budget``.  It adds one narrow portfolio-control
mechanism only: a profitable position that drifts above a high single-name
weight may be trimmed down to a still-large target weight after a cooldown.

The purpose is to test whether portfolio drawdown can be reduced without
mechanically selling ordinary volatility or preventing long-duration winners
from compounding.  The named famous-stock panel remains ex-post selected and is
not a production authorization.
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

from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    StrategyMetrics,
    cagr_pct,
    max_drawdown_pct,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    fetch_case_data,
    load_cases,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    _finite,
    _policy_to_risk_policy,
    _portfolio_snapshot,
    _price_lookup,
    collect_frozen_events,
)
from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import position_fraction

RULE_VERSION = "winner_concentration_trim_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


@dataclass(frozen=True)
class WinnerTrimPolicy:
    name: str
    trigger_weight_fraction: float
    target_weight_fraction: float
    minimum_gain_pct: float
    cooldown_sessions: int
    rebalance_cost_bps: float = 15.0


BASE_ENTRY_POLICY = PortfolioConstructionPolicy(
    name="risk075_open4",
    risk_per_trade_pct=0.75,
    max_single_name_fraction=0.20,
    max_total_gross_fraction=0.90,
    max_total_open_risk_pct=4.0,
)

TRIM_GRID: tuple[WinnerTrimPolicy, ...] = (
    WinnerTrimPolicy("no_trim", 9.0, 9.0, 9_999.0, 10_000),
    WinnerTrimPolicy("trim30_to22_gain50_cd60", 0.30, 0.22, 50.0, 60),
    WinnerTrimPolicy("trim35_to25_gain75_cd60", 0.35, 0.25, 75.0, 60),
    WinnerTrimPolicy("trim40_to30_gain100_cd90", 0.40, 0.30, 100.0, 90),
    WinnerTrimPolicy("trim45_to32_gain100_cd90", 0.45, 0.32, 100.0, 90),
)


def _metrics(name: str, curve: pd.Series) -> StrategyMetrics:
    if curve.empty:
        return StrategyMetrics(name=name, cagr_pct=0.0, max_drawdown_pct=100.0)
    years = max(1.0 / 365.25, (curve.index[-1] - curve.index[0]).days / 365.25)
    growth = cagr_pct(float(curve.iloc[0]), float(curve.iloc[-1]), years) or 0.0
    mdd = max_drawdown_pct(curve.tolist()) or 0.0
    return StrategyMetrics(name=name, cagr_pct=round(growth, 6), max_drawdown_pct=round(float(mdd), 6))


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    values = [dict(row) for row in rows]
    names = sorted({key for row in values for key in row}) if values else list(fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def replay_with_winner_trim(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, Any],
    *,
    start_date: date,
    end_date: date,
    trim_policy: WinnerTrimPolicy,
    entry_policy: PortfolioConstructionPolicy = BASE_ENTRY_POLICY,
) -> tuple[pd.Series, list[dict[str, Any]], dict[str, Any]]:
    dates, closes = _price_lookup(data_map)
    dates = [day for day in dates if start_date <= day <= end_date]
    day_index = {day: index for index, day in enumerate(dates)}

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
    nav_dates: list[date] = []
    nav_values: list[float] = []
    trim_rows: list[dict[str, Any]] = []
    blocked_counts: dict[str, int] = {}
    total_trim_turnover = 0.0

    for day in dates:
        # Frozen baseline exits occur first.  Any earlier trim changes only the
        # remaining share count; the exit date/reason is never changed.
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

        # Execute allocations sized at the prior signal close.
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
                "entry_cost_dollars": amount,
                "stop_price": stop,
                "initial_risk_dollars": risk_dollars,
                "entry_date": day,
                "last_close": entry_price,
                "last_trim_session": -10_000,
                "trim_count": 0,
            }

        # Current close is the only mark used for same-day concentration checks.
        for position in positions.values():
            close = closes.get(str(position["code"]), {}).get(day)
            if close is not None:
                position["last_close"] = close

        snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        equity = float(snapshot["equity"])
        if equity <= 0:
            break

        # Low-frequency concentration trim.  Decisions are after close and are
        # charged explicit one-sided sale friction at that close.  This overlay
        # does not change the frozen final exit date or any entry signal.
        session = day_index[day]
        candidates: list[tuple[float, str]] = []
        for event_id, position in positions.items():
            mark = float(position["shares"]) * float(position["last_close"])
            weight = mark / equity if equity > 0 else 0.0
            gain_pct = (float(position["last_close"]) / float(position["entry_price"]) - 1.0) * 100.0
            cooldown_ok = session - int(position.get("last_trim_session", -10_000)) >= trim_policy.cooldown_sessions
            if (
                weight > trim_policy.trigger_weight_fraction
                and gain_pct >= trim_policy.minimum_gain_pct
                and cooldown_ok
            ):
                candidates.append((weight, event_id))

        # Largest concentration is handled first; recompute equity/weight after
        # each trim so simultaneous winners cannot over-trim the account.
        for _, event_id in sorted(candidates, reverse=True):
            position = positions.get(event_id)
            if position is None:
                continue
            snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
            equity = float(snapshot["equity"])
            price = float(position["last_close"])
            mark = float(position["shares"]) * price
            weight_before = mark / equity if equity > 0 else 0.0
            gain_pct = (price / float(position["entry_price"]) - 1.0) * 100.0
            if weight_before <= trim_policy.trigger_weight_fraction or gain_pct < trim_policy.minimum_gain_pct:
                continue
            target_dollars = equity * trim_policy.target_weight_fraction
            sell_dollars_gross = max(0.0, mark - target_dollars)
            if sell_dollars_gross <= 0:
                continue
            sell_shares = min(float(position["shares"]), sell_dollars_gross / price)
            gross_proceeds = sell_shares * price
            friction = gross_proceeds * trim_policy.rebalance_cost_bps / 10_000.0
            net_proceeds = gross_proceeds - friction
            if sell_shares <= 0 or net_proceeds <= 0:
                continue
            position["shares"] = float(position["shares"]) - sell_shares
            position["last_trim_session"] = session
            position["trim_count"] = int(position.get("trim_count", 0)) + 1
            cash += net_proceeds
            total_trim_turnover += gross_proceeds
            after_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
            after_mark = float(position["shares"]) * price
            weight_after = after_mark / float(after_snapshot["equity"])
            trim_rows.append({
                "policy": trim_policy.name,
                "date": day,
                "event_id": event_id,
                "code": position["code"],
                "stock_name": position["stock_name"],
                "entry_date": position["entry_date"],
                "entry_price": round(float(position["entry_price"]), 6),
                "mark_price": round(price, 6),
                "gain_pct": round(gain_pct, 4),
                "weight_before_pct": round(weight_before * 100.0, 4),
                "weight_after_pct": round(weight_after * 100.0, 4),
                "gross_trim_fraction_of_equity": round(gross_proceeds / equity, 8),
                "gross_trim_dollars_nav1": round(gross_proceeds, 8),
                "friction_dollars_nav1": round(friction, 10),
                "trim_count_for_position": position["trim_count"],
            })

        # Size future entries only after the trim decision, so released cash can
        # be used next session without using that next session's opening price.
        snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        equity = float(snapshot["equity"])
        reserved_fraction = 0.0
        reserved_open_risk_pct = 0.0
        for event in signals_by_day.get(day, []):
            event_id = str(event["event_id"])
            geometry = dict(event.get("risk_geometry") or {})
            stop_distance = _finite(geometry.get("stop_distance_pct"))
            if stop_distance is None or stop_distance <= 0:
                blocked_counts["RISK_GEOMETRY_UNAVAILABLE"] = blocked_counts.get("RISK_GEOMETRY_UNAVAILABLE", 0) + 1
                continue
            current = _portfolio_snapshot(
                positions,
                cash=cash,
                day=day,
                closes=closes,
                reserved_fraction=reserved_fraction,
                reserved_open_risk_pct=reserved_open_risk_pct,
            )
            fraction = position_fraction(
                stop_distance_pct=stop_distance,
                portfolio_drawdown_pct=0.0,
                current_name_fraction=0.0,
                current_industry_fraction=0.0,
                current_total_fraction=float(current["gross_fraction"]),
                current_open_risk_pct=float(current["open_risk_pct"]),
                policy=_policy_to_risk_policy(entry_policy),
            )
            fraction = round(max(0.0, float(fraction)), 8)
            planned_dollars = equity * fraction
            available = max(0.0, cash - equity * reserved_fraction)
            if planned_dollars > available:
                planned_dollars = available
                fraction = planned_dollars / equity if equity > 0 else 0.0
            if fraction > 0 and planned_dollars > 0:
                reservations[event_id] = {
                    "planned_fraction": fraction,
                    "planned_dollars": planned_dollars,
                }
                reserved_fraction += fraction
                reserved_open_risk_pct += fraction * stop_distance
            else:
                blocked_counts["NO_RISK_CAPACITY"] = blocked_counts.get("NO_RISK_CAPACITY", 0) + 1

        end_snapshot = _portfolio_snapshot(positions, cash=cash, day=day, closes=closes)
        nav_dates.append(day)
        nav_values.append(float(end_snapshot["equity"]))

    curve = pd.Series(nav_values, index=pd.Index(nav_dates, name="date"), dtype=float)
    audit = {
        "trim_event_count": len(trim_rows),
        "trimmed_position_count": len({row["event_id"] for row in trim_rows}),
        "trim_turnover_nav1": round(total_trim_turnover, 8),
        "blocked_reason_counts": blocked_counts,
        "ending_cash": round(cash, 8),
        "ending_open_position_count": len(positions),
    }
    return curve, trim_rows, audit


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
    policies: Sequence[WinnerTrimPolicy] = TRIM_GRID,
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

    curves: dict[str, pd.Series] = {}
    metrics_by_name: dict[str, StrategyMetrics] = {}
    audits: dict[str, dict[str, Any]] = {}
    all_trims: list[dict[str, Any]] = []
    comparison: list[dict[str, Any]] = []

    for policy in policies:
        curve, trims, audit = replay_with_winner_trim(
            events,
            data_map,
            start_date=start_date,
            end_date=end_date,
            trim_policy=policy,
        )
        curves[policy.name] = curve
        metrics_by_name[policy.name] = _metrics(policy.name, curve)
        audits[policy.name] = audit
        all_trims.extend(trims)

    baseline = metrics_by_name["no_trim"]
    for policy in policies:
        metrics = metrics_by_name[policy.name]
        dd_improvement = (
            (baseline.max_drawdown_pct - metrics.max_drawdown_pct) / baseline.max_drawdown_pct * 100.0
            if baseline.max_drawdown_pct > 0 else 0.0
        )
        retention = metrics.cagr_pct / baseline.cagr_pct * 100.0 if baseline.cagr_pct > 0 else 0.0
        calmar = metrics.cagr_pct / metrics.max_drawdown_pct if metrics.max_drawdown_pct > 0 else None
        accepted = (
            policy.name != "no_trim"
            and retention >= 70.0
            and (
                metrics.max_drawdown_pct <= 20.0
                or dd_improvement >= 20.0
            )
        )
        comparison.append({
            **asdict(policy),
            "cagr_pct": metrics.cagr_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "calmar_ratio": calmar,
            "cagr_retention_pct": round(retention, 6),
            "drawdown_improvement_pct": round(dd_improvement, 6),
            "accepted": accepted,
            **audits[policy.name],
        })

    candidates = [row for row in comparison if row["name"] != "no_trim"]
    accepted = [row for row in candidates if row["accepted"]]
    selected = max(
        accepted or candidates,
        key=lambda row: (
            bool(row["accepted"]),
            float(row.get("calmar_ratio") or 0.0),
            float(row.get("cagr_retention_pct") or 0.0),
        ),
    ) if candidates else None

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "winner_trim_comparison.csv", comparison, ["name"])
    _write_csv(output_dir / "winner_trim_events.csv", all_trims, ["policy", "date", "code"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    if selected:
        selected_curve = curves[str(selected["name"])]
        selected_curve.rename("nav").to_csv(output_dir / "selected_winner_trim_nav.csv")

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "entry_policy": asdict(BASE_ENTRY_POLICY),
        "baseline_metrics": asdict(baseline),
        "selected_policy": selected,
        "risk_gate_passed_on_diagnostic_panel": bool(selected and selected.get("accepted")),
        "entry_signal_set_frozen": True,
        "exit_signal_set_frozen": True,
        "trim_only_profitable_concentration": True,
        "trim_decision_after_close": True,
        "trim_rebalance_cost_charged": True,
        "ordinary_volatility_exit_added": False,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "winner_concentration_trim_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Winner Concentration Trim Diagnostic",
        "",
        f"- period: {start_date} to {end_date}",
        f"- frozen events: {len(events)}",
        f"- geometry coverage: {geometry_audit['risk_geometry_coverage_ratio'] * 100:.2f}%",
        f"- no-trim CAGR: {baseline.cagr_pct:.4f}%",
        f"- no-trim MDD: {baseline.max_drawdown_pct:.4f}%",
        "- entries/exits remain frozen; only profitable concentration trims are added",
        "- all trims are close-known, low-frequency and charged explicit friction",
        "- production remains blocked pending survivorship-aware All-A validation",
        "",
        "## Comparison",
    ]
    for row in comparison:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row['cagr_retention_pct']}% | "
            f"DD improvement={row['drawdown_improvement_pct']}% | trims={row['trim_event_count']} | "
            f"accepted={row['accepted']}"
        )
    (output_dir / "winner_concentration_trim.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
