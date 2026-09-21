"""Official NBS fixed-asset-investment collector for Era Radar.

This collector discovers the newest National Bureau of Statistics monthly fixed
asset investment release and emits INDUSTRIAL_CAPITAL observations. It measures
real-economy capital expenditure direction; it is not a stock-market fund-flow
feed and has no trading authority.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .collectors import RawObservation
from .live_world_bank import iso_now

NBS_RELEASE_INDEX = "https://www.stats.gov.cn/sj/zxfb/"
NBS_ROOT = "https://www.stats.gov.cn/"
TRANSIENT_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_TITLE = re.compile(r"(?P<year>\d{4})年1[—-](?P<month>\d{1,2})月份全国固定资产投资基本情况")
_PUBLISHED = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}:\d{2})")
_TOTAL = re.compile(r"全国固定资产投资（不含农户）[0-9]+亿元，同比(增长|下降)([0-9.]+)%")
_INDUSTRIAL = re.compile(r"工业投资同比(增长|下降)([0-9.]+)%")
_MANUFACTURING = re.compile(r"制造业投资(增长|下降)([0-9.]+)%")
_INFRASTRUCTURE = re.compile(r"基础设施投资[^。]*同比(增长|下降)([0-9.]+)%")
_INFORMATION = re.compile(r"信息传输业投资(增长|下降)([0-9.]+)%")
_EQUIPMENT = re.compile(r"设备工器具购置\s*[|｜]?\s*([+-]?[0-9.]+)")


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            title = " ".join("".join(self._parts).split())
            if title:
                self.anchors.append((self._href, title))
            self._href = None
            self._parts = []


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(frozen=True)
class _Release:
    year: int
    month: int
    title: str
    url: str


def _fetch_html(url: str, *, timeout: float = 20.0, attempts: int = 3) -> str:
    if not url.startswith(NBS_ROOT):
        raise ValueError("NBS collector refuses non-NBS URL")
    request = Request(
        url,
        headers={
            "User-Agent": "daily-stock-analysis-era-radar/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - allowlisted NBS HTTPS root
                status = int(getattr(response, "status", 200))
                if status != 200:
                    if status in TRANSIENT_HTTP_STATUS and attempt < attempts:
                        time.sleep(attempt)
                        continue
                    raise RuntimeError(f"NBS HTTP {status}")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="strict")
        except HTTPError as exc:
            last_error = exc
            if exc.code in TRANSIENT_HTTP_STATUS and attempt < attempts:
                time.sleep(attempt)
                continue
            raise RuntimeError(f"NBS collection failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt)
                continue
            raise RuntimeError(f"NBS collection failed after {attempts} attempts: {exc}") from exc
    raise RuntimeError(f"NBS collection failed after {attempts} attempts: {last_error}")


def _latest_release(index_html: str) -> _Release:
    parser = _AnchorParser()
    parser.feed(index_html)
    candidates: list[_Release] = []
    for href, title in parser.anchors:
        match = _TITLE.fullmatch(title.strip())
        if not match:
            continue
        candidates.append(
            _Release(
                year=int(match.group("year")),
                month=int(match.group("month")),
                title=title.strip(),
                url=urljoin(NBS_RELEASE_INDEX, href),
            )
        )
    if not candidates:
        raise ValueError("NBS fixed-asset-investment release link not found")
    return max(candidates, key=lambda item: (item.year, item.month, item.url))


def _article_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return parser.text()


def _published_at(text: str) -> str:
    match = _PUBLISHED.search(text)
    if not match:
        raise ValueError("NBS investment release publication timestamp missing")
    local = datetime.fromisoformat(
        f"{match.group(1)}-{match.group(2)}-{match.group(3)}T{match.group(4)}:00+08:00"
    )
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _freshness(published_at: str, retrieved_at: str) -> tuple[str, float]:
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    age_days = (retrieved - published).total_seconds() / 86400.0
    if age_days < -1:
        raise ValueError("NBS release publication time is in the future")
    if age_days <= 65:
        return "FRESH", 0.96
    if age_days <= 120:
        return "UNKNOWN", 0.84
    raise ValueError(f"NBS newest investment release is stale: {age_days:.1f} days")


def _signed_growth(match: re.Match[str]) -> float:
    value = float(match.group(2))
    return value if match.group(1) == "增长" else -value


def _strength(growth_pct: float) -> float:
    return round(min(0.90, 0.45 + min(abs(growth_pct) / 30.0, 1.0) * 0.40), 4)


def _observation(
    *,
    release: _Release,
    published_at: str,
    retrieved_at: str,
    freshness: str,
    quality: float,
    metric: str,
    trend_id: str,
    growth_pct: float,
) -> RawObservation:
    return RawObservation(
        evidence_id=f"nbs-investment:{release.year}-{release.month:02d}:{metric}",
        topic_keys=(trend_id,),
        family="INDUSTRIAL_CAPITAL",
        source_id="stats_cn_investment",
        source_key=f"nbs-investment:{release.year}-{release.month:02d}:{metric}",
        source_name="国家统计局固定资产投资",
        source_url=release.url,
        observed_at=published_at,
        published_at=published_at,
        retrieved_at=retrieved_at,
        freshness=freshness,
        direction=1 if growth_pct > 0 else -1 if growth_pct < 0 else 0,
        strength=_strength(growth_pct),
        quality=quality,
        components={"industrial_capex": 1.0, "evidence_quality": 0.95},
    )


class NbsFixedAssetInvestmentCollector:
    source_id = "stats_cn_investment"

    def __init__(
        self,
        *,
        index_fetcher: Callable[[str], str] = _fetch_html,
        article_fetcher: Callable[[str], str] = _fetch_html,
        clock: Callable[[], str] = iso_now,
    ):
        self.index_fetcher = index_fetcher
        self.article_fetcher = article_fetcher
        self.clock = clock

    def collect(self, research_as_of: str):
        del research_as_of
        release = _latest_release(self.index_fetcher(NBS_RELEASE_INDEX))
        text = _article_text(self.article_fetcher(release.url))
        published_at = _published_at(text)
        retrieved_at = self.clock()
        freshness, quality = _freshness(published_at, retrieved_at)

        total = _TOTAL.search(text)
        industrial = _INDUSTRIAL.search(text)
        manufacturing = _MANUFACTURING.search(text)
        infrastructure = _INFRASTRUCTURE.search(text)
        information = _INFORMATION.search(text)
        equipment = _EQUIPMENT.search(text)
        missing = [
            name
            for name, match in (
                ("total_fixed_asset_investment", total),
                ("industrial_investment", industrial),
                ("manufacturing_investment", manufacturing),
                ("infrastructure_investment", infrastructure),
                ("equipment_purchase", equipment),
            )
            if match is None
        ]
        if missing:
            raise ValueError(f"NBS investment release schema changed; missing={','.join(missing)}")

        rows = [
            ("aggregate_fixed_asset_investment", "macro_industrial_capex", _signed_growth(total)),
            ("industrial_investment", "industrial_capex_cycle", _signed_growth(industrial)),
            ("manufacturing_investment", "manufacturing_capex", _signed_growth(manufacturing)),
            ("infrastructure_investment", "infrastructure_capex", _signed_growth(infrastructure)),
        ]
        equipment_growth = float(equipment.group(1))
        rows.append(("equipment_purchase", "equipment_investment", equipment_growth))
        if information is not None:
            rows.append(("information_transmission_investment", "digital_infrastructure", _signed_growth(information)))

        for metric, trend_id, growth_pct in rows:
            yield _observation(
                release=release,
                published_at=published_at,
                retrieved_at=retrieved_at,
                freshness=freshness,
                quality=quality,
                metric=metric,
                trend_id=trend_id,
                growth_pct=growth_pct,
            )
