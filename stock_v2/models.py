from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Candidate:
    code: str
    name: str
    industry: str = "UNKNOWN"
    score: float = 0.0
    state: str = "WATCH"
    confidence: str = "LOW"
    current_price: float | None = None
    buy_low: float | None = None
    buy_high: float | None = None
    distance_to_buy_pct: float | None = None
    change: str = "NEW"
    rank: int = 0
    source: str = ""
    source_tier: str = ""
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    holding: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
