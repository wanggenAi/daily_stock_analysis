"""Official MIIT live collectors for Era Radar.

Policy titles provide POLICY_CAPITAL evidence only when they contain policy/standard markers.
Official industrial-operation articles provide REAL_DEMAND evidence from deterministic growth
vs decline language. Neither collector has trading authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
    TopicRule("automotive_industry", ("汽车工业", "汽车产业")),
    TopicRule("solar_energy_system", ("光伏", "太阳光伏")),
    TopicRule("digital_infrastructure", ("通信业", "信息通信", "5G", "6G")),
    TopicRule("software_digital_economy", ("软件业", "工业软件", "数字经济")),
    TopicRule("electronics_manufacturing", ("电子信息制造业", "电子信息产业")),
    TopicRule("advanced_shipbuilding", ("造船", "船舶工业")),
    TopicRule("artificial_intelligence", ("人工智能", "大模型")),
    TopicRule("semiconductor_independence", ("集成电路", "半导体")),
    TopicRule("industrial_machine_tools", ("工业母机", "数控机床")),
    TopicRule("advanced_materials", ("新材料", "先进材料")),
)

_POLICY_MARKERS = ("指南", "规划", "标准", "规范", "意见", "方案", "公告", "办法", "目录")
_POSITIVE = re.compile(r"(?:同比|较上年[^，。；]*|比上年[^，。；]*)(?:增长|增加|提升|上升)|持续扩大|稳步增加|较快增长")
_NEGATIVE = re.compile(r"(?:同比|较上年[^，。；]*|比上年[^，。；]*)(?:下降|减少|下滑)|持续下滑")
_PUBLISHED = re.compile(r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})?")


class _AnchorParser(HTMLParser):
    def __init__(self):
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
            text = " ".join("".join(self._parts).split())
            if text:
                self.anchors.append((self._href, text))
            self._href = None
            self._parts = []


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


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


def _fetch_index() -> str:
    return _fetch_html(MIIT_RSS_PAGE)


def _topics(title: str) -> tuple[str, ...]:
    return tuple(sorted({rule.trend_id for rule in TOPIC_RULES if any(word in title for word in rule.keywords)}))


def _published_at(text: str) -> str | None:
    match = _PUBLISHED.search(text)
    if not match:
        return None
    clock = match.group(2) or "00:00"
    local = datetime.fromisoformat(f"{match.group(1)}T{clock}:00+08:00")
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _demand_direction(text: str) -> tuple[int, float] | None:
    positive = len(_POSITIVE.findall(text))
    negative = len(_NEGATIVE.findall(text))
    total = positive + negative
    if total == 0:
        return None
    direction = 1 if positive > negative else -1 if negative > positive else 0
    balance = abs(positive - negative) / total
    strength = round(min(0.82, 0.42 + 0.35 * balance + min(total, 8) * 0.02), 4)
    return direction, strength


class MiitPolicyCollector:
    source_id = "miit"

    def __init__(self, *, fetcher: Callable[[], str] = _fetch_index, clock: Callable[[], str] = iso_now):
        self.fetcher = fetcher
        self.clock = clock

    def collect(self, research_as_of: str):
        del research_as_of
        parser = _AnchorParser()
        parser.feed(self.fetcher())
        retrieved_at = self.clock()
        seen: set[tuple[str, str]] = set()
        for href, title in parser.anchors:
            topics = _topics(title)
            if not topics or not any(marker in title for marker in _POLICY_MARKERS):
                continue
            absolute = urljoin(MIIT_RSS_PAGE, href)
            key = hashlib.sha256(f"{absolute}\n{title}".encode("utf-8")).hexdigest()[:16]
            for topic in topics:
                if (topic, key) in seen:
                    continue
                seen.add((topic, key))
                yield RawObservation(
                    evidence_id=f"miit-policy:{key}:{topic}",
                    topic_keys=(topic,),
                    family="POLICY_CAPITAL",
                    source_id=self.source_id,
                    source_key=f"miit-policy:{key}",
                    source_name="工业和信息化部",
                    source_url=absolute,
                    observed_at=retrieved_at,
                    published_at=None,
                    retrieved_at=retrieved_at,
                    freshness="FRESH",
                    direction=1,
                    strength=0.62,
                    quality=0.78,
                    components={"policy_commitment": 1.0, "evidence_quality": 0.75},
                )


class MiitStatisticsCollector:
    source_id = "miit_statistics"

    def __init__(
        self,
        *,
        index_fetcher: Callable[[], str] = _fetch_index,
        article_fetcher: Callable[[str], str] = _fetch_html,
        clock: Callable[[], str] = iso_now,
    ):
        self.index_fetcher = index_fetcher
        self.article_fetcher = article_fetcher
        self.clock = clock

    def collect(self, research_as_of: str):
        del research_as_of
        parser = _AnchorParser()
        parser.feed(self.index_fetcher())
        retrieved_at = self.clock()
        seen_urls: set[str] = set()
        for href, title in parser.anchors:
            topics = _topics(title)
            if not topics or not ("运行情况" in title or "经济运行" in title or "统计" in title):
                continue
            absolute = urljoin(MIIT_RSS_PAGE, href)
            if absolute in seen_urls:
                continue
            seen_urls.add(absolute)
            article_html = self.article_fetcher(absolute)
            text_parser = _TextParser()
            text_parser.feed(article_html)
            article_text = text_parser.text()
            demand = _demand_direction(article_text)
            if demand is None:
                continue
            direction, strength = demand
            published_at = _published_at(article_text)
            observed_at = published_at or retrieved_at
            digest = hashlib.sha256(article_text.encode("utf-8")).hexdigest()[:16]
            for topic in topics:
                yield RawObservation(
                    evidence_id=f"miit-stats:{digest}:{topic}",
                    topic_keys=(topic,),
                    family="REAL_DEMAND",
                    source_id=self.source_id,
                    source_key=f"miit-stats:{digest}",
                    source_name="工业和信息化部统计分析",
                    source_url=absolute,
                    observed_at=observed_at,
                    published_at=published_at,
                    retrieved_at=retrieved_at,
                    freshness="FRESH",
                    direction=direction,
                    strength=strength,
                    quality=0.86,
                    components={"real_demand_confirmation": 1.0, "evidence_quality": 0.85},
                )
