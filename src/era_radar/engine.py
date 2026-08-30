"""Deterministic scoring core for the Era & Capital Trend Radar V1.

The engine deliberately consumes normalized evidence rather than fetching data. Collection,
PIT validation and provenance live outside this module so frozen fixtures are reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

FAMILIES = {
    "POLICY_CAPITAL",
    "INDUSTRIAL_CAPITAL",
    "FINANCIAL_CAPITAL",
    "REAL_DEMAND",
    "TECHNOLOGY",
    "GLOBAL_STRUCTURE",
}

COMPONENTS = (
    "structural_demand",
    "policy_commitment",
    "industrial_capex",
    "real_demand_confirmation",
    "technology_enablement",
    "global_confirmation",
    "profit_pool_quality",
    "investable_bottleneck_strength",
    "financial_crowding",
    "evidence_quality",
)


@dataclass(frozen=True)
class EvidenceSignal:
    evidence_id: str
    family: str
    source_key: str
    direction: int  # -1 counter-evidence, 0 neutral, +1 supportive
    strength: float  # 0..1
    quality: float  # 0..1
    components: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown evidence family: {self.family}")
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction must be -1, 0 or 1")
        if not 0 <= self.strength <= 1 or not 0 <= self.quality <= 1:
            raise ValueError("strength and quality must be within [0, 1]")
        unknown = set(self.components) - set(COMPONENTS)
        if unknown:
            raise ValueError(f"unknown components: {sorted(unknown)}")


@dataclass(frozen=True)
class TrendSnapshot:
    trend_id: str
    components: Mapping[str, float]
    structural_score: float
    industrial_score: float
    cyclical_score: float
    confidence_score: float
    lifecycle: str
    independent_families: int
    evidence_count: int


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _dedupe(evidence: Iterable[EvidenceSignal]) -> list[EvidenceSignal]:
    """Do not treat repeated publication of the same source claim as confirmation."""
    best: dict[tuple[str, str], EvidenceSignal] = {}
    for item in evidence:
        key = (item.family, item.source_key)
        current = best.get(key)
        if current is None or item.quality * item.strength > current.quality * current.strength:
            best[key] = item
    return sorted(best.values(), key=lambda x: (x.family, x.source_key, x.evidence_id))


def score_trend(trend_id: str, evidence: Iterable[EvidenceSignal]) -> TrendSnapshot:
    items = _dedupe(evidence)
    totals = {name: 50.0 for name in COMPONENTS}
    weights = {name: 0.0 for name in COMPONENTS}

    for item in items:
        base_weight = item.strength * item.quality
        for component, exposure in item.components.items():
            if not -1 <= exposure <= 1:
                raise ValueError("component exposure must be within [-1, 1]")
            signed = item.direction * exposure
            totals[component] += 50.0 * signed * base_weight
            weights[component] += base_weight

    components = {}
    for name in COMPONENTS:
        # Shrink sparse evidence toward neutral rather than manufacture certainty.
        divisor = max(1.0, weights[name])
        components[name] = _clamp(50.0 + (totals[name] - 50.0) / divisor)

    structural = _clamp(
        0.42 * components["structural_demand"]
        + 0.18 * components["technology_enablement"]
        + 0.15 * components["global_confirmation"]
        + 0.15 * components["profit_pool_quality"]
        + 0.10 * components["investable_bottleneck_strength"]
    )
    industrial = _clamp(
        0.25 * components["industrial_capex"]
        + 0.25 * components["real_demand_confirmation"]
        + 0.20 * components["profit_pool_quality"]
        + 0.15 * components["policy_commitment"]
        + 0.15 * components["investable_bottleneck_strength"]
    )
    cyclical_raw = (
        0.35 * components["real_demand_confirmation"]
        + 0.25 * components["industrial_capex"]
        + 0.20 * components["profit_pool_quality"]
        + 0.20 * components["investable_bottleneck_strength"]
    )
    # Crowding is temperature/risk. It cannot upgrade a trend.
    cyclical = _clamp(cyclical_raw - max(0.0, components["financial_crowding"] - 70.0) * 0.35)

    families = {item.family for item in items if item.direction != 0 and item.quality >= 0.5}
    quality = components["evidence_quality"]
    breadth_factor = min(1.0, len(families) / 4.0)
    confidence = _clamp((0.45 * structural + 0.30 * industrial + 0.25 * quality) * breadth_factor)

    # Policy headlines alone are explicitly insufficient for confirmation.
    if families == {"POLICY_CAPITAL"}:
        confidence = min(confidence, 39.0)

    if confidence >= 72 and structural >= 65 and industrial >= 60 and len(families) >= 3:
        lifecycle = "CONFIRMED"
    elif confidence >= 58 and industrial >= 60:
        lifecycle = "ACCELERATING"
    elif confidence >= 40:
        lifecycle = "EMERGING"
    else:
        lifecycle = "EMERGING"

    if components["financial_crowding"] >= 82 and structural >= 65:
        lifecycle = "CROWDED"

    return TrendSnapshot(
        trend_id=trend_id,
        components=components,
        structural_score=structural,
        industrial_score=industrial,
        cyclical_score=cyclical,
        confidence_score=confidence,
        lifecycle=lifecycle,
        independent_families=len(families),
        evidence_count=len(items),
    )
