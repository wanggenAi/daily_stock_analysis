"""Evidence-gated competitive-change collector for GenGe research.

The collector never guesses peers from industry labels. It only consumes explicit,
reviewed peer mappings and already-persisted peer Evidence Events. Competitive
signals are research-only and cannot change Formal actions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .evidence_event_store import append_events, recent_for_code


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def collect(
    *,
    peer_map: Mapping[str, Any],
    evidence_root: Path,
    now: datetime | None = None,
    lookback_hours: int = 168,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    mappings = [m for m in (peer_map.get("mappings") or []) if isinstance(m, Mapping)]
    cutoff = now - timedelta(hours=max(1, int(lookback_hours)))
    events: list[dict[str, Any]] = []
    mapped_targets: set[str] = set()
    mapped_peers: set[str] = set()

    for mapping in mappings:
        target = str(mapping.get("target_code") or "").zfill(6)
        peer = str(mapping.get("peer_code") or "").zfill(6)
        evidence_ref = str(mapping.get("evidence_ref") or "").strip()
        if not (target.isdigit() and len(target) == 6 and peer.isdigit() and len(peer) == 6 and evidence_ref):
            continue
        mapped_targets.add(target)
        mapped_peers.add(peer)
        for peer_event in recent_for_code(evidence_root, peer, limit=50):
            published = _parse_ts(peer_event.get("published_at"))
            if published is None or published < cutoff:
                continue
            events.append({
                "code": target,
                "name": str(mapping.get("target_name") or ""),
                "observed_at": now.isoformat(),
                "published_at": peer_event.get("published_at"),
                "source": "competition_peer_event_bridge",
                "source_ref": f"{evidence_ref}|peer_event={peer_event.get('evidence_id','')}",
                "evidence_type": "COMPETITIVE_CHANGE",
                "title": f"Peer evidence: {mapping.get('peer_name') or peer} — {peer_event.get('title') or ''}",
                "summary": str(peer_event.get("summary") or ""),
                "materiality": "MEDIUM" if str(peer_event.get("materiality") or "").upper() in {"HIGH", "MEDIUM"} else "LOW",
                "direction": "UNKNOWN",
                "thesis_link": "COMPETITIVE_CONTEXT_REQUIRES_HUMAN_INTERPRETATION",
                "confidence": "MAPPED_PEER_SOURCE",
            })

    status = (
        "CONNECTED_NO_EVIDENCE_BACKED_PEER_MAPPINGS"
        if not mappings
        else ("CONNECTED_NO_RECENT_PEER_EVENTS" if not events else "CONNECTED_WITH_PEER_EVENTS")
    )
    summary = {
        "generated_at": now.isoformat(),
        "status": status,
        "mapping_count": len(mappings),
        "mapped_target_count": len(mapped_targets),
        "mapped_peer_count": len(mapped_peers),
        "event_candidate_count": len(events),
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }
    return events, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peer-map", type=Path, default=Path("config/competition_peer_map.json"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/competition_collector_status.json"))
    parser.add_argument("--lookback-hours", type=int, default=168)
    args = parser.parse_args(argv)
    events, status = collect(
        peer_map=_load(args.peer_map), evidence_root=args.evidence_root, lookback_hours=args.lookback_hours
    )
    result = append_events(args.evidence_root, events) if events else {"accepted": 0, "duplicates": 0}
    status.update(result)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
