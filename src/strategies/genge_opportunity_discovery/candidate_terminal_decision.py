"""Research-terminal decision layer for the GenGe opportunity pipeline.

Every candidate that reaches the master research ranking is closed for the
current research cycle as exactly one of BUY / WAIT_PRICE / REJECT.  This layer
is deliberately downstream from discovery and valuation and is *not* a new
trading authority:

* BUY can only mirror an already-authorized frozen-V3.1 long-term Formal BUY.
* WAIT_PRICE is research-only and is allowed only when the complete V3.1
  evidence set is present and the remaining failed conditions are explicitly
  price/return/chase conditions.
* REJECT is a terminal state for the current research cycle.  Missing evidence
  is reported as retryable EVIDENCE_INSUFFICIENT rather than silently treated
  as PASS.

The Canonical/Production authority, Confidence Gate, Hard Gate, sizing rules and
no-auto-trade contract remain unchanged.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery import selection_framework_v31

DISCLAIMER = "仅用于公开数据长期研究与人工复核，不构成买入或卖出建议，不应自动交易。"
POLICY_VERSION = "candidate_terminal_decision_v1_research_only"
DECISION_AUTHORITY = "RESEARCH_TERMINAL_VIEW"
TERMINAL_DECISIONS = frozenset({"BUY", "WAIT_PRICE", "REJECT"})

# These are the only frozen-V3.1 buy-condition failures that can be represented
# as WAIT_PRICE.  Portfolio/risk/fundamental/evidence failures are never
# converted into a price wait.
PRICE_WAIT_CONDITIONS = frozenset(
    {
        "clear_margin_of_safety",
        "attractive_risk_adjusted_3y_cagr",
        "market_position_not_extreme_chase",
    }
)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _split(value: Any) -> list[str]:
    return [token.strip() for token in _text(value).split(";") if token.strip()]


def _current_price(row: Mapping[str, Any]) -> float | None:
    for key in ("v31_current_price", "current_price", "raw_latest_close"):
        value = _float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def _neutral_value(row: Mapping[str, Any]) -> float | None:
    for key in ("v31_neutral_value", "neutral_value"):
        value = _float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def _reference_prices(row: Mapping[str, Any]) -> tuple[float | None, str, float | None]:
    """Return research wait reference, its source, and the 0.85 diagnostic ceiling.

    The 0.85 neutral-value band is frozen V3.1 diagnostic context, not a
    standalone Formal BUY gate and therefore never authorizes BUY by itself.
    """
    neutral = _neutral_value(row)
    ceiling = round(neutral * 0.85, 4) if neutral is not None else None
    entry_high = _float(row.get("entry_high"))
    if entry_high is not None and entry_high > 0:
        return entry_high, "existing_entry_high", ceiling
    if ceiling is not None:
        return ceiling, "v31_staged_buy_reference_band_diagnostic", ceiling
    return None, "unavailable", None


def _evidence_complete(assessment: selection_framework_v31.V31Assessment) -> bool:
    return bool(
        assessment.hard_gates_passed
        and assessment.score_complete
        and assessment.a_eligible
        and assessment.execution_universe_eligible
        and assessment.normalized_profit_ready
        and assessment.scenario_valuation_ready
        and assessment.implied_expectation_ready
        and assessment.expectation_gap_ready
        and assessment.risk_adjusted_cagr_ready
        and assessment.downside_ready
        and assessment.falsification_ready
    )


def _formal_buy_authorized(row: Mapping[str, Any]) -> bool:
    return bool(
        _bool(row.get("long_term_formal_buy_eligible"))
        and _bool(row.get("v31_buy_ready"))
        and _text(row.get("production_action")).upper() == "BUY"
    )


def _attempted_full_review(row: Mapping[str, Any]) -> bool:
    return bool(
        _text(row.get("valuation_research_rank"))
        or _text(row.get("valuation_model_execution_state"))
        or _text(row.get("financial_review_status"))
        or _text(row.get("valuation_diagnostic_status"))
    )


def terminalize_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    """Close one master-research candidate for this cycle without new authority."""
    source = dict(row)
    assessment = selection_framework_v31.assess_v31(source)
    evidence_complete = _evidence_complete(assessment)
    formal_buy = _formal_buy_authorized(source)
    wait_reference, wait_source, research_ceiling = _reference_prices(source)
    current = _current_price(source)

    decision = "REJECT"
    reason_class = "EVIDENCE_INSUFFICIENT"
    reasons: list[str] = []
    retryable = True

    if formal_buy:
        decision = "BUY"
        reason_class = "FORMAL_BUY_READY"
        reasons = ["authorized_frozen_v31_formal_buy"]
        retryable = False
    elif assessment.hard_gate_failures:
        reason_class = "HARD_GATE_FAILED"
        reasons = [f"hard_gate_failed:{name}" for name in assessment.hard_gate_failures]
        retryable = False
    elif assessment.hard_gate_unknowns:
        reason_class = "EVIDENCE_INSUFFICIENT"
        reasons = [f"hard_gate_unknown:{name}" for name in assessment.hard_gate_unknowns]
    elif not assessment.execution_universe_eligible:
        reason_class = "EXECUTION_UNIVERSE_RESEARCH_ONLY"
        reasons = [f"execution_universe:{assessment.execution_universe_status}"]
        retryable = False
    elif not assessment.a_eligible:
        reason_class = "A_CLASS_NOT_PROVEN"
        reasons = [f"candidate_class:{assessment.candidate_class}"]
    elif not evidence_complete:
        reason_class = "EVIDENCE_INSUFFICIENT"
        readiness = {
            "score": assessment.score_complete,
            "normalized_profit": assessment.normalized_profit_ready,
            "scenario_valuation": assessment.scenario_valuation_ready,
            "implied_expectation": assessment.implied_expectation_ready,
            "expectation_gap": assessment.expectation_gap_ready,
            "risk_adjusted_cagr": assessment.risk_adjusted_cagr_ready,
            "downside": assessment.downside_ready,
            "falsification": assessment.falsification_ready,
        }
        reasons = [f"incomplete:{name}" for name, ready in readiness.items() if not ready]
    else:
        failed_conditions = {
            name for name, passed in assessment.buy_conditions.items() if not passed
        }
        if failed_conditions and failed_conditions.issubset(PRICE_WAIT_CONDITIONS):
            decision = "WAIT_PRICE"
            reason_class = "PRICE_OR_RETURN_NOT_ATTRACTIVE"
            reasons = [f"buy_condition_failed:{name}" for name in sorted(failed_conditions)]
            retryable = True
        elif failed_conditions:
            reason_class = "NON_PRICE_BUY_CONDITION_FAILED"
            reasons = [f"buy_condition_failed:{name}" for name in sorted(failed_conditions)]
            retryable = True
        else:
            # The research evidence says BUY-ready, but no Formal BUY was
            # authorized.  Fail closed: terminal research cannot self-promote.
            reason_class = "FORMAL_BUY_NOT_AUTHORIZED"
            reasons = _split(source.get("long_term_blockers")) or [
                f"production_action:{_text(source.get('production_action')) or 'UNAVAILABLE'}"
            ]
            retryable = True

    result = dict(source)
    result.update(assessment.as_dict())
    result.update(
        {
            "terminal_decision": decision,
            "terminal_reason_class": reason_class,
            "terminal_reason_codes": ";".join(dict.fromkeys(reasons)),
            "terminal_retryable_next_cycle": retryable,
            "terminal_evidence_complete": evidence_complete,
            "terminal_full_review_attempted": _attempted_full_review(source),
            "terminal_formal_buy_authorized": formal_buy,
            "terminal_current_price": current,
            "wait_price_reference": wait_reference if decision == "WAIT_PRICE" else None,
            "wait_price_reference_source": wait_source if decision == "WAIT_PRICE" else "",
            "research_reference_ceiling": research_ceiling,
            "research_reference_ceiling_semantics": (
                "diagnostic_only_not_formal_buy_gate" if research_ceiling is not None else "unavailable"
            ),
            "decision_authority": DECISION_AUTHORITY,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "terminal_policy_version": POLICY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    )
    if result["terminal_decision"] not in TERMINAL_DECISIONS:
        raise AssertionError(f"non-terminal decision emitted: {result['terminal_decision']}")
    if result["terminal_decision"] == "BUY" and not result["terminal_formal_buy_authorized"]:
        raise AssertionError("research terminal layer attempted unauthorized BUY")
    return result


def build_terminal_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        code = _text(raw.get("code"))
        if not code or code in seen:
            continue
        result.append(terminalize_candidate(raw))
        seen.add(code)
    priority = {"BUY": 0, "WAIT_PRICE": 1, "REJECT": 2}
    result.sort(
        key=lambda row: (
            priority[row["terminal_decision"]],
            float(row.get("master_research_rank") or 10**9),
            _text(row.get("code")),
        )
    )
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    preferred = [
        "master_research_rank", "code", "stock_name", "industry",
        "terminal_decision", "terminal_reason_class", "terminal_reason_codes",
        "terminal_retryable_next_cycle", "terminal_evidence_complete",
        "terminal_full_review_attempted", "terminal_formal_buy_authorized",
        "terminal_current_price", "wait_price_reference", "wait_price_reference_source",
        "research_reference_ceiling", "research_reference_ceiling_semantics",
        "v31_candidate_class", "v31_score_total", "v31_hard_gates_passed",
        "v31_hard_gate_failures", "v31_hard_gate_unknowns", "v31_buy_ready",
        "v31_margin_reference_band", "production_action", "long_term_blockers",
        "valuation_model_execution_state", "financial_review_status",
        "valuation_diagnostic_status", "decision_authority", "formal_signal_eligible",
        "automatic_promotion_allowed", "no_auto_trade", "terminal_policy_version",
        "disclaimer",
    ]
    fields = list(preferred)
    for key in sorted({key for row in rows for key in row}):
        if key not in fields:
            fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(master_ranking_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    source = _read(master_ranking_dir / "master_opportunity_ranking.csv")
    rows = build_terminal_rows(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "candidate_terminal_decisions.csv", rows)

    counts = Counter(row["terminal_decision"] for row in rows)
    reason_counts = Counter(row["terminal_reason_class"] for row in rows)
    unauthorized_buy_count = sum(
        row["terminal_decision"] == "BUY" and not row["terminal_formal_buy_authorized"]
        for row in rows
    )
    summary = {
        "candidate_count": len(rows),
        "terminalized_count": len(rows),
        "buy_count": counts["BUY"],
        "wait_price_count": counts["WAIT_PRICE"],
        "reject_count": counts["REJECT"],
        "reason_counts": dict(sorted(reason_counts.items())),
        "research_limbo_count": 0,
        "unauthorized_buy_count": unauthorized_buy_count,
        "formal_buy_is_mirror_only": True,
        "canonical_authority_unchanged": True,
        "hard_gate_unknown_is_pass": False,
        "no_auto_trade": True,
        "decision_authority": DECISION_AUTHORITY,
        "policy_version": POLICY_VERSION,
    }
    if summary["terminalized_count"] != summary["candidate_count"]:
        raise AssertionError("not every candidate was terminalized")
    if unauthorized_buy_count:
        raise AssertionError("unauthorized BUY escaped terminal layer")
    (output_dir / "candidate_terminal_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Candidate Terminal Decisions",
        "",
        DISCLAIMER,
        "",
        f"- candidates: {len(rows)}",
        f"- BUY: {counts['BUY']}",
        f"- WAIT_PRICE: {counts['WAIT_PRICE']}",
        f"- REJECT: {counts['REJECT']}",
        "- research limbo: 0",
        "- BUY authority: mirror of already-authorized frozen V3.1 Formal BUY only",
        "- WAIT_PRICE reference: research diagnostic only; never a standalone Formal BUY gate",
        "- UNKNOWN evidence: terminal REJECT/EVIDENCE_INSUFFICIENT for this cycle, retryable next cycle",
        "",
    ]
    for index, row in enumerate(rows, 1):
        wait = (
            f" | wait_ref={row.get('wait_price_reference')} ({row.get('wait_price_reference_source')})"
            if row["terminal_decision"] == "WAIT_PRICE"
            else ""
        )
        lines.append(
            f"{index}. {row.get('code','')} {row.get('stock_name','')} | "
            f"{row['terminal_decision']} | {row['terminal_reason_class']} | "
            f"{row['terminal_reason_codes']}{wait}"
        )
    (output_dir / "candidate_terminal_decisions.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-ranking-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_report(args.master_ranking_dir, args.output_dir)
    print(f"candidate_terminal_decisions={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
