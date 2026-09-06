"""Build reviewed research mappings and explicit coverage gaps.

The mapping layer is research metadata only. It merges current manually confirmed
holdings with ACTIVE candidate lifecycle names, projects reviewed industry profiles
into a CSV consumed by evidence collectors, and reports applicability-aware
commodity/peer coverage. Missing or partial applicable mappings remain visible
gaps; mappings are never guessed and never alter Formal actions.

A production All-A scan may supply an explicit company->industry classification as
an additional research-only metadata source. Reviewed static profiles always win.
Conflicting production classifications fail closed, and production industry
metadata is never used to infer commodity exposure or peer relationships.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


UNRESOLVED_INDUSTRIES = {"", "UNRESOLVED", "UNKNOWN", "UNCLASSIFIED", "N/A", "NA", "NONE"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _holding_codes(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*(\d{6})\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def _active_candidates(path: Path) -> dict[str, str]:
    payload = _load_json(path)
    result: dict[str, str] = {}
    for code, raw in (payload.get("candidates") or {}).items():
        if not isinstance(raw, Mapping) or str(raw.get("lifecycle_state") or "").upper() != "ACTIVE":
            continue
        normalized = _normalize_code(raw.get("code") or code)
        if normalized:
            result[normalized] = str(raw.get("stock_name") or "")
    return result


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    if match:
        return match.group(1)
    digits = re.sub(r"\D", "", text)
    return digits.zfill(6) if 0 < len(digits) <= 6 else ""


def _normalize_industry(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.upper() in UNRESOLVED_INDUSTRIES else text


def _load_explicit_industry_source(path: Path | None) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Load explicit industry metadata while failing closed on conflicts.

    Multiple identical rows are harmless. If a code carries more than one distinct
    resolved industry in the same source, the code is removed from the source map
    and reported as a conflict instead of arbitrarily picking a classification.
    """
    if path is None or not path.is_file():
        return {}, []
    industries_by_code: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for raw in csv.DictReader(stream):
            code = _normalize_code(raw.get("code") or raw.get("stock_code") or raw.get("symbol") or raw.get("ts_code"))
            industry = _normalize_industry(raw.get("industry") or raw.get("normalized_industry") or raw.get("raw_industry"))
            if not code or not industry:
                continue
            industries_by_code.setdefault(code, set()).add(industry)
            candidate_name = str(raw.get("stock_name") or raw.get("name") or "").strip()
            if candidate_name:
                names.setdefault(code, candidate_name)
    conflicts = sorted(code for code, values in industries_by_code.items() if len(values) > 1)
    resolved = {
        code: {"industry": next(iter(values)), "name": names.get(code, "")}
        for code, values in industries_by_code.items()
        if len(values) == 1
    }
    return resolved, conflicts


def _monitoring_state(profile: Mapping[str, Any], key: str, *, mapped: bool) -> str:
    declared = str(profile.get(key) or "UNRESOLVED").strip().upper()
    if declared == "NOT_APPLICABLE":
        return "NOT_APPLICABLE"
    if declared == "PARTIAL_MAPPED" and mapped:
        return "PARTIAL_MAPPED"
    if mapped:
        return "MAPPED"
    if declared in {"APPLICABLE", "APPLICABLE_UNMAPPED", "MAPPED", "PARTIAL_MAPPED"}:
        return "APPLICABLE_UNMAPPED"
    return "UNRESOLVED"


