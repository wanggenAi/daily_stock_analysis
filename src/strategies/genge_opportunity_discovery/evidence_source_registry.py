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


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def build(root: Path, *, collector_status: Path | None = None) -> dict[str, Any]:
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

    collector = _load(collector_status) if collector_status else {}
    registered = {
        "COMPANY_ANNOUNCEMENTS": {
            "implemented": True,
            "collector": "hourly_evidence_collector",
            "last_status": collector.get("status") or collector.get("collector_status") or "UNKNOWN",
            "last_generated_at": collector.get("generated_at") or collector.get("observed_at"),
        },
        "INDUSTRY_SUPPLY_DEMAND": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
        "COMMODITY_PRICES": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
        "COMPETITIVE_CHANGE": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
        "REGULATORY_POLICY": {"implemented": False, "collector": None, "last_status": "NOT_CONNECTED"},
    }
    return {
        "contract_version": "GEN_GE_EVIDENCE_SOURCE_REGISTRY_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registered_sources": registered,
        "observed_sources": sources,
        "event_count": len(events),
        "implemented_source_count": sum(bool(v.get("implemented")) for v in registered.values()),
        "planned_source_count": sum(not bool(v.get("implemented")) for v in registered.values()),
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--collector-status", type=Path, default=Path("data/evidence_events/collector_status.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evidence_events/source_registry.json"))
    args = parser.parse_args(argv)
    payload = build(args.evidence_root, collector_status=args.collector_status)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
