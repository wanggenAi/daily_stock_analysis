"""Bounded evidence-driven closure for automatic V3.1 deep review.

An execution-successful but research-partial calculation is closed in the SAME
Lambda invocation. Strict verified evidence may resolve a qualitative gate;
otherwise UNKNOWN is preserved and the process terminates as
EVIDENCE_EXHAUSTED instead of waiting for a human to start another round.

Transient official-source failures receive one bounded refetch attempt with a
fresh cache namespace. Identical evidence is never used to create an infinite
retry loop. This module is research-only and cannot create Formal BUY authority
or place trades.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evidence_collectors import collect_auto_evidence
from .evidence_collectors.multi_year_predictability import (
    collect_multi_year_predictability_evidence,
)

CONTRACT = "GEN_GE_V31_DEEP_GAP_CLOSURE_V1"
GATES = ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")
MAX_COLLECTION_ATTEMPTS = 2
CONTINUITY_CONFIG = Path("config/v31_explicit_deep_reviews.json")
CONTINUITY_TERMINAL = Path("data/deep_calculation/latest_research_decisions.json")

# Only VERIFIED, ACTIVE, HIGH-severity exchange-disclosed events can resolve a
# gate negatively. This is intentionally one-way: absence of a risk event never
# creates PASS. New high-confidence risk can also override an older PASS.
MATERIAL_EVENT_FAIL_GATES: Mapping[str, tuple[str, ...]] = {
    "ACCOUNTING_FRAUD": ("earnings_authenticity", "predictability"),
    "NON_STANDARD_AUDIT": ("earnings_authenticity",),
    "DEBT_DEFAULT": ("financial_safety", "predictability"),
    "BANKRUPTCY_RESTRUCTURING": ("financial_safety", "predictability"),
    "DELISTING_RISK": ("financial_safety", "predictability"),
    "FUNDS_OCCUPATION": ("financial_safety",),
    "ILLEGAL_GUARANTEE": ("financial_safety",),
}


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


def resolve_requested_codes(
    raw: Iterable[str],
    *,
    continuity_config: Path = CONTINUITY_CONFIG,
    terminal_path: Path = CONTINUITY_TERMINAL,
) -> list[str]:
    """Union live requests with durable research-workset continuity anchors.

    The previous implementation trusted only the workflow's current dynamic
    request list. A code could therefore disappear merely because one upstream
    queue stopped emitting it. That is an observability/continuity failure, not
    an explicit research retirement.

    Continuity has two auditable sources:
    * the latest persisted Terminal requested workset; and
    * ``continuity_required_codes`` in the existing RESEARCH_ONLY explicit
      review config, used to bootstrap names that were already dropped before
      this rule existed.

    This function only affects research coverage. It cannot create PASS, Formal
    BUY, or trading authority. Missing current profiles remain visible and are
    terminalized fail-closed as DEEP_PROFILE_MISSING.
    """
    codes = set(_requested_codes(raw))

    if continuity_config.is_file():
        config = _read_json(continuity_config)
        if config.get("contract") != "GEN_GE_V31_EXPLICIT_DEEP_REVIEW_V1":
            raise ValueError("unexpected continuity config contract")
        if config.get("authority") != "RESEARCH_ONLY":
            raise ValueError("continuity config must remain RESEARCH_ONLY")
        if config.get("automatic_formal_buy_allowed") is not False:
            raise ValueError("continuity config must not allow Formal BUY")
        if config.get("unknown_is_pass") is not False:
            raise ValueError("continuity config must preserve UNKNOWN != PASS")
        for raw_code in config.get("continuity_required_codes") or []:
            code = _code(raw_code)
            if code and code.isdigit() and len(code) == 6:
                codes.add(code)

    if terminal_path.is_file():
        terminal = _read_json(terminal_path)
        if terminal.get("research_authority") != "RESEARCH_ONLY":
            raise ValueError("terminal continuity source must remain RESEARCH_ONLY")
        if terminal.get("formal_trading_authority") is not False:
            raise ValueError("terminal continuity source must not grant Formal authority")
        if terminal.get("automatic_formal_buy_allowed") is not False:
            raise ValueError("terminal continuity source must not grant Formal BUY")
        if terminal.get("no_auto_trade") is not True:
            raise ValueError("terminal continuity source must preserve no-auto-trade")
        for row in terminal.get("terminal_rows") or []:
            if not isinstance(row, Mapping):
                continue
            code = _code(row.get("code"))
            if code and code.isdigit() and len(code) == 6:
                codes.add(code)

    return sorted(codes)


def _status(gate: Mapping[str, Any] | None) -> str:
    value = str((gate or {}).get("status") or "UNKNOWN").upper()
    return value if value in {"PASS", "FAIL"} else "UNKNOWN"


def _source_family(value: Any) -> str:
    domain = str(value or "").strip().lower().rstrip(".")
    while domain.startswith("www."):
        domain = domain[4:]
    return domain


def _verified_official(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("evidence_status") or "").upper() == "VERIFIED"
        and str(row.get("source_type") or "").upper() == "OFFICIAL_REPORT"
        and bool(_source_family(row.get("source_domain")))
        and bool(str(row.get("publish_date") or row.get("date") or "").strip())
    )


def _official_exchange_domain(value: Any) -> bool:
    domain = _source_family(value)
    return bool(
        domain == "cninfo.com.cn"
        or domain.endswith(".cninfo.com.cn")
        or domain == "sse.com.cn"
        or domain.endswith(".sse.com.cn")
    )


def _verified_active_high_material_event(row: Mapping[str, Any], code: str) -> bool:
    event_type = str(row.get("event_type") or "").upper()
    return bool(
        _code(row.get("code")) == code
        and str(row.get("evidence_status") or "").upper() == "VERIFIED"
        and str(row.get("source_type") or "").upper() == "EXCHANGE_DISCLOSURE"
        and _official_exchange_domain(row.get("source_domain"))
        and str(row.get("evidence_kind") or "").lower() == "material_event"
        and str(row.get("event_status") or "").upper() == "ACTIVE"
        and str(row.get("event_severity") or "").upper() == "HIGH"
        and event_type in MATERIAL_EVENT_FAIL_GATES
        and bool(str(row.get("publish_date") or row.get("date") or "").strip())
    )


def _material_event_evidence(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_type": row.get("source_type"),
        "source_domain": row.get("source_domain"),
        "url": row.get("original_url") or row.get("source"),
        "publish_date": row.get("publish_date") or row.get("date"),
        "event_type": row.get("event_type"),
        "event_status": row.get("event_status"),
        "event_severity": row.get("event_severity"),
        "summary": row.get("normalized_summary") or row.get("evidence_value"),
    }


def infer_material_event_gate_failures(
    code: str, company_evidence: Iterable[Mapping[str, Any]]
) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    """Return strict FAIL decisions created by current verified material risks."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    event_types: dict[str, set[str]] = {}
    for raw in company_evidence:
        if not _verified_active_high_material_event(raw, code):
            continue
        event_type = str(raw.get("event_type") or "").upper()
        evidence = _material_event_evidence(raw)
        for gate in MATERIAL_EVENT_FAIL_GATES[event_type]:
            grouped.setdefault(gate, []).append(evidence)
            event_types.setdefault(gate, set()).add(event_type)

    result: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for gate, evidence in grouped.items():
        types = ",".join(sorted(event_types.get(gate) or set()))
        rationale = (
            "Verified ACTIVE/HIGH exchange disclosure establishes a material "
            f"risk incompatible with {gate}: {types}."
        )
        result[gate] = (rationale, evidence)
    return result


