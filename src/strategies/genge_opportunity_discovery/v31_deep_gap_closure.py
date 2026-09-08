"""Bounded evidence-driven closure for automatic V3.1 deep review.

This module turns an execution-successful but research-partial deep calculation
into a process-terminal state in the SAME Lambda invocation. It may resolve a
qualitative gate only from strict verified evidence rules. Otherwise UNKNOWN is
preserved and the process terminates as EVIDENCE_EXHAUSTED rather than waiting
for a human to start another round.

It is research-only: it cannot create Formal BUY authority or place trades.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evidence_collectors import collect_auto_evidence

CONTRACT = "GEN_GE_V31_DEEP_GAP_CLOSURE_V1"
GATES = ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _requested_codes(raw: Iterable[str]) -> list[str]:
    return sorted({_code(x) for x in raw if _code(x)})


def _status(gate: Mapping[str, Any] | None) -> str:
    value = str((gate or {}).get("status") or "UNKNOWN").upper()
    return value if value in {"PASS", "FAIL"} else "UNKNOWN"


def _verified_official(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("evidence_status") or "").upper() == "VERIFIED"
        and str(row.get("source_type") or "").upper() == "OFFICIAL_REPORT"
        and bool(str(row.get("source_domain") or "").strip())
        and bool(str(row.get("publish_date") or row.get("date") or "").strip())
    )


def infer_long_term_demand(
    industry: str, industry_evidence: Iterable[Mapping[str, Any]]
) -> tuple[str, str, list[dict[str, Any]]]:
    """Resolve only from >=2 independent verified official domains, fail closed."""
    rows = [dict(r) for r in industry_evidence if str(r.get("industry") or "") == industry and _verified_official(r)]
    positive = {str(r.get("source_domain")) for r in rows if str(r.get("direction") or r.get("evidence_direction") or "").upper() in {"POSITIVE", "STRENGTHENING"}}
    negative = {str(r.get("source_domain")) for r in rows if str(r.get("direction") or r.get("evidence_direction") or "").upper() in {"NEGATIVE", "WEAKENING"}}
    evidence = [
        {
            "source_type": r.get("source_type"),
            "source_domain": r.get("source_domain"),
            "url": r.get("original_url") or r.get("source"),
            "publish_date": r.get("publish_date") or r.get("date"),
            "direction": r.get("direction") or r.get("evidence_direction"),
            "summary": r.get("normalized_summary") or r.get("evidence_value"),
        }
        for r in rows
    ]
    if len(positive) >= 2 and not negative:
        return "PASS", f"At least two independent verified official domains support long-term demand: {sorted(positive)}", evidence
    if len(negative) >= 2 and not positive:
        return "FAIL", f"At least two independent verified official domains weaken long-term demand: {sorted(negative)}", evidence
    if positive and negative:
        return "UNKNOWN", "Verified official evidence conflicts; fail-closed UNKNOWN retained.", evidence
    return "UNKNOWN", "Fewer than two independent same-direction verified official domains; evidence threshold not met.", evidence


def _unresolved_reason(gate: str, evidence_summary: Mapping[str, Any]) -> str:
    if gate == "long_term_demand":
        return "OFFICIAL_INDEPENDENT_CORROBORATION_THRESHOLD_NOT_MET"
    if gate == "moat":
        return "NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE"
    if gate == "predictability":
        return "NO_STRICT_MULTI_YEAR_PREDICTABILITY_RULE_PROVEN"
    if gate == "financial_safety":
        return "SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT"
    if gate == "earnings_authenticity":
        return "SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT"
    return "EVIDENCE_INSUFFICIENT"


def close_profiles(
    profiles_payload: Mapping[str, Any],
    candidate_rows: list[Mapping[str, Any]],
    *,
    requested_codes: Iterable[str],
    industry_evidence: list[Mapping[str, Any]],
    company_evidence: list[Mapping[str, Any]],
    evidence_audit: list[Mapping[str, Any]],
    evidence_summary: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = json.loads(json.dumps(profiles_payload, ensure_ascii=False))
    profiles = out.get("profiles") if isinstance(out.get("profiles"), dict) else {}
    rows_by_code = {_code(r.get("code")): dict(r) for r in candidate_rows if _code(r.get("code"))}
    requested = _requested_codes(requested_codes)
    progressed = 0
    unresolved: dict[str, dict[str, str]] = {}
    complete_codes: list[str] = []
    exhausted_codes: list[str] = []

    for code in requested:
        profile = profiles.get(code)
        if not isinstance(profile, dict):
            unresolved[code] = {"profile": "REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE"}
            exhausted_codes.append(code)
            continue
        gates = profile.get("gates") if isinstance(profile.get("gates"), dict) else {}
        row = rows_by_code.get(code, {})
        industry = str(profile.get("industry") or row.get("normalized_industry") or row.get("industry") or "")

        ltd = gates.get("long_term_demand") if isinstance(gates.get("long_term_demand"), dict) else None
        if ltd is not None and _status(ltd) == "UNKNOWN" and industry:
            decision, rationale, evidence = infer_long_term_demand(industry, industry_evidence)
            if decision in {"PASS", "FAIL"}:
                ltd.update({
                    "status": decision,
                    "confidence": "HIGH",
                    "rationale": rationale,
                    "evidence": evidence,
                    "source": "AUTOMATIC_OFFICIAL_EVIDENCE_CLOSURE",
                })
                progressed += 1
            else:
                ltd["gap_closure_evidence"] = evidence
                ltd["gap_closure_rationale"] = rationale

        code_unresolved: dict[str, str] = {}
        for gate in GATES:
            raw = gates.get(gate) if isinstance(gates.get(gate), dict) else None
            if raw is None or _status(raw) == "UNKNOWN":
                reason = _unresolved_reason(gate, evidence_summary)
                code_unresolved[gate] = reason
                if raw is not None:
                    raw["terminal_unresolved_reason"] = reason
        if code_unresolved:
            unresolved[code] = code_unresolved
            exhausted_codes.append(code)
            profile["research_terminal_state"] = "EVIDENCE_EXHAUSTED"
            profile["research_disposition"] = "EVIDENCE_BLOCKED" if str(row.get("production_shortlist_scope") or "") != "HOLDING" else "HOLD_REVIEW_EVIDENCE_BLOCKED"
        else:
            complete_codes.append(code)
            profile["research_terminal_state"] = "COMPLETE"
            profile["research_disposition"] = "DEEP_REVIEW_COMPLETE"

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    terminal_state = "COMPLETE" if not exhausted_codes else "EVIDENCE_EXHAUSTED"
    status = {
        "contract": CONTRACT,
        "execution_status": "SUCCESS",
        "run_state": "COMPLETED",
        "research_terminal_state": terminal_state,
        "research_outcome": terminal_state,
        "generated_at": now,
        "requested_count": len(requested),
        "complete_requested_count": len(complete_codes),
        "evidence_exhausted_requested_count": len(exhausted_codes),
        "progressed_gate_count": progressed,
        "unresolved_requested_gate_count": sum(len(v) for v in unresolved.values()),
        "unresolved_reasons": unresolved,
        "gap_closure_attempt_count": 1,
        "new_evidence_count": len(industry_evidence) + len(company_evidence),
        "evidence_audit_count": len(evidence_audit),
        "evidence_collection_summary": dict(evidence_summary),
        "immediate_retry_required": False,
        "retry_rule": "Retry only after genuinely new evidence/event; never loop on identical evidence.",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    out.update({
        "gap_closure_contract": CONTRACT,
        "gap_closure_generated_at": now,
        "research_terminal_state": terminal_state,
        "research_outcome": terminal_state,
        "gap_closure_attempt_count": 1,
        "new_evidence_count": status["new_evidence_count"],
        "progressed_gate_count": progressed,
        "immediate_retry_required": False,
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    })
    return out, status


def run(
    *,
    profiles_json: Path,
    candidate_csv: Path,
    output_dir: Path,
    cache_dir: Path,
    requested_codes: Iterable[str],
    as_of: date,
) -> dict[str, Any]:
    profiles = _read_json(profiles_json)
    rows = _read_csv(candidate_csv)
    requested = _requested_codes(requested_codes)
    selected = []
    for row in rows:
        code = _code(row.get("code"))
        if code not in requested:
            continue
        copy = dict(row)
        copy["normalized_industry"] = copy.get("normalized_industry") or copy.get("industry") or ""
        copy["stock_name"] = copy.get("stock_name") or copy.get("name") or ""
        selected.append(copy)

    industry_evidence, company_evidence, audit_rows, evidence_summary = collect_auto_evidence(
        priority_rows=selected,
        as_of=as_of,
        cache_dir=cache_dir,
        max_companies=max(1, len(selected)),
    )
    closed_profiles, status = close_profiles(
        profiles,
        rows,
        requested_codes=requested,
        industry_evidence=industry_evidence,
        company_evidence=company_evidence,
        evidence_audit=audit_rows,
        evidence_summary=evidence_summary,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "deep_review_profiles.json").write_text(json.dumps(closed_profiles, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "deep_calculation_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_packet = {
        "contract": CONTRACT,
        "as_of": as_of.isoformat(),
        "requested_codes": requested,
        "industry_evidence": industry_evidence,
        "company_evidence": company_evidence,
        "audit": audit_rows,
        "summary": evidence_summary,
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }
    (output_dir / "gap_closure_evidence.json").write_text(json.dumps(evidence_packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "deep_calculation.md").write_text(
        "# GenGe Deep Calculation Gap Closure\n\n"
        f"- execution: **SUCCESS**\n- terminal state: **{status['research_terminal_state']}**\n"
        f"- requested: **{status['requested_count']}**\n- complete: **{status['complete_requested_count']}**\n"
        f"- evidence exhausted: **{status['evidence_exhausted_requested_count']}**\n"
        f"- progressed gates: **{status['progressed_gate_count']}**\n"
        f"- unresolved gates: **{status['unresolved_requested_gate_count']}**\n"
        "- immediate retry required: **False**\n- UNKNOWN != PASS; no automatic Formal BUY; no auto trade.\n",
        encoding="utf-8",
    )
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-json", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/v31_deep_gap_closure"))
    parser.add_argument("--requested-codes", required=True)
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    requested = [x.strip() for x in args.requested_codes.replace(";", ",").split(",") if x.strip()]
    status = run(
        profiles_json=args.profiles_json,
        candidate_csv=args.candidate_csv,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        requested_codes=requested,
        as_of=date.fromisoformat(args.as_of),
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
