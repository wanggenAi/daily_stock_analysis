"""Official MIIT policy-title collector for Era Radar.

This adapter reads the Ministry of Industry and Information Technology RSS/subscription page
and turns only explicitly classified policy/standard/plan titles into low-to-moderate strength
POLICY_CAPITAL evidence. Titles alone can never confirm a trend because the scoring engine
requires independent non-policy evidence families.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .collectors import RawObservation
from .live_world_bank import iso_now

MIIT_RSS_PAGE = "https://www.miit.gov.cn/RRSdy/"


@dataclass(frozen=True)
class TopicRule:
    trend_id: str
    keywords: tuple[str, ...]


TOPIC_RULES = (
    TopicRule("embodied_intelligence", ("人形机器人", "机器人产业")),
    TopicRule("brain_computer_interface", ("脑机接口",)),
    TopicRule("quantum_information", ("量子信息", "量子通信", "量子计算")),
    TopicRule("intelligent_ev_supply_chain", ("新能源汽车", "动力电池", "智能网联汽车")),
    TopicRule("solar_energy_system", ("光伏", "太阳光伏")),
    TopicRule("digital_infrastructure", ("通信业", "信息通信", "5G", "6G")),
    TopicRule("software_digital_economy", ("软件业", "工业软件", "数字经济")),
    TopicRule("advanced_shipbuilding", ("造船", "船舶工业")),
    TopicRule("artificial_intelligence", ("人工智能", "大模型")),
    TopicRule("semiconductor_independence", ("集成电路", "半导体")),
    TopicRule("industrial_machine_tools", ("工业母机", "数控机床")),
    TopicRule("advanced_materials", ("新材料", "先进材料")),
)

_POLICY_MARKERS = ("指南", "规划", "标准", "规范", "意见", "方案", "公告", "办法", "目录")


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._href: str | None = None
        self._parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href")
        self._parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            text = " ".join("".join(self._parts).split())
            if text:
                self.anchors.append((self._href, text))
            self._href = None
            self._parts = []


def _fetch_html(url: str = MIIT_RSS_PAGE, *, timeout: float = 20.0) -> str:
    if not url.startswith("https://www.miit.gov.cn/"):
        raise ValueError("MIIT collector refuses non-MIIT URL")
    request = Request(url, headers={"User-Agent": "daily-stock-analysis-era-radar/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - allowlisted HTTPS root above
            if response.status != 200:
                raise RuntimeError(f"MIIT HTTP {response.status}")
            return response.read().decode("utf-8", errors="strict")
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"MIIT collection failed: {exc}") from exc


def _topics(title: str) -> tuple[str, ...]:
    return tuple(sorted({rule.trend_id for rule in TOPIC_RULES if any(word in title for word in rule.keywords)}))


def _strength(title: str) -> float:
    marker_count = sum(marker in title for marker in _POLICY_MARKERS)
    return 0.62 if marker_count else 0.42


class MiitPolicyCollector:
    source_id = "miit"

    def __init__(self, *, fetcher: Callable[[], str] = _fetch_html, clock: Callable[[], str] = iso_now):
        self.fetcher = fetcher
        self.clock = clock

    def collect(self, research_as_of: str):
        del research_as_of
        html = self.fetcher()
        parser = _AnchorParser()
        parser.feed(html)
        retrieved_at = self.clock()
        seen: set[tuple[str, str]] = set()
        for href, title in parser.anchors:
            topics = _topics(title)
            if not topics:
                continue
            absolute = urljoin(MIIT_RSS_PAGE, href)
            key = hashlib.sha256(f"{absolute}\n{title}".encode("utf-8")).hexdigest()[:16]
            for topic in topics:
                dedupe = (topic, key)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                yield RawObservation(
                    evidence_id=f"miit:{key}:{topic}",
                    topic_keys=(topic,),
                    family="POLICY_CAPITAL",
                    source_id=self.source_id,
                    source_key=f"miit:{key}",
                    source_name="工业和信息化部",
                    source_url=absolute,
                    observed_at=retrieved_at,
                    published_at=None,
                    retrieved_at=retrieved_at,
                    freshness="FRESH",
                    direction=1,
                    strength=_strength(title),
                    quality=0.78,
                    components={"policy_commitment": 1.0, "evidence_quality": 0.75},
                )
