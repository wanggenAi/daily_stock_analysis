#!/usr/bin/env python3
"""Observer-only Near-BUY overlay for GenGe V3.1.1 terminal research output.

The overlay improves research recall without creating trade authority. It consumes
Candidate Terminal Review rows after they have already converged to BUY,
WAIT_PRICE, or REJECT and adds evidence-quality, asymmetric-opportunity and
starter-position advisory fields. It never changes the terminal/formal action,
Canonical Authority, frozen V3.1.1 gates, or no-auto-trade semantics.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

POLICY_VERSION = "near_buy_research_overlay_v2_evidence_recovery"
RESEARCH_AUTHORITY = "OBSERVER_ONLY_RESEARCH_OVERLAY"
EVIDENCE_STATES = frozenset({"SUFFICIENT", "MISSING", "CONFLICTED", "CONFIRMED_NEGATIVE"})
NEAR_BUY_STATE = "NEAR_BUY"
EVIDENCE_RECOVERY_STATE = "EVIDENCE_RECOVERY_PRIORITY"
NONE_STATE = "NONE"
RECOVERY_TIERS = ("A", "B", "C")
STARTER_FRACTION = 0.25
MIN_NEAR_BUY_SCORE = 70.0
FORWARD_HORIZONS = (5, 10, 20, 60)

_MISSING_REASON_CLASSES = frozenset(
    {
        "EVIDENCE_INSUFFICIENT",
        "FORMAL_REVIEW_NOT_PROVEN",
        "PRODUCTION_DECISION_MISSING",
    }
)
_NEAR_BUY_REASON_CLASSES = _MISSING_REASON_CLASSES | frozenset(
    {"NON_PRICE_WAIT", "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK"}
)
_CONFLICT_MARKERS = ("CONFLICT", "INCONSISTENT", "MISMATCH", "DISAGREE")
_NEGATIVE_MARKERS = (
    "STRUCTURAL_DECLINE",
    "HARD_GATE_FAILED",
    "FALSIFICATION_FAILED",
    "FALSIFICATION_FAIL",
    "FUNDAMENTAL_BREAK",
    "MOAT_FAILED",
    "FINANCIAL_SAFETY_FAILED",
    "EARNINGS_AUTHENTICITY_FAILED",
)
_READINESS_FIELDS = (
    "v31_score_complete",
    "v31_normalized_profit_ready",
    "v31_scenario_valuation_ready",
    "v31_implied_expectation_ready",
    "v31_expectation_gap_ready",
    "v31_risk_adjusted_cagr_ready",
    "v31_downside_ready",
    "v31_falsification_ready",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _tokens(value: Any) -> list[str]:
    text = _text(value).replace(",", ";")
    return [token.strip() for token in text.split(";") if token.strip()]


def _code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _evidence_components(row: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    missing: list[str] = []
    conflicts: list[str] = []
    negatives: list[str] = []

    hard_failures = _tokens(row.get("v31_hard_gate_failures"))
    hard_unknowns = _tokens(row.get("v31_hard_gate_unknowns"))
    negatives.extend(f"hard_gate:{item}" for item in hard_failures)
    missing.extend(f"hard_gate:{item}" for item in hard_unknowns)

    for field in _READINESS_FIELDS:
        value = row.get(field)
        if value not in (None, "") and not _bool(value):
            missing.append(field.removeprefix("v31_").removesuffix("_ready"))

    reason_class = _text(row.get("terminal_reason_class")).upper()
    if reason_class in _MISSING_REASON_CLASSES and not missing:
        missing.append(reason_class.lower())
    if reason_class == "HARD_GATE_FAILED":
        negatives.append("terminal:HARD_GATE_FAILED")

    evidence_text = ";".join(
        _tokens(row.get("terminal_reason_codes"))
        + _tokens(row.get("source_production_reason_codes"))
        + _tokens(row.get("valuation_provider_errors"))
        + _tokens(row.get("financial_provider_errors"))
    ).upper()
    for marker in _CONFLICT_MARKERS:
        if marker in evidence_text:
            conflicts.append(marker.lower())
    for marker in _NEGATIVE_MARKERS:
        if marker in evidence_text:
            negatives.append(marker.lower())

    return (
        list(dict.fromkeys(missing)),
        list(dict.fromkeys(conflicts)),
        list(dict.fromkeys(negatives)),
    )


def evidence_state(row: Mapping[str, Any]) -> tuple[str, list[str], list[str], list[str]]:
    missing, conflicts, negatives = _evidence_components(row)
    if negatives:
        state = "CONFIRMED_NEGATIVE"
    elif conflicts:
        state = "CONFLICTED"
    elif missing:
        state = "MISSING"
    else:
        state = "SUFFICIENT"
    if state not in EVIDENCE_STATES:
        raise AssertionError(f"invalid evidence state: {state}")
    return state, missing, conflicts, negatives


def _evidence_recovery_tier(
    row: Mapping[str, Any],
    *,
    state: str,
    hard_failures: Sequence[str],
    negatives: Sequence[str],
    conflicts: Sequence[str],
    exec_eligible: bool,
    retryable: bool,
    full_review: bool,
    terminal_decision: str,
) -> str | None:
    """Prioritize missing-only evidence recovery without creating trade authority."""
    if (
        terminal_decision != "REJECT"
        or state != "MISSING"
        or hard_failures
        or negatives
        or conflicts
        or not exec_eligible
        or not retryable
        or not full_review
    ):
        return None

    financial_ok = _text(row.get("financial_review_status")).upper() == "OK"
    valuation_ok = _text(row.get("valuation_diagnostic_status")).upper() == "OK"
    if not (financial_ok and valuation_ok):
        return None

    second_pass = _text(row.get("long_term_second_pass_status")).upper()
    quant_status = _text(row.get("quant_status")).upper()
    if second_pass == "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES":
        return "A"
    if quant_status == "PRIORITY_RESEARCH":
        return "B"
    if quant_status == "SECONDARY_RESEARCH":
        return "C"
    return None


def classify_terminal_row(row: Mapping[str, Any], *, starter_fraction: float = STARTER_FRACTION) -> dict[str, Any]:
    """Return an immutable observer projection for one terminalized candidate."""
    if not 0.20 <= starter_fraction <= 0.30:
        raise ValueError("starter_fraction must remain within the frozen research advisory band [0.20, 0.30]")

    original = dict(row)
    result = dict(row)
    state, missing, conflicts, negatives = evidence_state(row)
    terminal_decision = _text(row.get("terminal_decision")).upper()
    reason_class = _text(row.get("terminal_reason_class")).upper()
    score = _float(row.get("v31_score_total"))
    candidate_class = _text(row.get("v31_candidate_class")).upper()
    hard_failures = _tokens(row.get("v31_hard_gate_failures"))
    exec_eligible = _bool(row.get("v31_execution_universe_eligible")) or (
        _text(row.get("v31_execution_universe_status")).upper() == "EXECUTION_ELIGIBLE"
    )
    retryable = _bool(row.get("terminal_retryable_next_cycle"))
    full_review = _bool(row.get("terminal_full_review_attempted"))

    near_buy = bool(
        terminal_decision != "BUY"
        and terminal_decision in {"WAIT_PRICE", "REJECT"}
        and not hard_failures
        and not negatives
        and exec_eligible
        and retryable
        and full_review
        and candidate_class in {"A1", "A2", "A3"}
        and score is not None
        and score >= MIN_NEAR_BUY_SCORE
        and reason_class in _NEAR_BUY_REASON_CLASSES
        and state in {"MISSING", "CONFLICTED", "SUFFICIENT"}
    )

    recovery_tier = None if near_buy else _evidence_recovery_tier(
        row,
        state=state,
        hard_failures=hard_failures,
        negatives=negatives,
        conflicts=conflicts,
        exec_eligible=exec_eligible,
        retryable=retryable,
        full_review=full_review,
        terminal_decision=terminal_decision,
    )

    reason_codes: list[str] = []
    if near_buy:
        reason_codes.append("high_research_score_without_confirmed_negative")
        if terminal_decision == "WAIT_PRICE":
            reason_codes.append("already_terminal_wait_price")
        if missing:
            reason_codes.append("missing_evidence_not_negative_evidence")
        if conflicts:
            reason_codes.append("conflicted_evidence_requires_resolution")

    recovery_reason_codes: list[str] = []
    if recovery_tier:
        recovery_reason_codes.extend([
            "missing_evidence_requires_recovery",
            "financial_review_completed",
            "valuation_diagnostic_completed",
        ])
        if recovery_tier == "A":
            recovery_reason_codes.append("non_exit_profile_second_pass_completed")
        else:
            recovery_reason_codes.append(
                f"quant_research_priority:{_text(row.get('quant_status')).upper() or 'UNKNOWN'}"
            )

    if near_buy:
        opportunity_state = NEAR_BUY_STATE
    elif recovery_tier:
        opportunity_state = EVIDENCE_RECOVERY_STATE
    else:
        opportunity_state = NONE_STATE

    result.update(
        {
            "research_opportunity_state": opportunity_state,
            "near_buy_reason_codes": ";".join(reason_codes),
            "evidence_recovery_priority_tier": recovery_tier or "",
            "evidence_recovery_reason_codes": ";".join(recovery_reason_codes),
            "evidence_recovery_starter_allowed": False,
            "near_buy_evidence_state": state,
            "missing_evidence_items": ";".join(missing),
            "conflicted_evidence_items": ";".join(conflicts),
            "confirmed_negative_items": ";".join(negatives),
            "starter_position_advisory_allowed": near_buy,
            "starter_fraction_of_normal_target": starter_fraction if near_buy else None,
            "starter_advisory_research_only": True,
            "formal_action_unchanged": True,
            "canonical_authority_unchanged": True,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "near_buy_policy_version": POLICY_VERSION,
            "near_buy_authority": RESEARCH_AUTHORITY,
        }
    )
    if dict(row) != original:
        raise AssertionError("near-buy overlay mutated its source row")
    if result.get("terminal_decision") != row.get("terminal_decision"):
        raise AssertionError("near-buy overlay changed terminal decision")
    if near_buy and (negatives or hard_failures):
        raise AssertionError("Near-BUY emitted despite confirmed negative/hard failure")
    if recovery_tier and (negatives or hard_failures or conflicts):
        raise AssertionError("evidence recovery emitted despite negative/conflicted evidence")
    if recovery_tier and result["starter_position_advisory_allowed"]:
        raise AssertionError("missing-evidence recovery must never receive starter advisory")
    return result


def build_overlay(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected = [classify_terminal_row(row) for row in rows]
    tier_priority = {tier: index for index, tier in enumerate(RECOVERY_TIERS)}

    def sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        state = _text(row.get("research_opportunity_state"))
        rank = _float(row.get("master_research_rank")) or 10**9
        code = _code(row.get("code"))
        if state == NEAR_BUY_STATE:
            return (0, 0, -(_float(row.get("v31_score_total")) or -1.0), rank, code)
        if state == EVIDENCE_RECOVERY_STATE:
            tier = _text(row.get("evidence_recovery_priority_tier"))
            return (1, tier_priority.get(tier, 99), 0.0, rank, code)
        return (2, 99, 0.0, rank, code)

    projected.sort(key=sort_key)
    return projected


def summarize_overlay(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evidence_counts = Counter(_text(row.get("near_buy_evidence_state")) for row in rows)
    near_buy_count = sum(row.get("research_opportunity_state") == NEAR_BUY_STATE for row in rows)
    recovery_rows = [row for row in rows if row.get("research_opportunity_state") == EVIDENCE_RECOVERY_STATE]
    recovery_tiers = Counter(_text(row.get("evidence_recovery_priority_tier")) for row in recovery_rows)
    return {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "authority": RESEARCH_AUTHORITY,
        "candidate_count": len(rows),
        "near_buy_count": near_buy_count,
        "evidence_recovery_count": len(recovery_rows),
        "evidence_recovery_tier_counts": {tier: recovery_tiers.get(tier, 0) for tier in RECOVERY_TIERS},
        "evidence_state_counts": dict(sorted(evidence_counts.items())),
        "starter_fraction_of_normal_target": STARTER_FRACTION,
        "starter_fraction_band": [0.20, 0.30],
        "formal_action_unchanged": True,
        "canonical_authority_unchanged": True,
        "hard_gate_failure_can_be_near_buy": False,
        "confirmed_negative_can_be_near_buy": False,
        "evidence_recovery_starter_allowed": False,
        "unknown_evidence_is_pass": False,
        "evidence_recovery_is_formal_signal": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }


def evaluate_forward_outcomes(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate PIT/OOS forward observations for Near-BUY false-negative audit.

    Each observation may contain return_5d/10d/20d/60d, benchmark_return_*d,
    and max_drawdown_60d. Missing horizons stay missing; no return is invented.
    """
    horizons: dict[str, Any] = {}
    for days in FORWARD_HORIZONS:
        key = f"return_{days}d"
        benchmark_key = f"benchmark_return_{days}d"
        values = [value for row in observations if (value := _float(row.get(key))) is not None]
        excess = [
            value - benchmark
            for row in observations
            if (value := _float(row.get(key))) is not None
            and (benchmark := _float(row.get(benchmark_key))) is not None
        ]
        wins = [value for value in values if value > 0]
        losses = [value for value in values if value < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        horizons[str(days)] = {
            "observations": len(values),
            "average_return": statistics.fmean(values) if values else None,
            "median_return": statistics.median(values) if values else None,
            "win_rate": len(wins) / len(values) if values else None,
            "profit_loss_ratio": (
                (gross_win / len(wins)) / (gross_loss / len(losses))
                if wins and losses and gross_loss > 0
                else None
            ),
            "average_excess_return": statistics.fmean(excess) if excess else None,
            "excess_observations": len(excess),
        }
    drawdowns = [
        value for row in observations
        if (value := _float(row.get("max_drawdown_60d"))) is not None
    ]
    return {
        "schema_version": 1,
        "observer_only": True,
        "policy_version": POLICY_VERSION,
        "forward_horizons_trading_days": list(FORWARD_HORIZONS),
        "horizons": horizons,
        "max_drawdown_60d": {
            "observations": len(drawdowns),
            "average": statistics.fmean(drawdowns) if drawdowns else None,
            "worst": min(drawdowns) if drawdowns else None,
        },
        "causal_claims_allowed": False,
        "production_semantics_mutated": False,
        "canonical_authority_unchanged": True,
        "no_auto_trade": True,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "master_research_rank", "code", "stock_name", "terminal_decision",
        "research_opportunity_state", "near_buy_evidence_state", "near_buy_reason_codes",
        "evidence_recovery_priority_tier", "evidence_recovery_reason_codes",
        "missing_evidence_items", "conflicted_evidence_items", "confirmed_negative_items",
        "v31_candidate_class", "v31_score_total", "terminal_reason_class",
        "starter_position_advisory_allowed", "starter_fraction_of_normal_target",
        "evidence_recovery_starter_allowed", "starter_advisory_research_only", "formal_action_unchanged",
        "canonical_authority_unchanged", "automatic_promotion_allowed", "no_auto_trade",
        "near_buy_authority", "near_buy_policy_version",
    ]
    extra = [key for key in sorted({key for row in rows for key in row}) if key not in fields]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields + extra, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_overlay(terminal_csv: Path, output_dir: Path) -> list[dict[str, Any]]:
    rows = build_overlay(_read_csv(terminal_csv))
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "near_buy_research_overlay.csv", rows)
    summary = summarize_overlay(rows)
    (output_dir / "near_buy_research_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Near-BUY Research Overlay",
        "",
        "Observer-only: terminal/formal action and Canonical Authority are unchanged; no auto trade.",
        "",
        f"- candidates: {len(rows)}",
        f"- Near-BUY: {summary['near_buy_count']}",
        f"- Evidence recovery priority: {summary['evidence_recovery_count']} "
        f"(A={summary['evidence_recovery_tier_counts']['A']}, "
        f"B={summary['evidence_recovery_tier_counts']['B']}, "
        f"C={summary['evidence_recovery_tier_counts']['C']})",
        f"- starter advisory: {STARTER_FRACTION:.0%} of normal target for Near-BUY only",
        "- missing-evidence recovery: no starter position; UNKNOWN remains non-PASS",
        "",
    ]
    for row in rows:
        if row["research_opportunity_state"] != NEAR_BUY_STATE:
            continue
        lines.append(
            f"- {row.get('code')} {row.get('stock_name', '')}"
            f" | terminal={row.get('terminal_decision')}"
            f" | score={row.get('v31_score_total')}"
            f" | evidence={row.get('near_buy_evidence_state')}"
            f" | missing={row.get('missing_evidence_items') or 'none'}"
            f" | starter={row.get('starter_fraction_of_normal_target')}"
        )
    recovery_rows = [row for row in rows if row["research_opportunity_state"] == EVIDENCE_RECOVERY_STATE]
    if recovery_rows:
        lines.extend(["", "## Evidence Recovery Priority", ""])
        for row in recovery_rows[:50]:
            lines.append(
                f"- {row.get('code')} {row.get('stock_name', '')}"
                f" | tier={row.get('evidence_recovery_priority_tier')}"
                f" | master_rank={row.get('master_research_rank') or 'NA'}"
                f" | quant_status={row.get('quant_status') or 'NA'}"
                f" | missing={row.get('missing_evidence_items') or 'none'}"
                f" | next={row.get('next_research_action') or 'recover_v31_evidence'}"
                f" | starter=NOT_ALLOWED"
            )
    (output_dir / "near_buy_research_overlay.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_overlay(args.terminal_csv, args.output_dir)
    print(json.dumps(summarize_overlay(rows), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
