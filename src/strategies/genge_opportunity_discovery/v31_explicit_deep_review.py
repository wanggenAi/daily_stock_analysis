"""Apply evidence-backed explicit V3.1 hard-gate reviews, fail closed.

The frozen V3.1 contract deliberately refuses to infer judgement-heavy gates from
legacy scores. This executor fills the missing production stage between the deep
review queue and the production shortlist. It only accepts:

* an already-explicit upstream PASS/FAIL; or
* a repository-reviewed profile with HTTPS evidence, HIGH confidence, and any
  declared machine checks satisfied by the same-run PIT valuation row.

A requested PASS whose evidence or machine checks cannot be verified remains
UNKNOWN. The module never creates Formal BUY authority and never auto-trades.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .selection_framework_v31 import HARD_GATE_FIELDS, assess_v31

CONTRACT = "GEN_GE_V31_EXPLICIT_DEEP_REVIEW_V1"
ALLOWED_SOURCE_TYPES = frozenset({"PRIMARY_COMPANY", "INTERNATIONAL_AUTHORITY", "OFFICIAL_REGULATOR"})
EXPLICIT_STATUSES = frozenset({"PASS", "FAIL"})
ALLOWED_MACHINE_CHECKS = frozenset(
    {
        "financial_review_status",
        "minimum_cash_conversion_ratio",
        "minimum_earnings_quality_score",
        "required_earnings_quality_confidence",
        "normalized_core_operating_profit_positive",
        "operating_cash_flow_positive",
        "disclosure_not_after_research_as_of",
    }
)


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


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y", "pass", "ok"}:
        return True
    if text in {"0", "false", "no", "n", "fail"}:
        return False
    return None


def _parse_date(value: Any) -> date | None:
    text = _text(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _latest_valuation_csv(root: Path) -> Path:
    candidates = sorted(root.glob("*/valuation_research_queue.csv"))
    if not candidates:
        direct = root / "valuation_research_queue.csv"
        if direct.exists():
            return direct
        raise FileNotFoundError(f"valuation research queue not found under {root}")
    return candidates[-1]


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract") != CONTRACT:
        raise ValueError(f"unexpected deep-review contract: {payload.get('contract')}")
    if payload.get("authority") != "RESEARCH_ONLY":
        raise ValueError("explicit deep reviews must remain RESEARCH_ONLY")
    if payload.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("automatic_formal_buy_allowed must be false")
    if payload.get("unknown_is_pass") is not False:
        raise ValueError("unknown_is_pass must be false")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be an object")
    return payload


def _validate_evidence(review: Mapping[str, Any], *, research_as_of: date | None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    evidence = review.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False, ["evidence_missing"]
    for item in evidence:
        if not isinstance(item, Mapping):
            errors.append("evidence_item_invalid")
            continue
        url = _text(item.get("url"))
        if not url.startswith("https://"):
            errors.append("evidence_url_not_https")
        if _text(item.get("source_type")) not in ALLOWED_SOURCE_TYPES:
            errors.append("evidence_source_type_not_allowed")
        published = _parse_date(item.get("published_date"))
        if research_as_of and published and published > research_as_of:
            errors.append("evidence_published_after_research_as_of")
    return not errors, errors


def _machine_checks(
    checks: Mapping[str, Any] | None,
    valuation: Mapping[str, Any],
    *,
    research_as_of: date | None,
) -> tuple[bool, list[str]]:
    if not checks:
        return True, []
    unknown = sorted(set(checks) - ALLOWED_MACHINE_CHECKS)
    if unknown:
        raise ValueError("unsupported machine checks: " + ",".join(unknown))

    failures: list[str] = []
    expected_review = _text(checks.get("financial_review_status"))
    if expected_review and _text(valuation.get("financial_review_status")).upper() != expected_review.upper():
        failures.append("financial_review_status")

    minimum_cash = _float(checks.get("minimum_cash_conversion_ratio"))
    actual_cash = _float(valuation.get("cash_conversion_ratio"))
    if minimum_cash is not None and (actual_cash is None or actual_cash < minimum_cash):
        failures.append("cash_conversion_ratio")

    minimum_quality = _float(checks.get("minimum_earnings_quality_score"))
    actual_quality = _float(valuation.get("earnings_quality_score"))
    if minimum_quality is not None and (actual_quality is None or actual_quality < minimum_quality):
        failures.append("earnings_quality_score")

    required_confidence = _text(checks.get("required_earnings_quality_confidence"))
    if required_confidence and _text(valuation.get("earnings_quality_confidence")).upper() != required_confidence.upper():
        failures.append("earnings_quality_confidence")

    if checks.get("normalized_core_operating_profit_positive") is True:
        value = _float(valuation.get("normalized_core_operating_profit"))
        if value is None or value <= 0.0:
            failures.append("normalized_core_operating_profit")

    if checks.get("operating_cash_flow_positive") is True:
        value = _float(valuation.get("operating_cash_flow"))
        if value is None or value <= 0.0:
            failures.append("operating_cash_flow")

    if checks.get("disclosure_not_after_research_as_of") is True:
        disclosure = _parse_date(valuation.get("financial_disclosure_date"))
        if research_as_of is None or disclosure is None or disclosure > research_as_of:
            failures.append("financial_disclosure_date")

    return not failures, failures


def _apply_gate_review(
    row: dict[str, Any],
    gate: str,
    review: Mapping[str, Any],
    valuation: Mapping[str, Any],
    *,
    research_as_of: date | None,
) -> tuple[str, str]:
    field = HARD_GATE_FIELDS[gate]
    existing = _text(row.get(field)).upper()
    if existing in EXPLICIT_STATUSES:
        return existing, "UPSTREAM_EXPLICIT"

    requested = _text(review.get("status")).upper()
    if requested not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ValueError(f"invalid explicit review status for {gate}: {requested}")
    confidence = _text(review.get("confidence")).upper()
    evidence_ok, evidence_errors = _validate_evidence(review, research_as_of=research_as_of)
    machine_ok, machine_failures = _machine_checks(
        review.get("machine_checks") if isinstance(review.get("machine_checks"), Mapping) else None,
        valuation,
        research_as_of=research_as_of,
    )

    provenance = {
        "contract": CONTRACT,
        "requested_status": requested,
        "confidence": confidence,
        "rationale": _text(review.get("rationale")),
        "evidence": review.get("evidence") or [],
        "evidence_valid": evidence_ok,
        "evidence_errors": evidence_errors,
        "machine_checks_passed": machine_ok,
        "machine_check_failures": machine_failures,
    }
    row[f"v31_deep_review_{gate}_provenance"] = json.dumps(
        provenance, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )

    if requested == "UNKNOWN":
        row[field] = "UNKNOWN"
        return "UNKNOWN", "EXPLICIT_UNKNOWN"
    if confidence != "HIGH" or not evidence_ok or not machine_ok or not provenance["rationale"]:
        row[field] = "UNKNOWN"
        return "UNKNOWN", "REVIEW_NOT_VERIFIED"
    row[field] = requested
    return requested, "EXPLICIT_REVIEW_VERIFIED"


def apply_explicit_reviews(
    candidate_rows: list[dict[str, Any]],
    valuation_rows: list[dict[str, Any]],
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valuation_by_code = {_code(row.get("code")): row for row in valuation_rows if _code(row.get("code"))}
    profiles = config.get("profiles") if isinstance(config.get("profiles"), Mapping) else {}
    out: list[dict[str, Any]] = []
    applied_gate_counts = {gate: 0 for gate in HARD_GATE_FIELDS}
    verified_pass_counts = {gate: 0 for gate in HARD_GATE_FIELDS}

    for source in candidate_rows:
        row: dict[str, Any] = dict(source)
        code = _code(row.get("code") or row.get("stock_code") or row.get("symbol"))
        profile = profiles.get(code) if isinstance(profiles, Mapping) else None
        valuation = valuation_by_code.get(code, {})
        resolved: list[str] = []
        sources: list[str] = []

        if isinstance(profile, Mapping):
            profile_as_of = _parse_date(profile.get("research_as_of"))
            gates = profile.get("gates")
            if not isinstance(gates, Mapping):
                raise ValueError(f"profile {code} gates must be an object")
            for gate in HARD_GATE_FIELDS:
                review = gates.get(gate)
                if not isinstance(review, Mapping):
                    continue
                status, source_kind = _apply_gate_review(
                    row,
                    gate,
                    review,
                    valuation,
                    research_as_of=profile_as_of,
                )
                applied_gate_counts[gate] += 1
                if status == "PASS":
                    verified_pass_counts[gate] += 1
                if status in EXPLICIT_STATUSES:
                    resolved.append(gate)
                sources.append(f"{gate}:{source_kind}")

        row["v31_deep_review_contract"] = CONTRACT
        row["v31_deep_review_profile_applied"] = bool(isinstance(profile, Mapping))
        row["v31_deep_review_resolved_gates"] = ";".join(resolved)
        row["v31_deep_review_sources"] = ";".join(sources)
        row["v31_deep_review_formal_trading_authority"] = False
        row["v31_deep_review_no_auto_trade"] = True
        row["v31_deep_review_unknown_is_pass"] = False
        row.update(assess_v31(row).as_dict())
        out.append(row)

    summary = {
        "contract": CONTRACT,
        "input_count": len(candidate_rows),
        "output_count": len(out),
        "profile_count": len(profiles),
        "profile_applied_count": sum(1 for row in out if _bool(row.get("v31_deep_review_profile_applied")) is True),
        "applied_gate_counts": applied_gate_counts,
        "verified_pass_counts": verified_pass_counts,
        "hard_gate_passed_count": sum(1 for row in out if _bool(row.get("v31_hard_gates_passed")) is True),
        "buy_ready_count": sum(1 for row in out if _bool(row.get("v31_buy_ready")) is True),
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    return out, summary


def run(*, candidate_csv: Path, valuation_root: Path, config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = _load_config(config_path)
    candidate_rows = _read_csv(candidate_csv)
    valuation_csv = _latest_valuation_csv(valuation_root)
    valuation_rows = _read_csv(valuation_csv)
    reviewed, summary = apply_explicit_reviews(candidate_rows, valuation_rows, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "v31_review_queue_reviewed.csv", reviewed)
    (output_dir / "v31_explicit_deep_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/v31_explicit_deep_reviews.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = run(
        candidate_csv=args.candidate_csv,
        valuation_root=args.valuation_root,
        config_path=args.config,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
