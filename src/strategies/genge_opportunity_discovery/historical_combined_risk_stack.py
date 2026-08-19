"""Combined point-in-time portfolio risk stack diagnostic.

This module combines only independently tested, orthogonal controls:

1. frozen hard-logic + reverse-valuation stock entry/exit events;
2. point-in-time entry risk budget;
3. entry/static correlation cap plus dynamic stressed-cluster trims;
4. low-frequency single-name concentration trim already embedded in the dynamic replay;
5. broad A-share systemic exposure scaling applied one session later.

No stock BUY/SELL signal is changed. Dynamic-cluster trim orders are frozen after
close and execute at the next observed open. Broad-index exposure is also chosen
after close and applied only to the next session return. Explicit friction is
charged at both layers. This remains a biased famous-stock diagnostic; production
use requires survivorship-aware All-A walk-forward validation.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.strategies.genge_opportunity_discovery.all_a_full_scan import load_board_rules
from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import evaluate_candidate
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    FamousCase, fetch_case_data, load_cases,
)
from src.strategies.genge_opportunity_discovery.historical_dynamic_cluster_guard import (
    BASE_CONCENTRATION_GUARD,
    BASE_ENTRY_CORRELATION_POLICY,
    BASE_ENTRY_POLICY,
    DynamicClusterPolicy,
    replay_with_dynamic_cluster_guard,
)
from src.strategies.genge_opportunity_discovery.historical_portfolio_risk_budget import (
    PortfolioConstructionPolicy, _metrics, collect_frozen_events, replay_single_account,
)
from src.strategies.genge_opportunity_discovery.historical_systemic_index_guard import (
    SystemicExposurePolicy,
    apply_systemic_overlay,
    build_index_feature_maps,
    fetch_index_histories,
)

RULE_VERSION = "historical_combined_risk_stack_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"

DYNAMIC_POLICIES: tuple[DynamicClusterPolicy, ...] = (
    DynamicClusterPolicy("dyn65_45to35", 0.65, 0.45, 0.35),
    DynamicClusterPolicy("dyn65_50to40", 0.65, 0.50, 0.40),
)

SYSTEMIC_POLICIES: tuple[SystemicExposurePolicy, ...] = (
    SystemicExposurePolicy("crisis100_60", yellow_fraction=1.00, red_fraction=0.60),
    SystemicExposurePolicy("crisis100_55", yellow_fraction=1.00, red_fraction=0.55),
    SystemicExposurePolicy("mild90_55", yellow_fraction=0.90, red_fraction=0.55),
    SystemicExposurePolicy("mild90_50", yellow_fraction=0.90, red_fraction=0.50),
    SystemicExposurePolicy("balanced85_50", yellow_fraction=0.85, red_fraction=0.50),
)


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fallback: Sequence[str]) -> None:
    values = [dict(row) for row in rows]
    fields = sorted({key for row in values for key in row}) if values else list(fallback)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def run_suite(
    cases: Sequence[FamousCase], *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    index_cache_dir: Path,
    board_rules_file: Path,
    evaluation_stride: int = 5,
    cost_bps_per_side: float = 15.0,
    dynamic_policies: Sequence[DynamicClusterPolicy] = DYNAMIC_POLICIES,
    systemic_policies: Sequence[SystemicExposurePolicy] = SYSTEMIC_POLICIES,
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
        events, data_map, start_date=start_date, end_date=end_date, policy=naive_policy,
    )
    naive_metrics = _metrics(naive_policy.name, naive_curve)

    index_histories, index_failures = fetch_index_histories(
        start_date=start_date, end_date=end_date, cache_dir=index_cache_dir,
    )
    feature_maps = build_index_feature_maps(index_histories)

    comparison: list[dict[str, Any]] = []
    dynamic_audits: list[dict[str, Any]] = []
    systemic_daily: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None

    for dynamic_policy in dynamic_policies:
        base_curve, allocations, trims, dynamic_audit = replay_with_dynamic_cluster_guard(
            events,
            data_map,
            start_date=start_date,
            end_date=end_date,
            entry_policy=BASE_ENTRY_POLICY,
            concentration_policy=BASE_CONCENTRATION_GUARD,
            entry_correlation_policy=BASE_ENTRY_CORRELATION_POLICY,
            dynamic_policy=dynamic_policy,
        )
        base_metrics = _metrics(dynamic_policy.name, base_curve)
        dynamic_audits.append({
            "dynamic_policy": dynamic_policy.name,
            "base_cagr_pct": base_metrics.cagr_pct,
            "base_max_drawdown_pct": base_metrics.max_drawdown_pct,
            "allocation_count": len(allocations),
            "trim_row_count": len(trims),
            **dynamic_audit,
        })

        for systemic_policy in systemic_policies:
            curve, daily_rows, systemic_audit = apply_systemic_overlay(
                base_curve, feature_maps=feature_maps, policy=systemic_policy,
            )
            name = f"{dynamic_policy.name}+{systemic_policy.name}"
            metrics = _metrics(name, curve)
            evaluation = evaluate_candidate(naive_metrics, metrics)
            row = {
                "name": name,
                "dynamic_policy": dynamic_policy.name,
                "systemic_policy": systemic_policy.name,
                "cagr_pct": metrics.cagr_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "calmar_ratio": evaluation.calmar_ratio,
                "cagr_retention_vs_naive_pct": evaluation.cagr_retention_pct,
                "drawdown_improvement_vs_naive_pct": evaluation.drawdown_improvement_pct,
                "accepted": evaluation.accepted,
                "reasons": ";".join(evaluation.reasons),
                "dynamic_cluster_trigger_count": dynamic_audit.get("dynamic_cluster_trigger_count", 0),
                "dynamic_trim_order_count": dynamic_audit.get("dynamic_cluster_trim_order_count", 0),
                "entry_correlation_reduced_count": dynamic_audit.get("entry_correlation_reduced_count", 0),
                "concentration_and_dynamic_trim_count": dynamic_audit.get("trim_count", 0),
                **systemic_audit,
            }
            comparison.append(row)
            systemic_daily.extend({"combined_policy": name, **daily} for daily in daily_rows)
            if evaluation.accepted and (
                selected is None
                or float(row.get("calmar_ratio") or 0.0) > float(selected.get("calmar_ratio") or 0.0)
            ):
                selected = row

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "combined_risk_stack_comparison.csv", comparison, ["name"])
    _write_csv(output_dir / "dynamic_base_audit.csv", dynamic_audits, ["dynamic_policy"])
    _write_csv(output_dir / "combined_systemic_daily.csv", systemic_daily, ["combined_policy", "date"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    _write_csv(output_dir / "index_failures.csv", index_failures, ["name", "code", "reason"])

    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_ready_case_count": len(ready),
        "frozen_event_count": len(events),
        "risk_geometry_audit": geometry_audit,
        "naive_metrics": asdict(naive_metrics),
        "entry_risk_policy": asdict(BASE_ENTRY_POLICY),
        "entry_correlation_policy": asdict(BASE_ENTRY_CORRELATION_POLICY),
        "concentration_policy": asdict(BASE_CONCENTRATION_GUARD),
        "index_history_count": len(index_histories),
        "selected_policy": selected,
        "risk_gate_passed_on_diagnostic_panel": selected is not None,
        "stock_entry_exit_signal_set_frozen": True,
        "dynamic_cluster_point_in_time": True,
        "dynamic_trim_executes_next_open": True,
        "systemic_signal_point_in_time": True,
        "systemic_exposure_applies_next_session": True,
        "all_layers_charge_explicit_friction": True,
        "famous_case_selection_bias_warning": True,
        "survivorship_aware_all_a_required": True,
        "production_deployment_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_combined_risk_stack_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    lines = [
        "# Historical Combined Risk Stack",
        "",
        f"- period: {start_date} to {end_date}",
        f"- frozen events: {len(events)}",
        f"- naive CAGR/MDD: {naive_metrics.cagr_pct:.4f}% / {naive_metrics.max_drawdown_pct:.4f}%",
        "- stock entry/exit events remain frozen",
        "- dynamic/concentration trims execute next observed open",
        "- broad-index exposure decisions apply only to the next session",
        "- deployment remains blocked pending survivorship-aware All-A validation",
        "",
        "## Comparison",
    ]
    for row in comparison:
        lines.append(
            f"- {row['name']} | CAGR={row['cagr_pct']}% | MDD={row['max_drawdown_pct']}% | "
            f"Calmar={row['calmar_ratio']} | retention={row['cagr_retention_vs_naive_pct']}% | "
            f"DD improvement={row['drawdown_improvement_vs_naive_pct']}% | accepted={row['accepted']}"
        )
    (output_dir / "historical_combined_risk_stack.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--index-cache-dir", type=Path, default=Path("data/cache/systemic_index_guard"))
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
    return 0 if summary["data_ready_case_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
