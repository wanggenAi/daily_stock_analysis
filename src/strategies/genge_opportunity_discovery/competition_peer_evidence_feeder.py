"""Collect official peer material-event evidence for reviewed competition mappings.

Peers outside the hourly workset would otherwise have no Evidence Events for the
competition bridge to consume. This slow-lane feeder scans only explicitly mapped
peers via the repository's official material-event collector and converts verified
rows into the common Evidence Event Store. It is research-only.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .evidence_collectors.cache import EvidenceCache
from .evidence_collectors.company_announcements import collect_company_material_events
from .evidence_event_store import append_events


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def peer_rows(peer_map: Mapping[str, Any]) -> list[dict[str, str]]:
    peers: dict[str, str] = {}
    for mapping in peer_map.get("mappings") or []:
        if not isinstance(mapping, Mapping):
            continue
        code = str(mapping.get("peer_code") or "").zfill(6)
        name = str(mapping.get("peer_name") or "")
        evidence_ref = str(mapping.get("evidence_ref") or "")
        if code.isdigit() and len(code) == 6 and evidence_ref:
            peers[code] = name
    return [{"code": code, "stock_name": name, "industry": "", "normalized_industry": ""} for code, name in sorted(peers.items())]


def to_events(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    result: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("code") or "").zfill(6)
        title = str(row.get("title") or row.get("evidence_value") or "").strip()
        source = str(row.get("source") or row.get("original_url") or "").strip()
        if not (code and title and source):
            continue
        raw_direction = str(row.get("direction") or row.get("evidence_direction") or "").upper()
        direction = "WEAKENING" if raw_direction == "NEGATIVE" else "NEUTRAL"
        severity = str(row.get("event_severity") or "MEDIUM").upper()
        materiality = severity if severity in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM"
        publish = str(row.get("publish_date") or row.get("date") or "")
        result.append({
            "code": code,
            "name": str(row.get("stock_name") or ""),
            "observed_at": now,
            "published_at": publish + "T00:00:00+00:00" if len(publish) == 10 else now,
            "source": "peer_official_material_event",
            "source_ref": source,
            "evidence_type": "PEER_MATERIAL_EVENT",
            "title": title,
            "summary": str(row.get("normalized_summary") or row.get("raw_excerpt") or ""),
            "materiality": materiality,
            "direction": direction,
            "thesis_link": "PEER_SOURCE_EVENT_ONLY",
            "value_anchor_impact": "UNASSESSED",
            "sell_relevance": "RESEARCH_ONLY",
            "confidence": "HIGH" if str(row.get("evidence_status") or "").upper() == "VERIFIED" else "MEDIUM",
        })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-map", type=Path, default=Path("config/competition_peer_map.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/evidence_cache/competition_peers"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/competition_peer_feeder_status.json"))
    parser.add_argument("--max-peers", type=int, default=20)
    args = parser.parse_args(argv)
    targets = peer_rows(_load(args.peer_map))[: max(0, args.max_peers)]
    cache = EvidenceCache(args.cache_dir, ttl_days=1)
    evidence_rows, audit_rows, summary = collect_company_material_events(
        rows=targets,
        as_of=date.today(),
        cache=cache,
        limit=len(targets),
        timeout=12,
    ) if targets else ([], [], {})
    events = to_events(evidence_rows)
    append_result = append_events(args.evidence_root, events) if events else {"accepted": 0, "duplicates": 0}
    status = {
        "contract_version": "GEN_GE_COMPETITION_PEER_FEEDER_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "CONNECTED" if targets else "NO_EVIDENCE_BACKED_PEERS",
        "peer_target_count": len(targets),
        "verified_peer_event_rows": len(evidence_rows),
        "audit_count": len(audit_rows),
        **summary,
        **append_result,
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
