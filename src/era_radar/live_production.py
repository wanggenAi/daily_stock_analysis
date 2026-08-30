"""Fail-closed live production orchestration for Era Radar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .collectors import Collector, normalize_observation
from .evidence import EvidenceRecord
from .live_world_bank import iso_now
from .persistence import persist_snapshot
from .pipeline import build_snapshot


@dataclass(frozen=True)
class CollectorHealth:
    collector: str
    status: str
    observations: int
    error: str | None = None


@dataclass(frozen=True)
class LiveCollectionResult:
    records: tuple[EvidenceRecord, ...]
    health: tuple[CollectorHealth, ...]
    research_as_of: str

    @property
    def successful_collectors(self) -> int:
        return sum(item.status == "SUCCESS" for item in self.health)

    @property
    def failed_collectors(self) -> int:
        return sum(item.status == "FAILED" for item in self.health)


def collect_live(collectors: Iterable[Collector]) -> LiveCollectionResult:
    records: list[EvidenceRecord] = []
    health: list[CollectorHealth] = []
    provisional = iso_now()
    for collector in collectors:
        name = collector.__class__.__name__
        count = 0
        try:
            for observation in collector.collect(provisional):
                normalized = normalize_observation(observation)
                records.extend(normalized)
                count += len(normalized)
        except Exception as exc:
            health.append(CollectorHealth(name, "FAILED", count, f"{type(exc).__name__}: {exc}"))
        else:
            health.append(CollectorHealth(name, "SUCCESS", count))
    return LiveCollectionResult(tuple(records), tuple(health), iso_now())


def _no_publish(status: str, collection: LiveCollectionResult) -> dict:
    return {
        "status": status,
        "research_as_of": collection.research_as_of,
        "health": [asdict(item) for item in collection.health],
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }


def _semantic_rows(records: Iterable[EvidenceRecord]) -> list[dict]:
    rows = []
    for item in records:
        row = asdict(item)
        row.pop("retrieved_at", None)
        rows.append(row)
    rows.sort(key=lambda row: row["evidence_id"])
    return rows


def semantic_fingerprint(records: Iterable[EvidenceRecord]) -> str:
    payload = json.dumps(_semantic_rows(records), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_latest_fingerprint(output_dir: str | Path) -> str | None:
    root = Path(output_dir)
    latest = root / "latest.json"
    if not latest.exists():
        return None
    latest_payload = json.loads(latest.read_text(encoding="utf-8"))
    snapshot_id = latest_payload.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("invalid Era Radar latest snapshot")
    evidence_path = root / "evidence" / f"{snapshot_id}.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError("invalid Era Radar evidence bundle")
    return semantic_fingerprint(EvidenceRecord(**row) for row in rows)


def run_live_production(collectors: Iterable[Collector], *, output_dir: str | Path) -> dict:
    configured = tuple(collectors)
    if not configured:
        raise ValueError("live Era Radar requires at least one configured collector")

    collection = collect_live(configured)
    if collection.failed_collectors:
        return _no_publish("NO_PUBLISH_PARTIAL_COLLECTION", collection)
    if collection.successful_collectors != len(configured):
        return _no_publish("NO_PUBLISH_COLLECTION_INCOMPLETE", collection)
    if not collection.records:
        return _no_publish("NO_PUBLISH_NO_EVIDENCE", collection)

    fresh = list(collection.records)
    previous_fingerprint = _load_latest_fingerprint(output_dir)
    current_fingerprint = semantic_fingerprint(fresh)
    if previous_fingerprint == current_fingerprint:
        result = _no_publish("NO_CHANGE", collection)
        result["evidence_fingerprint"] = current_fingerprint
        return result

    snapshot = build_snapshot(fresh, collection.research_as_of)
    persisted = persist_snapshot(snapshot, output_dir, evidence_records=fresh)
    return {
        **persisted,
        "research_as_of": collection.research_as_of,
        "health": [asdict(item) for item in collection.health],
        "evidence_count": len(fresh),
        "evidence_fingerprint": current_fingerprint,
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }
