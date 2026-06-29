"""Report writers for GenGe Cycle Bottom Strategy."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .backtest import BALANCED_EXIT_POLICY_NAME, EVAL_WINDOWS, EXIT_POLICY_EXPERIMENTS, EXIT_POLICY_NAME


SIGNAL_DETAIL_COLUMNS = [
    "code",
    "stock_name",
    "as_of_date",
    "signal_type",
    "total_score",
    "price_percentile_score",
    "valuation_score",
    "financial_safety_score",
    "trend_stabilization_score",
    "market_environment_score",
    "industry_cycle_score",
    "industry",
    "industry_cycle_phase",
    "market_environment_state",
    "price_percentile_3y",
    "price_percentile_5y",
    "price_percentile_10y",
    "distance_from_5y_low_pct",
    "distance_from_5y_high_pct",
    "distance_from_10y_low_pct",
    "distance_from_10y_high_pct",
    "history_sufficiency_score",
    "history_sufficiency_quality",
    "long_term_position_risk_score",
    "distance_to_ma250_pct",
    "ma250_slope_pct",
    "stabilization_days",
    "downtrend_exhaustion_score",
    "reclaim_ma_score",
    "no_falling_knife_filter",
    "second_low_confirmation",
    "trend_confirmation_level",
    "value_trap_score",
    "value_trap_flag",
    "valuation_repair_signal",
    "industry_cycle_quality",
    "dynamic_stop_loss",
    "stop_loss_distance_pct",
    "invalidation_level",
    "execution_risk_score",
    "entry_price",
    "entry_date",
    "entry_mode",
    "suspended_or_missing_bar",
    "limit_up_entry_risk",
    "limit_down_entry_risk",
    "limit_down_exit_risk",
    "abnormal_gap_open",
    "low_liquidity_risk",
    "executable_entry_quality",
    "entry_open_change_pct",
    "entry_close_available",
    "stop_loss",
    "take_profit",
    "max_position_pct",
    "raw_return_20d",
    "raw_return_60d",
    "raw_return_120d",
    "raw_return_250d",
    "net_return_20d",
    "net_return_60d",
    "net_return_120d",
    "net_return_250d",
    "stop_adjusted_return_20d",
    "stop_adjusted_return_60d",
    "stop_adjusted_return_120d",
    "stop_adjusted_return_250d",
    "stop_adjusted_net_return_20d",
    "stop_adjusted_net_return_60d",
    "stop_adjusted_net_return_120d",
    "stop_adjusted_net_return_250d",
    "stop_triggered_20d",
    "stop_triggered_60d",
    "stop_triggered_120d",
    "stop_triggered_250d",
    "exit_policy_name",
    "exit_date_20d",
    "exit_date_60d",
    "exit_date_120d",
    "exit_date_250d",
    "exit_reason_20d",
    "exit_reason_60d",
    "exit_reason_120d",
    "exit_reason_250d",
    "exit_price_20d",
    "exit_price_60d",
    "exit_price_120d",
    "exit_price_250d",
    "exit_adjusted_raw_return_20d",
    "exit_adjusted_raw_return_60d",
    "exit_adjusted_raw_return_120d",
    "exit_adjusted_raw_return_250d",
    "exit_adjusted_net_return_20d",
    "exit_adjusted_net_return_60d",
    "exit_adjusted_net_return_120d",
    "exit_adjusted_net_return_250d",
    "exit_adjusted_max_drawdown_20d",
    "exit_adjusted_max_drawdown_60d",
    "exit_adjusted_max_drawdown_120d",
    "exit_adjusted_max_drawdown_250d",
    "exit_holding_days_20d",
    "exit_holding_days_60d",
    "exit_holding_days_120d",
    "exit_holding_days_250d",
    "post_entry_adverse_excursion_pct",
    "future_return_20d",
    "future_return_60d",
    "future_return_120d",
    "future_return_250d",
    "close_max_drawdown_20d",
    "close_max_drawdown_60d",
    "close_max_drawdown_120d",
    "close_max_drawdown_250d",
    "low_max_drawdown_20d",
    "low_max_drawdown_60d",
    "low_max_drawdown_120d",
    "low_max_drawdown_250d",
    "max_drawdown_20d",
    "max_drawdown_60d",
    "max_drawdown_120d",
    "max_drawdown_250d",
    "benchmark_return_20d",
    "benchmark_return_60d",
    "benchmark_return_120d",
    "benchmark_return_250d",
    "outperform_benchmark_20d",
    "outperform_benchmark_60d",
    "outperform_benchmark_120d",
    "outperform_benchmark_250d",
    "hit_stop_loss_20d",
    "hit_stop_loss_60d",
    "hit_stop_loss_120d",
    "hit_stop_loss_250d",
    "hit_stop_loss",
    "risk_flags",
    "missing_fields",
    "invalidation_reason",
    "explanation",
]


def _append_unique_columns(columns: List[str], extra_columns: List[str]) -> None:
    seen = set(columns)
    for column in extra_columns:
        if column not in seen:
            columns.append(column)
            seen.add(column)


_BALANCED_DETAIL_COLUMNS: List[str] = ["balanced_exit_policy_name"]
for _days in EVAL_WINDOWS:
    for _metric in (
        "exit_date",
        "exit_reason",
        "exit_price",
        "exit_adjusted_raw_return",
        "exit_adjusted_net_return",
        "exit_adjusted_max_drawdown",
        "exit_holding_days",
    ):
        _BALANCED_DETAIL_COLUMNS.append(f"{BALANCED_EXIT_POLICY_NAME}_{_metric}_{_days}d")
for _experiment in EXIT_POLICY_EXPERIMENTS:
    for _days in EVAL_WINDOWS:
        for _metric in (
            "exit_reason",
            "exit_adjusted_net_return",
            "exit_adjusted_max_drawdown",
            "exit_holding_days",
        ):
            _BALANCED_DETAIL_COLUMNS.append(f"exit_policy_experiment_{_experiment}_{_metric}_{_days}d")
_append_unique_columns(SIGNAL_DETAIL_COLUMNS, _BALANCED_DETAIL_COLUMNS)


def _run_dir(output_dir: str | Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _format_pct(value: Any) -> str:
    if value is None:
        return "无可用数据"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _format_value(value: Any) -> str:
    if value is None:
        return "无可用数据"
    return str(value)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def _top_group_lines(title: str, grouped: Dict[str, Any], limit: int = 8) -> List[str]:
    lines = [f"## {title}", ""]
    if not grouped:
        return lines + ["- 无可用数据", ""]
    ordered = sorted(
        grouped.items(),
        key=lambda item: int((item[1] or {}).get("total_signals") or 0),
        reverse=True,
    )
    for name, metrics in ordered[:limit]:
        metrics = metrics or {}
        lines.append(
            "- "
            f"{name}: 样本 {metrics.get('total_signals', 0)}，"
            f"60日胜率 {_format_pct(metrics.get('win_rate_60d'))}，"
            f"60日平均净收益 {_format_pct(metrics.get('avg_net_return_60d'))}，"
            f"250日低点回撤 {_format_pct(metrics.get('low_max_drawdown_250d'))}，"
            f"判断 {metrics.get('verdict', '无可用数据')}"
        )
    lines.append("")
    return lines


def _failure_reason_text(summary: Dict[str, Any]) -> List[str]:
    failure = summary.get("failure_reason_summary") or {}
    reasons = failure.get("reason_counts") or {}
    industry_drag = failure.get("industry_drag") or {}
    signal_type_summary = summary.get("signal_type_summary") or {}
    expectancy = summary.get("expectancy_diagnostics") or {}
    top_reasons = "、".join(f"{key}({value})" for key, value in list(reasons.items())[:5]) or "样本不足，暂无法归因"
    drag_industries = "、".join(list(industry_drag.keys())[:5]) or "无可用数据"
    signal_order = sorted(
        signal_type_summary.items(),
        key=lambda item: ((item[1] or {}).get("avg_net_return_60d") is None, (item[1] or {}).get("avg_net_return_60d") or -999),
        reverse=True,
    )
    best_signal = signal_order[0][0] if signal_order else "无可用数据"
    worst_signal = signal_order[-1][0] if signal_order else "无可用数据"
    lines = [
        "## 失败原因诊断",
        "",
        f"- 策略当前主要失败原因可能是：{top_reasons}。",
        f"- 拖累较大的行业包括：{drag_industries}。",
        f"- LEFT_SMALL_BUY 和 CONFIRM_BUY 谁更有效：当前 60 日平均净收益较好的信号类型是 {best_signal}，较弱的是 {worst_signal}。",
        f"- 是否应该缩短持有周期：{'是，当前短周期相对更好' if expectancy.get('short_horizon_better') else '暂不能仅凭当前样本判断'}。",
        f"- 是否应该提高趋势确认门槛：若趋势未确认、买太早或止损不够严格占比靠前，应继续提高 CONFIRM_BUY 趋势门槛并降低左侧信号仓位。",
        "",
    ]
    return lines


def _time_split_lines(summary: Dict[str, Any]) -> List[str]:
    split = summary.get("time_split_summary") or {}
    labels = {
        "first_half": "前半段历史",
        "second_half": "后半段历史",
        "recent_2y": "最近两年",
    }
    lines = ["## 时间切片", ""]
    for key, label in labels.items():
        metrics = split.get(key) or {}
        lines.append(
            f"- {label}: 样本 {metrics.get('total_signals', 0)}，"
            f"60日胜率 {_format_pct(metrics.get('win_rate_60d'))}，"
            f"60日平均净收益 {_format_pct(metrics.get('avg_net_return_60d'))}，"
            f"250日低点回撤 {_format_pct(metrics.get('low_max_drawdown_250d'))}，"
            f"判断 {metrics.get('verdict', '无可用数据')}"
        )
    lines.append("")
    return lines


def _baseline_lines(summary: Dict[str, Any]) -> List[str]:
    comparison = summary.get("baseline_comparison") or {}
    lines = ["## 基线对比", ""]
    if not comparison.get("available"):
        return lines + ["- 未匹配到本次运行的 core/cycle/broad 基线，无法做自动对比。", ""]
    metrics = comparison.get("metrics") or {}
    label_map = {
        "total_signals": "样本数",
        "avg_net_return_60d": "60日平均净收益",
        "win_rate_60d": "60日胜率",
        "outperform_benchmark_rate_60d": "60日跑赢基准比例",
        "avg_low_max_drawdown_250d": "250日低点平均回撤",
    }
    lines.append(
        f"- 基线组：{comparison.get('baseline_group')}；基线 commit：{comparison.get('baseline_commit')}；"
        f"总体判断：{'改善' if comparison.get('overall_improved') else '未达到整体改善'}。"
    )
    lines.append(
        f"- 样本数变化：{_format_pct(comparison.get('sample_count_change_pct'))}；"
        f"过拟合/样本骤降警告：{'是' if comparison.get('overfit_warning') else '否'}。"
    )
    for field_name, label in label_map.items():
        item = metrics.get(field_name) or {}
        lines.append(
            f"- {label}: 当前 {_format_value(item.get('current'))}，"
            f"基线 {_format_value(item.get('baseline'))}，"
            f"变化 {_format_value(item.get('delta'))}，"
            f"{'改善' if item.get('improved') is True else '未改善' if item.get('improved') is False else '无法比较'}。"
        )
    lines.append("")
    return lines


def _quality_lines(summary: Dict[str, Any]) -> List[str]:
    stop_policy = summary.get("stop_policy_summary") or {}
    filters = summary.get("quality_filter_summary") or {}
    lines = [
        "## 信号质量与止损政策",
        "",
        f"- 趋势确认分布：{json.dumps(summary.get('trend_confirmation_summary', {}), ensure_ascii=False)}",
        f"- 行业周期证据质量分布：{json.dumps(summary.get('industry_cycle_quality_summary', {}), ensure_ascii=False)}",
        f"- 执行入口质量分布：{json.dumps(summary.get('execution_entry_quality_summary', {}), ensure_ascii=False)}",
        f"- 执行风险分数分布：{json.dumps(summary.get('execution_risk_score_distribution', {}), ensure_ascii=False)}",
        f"- 分执行风险表现：{json.dumps(summary.get('execution_risk_score_summary', {}), ensure_ascii=False)}",
        f"- 历史样本质量分布：{json.dumps(summary.get('history_sufficiency_quality_summary', {}), ensure_ascii=False)}",
        f"- 长周期位置风险分布：{json.dumps(summary.get('long_term_position_risk_score_summary', {}), ensure_ascii=False)}",
        f"- 估值陷阱/飞刀/执行风险统计：{json.dumps(filters, ensure_ascii=False)}",
        f"- 止损修正 60/120/250 日平均净收益：{_format_pct(stop_policy.get('avg_stop_adjusted_net_return_60d'))} / {_format_pct(stop_policy.get('avg_stop_adjusted_net_return_120d'))} / {_format_pct(stop_policy.get('avg_stop_adjusted_net_return_250d'))}",
        f"- 止损触发率 60/120/250 日：{_format_pct(stop_policy.get('stop_trigger_rate_60d'))} / {_format_pct(stop_policy.get('stop_trigger_rate_120d'))} / {_format_pct(stop_policy.get('stop_trigger_rate_250d'))}",
        f"- 止损是否改善长期收益代理：{'是' if stop_policy.get('reduced_drawdown_proxy') else '否'}；是否可能截断反弹代理：{'是' if stop_policy.get('may_cut_rebound_proxy') else '否'}。",
        "",
    ]
    return lines


def _exit_policy_lines(summary: Dict[str, Any]) -> List[str]:
    exit_summary = summary.get("exit_policy_summary") or {}
    comparison = summary.get("raw_stop_exit_comparison") or {}
    hybrid = exit_summary.get(EXIT_POLICY_NAME) or {}
    balanced = exit_summary.get(BALANCED_EXIT_POLICY_NAME) or {}
    raw_hold = exit_summary.get("raw_hold") or {}
    diagnostics = summary.get("exit_reason_diagnostics") or {}
    worst_reason = diagnostics.get("worst_return_reason") or "无可用数据"
    reason_metrics = (diagnostics.get("by_reason") or {}).get(worst_reason) or {}
    lines = [
        "## 60 日修复策略与退出机制",
        "",
        "- strategy_primary_horizon = 60d",
        "- strategy_secondary_horizon = 20d/120d",
        "- strategy_risk_horizon = 250d",
        "- 250 日 raw hold 是“如果死拿”的风险压力测试；exit_adjusted 250 日是按退出策略模拟后的风险。本策略不默认持有到 250 日。",
        f"- raw_hold 60 日净收益：{_format_pct(raw_hold.get('avg_exit_adjusted_net_return_60d'))}；250 日低点回撤：{_format_pct(raw_hold.get('avg_exit_adjusted_max_drawdown_250d'))}。",
        f"- {EXIT_POLICY_NAME} 60 日退出净收益：{_format_pct(hybrid.get('avg_exit_adjusted_net_return_60d'))}；250 日退出回撤：{_format_pct(hybrid.get('avg_exit_adjusted_max_drawdown_250d'))}；回撤降低比例：{_format_pct(hybrid.get('drawdown_reduction_rate_250d'))}。",
        f"- {BALANCED_EXIT_POLICY_NAME} 60 日退出净收益：{_format_pct(balanced.get('avg_exit_adjusted_net_return_60d'))}；收益保留率：{_format_pct(balanced.get('return_retention_rate_60d'))}；250 日退出回撤：{_format_pct(balanced.get('avg_exit_adjusted_max_drawdown_250d'))}；回撤降低比例：{_format_pct(balanced.get('drawdown_reduction_rate_250d'))}；综合效率分：{_format_value(balanced.get('exit_efficiency_score'))}。",
        "",
        "### Raw Hold / Stop / Exit 对比",
        "",
    ]
    for key in ("20d", "60d", "120d", "250d"):
        item = comparison.get(key) or {}
        lines.append(
            f"- {key}: raw 净收益 {_format_pct(item.get('raw_hold_avg_net_return'))}，"
            f"stop 修正净收益 {_format_pct(item.get('stop_adjusted_avg_net_return'))}，"
            f"exit 修正净收益 {_format_pct(item.get('exit_policy_avg_net_return'))}；"
            f"raw 低点回撤 {_format_pct(item.get('raw_hold_avg_low_drawdown'))}，"
            f"exit 回撤 {_format_pct(item.get('exit_policy_avg_max_drawdown'))}。"
        )
    lines.extend(["", "### Exit Policy 对比", ""])
    best_drawdown = None
    worst_return_impact = None
    for name, metrics in exit_summary.items():
        if not isinstance(metrics, dict):
            continue
        lines.append(
            f"- {name}: 60日退出净收益 {_format_pct(metrics.get('avg_exit_adjusted_net_return_60d'))}，"
            f"60日胜率 {_format_pct(metrics.get('win_rate_exit_adjusted_60d'))}，"
            f"60日跑赢基准 {_format_pct(metrics.get('outperform_benchmark_exit_adjusted_60d'))}，"
            f"250日退出回撤 {_format_pct(metrics.get('avg_exit_adjusted_max_drawdown_250d'))}，"
            f"平均持有 {metrics.get('avg_holding_days', '无可用数据')} 天，"
            f"收益保留 {_format_pct(metrics.get('return_retention_rate_60d'))}，"
            f"回撤降低 {_format_pct(metrics.get('drawdown_reduction_rate_250d'))}。"
        )
        dd_reduction = metrics.get("exit_policy_drawdown_reduction_pct")
        return_impact = metrics.get("exit_policy_return_impact_pct")
        if best_drawdown is None or (dd_reduction is not None and dd_reduction > (best_drawdown[1] if best_drawdown else -999)):
            best_drawdown = (name, dd_reduction)
        if worst_return_impact is None or (return_impact is not None and return_impact < (worst_return_impact[1] if worst_return_impact else 999)):
            worst_return_impact = (name, return_impact)
    lines.extend(
        [
            "",
            f"- 哪个 exit policy 最稳定：优先看 {BALANCED_EXIT_POLICY_NAME} 的 validation/recent_2y、收益保留率和 250 日回撤降低率；旧 {EXIT_POLICY_NAME} 保留为风险压缩对照。",
            f"- 哪个 exit policy 降低回撤最多：{best_drawdown[0] if best_drawdown else '无可用数据'}（{_format_pct(best_drawdown[1] if best_drawdown else None)}）。",
            f"- 哪个 exit policy 对收益伤害最大：{worst_return_impact[0] if worst_return_impact else '无可用数据'}（{_format_pct(worst_return_impact[1] if worst_return_impact else None)}）。",
            f"- balanced 退出原因中最拖累收益的是：{worst_reason}，该原因 60 日退出平均净收益 {_format_pct(reason_metrics.get('avg_exit_adjusted_net_return_60d'))}；下一步：{diagnostics.get('next_step', '无可用数据')}",
            f"- 60d 修复策略是否成立：需要结合 broad 真实运行指标判断；balanced 若能保留 60 日收益并明显降低 250 日 raw hold 风险，才可提高到平衡退出策略验证。",
            f"- 是否应该把主周期定义为 60d：是，当前报告将 60d 作为主观察周期，120d 只作延伸观察，250d 只作风险压力测试。",
            f"- 当前是否可以进入模拟观察候选：严格候选 {summary.get('strict_observation_candidate_count', 0)}，研究候选 {summary.get('research_observation_candidate_count', 0)}；仍需人工复核公开数据。",
            "- 为什么仍然不是交易建议：本系统不接券商、不读取账户、不自动下单，所有输出只用于模拟观察和复盘。",
            "",
        ]
    )
    return lines


def _sample_warning(summary: Dict[str, Any]) -> str:
    total = int(summary.get("total_signals") or 0)
    if total < 100:
        return "样本数量不足 100，不能据此进入模拟盘。"
    if total < 300:
        return "样本数量已超过最低门槛，但仍偏少，需要更大真实股票池复核。"
    return "样本数量达到研究统计门槛，但仍需检查数据质量与市场阶段分布。"


def _conclusion(summary: Dict[str, Any]) -> str:
    total = int(summary.get("total_signals") or 0)
    avg_60d = summary.get("avg_return_60d")
    win_60d = summary.get("win_rate_60d")
    drawdown = summary.get("avg_max_drawdown")
    if total == 0:
        return "第一版结论：样本未触发可验证信号，需要扩大股票池、补充估值/财务数据后继续研究。"
    if avg_60d is not None and win_60d is not None and avg_60d > 0 and win_60d >= 50:
        return "第一版结论：样本呈现正向迹象，可继续研究，但仍需扩大样本和检查交易成本。"
    if drawdown is not None and drawdown < -20:
        return "第一版结论：回撤压力偏大，需要调整过滤和风控参数，暂不适合直接实盘。"
    return "第一版结论：结果仍需调整和复核，暂不适合直接实盘。"


def write_signal_details(rows: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SIGNAL_DETAIL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in SIGNAL_DETAIL_COLUMNS})


def write_baseline_comparison(summary: Dict[str, Any], path: Path) -> None:
    comparison = summary.get("baseline_comparison") or {}
    path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")


def write_parameter_experiment(summary: Dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    experiment = summary.get("parameter_experiment") or {}
    json_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 参数实验摘要",
        "",
        f"- 结论：{experiment.get('conclusion', '无可用数据')}",
        f"- 推荐组合：{experiment.get('recommended') or '无稳定推荐'}",
        "",
    ]
    for name, result in (experiment.get("experiments") or {}).items():
        lines.append(f"## {name}")
        for split_name in ("train", "validation", "recent_2y"):
            metrics = (result or {}).get(split_name) or {}
            lines.append(
                f"- {split_name}: 样本 {metrics.get('total_signals', 0)}，"
                f"60日平均净收益 {_format_pct(metrics.get('avg_net_return_60d'))}，"
                f"60日胜率 {_format_pct(metrics.get('win_rate_60d'))}，"
                f"60日跑赢基准 {_format_pct(metrics.get('outperform_benchmark_rate_60d'))}"
            )
        lines.append("")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_exit_policy_experiment(summary: Dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    experiment = summary.get("exit_policy_experiment") or {}
    json_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 退出策略参数实验",
        "",
        f"- 策略：{experiment.get('policy', 'hybrid_60d_repair_exit')}",
        f"- 结论：{experiment.get('conclusion', '无可用数据')}",
        f"- 推荐参数：{experiment.get('recommended') or '无稳定推荐'}",
        f"- 推荐说明：{experiment.get('recommendation_reason', '无可用数据')}",
        "",
        "说明：本实验只用于模拟观察和复盘，不构成买入建议，不应自动交易。",
        "",
    ]
    for name, result in (experiment.get("experiments") or {}).items():
        params = result.get("params") or {}
        lines.append(f"## {name}")
        lines.append(f"- 参数：{json.dumps(params, ensure_ascii=False)}")
        for split_name in ("train", "validation", "recent_2y", "all"):
            metrics = (result or {}).get(split_name) or {}
            lines.append(
                f"- {split_name}: 样本 {metrics.get('total_signals', 0)}，"
                f"60日退出净收益 {_format_pct(metrics.get('avg_exit_adjusted_net_return_60d'))}，"
                f"60日退出胜率 {_format_pct(metrics.get('win_rate_exit_adjusted_60d'))}，"
                f"60日跑赢基准 {_format_pct(metrics.get('outperform_benchmark_exit_adjusted_60d'))}，"
                f"250日退出回撤 {_format_pct(metrics.get('avg_exit_adjusted_max_drawdown_250d'))}，"
                f"收益保留 {_format_pct(metrics.get('return_retention_rate_60d'))}，"
                f"回撤降低 {_format_pct(metrics.get('drawdown_reduction_rate_250d'))}，"
                f"效率分 {_format_value(metrics.get('exit_efficiency_score'))}"
            )
        lines.append(
            f"- 过拟合警告：{'是' if result.get('overfit_warning') else '否'}；"
            f"最近两年不稳定：{'是' if result.get('recent_2y_unstable') else '否'}"
        )
        lines.append("")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_reason(row: Dict[str, Any]) -> str:
    parts = []
    if row.get("price_percentile_5y") is not None:
        parts.append(f"5年价格分位 {float(row['price_percentile_5y']):.1%}")
    if row.get("trend_confirmation_level"):
        parts.append(f"趋势确认 {row.get('trend_confirmation_level')}")
    if row.get("valuation_repair_signal"):
        parts.append("估值修复信号存在")
    if row.get("industry_cycle_phase"):
        parts.append(f"行业周期 {row.get('industry_cycle_phase')}")
    if row.get("long_term_position_risk_score") is not None:
        parts.append(f"长周期位置风险分 {float(row['long_term_position_risk_score']):.1f}")
    return "；".join(parts) or "触发研究信号，需人工复核公开数据"


def _observation_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trend_rank = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}

    def number(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return None if result != result else result

    candidates = []
    for row in rows:
        stop_distance = number(row.get("stop_loss_distance_pct"))
        execution_risk = number(row.get("execution_risk_score")) or 0.0
        value_trap_score = number(row.get("value_trap_score")) or 0.0
        market_score = number(row.get("market_environment_score")) or 0.0
        long_term_risk = number(row.get("long_term_position_risk_score")) or 0.0
        history_quality = str(row.get("history_sufficiency_quality") or "limited")
        if (
            str(row.get("signal_type") or "") == "CONFIRM_BUY"
            and trend_rank.get(str(row.get("trend_confirmation_level") or "NONE"), 0) >= trend_rank["MEDIUM"]
            and value_trap_score < 60
            and long_term_risk <= 45
            and history_quality not in {"insufficient", "limited"}
            and stop_distance is not None
            and stop_distance <= 12
            and execution_risk <= 25
            and str(row.get("industry_cycle_quality") or "missing") not in {"missing", "manual_template"}
            and market_score >= 40
        ):
            candidates.append(row)
    return candidates


def _research_observation_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trend_rank = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}

    def number(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return None if result != result else result

    candidates = []
    for row in rows:
        signal_type = str(row.get("signal_type") or "")
        trend_level = str(row.get("trend_confirmation_level") or "NONE")
        total_score = number(row.get("total_score")) or 0.0
        stop_distance = number(row.get("stop_loss_distance_pct"))
        execution_risk = number(row.get("execution_risk_score")) or 0.0
        value_trap_score = number(row.get("value_trap_score")) or 0.0
        long_term_risk = number(row.get("long_term_position_risk_score")) or 0.0
        entry_quality = str(row.get("executable_entry_quality") or "")
        high_quality_left = (
            signal_type == "LEFT_SMALL_BUY"
            and total_score >= 72
            and trend_rank.get(trend_level, 0) >= trend_rank["MEDIUM"]
        )
        confirm = signal_type == "CONFIRM_BUY" and trend_rank.get(trend_level, 0) >= trend_rank["MEDIUM"]
        if (
            (confirm or high_quality_left)
            and value_trap_score < 70
            and long_term_risk < 60
            and stop_distance is not None
            and stop_distance <= 15
            and execution_risk < 60
            and entry_quality not in {"risky", "unavailable"}
        ):
            candidates.append(row)
    return candidates


def _balanced_research_observation_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trend_rank = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}

    def number(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return None if result != result else result

    candidates = []
    for row in rows:
        signal_type = str(row.get("signal_type") or "")
        trend_level = str(row.get("trend_confirmation_level") or "NONE")
        stop_distance = number(row.get("stop_loss_distance_pct"))
        execution_risk = number(row.get("execution_risk_score")) or 0.0
        value_trap_score = number(row.get("value_trap_score")) or 0.0
        long_term_risk = number(row.get("long_term_position_risk_score")) or 0.0
        entry_quality = str(row.get("executable_entry_quality") or "")
        balanced_return = number(row.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d"))
        if (
            signal_type in {"CONFIRM_BUY", "LEFT_SMALL_BUY", "ADD"}
            and trend_rank.get(trend_level, 0) >= trend_rank["MEDIUM"]
            and value_trap_score < 70
            and long_term_risk < 60
            and stop_distance is not None
            and stop_distance <= 15
            and execution_risk < 60
            and entry_quality not in {"risky", "unavailable"}
            and (balanced_return is None or balanced_return > -8)
        ):
            candidates.append(row)
    return candidates


def _watch_only_candidate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []
    for row in rows:
        trend_level = str(row.get("trend_confirmation_level") or "NONE")
        signal_type = str(row.get("signal_type") or "")
        value_trap_score = _number(row.get("value_trap_score")) or 0.0
        execution_risk = _number(row.get("execution_risk_score")) or 0.0
        if signal_type in {"LEFT_SMALL_BUY", "CONFIRM_BUY", "ADD"} and (
            trend_level in {"NONE", "WEAK"}
            or value_trap_score >= 60
            or execution_risk >= 45
            or str(row.get("industry_cycle_quality") or "") in {"missing", "manual_template"}
        ):
            candidates.append(row)
    return candidates


def _candidate_columns() -> List[str]:
    return [
        "code",
        "stock_name",
        "industry",
        "as_of_date",
        "signal_type",
        "total_score",
        "trend_confirmation_level",
        "value_trap_score",
        "exit_policy_name",
        "balanced_exit_policy_name",
        "exit_reason_expected",
        "stop_loss",
        "stop_loss_distance_pct",
        "take_profit_reference",
        "execution_risk_score",
        "max_position_pct_research_only",
        "primary_horizon",
        "reason",
        "invalidation_condition",
        "disclaimer",
    ]


def _candidate_output_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": row.get("code"),
        "stock_name": row.get("stock_name"),
        "industry": row.get("industry"),
        "as_of_date": row.get("as_of_date"),
        "signal_type": row.get("signal_type"),
        "total_score": row.get("total_score"),
        "trend_confirmation_level": row.get("trend_confirmation_level"),
        "value_trap_score": row.get("value_trap_score"),
        "exit_policy_name": row.get("exit_policy_name") or "hybrid_60d_repair_exit",
        "balanced_exit_policy_name": row.get("balanced_exit_policy_name") or BALANCED_EXIT_POLICY_NAME,
        "exit_reason_expected": row.get(f"{BALANCED_EXIT_POLICY_NAME}_exit_reason_60d") or row.get("exit_reason_60d") or "60d repair observation",
        "stop_loss": row.get("stop_loss"),
        "stop_loss_distance_pct": row.get("stop_loss_distance_pct"),
        "take_profit_reference": row.get("take_profit"),
        "execution_risk_score": row.get("execution_risk_score"),
        "max_position_pct_research_only": row.get("max_position_pct"),
        "primary_horizon": "60d",
        "reason": _candidate_reason(row),
        "invalidation_condition": row.get("invalidation_reason"),
        "disclaimer": "仅用于模拟观察和复盘，不构成买入建议，不应自动交易。",
    }


def _write_candidate_file(candidates: List[Dict[str, Any]], path: Path) -> None:
    columns = _candidate_columns()
    candidates = sorted(
        candidates,
        key=lambda row: (_number(row.get("total_score")) or 0.0, -(_number(row.get("value_trap_score")) or 0.0)),
        reverse=True,
    )[:50]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        if not candidates:
            writer.writerow({"disclaimer": "仅用于模拟观察和复盘，不构成买入建议，不应自动交易。"})
            return
        for row in candidates:
            writer.writerow(_candidate_output_row(row))


def write_paper_observation_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    _write_candidate_file(_observation_candidate_rows(rows), path)


def write_strict_observation_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    _write_candidate_file(_observation_candidate_rows(rows), path)


def write_research_observation_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    _write_candidate_file(_research_observation_candidate_rows(rows), path)


def write_balanced_research_observation_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    _write_candidate_file(_balanced_research_observation_candidate_rows(rows), path)


def write_watch_only_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    _write_candidate_file(_watch_only_candidate_rows(rows), path)


def write_summary_markdown(summary: Dict[str, Any], path: Path) -> None:
    diagnostics = summary.get("diagnostics") or {}
    missing_fields = diagnostics.get("missing_fields") or {}
    risk_flags = diagnostics.get("risk_flags") or {}
    execution = summary.get("execution_diagnostics") or diagnostics.get("execution_diagnostics") or {}
    coverage = diagnostics.get("coverage") or {}
    best_signal_type = diagnostics.get("best_signal_type_by_avg_60d_return") or "无可用数据"
    best_horizon = diagnostics.get("best_return_horizon_by_average") or "无可用数据"
    best_signals = summary.get("best_signals") or []
    worst_signals = summary.get("worst_signals") or []
    gate = summary.get("paper_trading_gate") or {}
    lines = [
        "# 根哥周期底部硬逻辑策略 - 第一版回测摘要",
        "",
        "## 本次回测范围",
        "",
        f"- 开始日期：{diagnostics.get('start_date', '无可用数据')}",
        f"- 结束日期：{diagnostics.get('end_date', '无可用数据')}",
        f"- 股票池：{json.dumps(diagnostics.get('requested_codes', []), ensure_ascii=False)}",
        f"- 扫描步长：{diagnostics.get('step_days', '无可用数据')} 个交易日",
        f"- 入场模式：默认 next_open，缺失时回退 next_close",
        f"- 交易成本：fee_bps={diagnostics.get('fee_bps', '无可用数据')}，slippage_bps={diagnostics.get('slippage_bps', '无可用数据')}",
        f"- 估值数据源：{diagnostics.get('valuation_provider', '无可用数据')}；财务数据源：{diagnostics.get('financial_provider', '无可用数据')}",
        f"- 行业周期来源：{diagnostics.get('industry_cycle_source', '无可用数据')}",
        "",
        "## 核心结果",
        "",
        f"- 触发可验证信号数量：{summary.get('total_signals', 0)}",
        f"- 信号分布：{json.dumps(summary.get('signals_by_type', {}), ensure_ascii=False)}",
        f"- 表现较好的信号类型：{best_signal_type}",
        f"- 平均收益较好的验证周期：{best_horizon}",
        f"- 20 日净收益胜率 / 平均净收益 / 中位数净收益：{_format_pct(summary.get('win_rate_20d'))} / {_format_pct(summary.get('avg_return_20d'))} / {_format_pct(summary.get('median_return_20d'))}",
        f"- 60 日净收益胜率 / 平均净收益 / 中位数净收益：{_format_pct(summary.get('win_rate_60d'))} / {_format_pct(summary.get('avg_return_60d'))} / {_format_pct(summary.get('median_return_60d'))}",
        f"- 120 日净收益胜率 / 平均净收益 / 中位数净收益：{_format_pct(summary.get('win_rate_120d'))} / {_format_pct(summary.get('avg_return_120d'))} / {_format_pct(summary.get('median_return_120d'))}",
        f"- 250 日净收益胜率 / 平均净收益 / 中位数净收益：{_format_pct(summary.get('win_rate_250d'))} / {_format_pct(summary.get('avg_return_250d'))} / {_format_pct(summary.get('median_return_250d'))}",
        f"- 平均最大回撤：{_format_pct(summary.get('avg_max_drawdown'))}（默认使用 low_max_drawdown）",
        f"- 最差最大回撤：{_format_pct(summary.get('max_drawdown_worst'))}",
        f"- 20/60/120/250 日跑赢基准比例：{_format_pct(summary.get('outperform_benchmark_rate_20d'))} / {_format_pct(summary.get('outperform_benchmark_rate_60d'))} / {_format_pct(summary.get('outperform_benchmark_rate_120d'))} / {_format_pct(summary.get('outperform_benchmark_rate_250d'))}",
        f"- 估值/财务/行业周期覆盖率：{_format_pct(summary.get('valuation_coverage_rate'))} / {_format_pct(summary.get('financial_coverage_rate'))} / {_format_pct(summary.get('industry_cycle_coverage_rate'))}",
        f"- 最大连续亏损次数：{_format_value(summary.get('max_consecutive_losses'))}",
        f"- 模拟观察候选数：{_format_value(summary.get('paper_observation_candidate_count'))}",
        f"- 样本数量警告：{_sample_warning(summary)}",
        f"- 最好历史信号：{json.dumps(best_signals[:3], ensure_ascii=False)}",
        f"- 最差历史信号：{json.dumps(worst_signals[:3], ensure_ascii=False)}",
        "",
        "## 分持有周期结果",
        "",
        f"- 20 日：胜率 {_format_pct(summary.get('win_rate_20d'))}，平均净收益 {_format_pct(summary.get('avg_net_return_20d'))}，跑赢基准 {_format_pct(summary.get('outperform_benchmark_rate_20d'))}",
        f"- 60 日：胜率 {_format_pct(summary.get('win_rate_60d'))}，平均净收益 {_format_pct(summary.get('avg_net_return_60d'))}，跑赢基准 {_format_pct(summary.get('outperform_benchmark_rate_60d'))}",
        f"- 120 日：胜率 {_format_pct(summary.get('win_rate_120d'))}，平均净收益 {_format_pct(summary.get('avg_net_return_120d'))}，跑赢基准 {_format_pct(summary.get('outperform_benchmark_rate_120d'))}",
        f"- 250 日：胜率 {_format_pct(summary.get('win_rate_250d'))}，平均净收益 {_format_pct(summary.get('avg_net_return_250d'))}，跑赢基准 {_format_pct(summary.get('outperform_benchmark_rate_250d'))}",
        "",
    ]
    lines.extend(_top_group_lines("分行业结果", summary.get("industry_summary") or {}))
    lines.extend(_top_group_lines("分 Signal Type 结果", summary.get("signal_type_summary") or {}))
    lines.extend(_top_group_lines("分 Market Environment 结果", summary.get("market_environment_summary") or {}))
    lines.extend(_top_group_lines("分 Industry Cycle Phase 结果", summary.get("industry_cycle_phase_summary") or {}))
    lines.extend(_time_split_lines(summary))
    lines.extend(_baseline_lines(summary))
    lines.extend(_quality_lines(summary))
    lines.extend(_exit_policy_lines(summary))
    lines.extend(_failure_reason_text(summary))
    lines.extend(
        [
            "## 风险与缺失",
            "",
            f"- 主要风险标签：{json.dumps(risk_flags, ensure_ascii=False) if risk_flags else '无'}",
            f"- 数据缺失字段：{json.dumps(missing_fields, ensure_ascii=False) if missing_fields else '无'}",
            f"- 数据缺口统计：{json.dumps(diagnostics.get('data_gap_counts', {}), ensure_ascii=False)}",
            f"- 覆盖率统计：{json.dumps(coverage or {'valuation_coverage_rate': summary.get('valuation_coverage_rate'), 'financial_coverage_rate': summary.get('financial_coverage_rate')}, ensure_ascii=False)}",
            f"- PE/PB/财务缺失数量：{summary.get('pe_missing_count', 0)} / {summary.get('pb_missing_count', 0)} / {summary.get('financial_missing_count', 0)}",
            f"- 严格观察候选数 / 研究观察候选数：{summary.get('strict_observation_candidate_count', 0)} / {summary.get('research_observation_candidate_count', 0)}",
            f"- balanced 研究观察候选数 / watch-only 候选数：{summary.get('balanced_research_observation_candidate_count', 0)} / {summary.get('watch_only_candidate_count', 0)}",
            f"- 可执行性诊断：{json.dumps(execution, ensure_ascii=False)}",
            f"- 公开数据 provider_errors：{json.dumps(diagnostics.get('provider_errors', {}), ensure_ascii=False)}",
            f"- 研究验收枚举：{gate.get('verdict', '无可用数据')}；原因：{json.dumps(gate.get('reasons', []), ensure_ascii=False)}",
            "",
            "## 第一版判断",
            "",
            _conclusion(summary),
            "",
            "明确结论：不可实盘。第一版仅可用于研究复核，是否进入模拟盘观察必须结合更大股票池、更稳定估值/财务数据和人工复核。",
            "",
            "说明：本报告只做历史信号验证，不构成投资建议，不接入券商账户，不自动下单。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(rows: List[Dict[str, Any]], summary: Dict[str, Any], output_dir: str | Path) -> Path:
    path = _run_dir(output_dir)
    write_signal_details(rows, path / "signal_details.csv")
    (path / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_baseline_comparison(summary, path / "baseline_comparison.json")
    write_parameter_experiment(summary, path / "parameter_experiment.json", path / "parameter_experiment.md")
    write_exit_policy_experiment(summary, path / "exit_policy_experiment.json", path / "exit_policy_experiment.md")
    write_paper_observation_candidates(rows, path / "paper_observation_candidates.csv")
    write_strict_observation_candidates(rows, path / "strict_observation_candidates.csv")
    write_research_observation_candidates(rows, path / "research_observation_candidates.csv")
    write_balanced_research_observation_candidates(rows, path / "balanced_research_observation_candidates.csv")
    write_watch_only_candidates(rows, path / "watch_only_candidates.csv")
    write_summary_markdown(summary, path / "summary.md")
    return path
