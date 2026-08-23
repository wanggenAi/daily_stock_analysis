"""Auditable long-term Formal BUY layer governed by frozen V3.1.

Legacy operational checks remain as additional production safety constraints.
They can block a candidate, but they can no longer promote a candidate. A formal
long-term BUY is emitted only when the complete frozen V3.1 framework passes.
There is no formal TRY_POSITION bypass.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery import selection_framework_v31

DISCLAIMER = "仅用于公开数据长期研究与人工复核，不构成买入或卖出建议，不应自动交易。"
POLICY_VERSION = "long_term_formal_buy_v2_v31_frozen"

DEFENSIVE_MARKETS = {"RED", "CRISIS", "RISK_OFF", "EXTREME_RISK"}
BLOCKING_EVENT_RISKS = {"HIGH", "CRITICAL", "EXTREME"}
READY_EXECUTION_STATES = {"GENERIC_REVERSE_DIAGNOSTIC_READY"}

MIN_REAL_REWARD_RISK = 1.8
MIN_EARNINGS_QUALITY_SCORE = 50.0
MIN_BUY_READY_EARNINGS_QUALITY_SCORE = 65.0
MIN_ROUTING_CONFIDENCE = 0.50
MAX_BUY_READY_REQUIRED_GROWTH = 0.15
MAX_TRY_POSITION_REQUIRED_GROWTH = 0.35


@dataclass(frozen=True)
class LongTermPolicy:
    min_real_reward_risk: float = MIN_REAL_REWARD_RISK
    min_earnings_quality_score: float = MIN_EARNINGS_QUALITY_SCORE
    min_buy_ready_earnings_quality_score: float = MIN_BUY_READY_EARNINGS_QUALITY_SCORE
    min_routing_confidence: float = MIN_ROUTING_CONFIDENCE
    max_buy_ready_required_growth: float = MAX_BUY_READY_REQUIRED_GROWTH
    max_try_position_required_growth: float = MAX_TRY_POSITION_REQUIRED_GROWTH


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _latest_report(root: Path) -> Path:
    if (root / "run_summary.json").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/run_summary.json") if p.is_file()}, key=str
    )
    if not candidates:
        raise FileNotFoundError(f"no All-A report under {root}")
    return candidates[-1]


def _latest_valuation(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file()}, key=str
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def _full_plan_map(report_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in (
        "top30_deep_review.csv",
        "condition_watch.csv",
        "research_watch.csv",
        "tomorrow_watchlist.csv",
        "daily_candidate_top5.csv",
    ):
        for raw in _read(report_dir / name):
            code = _code(raw.get("code"))
            if not code:
                continue
            if code not in result:
                result[code] = dict(raw)
                continue
            for key, value in raw.items():
                if not str(result[code].get(key) or "").strip() and str(value or "").strip():
                    result[code][key] = value
    return result


def _valuation_map(valuation_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        _code(row.get("code")): row
        for row in _read(valuation_dir / "valuation_research_routed.csv")
        if _code(row.get("code"))
    }


def _entry_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    preferred = str(plan.get("preferred_plan") or "").strip().lower()
    latest = _float(plan.get("raw_latest_close"))
    if preferred == "breakout":
        low = _float(plan.get("breakout_trigger_price"))
        high = _float(plan.get("breakout_max_chase_price")) or _float(plan.get("breakout_confirmation_high"))
        stop = _float(plan.get("breakout_stop_price")) or _float(plan.get("breakout_logic_invalidation_price"))
        target1 = _float(plan.get("breakout_target_1"))
        target2 = _float(plan.get("breakout_target_2"))
        status = str(plan.get("breakout_status") or "")
    else:
        preferred = "pullback"
        low = _float(plan.get("pullback_entry_low"))
        high = _float(plan.get("pullback_entry_high"))
        stop = _float(plan.get("pullback_stop_price")) or _float(plan.get("pullback_logic_invalidation_price"))
        target1 = _float(plan.get("pullback_target_1"))
        target2 = _float(plan.get("pullback_target_2"))
        status = str(plan.get("pullback_status") or "")

    in_zone = bool(
        latest is not None and low is not None and high is not None
        and min(low, high) <= latest <= max(low, high)
    )
    trigger_observed = any(
        token in status.upper() for token in ("TRIGGER", "CONFIRM", "READY", "ACTIVE")
    )
    return {
        "preferred_plan": preferred,
        "current_price": latest,
        "entry_low": low,
        "entry_high": high,
        "risk_invalidation_price": stop,
        "target_1": target1,
        "target_2": target2,
        "entry_plan_status": status,
        "current_action": (
            "ENTRY_CONDITION_PRESENT_REVIEW_NOW" if in_zone or trigger_observed else "WAIT_FOR_ENTRY"
        ),
    }


def _production_blockers(
    second_pass: Mapping[str, Any],
    plan: Mapping[str, Any],
    valuation: Mapping[str, Any],
    *,
    policy: LongTermPolicy,
) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    if str(second_pass.get("long_term_second_pass_status") or "") != "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES":
        blockers.append("non_exit_hard_gates_not_proven")

    hard = str(plan.get("hard_blockers") or plan.get("hard_reject_blockers") or "").strip()
    if hard:
        blockers.append("hard_blocker_present")

    market = str(plan.get("market_regime_status") or "UNKNOWN").upper()
    if market in DEFENSIVE_MARKETS:
        blockers.append("defensive_market")
    event_risk = str(plan.get("event_risk_level") or "UNKNOWN").upper()
    if event_risk in BLOCKING_EVENT_RISKS:
        blockers.append("blocking_event_risk")

    rr = _float(plan.get("real_reward_risk_ratio") or second_pass.get("real_reward_risk_ratio"))
    if rr is None or rr < policy.min_real_reward_risk:
        blockers.append("real_reward_risk_below_minimum")

    if not valuation:
        blockers.append("valuation_missing")
    execution = str(valuation.get("valuation_model_execution_state") or "")
    if valuation and execution not in READY_EXECUTION_STATES:
        blockers.append("valuation_model_not_executed")
    if valuation and str(valuation.get("valuation_diagnostic_status") or "") != "OK":
        blockers.append("valuation_diagnostic_not_ready")
    if valuation and str(valuation.get("financial_review_status") or "") != "OK":
        blockers.append("financial_review_not_ready")

    core_profit = _float(valuation.get("normalized_core_operating_profit"))
    if valuation and (core_profit is None or core_profit <= 0):
        blockers.append("normalized_core_profit_not_positive")
    quality = _float(valuation.get("earnings_quality_score"))
    if valuation and (quality is None or quality < policy.min_earnings_quality_score):
        blockers.append("earnings_quality_below_minimum")
    route_confidence = _float(valuation.get("valuation_routing_confidence"))
    if valuation and (route_confidence is None or route_confidence < policy.min_routing_confidence):
        blockers.append("valuation_route_low_confidence")

    required_growth = _float(valuation.get("required_profit_growth_vs_reference"))
    if valuation and required_growth is None:
        blockers.append("required_profit_growth_unavailable")
    elif required_growth is not None and required_growth > policy.max_try_position_required_growth:
        blockers.append("valuation_expectation_too_high")

    return blockers, {
        "market_regime_status": market,
        "event_risk_level": event_risk,
        "real_reward_risk_ratio": rr,
        "valuation_model_execution_state": execution,
        "valuation_routing_confidence": route_confidence,
        "required_profit_growth_vs_reference": required_growth,
        "earnings_quality_score": quality,
        "normalized_core_operating_profit": core_profit,
    }


def evaluate_long_term_candidate(
    second_pass: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
    valuation: Mapping[str, Any] | None,
    *,
    policy: LongTermPolicy = LongTermPolicy(),
) -> dict[str, Any]:
    code = _code(second_pass.get("code"))
    plan = dict(plan or {})
    valuation = dict(valuation or {})

    blockers, diagnostics = _production_blockers(second_pass, plan, valuation, policy=policy)
    v31_input = selection_framework_v31.merge_research_inputs(second_pass, plan, valuation)
    if not str(v31_input.get("v31_current_price") or "").strip() and diagnostics["real_reward_risk_ratio"] is not None:
        # Only price is safely inherited. Qualitative V3.1 gates are never inferred
        # from legacy scores/evidence and remain UNKNOWN until explicitly reviewed.
        v31_input["v31_current_price"] = plan.get("raw_latest_close")
    assessment = selection_framework_v31.assess_v31(v31_input)

    if not assessment.buy_ready:
        blockers.extend(f"v31:{item}" for item in assessment.blockers)
    blockers = list(dict.fromkeys(blockers))
    eligible = not blockers and assessment.buy_ready

    entry = _entry_plan(plan)
    result = {
        "code": code,
        "stock_name": plan.get("stock_name") or second_pass.get("stock_name") or valuation.get("stock_name") or "",
        "industry": plan.get("industry") or second_pass.get("industry") or valuation.get("industry") or "",
        "long_term_classification": "LONG_TERM_BUY_READY" if eligible else "LONG_TERM_REVIEW_BLOCKED",
        "long_term_formal_buy_eligible": eligible,
        "long_term_blockers": ";".join(blockers),
        **diagnostics,
        "valuation_primary_strategy_id": valuation.get("valuation_primary_strategy_id") or "",
        "valuation_diagnostic_status": valuation.get("valuation_diagnostic_status") or "",
        "required_profit_growth_pct": (
            diagnostics["required_profit_growth_vs_reference"] * 100.0
            if diagnostics["required_profit_growth_vs_reference"] is not None else None
        ),
        "earnings_quality_confidence": valuation.get("earnings_quality_confidence") or "",
        "financial_review_status": valuation.get("financial_review_status") or "",
        "medium_horizon_exit_profile_limitation": True,
        "legacy_exit_profile_is_long_term_veto": False,
        **entry,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "policy_version": POLICY_VERSION,
        "disclaimer": DISCLAIMER,
    }
    result.update(assessment.as_dict())
    return result


def build_long_term_formal_buy_rows(
    second_pass_rows: Iterable[Mapping[str, Any]],
    *,
    plan_map: Mapping[str, Mapping[str, Any]],
    valuation_map: Mapping[str, Mapping[str, Any]],
    policy: LongTermPolicy = LongTermPolicy(),
) -> list[dict[str, Any]]:
    rows = [
        evaluate_long_term_candidate(
            raw,
            plan_map.get(_code(raw.get("code"))),
            valuation_map.get(_code(raw.get("code"))),
            policy=policy,
        )
        for raw in second_pass_rows
        if _code(raw.get("code"))
    ]
    rows.sort(
        key=lambda r: (
            0 if r.get("long_term_classification") == "LONG_TERM_BUY_READY" else 1,
            -(_float(r.get("v31_score_total")) or -1.0),
            -(_float(r.get("v31_risk_adjusted_3y_cagr")) or -1.0),
            str(r.get("code") or ""),
        )
    )
    return rows


V31_REPORT_FIELDS = [
    "v31_policy_version", "v31_hard_gates_passed", "v31_hard_gate_failures",
    "v31_hard_gate_unknowns", "v31_score_total", "v31_score_complete",
    "v31_candidate_class", "v31_a_eligible", "v31_normalized_profit_ready",
    "v31_scenario_valuation_ready", "v31_implied_expectation_ready",
    "v31_expectation_gap_ready", "v31_risk_adjusted_cagr_ready",
    "v31_downside_ready", "v31_falsification_ready", "v31_margin_reference_band",
    "v31_buy_ready", "v31_blockers",
]


def write_report(
    report_root: Path,
    long_term_dir: Path,
    valuation_root: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    report_dir = _latest_report(report_root)
    valuation_dir = _latest_valuation(valuation_root)
    second_pass = _read(long_term_dir / "long_term_second_pass_candidates.csv")
    rows = build_long_term_formal_buy_rows(
        second_pass,
        plan_map=_full_plan_map(report_dir),
        valuation_map=_valuation_map(valuation_dir),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "code", "stock_name", "industry", "long_term_classification",
        "long_term_formal_buy_eligible", "long_term_blockers",
        *V31_REPORT_FIELDS,
        "market_regime_status", "event_risk_level", "real_reward_risk_ratio",
        "valuation_model_execution_state", "valuation_primary_strategy_id",
        "valuation_routing_confidence", "valuation_diagnostic_status",
        "required_profit_growth_vs_reference", "required_profit_growth_pct",
        "earnings_quality_score", "earnings_quality_confidence",
        "financial_review_status", "normalized_core_operating_profit",
        "preferred_plan", "current_price", "entry_low", "entry_high",
        "risk_invalidation_price", "target_1", "target_2", "entry_plan_status",
        "current_action", "medium_horizon_exit_profile_limitation",
        "legacy_exit_profile_is_long_term_veto", "formal_signal_eligible",
        "automatic_promotion_allowed", "no_auto_trade", "policy_version", "disclaimer",
    ]
    with (output_dir / "long_term_formal_buy_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({k: row.get(k, "") for k in fields} for row in rows)

    eligible = [r for r in rows if r["long_term_formal_buy_eligible"]]
    summary = {
        "candidate_count": len(rows),
        "long_term_formal_buy_count": len(eligible),
        "buy_ready_count": len(eligible),
        "try_position_count": 0,
        "blocked_count": len(rows) - len(eligible),
        "formal_buy_codes": [r["code"] for r in eligible],
        "policy_version": POLICY_VERSION,
        "frozen_v31_required": True,
        "legacy_exit_profile_is_long_term_veto": False,
        "no_auto_trade": True,
    }
    (output_dir / "long_term_formal_buy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Long-Term Formal BUY Review — Frozen V3.1",
        "",
        DISCLAIMER,
        "",
        f"- policy: {POLICY_VERSION}",
        f"- formal candidates: {len(eligible)} / {len(rows)}",
        "- formal TRY_POSITION: disabled",
        "- legacy 60-day exit-profile shortage is not by itself a long-term veto",
        "- missing V3.1 qualitative evidence remains UNKNOWN and blocks Formal BUY",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.extend([
            f"## {i}. {row['code']} {row['stock_name']} — {row['long_term_classification']}",
            f"- industry: {row['industry']}",
            f"- V3.1 class: {row.get('v31_candidate_class','')}",
            f"- V3.1 score: {row.get('v31_score_total','')}",
            f"- V3.1 gates passed: {row.get('v31_hard_gates_passed','')}",
            f"- current action: {row['current_action']}",
            f"- entry: {row['entry_low']} ~ {row['entry_high']}",
            f"- invalidation: {row['risk_invalidation_price']}",
            f"- target: {row['target_1']} / {row['target_2']}",
            f"- R/R: {row['real_reward_risk_ratio']}",
            f"- blockers: {row['long_term_blockers'] or 'NONE'}",
            "",
        ])
    (output_dir / "long_term_formal_buy.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--long-term-dir", type=Path, required=True)
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_report(args.report_root, args.long_term_dir, args.valuation_root, args.output_dir)
    print(f"long_term_formal_buy={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
