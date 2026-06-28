"""Report writers for GenGe Cycle Bottom Strategy."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


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


def write_paper_observation_candidates(rows: List[Dict[str, Any]], path: Path) -> None:
    columns = [
        "code",
        "stock_name",
        "industry",
        "as_of_date",
        "signal_type",
        "total_score",
        "trend_confirmation_level",
        "value_trap_score",
        "stop_loss_distance_pct",
        "history_sufficiency_quality",
        "long_term_position_risk_score",
        "execution_risk_score",
        "max_position_pct_research_only",
        "reason",
        "invalidation_condition",
        "disclaimer",
    ]
    candidates = _observation_candidate_rows(rows)
    candidates = sorted(
        candidates,
        key=lambda row: (float(row.get("total_score") or 0), -float(row.get("value_trap_score") or 0)),
        reverse=True,
    )[:50]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        if not candidates:
            writer.writerow({"disclaimer": "该清单仅用于模拟观察和复盘，不构成买入建议。"})
            return
        for row in candidates:
            writer.writerow(
                {
                    "code": row.get("code"),
                    "stock_name": row.get("stock_name"),
                    "industry": row.get("industry"),
                    "as_of_date": row.get("as_of_date"),
                    "signal_type": row.get("signal_type"),
                    "total_score": row.get("total_score"),
                    "trend_confirmation_level": row.get("trend_confirmation_level"),
                    "value_trap_score": row.get("value_trap_score"),
                    "stop_loss_distance_pct": row.get("stop_loss_distance_pct"),
                    "history_sufficiency_quality": row.get("history_sufficiency_quality"),
                    "long_term_position_risk_score": row.get("long_term_position_risk_score"),
                    "execution_risk_score": row.get("execution_risk_score"),
                    "max_position_pct_research_only": row.get("max_position_pct"),
                    "reason": _candidate_reason(row),
                    "invalidation_condition": row.get("invalidation_reason"),
                    "disclaimer": "该清单仅用于模拟观察和复盘，不构成买入建议。",
                }
            )


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
    write_paper_observation_candidates(rows, path / "paper_observation_candidates.csv")
    write_summary_markdown(summary, path / "summary.md")
    return path