def infer_long_term_demand(
    industry: str, industry_evidence: Iterable[Mapping[str, Any]]
) -> tuple[str, str, list[dict[str, Any]]]:
    """Resolve only from >=2 independent verified official source families."""
    rows = [
        dict(r)
        for r in industry_evidence
        if str(r.get("industry") or "") == industry and _verified_official(r)
    ]
    positive = {
        _source_family(r.get("source_domain"))
        for r in rows
        if str(r.get("direction") or r.get("evidence_direction") or "").upper()
        in {"POSITIVE", "STRENGTHENING"}
    }
    negative = {
        _source_family(r.get("source_domain"))
        for r in rows
        if str(r.get("direction") or r.get("evidence_direction") or "").upper()
        in {"NEGATIVE", "WEAKENING"}
    }
    evidence = [
        {
            "source_type": r.get("source_type"),
            "source_domain": r.get("source_domain"),
            "source_family": _source_family(r.get("source_domain")),
            "url": r.get("original_url") or r.get("source"),
            "publish_date": r.get("publish_date") or r.get("date"),
            "direction": r.get("direction") or r.get("evidence_direction"),
            "summary": r.get("normalized_summary") or r.get("evidence_value"),
        }
        for r in rows
    ]
    if len(positive) >= 2 and not negative:
        return (
            "PASS",
            f"At least two independent verified official source families support long-term demand: {sorted(positive)}",
            evidence,
        )
    if len(negative) >= 2 and not positive:
        return (
            "FAIL",
            f"At least two independent verified official source families weaken long-term demand: {sorted(negative)}",
            evidence,
        )
    if positive and negative:
        return "UNKNOWN", "Verified official evidence conflicts; fail-closed UNKNOWN retained.", evidence
    return (
        "UNKNOWN",
        "Fewer than two independent same-direction verified official source families; evidence threshold not met.",
        evidence,
    )


def infer_predictability(
    code: str, company_evidence: Iterable[Mapping[str, Any]]
) -> tuple[str, str, list[dict[str, Any]]]:
    """Consume only dedicated strict multi-year official predictability evidence."""
    rows = [
        dict(row)
        for row in company_evidence
        if _code(row.get("code")) == code
        and str(row.get("evidence_kind") or "").lower() == "multi_year_predictability"
        and _official_exchange_domain(row.get("source_domain"))
    ]
    evidence = [
        {
            "source_type": row.get("source_type"),
            "source_domain": row.get("source_domain"),
            "url": row.get("original_url") or row.get("source"),
            "source_urls": row.get("source_urls") or [],
            "publish_date": row.get("publish_date") or row.get("date"),
            "rule_version": row.get("rule_version"),
            "coverage_years": row.get("coverage_years") or [],
            "metrics_by_year": row.get("metrics_by_year") or [],
            "cyclical_or_resource": bool(row.get("cyclical_or_resource")),
            "classification": row.get("predictability_classification"),
            "reason_code": row.get("reason_code"),
            "summary": row.get("normalized_summary") or row.get("evidence_value"),
        }
        for row in rows
    ]
    verified = [
        row
        for row in rows
        if str(row.get("evidence_status") or "").upper() == "VERIFIED"
        and bool(row.get("adopted_for_gate"))
        and str(row.get("predictability_classification") or "").upper() in {"PASS", "FAIL"}
        and bool(str(row.get("publish_date") or "").strip())
    ]
    decisions = {str(row.get("predictability_classification") or "").upper() for row in verified}
    if len(decisions) == 1:
        decision = next(iter(decisions))
        return (
            decision,
            "Strict multi-year official-report predictability rule resolved the gate: "
            + ",".join(sorted({str(row.get("reason_code") or "") for row in verified})),
            evidence,
        )
    if len(decisions) > 1:
        return "UNKNOWN", "Strict predictability evidence conflicts; fail-closed UNKNOWN retained.", evidence
    reason_codes = sorted({str(row.get("reason_code") or "") for row in rows if row.get("reason_code")})
    reason = reason_codes[0] if len(reason_codes) == 1 else "STRICT_MULTI_YEAR_PREDICTABILITY_THRESHOLD_NOT_MET"
    return "UNKNOWN", reason, evidence


