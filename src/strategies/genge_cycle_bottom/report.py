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
    "price_percentile_3y",
    "price_percentile_5y",
    "price_percentile_10y",
    "distance_from_5y_low_pct",
    "distance_from_5y_high_pct",
    "distance_from_10y_low_pct",
    "distance_from_10y_high_pct",
    "entry_price",
    "entry_date",
    "entry_mode",
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


def write_summary_markdown(summary: Dict[str, Any], path: Path) -> None:
    diagnostics = summary.get("diagnostics") or {}
    missing_fields = diagnostics.get("missing_fields") or {}
    risk_flags = diagnostics.get("risk_flags") or {}
    best_signal_type = diagnostics.get("best_signal_type_by_avg_60d_return") or "无可用数据"
    best_horizon = diagnostics.get("best_return_horizon_by_average") or "无可用数据"
    best_signals = summary.get("best_signals") or []
    worst_signals = summary.get("worst_signals") or []
    threshold_pass = (
        (summary.get("total_signals") or 0) > 0
        and (summary.get("avg_return_60d") or 0) > 0
        and (summary.get("avg_return_120d") or 0) > 0
        and (summary.get("avg_max_drawdown") is not None)
    )

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
        f"- 最大连续亏损次数：{_format_value(summary.get('max_consecutive_losses'))}",
        f"- 最好历史信号：{json.dumps(best_signals[:3], ensure_ascii=False)}",
        f"- 最差历史信号：{json.dumps(worst_signals[:3], ensure_ascii=False)}",
        "",
        "## 风险与缺失",
        "",
        f"- 主要风险标签：{json.dumps(risk_flags, ensure_ascii=False) if risk_flags else '无'}",
        f"- 数据缺失字段：{json.dumps(missing_fields, ensure_ascii=False) if missing_fields else '无'}",
        f"- 实盘前门槛：{'通过研究门槛，可继续模拟盘前观察' if threshold_pass else '未通过，需要继续调整或补数据'}",
        "",
        "## 第一版判断",
        "",
        _conclusion(summary),
        "",
        "明确结论：不可实盘。第一版仅可用于研究复核，是否进入模拟盘观察必须结合更大股票池、更稳定估值/财务数据和人工复核。",
        "",
        "说明：本报告只做历史信号验证，不构成投资建议，不接入券商账户，不自动下单。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(rows: List[Dict[str, Any]], summary: Dict[str, Any], output_dir: str | Path) -> Path:
    path = _run_dir(output_dir)
    write_signal_details(rows, path / "signal_details.csv")
    (path / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary_markdown(summary, path / "summary.md")
    return path
