"""Point-in-time broad-index risk overlay for the historical single account.

The stock-selection, entry, exit and winner-concentration rules are unchanged.
This module takes the resulting daily NAV and varies only total capital exposure
using broad A-share index information available at each close.  The exposure
chosen after close is used for the next session; no same-day close information
can alter that day's return.  Exposure changes pay explicit turnover friction.

This is a diagnostic on an ex-post famous-stock panel.  It cannot authorize
production deployment.  Survivorship-aware All-A walk-forward validation is
still mandatory before any live use.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import evaluate_candidate
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    fetch_case_data,
    load_cases,
)
from src.strategies.genge_opportunity_discovery.historical_concentration_guard import (
    BASE_ENTRY_POLICY,
    ConcentrationGuardPolicy,
    replay_with_concentration_guard,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy,
    _metrics,
    collect_frozen_events,
    replay_single_account,
)

RULE_VERSION = "historical_systemic_index_guard_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

INDEX_CODES = {
    "上证指数": "sh.000001",
    "深证成指": "sz.399001",
    "创业板指": "sz.399006",
    "科创50": "sh.000688",
}

BASE_CONCENTRATION_GUARD = ConcentrationGuardPolicy(
    "conc40_to30_cd20", trigger_fraction=0.40, target_fraction=0.30,
    min_holding_sessions=20, cooldown_sessions=20, trim_cost_bps=15.0,
)


@dataclass(frozen=True)
class SystemicExposurePolicy:
    name: str
    green_fraction: float = 1.0
    yellow_fraction: float = 0.80
    red_fraction: float = 0.50
    unknown_fraction: float = 0.75
    rebalance_cost_bps: float = 5.0

    def __post_init__(self) -> None:
        values = (self.green_fraction, self.yellow_fraction, self.red_fraction, self.unknown_fraction)
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("exposure fractions must be in [0, 1]")
        if not self.green_fraction >= self.yellow_fraction >= self.red_fraction:
            raise ValueError("require green >= yellow >= red exposure")
        if self.rebalance_cost_bps < 0:
            raise ValueError("rebalance cost must be non-negative")


POLICY_GRID: tuple[SystemicExposurePolicy, ...] = (
    SystemicExposurePolicy("index_soft_85_60", yellow_fraction=0.85, red_fraction=0.60),
    SystemicExposurePolicy("index_balanced_80_50", yellow_fraction=0.80, red_fraction=0.50),
    SystemicExposurePolicy("index_balanced_75_45", yellow_fraction=0.75, red_fraction=0.45),
    SystemicExposurePolicy("index_crisis_only_100_55", yellow_fraction=1.00, red_fraction=0.55),
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fetch_index_histories(
    *,
    start_date: date,
    end_date: date,
    cache_dir: Path,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Fetch broad-index daily bars from BaoStock with transparent local cache."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, pd.DataFrame] = {}
    failures: list[dict[str, Any]] = []
    missing: list[tuple[str, str, Path]] = []
    padded_start = start_date - timedelta(days=240)

    for name, code in INDEX_CODES.items():
        path = cache_dir / f"{code.replace('.', '_')}.csv"
        if path.exists():
            try:
                frame = pd.read_csv(path)
                prepared = prepare_price_frame(frame)
                if not prepared.empty:
                    last = prepared.iloc[-1]["date"]
                    if isinstance(last, date) and last >= end_date - timedelta(days=7):
                        result[name] = prepared
                        continue
            except Exception:
                pass
        missing.append((name, code, path))

    if not missing:
        return result, failures

    try:
        import baostock as bs
    except Exception as exc:
        for name, code, _ in missing:
            failures.append({"name": name, "code": code, "reason": f"baostock_import:{type(exc).__name__}"})
        return result, failures

    login = bs.login()
    if str(getattr(login, "error_code", "")) != "0":
        for name, code, _ in missing:
            failures.append({"name": name, "code": code, "reason": f"baostock_login:{getattr(login, 'error_msg', '')}"})
        return result, failures
    try:
        for name, code, path in missing:
            try:
                rs = bs.query_history_k_data_plus(
                    code,
                    "date,code,open,high,low,close,volume,amount",
                    start_date=padded_start.isoformat(),
                    end_date=end_date.isoformat(),
                    frequency="d",
                    adjustflag="3",
                )
                rows: list[list[str]] = []
                while getattr(rs, "error_code", "1") == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if getattr(rs, "error_code", "1") != "0" or not rows:
                    failures.append({"name": name, "code": code, "reason": f"baostock_query:{getattr(rs, 'error_msg', '') or 'empty'}"})
                    continue
                frame = pd.DataFrame(rows, columns=rs.fields)
                for column in ("open", "high", "low", "close", "volume", "amount"):
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")
                prepared = prepare_price_frame(frame)
                if prepared.empty:
                    failures.append({"name": name, "code": code, "reason": "prepared_history_empty"})
                    continue
                frame.to_csv(path, index=False)
                result[name] = prepared
            except Exception as exc:
                failures.append({"name": name, "code": code, "reason": f"fetch_exception:{type(exc).__name__}:{exc}"})
    finally:
        bs.logout()
    return result, failures


def build_index_feature_maps(
    histories: Mapping[str, pd.DataFrame],
) -> dict[str, dict[date, dict[str, Any]]]:
    result: dict[str, dict[date, dict[str, Any]]] = {}
    for name, history in histories.items():
        frame = prepare_price_frame(history).copy()
        if frame.empty:
            continue
        close = pd.to_numeric(frame["close"], errors="coerce")
        frame["ma60"] = close.rolling(60, min_periods=40).mean()
        frame["ma120"] = close.rolling(120, min_periods=80).mean()
        frame["ret5"] = close.pct_change(5) * 100.0
        frame["ret20"] = close.pct_change(20) * 100.0
        frame["peak60"] = close.rolling(60, min_periods=20).max()
        frame["dd60"] = (close / frame["peak60"] - 1.0) * 100.0
        mapping: dict[date, dict[str, Any]] = {}
        for _, row in frame.iterrows():
            day = row.get("date")
            if not isinstance(day, date):
                continue
            current = _finite(row.get("close"))
            ma60 = _finite(row.get("ma60"))
            ma120 = _finite(row.get("ma120"))
            mapping[day] = {
                "above_ma60": None if current is None or ma60 is None else current >= ma60,
                "above_ma120": None if current is None or ma120 is None else current >= ma120,
                "ret5_pct": _finite(row.get("ret5")),
                "ret20_pct": _finite(row.get("ret20")),
                "dd60_pct": _finite(row.get("dd60")),
            }
        result[name] = mapping
    return result


def systemic_state(
    feature_maps: Mapping[str, Mapping[date, Mapping[str, Any]]],
    *,
    as_of: date,
) -> dict[str, Any]:
    rows = [mapping.get(as_of) for mapping in feature_maps.values()]
    rows = [dict(row) for row in rows if row is not None]
    mature = [row for row in rows if row.get("above_ma120") is not None and row.get("ret20_pct") is not None]
    if len(mature) < 2:
        return {"status": "UNKNOWN", "available_index_count": len(mature), "reasons": ["insufficient_mature_indices"]}

    above120_ratio = sum(bool(row["above_ma120"]) for row in mature) / len(mature)
    above60_values = [row.get("above_ma60") for row in mature if row.get("above_ma60") is not None]
    above60_ratio = sum(bool(value) for value in above60_values) / len(above60_values) if above60_values else 0.5
    ret5_values = [float(row["ret5_pct"]) for row in mature if row.get("ret5_pct") is not None]
    ret20_values = [float(row["ret20_pct"]) for row in mature if row.get("ret20_pct") is not None]
    dd60_values = [float(row["dd60_pct"]) for row in mature if row.get("dd60_pct") is not None]
    med5 = median(ret5_values) if ret5_values else 0.0
    med20 = median(ret20_values) if ret20_values else 0.0
    med_dd60 = median(dd60_values) if dd60_values else 0.0

    reasons: list[str] = []
    red = False
    if med5 <= -5.0:
        red = True
        reasons.append("broad_5d_crash")
    if above120_ratio <= 0.25 and med20 <= -6.0:
        red = True
        reasons.append("broad_below_ma120_with_20d_loss")
    if med_dd60 <= -12.0:
        red = True
        reasons.append("broad_60d_drawdown_severe")

    yellow = (
        above120_ratio <= 0.50
        or above60_ratio <= 0.25
        or med5 <= -2.5
        or med20 <= -4.0
        or med_dd60 <= -8.0
    )
    if not red and yellow:
        reasons.append("broad_market_stress")
    status = "RED" if red else "YELLOW" if yellow else "GREEN"
    return {
        "status": status,
        "available_index_count": len(mature),
        "above_ma60_ratio": round(above60_ratio, 4),
        "above_ma120_ratio": round(above120_ratio, 4),
        "median_return_5d_pct": round(med5, 4),
        "median_return_20d_pct": round(med20, 4),
        "median_drawdown_60d_pct": round(med_dd60, 4),
        "reasons": reasons,
    }


def apply_systemic_overlay(
    base_curve: pd.Series,
    *,
    feature_maps: Mapping[str, Mapping[date, Mapping[str, Any]]],
    policy: SystemicExposurePolicy,
) -> tuple[pd.Series, list[dict[str, Any]], dict[str, Any]]:
    if base_curve.empty:
        return base_curve.copy(), [], {"exposure_change_count": 0}
    base_curve = base_curve.sort_index()
    returns = base_curve.pct_change().fillna(0.0)
    equity = 1.0
    exposure = policy.green_fraction
    pending_exposure = exposure
    values: list[float] = []
    dates: list[date] = []
    rows: list[dict[str, Any]] = []
    exposure_change_count = 0
    total_rebalance_cost = 0.0
    red_sessions = yellow_sessions = green_sessions = unknown_sessions = 0

    mapping = {
        "GREEN": policy.green_fraction,
        "YELLOW": policy.yellow_fraction,
        "RED": policy.red_fraction,
        "UNKNOWN": policy.unknown_fraction,
    }

    for day, raw_return in returns.items():
        # Target decided after the previous close is executed before today's
        # return.  Turnover cost is charged before return accrues.
        if abs(pending_exposure - exposure) > 1e-12:
            turnover = abs(pending_exposure - exposure)
            cost = equity * turnover * policy.rebalance_cost_bps / 10_000.0
            equity -= cost
            total_rebalance_cost += cost
            exposure = pending_exposure
            exposure_change_count += 1
        daily_return = float(raw_return)
        equity *= 1.0 + exposure * daily_return
        dates.append(day)
        values.append(equity)

        state = systemic_state(feature_maps, as_of=day)
        status = str(state.get("status") or "UNKNOWN")
        if status == "RED":
            red_sessions += 1
        elif status == "YELLOW":
            yellow_sessions += 1
        elif status == "GREEN":
            green_sessions += 1
        else:
            unknown_sessions += 1
        pending_exposure = mapping.get(status, policy.unknown_fraction)
        rows.append(
            {
                "date": day,
                "base_return_pct": round(daily_return * 100.0, 6),
                "exposure_used": round(exposure, 6),
                "next_session_target_exposure": round(pending_exposure, 6),
                **state,
                "equity": round(equity, 10),
            }
        )

    curve = pd.Series(values, index=pd.Index(dates, name="date"), dtype=float)
    audit = {
        "exposure_change_count": exposure_change_count,
        "total_rebalance_cost": round(total_rebalance_cost, 8),
        "red_sessions": red_sessions,
        "yellow_sessions": yellow_sessions,
        "green_sessions": green_sessions,
        "unknown_sessions": unknown_sessions,
    }
    return curve, rows, audit


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
    index_cache_dir: Path,
    board_rules_file: Path,
    evaluation_stride: int = 5,
    cost_bps_per_side: float = 15.0,
    policies: Sequence[SystemicExposurePolicy] = POLICY_GRID,
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

    concentration_curve, _, _, concentration_audit = replay_with_concentration_guard(
        events,
        data_map,
        start_date=start_date,
        end_date=end_date,
        entry_policy=BASE_ENTRY_POLICY,
        guard_policy=BASE_CONCENTRATION_GUARD,
    )
    concentration_metrics = _metrics(BASE_CONCENTRATION_GUARD.name, concentration_curve)

    index_histories, index_failures = fetch_index_histories(
        start_date=start_date, end_date=end_date, cache_dir=index_cache_dir
    )
    feature_maps = build_index_feature_maps(index_histories)

    comparison_rows: list[dict[str, Any]] = []
    all_daily_rows: list[dict[str, Any]] = []
    concentration_eval = evaluate_candidate(naive_metrics, concentration_metrics)
    comparison_rows.append(
        {
            "name": BASE_CONCENTRATION_GUARD.name,
            "kind": "concentration_base",
            "cagr_pct": concentration_metrics.cagr_pct,
            "max_drawdown_pct": concentration_metrics.max_drawdown_pct,
            "calmar_ratio": concentration_eval.calmar_ratio,
            "cagr_retention_vs_naive_pct": concentration_eval.cagr_retention_pct,
            "drawdown_improvement_vs_naive_pct": concentration_eval.drawdown_improvement_pct,
            "accepted": concentration_eval.accepted,
            **concentration_audit,
        }
    )

    selected_row: dict[str, Any] | None = None
    for policy in policies:
        curve, daily_rows, audit = apply_systemic_overlay(
            concentration_curve, feature_maps=feature_maps, policy=policy
        )
        metrics = _metrics(policy.name, curve)
        evaluation = evaluate_candidate(naive_metrics, metrics)
        row = {
            **asdict(policy),
            "kind": "systemic_index_overlay",
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
        for daily in daily_rows:
            all_daily_rows.append({"policy": policy.name, **daily})
        if evaluation.accepted and (
            selected_row is None or float(row.get("calmar_ratio") or -math.inf) > float(selected_row.get("calmar_ratio") or -math.inf)
        ):
            selected_row = row

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "systemic_index_guard_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "systemic_index_guard_daily.csv", all_daily_rows, ["policy", "date"])
    _write_csv(output_dir / "index_data_failures.csv", index_failures, ["name", "code", "reason"])
    _write_csv(output_dir / "stock_data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "index_history_count": len(index_histories),
        "index_names": sorted(index_histories),
        "naive_metrics": asdict(naive_metrics),
        "concentration_base_metrics": asdict(concentration_metrics),
        "selected_policy": selected_row,
        "risk_gate_passed_on_diagnostic_panel": selected_row is not None,
        "stock_entry_exit_signals_changed": False,
        "concentration_guard_changed": False,
        "systemic_decision_after_close_for_next_session": True,
        "systemic_overlay_uses_only_index_history": True,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_systemic_index_guard_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Historical Systemic Index Risk Overlay",
        "",
        f"- period: {start_date} to {end_date}",
        f"- index histories: {len(index_histories)} / {len(INDEX_CODES)}",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        f"- concentration-base CAGR/MDD: {concentration_metrics.cagr_pct:.4f}% / {concentration_metrics.max_drawdown_pct:.4f}%",
        "- index regime is formed after close and changes next-session exposure only",
        "- exposure turnover pays explicit friction",
        "- stock entry/exit signals are unchanged",
        "- production deployment remains blocked pending survivorship-aware All-A validation",
        "",
        "## Comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_vs_naive_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_vs_naive_pct')}% | accepted={row.get('accepted')}"
        )
    (output_dir / "historical_systemic_index_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--index-cache-dir", type=Path, default=Path("data/cache/genge_systemic_index_guard"))
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
        index_cache_dir=args.index_cache_dir,
        board_rules_file=args.board_rules_file,
        evaluation_stride=max(1, args.evaluation_stride),
        cost_bps_per_side=max(0.0, args.cost_bps_per_side),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary["data_ready_case_count"] and summary["index_history_count"] >= 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
