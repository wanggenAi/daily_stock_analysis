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
    "stop_loss",
    "take_profit",
    "max_position_pct",
    "future_return_20d",
    "future_return_60d",
    "future_return_120d",
    "future_return_250d",
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

    lines = [
        "# 根哥周期底部硬逻辑策略 - 第一版回测摘要",
        "",
        "## 核心结果",
        "",
        f"- 触发可验证信号数量：{summary.get('total_signals', 0)}",
        f"- 信号分布：{json.dumps(summary.get('signals_by_type', {}), ensure_ascii=False)}",
        f"- 表现较好的信号类型：{best_signal_type}",
        f"- 平均收益较好的验证周期：{best_horizon}",
        f"- 20 日胜率 / 平均收益 / 中位数收益：{_format_pct(summary.get('win_rate_20d'))} / {_format_pct(summary.get('avg_return_20d'))} / {_format_pct(summary.get('median_return_20d'))}",
        f"- 60 日胜率 / 平均收益 / 中位数收益：{_format_pct(summary.get('win_rate_60d'))} / {_format_pct(summary.get('avg_return_60d'))} / {_format_pct(summary.get('median_return_60d'))}",
        f"- 120 日胜率 / 平均收益 / 中位数收益：{_format_pct(summary.get('win_rate_120d'))} / {_format_pct(summary.get('avg_return_120d'))} / {_format_pct(summary.get('median_return_120d'))}",
        f"- 250 日胜率 / 平均收益 / 中位数收益：{_format_pct(summary.get('win_rate_250d'))} / {_format_pct(summary.get('avg_return_250d'))} / {_format_pct(summary.get('median_return_250d'))}",
        f"- 平均最大回撤：{_format_pct(summary.get('avg_max_drawdown'))}",
        f"- 最差最大回撤：{_format_pct(summary.get('max_drawdown_worst'))}",
        f"- 20/60/120/250 日跑赢基准比例：{_format_pct(summary.get('outperform_benchmark_rate_20d'))} / {_format_pct(summary.get('outperform_benchmark_rate_60d'))} / {_format_pct(summary.get('outperform_benchmark_rate_120d'))} / {_format_pct(summary.get('outperform_benchmark_rate_250d'))}",
        f"- 最大连续亏损次数：{_format_value(summary.get('max_consecutive_losses'))}",
        "",
        "## 风险与缺失",
        "",
        f"- 主要风险标签：{json.dumps(risk_flags, ensure_ascii=False) if risk_flags else '无'}",
        f"- 数据缺失字段：{json.dumps(missing_fields, ensure_ascii=False) if missing_fields else '无'}",
        "",
        "## 第一版判断",
        "",
        _conclusion(summary),
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
