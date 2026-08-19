"""Audit post-entry fundamental deterioration on the historical capture panel.

The purpose of this diagnostic is narrow: determine whether losing trades show
observable deterioration at financial-statement disclosure dates materially
before the existing hard-logic BLOCKED exit, without assuming that every
negative quarter should force an exit.

Every observation is evaluated only on its effective disclosure date. Missing
actual disclosure dates keep the same conservative fallback lags used by the
historical backtest. Trade outcomes are used only *afterward* to compare warning
selectivity; they are never inputs to warning formation.

The named famous-stock panel is ex-post selected. Results are diagnostic only
and cannot authorize production deployment or an automatic sell rule.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    HistoricalCompanyData,
    _finite,
    _growth,
    _prior_same_period,
    _profit,
    fetch_case_data,
    load_cases,
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
    simulate_company,
)

RULE_VERSION = "historical_fundamental_deterioration_audit_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

WARNING_RULES: tuple[str, ...] = (
    "state_not_pass_and_yoy_le_minus10",
    "score_drop15_and_yoy_negative",
    "score_le55_and_yoy_le_minus20",
    "base_nonpositive_and_yoy_le_minus10",
    "two_consecutive_yoy_le_minus10",
)


def _safe_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _latest_visible_row(financial: pd.DataFrame, as_of: date) -> Mapping[str, Any] | None:
    visible = financial[financial["effective_disclosure_date"] <= as_of]
    if visible.empty:
        return None
    return visible.sort_values(["report_date", "effective_disclosure_date"]).iloc[-1].to_dict()


def disclosure_observation(
    financial: pd.DataFrame,
    *,
    as_of: date,
    entry_score: float | None,
    previous_yoy: float | None,
) -> dict[str, Any]:
    logic = point_in_time_hard_logic(financial, as_of)
    latest = _latest_visible_row(financial, as_of)
    latest_report = _safe_date(latest.get("report_date")) if latest else None
    core_profit = _profit(latest) if latest else None
    prior = _prior_same_period(financial[financial["effective_disclosure_date"] <= as_of], latest_report) if latest and latest_report else None
    yoy = _growth(core_profit, _profit(prior) if prior else None)
    score = _finite(logic.get("score"))
    base = _finite(logic.get("supported_growth_base_pct"))
    score_drop = None if score is None or entry_score is None else entry_score - score
    state = str(logic.get("state") or "REVIEW")

    flags = {
        "state_not_pass_and_yoy_le_minus10": bool(state != "PASS" and yoy is not None and yoy <= -10.0),
        "score_drop15_and_yoy_negative": bool(score_drop is not None and score_drop >= 15.0 and yoy is not None and yoy < 0.0),
        "score_le55_and_yoy_le_minus20": bool(score is not None and score <= 55.0 and yoy is not None and yoy <= -20.0),
        "base_nonpositive_and_yoy_le_minus10": bool(base is not None and base <= 0.0 and yoy is not None and yoy <= -10.0),
        "two_consecutive_yoy_le_minus10": bool(previous_yoy is not None and previous_yoy <= -10.0 and yoy is not None and yoy <= -10.0),
    }
    return {
        "as_of": as_of,
        "latest_report_date": latest_report,
        "hard_logic_state": state,
        "hard_logic_score": score,
        "hard_logic_reasons": ";".join(str(item) for item in logic.get("reasons") or []),
        "core_profit": core_profit,
        "prior_same_period_core_profit": _profit(prior) if prior else None,
        "profit_yoy_pct": round(yoy, 6) if yoy is not None else None,
        "supported_growth_base_pct": base,
        "entry_hard_logic_score": entry_score,
        "score_drop_from_entry": round(score_drop, 6) if score_drop is not None else None,
        **flags,
    }


def audit_trade(
    data: HistoricalCompanyData,
    trade: Mapping[str, Any],
    *,
    normalized_financial: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entry_signal = _safe_date(trade.get("entry_signal_date")) or _safe_date(trade.get("entry_date"))
    exit_signal = _safe_date(trade.get("exit_signal_date")) or _safe_date(trade.get("exit_date"))
    entry_date = _safe_date(trade.get("entry_date"))
    exit_date = _safe_date(trade.get("exit_date"))
    if entry_signal is None or exit_signal is None or entry_date is None or exit_date is None:
        return [], {}

    entry_logic = point_in_time_hard_logic(normalized_financial, entry_signal)
    entry_score = _finite(entry_logic.get("score"))
    disclosure_dates = sorted({
        value
        for value in normalized_financial["effective_disclosure_date"].tolist()
        if isinstance(value, date) and entry_signal < value <= exit_signal
    })

    observations: list[dict[str, Any]] = []
    previous_yoy: float | None = None
    first_warning: dict[str, dict[str, Any]] = {}
    trade_id = f"{data.code}:{entry_date.isoformat()}"
    for disclosure_date in disclosure_dates:
        observation = disclosure_observation(
            normalized_financial,
            as_of=disclosure_date,
            entry_score=entry_score,
            previous_yoy=previous_yoy,
        )
        yoy = _finite(observation.get("profit_yoy_pct"))
        row = {
            "trade_id": trade_id,
            "code": data.code,
            "stock_name": data.stock_name,
            "entry_date": entry_date,
            "entry_signal_date": entry_signal,
            "existing_exit_date": exit_date,
            "existing_exit_signal_date": exit_signal,
            "existing_exit_reason": trade.get("exit_reason"),
            "net_return_pct": _finite(trade.get("net_return_pct")),
            "max_drawdown_pct": _finite(trade.get("max_drawdown_pct")),
            "trade_outcome": "LOSS" if (_finite(trade.get("net_return_pct")) or 0.0) < 0.0 else "WIN",
            **observation,
        }
        observations.append(row)
        for rule in WARNING_RULES:
            if bool(row.get(rule)) and rule not in first_warning:
                first_warning[rule] = row
        previous_yoy = yoy

    summary: dict[str, Any] = {
        "trade_id": trade_id,
        "code": data.code,
        "stock_name": data.stock_name,
        "entry_date": entry_date,
        "existing_exit_date": exit_date,
        "existing_exit_reason": trade.get("exit_reason"),
        "net_return_pct": _finite(trade.get("net_return_pct")),
        "max_drawdown_pct": _finite(trade.get("max_drawdown_pct")),
        "trade_outcome": "LOSS" if (_finite(trade.get("net_return_pct")) or 0.0) < 0.0 else "WIN",
        "entry_hard_logic_state": entry_logic.get("state"),
        "entry_hard_logic_score": entry_score,
        "post_entry_disclosure_count": len(disclosure_dates),
    }
    for rule in WARNING_RULES:
        warning = first_warning.get(rule)
        summary[f"{rule}_triggered"] = warning is not None
        summary[f"{rule}_first_date"] = warning.get("as_of") if warning else None
        summary[f"{rule}_lead_days_before_existing_exit"] = (
            (exit_signal - warning["as_of"]).days if warning else None
        )
        summary[f"{rule}_first_score"] = warning.get("hard_logic_score") if warning else None
        summary[f"{rule}_first_yoy_pct"] = warning.get("profit_yoy_pct") if warning else None
    return observations, summary


def _rule_stats(trade_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    losses = [row for row in trade_rows if row.get("trade_outcome") == "LOSS"]
    wins = [row for row in trade_rows if row.get("trade_outcome") == "WIN"]
    rows: list[dict[str, Any]] = []
    for rule in WARNING_RULES:
        loss_hits = [row for row in losses if bool(row.get(f"{rule}_triggered"))]
        win_hits = [row for row in wins if bool(row.get(f"{rule}_triggered"))]
        all_hits = loss_hits + win_hits
        rows.append({
            "rule": rule,
            "loss_trade_count": len(losses),
            "win_trade_count": len(wins),
            "loss_hit_count": len(loss_hits),
            "win_hit_count": len(win_hits),
            "loss_recall_pct": round(len(loss_hits) / len(losses) * 100.0, 6) if losses else None,
            "win_false_positive_pct": round(len(win_hits) / len(wins) * 100.0, 6) if wins else None,
            "warning_precision_for_loss_pct": round(len(loss_hits) / len(all_hits) * 100.0, 6) if all_hits else None,
            "median_lead_days_loss": (
                float(pd.Series([
                    row.get(f"{rule}_lead_days_before_existing_exit")
                    for row in loss_hits
                    if row.get(f"{rule}_lead_days_before_existing_exit") is not None
                ]).median()) if loss_hits else None
            ),
        })
    return rows


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fallback_fields: Sequence[str]) -> None:
    values = [dict(row) for row in rows]
    fields = sorted({key for row in values for key in row}) if values else list(fallback_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def run_audit(
    cases: Sequence[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    evaluation_stride: int = 5,
    cost_bps_per_side: float = 15.0,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    observations: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for case in ready:
        trades, _, _ = simulate_company(
            case,
            start_date=start_date,
            end_date=end_date,
            evaluation_stride=evaluation_stride,
            cost_bps_per_side=cost_bps_per_side,
        )
        financial = normalize_financial_point_in_time(case.financial_df)
        for trade in trades:
            obs, trade_summary = audit_trade(case, trade, normalized_financial=financial)
            observations.extend(obs)
            if trade_summary:
                trade_rows.append(trade_summary)

    stats = _rule_stats(trade_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "fundamental_deterioration_observations.csv", observations, ["trade_id"])
    _write_csv(output_dir / "fundamental_deterioration_trade_summary.csv", trade_rows, ["trade_id"])
    _write_csv(output_dir / "fundamental_deterioration_rule_stats.csv", stats, ["rule"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    hengrui = [row for row in observations if row.get("code") == "600276" and str(row.get("entry_date")) == "2021-04-28"]
    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "trade_count": len(trade_rows),
        "observation_count": len(observations),
        "loss_trade_count": sum(row.get("trade_outcome") == "LOSS" for row in trade_rows),
        "win_trade_count": sum(row.get("trade_outcome") == "WIN" for row in trade_rows),
        "warning_rules": list(WARNING_RULES),
        "hengrui_2021_trade_observation_count": len(hengrui),
        "point_in_time_disclosure_only": True,
        "trade_outcome_not_used_to_form_warning": True,
        "existing_sell_rule_unchanged": True,
        "famous_case_selection_bias_warning": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_fundamental_deterioration_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# Historical Fundamental Deterioration Audit",
        "",
        f"- period: {start_date} to {end_date}",
        f"- trades: {len(trade_rows)} (losses={summary['loss_trade_count']}, wins={summary['win_trade_count']})",
        f"- disclosure observations while held: {len(observations)}",
        "- warning formation uses only information visible at each effective disclosure date",
        "- outcomes are used only for post-hoc selectivity diagnostics",
        "- existing exit policy is not changed by this audit",
        "",
        "## Candidate rule diagnostics",
    ]
    for row in stats:
        lines.append(
            f"- {row['rule']} | loss recall={row['loss_recall_pct']}% | "
            f"win false-positive={row['win_false_positive_pct']}% | "
            f"loss precision={row['warning_precision_for_loss_pct']}% | "
            f"median loss lead={row['median_lead_days_loss']} days"
        )
    (output_dir / "historical_fundamental_deterioration_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--evaluation-stride", type=int, default=5)
    parser.add_argument("--cost-bps-per-side", type=float, default=15.0)
    args = parser.parse_args(argv)
    summary = run_audit(
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
