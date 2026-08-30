"""Read-only research handoff from Era Radar to downstream discovery.

This module deliberately cannot emit Formal trading actions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchHandoff:
    trend_id: str
    industry_link: str
    symbol: str
    market: str
    rationale: str
    confidence_score: float
    authority: str = "RESEARCH_ONLY"


def build_research_handoff(
    *,
    trend_id: str,
    industry_link: str,
    symbol: str,
    market: str,
    rationale: str,
    confidence_score: float,
    provenance_ok: bool,
    freshness_ok: bool,
    min_confidence: float = 58.0,
) -> ResearchHandoff | None:
    if market not in {"SH", "SZ"}:
        return None
    if not provenance_ok or not freshness_ok:
        return None
    if confidence_score < min_confidence:
        return None
    if not rationale.strip():
        return None
    return ResearchHandoff(
        trend_id=trend_id,
        industry_link=industry_link,
        symbol=symbol,
        market=market,
        rationale=rationale,
        confidence_score=confidence_score,
    )
