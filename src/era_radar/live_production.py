"""Fail-closed live production orchestration for Era Radar.

A configured live source set is an atomic evidence acquisition unit: if any collector fails,
no new durable truth is published. This avoids false trend downgrades from partial outages and
avoids indefinitely carrying stale evidence forward.
"""

from __future__ import annotations

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
        except Exception as exc:  # source isolation and health reporting boundary
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

    # Build/validate only after all configured collectors completed successfully. Any PIT,
    # schema or scoring error raises before persistence and therefore preserves prior truth.
    fresh = list(collection.records)
    snapshot = build_snapshot(fresh, collection.research_as_of)
    persisted = persist_snapshot(snapshot, output_dir, evidence_records=fresh)
    return {
        **persisted,
        "research_as_of": collection.research_as_of,
        "health": [asdict(item) for item in collection.health],
        "evidence_count": len(fresh),
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }
