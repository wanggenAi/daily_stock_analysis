"""Industry-agnostic trend hypothesis discovery.

Discovery groups normalized evidence by topic key. Topic labels identify a hypothesis; they
never determine the score or lifecycle state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .evidence import EvidenceRecord


@dataclass(frozen=True)
class TrendHypothesis:
    trend_id: str
    evidence_ids: tuple[str, ...]
    evidence_families: tuple[str, ...]
    source_count: int
    research_priority: str


def discover_hypotheses(records: Iterable[EvidenceRecord]) -> tuple[TrendHypothesis, ...]:
    grouped: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        key = record.trend_id.strip().lower()
        if not key:
            raise ValueError("empty trend/topic key")
        grouped.setdefault(key, []).append(record)

    hypotheses = []
    for trend_id, items in sorted(grouped.items()):
        families = tuple(sorted({item.family for item in items}))
        sources = {(item.family, item.source_key) for item in items}
        causal_families = set(families) - {"FINANCIAL_CAPITAL"}
        if len(causal_families) >= 4:
            priority = "HIGH"
        elif len(causal_families) >= 2:
            priority = "NORMAL"
        else:
            priority = "WATCH"
        hypotheses.append(
            TrendHypothesis(
                trend_id=trend_id,
                evidence_ids=tuple(sorted(item.evidence_id for item in items)),
                evidence_families=families,
                source_count=len(sources),
                research_priority=priority,
            )
        )
    return tuple(hypotheses)
