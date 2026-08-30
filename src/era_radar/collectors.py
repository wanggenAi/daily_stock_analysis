"""Collector boundary for Era Radar.

Collectors acquire observations; they do not score trends. Live adapters may be added per
source, while this module keeps ingestion deterministic and fail-closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .evidence import EvidenceRecord
from .source_registry import DEFAULT_SOURCE_REGISTRY


@dataclass(frozen=True)
class RawObservation:
    evidence_id: str
    topic_keys: tuple[str, ...]
    family: str
    source_id: str
    source_key: str
    source_name: str
    source_url: str
    observed_at: str
    published_at: str | None
    retrieved_at: str
    freshness: str
    direction: int
    strength: float
    quality: float
    components: dict[str, float]


class Collector(Protocol):
    def collect(self, research_as_of: str) -> Iterable[RawObservation]: ...


def _source(source_id: str):
    matches = [item for item in DEFAULT_SOURCE_REGISTRY if item.source_id == source_id]
    if len(matches) != 1:
        raise ValueError(f"unregistered source_id: {source_id}")
    return matches[0]


def normalize_observation(item: RawObservation) -> list[EvidenceRecord]:
    spec = _source(item.source_id)
    if spec.family != item.family:
        raise ValueError(f"source family mismatch for {item.source_id}")
    topics = tuple(sorted({key.strip().lower() for key in item.topic_keys if key.strip()}))
    if not topics:
        raise ValueError("collector observation requires at least one topic key")
    return [
        EvidenceRecord(
            evidence_id=f"{item.evidence_id}:{topic}",
            trend_id=topic,
            family=item.family,
            source_key=item.source_key,
            source_name=item.source_name,
            source_url=item.source_url,
            source_tier=spec.tier,
            observed_at=item.observed_at,
            published_at=item.published_at,
            retrieved_at=item.retrieved_at,
            freshness=item.freshness,
            direction=item.direction,
            strength=item.strength,
            quality=item.quality,
            components=item.components,
        )
        for topic in topics
    ]


def collect_all(collectors: Iterable[Collector], research_as_of: str) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for collector in collectors:
        for observation in collector.collect(research_as_of):
            records.extend(normalize_observation(observation))
    return records


class JsonObservationCollector:
    """Deterministic adapter for normalized collector exports.

    Production source-specific fetchers can write the same JSON schema; this adapter makes
    collector outputs replayable for CI, audits and PIT reconstruction.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def collect(self, research_as_of: str) -> Iterable[RawObservation]:
        del research_as_of
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("observations")
        if not isinstance(rows, list):
            raise ValueError("collector JSON must contain observations list")
        for row in rows:
            yield RawObservation(
                evidence_id=row["evidence_id"],
                topic_keys=tuple(row["topic_keys"]),
                family=row["family"],
                source_id=row["source_id"],
                source_key=row["source_key"],
                source_name=row["source_name"],
                source_url=row["source_url"],
                observed_at=row["observed_at"],
                published_at=row.get("published_at"),
                retrieved_at=row["retrieved_at"],
                freshness=row["freshness"],
                direction=int(row["direction"]),
                strength=float(row["strength"]),
                quality=float(row["quality"]),
                components={str(k): float(v) for k, v in row["components"].items()},
            )
