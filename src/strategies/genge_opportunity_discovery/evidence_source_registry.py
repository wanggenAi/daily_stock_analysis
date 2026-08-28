"""Build evidence-source coverage metadata for GenGe research observability.

Coverage metadata distinguishes 'no evidence observed' from 'source unavailable'.
It is research infrastructure only and has no authority over Formal actions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_event_store import load_events


def _load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _registered_status(payload: dict[str, Any], *, fallback: str = "UNKNOWN") -> tuple[str, Any]:
    return (
        str(payload.get("freshness_status") or payload.get("status") or payload.get("collector_status") or fallback),
        payload.get("generated_at") or payload.get("observed_at"),
    )


def build(
    root: Path,
    *,
    collector_status: Path | None = None,
    industry_status: Path | None = None,
    commodity_status: Path | None = None,
) -> dict[str, Any]:
    events = load_events(root)
    by_source: dict[str, dict[str, Any]] = {}
    for event in events:
        source = str(event.get("source") or "UNKNOWN")
        item = by_source.setdefault(source, {"event_count": 0, "security_codes": set(), "latest_published_at": ""})
        item["event_count"] += 1
        code = str(event.get("code") or "")
        if code:
            item["security_codes"].add(code)
        published = str(event.get("published_at") or event.get("observed_at") or "")
        if published > item["latest_published_at"]:
            item["latest_published_at"] = published

    sources = {}
    for source, item in sorted(by_source.items()):
        sources[source] = {
            "event_count": item["event_count"],
            "security_count": len(item["security_codes"]),
            "latest_published_at": item["latest_published_at"],
        }

    company = _load(collector_status)
    industry = _load(industry_status)
    commodity = _load(commodity_status)
    company_state, company_at = _registered_status(company)
    industry_state, industry_at = _registered_status(industry, fallback="NOT_RUN")
    commodity_state, commodity_at = _registered_status(commodity, fallback="NOT_RUN")

    registered = {
        "COMPANY_ANNOUNCEMENTS": {
            "implemented": True,
            "collector": "hourly_evidence_collector",
            "last_status": company_state,
            "last_generated_at": company_at,
        },
        "INDUSTRY_SUPPLY_DEMAND": {
            "implemented": True,
            "collector": "industry_cycle_evidence_bridge",
            "last_status": industry_state,
            "last_generated_at": industry_at,
            "latest_source_date": industry.get("latest_source_date"),
            "mapped_security_count": industry.get("mapped_security_count"),
            "freshness_is_explicit": True,
        },
        "COMMODITY_PRICES": {
            "implemented": True,
            "collector": "commodity_price_evidence_collector",
            "last_status": commodity_state,
            "last_generated_at": commodity_at,
            "latest_market_date": commodity.get("latest_market_date"),
            "mapping_status": commodity.get("mapping_status"),
            "mapped_workset_security_count": commodity.get("mapped_workset_security_count"),
        },
        "COMPETITIVE_CHANGE": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
        "REGULATORY_POLICY": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
    }
    return {
        "contract_version": "GEN_GE_EVIDENCE_SOURCE_REGISTRY_V2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registered_sources": registered,
        "observed_sources": sources,
        "event_count": len(events),
        "implemented_source_count": sum(bool(v.get("implemented")) for v in registered.values()),
        "planned_source_count": sum(not bool(v.get("implemented")) for v in registered.values()),
        "coverage_semantics": "CONNECTED_DOES_NOT_IMPLY_FRESH_OR_MAPPED",
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--collector-status", type=Path, default=Path("data/evidence_events/collector_status.json"))
    parser.add_argument("--industry-status", type=Path, default=Path("data/evidence_events/industry_collector_status.json"))
    parser.add_argument("--commodity-status", type=Path, default=Path("data/evidence_events/commodity_collector_status.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evidence_events/source_registry.json"))
    args = parser.parse_args(argv)
    payload = build(
        args.evidence_root,
        collector_status=args.collector_status,
        industry_status=args.industry_status,
        commodity_status=args.commodity_status,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
