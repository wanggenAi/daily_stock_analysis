"""Acceptance gate for GenGe Cycle Bottom research reports."""

from __future__ import annotations

from typing import Any, Dict


FAIL_CI = "FAIL_CI"
FAIL_REAL_DATA_FETCH = "FAIL_REAL_DATA_FETCH"
FAIL_DATA_QUALITY = "FAIL_DATA_QUALITY"
FAIL_LOOKAHEAD_RISK = "FAIL_LOOKAHEAD_RISK"
FAIL_STRATEGY_EXPECTANCY = "FAIL_STRATEGY_EXPECTANCY"
FAIL_EXIT_POLICY = "FAIL_EXIT_POLICY"
FAIL_EXIT_BALANCE = "FAIL_EXIT_BALANCE"
FAIL_EVIDENCE_LAYER = "FAIL_EVIDENCE_LAYER"
PASS_RESEARCH_ONLY = "PASS_RESEARCH_ONLY"
PASS_REAL_DATA_RESEARCH = "PASS_REAL_DATA_RESEARCH"
PASS_EXIT_POLICY_RESEARCH = "PASS_EXIT_POLICY_RESEARCH"
PASS_BALANCED_EXIT_POLICY = "PASS_BALANCED_EXIT_POLICY"
PASS_60D_REPAIR_STRATEGY_VALIDATED = "PASS_60D_REPAIR_STRATEGY_VALIDATED"
PASS_INDUSTRY_EVIDENCE_FRAMEWORK = "PASS_INDUSTRY_EVIDENCE_FRAMEWORK"
PASS_HARD_LOGIC_RESEARCH_READY = "PASS_HARD_LOGIC_RESEARCH_READY"
PASS_CYCLE_TURNING_POINT_SCREENER = "PASS_CYCLE_TURNING_POINT_SCREENER"
PASS_PAPER_TRADING_CANDIDATE = "PASS_PAPER_TRADING_CANDIDATE"
PASS_PAPER_TRADING_READY = "PASS_PAPER_TRADING_READY"

ACCEPTANCE_ENUMS = (
    FAIL_CI,
    FAIL_REAL_DATA_FETCH,
    FAIL_DATA_QUALITY,
    FAIL_LOOKAHEAD_RISK,
    FAIL_STRATEGY_EXPECTANCY,
    FAIL_EXIT_POLICY,
    FAIL_EXIT_BALANCE,
    FAIL_EVIDENCE_LAYER,
    PASS_RESEARCH_ONLY,
    PASS_REAL_DATA_RESEARCH,
    PASS_EXIT_POLICY_RESEARCH,
    PASS_BALANCED_EXIT_POLICY,
    PASS_60D_REPAIR_STRATEGY_VALIDATED,
    PASS_INDUSTRY_EVIDENCE_FRAMEWORK,
    PASS_HARD_LOGIC_RESEARCH_READY,
    PASS_CYCLE_TURNING_POINT_SCREENER,
    PASS_PAPER_TRADING_CANDIDATE,
    PASS_PAPER_TRADING_READY,
)

