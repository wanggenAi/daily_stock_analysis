"""Terminal research-only decisions for requested V3.1 deep-calculation worksets.

Every requested code converges to BUY, WAIT_PRICE, or REJECT at research authority.
UNKNOWN hard gates are never promoted: after bounded evidence recovery they converge
fail-closed to REJECT_EVIDENCE_INSUFFICIENT and may be reopened only by a new
evidence epoch. Formal/Production trading authority is never created here.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT = "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1"
DECISIONS = {"BUY", "WAIT_PRICE", "REJECT"}
GATES = ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")
PE_BUY_RATIO = 0.80
SPECIALIZED_INDUSTRY_PREFIXES = ("J66", "J67", "J68", "B08", "B09", "C32")


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


def _valuation_decision(row: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    industry = str(row.get("industry") or "").strip().upper()
    current_pe = _num(row.get("current_pe"))
    median_pe = _num(row.get("historical_median_pe_reference"))
    financial_status = str(row.get("financial_review_status") or "").upper()
    quality_conf = str(row.get("earnings_quality_confidence") or "").upper()
    quality_score = _num(row.get("earnings_quality_score"))
    expectation = str(row.get("expectation_state") or "").upper()
    snapshot = {
        "current_pe": current_pe,
        "historical_median_pe_reference": median_pe,
        "pe_to_history_ratio": (current_pe / median_pe) if current_pe and median_pe and median_pe > 0 else None,
        "financial_review_status": financial_status,
        "earnings_quality_confidence": quality_conf,
        "earnings_quality_score": quality_score,
        "expectation_state": expectation,
        "required_profit_growth_pct": _num(row.get("required_profit_growth_pct")),
    }
    if industry.startswith(SPECIALIZED_INDUSTRY_PREFIXES):
        return "REJECT", "SPECIALIZED_VALUATION_REQUIRED", snapshot
    if financial_status != "OK" or quality_conf != "HIGH":
        return "REJECT", "VALUATION_FINANCIAL_EVIDENCE_INCOMPLETE", snapshot
    if current_pe is None or median_pe is None or current_pe <= 0 or median_pe <= 0:
        return "REJECT", "VALUATION_REFERENCE_INCOMPLETE", snapshot
    ratio = current_pe / median_pe
    if ratio <= PE_BUY_RATIO and expectation == "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE":
        return "BUY", "ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT", snapshot
    return "WAIT_PRICE", "ALL_HARD_GATES_PASS_BUT_PRICE_NOT_AT_RESEARCH_BUY_THRESHOLD", snapshot


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
        profile = profiles.get(code) if isinstance(profiles.get(code), Mapping) else {}
        failed, unknown, passed = _gate_state(profile)
        valuation = valuation_by_code.get(code, {})
        priority = priority_by_code.get(code, {})
        if not profile:
            decision, reason = "REJECT", "DEEP_PROFILE_MISSING"
        elif failed:
            decision, reason = "REJECT", "HARD_GATE_FAIL"
        elif unknown:
            decision, reason = "REJECT", "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
        else:
            decision, reason, _ = _valuation_decision(valuation)

        _, _, valuation_snapshot = _valuation_decision(valuation)
        quant_score = _num(valuation.get("quant_score"))
        pe_ratio = valuation_snapshot.get("pe_to_history_ratio")
        evidence_blocked = decision == "REJECT" and reason == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
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
            }
        )

    order = {"BUY": 0, "WAIT_PRICE": 1, "REJECT": 2}
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
        "interpretation": "BUY/WAIT_PRICE are research-only outputs and never create Formal/Production authority. UNKNOWN hard gates converge fail-closed to REJECT after bounded evidence recovery and may reopen only on new evidence.",
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    counts = payload.get("decision_counts") or {}
    lines = [
        "# GenGe V3.1 Terminal Research Decisions",
        "",
        f"- requested: **{payload.get('requested_count', 0)}**",
        f"- BUY: **{counts.get('BUY', 0)}** / WAIT_PRICE: **{counts.get('WAIT_PRICE', 0)}** / REJECT: **{counts.get('REJECT', 0)}**",
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
        lines.append(
            f"- {row.get('code')} {row.get('name')}: quant={row.get('quant_score')}, PE/history={ratio}, unknown={','.join(row.get('hard_gate_unknowns') or [])}, urgent={reasons}"
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
        raise ValueError("not every requested code reached BUY/WAIT_PRICE/REJECT")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"requested_count": payload["requested_count"], "decision_counts": payload["decision_counts"], "urgent_research_count": len(payload["urgent_research_queue"])}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())