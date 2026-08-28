"""Build reviewed research mappings and explicit coverage gaps.

The mapping layer is research metadata only. It merges current manually confirmed
holdings with ACTIVE candidate lifecycle names, projects reviewed industry profiles
into a CSV consumed by evidence collectors, and reports commodity/peer coverage.
Missing mappings remain visible gaps; they are never guessed and never alter
Formal actions.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


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
        normalized = str(raw.get("code") or code).zfill(6)
        result[normalized] = str(raw.get("stock_name") or "")
    return result


def build(
    *,
    holdings_path: Path,
    lifecycle_path: Path,
    profiles_path: Path,
    commodity_path: Path,
    peer_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    holdings = _holding_codes(holdings_path)
    candidates = _active_candidates(lifecycle_path)
    universe = dict(candidates)
    universe.update(holdings)
    profiles = (_load_json(profiles_path).get("profiles") or {})
    commodity = (_load_json(commodity_path).get("security_exposures") or {})
    peer_mappings = [m for m in (_load_json(peer_path).get("mappings") or []) if isinstance(m, Mapping)]
    peer_targets = {str(m.get("target_code") or "").zfill(6) for m in peer_mappings}

    rows: list[dict[str, str]] = []
    securities: list[dict[str, Any]] = []
    for code, name in sorted(universe.items()):
        profile = profiles.get(code) if isinstance(profiles.get(code), Mapping) else {}
        industry = str(profile.get("industry") or "").strip()
        industry_resolved = bool(industry and industry.upper() not in {"UNRESOLVED", "UNKNOWN"})
        commodity_mapped = bool(commodity.get(code))
        peer_mapped = code in peer_targets
        scopes = []
        if code in holdings:
            scopes.append("HOLDING")
        if code in candidates:
            scopes.append("ACTIVE_CANDIDATE")
        if industry_resolved:
            rows.append({
                "date": datetime.now(timezone.utc).date().isoformat(),
                "code": code,
                "stock_name": str(profile.get("name") or name),
                "industry": industry,
                "evidence_name": "reviewed research profile industry mapping",
                "evidence_value": str(profile.get("profile_status") or "REVIEWED"),
                "evidence_direction": "NEUTRAL",
                "source": "config/research_security_profiles.json",
                "source_type": "reviewed_research_mapping",
                "confidence": "HIGH" if str(profile.get("profile_status")) == "REVIEWED" else "MEDIUM",
                "note": "Research mapping only; cannot create Formal actions."
            })
        securities.append({
            "code": code,
            "name": name,
            "scopes": scopes,
            "profile_status": profile.get("profile_status") or "MISSING",
            "industry": industry or None,
            "industry_mapped": industry_resolved,
            "commodity_mapped": commodity_mapped,
            "peer_mapped": peer_mapped,
        })

    total = len(securities)
    summary = {
        "contract_version": "GEN_GE_RESEARCH_MAPPING_COVERAGE_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracked_security_count": total,
        "holding_count": len(holdings),
        "active_candidate_count": len(candidates),
        "industry_mapped_count": sum(x["industry_mapped"] for x in securities),
        "commodity_mapped_count": sum(x["commodity_mapped"] for x in securities),
        "peer_mapped_count": sum(x["peer_mapped"] for x in securities),
        "industry_unmapped_codes": [x["code"] for x in securities if not x["industry_mapped"]],
        "commodity_unmapped_codes": [x["code"] for x in securities if not x["commodity_mapped"]],
        "peer_unmapped_codes": [x["code"] for x in securities if not x["peer_mapped"]],
        "securities": securities,
        "mapping_policy": "MISSING_MAPPING_IS_A_VISIBLE_RESEARCH_GAP_NOT_A_GUESS",
        "formal_action_eligible": False,
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
    parser.add_argument("--coverage-output", type=Path, default=Path("data/research_mapping/coverage.json"))
    parser.add_argument("--industry-csv-output", type=Path, default=Path("data/research_mapping/company_industry_map.csv"))
    args = parser.parse_args(argv)
    payload, rows = build(
        holdings_path=args.holdings,
        lifecycle_path=args.lifecycle,
        profiles_path=args.profiles,
        commodity_path=args.commodity,
        peer_path=args.peers,
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
