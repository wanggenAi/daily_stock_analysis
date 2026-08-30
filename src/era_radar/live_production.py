"""Fail-closed live production orchestration for Era Radar.

Live collection is separated from scoring/persistence so partial network failures cannot
silently downgrade durable trend state. Successful sources may extend the evidence set; a
failed source leaves prior durable truth untouched.
"""

from __future__ import annotations

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
    # Collector protocol includes a cutoff for deterministic adapters; live adapters ignore
    # this provisional value and stamp real retrieval time. Final cutoff is assigned below.
    provisional = iso_now()
    for collector in collectors:
        name = collector.__class__.__name__
        count = 0
        try:
            for observation in collector.collect(provisional):
                normalized = normalize_observation(observation)
                records.extend(normalized)
                count += len(normalized)
        except Exception as exc:  # collector isolation is intentional at this boundary
            health.append(CollectorHealth(name, "FAILED", count, f"{type(exc).__name__}: {exc}"))
        else:
            health.append(CollectorHealth(name, "SUCCESS", count))
    return LiveCollectionResult(tuple(records), tuple(health), iso_now())


def load_previous_evidence(output_dir: str | Path) -> list[EvidenceRecord]:
    root = Path(output_dir)
    latest = root / "latest.json"
    if not latest.exists():
        return []
    latest_payload = json.loads(latest.read_text(encoding="utf-8"))
    snapshot_id = latest_payload.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("invalid Era Radar latest snapshot id")
    evidence_path = root / "evidence" / f"{snapshot_id}.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError("invalid Era Radar evidence bundle")
    return [EvidenceRecord(**row) for row in rows]


def merge_evidence(previous: Iterable[EvidenceRecord], fresh: Iterable[EvidenceRecord]) -> list[EvidenceRecord]:
    """Replace matching source/topic claims while retaining unrelated prior evidence.

    This prevents a temporarily unavailable collector from creating false negative trend
    transitions. Evidence freshness is still validated by the downstream PIT boundary.
    """
    merged: dict[tuple[str, str, str], EvidenceRecord] = {}
    for item in previous:
        merged[(item.trend_id, item.family, item.source_key)] = item
    for item in fresh:
        merged[(item.trend_id, item.family, item.source_key)] = item
    # evidence_id must remain unique after merging. Newer exact ids replace prior ids.
    by_id: dict[str, EvidenceRecord] = {}
    for item in merged.values():
        by_id[item.evidence_id] = item
    return sorted(by_id.values(), key=lambda x: x.evidence_id)


def run_live_production(
    collectors: Iterable[Collector],
    *,
    output_dir: str | Path,
    require_any_success: bool = True,
) -> dict:
    collection = collect_live(collectors)
    if require_any_success and collection.successful_collectors == 0:
        return {
            "status": "NO_PUBLISH_COLLECTION_FAILED",
            "research_as_of": collection.research_as_of,
            "health": [asdict(item) for item in collection.health],
            "formal_trading_authority": False,
            "no_auto_trade": True,
        }

    previous = load_previous_evidence(output_dir)
    combined = merge_evidence(previous, collection.records)
    if not combined:
        return {
            "status": "NO_PUBLISH_NO_EVIDENCE",
            "research_as_of": collection.research_as_of,
            "health": [asdict(item) for item in collection.health],
            "formal_trading_authority": False,
            "no_auto_trade": True,
        }

    snapshot = build_snapshot(combined, collection.research_as_of)
    persisted = persist_snapshot(snapshot, output_dir, evidence_records=combined)
    return {
        **persisted,
        "research_as_of": collection.research_as_of,
        "health": [asdict(item) for item in collection.health],
        "evidence_count": len(combined),
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }
