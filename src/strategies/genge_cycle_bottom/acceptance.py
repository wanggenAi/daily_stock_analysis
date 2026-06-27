"""Acceptance gate for GenGe Cycle Bottom research reports."""

from __future__ import annotations

from typing import Any, Dict


FAIL_CI = "FAIL_CI"
FAIL_REAL_DATA_FETCH = "FAIL_REAL_DATA_FETCH"
FAIL_DATA_QUALITY = "FAIL_DATA_QUALITY"
FAIL_LOOKAHEAD_RISK = "FAIL_LOOKAHEAD_RISK"
FAIL_STRATEGY_EXPECTANCY = "FAIL_STRATEGY_EXPECTANCY"
PASS_RESEARCH_ONLY = "PASS_RESEARCH_ONLY"
PASS_REAL_DATA_RESEARCH = "PASS_REAL_DATA_RESEARCH"
PASS_PAPER_TRADING_READY = "PASS_PAPER_TRADING_READY"

ACCEPTANCE_ENUMS = (
    FAIL_CI,
    FAIL_REAL_DATA_FETCH,
    FAIL_DATA_QUALITY,
    FAIL_LOOKAHEAD_RISK,
    FAIL_STRATEGY_EXPECTANCY,
    PASS_RESEARCH_ONLY,
    PASS_REAL_DATA_RESEARCH,
    PASS_PAPER_TRADING_READY,
)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _has_data_errors(summary: Dict[str, Any]) -> bool:
    diagnostics = summary.get("diagnostics") or {}
    data_errors = diagnostics.get("data_errors") or {}
    return bool(data_errors)


def evaluate_paper_trading_gate(
    summary: Dict[str, Any],
    *,
    ci_passed: bool | None = None,
    fixture_smoke_passed: bool | None = None,
    real_5y_passed: bool = False,
    real_10y_passed: bool = False,
    real_10y_safely_degraded: bool = False,
    no_lookahead_risk: bool = True,
    no_auto_trade: bool = True,
    source_mode: str = "fixture",
) -> Dict[str, Any]:
    """Return a conservative research/paper-trading decision."""

    reasons: list[str] = []
    total_signals = int(summary.get("total_signals") or 0)
    avg_60d = _number(summary.get("avg_net_return_60d", summary.get("avg_return_60d")))
    avg_120d = _number(summary.get("avg_net_return_120d", summary.get("avg_return_120d")))
    win_60d = _number(summary.get("win_rate_60d"))
    outperform_60d = _number(summary.get("outperform_benchmark_rate_60d"))
    drawdown_250d = _number(summary.get("avg_low_max_drawdown_250d", summary.get("avg_max_drawdown_250d")))
    recent = (summary.get("time_split_summary") or {}).get("recent_2y") or {}
    recent_avg_60d = _number(recent.get("avg_net_return_60d"))
    recent_win_60d = _number(recent.get("win_rate_60d"))

    if ci_passed is not True:
        reasons.append("CI 未确认通过")
    if fixture_smoke_passed is not True:
        reasons.append("fixture smoke 未确认通过")
    if not no_lookahead_risk:
        return {"verdict": FAIL_LOOKAHEAD_RISK, "reasons": ["存在已知未来函数风险"]}
    if not no_auto_trade:
        reasons.append("存在自动交易能力，不符合本系统边界")
    if _has_data_errors(summary) and source_mode == "real":
        reasons.append("真实数据存在拉取失败")
    if total_signals < 100:
        reasons.append("样本数量少于 100")
    if avg_60d is None or avg_60d <= 0:
        reasons.append("60 日平均净收益未转正")
    if win_60d is None or win_60d < 52:
        reasons.append("60 日胜率低于 52%")
    if outperform_60d is None or outperform_60d < 50:
        reasons.append("60 日跑赢基准比例低于 50%")
    if drawdown_250d is None or drawdown_250d < -25:
        reasons.append("250 日低点口径平均回撤过大")
    if recent_avg_60d is not None and recent_avg_60d < -2:
        reasons.append("最近两年 60 日平均净收益明显走弱")
    if recent_win_60d is not None and recent_win_60d < 45:
        reasons.append("最近两年 60 日胜率明显偏低")

    short_horizon_ok = bool(avg_60d is not None and avg_60d > 0 and avg_120d is not None and avg_120d <= 0)
    if avg_120d is None or avg_120d <= 0:
        reasons.append("120 日平均净收益未转正，最多按 20/60 日短中期研究观察")

    if ci_passed is False and source_mode == "ci":
        verdict = FAIL_CI
    elif source_mode == "real" and _has_data_errors(summary) and total_signals == 0:
        verdict = FAIL_REAL_DATA_FETCH
    elif source_mode == "real" and total_signals == 0:
        verdict = FAIL_DATA_QUALITY
    elif source_mode == "fixture":
        verdict = PASS_RESEARCH_ONLY
    elif avg_60d is not None and avg_60d <= 0 and total_signals >= 100:
        verdict = FAIL_STRATEGY_EXPECTANCY
    elif source_mode == "real" and real_5y_passed and (real_10y_passed or real_10y_safely_degraded):
        verdict = PASS_REAL_DATA_RESEARCH
    else:
        verdict = PASS_RESEARCH_ONLY

    can_paper = (
        ci_passed is True
        and fixture_smoke_passed is True
        and real_5y_passed
        and (real_10y_passed or real_10y_safely_degraded)
        and no_lookahead_risk
        and no_auto_trade
        and not _has_data_errors(summary)
        and total_signals >= 100
        and avg_60d is not None
        and avg_60d > 0
        and win_60d is not None
        and win_60d >= 52
        and outperform_60d is not None
        and outperform_60d >= 50
        and drawdown_250d is not None
        and drawdown_250d >= -25
        and (avg_120d is not None and avg_120d > 0 or short_horizon_ok)
        and not (recent_avg_60d is not None and recent_avg_60d < -2)
        and no_auto_trade
    )
    if can_paper:
        verdict = PASS_PAPER_TRADING_READY
        reasons = ["满足当前模拟盘观察门槛，但仍不构成交易建议"]

    return {"verdict": verdict, "reasons": reasons or ["仅通过研究验证，尚未达到更高门槛"]}


def merge_gate_context(summary: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    context = dict(context or {})
    gate = evaluate_paper_trading_gate(summary, **context)
    summary["paper_trading_gate"] = gate
    return summary