def build(
    *,
    holdings_path: Path,
    lifecycle_path: Path,
    profiles_path: Path,
    commodity_path: Path,
    peer_path: Path,
    industry_source_path: Path | None = None,
    industry_source_label: str = "production_all_a_scan",
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    holdings = _holding_codes(holdings_path)
    candidates = _active_candidates(lifecycle_path)
    universe = dict(candidates)
    universe.update(holdings)
    profiles = (_load_json(profiles_path).get("profiles") or {})
    commodity = (_load_json(commodity_path).get("security_exposures") or {})
    peer_mappings = [m for m in (_load_json(peer_path).get("mappings") or []) if isinstance(m, Mapping)]
    peer_targets = {_normalize_code(m.get("target_code")) for m in peer_mappings}
    peer_targets.discard("")
    industry_source, industry_source_conflicts = _load_explicit_industry_source(industry_source_path)

    rows: list[dict[str, str]] = []
    securities: list[dict[str, Any]] = []
    for code, name in sorted(universe.items()):
        profile = profiles.get(code) if isinstance(profiles.get(code), Mapping) else {}
        profile_industry = _normalize_industry(profile.get("industry"))
        production_mapping = industry_source.get(code) or {}
        production_industry = _normalize_industry(production_mapping.get("industry"))

        if profile_industry:
            industry = profile_industry
            industry_origin = "REVIEWED_STATIC_PROFILE"
            industry_source_ref = "config/research_security_profiles.json"
            industry_confidence = "HIGH" if str(profile.get("profile_status") or "").upper() == "REVIEWED" else "MEDIUM"
            evidence_value = str(profile.get("profile_status") or "REVIEWED")
            source_type = "reviewed_research_mapping"
            mapped_name = str(profile.get("name") or name)
        elif production_industry:
            industry = production_industry
            industry_origin = "PRODUCTION_ALL_A_EXPLICIT_METADATA"
            industry_source_ref = industry_source_label
            industry_confidence = "MEDIUM"
            evidence_value = "EXPLICIT_PRODUCTION_SCAN_METADATA"
            source_type = "production_scan_industry_metadata"
            mapped_name = str(production_mapping.get("name") or name)
        else:
            industry = ""
            industry_origin = "UNRESOLVED"
            industry_source_ref = ""
            industry_confidence = ""
            evidence_value = ""
            source_type = ""
            mapped_name = str(profile.get("name") or name)

        industry_resolved = bool(industry)
        commodity_mapped = bool(commodity.get(code))
        peer_mapped = code in peer_targets
        commodity_state = _monitoring_state(profile, "commodity_monitoring", mapped=commodity_mapped)
        peer_state = _monitoring_state(profile, "peer_monitoring", mapped=peer_mapped)
        scopes = []
        if code in holdings:
            scopes.append("HOLDING")
        if code in candidates:
            scopes.append("ACTIVE_CANDIDATE")
        if industry_resolved:
            rows.append({
                "date": datetime.now(timezone.utc).date().isoformat(),
                "code": code,
                "stock_name": mapped_name,
                "industry": industry,
                "evidence_name": "explicit research industry mapping",
                "evidence_value": evidence_value,
                "evidence_direction": "NEUTRAL",
                "source": industry_source_ref,
                "source_type": source_type,
                "confidence": industry_confidence,
                "note": "Research mapping only; cannot create Formal actions or infer commodity/peer mappings.",
            })
        securities.append({
            "code": code,
            "name": name,
            "scopes": scopes,
            "profile_status": profile.get("profile_status") or "MISSING",
            "industry": industry or None,
            "industry_mapped": industry_resolved,
            "industry_mapping_origin": industry_origin,
            "industry_mapping_source": industry_source_ref or None,
            "industry_mapping_confidence": industry_confidence or None,
            "industry_source_conflict": code in industry_source_conflicts,
            "commodity_monitoring_state": commodity_state,
            "commodity_mapped": commodity_state in {"MAPPED", "PARTIAL_MAPPED"},
            "commodity_fully_mapped": commodity_state == "MAPPED",
            "peer_monitoring_state": peer_state,
            "peer_mapped": peer_state == "MAPPED",
        })

    total = len(securities)
    commodity_applicable = [x for x in securities if x["commodity_monitoring_state"] in {"MAPPED", "PARTIAL_MAPPED", "APPLICABLE_UNMAPPED"}]
    peer_applicable = [x for x in securities if x["peer_monitoring_state"] in {"MAPPED", "APPLICABLE_UNMAPPED"}]
    origin_counts = Counter(str(x["industry_mapping_origin"]) for x in securities)
    summary = {
        "contract_version": "GEN_GE_RESEARCH_MAPPING_COVERAGE_V4_PRODUCTION_INDUSTRY_METADATA",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracked_security_count": total,
        "holding_count": len(holdings),
        "active_candidate_count": len(candidates),
        "industry_mapped_count": sum(x["industry_mapped"] for x in securities),
        "industry_unmapped_codes": [x["code"] for x in securities if not x["industry_mapped"]],
        "industry_mapping_origin_counts": dict(sorted(origin_counts.items())),
        "industry_source_input_available": industry_source_path is not None and industry_source_path.is_file(),
        "industry_source_resolved_security_count": len(industry_source),
        "industry_source_conflict_codes": industry_source_conflicts,
        "industry_source_policy": "REVIEWED_STATIC_PROFILE_FIRST_THEN_EXPLICIT_PRODUCTION_METADATA_CONFLICT_FAILS_CLOSED",
        "industry_source_is_research_metadata_only": True,
        "industry_source_may_infer_commodity_or_peers": False,
        "commodity_applicable_count": len(commodity_applicable),
        "commodity_mapped_count": sum(x["commodity_monitoring_state"] == "MAPPED" for x in commodity_applicable),
        "commodity_partial_mapped_count": sum(x["commodity_monitoring_state"] == "PARTIAL_MAPPED" for x in commodity_applicable),
        "commodity_connected_count": sum(x["commodity_monitoring_state"] in {"MAPPED", "PARTIAL_MAPPED"} for x in commodity_applicable),
        "commodity_not_applicable_count": sum(x["commodity_monitoring_state"] == "NOT_APPLICABLE" for x in securities),
        "commodity_unresolved_count": sum(x["commodity_monitoring_state"] == "UNRESOLVED" for x in securities),
        "commodity_unmapped_codes": [x["code"] for x in commodity_applicable if x["commodity_monitoring_state"] == "APPLICABLE_UNMAPPED"],
        "commodity_partial_mapped_codes": [x["code"] for x in commodity_applicable if x["commodity_monitoring_state"] == "PARTIAL_MAPPED"],
        "peer_applicable_count": len(peer_applicable),
        "peer_mapped_count": sum(x["peer_monitoring_state"] == "MAPPED" for x in peer_applicable),
        "peer_unresolved_count": sum(x["peer_monitoring_state"] == "UNRESOLVED" for x in securities),
        "peer_unmapped_codes": [x["code"] for x in peer_applicable if x["peer_monitoring_state"] == "APPLICABLE_UNMAPPED"],
        "securities": securities,
        "mapping_policy": "MISSING_APPLICABLE_MAPPING_IS_A_VISIBLE_RESEARCH_GAP_NOT_A_GUESS",
        "partial_mapping_policy": "PARTIAL_MAPPED_IS_CONNECTED_BUT_REMAINS_A_VISIBLE_RESEARCH_GAP",
        "applicability_policy": "NOT_APPLICABLE_IS_NOT_A_COVERAGE_GAP",
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "changes_thresholds": False,
        "no_auto_trade": True,
    }
    return summary, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdings", type=Path, default=Path("CURRENT_HOLDINGS.md"))
    parser.add_argument("--lifecycle", type=Path, default=Path("data/opportunity_snapshots/candidate_lifecycle_state.json"))
    parser.add_argument("--profiles", type=Path, default=Path("config/research_security_profiles.json"))
    parser.add_argument("--commodity", type=Path, default=Path("config/commodity_research_benchmarks.json"))
    parser.add_argument("--peers", type=Path, default=Path("config/competition_peer_map.json"))
    parser.add_argument("--industry-source-csv", type=Path)
    parser.add_argument("--industry-source-label", default="production_all_a_scan")
    parser.add_argument("--coverage-output", type=Path, default=Path("data/research_mapping/coverage.json"))
    parser.add_argument("--industry-csv-output", type=Path, default=Path("data/research_mapping/company_industry_map.csv"))
    args = parser.parse_args(argv)
    payload, rows = build(
        holdings_path=args.holdings,
        lifecycle_path=args.lifecycle,
        profiles_path=args.profiles,
        commodity_path=args.commodity,
        peer_path=args.peers,
        industry_source_path=args.industry_source_csv,
        industry_source_label=args.industry_source_label,
    )
    args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.industry_csv_output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["date", "code", "stock_name", "industry", "evidence_name", "evidence_value", "evidence_direction", "source", "source_type", "confidence", "note"]
    with args.industry_csv_output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
