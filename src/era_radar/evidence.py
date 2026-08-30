"""PIT/provenance normalization for Era Radar evidence.

Collectors may fetch from heterogeneous sources, but scoring only accepts normalized
EvidenceRecord instances that pass this validation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from .engine import EvidenceSignal, FAMILIES

SOURCE_TIERS = {"PRIMARY", "OFFICIAL", "HIGH_QUALITY_SECONDARY", "SECONDARY"}
FRESHNESS = {"FRESH", "STALE", "UNKNOWN"}


def _parse_iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp for {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    trend_id: str
    family: str
    source_key: str
    source_name: str
    source_url: str
    source_tier: str
    observed_at: str
    published_at: str | None
    retrieved_at: str
    freshness: str
    direction: int
    strength: float
    quality: float
    components: Mapping[str, float]

    def validate(self, research_as_of: str) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown evidence family: {self.family}")
        if self.source_tier not in SOURCE_TIERS:
            raise ValueError(f"unknown source tier: {self.source_tier}")
        if self.freshness not in FRESHNESS:
            raise ValueError(f"unknown freshness: {self.freshness}")
        if not self.source_key or not self.source_name or not self.source_url:
            raise ValueError("source identity and URL are required")

        cutoff = _parse_iso(research_as_of, "research_as_of")
        observed = _parse_iso(self.observed_at, "observed_at")
        retrieved = _parse_iso(self.retrieved_at, "retrieved_at")
        published = _parse_iso(self.published_at, "published_at") if self.published_at else None

        # Strict PIT: no future observation, publication, or retrieval may inform a snapshot.
        for field, value in (("observed_at", observed), ("retrieved_at", retrieved), ("published_at", published)):
            if value is not None and value > cutoff:
                raise ValueError(f"PIT violation: {field} is after research_as_of")
        if observed > retrieved:
            raise ValueError("observed_at cannot be after retrieved_at")
        if published is not None and published > retrieved:
            raise ValueError("published_at cannot be after retrieved_at")
        if self.freshness == "STALE":
            raise ValueError("stale evidence cannot enter scoring")

        # Preserve scoring validation in one place.
        self.to_signal()

    def to_signal(self) -> EvidenceSignal:
        return EvidenceSignal(
            evidence_id=self.evidence_id,
            family=self.family,
            source_key=self.source_key,
            direction=self.direction,
            strength=self.strength,
            quality=self.quality,
            components=self.components,
        )


def normalize_for_scoring(records: list[EvidenceRecord], research_as_of: str) -> dict[str, list[EvidenceSignal]]:
    by_trend: dict[str, list[EvidenceSignal]] = {}
    seen_ids: set[str] = set()
    for record in records:
        if record.evidence_id in seen_ids:
            raise ValueError(f"duplicate evidence_id: {record.evidence_id}")
        seen_ids.add(record.evidence_id)
        record.validate(research_as_of)
        by_trend.setdefault(record.trend_id, []).append(record.to_signal())
    return by_trend
