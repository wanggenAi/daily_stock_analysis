"""Portfolio-NAV risk overlay for the hard-logic strategy.

The stock-level entry/exit engine is frozen.  This layer changes only the amount
of total capital exposed to that baseline portfolio.  Decisions are made after
close from information available through that session and affect the next
session.  The goal is to reduce *portfolio* drawdown without cutting individual
long-term winners solely because their own price path is volatile.

The famous-stock panel remains a diagnostic panel.  Any deployable policy must
still pass a survivorship-aware point-in-time All-A portfolio walk-forward.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from src.strategies.genge_opportunity_discovery.drawdown_overlay_backtest import (
    equal_weight_portfolio,
    equity_curve_from_trades,
)
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import (
    StrategyMetrics,
    cagr_pct,
    evaluate_candidate,
    max_drawdown_pct,
    select_drawdown_optimized,
)
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    DEFAULT_STRIDE,
    FamousCase,
    fetch_case_data,
    load_cases,
    simulate_company,
)

RULE_VERSION = "portfolio_nav_risk_overlay_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"


@dataclass(frozen=True)
class PortfolioOverlayPolicy:
    name: str
    max_gross_fraction: float = 0.90
    volatility_target_pct: float | None = None
    volatility_lookback_sessions: int = 20
    volatility_floor_fraction: float = 0.25
    dd_level_1_pct: float = 8.0
    dd_level_2_pct: float = 12.0
    dd_level_3_pct: float = 16.0
    dd_multiplier_1: float = 0.75
    dd_multiplier_2: float = 0.50
    dd_multiplier_3: float = 0.25
    use_drawdown_guard: bool = True
    rebalance_cost_bps: float = 5.0


POLICY_GRID: tuple[PortfolioOverlayPolicy, ...] = (
    PortfolioOverlayPolicy(
        name="gross90_only",
        use_drawdown_guard=False,
        volatility_target_pct=None,
    ),
    PortfolioOverlayPolicy(
        name="dd_guard",
        volatility_target_pct=None,
        dd_level_1_pct=8.0,
        dd_level_2_pct=12.0,
        dd_level_3_pct=16.0,
        dd_multiplier_1=0.75,
        dd_multiplier_2=0.50,
        dd_multiplier_3=0.25,
    ),
    PortfolioOverlayPolicy(
        name="vol30",
        volatility_target_pct=30.0,
        volatility_floor_fraction=0.35,
        use_drawdown_guard=False,
    ),
    PortfolioOverlayPolicy(
        name="vol30_dd_guard",
        volatility_target_pct=30.0,
        volatility_floor_fraction=0.35,
        dd_level_1_pct=8.0,
        dd_level_2_pct=12.0,
        dd_level_3_pct=16.0,
        dd_multiplier_1=0.80,
        dd_multiplier_2=0.55,
        dd_multiplier_3=0.30,
    ),
    PortfolioOverlayPolicy(
        name="vol35_mild_dd",
        volatility_target_pct=35.0,
        volatility_floor_fraction=0.45,
        dd_level_1_pct=10.0,
        dd_level_2_pct=15.0,
        dd_level_3_pct=20.0,
        dd_multiplier_1=0.85,
        dd_multiplier_2=0.65,
        dd_multiplier_3=0.40,
    ),
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _drawdown_from_peak(current: float, peak: float) -> float:
    if current <= 0 or peak <= 0:
        return 100.0
    return max(0.0, (peak - current) / peak * 100.0)


def _drawdown_multiplier(drawdown_pct: float, policy: PortfolioOverlayPolicy) -> float:
    if not policy.use_drawdown_guard:
        return 1.0
    dd = max(0.0, float(drawdown_pct))
    if dd < policy.dd_level_1_pct:
        return 1.0
    if dd < policy.dd_level_2_pct:
        return policy.dd_multiplier_1
    if dd < policy.dd_level_3_pct:
        return policy.dd_multiplier_2
    return policy.dd_multiplier_3


def _volatility_fraction(
    observed_returns: Sequence[float],
    policy: PortfolioOverlayPolicy,
) -> float:
    target = _finite(policy.volatility_target_pct)
    if target is None or target <= 0:
        return policy.max_gross_fraction
    lookback = max(5, int(policy.volatility_lookback_sessions))
    if len(observed_returns) < lookback:
        return policy.max_gross_fraction
    series = pd.Series(observed_returns[-lookback:], dtype=float)
    daily_std = float(series.std(ddof=1))
    if not math.isfinite(daily_std) or daily_std <= 0:
        return policy.max_gross_fraction
    annualized_vol_pct = daily_std * math.sqrt(252.0) * 100.0
    if annualized_vol_pct <= 0:
        return policy.max_gross_fraction
    fraction = target / annualized_vol_pct
    fraction = max(policy.volatility_floor_fraction, fraction)
    return min(policy.max_gross_fraction, fraction)


def apply_portfolio_overlay(
    baseline_curve: pd.Series,
    policy: PortfolioOverlayPolicy,
) -> tuple[pd.Series, pd.DataFrame]:
    """Apply next-session exposure sizing to a frozen baseline NAV curve."""

    if baseline_curve is None or baseline_curve.empty:
        return pd.Series(dtype=float), pd.DataFrame()
    baseline = baseline_curve.astype(float).sort_index()
    returns = baseline.pct_change().fillna(0.0)

    overlay_nav = 1.0
    peak = 1.0
    exposure = min(1.0, max(0.0, policy.max_gross_fraction))
    observed_returns: list[float] = []
    nav_values: list[float] = []
    audit_rows: list[dict[str, Any]] = []

    for day, raw_return in returns.items():
        baseline_return = float(raw_return) if math.isfinite(float(raw_return)) else 0.0
        nav_before = overlay_nav
        overlay_nav *= max(0.0, 1.0 + exposure * baseline_return)
        peak = max(peak, overlay_nav)
        drawdown = _drawdown_from_peak(overlay_nav, peak)
        observed_returns.append(baseline_return)

        vol_fraction = _volatility_fraction(observed_returns, policy)
        dd_multiplier = _drawdown_multiplier(drawdown, policy)
        next_exposure = min(
            policy.max_gross_fraction,
            max(0.0, vol_fraction * dd_multiplier),
        )
        turnover = abs(next_exposure - exposure)
        rebalance_cost = turnover * max(0.0, policy.rebalance_cost_bps) / 10000.0
        if rebalance_cost > 0:
            overlay_nav *= max(0.0, 1.0 - rebalance_cost)
            peak = max(peak, overlay_nav)
            drawdown = _drawdown_from_peak(overlay_nav, peak)

        nav_values.append(overlay_nav)
        audit_rows.append(
            {
                "date": day,
                "baseline_return_pct": baseline_return * 100.0,
                "nav_before": nav_before,
                "nav_after": overlay_nav,
                "portfolio_drawdown_pct": drawdown,
                "exposure_used_today": exposure,
                "next_session_exposure": next_exposure,
                "volatility_fraction": vol_fraction,
                "drawdown_multiplier": dd_multiplier,
                "rebalance_turnover_fraction": turnover,
                "rebalance_cost_fraction": rebalance_cost,
            }
        )
        exposure = next_exposure

    curve = pd.Series(nav_values, index=baseline.index, dtype=float)
    return curve, pd.DataFrame(audit_rows)


def _metrics(name: str, curve: pd.Series) -> StrategyMetrics:
    if curve.empty:
        return StrategyMetrics(name=name, cagr_pct=0.0, max_drawdown_pct=100.0)
    years = max(1.0 / 365.25, (curve.index[-1] - curve.index[0]).days / 365.25)
    growth = cagr_pct(float(curve.iloc[0]), float(curve.iloc[-1]), years) or 0.0
    mdd = max_drawdown_pct(curve.tolist()) or 0.0
    return StrategyMetrics(name=name, cagr_pct=round(growth, 6), max_drawdown_pct=round(float(mdd), 6))


def _write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_suite(
    cases: Sequence[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    evaluation_stride: int = DEFAULT_STRIDE,
    cost_bps_per_side: float = 15.0,
    policies: Sequence[PortfolioOverlayPolicy] = POLICY_GRID,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(list(cases), as_of=end_date, years=years, cache_dir=cache_dir)

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
        baseline_trade_count += len(trades)
        baseline_curves.append(
            equity_curve_from_trades(data, trades, start_date=start_date, end_date=end_date)
        )
    baseline_curve = equal_weight_portfolio(baseline_curves)
    baseline = _metrics("baseline", baseline_curve)

    comparison_rows: list[dict[str, Any]] = []
    candidate_metrics: list[StrategyMetrics] = []
    audit_by_policy: dict[str, pd.DataFrame] = {}

    for policy in policies:
        curve, audit = apply_portfolio_overlay(baseline_curve, policy)
        metrics = _metrics(policy.name, curve)
        evaluation = evaluate_candidate(baseline, metrics)
        candidate_metrics.append(metrics)
        audit_by_policy[policy.name] = audit
        exposures = audit["exposure_used_today"].astype(float) if not audit.empty else pd.Series(dtype=float)
        turnover = audit["rebalance_turnover_fraction"].astype(float).sum() if not audit.empty else 0.0
        comparison_rows.append(
            {
                **asdict(policy),
                "cagr_pct": metrics.cagr_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "calmar_ratio": evaluation.calmar_ratio,
                "drawdown_improvement_pct": evaluation.drawdown_improvement_pct,
                "cagr_retention_pct": evaluation.cagr_retention_pct,
                "average_exposure_pct": round(float(exposures.mean()) * 100.0, 4) if not exposures.empty else None,
                "minimum_exposure_pct": round(float(exposures.min()) * 100.0, 4) if not exposures.empty else None,
                "exposure_below_50pct_sessions": int((exposures < 0.50).sum()) if not exposures.empty else 0,
                "gross_rebalance_turnover": round(float(turnover), 6),
                "accepted": evaluation.accepted,
                "deployment_allowed": evaluation.deployment_allowed,
                "reasons": ";".join(evaluation.reasons),
            }
        )

    selected = select_drawdown_optimized(baseline, candidate_metrics)
    selected_policy = next(
        (policy for policy in policies if selected and policy.name == selected.metrics.name),
        None,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "portfolio_overlay_comparison.csv", comparison_rows, ["name"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    if selected and selected.metrics.name in audit_by_policy:
        audit_by_policy[selected.metrics.name].to_csv(
            output_dir / "selected_portfolio_overlay_daily.csv", index=False, encoding="utf-8"
        )

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "baseline_trade_count": baseline_trade_count,
        "baseline_metrics": asdict(baseline),
        "selected_policy": asdict(selected_policy) if selected_policy else None,
        "selected_metrics": asdict(selected.metrics) if selected else None,
        "risk_gate_passed_on_diagnostic_panel": bool(selected and selected.accepted),
        "selected_drawdown_improvement_pct": selected.drawdown_improvement_pct if selected else None,
        "selected_cagr_retention_pct": selected.cagr_retention_pct if selected else None,
        "selected_calmar_ratio": selected.calmar_ratio if selected else None,
        "selected_reasons": list(selected.reasons) if selected else ["no_candidate_policy"],
        "stock_entry_exit_signals_changed": False,
        "portfolio_exposure_decision_after_close_for_next_session": True,
        "famous_case_selection_bias_warning": True,
        "production_deployment_allowed": False,
        "full_all_a_walk_forward_required": True,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "portfolio_nav_risk_overlay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Portfolio NAV Risk Overlay",
        "",
        f"- period: {start_date} to {end_date}",
        f"- data-ready cases: {len(ready)}",
        f"- frozen baseline trades: {baseline_trade_count}",
        f"- baseline CAGR: {baseline.cagr_pct:.4f}%",
        f"- baseline MDD: {baseline.max_drawdown_pct:.4f}%",
        "- stock-level entry/exit signals are unchanged",
        "- exposure decisions are after-close and affect the next session",
        "- famous-stock panel is diagnostic only",
        "",
        "## Policy comparison",
    ]
    for row in comparison_rows:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row['calmar_ratio']} | retention={row['cagr_retention_pct']}% | "
            f"DD improvement={row['drawdown_improvement_pct']}% | avg exposure={row['average_exposure_pct']}% | "
            f"accepted={row['accepted']}"
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
            "- production deployment remains blocked until unbiased All-A validation",
        ]
    (output_dir / "portfolio_nav_risk_overlay.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--evaluation-stride", type=int, default=DEFAULT_STRIDE)
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
