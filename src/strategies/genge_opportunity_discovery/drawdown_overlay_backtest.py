"""Evaluate drawdown-only exits on frozen hard-logic/reverse-valuation entries.

The baseline entry set is produced by ``hard_logic_historical_backtest``.  This
module never invents a better entry and never adds a new BUY.  It only asks a
clean question: if the same historical entries had a disciplined loss/profit
protection overlay, how much drawdown would have been removed and how much CAGR
would have been sacrificed?

The named famous-stock panel remains selection/survivorship biased.  Passing the
risk gates here is diagnostic only; production deployment still requires an
unbiased All-A walk-forward portfolio test.
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
    cagr_pct,
    evaluate_candidate,
    max_drawdown_pct,
    select_drawdown_optimized,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase,
    HistoricalCompanyData,
    fetch_case_data,
    load_cases,
    simulate_company,
)

RULE_VERSION = "hard_logic_drawdown_overlay_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


@dataclass(frozen=True)
class RiskOverlayPolicy:
    name: str
    initial_stop_pct: float
    breakeven_activation_pct: float
    breakeven_floor_pct: float
    trailing_activation_pct: float
    trailing_drawdown_pct: float


DEFAULT_POLICY_GRID: tuple[RiskOverlayPolicy, ...] = (
    RiskOverlayPolicy("tight", 12.0, 20.0, 1.0, 30.0, 15.0),
    RiskOverlayPolicy("balanced", 15.0, 25.0, 2.0, 40.0, 18.0),
    RiskOverlayPolicy("growth", 18.0, 30.0, 3.0, 50.0, 22.0),
    RiskOverlayPolicy("wide", 22.0, 35.0, 3.0, 60.0, 25.0),
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


def risk_exit_reason(
    *,
    entry_price: float,
    peak_close: float,
    close: float,
    policy: RiskOverlayPolicy,
) -> str | None:
    """Return an after-close risk exit reason; execution is next session open."""

    if entry_price <= 0 or peak_close <= 0 or close <= 0:
        return None
    runup_pct = (peak_close / entry_price - 1.0) * 100.0

    if runup_pct >= policy.trailing_activation_pct:
        trail_floor = peak_close * (1.0 - policy.trailing_drawdown_pct / 100.0)
        if close <= trail_floor:
            return "SELL_RISK_TRAILING_PROFIT_PROTECTION"

    if runup_pct >= policy.breakeven_activation_pct:
        breakeven_floor = entry_price * (1.0 + policy.breakeven_floor_pct / 100.0)
        if close <= breakeven_floor:
            return "SELL_RISK_PROFIT_GIVEBACK_PROTECTION"

    initial_floor = entry_price * (1.0 - policy.initial_stop_pct / 100.0)
    if close <= initial_floor:
        return "SELL_RISK_INITIAL_LOSS_LIMIT"
    return None


def _trade_drawdown(values: Iterable[float]) -> float:
    peak: float | None = None
    worst = 0.0
    for raw in values:
        value = _finite(raw)
        if value is None or value <= 0:
            continue
        peak = value if peak is None else max(peak, value)
        worst = min(worst, (value / peak - 1.0) * 100.0)
    return round(worst, 4)


def apply_risk_overlay_to_trade(
    data: HistoricalCompanyData,
    trade: Mapping[str, Any],
    policy: RiskOverlayPolicy,
    *,
    cost_bps_per_side: float = 15.0,
) -> dict[str, Any]:
    """Cut a baseline trade earlier only when a risk rule fires.

    Baseline entry date/price and the baseline maximum holding horizon are frozen.
    A trigger is observed at close and executed at the next available open.
    """

    result = dict(trade)
    result["risk_overlay_policy"] = policy.name
    result["risk_overlay_exit"] = False

    entry_date = _day(trade.get("entry_date"))
    baseline_exit_date = _day(trade.get("exit_date"))
    entry_price = _finite(trade.get("entry_price"))
    if entry_date is None or baseline_exit_date is None or entry_price is None or entry_price <= 0:
        return result

    price = prepare_price_frame(data.price_df)
    window = price[(price["date"] >= entry_date) & (price["date"] <= baseline_exit_date)].reset_index(drop=True)
    if len(window) < 2:
        return result

    peak_close = entry_price
    for i in range(len(window) - 1):
        close = _finite(window.iloc[i].get("close"))
        if close is None or close <= 0:
            continue
        peak_close = max(peak_close, close)
        reason = risk_exit_reason(
            entry_price=entry_price,
            peak_close=peak_close,
            close=close,
            policy=policy,
        )
        if not reason:
            continue

        next_open = _finite(window.iloc[i + 1].get("open"))
        if next_open is None or next_open <= 0:
            continue
        exit_price = next_open * (1.0 - cost_bps_per_side / 10000.0)
        exit_date = window.iloc[i + 1]["date"]
        held = window.iloc[: i + 2]
        closes = pd.to_numeric(held["close"], errors="coerce").dropna().tolist()
        highs = pd.to_numeric(held["high"], errors="coerce").dropna().tolist()
        gross = (exit_price / entry_price - 1.0) * 100.0
        max_runup = ((max(highs) / entry_price - 1.0) * 100.0) if highs else gross

        result.update(
            {
                "exit_signal_date": window.iloc[i]["date"],
                "exit_date": exit_date,
                "exit_price": round(exit_price, 4),
                "exit_reason": reason,
                "gross_return_pct": round(gross, 4),
                "net_return_pct": round(gross, 4),
                "max_runup_pct": round(max_runup, 4),
                "max_drawdown_pct": _trade_drawdown([entry_price, *closes]),
                "capture_ratio_pct": round(gross / max_runup * 100.0, 4) if max_runup > 0 else None,
                "holding_sessions": len(held),
                "low_buy_high_sell": False,
                "risk_overlay_exit": True,
            }
        )
        return result
    return result


def equity_curve_from_trades(
    data: HistoricalCompanyData,
    trades: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
) -> pd.Series:
    """Rebuild normalized daily equity from already cost-adjusted trade prices."""

    price = prepare_price_frame(data.price_df)
    price = price[(price["date"] >= start_date) & (price["date"] <= end_date)].reset_index(drop=True)
    if price.empty:
        return pd.Series(dtype=float)

    ordered = sorted(
        [dict(t) for t in trades if _day(t.get("entry_date")) is not None],
        key=lambda t: _day(t.get("entry_date")) or date.max,
    )
    trade_index = 0
    active: dict[str, Any] | None = None
    cash = 1.0
    shares = 0.0
    values: list[float] = []
    dates: list[date] = []

    for _, bar in price.iterrows():
        day = bar["date"]
        close = _finite(bar.get("close"))

        if active is not None and _day(active.get("exit_date")) == day:
            exit_price = _finite(active.get("exit_price"))
            if exit_price is not None and exit_price > 0:
                cash = shares * exit_price
                shares = 0.0
                active = None

        if active is None and trade_index < len(ordered):
            candidate = ordered[trade_index]
            if _day(candidate.get("entry_date")) == day:
                entry_price = _finite(candidate.get("entry_price"))
                if entry_price is not None and entry_price > 0:
                    shares = cash / entry_price
                    cash = 0.0
                    active = candidate
                trade_index += 1

        if active is not None and str(active.get("exit_reason") or "") == "END_OF_TEST_MARK_TO_MARKET":
            if _day(active.get("exit_date")) == day:
                exit_price = _finite(active.get("exit_price"))
                if exit_price is not None and exit_price > 0:
                    cash = shares * exit_price
                    shares = 0.0
                    active = None

        equity = cash if active is None else shares * close if close is not None and close > 0 else cash
        dates.append(day)
        values.append(float(equity))

    return pd.Series(values, index=pd.Index(dates, name="date"), dtype=float)


def equal_weight_portfolio(curves: Sequence[pd.Series]) -> pd.Series:
    usable = [series.rename(str(i)) for i, series in enumerate(curves) if series is not None and not series.empty]
    if not usable:
        return pd.Series(dtype=float)
    frame = pd.concat(usable, axis=1).sort_index().ffill().fillna(1.0)
    return frame.mean(axis=1)


def _metrics(name: str, curve: pd.Series) -> StrategyMetrics:
    if curve.empty:
        return StrategyMetrics(name=name, cagr_pct=0.0, max_drawdown_pct=100.0)
    years = max(1.0 / 365.25, (curve.index[-1] - curve.index[0]).days / 365.25)
    cagr = cagr_pct(float(curve.iloc[0]), float(curve.iloc[-1]), years) or 0.0
    mdd = max_drawdown_pct(curve.tolist())
    return StrategyMetrics(name=name, cagr_pct=round(cagr, 6), max_drawdown_pct=float(mdd or 0.0))


def _write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_suite(
    cases: Sequence[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    evaluation_stride: int = 5,
    cost_bps_per_side: float = 15.0,
    policies: Sequence[RiskOverlayPolicy] = DEFAULT_POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)
    baseline_by_code: dict[str, list[dict[str, Any]]] = {}
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
        baseline_by_code[data.code] = trades
        baseline_trade_count += len(trades)
        baseline_curves.append(
            equity_curve_from_trades(data, trades, start_date=start_date, end_date=end_date)
        )

    baseline_curve = equal_weight_portfolio(baseline_curves)
    baseline_metrics = _metrics("baseline", baseline_curve)
    comparison_rows: list[dict[str, Any]] = [
        {
            "policy": "baseline",
            "cagr_pct": baseline_metrics.cagr_pct,
            "max_drawdown_pct": baseline_metrics.max_drawdown_pct,
            "calmar_ratio": (
                baseline_metrics.cagr_pct / baseline_metrics.max_drawdown_pct
                if baseline_metrics.max_drawdown_pct > 0
                else None
            ),
            "risk_exit_count": 0,
            "accepted": True,
            "deployment_allowed": False,
            "reasons": "diagnostic_baseline",
        }
    ]
    candidate_metrics: list[StrategyMetrics] = []
    overlay_trade_rows: list[dict[str, Any]] = []

    for policy in policies:
        curves: list[pd.Series] = []
        risk_exit_count = 0
        policy_trades: list[dict[str, Any]] = []
        for data in ready:
            baseline_trades = baseline_by_code.get(data.code, [])
            overlay_trades = [
                apply_risk_overlay_to_trade(data, trade, policy, cost_bps_per_side=cost_bps_per_side)
                for trade in baseline_trades
            ]
            risk_exit_count += sum(bool(t.get("risk_overlay_exit")) for t in overlay_trades)
            policy_trades.extend(overlay_trades)
            curves.append(
                equity_curve_from_trades(data, overlay_trades, start_date=start_date, end_date=end_date)
            )

        curve = equal_weight_portfolio(curves)
        metrics = _metrics(policy.name, curve)
        candidate_metrics.append(metrics)
        evaluation = evaluate_candidate(baseline_metrics, metrics)
        comparison_rows.append(
            {
                "policy": policy.name,
                "initial_stop_pct": policy.initial_stop_pct,
                "breakeven_activation_pct": policy.breakeven_activation_pct,
                "breakeven_floor_pct": policy.breakeven_floor_pct,
                "trailing_activation_pct": policy.trailing_activation_pct,
                "trailing_drawdown_pct": policy.trailing_drawdown_pct,
                "cagr_pct": metrics.cagr_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "calmar_ratio": evaluation.calmar_ratio,
                "drawdown_improvement_pct": evaluation.drawdown_improvement_pct,
                "cagr_retention_pct": evaluation.cagr_retention_pct,
                "risk_exit_count": risk_exit_count,
                "accepted": evaluation.accepted,
                "deployment_allowed": evaluation.deployment_allowed,
                "reasons": ";".join(evaluation.reasons),
            }
        )
        for row in policy_trades:
            overlay_trade_rows.append({"policy": policy.name, **row})

    selected = select_drawdown_optimized(baseline_metrics, candidate_metrics)
    selected_policy = next((p for p in policies if selected and p.name == selected.metrics.name), None)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "drawdown_policy_comparison.csv", comparison_rows, ["policy"])
    _write_csv(output_dir / "overlay_trades.csv", overlay_trade_rows, ["policy", "code", "stock_name"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "baseline_trade_count": baseline_trade_count,
        "baseline_metrics": asdict(baseline_metrics),
        "selected_policy": asdict(selected_policy) if selected_policy else None,
        "selected_metrics": asdict(selected.metrics) if selected else None,
        "risk_gate_passed_on_diagnostic_panel": bool(selected and selected.accepted),
        "selected_drawdown_improvement_pct": selected.drawdown_improvement_pct if selected else None,
        "selected_cagr_retention_pct": selected.cagr_retention_pct if selected else None,
        "selected_calmar_ratio": selected.calmar_ratio if selected else None,
        "selected_reasons": list(selected.reasons) if selected else ["no_candidate_policy"],
        "same_entry_set_as_baseline": True,
        "new_buy_signals_allowed": False,
        "risk_signals_observed_after_close_execute_next_open": True,
        "famous_case_selection_bias_warning": True,
        "production_deployment_allowed": False,
        "full_all_a_walk_forward_required": True,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "drawdown_overlay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Drawdown Overlay Backtest",
        "",
        f"- period: {start_date} to {end_date}",
        f"- data-ready cases: {len(ready)}",
        f"- frozen baseline trades: {baseline_trade_count}",
        f"- baseline CAGR: {baseline_metrics.cagr_pct:.4f}%",
        f"- baseline MDD: {baseline_metrics.max_drawdown_pct:.4f}%",
        "- entries are frozen; overlay can only exit earlier",
        "- famous-stock panel is diagnostic and cannot authorize production deployment",
        "",
        "## Policy comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['policy']} | CAGR={row.get('cagr_pct')}% | MDD={row.get('max_drawdown_pct')}% | "
            f"Calmar={row.get('calmar_ratio')} | retention={row.get('cagr_retention_pct')}% | "
            f"DD improvement={row.get('drawdown_improvement_pct')}% | risk exits={row.get('risk_exit_count')} | "
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
            "- production deployment: BLOCKED until unbiased All-A walk-forward validation",
        ]
    (output_dir / "drawdown_overlay.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
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
