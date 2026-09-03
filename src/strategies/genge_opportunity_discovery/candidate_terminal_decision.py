"""Terminal research closure for every Master Opportunity Ranking candidate.

This module never creates trade authority.  It consumes the broad postscan
Master Opportunity Ranking as the candidate universe, then overlays existing
Formal-BUY and GenGe V3.1.1 Production outputs.  Every candidate ends the current
cycle as exactly BUY, WAIT_PRICE, or REJECT.

Safety invariants:
* BUY only mirrors an already-authorized Formal BUY + frozen Production BUY.
* WAIT_PRICE only mirrors a HIGH-confidence Production WAIT whose blocker is
  the frozen formal-BUY price gate; the wait price is the production 0.80 x
  neutral-value ceiling, never the looser V3.1 diagnostic bands.
* UNKNOWN/missing evidence remains non-pass and becomes a retryable current-cycle
  REJECT rather than indefinite RESEARCH_CANDIDATE / RAISE_ONLY limbo.
* Canonical Authority, Hard Gate, Confidence Gate and no-auto-trade are unchanged.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_model import FORMAL_BUY_MAX_PRICE_TO_NEUTRAL
from .selection_framework_v31 import assess_v31, execution_universe_status, merge_research_inputs

DISCLAIMER = "仅用于公开数据长期研究与人工复核，不构成买入或卖出建议，不应自动交易。"
POLICY_VERSION = "candidate_terminal_decision_v2_master_production_overlay"
DECISION_AUTHORITY = "RESEARCH_TERMINAL_VIEW"
TERMINAL_DECISIONS = frozenset({"BUY", "WAIT_PRICE", "REJECT"})
PRICE_ONLY_REASON_CODES = frozenset(
    {"BUY_MARGIN_OF_SAFETY_INSUFFICIENT", "PRICE_TOO_CLOSE_TO_BASE_VALUE"}
)
PRICE_WAIT_CONTEXT_CODES = frozenset({"CORE_POOL_CONFERS_NO_BUY_PRIVILEGE"})
CONFIDENCE_BLOCK_REASON_CODES = frozenset(
    {"BUY_VALUATION_CONFIDENCE_NOT_HIGH", "VALUATION_CONFIDENCE_NOT_HIGH", "STRICT_PIT_INPUT_INCOMPLETE"}
)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


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


def _tokens(value: Any) -> set[str]:
    text = _text(value).replace(",", ";")
    return {token.strip() for token in text.split(";") if token.strip()}


def _map(rows: Iterable[Mapping[str, Any]], *, candidate_only: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if candidate_only and _text(raw.get("decision_scope")).upper() != "CANDIDATE":
            continue
        code = _code(raw.get("code"))
        if code:
            result[code] = dict(raw)
    return result


def _current_price(*rows: Mapping[str, Any]) -> float | None:
    for row in rows:
        for key in ("current_price", "v31_current_price", "raw_latest_close"):
            value = _float(row.get(key))
            if value is not None and value > 0:
                return value
    return None


def _neutral_value(*rows: Mapping[str, Any]) -> float | None:
    for row in rows:
        for key in ("neutral_value", "v31_neutral_value"):
            value = _float(row.get(key))
            if value is not None and value > 0:
                return value
    return None


def _formal_buy_authorized(formal: Mapping[str, Any], production: Mapping[str, Any]) -> bool:
    return bool(
        _bool(formal.get("long_term_formal_buy_eligible"))
        and _bool(formal.get("v31_buy_ready"))
        and _text(production.get("production_action")).upper() == "BUY"
        and _text(production.get("valuation_confidence")).upper() == "HIGH"
        and _bool(production.get("production_model_frozen", True))
    )


def _attempted_deep_review(master: Mapping[str, Any]) -> bool:
    return bool(
        _text(master.get("valuation_research_rank"))
        or _text(master.get("valuation_model_execution_state"))
        or _text(master.get("financial_review_status"))
        or _text(master.get("valuation_diagnostic_status"))
    )


def _evidence_complete(assessment: Any) -> bool:
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


def terminalize_candidate(
    master: Mapping[str, Any],
    formal: Mapping[str, Any] | None = None,
    production: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    master = dict(master)
    formal = dict(formal or {})
    production = dict(production or {})
    code = _code(master.get("code") or formal.get("code") or production.get("code"))
    merged = merge_research_inputs(master, formal, production)
    assessment = assess_v31(merged)
    current = _current_price(production, formal, master)
    neutral = _neutral_value(production, formal, master)
    action = _text(production.get("production_action")).upper()
    confidence = _text(production.get("valuation_confidence") or formal.get("valuation_confidence")).upper()
    reasons = _tokens(production.get("reason_codes"))
    full_review_attempted = _attempted_deep_review(master)
    evidence_complete = _evidence_complete(assessment)

    decision = "REJECT"
    reason_class = "EVIDENCE_INSUFFICIENT"
    reason_codes: list[str] = []
    retryable = True
    wait_price: float | None = None
    formal_authorized = False

    if execution_universe_status(code) != "EXECUTION_ELIGIBLE":
        reason_class = "EXECUTION_UNIVERSE_RESEARCH_ONLY"
        reason_codes = [f"execution_universe:{execution_universe_status(code)}"]
        retryable = False
    elif formal and production and _formal_buy_authorized(formal, production):
        decision = "BUY"
        reason_class = "FORMAL_BUY_READY"
        reason_codes = ["authorized_frozen_v31_production_buy"]
        retryable = False
        formal_authorized = True
        evidence_complete = True
    else:
        ratio = _float(production.get("formal_buy_max_price_to_neutral"))
        if ratio is None:
            ratio = FORMAL_BUY_MAX_PRICE_TO_NEUTRAL
        allowed_wait_reasons = PRICE_ONLY_REASON_CODES | PRICE_WAIT_CONTEXT_CODES
        price_only_wait = bool(reasons & PRICE_ONLY_REASON_CODES) and not bool(
            reasons - allowed_wait_reasons
        )
        if (
            action == "WAIT"
            and confidence == "HIGH"
            and price_only_wait
            and not (reasons & CONFIDENCE_BLOCK_REASON_CODES)
            and current is not None
            and neutral is not None
            and ratio is not None
            and ratio > 0
        ):
            candidate_wait = round(neutral * ratio, 4)
            if current > candidate_wait:
                decision = "WAIT_PRICE"
                reason_class = "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK"
                reason_codes = sorted(reasons & PRICE_ONLY_REASON_CODES)
                wait_price = candidate_wait
                retryable = True

        if decision == "REJECT":
            if assessment.hard_gate_failures:
                reason_class = "HARD_GATE_FAILED"
                reason_codes = [f"hard_gate_failed:{name}" for name in assessment.hard_gate_failures]
                retryable = False
            elif assessment.hard_gate_unknowns:
                reason_class = "EVIDENCE_INSUFFICIENT"
                reason_codes = [f"hard_gate_unknown:{name}" for name in assessment.hard_gate_unknowns]
            elif not full_review_attempted:
                reason_class = "DEEP_REVIEW_NOT_COMPLETED"
                reason_codes = ["master_candidate_not_valuation_researched"]
            elif not formal:
                reason_class = "FORMAL_REVIEW_NOT_PROVEN"
                reason_codes = ["candidate_not_admitted_to_strict_formal_review"]
            elif not production:
                reason_class = "PRODUCTION_DECISION_MISSING"
                reason_codes = ["authoritative_candidate_production_decision_missing"]
            elif not evidence_complete:
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
                reason_class = "EVIDENCE_INSUFFICIENT"
                reason_codes = [f"incomplete:{name}" for name, ready in readiness.items() if not ready]
            elif action == "WAIT":
                reason_class = "NON_PRICE_WAIT"
                reason_codes = sorted(reasons) or ["wait_reason_unavailable"]
            else:
                reason_class = "NON_BUY_PRODUCTION_ACTION"
                reason_codes = [f"production_action:{action or 'UNKNOWN'}"]

    result = dict(master)
    result.update(
        {
            "code": code,
            "terminal_decision": decision,
            "terminal_reason_class": reason_class,
            "terminal_reason_codes": ";".join(dict.fromkeys(reason_codes)),
            "terminal_retryable_next_cycle": retryable,
            "terminal_evidence_complete": evidence_complete,
            "terminal_full_review_attempted": full_review_attempted,
            "terminal_formal_buy_authorized": formal_authorized,
            "terminal_current_price": current,
            "wait_price_max": wait_price,
            "wait_price_semantics": "frozen_formal_buy_ceiling" if wait_price is not None else "",
            "formal_buy_max_price_to_neutral": FORMAL_BUY_MAX_PRICE_TO_NEUTRAL,
            "source_production_action": action,
            "source_valuation_confidence": confidence,
            "source_production_reason_codes": ";".join(sorted(reasons)),
            "decision_authority": DECISION_AUTHORITY,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "terminal_policy_version": POLICY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    )
    for key, value in assessment.as_dict().items():
        if not _text(result.get(key)):
            result[key] = value
    if decision not in TERMINAL_DECISIONS:
        raise AssertionError(f"non-terminal decision emitted: {decision}")
    if decision == "BUY" and not formal_authorized:
        raise AssertionError("terminal layer attempted unauthorized BUY")
    return result


def build_terminal_rows(
    master_rows: Iterable[Mapping[str, Any]],
    formal_rows: Iterable[Mapping[str, Any]],
    production_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    formal_map = _map(formal_rows)
    production_map = _map(production_rows, candidate_only=True)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in master_rows:
        code = _code(raw.get("code"))
        if not code or code in seen:
            continue
        rows.append(terminalize_candidate(raw, formal_map.get(code), production_map.get(code)))
        seen.add(code)
    priority = {"BUY": 0, "WAIT_PRICE": 1, "REJECT": 2}
    rows.sort(key=lambda row: (priority[row["terminal_decision"]], float(row.get("master_research_rank") or 10**9), row["code"]))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    preferred = [
        "master_research_rank", "code", "stock_name", "industry", "terminal_decision",
        "terminal_reason_class", "terminal_reason_codes", "terminal_retryable_next_cycle",
        "terminal_evidence_complete", "terminal_full_review_attempted", "terminal_formal_buy_authorized",
        "terminal_current_price", "wait_price_max", "wait_price_semantics",
        "formal_buy_max_price_to_neutral", "source_production_action", "source_valuation_confidence",
        "source_production_reason_codes", "v31_candidate_class", "v31_score_total",
        "v31_hard_gates_passed", "v31_hard_gate_failures", "v31_hard_gate_unknowns",
        "v31_buy_ready", "decision_authority", "formal_signal_eligible",
        "automatic_promotion_allowed", "no_auto_trade", "terminal_policy_version", "disclaimer",
    ]
    fields = preferred + [key for key in sorted({k for row in rows for k in row}) if key not in preferred]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(master_csv: Path, formal_csv: Path, production_csv: Path, output_dir: Path) -> list[dict[str, Any]]:
    master_rows = _read(master_csv)
    formal_rows = _read(formal_csv)
    production_rows = _read(production_csv)
    rows = build_terminal_rows(master_rows, formal_rows, production_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "candidate_terminal_decisions.csv", rows)

    counts = Counter(row["terminal_decision"] for row in rows)
    reasons = Counter(row["terminal_reason_class"] for row in rows)
    summary = {
        "candidate_count": len(rows),
        "terminalized_count": len(rows),
        "buy_count": counts["BUY"],
        "wait_price_count": counts["WAIT_PRICE"],
        "reject_count": counts["REJECT"],
        "reason_counts": dict(sorted(reasons.items())),
        "research_limbo_count": 0,
        "unauthorized_buy_count": sum(row["terminal_decision"] == "BUY" and not row["terminal_formal_buy_authorized"] for row in rows),
        "wait_price_without_price_count": sum(row["terminal_decision"] == "WAIT_PRICE" and _float(row.get("wait_price_max")) is None for row in rows),
        "formal_buy_is_mirror_only": True,
        "formal_buy_max_price_to_neutral": FORMAL_BUY_MAX_PRICE_TO_NEUTRAL,
        "canonical_authority_unchanged": True,
        "hard_gate_unknown_is_pass": False,
        "no_auto_trade": True,
        "decision_authority": DECISION_AUTHORITY,
        "policy_version": POLICY_VERSION,
    }
    if summary["unauthorized_buy_count"] or summary["wait_price_without_price_count"]:
        raise AssertionError("terminal authority/price contract violated")
    (output_dir / "candidate_terminal_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Candidate Terminal Decisions", "", DISCLAIMER, "",
        f"- candidates: {len(rows)}", f"- BUY: {counts['BUY']}",
        f"- WAIT_PRICE: {counts['WAIT_PRICE']}", f"- REJECT: {counts['REJECT']}",
        "- research limbo: 0",
        f"- WAIT_PRICE ceiling: frozen Production gate <= {FORMAL_BUY_MAX_PRICE_TO_NEUTRAL:.2f} x neutral value",
        "- BUY authority: mirror of existing Formal BUY + frozen Production BUY only", "",
    ]
    for index, row in enumerate(rows, 1):
        price = f" | wait <= {row['wait_price_max']}" if row["terminal_decision"] == "WAIT_PRICE" else ""
        lines.append(f"{index}. {row['code']} {row.get('stock_name','')} | {row['terminal_decision']} | {row['terminal_reason_class']} | {row['terminal_reason_codes']}{price}")
    (output_dir / "candidate_terminal_decisions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-csv", type=Path, required=True)
    parser.add_argument("--formal-csv", type=Path, required=True)
    parser.add_argument("--production-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_report(args.master_csv, args.formal_csv, args.production_csv, args.output_dir)
    print(f"candidate_terminal_decisions={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
