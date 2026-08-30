"""Snapshot assembly pipeline for Era & Capital Trend Radar V1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from .engine import TrendSnapshot, score_trend
from .evidence import EvidenceRecord, normalize_for_scoring


@dataclass(frozen=True)
class RadarSnapshot:
    snapshot_id: str
    research_as_of: str
    trends: tuple[TrendSnapshot, ...]
    evidence_count: int
    formal_trading_authority: bool = False
    no_auto_trade: bool = True

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "research_as_of": self.research_as_of,
            "formal_trading_authority": self.formal_trading_authority,
            "no_auto_trade": self.no_auto_trade,
            "evidence_count": self.evidence_count,
            "trends": [asdict(item) for item in self.trends],
        }


def _snapshot_id(research_as_of: str, records: list[EvidenceRecord]) -> str:
    canonical = {
        "research_as_of": research_as_of,
        "evidence": [asdict(item) for item in sorted(records, key=lambda x: x.evidence_id)],
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_snapshot(records: Iterable[EvidenceRecord], research_as_of: str) -> RadarSnapshot:
    frozen_records = list(records)
    grouped = normalize_for_scoring(frozen_records, research_as_of)
    trends = tuple(
        score_trend(trend_id, grouped[trend_id])
        for trend_id in sorted(grouped)
    )
    return RadarSnapshot(
        snapshot_id=_snapshot_id(research_as_of, frozen_records),
        research_as_of=research_as_of,
        trends=trends,
        evidence_count=len(frozen_records),
    )


def render_markdown(snapshot: RadarSnapshot) -> str:
    lines = [
        "# Era & Capital Trend Radar",
        "",
        f"Snapshot: `{snapshot.snapshot_id}`",
        f"Research as of: `{snapshot.research_as_of}`",
        "",
        "> Research intelligence only. No Formal trading authority. No auto-trade.",
        "",
        "| Trend | State | Structural | Industrial | Cyclical | Confidence | Evidence families |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    ordered = sorted(snapshot.trends, key=lambda x: (x.confidence_score, x.structural_score), reverse=True)
    for item in ordered:
        lines.append(
            f"| {item.trend_id} | {item.lifecycle} | {item.structural_score:.2f} | "
            f"{item.industrial_score:.2f} | {item.cyclical_score:.2f} | "
            f"{item.confidence_score:.2f} | {item.independent_families} |"
        )
    return "\n".join(lines) + "\n"