def _unresolved_reason(gate: str, evidence_summary: Mapping[str, Any]) -> str:
    fetch_failures = int(evidence_summary.get("final_failed_count") or evidence_summary.get("failed_count") or 0)
    if gate == "long_term_demand":
        if fetch_failures:
            return "OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET"
        return "OFFICIAL_INDEPENDENT_CORROBORATION_THRESHOLD_NOT_MET"
    if gate == "moat":
        return "NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE"
    if gate == "predictability":
        return str(evidence_summary.get("predictability_unresolved_reason") or "NO_STRICT_MULTI_YEAR_PREDICTABILITY_RULE_PROVEN")
    if gate == "financial_safety":
        return "SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT"
    if gate == "earnings_authenticity":
        return "SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT"
    return "EVIDENCE_INSUFFICIENT"


def _evidence_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("content_hash") or ""),
        str(row.get("original_url") or row.get("source") or ""),
        str(row.get("code") or ""),
        str(row.get("industry") or ""),
        str(row.get("indicator") or ""),
        str(row.get("publish_date") or row.get("date") or ""),
    )


def _dedupe(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for raw in rows:
        row = dict(raw)
        key = _evidence_key(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


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
    material_event_failed_gates = 0
    material_event_pass_overrides = 0
    predictability_resolved_gates = 0
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

        risk_failures = infer_material_event_gate_failures(code, company_evidence)
        for gate, (rationale, evidence) in risk_failures.items():
            raw = gates.get(gate) if isinstance(gates.get(gate), dict) else None
            if raw is None or _status(raw) == "FAIL":
                continue
            previous = _status(raw)
            raw.update(
                {
                    "status": "FAIL",
                    "confidence": "HIGH",
                    "rationale": rationale,
                    "evidence": evidence,
                    "source": "AUTOMATIC_VERIFIED_MATERIAL_EVENT_CLOSURE",
                }
            )
            raw.pop("terminal_unresolved_reason", None)
            progressed += 1
            material_event_failed_gates += 1
            if previous == "PASS":
                material_event_pass_overrides += 1

        ltd = gates.get("long_term_demand") if isinstance(gates.get("long_term_demand"), dict) else None
        if ltd is not None and _status(ltd) == "UNKNOWN" and industry:
            decision, rationale, evidence = infer_long_term_demand(industry, industry_evidence)
            if decision in {"PASS", "FAIL"}:
                ltd.update(
                    {
                        "status": decision,
                        "confidence": "HIGH",
                        "rationale": rationale,
                        "evidence": evidence,
                        "source": "AUTOMATIC_OFFICIAL_EVIDENCE_CLOSURE",
                    }
                )
                ltd.pop("terminal_unresolved_reason", None)
                progressed += 1
            else:
                ltd["gap_closure_evidence"] = evidence
                ltd["gap_closure_rationale"] = rationale

        predictability = gates.get("predictability") if isinstance(gates.get("predictability"), dict) else None
        if predictability is not None and _status(predictability) == "UNKNOWN":
            decision, rationale, evidence = infer_predictability(code, company_evidence)
            if decision in {"PASS", "FAIL"}:
                predictability.update(
                    {
                        "status": decision,
                        "confidence": "HIGH",
                        "rationale": rationale,
                        "evidence": evidence,
                        "source": "AUTOMATIC_STRICT_MULTI_YEAR_OFFICIAL_EVIDENCE_CLOSURE",
                    }
                )
                predictability.pop("terminal_unresolved_reason", None)
                progressed += 1
                predictability_resolved_gates += 1
            else:
                predictability["gap_closure_evidence"] = evidence
                predictability["gap_closure_rationale"] = rationale

        code_unresolved: dict[str, str] = {}
        for gate in GATES:
            raw = gates.get(gate) if isinstance(gates.get(gate), dict) else None
            if raw is None or _status(raw) == "UNKNOWN":
                reason = _unresolved_reason(gate, evidence_summary)
                if gate == "predictability" and raw is not None:
                    reason = str(raw.get("gap_closure_rationale") or reason)
                code_unresolved[gate] = reason
                if raw is not None:
                    raw["terminal_unresolved_reason"] = reason
        if code_unresolved:
            unresolved[code] = code_unresolved
            exhausted_codes.append(code)
            profile["research_terminal_state"] = "EVIDENCE_EXHAUSTED"
            profile["research_disposition"] = "EVIDENCE_BLOCKED"
        else:
            complete_codes.append(code)
            profile["research_terminal_state"] = "COMPLETE"
            profile["research_disposition"] = "DEEP_REVIEW_COMPLETE"

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    terminal_state = "COMPLETE" if not exhausted_codes else "EVIDENCE_EXHAUSTED"
    attempt_count = int(evidence_summary.get("collection_attempt_count") or 1)
    new_evidence_count = int(
        evidence_summary.get("unique_evidence_count")
        or (len(industry_evidence) + len(company_evidence))
    )
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
        "predictability_resolved_gate_count": predictability_resolved_gates,
        "material_event_failed_gate_count": material_event_failed_gates,
        "material_event_pass_override_count": material_event_pass_overrides,
        "unresolved_requested_gate_count": sum(len(v) for v in unresolved.values()),
        "unresolved_reasons": unresolved,
        "gap_closure_attempt_count": attempt_count,
        "new_evidence_count": new_evidence_count,
        "evidence_audit_count": len(evidence_audit),
        "evidence_collection_summary": dict(evidence_summary),
        "immediate_retry_required": False,
        "retry_rule": "Transient source failures get bounded same-run refetch; identical evidence never loops. Future retry requires a new event/evidence epoch.",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    out.update(
        {
            "gap_closure_contract": CONTRACT,
            "gap_closure_generated_at": now,
            "research_terminal_state": terminal_state,
            "research_outcome": terminal_state,
            "gap_closure_attempt_count": attempt_count,
            "new_evidence_count": new_evidence_count,
            "progressed_gate_count": progressed,
            "predictability_resolved_gate_count": predictability_resolved_gates,
            "material_event_failed_gate_count": material_event_failed_gates,
            "material_event_pass_override_count": material_event_pass_overrides,
            "immediate_retry_required": False,
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
        }
    )
    return out, status


def _collect_with_bounded_retry(
    *,
    selected: list[Mapping[str, Any]],
    as_of: date,
    cache_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    all_industry: list[dict[str, Any]] = []
    all_company: list[dict[str, Any]] = []
    all_audit: list[dict[str, Any]] = []
    attempt_summaries: list[dict[str, Any]] = []

    for attempt in range(1, MAX_COLLECTION_ATTEMPTS + 1):
        industry, company, audit, summary = collect_auto_evidence(
            priority_rows=selected,
            as_of=as_of,
            cache_dir=cache_dir / f"attempt-{attempt}",
            max_companies=max(1, len(selected)),
        )
        all_industry.extend(industry)
        all_company.extend(company)
        all_audit.extend(audit)
        attempt_summaries.append(dict(summary))
        if int(summary.get("failed_count") or 0) == 0:
            break

    industry_unique = _dedupe(all_industry)
    company_unique = _dedupe(all_company)
    final_summary = {
        "collection_attempt_count": len(attempt_summaries),
        "max_collection_attempts": MAX_COLLECTION_ATTEMPTS,
        "attempts": attempt_summaries,
        "unique_industry_evidence_count": len(industry_unique),
        "unique_company_evidence_count": len(company_unique),
        "unique_evidence_count": len(industry_unique) + len(company_unique),
        "final_failed_count": int(attempt_summaries[-1].get("failed_count") or 0) if attempt_summaries else 0,
        "final_missing_count": int(attempt_summaries[-1].get("missing_count") or 0) if attempt_summaries else 0,
        "bounded_retry_exhausted": bool(
            len(attempt_summaries) == MAX_COLLECTION_ATTEMPTS
            and int(attempt_summaries[-1].get("failed_count") or 0) > 0
        ) if attempt_summaries else False,
    }
    return industry_unique, company_unique, all_audit, final_summary


def _predictability_unknown_rows(
    profiles_payload: Mapping[str, Any], selected: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    profiles = profiles_payload.get("profiles") if isinstance(profiles_payload.get("profiles"), dict) else {}
    result: list[dict[str, Any]] = []
    for raw in selected:
        row = dict(raw)
        code = _code(row.get("code"))
        profile = profiles.get(code) if isinstance(profiles.get(code), dict) else {}
        gates = profile.get("gates") if isinstance(profile.get("gates"), dict) else {}
        gate = gates.get("predictability") if isinstance(gates.get("predictability"), dict) else None
        if gate is not None and _status(gate) == "UNKNOWN":
            result.append(row)
    return result


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
    requested = resolve_requested_codes(requested_codes)
    selected: list[dict[str, Any]] = []
    for row in rows:
        code = _code(row.get("code"))
        if code not in requested:
            continue
        copy = dict(row)
        copy["normalized_industry"] = copy.get("normalized_industry") or copy.get("industry") or ""
        copy["stock_name"] = copy.get("stock_name") or copy.get("name") or ""
        selected.append(copy)

    industry_evidence, company_evidence, audit_rows, evidence_summary = _collect_with_bounded_retry(
        selected=selected,
        as_of=as_of,
        cache_dir=cache_dir,
    )

    predictability_selected = _predictability_unknown_rows(profiles, selected)
    predictability_evidence = collect_multi_year_predictability_evidence(
        priority_rows=predictability_selected,
        as_of=as_of,
    )
    company_evidence = _dedupe([*company_evidence, *predictability_evidence])
    evidence_summary["multi_year_predictability_requested_count"] = len(predictability_selected)
    evidence_summary["multi_year_predictability_evidence_count"] = len(predictability_evidence)
    evidence_summary["multi_year_predictability_verified_count"] = sum(
        1 for row in predictability_evidence if str(row.get("evidence_status") or "").upper() == "VERIFIED"
    )
    evidence_summary["unique_company_evidence_count"] = len(company_evidence)
    evidence_summary["unique_evidence_count"] = len(industry_evidence) + len(company_evidence)
    evidence_summary["continuity_requested_count"] = len(requested)

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
    (output_dir / "deep_review_profiles.json").write_text(
        json.dumps(closed_profiles, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "deep_calculation_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence_packet = {
        "contract": CONTRACT,
        "as_of": as_of.isoformat(),
        "requested_codes": requested,
        "industry_evidence": industry_evidence,
        "company_evidence": company_evidence,
        "audit": audit_rows,
        "summary": evidence_summary,
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    (output_dir / "gap_closure_evidence.json").write_text(
        json.dumps(evidence_packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "deep_calculation.md").write_text(
        "# GenGe Deep Calculation Gap Closure\n\n"
        f"- execution: **SUCCESS**\n- terminal state: **{status['research_terminal_state']}**\n"
        f"- requested: **{status['requested_count']}**\n- complete: **{status['complete_requested_count']}**\n"
        f"- evidence exhausted: **{status['evidence_exhausted_requested_count']}**\n"
        f"- evidence collection attempts: **{status['gap_closure_attempt_count']}**\n"
        f"- new evidence rows: **{status['new_evidence_count']}**\n"
        f"- progressed gates: **{status['progressed_gate_count']}**\n"
        f"- predictability resolved gates: **{status['predictability_resolved_gate_count']}**\n"
        f"- material-event failed gates: **{status['material_event_failed_gate_count']}**\n"
        f"- material-event PASS overrides: **{status['material_event_pass_override_count']}**\n"
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
