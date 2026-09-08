"""Automatic, fail-closed V3.1 deep calculation worker.

This module standardizes the executable part of a deep review so that GitHub
Actions can run it immediately whenever a holding/candidate requires deeper
research. It deliberately separates *automation of work* from *automatic
promotion*:

* machine-verifiable financial-safety / earnings-authenticity gates are resolved
  only from same-run PIT valuation evidence and conservative thresholds;
* existing explicit evidence-backed profiles are applied through the frozen
  explicit-review verifier;
* judgement-heavy gates that still lack verified evidence remain UNKNOWN;
* UNKNOWN is never treated as PASS and this worker never creates Formal BUY or
  trading authority.

The outputs are designed for both production consumption and observability:
reviewed CSV, profile JSON for the decision center, a machine-readable execution
status, and a human-readable Markdown summary.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .selection_framework_v31 import HARD_GATE_FIELDS, assess_v31
from .v31_explicit_deep_review import CONTRACT as EXPLICIT_CONTRACT
from .v31_explicit_deep_review import apply_explicit_reviews

CONTRACT = "GEN_GE_V31_AUTOMATIC_DEEP_CALC_V1"
MACHINE_PASS_CASH_CONVERSION = 0.80
MACHINE_PASS_EARNINGS_QUALITY = 70.0
MACHINE_FAIL_REVIEW_STATUSES = frozenset({"FAIL", "FAILED", "REJECT", "REJECTED", "INVALID"})


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)


def _latest_valuation_csv(root: Path) -> Path:
    direct = root / "valuation_research_queue.csv"
    if direct.is_file():
        return direct
    candidates = sorted(root.glob("**/valuation_research_queue.csv"), key=str)
    if not candidates:
        raise FileNotFoundError(f"valuation_research_queue.csv not found under {root}")
    return candidates[-1]


def _load_explicit_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != EXPLICIT_CONTRACT:
        raise ValueError(f"unexpected explicit deep-review contract: {payload.get('contract')}")
    if payload.get("authority") != "RESEARCH_ONLY":
        raise ValueError("explicit deep-review authority must remain RESEARCH_ONLY")
    if payload.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("automatic_formal_buy_allowed must remain false")
    if payload.get("unknown_is_pass") is not False:
        raise ValueError("unknown_is_pass must remain false")
    if not isinstance(payload.get("profiles"), Mapping):
        raise ValueError("explicit deep-review profiles must be an object")
    return payload


def _existing_explicit(row: Mapping[str, Any], gate: str) -> str:
    value = _text(row.get(HARD_GATE_FIELDS[gate])).upper()
    return value if value in {"PASS", "FAIL"} else ""


def _machine_snapshot(valuation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "financial_review_status": _text(valuation.get("financial_review_status")).upper(),
        "cash_conversion_ratio": _float(valuation.get("cash_conversion_ratio")),
        "earnings_quality_score": _float(valuation.get("earnings_quality_score")),
        "earnings_quality_confidence": _text(valuation.get("earnings_quality_confidence")).upper(),
        "normalized_core_operating_profit": _float(valuation.get("normalized_core_operating_profit")),
        "operating_cash_flow": _float(valuation.get("operating_cash_flow")),
        "financial_disclosure_date": _text(valuation.get("financial_disclosure_date")),
    }


def _strong_machine_financials(snapshot: Mapping[str, Any]) -> bool:
    return bool(
        snapshot.get("financial_review_status") == "OK"
        and snapshot.get("earnings_quality_confidence") == "HIGH"
        and snapshot.get("cash_conversion_ratio") is not None
        and float(snapshot["cash_conversion_ratio"]) >= MACHINE_PASS_CASH_CONVERSION
        and snapshot.get("earnings_quality_score") is not None
        and float(snapshot["earnings_quality_score"]) >= MACHINE_PASS_EARNINGS_QUALITY
        and snapshot.get("normalized_core_operating_profit") is not None
        and float(snapshot["normalized_core_operating_profit"]) > 0.0
        and snapshot.get("operating_cash_flow") is not None
        and float(snapshot["operating_cash_flow"]) > 0.0
    )


def _automatic_gate_decision(gate: str, valuation: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    snapshot = _machine_snapshot(valuation)
    strong = _strong_machine_financials(snapshot)
    review_status = str(snapshot.get("financial_review_status") or "")
    normalized = snapshot.get("normalized_core_operating_profit")
    operating_cash = snapshot.get("operating_cash_flow")
    confidence = str(snapshot.get("earnings_quality_confidence") or "")

    if gate == "financial_safety":
        if strong:
            return (
                "PASS",
                "Same-run PIT financial review is OK with HIGH earnings-quality confidence, positive normalized operating profit and operating cash flow, cash conversion >= 0.80, and earnings-quality score >= 70.",
                snapshot,
            )
        if review_status in MACHINE_FAIL_REVIEW_STATUSES:
            return "FAIL", f"Same-run PIT financial review status is {review_status}.", snapshot
        if confidence == "HIGH" and normalized is not None and operating_cash is not None and normalized <= 0 and operating_cash <= 0:
            return "FAIL", "Same-run high-confidence evidence shows both normalized operating profit and operating cash flow are non-positive.", snapshot
        return "UNKNOWN", "Same-run PIT evidence is insufficient for a verified financial-safety PASS or FAIL.", snapshot

    if gate == "earnings_authenticity":
        if strong:
            return (
                "PASS",
                "Same-run PIT evidence verifies positive normalized operating profit, positive operating cash flow, strong cash conversion and HIGH-confidence earnings quality.",
                snapshot,
            )
        if confidence == "HIGH" and normalized is not None and operating_cash is not None and normalized <= 0 and operating_cash <= 0:
            return "FAIL", "High-confidence same-run evidence does not support positive core earnings or cash realization.", snapshot
        return "UNKNOWN", "Same-run PIT evidence is insufficient for a verified earnings-authenticity PASS or FAIL.", snapshot

    return "UNKNOWN", "This qualitative gate requires verified evidence beyond deterministic same-run financial checks.", snapshot


def _apply_machine_reviews(rows: list[dict[str, Any]], valuation_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valuation_by_code = {_code(row.get("code")): row for row in valuation_rows if _code(row.get("code"))}
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        code = _code(row.get("code") or row.get("stock_code") or row.get("symbol"))
        valuation = valuation_by_code.get(code, {})
        for gate in HARD_GATE_FIELDS:
            if _existing_explicit(row, gate):
                continue
            status, rationale, snapshot = _automatic_gate_decision(gate, valuation)
            row[HARD_GATE_FIELDS[gate]] = status
            row[f"v31_auto_deep_review_{gate}_provenance"] = json.dumps(
                {
                    "contract": CONTRACT,
                    "source": "SAME_RUN_PIT_MACHINE" if gate in {"financial_safety", "earnings_authenticity"} else "QUALITATIVE_EVIDENCE_REQUIRED",
                    "status": status,
                    "rationale": rationale,
                    "machine_snapshot": snapshot,
                    "unknown_is_pass": False,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        row["v31_auto_deep_calculation_contract"] = CONTRACT
        row["v31_auto_deep_calculation_attempted"] = True
        row["v31_auto_deep_calculation_formal_trading_authority"] = False
        row["v31_auto_deep_calculation_unknown_is_pass"] = False
        row["v31_auto_deep_calculation_no_auto_trade"] = True
        row.update(assess_v31(row).as_dict())
        output.append(row)
    return output


def _prepare_profile_reverification(
    rows: list[dict[str, Any]], explicit_config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """Force profile-backed upstream PASS values through reviewed evidence again.

    A PASS already present in the candidate queue is not sufficient provenance for
    the runtime deep-review profile. If this repository contains an explicit gate
    review for that code, clear only the upstream PASS to UNKNOWN so the explicit
    verifier must re-establish it from HIGH-confidence evidence and any declared
    same-run machine checks. Existing FAIL values are intentionally preserved.
    """
    profiles = explicit_config.get("profiles") if isinstance(explicit_config.get("profiles"), Mapping) else {}
    output: list[dict[str, Any]] = []
    cleared = 0
    for source in rows:
        row = dict(source)
        code = _code(row.get("code") or row.get("stock_code") or row.get("symbol"))
        profile = profiles.get(code) if isinstance(profiles, Mapping) else None
        profile_gates = profile.get("gates") if isinstance(profile, Mapping) else None
        if isinstance(profile_gates, Mapping):
            for gate, field in HARD_GATE_FIELDS.items():
                if not isinstance(profile_gates.get(gate), Mapping):
                    continue
                if _text(row.get(field)).upper() == "PASS":
                    row[field] = "UNKNOWN"
                    cleared += 1
        output.append(row)
    return output, cleared


def _decode_provenance(row: Mapping[str, Any], gate: str) -> tuple[str, str, list[dict[str, Any]], str]:
    explicit_key = f"v31_deep_review_{gate}_provenance"
    automatic_key = f"v31_auto_deep_review_{gate}_provenance"
    for key, source in ((explicit_key, "EXPLICIT_VERIFIED"), (automatic_key, "AUTOMATIC_MACHINE")):
        raw = row.get(key)
        if not raw:
            continue
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            continue
        rationale = _text(payload.get("rationale"))
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
        if not evidence and source == "AUTOMATIC_MACHINE":
            evidence = [{"source_type": "SAME_RUN_PIT_MACHINE", "reference": "valuation_research_queue.csv"}]
        confidence = _text(payload.get("confidence")) or ("HIGH" if source == "EXPLICIT_VERIFIED" else "MACHINE")
        return rationale, confidence, evidence, source
    return "No verified evidence has resolved this gate yet.", "", [], "UNRESOLVED"


def _profiles(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for row in rows:
        code = _code(row.get("code"))
        if not code:
            continue
        gates: dict[str, Any] = {}
        for gate, field in HARD_GATE_FIELDS.items():
            status = _text(row.get(field)).upper()
            if status not in {"PASS", "FAIL"}:
                status = "UNKNOWN"
            rationale, confidence, evidence, source = _decode_provenance(row, gate)
            gates[gate] = {
                "status": status,
                "confidence": confidence,
                "rationale": rationale,
                "evidence": evidence,
                "source": source,
            }
        profiles[code] = {
            "name": row.get("stock_name") or row.get("name") or "",
            "industry": row.get("industry") or "",
            "gates": gates,
        }
    return {
        "contract": CONTRACT,
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "profiles": profiles,
    }


def calculate_rows(
    candidate_rows: list[dict[str, Any]],
    valuation_rows: list[dict[str, Any]],
    explicit_config: Mapping[str, Any],
    *,
    requested_codes: Iterable[str] | None = None,
    source_run_id: str = "",
    trigger_source: str = "UNKNOWN",
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    machine_reviewed = _apply_machine_reviews(candidate_rows, valuation_rows)
    machine_reviewed, reverified_upstream_pass_count = _prepare_profile_reverification(
        machine_reviewed, explicit_config
    )
    reviewed, explicit_summary = apply_explicit_reviews(machine_reviewed, valuation_rows, explicit_config)
    profile_payload = _profiles(reviewed)

    all_codes = {_code(row.get("code")) for row in reviewed if _code(row.get("code"))}
    requested = {_code(code) for code in (requested_codes or []) if _code(code)}
    if not requested:
        requested = set(all_codes)
    missing_requested = sorted(requested - all_codes)
    selected_profiles = [profile_payload["profiles"][code] for code in sorted(requested & all_codes)]
    unknown_count = sum(
        1
        for profile in selected_profiles
        for gate in profile["gates"].values()
        if gate.get("status") == "UNKNOWN"
    )
    complete_count = sum(
        1 for profile in selected_profiles if all(g.get("status") != "UNKNOWN" for g in profile["gates"].values())
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status = {
        "contract": CONTRACT,
        "execution_status": "SUCCESS",
        "research_outcome": "COMPLETE" if unknown_count == 0 and not missing_requested else "PARTIAL_GAPS_REMAIN",
        "generated_at": now,
        "source_run_id": str(source_run_id or ""),
        "trigger_source": str(trigger_source or "UNKNOWN"),
        "candidate_count": len(reviewed),
        "requested_count": len(requested),
        "processed_requested_count": len(requested & all_codes),
        "missing_requested_codes": missing_requested,
        "complete_requested_count": complete_count,
        "partial_requested_count": len(selected_profiles) - complete_count,
        "unresolved_requested_gate_count": unknown_count,
        "explicit_profile_applied_count": explicit_summary.get("profile_applied_count", 0),
        "reverified_upstream_pass_count": reverified_upstream_pass_count,
        "hard_gate_passed_count": sum(str(row.get("v31_hard_gates_passed")).lower() == "true" for row in reviewed),
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    profile_payload.update(
        {
            "generated_at": now,
            "source_run_id": str(source_run_id or ""),
            "trigger_source": str(trigger_source or "UNKNOWN"),
            "execution_status": "SUCCESS",
            "research_outcome": status["research_outcome"],
            "reverified_upstream_pass_count": reverified_upstream_pass_count,
        }
    )
    return reviewed, profile_payload, status


def _render_status(status: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# GenGe Automatic Deep Calculation",
            "",
            f"- execution: **{status.get('execution_status')}**",
            f"- research outcome: **{status.get('research_outcome')}**",
            f"- trigger: `{status.get('trigger_source')}`",
            f"- source run: `{status.get('source_run_id')}`",
            f"- requested: **{status.get('requested_count')}**",
            f"- complete: **{status.get('complete_requested_count')}**",
            f"- partial: **{status.get('partial_requested_count')}**",
            f"- unresolved hard gates: **{status.get('unresolved_requested_gate_count')}**",
            "- UNKNOWN != PASS; no automatic Formal BUY; no auto trade.",
            "",
        ]
    )


def run(
    *,
    candidate_csv: Path,
    valuation_root: Path,
    explicit_config_path: Path,
    output_dir: Path,
    requested_codes: Iterable[str] | None = None,
    source_run_id: str = "",
    trigger_source: str = "UNKNOWN",
) -> dict[str, Any]:
    config = _load_explicit_config(explicit_config_path)
    candidate_rows = _read_csv(candidate_csv)
    valuation_csv = _latest_valuation_csv(valuation_root)
    valuation_rows = _read_csv(valuation_csv)
    reviewed, profiles, status = calculate_rows(
        candidate_rows,
        valuation_rows,
        config,
        requested_codes=requested_codes,
        source_run_id=source_run_id,
        trigger_source=trigger_source,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v31_review_queue_deep_calculated.csv", reviewed)
    (output_dir / "deep_review_profiles.json").write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "deep_calculation_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "deep_calculation.md").write_text(_render_status(status), encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--explicit-config", type=Path, default=Path("config/v31_explicit_deep_reviews.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--requested-codes", default="")
    parser.add_argument("--source-run-id", default="")
    parser.add_argument("--trigger-source", default="UNKNOWN")
    args = parser.parse_args()
    requested = [part.strip() for part in args.requested_codes.replace(";", ",").split(",") if part.strip()]
    status = run(
        candidate_csv=args.candidate_csv,
        valuation_root=args.valuation_root,
        explicit_config_path=args.explicit_config,
        output_dir=args.output_dir,
        requested_codes=requested,
        source_run_id=args.source_run_id,
        trigger_source=args.trigger_source,
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())