"""Terminal research-only decisions for requested V3.1 deep-calculation worksets.

Every requested code converges to BUY, WAIT_PRICE, RESEARCH_GAP, or REJECT at research authority.
UNKNOWN hard gates are never promoted: after bounded evidence recovery they remain
explicit RESEARCH_GAP and may be reopened by new evidence. REJECT is reserved for
explicit hard-gate failure. Formal/Production trading authority is never created here.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .public_material_gate_recovery import merge_recovered_gates
from .v31_automatic_deep_calculation import (
    MACHINE_PASS_CASH_CONVERSION,
    MACHINE_PASS_EARNINGS_QUALITY,
)

CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
DECISIONS = {"BUY", "WAIT_PRICE", "RESEARCH_GAP", "REJECT"}
GATES = ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")
PE_BUY_RATIO = 0.80
SPECIALIZED_INDUSTRY_PREFIXES = ("J66", "J67", "J68", "B08", "B09", "C32")

# Research truth and capital deployment are deliberately separate.  UNKNOWN never
# becomes PASS, but a bounded advisory probe may be suggested when the two
# capital-preservation gates are explicitly PASS and the remaining uncertainty is
# compensated by valuation / quant evidence.  This layer never grants Formal BUY.
CAPITAL_MODEL_VERSION = "GEN_GE_RISK_BUDGET_CAPITAL_V1"
CAPITAL_ACTIONS = ("BUILD", "PROBE", "WATCH", "BLOCK")
CRITICAL_CAPITAL_GATES = ("financial_safety", "earnings_authenticity")
GATE_WEIGHTS = {
    "earnings_authenticity": 0.22,
    "financial_safety": 0.22,
    "long_term_demand": 0.20,
    "moat": 0.20,
    "predictability": 0.16,
}
UNKNOWN_GATE_PRIOR = 0.35
CAPITAL_PROBE_MAX_UNKNOWN = 2
CAPITAL_PROBE_MAX_PE_RATIO = 0.90
CAPITAL_PROBE_MIN_CONVICTION = 0.52


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _num(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _gate_state(profile: Mapping[str, Any]) -> tuple[list[str], list[str], int]:
    gates = profile.get("gates") if isinstance(profile.get("gates"), Mapping) else {}
    failed: list[str] = []
    unknown: list[str] = []
    passed = 0
    for gate in GATES:
        raw = gates.get(gate) if isinstance(gates.get(gate), Mapping) else {}
        status = str(raw.get("status") or "UNKNOWN").upper()
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed.append(gate)
        else:
            unknown.append(gate)
    return failed, unknown, passed


def _priority_meta(priority: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in priority.get("queue") or []:
        if not isinstance(row, Mapping):
            continue
        code = _code(row.get("code"))
        if code:
            out[code] = dict(row)
    return out


def _financial_gate_diagnostics(row: Mapping[str, Any]) -> dict[str, Any]:
    financial_status = str(row.get("financial_review_status") or "").upper()
    quality_conf = str(row.get("earnings_quality_confidence") or "").upper()
    cash_conversion = _num(row.get("cash_conversion_ratio"))
    quality_score = _num(row.get("earnings_quality_score"))
    normalized_profit = _num(row.get("normalized_core_operating_profit"))
    operating_cash = _num(row.get("operating_cash_flow"))
    blockers: list[str] = []

    if financial_status != "OK":
        blockers.append("FINANCIAL_REVIEW_STATUS_NOT_OK")
    if quality_conf != "HIGH":
        blockers.append("EARNINGS_QUALITY_CONFIDENCE_NOT_HIGH")
    if cash_conversion is None:
        blockers.append("CASH_CONVERSION_RATIO_MISSING")
    elif cash_conversion < MACHINE_PASS_CASH_CONVERSION:
        blockers.append("CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD")
    if quality_score is None:
        blockers.append("EARNINGS_QUALITY_SCORE_MISSING")
    elif quality_score < MACHINE_PASS_EARNINGS_QUALITY:
        blockers.append("EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD")
    if normalized_profit is None:
        blockers.append("NORMALIZED_CORE_OPERATING_PROFIT_MISSING")
    elif normalized_profit <= 0:
        blockers.append("NORMALIZED_CORE_OPERATING_PROFIT_NON_POSITIVE")
    if operating_cash is None:
        blockers.append("OPERATING_CASH_FLOW_MISSING")
    elif operating_cash <= 0:
        blockers.append("OPERATING_CASH_FLOW_NON_POSITIVE")

    return {
        "financial_review_status": financial_status,
        "earnings_quality_confidence": quality_conf,
        "cash_conversion_ratio": cash_conversion,
        "cash_conversion_pass_threshold": MACHINE_PASS_CASH_CONVERSION,
        "earnings_quality_score": quality_score,
        "earnings_quality_pass_threshold": MACHINE_PASS_EARNINGS_QUALITY,
        "normalized_core_operating_profit": normalized_profit,
        "operating_cash_flow": operating_cash,
        "financial_disclosure_date": str(row.get("financial_disclosure_date") or ""),
        "blockers": blockers,
        "machine_financial_pass_ready": not blockers,
    }


def _valuation_decision(row: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    industry = str(row.get("industry") or "").strip().upper()
    current_pe = _num(row.get("current_pe"))
    median_pe = _num(row.get("historical_median_pe_reference"))
    financial_status = str(row.get("financial_review_status") or "").upper()
    quality_conf = str(row.get("earnings_quality_confidence") or "").upper()
    quality_score = _num(row.get("earnings_quality_score"))
    expectation = str(row.get("expectation_state") or "").upper()
    financial_gate = _financial_gate_diagnostics(row)
    snapshot = {
        "current_pe": current_pe,
        "historical_median_pe_reference": median_pe,
        "pe_to_history_ratio": (current_pe / median_pe) if current_pe and median_pe and median_pe > 0 else None,
        "financial_review_status": financial_status,
        "earnings_quality_confidence": quality_conf,
        "earnings_quality_score": quality_score,
        "expectation_state": expectation,
        "required_profit_growth_pct": _num(row.get("required_profit_growth_pct")),
        "financial_gate_diagnostics": financial_gate,
    }
    if industry.startswith(SPECIALIZED_INDUSTRY_PREFIXES):
        return "RESEARCH_GAP", "SPECIALIZED_VALUATION_REQUIRED", snapshot
    if financial_status != "OK" or quality_conf != "HIGH":
        return "RESEARCH_GAP", "VALUATION_FINANCIAL_EVIDENCE_INCOMPLETE", snapshot
    if current_pe is None or median_pe is None or current_pe <= 0 or median_pe <= 0:
        return "RESEARCH_GAP", "VALUATION_REFERENCE_INCOMPLETE", snapshot
    ratio = current_pe / median_pe
    if ratio <= PE_BUY_RATIO and expectation == "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE":
        return "BUY", "ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT", snapshot
    return "WAIT_PRICE", "ALL_HARD_GATES_PASS_BUT_PRICE_NOT_AT_RESEARCH_BUY_THRESHOLD", snapshot


def _capital_allocation_advisory(
    *,
    profile: Mapping[str, Any],
    failed: list[str],
    unknown: list[str],
    valuation: Mapping[str, Any],
    valuation_snapshot: Mapping[str, Any],
    research_decision: str,
) -> dict[str, Any]:
    """Convert uncertainty into bounded advisory sizing instead of fake certainty.

    The research decision remains unchanged.  This function only answers whether
    the evidence/valuation mix is strong enough to justify a small *manual*
    research position.  It cannot authorize orders or mutate Formal actions.
    """
    gates = profile.get("gates") if isinstance(profile.get("gates"), Mapping) else {}
    gate_scores: dict[str, float] = {}
    unknown_weight = 0.0
    for gate, weight in GATE_WEIGHTS.items():
        raw = gates.get(gate) if isinstance(gates.get(gate), Mapping) else {}
        status = str(raw.get("status") or "UNKNOWN").upper()
        if status == "PASS":
            gate_scores[gate] = 1.0
        elif status == "FAIL":
            gate_scores[gate] = 0.0
        else:
            gate_scores[gate] = UNKNOWN_GATE_PRIOR
            unknown_weight += weight

    evidence_score = sum(GATE_WEIGHTS[g] * gate_scores[g] for g in GATE_WEIGHTS)
    pe_ratio = _num(valuation_snapshot.get("pe_to_history_ratio"))
    # 1.05x historical PE => zero valuation support; 0.60x or cheaper => full support.
    valuation_score = _clamp((1.05 - pe_ratio) / 0.45) if pe_ratio is not None else 0.0
    quant_score_raw = _num(valuation.get("quant_score"))
    quant_score = _clamp((quant_score_raw or 0.0) / 100.0)
    quality_score_raw = _num(valuation_snapshot.get("earnings_quality_score"))
    quality_score = _clamp((quality_score_raw or 0.0) / 100.0)
    uncertainty_penalty = 0.30 * unknown_weight
    conviction = _clamp(
        0.40 * evidence_score
        + 0.25 * valuation_score
        + 0.20 * quant_score
        + 0.15 * quality_score
        - uncertainty_penalty
    )

    financial_diag = (
        valuation_snapshot.get("financial_gate_diagnostics")
        if isinstance(valuation_snapshot.get("financial_gate_diagnostics"), Mapping)
        else {}
    )
    critical_pass = all(
        str((gates.get(g) or {}).get("status") or "UNKNOWN").upper() == "PASS"
        for g in CRITICAL_CAPITAL_GATES
    )
    specialized = str(valuation.get("industry") or "").strip().upper().startswith(
        SPECIALIZED_INDUSTRY_PREFIXES
    )
    action = "WATCH"
    reason = "UNCERTAINTY_OR_EDGE_NOT_STRONG_ENOUGH"
    max_portfolio_pct = 0.0

    if failed:
        action, reason = "BLOCK", "HARD_GATE_FAIL"
    elif not critical_pass:
        action, reason = "BLOCK", "CRITICAL_CAPITAL_GATES_NOT_PROVEN"
    elif financial_diag.get("machine_financial_pass_ready") is not True:
        action, reason = "BLOCK", "FINANCIAL_DIAGNOSTICS_NOT_PROBE_READY"
    elif specialized:
        action, reason = "WATCH", "SPECIALIZED_VALUATION_REQUIRED"
    elif pe_ratio is None:
        action, reason = "WATCH", "VALUATION_REFERENCE_INCOMPLETE"
    elif research_decision == "BUY":
        action, reason = "BUILD", "ALL_GATES_PASS_AND_RESEARCH_BUY"
        max_portfolio_pct = min(3.0, max(1.0, 3.5 * conviction))
    elif (
        len(unknown) <= CAPITAL_PROBE_MAX_UNKNOWN
        and pe_ratio <= CAPITAL_PROBE_MAX_PE_RATIO
        and conviction >= CAPITAL_PROBE_MIN_CONVICTION
    ):
        action, reason = "PROBE", "BOUNDED_UNCERTAINTY_WITH_VALUATION_MARGIN"
        max_portfolio_pct = min(
            1.5,
            max(0.5, 2.0 * conviction * max(0.0, 1.0 - unknown_weight)),
        )
    elif pe_ratio > CAPITAL_PROBE_MAX_PE_RATIO:
        action, reason = "WATCH", "PRICE_MARGIN_TOO_SMALL_FOR_UNCERTAIN_PROBE"

    return {
        "model_version": CAPITAL_MODEL_VERSION,
        "action": action,
        "reason": reason,
        "authority": "ADVISORY_ONLY",
        "automatic_execution_allowed": False,
        "formal_buy_authorized": False,
        "no_auto_trade": True,
        "critical_capital_gates": list(CRITICAL_CAPITAL_GATES),
        "critical_capital_gates_pass": critical_pass,
        "gate_weights": dict(GATE_WEIGHTS),
        "evidence_score": round(evidence_score, 4),
        "unknown_weight": round(unknown_weight, 4),
        "valuation_score": round(valuation_score, 4),
        "quant_score_component": round(quant_score, 4),
        "earnings_quality_component": round(quality_score, 4),
        "uncertainty_penalty": round(uncertainty_penalty, 4),
        "capital_conviction_score": round(conviction, 4),
        "suggested_max_portfolio_pct": round(max_portfolio_pct, 2),
        "probe_rules": {
            "max_unknown_gates": CAPITAL_PROBE_MAX_UNKNOWN,
            "max_pe_to_history_ratio": CAPITAL_PROBE_MAX_PE_RATIO,
            "min_capital_conviction_score": CAPITAL_PROBE_MIN_CONVICTION,
        },
    }


def build_terminal_decisions(
    *,
    profiles_payload: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
    valuation_rows: Iterable[Mapping[str, Any]],
    priority_payload: Mapping[str, Any] | None = None,
    deep_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if profiles_payload.get("unknown_is_pass") is not False:
        raise ValueError("deep profiles must preserve UNKNOWN != PASS")
    if profiles_payload.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("deep profiles must not grant Formal BUY")
    if profiles_payload.get("no_auto_trade") is not True:
        raise ValueError("deep profiles must preserve no-auto-trade")

    profiles = profiles_payload.get("profiles") if isinstance(profiles_payload.get("profiles"), Mapping) else {}
    valuation_by_code = {_code(row.get("code")): dict(row) for row in valuation_rows if _code(row.get("code"))}
    priority_by_code = _priority_meta(priority_payload or {})
    requested = [_code(x) for x in (evidence_payload.get("requested_codes") or []) if _code(x)]
    requested = list(dict.fromkeys(requested))
    rows: list[dict[str, Any]] = []

    for code in requested:
        base_profile = profiles.get(code) if isinstance(profiles.get(code), Mapping) else {}
        profile = merge_recovered_gates(base_profile, evidence_payload, code) if base_profile else {}
        failed, unknown, passed = _gate_state(profile)
        valuation = valuation_by_code.get(code, {})
        priority = priority_by_code.get(code, {})
        if not profile:
            decision, reason = "RESEARCH_GAP", "DEEP_PROFILE_MISSING"
        elif failed:
            decision, reason = "REJECT", "HARD_GATE_FAIL"
        elif unknown:
            decision, reason = "RESEARCH_GAP", "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
        else:
            decision, reason, _ = _valuation_decision(valuation)

        _, _, valuation_snapshot = _valuation_decision(valuation)
        capital_allocation = _capital_allocation_advisory(
            profile=profile,
            failed=failed,
            unknown=unknown,
            valuation=valuation,
            valuation_snapshot=valuation_snapshot,
            research_decision=decision,
        ) if profile else {
            "model_version": CAPITAL_MODEL_VERSION,
            "action": "BLOCK",
            "reason": "DEEP_PROFILE_MISSING",
            "authority": "ADVISORY_ONLY",
            "automatic_execution_allowed": False,
            "formal_buy_authorized": False,
            "no_auto_trade": True,
            "suggested_max_portfolio_pct": 0.0,
        }
        quant_score = _num(valuation.get("quant_score"))
        pe_ratio = valuation_snapshot.get("pe_to_history_ratio")
        evidence_blocked = decision == "RESEARCH_GAP" and reason == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
        attractive_screen = bool(
            evidence_blocked
            and quant_score is not None
            and quant_score >= 65.0
            and pe_ratio is not None
            and pe_ratio <= 0.80
            and not str(valuation.get("industry") or "").strip().upper().startswith(SPECIALIZED_INDUSTRY_PREFIXES)
            and str(valuation.get("financial_review_status") or "").upper() == "OK"
            and str(valuation.get("earnings_quality_confidence") or "").upper() == "HIGH"
        )
        priority_level = str(priority.get("priority") or "").strip().upper()
        urgent_reasons: list[str] = []
        if evidence_blocked and priority_level == "P0":
            urgent_reasons.append("P0_EVIDENCE_BLOCKED")
        if attractive_screen:
            urgent_reasons.append("QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED")
        rows.append(
            {
                "code": code,
                "name": profile.get("name") or valuation.get("stock_name") or priority.get("name") or "",
                "industry": profile.get("industry") or valuation.get("industry") or priority.get("industry") or "",
                "research_decision": decision,
                "research_reason": reason,
                "research_authority": "RESEARCH_ONLY",
                "formal_buy_authorized": False,
                "no_auto_trade": True,
                "hard_gate_pass_count": passed,
                "hard_gate_failures": failed,
                "hard_gate_unknowns": unknown,
                "reopen_on_new_evidence": reason in {"EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY", "DEEP_PROFILE_MISSING", "VALUATION_REFERENCE_INCOMPLETE", "VALUATION_FINANCIAL_EVIDENCE_INCOMPLETE"},
                "quant_score": quant_score,
                "quant_status": valuation.get("quant_status") or "",
                "research_priority": priority.get("priority") or "",
                "success_archetype_similarity_score": _num(priority.get("success_archetype_similarity_score")),
                "success_archetype_id": priority.get("success_archetype_id") or "",
                "screening_attractiveness": "HIGH" if attractive_screen else "NORMAL",
                "urgent_research": bool(urgent_reasons),
                "urgent_research_reasons": urgent_reasons,
                "valuation": valuation_snapshot,
                "capital_allocation": capital_allocation,
            }
        )

    order = {"BUY": 0, "WAIT_PRICE": 1, "RESEARCH_GAP": 2, "REJECT": 3}
    rows.sort(key=lambda r: (order[r["research_decision"]], -(r.get("quant_score") or -1.0), r["code"]))
    urgent = [r for r in rows if r.get("urgent_research") is True]
    urgent.sort(
        key=lambda r: (
            0 if str(r.get("research_priority") or "").upper() == "P0" else 1,
            -(r.get("quant_score") or -1.0),
            (r.get("valuation") or {}).get("pe_to_history_ratio") or 999.0,
            r["code"],
        )
    )
    counts = {decision: sum(r["research_decision"] == decision for r in rows) for decision in DECISIONS}
    capital_action_counts = {
        action: sum((r.get("capital_allocation") or {}).get("action") == action for r in rows)
        for action in CAPITAL_ACTIONS
    }
    capital_probe_queue = [
        r for r in rows
        if (r.get("capital_allocation") or {}).get("action") in {"BUILD", "PROBE"}
    ]
    capital_probe_queue.sort(
        key=lambda r: (
            0 if (r.get("capital_allocation") or {}).get("action") == "BUILD" else 1,
            -float((r.get("capital_allocation") or {}).get("capital_conviction_score") or 0.0),
            r["code"],
        )
    )
    status = dict(deep_status or {})
    return {
        "contract": CONTRACT,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_deep_lambda_run_id": str(status.get("lambda_run_id") or profiles_payload.get("lambda_run_id") or ""),
        "source_every_industry_run_id": str(status.get("source_run_id") or ""),
        "requested_count": len(requested),
        "decision_counts": counts,
        "all_requested_terminal": len(rows) == len(requested) and all(r["research_decision"] in DECISIONS for r in rows),
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "terminal_rows": rows,
        "urgent_research_queue": urgent,
        "capital_model_version": CAPITAL_MODEL_VERSION,
        "capital_action_counts": capital_action_counts,
        "capital_probe_queue": capital_probe_queue,
        "capital_advisory_authority": "ADVISORY_ONLY",
        "capital_advisory_automatic_execution_allowed": False,
        "interpretation": "Research truth and capital sizing are separate: UNKNOWN never becomes PASS or Formal BUY, but bounded manual PROBE sizing may be suggested when critical financial gates are explicitly PASS and valuation/quant evidence compensates for limited noncritical uncertainty.",
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    counts = payload.get("decision_counts") or {}
    lines = [
        "# GenGe V3.1 Terminal Research Decisions",
        "",
        f"- requested: **{payload.get('requested_count', 0)}**",
        f"- BUY: **{counts.get('BUY', 0)}** / WAIT_PRICE: **{counts.get('WAIT_PRICE', 0)}** / RESEARCH_GAP: **{counts.get('RESEARCH_GAP', 0)}** / REJECT: **{counts.get('REJECT', 0)}**",
        f"- all requested terminal: **{payload.get('all_requested_terminal') is True}**",
        "- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.",
        "",
        "## Urgent evidence queue",
        "",
    ]
    urgent = payload.get("urgent_research_queue") or []
    if not urgent:
        lines.append("- None")
    for row in urgent:
        ratio = (row.get("valuation") or {}).get("pe_to_history_ratio")
        reasons = ",".join(row.get("urgent_research_reasons") or [])
        blockers = ((row.get("valuation") or {}).get("financial_gate_diagnostics") or {}).get("blockers") or []
        lines.append(
            f"- {row.get('code')} {row.get('name')}: quant={row.get('quant_score')}, PE/history={ratio}, unknown={','.join(row.get('hard_gate_unknowns') or [])}, financial_blockers={','.join(blockers) or 'NONE'}, urgent={reasons}"
        )
    lines += ["", "## Risk-budget capital advisory", ""]
    capital_counts = payload.get("capital_action_counts") or {}
    lines.append(
        f"- BUILD: **{capital_counts.get('BUILD', 0)}** / PROBE: **{capital_counts.get('PROBE', 0)}** / WATCH: **{capital_counts.get('WATCH', 0)}** / BLOCK: **{capital_counts.get('BLOCK', 0)}**"
    )
    lines.append("- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.")
    for row in payload.get("capital_probe_queue") or []:
        cap = row.get("capital_allocation") or {}
        lines.append(
            f"- {row.get('code')} {row.get('name')}: **{cap.get('action')}** / conviction={cap.get('capital_conviction_score')} / max_portfolio={cap.get('suggested_max_portfolio_pct')}%"
        )

    lines += ["", "## Terminal rows", ""]
    for row in payload.get("terminal_rows") or []:
        lines.append(
            f"- {row.get('code')} {row.get('name')}: **{row.get('research_decision')}** / {row.get('research_reason')}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-json", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--valuation-csv", type=Path, required=True)
    parser.add_argument("--priority-json", type=Path, default=Path("data/research_priority/latest.json"))
    parser.add_argument("--deep-status-json", type=Path, default=Path("data/deep_calculation/latest_status.json"))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    payload = build_terminal_decisions(
        profiles_payload=_read_json(args.profiles_json),
        evidence_payload=_read_json(args.evidence_json),
        valuation_rows=_read_csv(args.valuation_csv),
        priority_payload=_read_json(args.priority_json) if args.priority_json.is_file() else {},
        deep_status=_read_json(args.deep_status_json) if args.deep_status_json.is_file() else {},
    )
    if payload["all_requested_terminal"] is not True:
        raise ValueError("not every requested code reached BUY/WAIT_PRICE/RESEARCH_GAP/REJECT")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"requested_count": payload["requested_count"], "decision_counts": payload["decision_counts"], "urgent_research_count": len(payload["urgent_research_queue"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
