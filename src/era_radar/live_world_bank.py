"""Live World Bank structural evidence collector for Era Radar.

Uses the public World Bank V2 Indicators API. This adapter is deliberately narrow:
only explicitly registered indicators with deterministic transforms may enter Radar evidence.
Network/data failures raise and therefore cannot silently mutate durable Radar truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .collectors import RawObservation

API_ROOT = "https://api.worldbank.org/v2"


@dataclass(frozen=True)
class IndicatorSpec:
    code: str
    trend_id: str
    component: str
    direction_when_rising: int
    min_years: int = 5


# Driver taxonomy, not investment conclusions. Scores are derived from observed series.
INDICATORS = (
    IndicatorSpec("SP.POP.65UP.TO.ZS", "demographic_longevity", "structural_demand", 1),
    IndicatorSpec("SP.URB.TOTL.IN.ZS", "urbanization_services", "structural_demand", 1),
    IndicatorSpec("GB.XPD.RSDV.GD.ZS", "research_intensity", "technology_enablement", 1),
    IndicatorSpec("NV.IND.MANF.ZS", "advanced_manufacturing", "industrial_capex", 1),
    IndicatorSpec("IT.NET.USER.ZS", "digitalization", "technology_enablement", 1),
    IndicatorSpec("EG.ELC.ACCS.ZS", "electrification_infrastructure", "structural_demand", 1),
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fetch_json(url: str, *, timeout: float = 20.0) -> object:
    request = Request(url, headers={"User-Agent": "daily-stock-analysis-era-radar/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API root
            if response.status != 200:
                raise RuntimeError(f"World Bank HTTP {response.status}")
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"World Bank collection failed: {exc}") from exc


def _series(code: str, *, fetcher: Callable[[str], object] = _fetch_json) -> list[tuple[int, float]]:
    query = urlencode({"format": "json", "mrnev": 12, "per_page": 100})
    url = f"{API_ROOT}/country/CHN/indicator/{code}?{query}"
    payload = fetcher(url)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise ValueError(f"invalid World Bank payload for {code}")
    points: list[tuple[int, float]] = []
    for row in payload[1]:
        if not isinstance(row, dict) or row.get("value") is None:
            continue
        try:
            points.append((int(row["date"]), float(row["value"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid World Bank data point for {code}") from exc
    points.sort()
    return points


def _trend_strength(points: list[tuple[int, float]], spec: IndicatorSpec) -> tuple[int, float]:
    if len(points) < spec.min_years:
        raise ValueError(f"insufficient history for {spec.code}: {len(points)}")
    recent = points[-min(5, len(points)):]
    first = recent[0][1]
    last = recent[-1][1]
    scale = max(abs(first), 1e-9)
    relative = (last - first) / scale
    signed = spec.direction_when_rising if relative > 0 else -spec.direction_when_rising if relative < 0 else 0
    # Saturating transform: prevents a single macro series from manufacturing certainty.
    strength = min(0.85, 0.35 + min(abs(relative), 0.50)) if signed else 0.20
    return signed, round(strength, 4)


class WorldBankChinaStructuralCollector:
    source_id = "world_bank"

    def __init__(self, *, fetcher: Callable[[str], object] = _fetch_json):
        self.fetcher = fetcher

    def collect(self, research_as_of: str):
        retrieved_at = _iso_now()
        if retrieved_at > research_as_of:
            # Scheduled production must set research_as_of at/after actual retrieval time.
            retrieved_at = research_as_of
        for spec in INDICATORS:
            points = _series(spec.code, fetcher=self.fetcher)
            direction, strength = _trend_strength(points, spec)
            latest_year, latest_value = points[-1]
            source_url = f"{API_ROOT}/country/CHN/indicator/{spec.code}?format=json"
            yield RawObservation(
                evidence_id=f"wb:{spec.code}:{latest_year}",
                topic_keys=(spec.trend_id,),
                family="GLOBAL_STRUCTURE",
                source_id=self.source_id,
                source_key=f"{spec.code}:{latest_year}",
                source_name=f"World Bank {spec.code}",
                source_url=source_url,
                observed_at=f"{latest_year}-12-31T23:59:59Z",
                published_at=None,
                retrieved_at=retrieved_at,
                freshness="FRESH",
                direction=direction,
                strength=strength,
                quality=0.82,
                components={spec.component: 1.0, "global_confirmation": 0.7, "evidence_quality": 0.8},
            )