INDUSTRY_EVIDENCE_ACCEPTANCE_ENUMS = (
    FAIL_EVIDENCE_LAYER,
    PASS_INDUSTRY_EVIDENCE_FRAMEWORK,
    PASS_HARD_LOGIC_RESEARCH_READY,
    PASS_CYCLE_TURNING_POINT_SCREENER,
    PASS_PAPER_TRADING_CANDIDATE,
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


def _has_severe_data_errors(summary: Dict[str, Any]) -> bool:
    diagnostics = summary.get("diagnostics") or {}
    data_errors = diagnostics.get("data_errors") or {}
    requested = diagnostics.get("requested_codes") or []
    if not data_errors:
        return False
    return len(data_errors) >= max(3, int(len(requested) * 0.5)) if requested else bool(data_errors)


def _coverage(summary: Dict[str, Any], field_name: str) -> float:
    value = _number(summary.get(field_name))
    return value if value is not None else 0.0


def _price_only_research(summary: Dict[str, Any]) -> bool:
    diagnostics = summary.get("diagnostics") or {}
    return bool(diagnostics.get("price_only_research"))


def _has_severe_provider_errors(summary: Dict[str, Any]) -> bool:
    diagnostics = summary.get("diagnostics") or {}
    provider_errors = diagnostics.get("provider_errors") or {}
    requested = diagnostics.get("requested_codes") or []
    if not provider_errors:
        return False
    return len(provider_errors) >= max(3, int(len(requested) * 0.5)) if requested else bool(provider_errors)


def _execution_risk_rate(summary: Dict[str, Any]) -> float:
    total = int(summary.get("total_signals") or 0)
    if total <= 0:
        return 100.0
    execution = summary.get("execution_diagnostics") or {}
    risky = (
        int(execution.get("limit_up_entry_count") or 0)
        + int(execution.get("missing_entry_count") or 0)
        + int(execution.get("degraded_entry_count") or 0)
        + int(execution.get("low_liquidity_count") or 0)
    )
    return risky / total * 100.0


def _summary_group_count(summary: Dict[str, Any], field_name: str, names: set[str]) -> int:
    grouped = summary.get(field_name) or {}
    total = 0
    for name, metrics in grouped.items():
        if str(name).upper() in names:
            total += int((metrics or {}).get("total_signals") or 0)
    return total


def _uses_industry_evidence_layer(summary: Dict[str, Any]) -> bool:
    diagnostics = summary.get("diagnostics") or {}
    return bool(
        diagnostics.get("industry_evidence_schema")
        or diagnostics.get("industry_evidence_schema_industries")
        or diagnostics.get("industry_evidence_file")
        or diagnostics.get("company_evidence_file")
    )


def _industry_evidence_layer_gate(
    summary: Dict[str, Any],
    *,
    base_verdict: str,
    base_reasons: list[str],
    no_lookahead_risk: bool,
    no_auto_trade: bool,
) -> Dict[str, Any] | None:
    if not _uses_industry_evidence_layer(summary):
        return None

    diagnostics = summary.get("diagnostics") or {}
    reasons = list(base_reasons)
    if not no_lookahead_risk:
        return {"verdict": FAIL_EVIDENCE_LAYER, "reasons": ["行业证据层存在未来函数风险"]}
    if not no_auto_trade:
        return {"verdict": FAIL_EVIDENCE_LAYER, "reasons": ["行业证据层不能包含自动交易能力"]}
    if not diagnostics.get("industry_evidence_schema_industries"):
        return {"verdict": FAIL_EVIDENCE_LAYER, "reasons": ["缺少行业证据 schema 或 schema 未加载成功"]}
    if "FAIL" in base_verdict:
        return {"verdict": FAIL_EVIDENCE_LAYER, "reasons": reasons or ["基础研究链路未通过，行业证据层不能单独升级"]}

    source_types = {
        str(diagnostics.get("industry_evidence_source") or "none"),
        str(diagnostics.get("company_evidence_source") or "none"),
    }
    if source_types & {"manual_template", "fixture", "none"}:
        return {
            "verdict": PASS_INDUSTRY_EVIDENCE_FRAMEWORK,
            "reasons": reasons
            or ["行业证据 schema、信号字段、证据卡和候选输出已可运行；当前证据来源偏模板或 fixture，不能升级硬逻辑结论"],
        }

    medium_or_strong = _summary_group_count(summary, "hard_logic_level_summary", {"MEDIUM", "STRONG"})
    strong_count = _summary_group_count(summary, "hard_logic_level_summary", {"STRONG"})
    cycle_candidate_count = int(summary.get("cycle_turning_point_candidate_count") or 0)
    evidence_confident = _summary_group_count(summary, "industry_evidence_confidence_summary", {"MEDIUM", "HIGH"})
    if cycle_candidate_count > 0 and medium_or_strong > 0:
        return {
            "verdict": PASS_CYCLE_TURNING_POINT_SCREENER,
            "reasons": reasons or ["行业证据层已产生周期拐点研究观察候选，仍只用于人工复核"],
        }
    if medium_or_strong > 0 and evidence_confident > 0 and strong_count >= 0:
        return {
            "verdict": PASS_HARD_LOGIC_RESEARCH_READY,
            "reasons": reasons or ["存在 MEDIUM 及以上硬逻辑样本，可进入人工研究复核"],
        }
    return {
        "verdict": PASS_INDUSTRY_EVIDENCE_FRAMEWORK,
        "reasons": reasons or ["行业证据框架可运行，但有效证据不足，保持框架通过级别"],
    }


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
    exit_summary = (summary.get("exit_policy_summary") or {}).get("hybrid_60d_repair_exit") or {}
    balanced_summary = (summary.get("exit_policy_summary") or {}).get("balanced_hybrid_60d_exit") or summary.get("balanced_exit_policy_summary") or {}
    exit_avg_60d = _number(exit_summary.get("avg_exit_adjusted_net_return_60d"))
    exit_dd_60d = _number(exit_summary.get("avg_exit_adjusted_max_drawdown_60d"))
    exit_dd_250d = _number(exit_summary.get("avg_exit_adjusted_max_drawdown_250d"))
    raw_dd_60d = _number(summary.get("avg_low_max_drawdown_60d"))
    exit_dd_reduction_250d = _number(exit_summary.get("exit_policy_drawdown_reduction_pct"))
    has_exit_policy = exit_avg_60d is not None and exit_dd_250d is not None
    balanced_avg_60d = _number(balanced_summary.get("avg_exit_adjusted_net_return_60d"))
    balanced_win_60d = _number(balanced_summary.get("win_rate_exit_adjusted_60d"))
    balanced_outperform_60d = _number(balanced_summary.get("outperform_benchmark_exit_adjusted_60d"))
    balanced_dd_250d = _number(balanced_summary.get("avg_exit_adjusted_max_drawdown_250d"))
    balanced_retention_60d = _number(balanced_summary.get("return_retention_rate_60d"))
    balanced_dd_reduction_250d = _number(balanced_summary.get("drawdown_reduction_rate_250d", balanced_summary.get("exit_policy_drawdown_reduction_pct")))
    has_balanced_policy = balanced_avg_60d is not None and balanced_dd_250d is not None
    overfit_warning = bool((summary.get("baseline_comparison") or {}).get("overfit_warning"))
    baseline = summary.get("baseline_comparison") or {}
    baseline_group = str(baseline.get("baseline_group") or "")
    sample_count_change_pct = _number(baseline.get("sample_count_change_pct"))
    research_candidate_count = int(summary.get("research_observation_candidate_count") or 0)
    recent = (summary.get("time_split_summary") or {}).get("recent_2y") or {}
    recent_avg_60d = _number(recent.get("avg_net_return_60d"))
    recent_win_60d = _number(recent.get("win_rate_60d"))
    valuation_coverage = _coverage(summary, "valuation_coverage_rate")
    financial_coverage = _coverage(summary, "financial_coverage_rate")
    price_only = _price_only_research(summary)
    real_run_passed = bool(real_5y_passed or real_10y_passed or real_10y_safely_degraded)
    severe_data_errors = _has_severe_data_errors(summary)
    severe_provider_errors = _has_severe_provider_errors(summary)
    execution_risk_rate = _execution_risk_rate(summary)
    fundamental_coverage_ready = price_only or (valuation_coverage > 30 and financial_coverage > 30)

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
    if not fundamental_coverage_ready:
        reasons.append("估值和财务覆盖率未同时超过 30%，不能按完整基本面研究通过")
    if severe_data_errors:
        reasons.append("真实行情 data_errors 较多，需要先复核数据源稳定性")
    if severe_provider_errors:
        reasons.append("公开数据 provider_errors 较多，需要先复核数据源稳定性")
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
    if has_exit_policy:
        if exit_avg_60d is not None and avg_60d is not None and exit_avg_60d < avg_60d - 0.5:
            reasons.append("退出策略对 60 日收益伤害偏大")
        if exit_dd_60d is not None and raw_dd_60d is not None and abs(exit_dd_60d) > abs(raw_dd_60d) + 0.5:
            reasons.append("退出策略未降低 60 日最大不利波动")
        if exit_dd_reduction_250d is None or exit_dd_reduction_250d <= 0:
            reasons.append("退出策略未降低 250 日死拿风险")
        if overfit_warning:
            reasons.append("样本骤降或 broad 样本低于 8000，暂不能提高到 60 日修复策略验证")
    if has_balanced_policy:
        if balanced_avg_60d is not None and balanced_avg_60d < 1.2 and baseline_group == "broad":
            reasons.append("balanced 60 日退出净收益低于 1.2%")
        if balanced_retention_60d is not None and balanced_retention_60d < 50 and baseline_group == "broad":
            reasons.append("balanced 60 日收益保留率低于 50%")
        if balanced_dd_reduction_250d is not None and balanced_dd_reduction_250d < 60 and baseline_group == "broad":
            reasons.append("balanced 250 日回撤降低率低于 60%")

    if ci_passed is False and source_mode == "ci":
        verdict = FAIL_CI
    elif source_mode == "real" and _has_data_errors(summary) and total_signals == 0:
        verdict = FAIL_REAL_DATA_FETCH
    elif source_mode == "real" and total_signals == 0:
        verdict = FAIL_DATA_QUALITY
    elif source_mode == "fixture":
        verdict = PASS_RESEARCH_ONLY
    elif source_mode == "real" and total_signals >= 100 and not fundamental_coverage_ready:
        verdict = FAIL_DATA_QUALITY
    elif source_mode == "real" and (severe_data_errors or severe_provider_errors) and total_signals >= 100:
        verdict = FAIL_DATA_QUALITY
    elif (
        source_mode == "real"
        and fixture_smoke_passed is True
        and real_run_passed
        and total_signals >= 100
        and no_lookahead_risk
        and no_auto_trade
        and fundamental_coverage_ready
    ):
        verdict = PASS_REAL_DATA_RESEARCH
    elif avg_60d is not None and avg_60d <= 0 and total_signals >= 100:
        verdict = FAIL_STRATEGY_EXPECTANCY
    else:
        verdict = PASS_RESEARCH_ONLY

    if source_mode == "real" and has_exit_policy and total_signals >= 100 and verdict == PASS_REAL_DATA_RESEARCH:
        exit_harms_60d = exit_avg_60d is not None and avg_60d is not None and exit_avg_60d < avg_60d - 1.0
        exit_worsens_drawdown = exit_dd_reduction_250d is not None and exit_dd_reduction_250d <= 0
        if exit_harms_60d and exit_worsens_drawdown:
            verdict = FAIL_EXIT_POLICY
        else:
            verdict = PASS_EXIT_POLICY_RESEARCH
            if (
                total_signals >= 8000
                and not overfit_warning
                and avg_60d is not None
                and avg_60d > 0
                and win_60d is not None
                and win_60d >= 47
                and outperform_60d is not None
                and outperform_60d >= 46.5
                and exit_avg_60d is not None
                and exit_avg_60d >= avg_60d - 0.5
                and exit_dd_reduction_250d is not None
                and exit_dd_reduction_250d > 0
            ):
                verdict = PASS_60D_REPAIR_STRATEGY_VALIDATED

    if source_mode == "real" and has_balanced_policy and total_signals >= 100 and verdict in {PASS_REAL_DATA_RESEARCH, PASS_EXIT_POLICY_RESEARCH, PASS_60D_REPAIR_STRATEGY_VALIDATED}:
        balanced_harms_60d = (
            balanced_avg_60d is not None
            and avg_60d is not None
            and balanced_avg_60d < avg_60d * 0.35
            and balanced_dd_reduction_250d is not None
            and balanced_dd_reduction_250d < 30
        )
        if balanced_harms_60d:
            verdict = FAIL_EXIT_BALANCE
        else:
            verdict = PASS_EXIT_POLICY_RESEARCH
            broad_sample_ok = baseline_group == "broad" and total_signals >= 9000
            sample_stable = sample_count_change_pct is None or sample_count_change_pct >= -10
            balanced_minimum_ok = (
                broad_sample_ok
                and sample_stable
                and balanced_avg_60d is not None
                and balanced_avg_60d >= 1.2
                and balanced_retention_60d is not None
                and balanced_retention_60d >= 50
                and balanced_dd_reduction_250d is not None
                and balanced_dd_reduction_250d >= 60
                and balanced_win_60d is not None
                and balanced_win_60d >= 46
                and balanced_outperform_60d is not None
                and balanced_outperform_60d >= 46
            )
            if balanced_minimum_ok:
                verdict = PASS_BALANCED_EXIT_POLICY
                stricter_recent_ok = not (
                    recent_avg_60d is not None
                    and recent_avg_60d < -2
                    or recent_win_60d is not None
                    and recent_win_60d < 45
                )
                if (
                    balanced_avg_60d >= 1.5
                    and balanced_retention_60d >= 65
                    and balanced_win_60d >= 48
                    and balanced_outperform_60d >= 47
                    and stricter_recent_ok
                    and research_candidate_count > 0
                ):
                    verdict = PASS_60D_REPAIR_STRATEGY_VALIDATED

    can_paper = (
        verdict == PASS_60D_REPAIR_STRATEGY_VALIDATED
        and ci_passed is True
        and fixture_smoke_passed is True
        and real_5y_passed
        and (real_10y_passed or real_10y_safely_degraded)
        and no_lookahead_risk
        and no_auto_trade
        and not _has_data_errors(summary)
        and not severe_data_errors
        and not severe_provider_errors
        and total_signals >= 200
        and research_candidate_count > 0
        and fundamental_coverage_ready
        and execution_risk_rate <= 20
        and avg_60d is not None
        and avg_60d > 0
        and balanced_avg_60d is not None
        and balanced_avg_60d >= 1.8
        and balanced_retention_60d is not None
        and balanced_retention_60d >= 70
        and balanced_dd_reduction_250d is not None
        and balanced_dd_reduction_250d >= 65
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

    can_paper_candidate = (
        verdict == PASS_60D_REPAIR_STRATEGY_VALIDATED
        and research_candidate_count > 0
        and execution_risk_rate <= 20
        and balanced_win_60d is not None
        and balanced_win_60d >= 50
        and balanced_outperform_60d is not None
        and balanced_outperform_60d >= 47
        and balanced_dd_reduction_250d is not None
        and balanced_dd_reduction_250d >= 60
        and balanced_retention_60d is not None
        and balanced_retention_60d >= 65
        and not (recent_avg_60d is not None and recent_avg_60d < -2)
    )
    if can_paper_candidate:
        verdict = PASS_PAPER_TRADING_CANDIDATE
        reasons = ["满足研究观察候选门槛，仅用于模拟观察和复盘，不构成买入建议"]

    industry_gate = _industry_evidence_layer_gate(
        summary,
        base_verdict=verdict,
        base_reasons=reasons,
        no_lookahead_risk=no_lookahead_risk,
        no_auto_trade=no_auto_trade,
    )
    if industry_gate is not None:
        return industry_gate

    return {"verdict": verdict, "reasons": reasons or ["仅通过研究验证，尚未达到更高门槛"]}


def merge_gate_context(summary: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    context = dict(context or {})
    gate = evaluate_paper_trading_gate(summary, **context)
    summary["paper_trading_gate"] = gate
    return summary
