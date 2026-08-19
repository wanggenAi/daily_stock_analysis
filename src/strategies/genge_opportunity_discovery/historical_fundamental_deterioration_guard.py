"""Backtest point-in-time fundamental deterioration exits.

Candidate warnings come from the disclosure-level audit.  This module turns a
warning into an actual exit only after the financial statement is visible.  A
warning formed after the close executes at the next observed session open with
the same sell-side friction as the historical strategy.  Optional price
confirmation uses only the warning-date close and trailing MA60.

The frozen entry event set is unchanged.  The original strategy exit remains in
place unless a qualifying deterioration exit executes earlier.  Portfolio
construction uses the same entry risk budget and low-frequency concentration
cap, with partial trims releasing frozen open-risk dollars proportionally.

This is an ex-post named-stock diagnostic.  No result can authorize production
or automatic trading; survivorship-aware All-A walk-forward remains required.
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
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import evaluate_candidate
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    HistoricalCompanyData,
    _finite,
    fetch_case_data,
    load_cases,
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
)
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import (
    BASE_ENTRY_POLICY,
    ConcentrationGuardPolicy,
)
from src.strategies.genge_opportunity_discovery.historical_fundamental_deterioration_audit import (
    WARNING_RULES,
    disclosure_observation,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    _metrics,
    collect_frozen_events,
    replay_single_account,
)
from src.strategies.genge_opportunity_discovery.historical_winner_trend_guard import (
    WinnerTrendPolicy,
    replay_with_winner_trend_guard,
)

RULE_VERSION = "historical_fundamental_deterioration_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

BASE_CONCENTRATION_GUARD = ConcentrationGuardPolicy(
    "conc40_to30_cd20", 0.40, 0.30, 20, 20, 15.0,
)
# Winner-trend functionality is deliberately disabled.  We use this replay
# engine because it contains the corrected proportional release of frozen
# open-risk dollars after a concentration trim.
DISABLED_WINNER_POLICY = WinnerTrendPolicy(
    "disabled_winner_trend_for_corrected_concentration",
    minimum_weight_fraction=0.99,
    minimum_gain_pct=1_000_000.0,
    moving_average_sessions=200,
    break_below_ma_pct=3.0,
    target_fraction=0.98,
    minimum_holding_sessions=20,
    cooldown_sessions=20,
    trim_cost_bps=15.0,
)


@dataclass(frozen=True)
class FundamentalExitPolicy:
    name: str
    warning_rule: str
    require_below_ma60: bool = False

    def __post_init__(self) -> None:
        if self.warning_rule not in WARNING_RULES:
            raise ValueError(f"unsupported warning rule: {self.warning_rule}")


POLICY_GRID: tuple[FundamentalExitPolicy, ...] = (
    FundamentalExitPolicy("fund_review_yoy10", "state_not_pass_and_yoy_le_minus10"),
    FundamentalExitPolicy("fund_review_yoy10_ma60", "state_not_pass_and_yoy_le_minus10", True),
    FundamentalExitPolicy("fund_score_drop15_yoyneg", "score_drop15_and_yoy_negative"),
    FundamentalExitPolicy("fund_score_drop15_yoyneg_ma60", "score_drop15_and_yoy_negative", True),
    FundamentalExitPolicy("fund_score55_yoy20", "score_le55_and_yoy_le_minus20"),
    FundamentalExitPolicy("fund_base_nonpos_yoy10", "base_nonpositive_and_yoy_le_minus10"),
    FundamentalExitPolicy("fund_two_negative_yoy10", "two_consecutive_yoy_le_minus10"),
)


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _price_features(data: HistoricalCompanyData) -> tuple[dict[date, float], dict[date, float], dict[date, float]]:
    history = prepare_price_frame(data.price_df).copy()
    close = pd.to_numeric(history["close"], errors="coerce")
    open_price = pd.to_numeric(history["open"], errors="coerce")
    ma60 = close.rolling(60, min_periods=45).mean()
    closes: dict[date, float] = {}
    opens: dict[date, float] = {}
    ma: dict[date, float] = {}
    for raw_day, raw_close, raw_open, raw_ma in zip(history["date"], close, open_price, ma60):
        day = _date(raw_day)
        if day is None:
            continue
        c = _finite(raw_close)
        o = _finite(raw_open)
        m = _finite(raw_ma)
        if c is not None and c > 0:
            closes[day] = c
        if o is not None and o > 0:
            opens[day] = o
        if m is not None and m > 0:
            ma[day] = m
    return closes, opens, ma


def first_fundamental_exit(
    data: HistoricalCompanyData,
    event: Mapping[str, Any],
    *,
    policy: FundamentalExitPolicy,
    cost_bps_per_side: float,
) -> dict[str, Any] | None:
    signal_date = _date(event.get("signal_date"))
    entry_date = _date(event.get("entry_date"))
    original_exit_date = _date(event.get("exit_date"))
    if signal_date is None or entry_date is None or original_exit_date is None:
        return None

    financial = normalize_financial_point_in_time(data.financial_df)
    if financial.empty:
        return None
    entry_logic = point_in_time_hard_logic(financial, signal_date)
    entry_score = _finite(entry_logic.get("score"))
    closes, opens, ma60 = _price_features(data)
    trading_days = sorted(opens)

    disclosure_dates = sorted({
        value for value in financial["effective_disclosure_date"].tolist()
        if isinstance(value, date) and signal_date < value < original_exit_date
    })
    previous_yoy: float | None = None
    for disclosure_date in disclosure_dates:
        observation = disclosure_observation(
            financial,
            as_of=disclosure_date,
            entry_score=entry_score,
            previous_yoy=previous_yoy,
        )
        yoy = _finite(observation.get("profit_yoy_pct"))
        matched = bool(observation.get(policy.warning_rule))
        current_close = closes.get(disclosure_date)
        current_ma60 = ma60.get(disclosure_date)
        price_confirmed = bool(
            current_close is not None and current_ma60 is not None and current_close < current_ma60
        )
        if matched and (not policy.require_below_ma60 or price_confirmed):
            execution_day = next(
                (
                    day for day in trading_days
                    if disclosure_date < day <= original_exit_date and opens.get(day, 0.0) > 0.0
                ),
                None,
            )
            if execution_day is not None and execution_day > entry_date:
                raw_open = opens[execution_day]
                exit_price = raw_open * (1.0 - max(0.0, cost_bps_per_side) / 10_000.0)
                return {
                    "policy": policy.name,
                    "warning_rule": policy.warning_rule,
                    "require_below_ma60": policy.require_below_ma60,
                    "event_id": event.get("event_id"),
                    "code": data.code,
                    "stock_name": data.stock_name,
                    "entry_date": entry_date,
                    "warning_date": disclosure_date,
                    "execution_date": execution_day,
                    "raw_execution_open": round(raw_open, 6),
                    "exit_price_after_friction": round(exit_price, 6),
                    "original_exit_date": original_exit_date,
                    "original_exit_reason": event.get("exit_reason"),
                    "lead_days_before_original_exit": (original_exit_date - execution_day).days,
                    "warning_hard_logic_state": observation.get("hard_logic_state"),
                    "warning_hard_logic_score": observation.get("hard_logic_score"),
                    "warning_profit_yoy_pct": observation.get("profit_yoy_pct"),
                    "warning_supported_growth_base_pct": observation.get("supported_growth_base_pct"),
                    "warning_score_drop_from_entry": observation.get("score_drop_from_entry"),
                    "warning_close": current_close,
                    "warning_ma60": current_ma60,
                    "price_confirmed_below_ma60": price_confirmed,
                    "decision_after_close_for_next_open": True,
                }
        previous_yoy = yoy
    return None


def adjusted_events_for_policy(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    policy: FundamentalExitPolicy,
    cost_bps_per_side: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adjusted: list[dict[str, Any]] = []
    exits: list[dict[str, Any]] = []
    for raw in events:
        event = dict(raw)
        data = data_map.get(str(event.get("code")))
        early = (
            first_fundamental_exit(
                data,
                event,
                policy=policy,
                cost_bps_per_side=cost_bps_per_side,
            )
            if data is not None else None
        )
        if early is not None and early["execution_date"] < event["exit_date"]:
            event["exit_date"] = early["execution_date"]
            event["exit_price"] = early["exit_price_after_friction"]
            event["exit_reason"] = f"SELL_FUNDAMENTAL_DETERIORATION:{policy.warning_rule}"
            event["fundamental_exit"] = early
            exits.append(early)
        adjusted.append(event)
    adjusted.sort(key=lambda item: (item["signal_date"], item["code"], item["event_id"]))
    return adjusted, exits


def _corrected_concentration_replay(
    events: Sequence[Mapping[str, Any]],
    data_map: Mapping[str, HistoricalCompanyData],
    *,
    start_date: date,
    end_date: date,
) -> tuple[pd.Series, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return replay_with_winner_trend_guard(
        events,
        data_map,
        start_date=start_date,
        end_date=end_date,
        entry_policy=BASE_ENTRY_POLICY,
        concentration_policy=BASE_CONCENTRATION_GUARD,
        winner_policy=DISABLED_WINNER_POLICY,
    )


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
    policies: Sequence[FundamentalExitPolicy] = POLICY_GRID,
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
        max_total_gross_fraction=1.0, max_total_open_risk_pct=100.0,
    )
    naive_curve, _, _ = replay_single_account(
        events, data_map, start_date=start_date, end_date=end_date, policy=naive_policy
    )
    naive_metrics = _metrics(naive_policy.name, naive_curve)

    base_curve, _, base_trims, base_audit = _corrected_concentration_replay(
        events, data_map, start_date=start_date, end_date=end_date,
    )
    base_metrics = _metrics("corrected_concentration_base", base_curve)

    comparison_rows: list[dict[str, Any]] = []
    all_early_exits: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    base_eval = evaluate_candidate(naive_metrics, base_metrics)
    comparison_rows.append({
        "name": "corrected_concentration_base", "kind": "baseline",
        "cagr_pct": base_metrics.cagr_pct, "max_drawdown_pct": base_metrics.max_drawdown_pct,
        "calmar_ratio": base_eval.calmar_ratio,
        "cagr_retention_vs_naive_pct": base_eval.cagr_retention_pct,
        "drawdown_improvement_vs_naive_pct": base_eval.drawdown_improvement_pct,
        "accepted": base_eval.accepted, "fundamental_exit_count": 0,
        "concentration_trim_count": len(base_trims), **base_audit,
    })

    for policy in policies:
        adjusted_events, early_exits = adjusted_events_for_policy(
            events, data_map, policy=policy, cost_bps_per_side=cost_bps_per_side,
        )
        curve, _, trims, audit = _corrected_concentration_replay(
            adjusted_events, data_map, start_date=start_date, end_date=end_date,
        )
        metrics = _metrics(policy.name, curve)
        evaluation = evaluate_candidate(naive_metrics, metrics)
        hengrui = [
            row for row in early_exits
            if row.get("code") == "600276" and str(row.get("entry_date")) == "2021-04-28"
        ]
        row = {
            **asdict(policy), "kind": "fundamental_exit",
            "cagr_pct": metrics.cagr_pct, "max_drawdown_pct": metrics.max_drawdown_pct,
            "calmar_ratio": evaluation.calmar_ratio,
            "cagr_retention_vs_naive_pct": evaluation.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": evaluation.drawdown_improvement_pct,
            "accepted": evaluation.accepted, "reasons": ";".join(evaluation.reasons),
            "fundamental_exit_count": len(early_exits),
            "hengrui_2021_exit_count": len(hengrui),
            "hengrui_2021_exit_date": hengrui[0]["execution_date"] if hengrui else None,
            "concentration_trim_count": len(trims), **audit,
        }
        comparison_rows.append(row)
        all_early_exits.extend(early_exits)
        if evaluation.accepted and (
            selected is None or float(row.get("calmar_ratio") or -math.inf) > float(selected.get("calmar_ratio") or -math.inf)
        ):
            selected = row

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "fundamental_guard_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "fundamental_guard_early_exits.csv", all_early_exits, ["policy", "event_id"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready), "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "naive_metrics": asdict(naive_metrics), "corrected_concentration_metrics": asdict(base_metrics),
        "selected_policy": selected, "risk_gate_passed_on_diagnostic_panel": selected is not None,
        "entry_signal_set_frozen": True,
        "original_exit_replaced_only_if_fundamental_exit_is_earlier": True,
        "fundamental_decision_uses_effective_disclosure_date": True,
        "fundamental_exit_executes_next_observed_open": True,
        "optional_ma60_confirmation_uses_warning_date_only": True,
        "partial_concentration_trim_releases_open_risk_budget": True,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_fundamental_deterioration_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Historical Fundamental Deterioration Guard",
        "",
        f"- period: {start_date} to {end_date}", f"- frozen events: {len(events)}",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        f"- corrected concentration base CAGR/MDD: {base_metrics.cagr_pct:.4f}% / {base_metrics.max_drawdown_pct:.4f}%",
        "- warning decisions use effective disclosure date only and execute next observed open",
        "- entry events remain frozen; original exit is replaced only when the confirmed warning exits earlier",
        "- production deployment remains blocked pending survivorship-aware All-A validation",
        "", "## Comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_vs_naive_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_vs_naive_pct')}% | "
            f"fund exits={row.get('fundamental_exit_count', 0)} | Hengrui={row.get('hengrui_2021_exit_date')} | accepted={row.get('accepted')}"
        )
    (output_dir / "historical_fundamental_deterioration_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
