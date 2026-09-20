"""Official PBC financial-capital collector for Era Radar.

The collector discovers the newest monthly Financial Statistics Report from the
People's Bank of China data-interpretation index and emits macro financing
channel observations only. These observations are FINANCIAL_CAPITAL research
evidence; they are never stock/industry fund-flow claims and never grant trading
authority.
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

PBC_INDEX_URL = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html"
PBC_ROOT = "https://www.pbc.gov.cn/"
TRANSIENT_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_REPORT_TITLE = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月金融统计数据报告")
_PUBLISHED = re.compile(r"文章来源[：:]\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})?")
_AFRE = re.compile(r"社会融资规模增量累计为([0-9.]+)万亿元，比上年同期(多|少)([0-9.]+)万亿元")
_ENTITY_RMB_LOANS = re.compile(
    r"对实体经济发放的人民币贷款增加([0-9.]+)万亿元，同比(多|少)增([0-9.]+)万亿元"
)
_CORPORATE_BONDS = re.compile(r"企业债券净融资([0-9.]+)万亿元，同比(多|少)([0-9.]+)万亿元")
_GOVERNMENT_BONDS = re.compile(r"政府债券净融资([0-9.]+)万亿元，同比(多|少)([0-9.]+)万亿元")
_EQUITY = re.compile(r"非金融企业境内股票融资([0-9.]+)亿元，同比(多|少)([0-9.]+)亿元")


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
class _Report:
    year: int
    month: int
    title: str
    url: str


def _fetch_html(url: str, *, timeout: float = 20.0, attempts: int = 3) -> str:
    if not url.startswith(PBC_ROOT):
        raise ValueError("PBC collector refuses non-PBC URL")
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
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - allowlisted PBC HTTPS root
                status = int(getattr(response, "status", 200))
                if status != 200:
                    if status in TRANSIENT_HTTP_STATUS and attempt < attempts:
                        time.sleep(attempt)
                        continue
                    raise RuntimeError(f"PBC HTTP {status}")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="strict")
        except HTTPError as exc:
            last_error = exc
            if exc.code in TRANSIENT_HTTP_STATUS and attempt < attempts:
                time.sleep(attempt)
                continue
            raise RuntimeError(f"PBC collection failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, UnicodeDecodeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt)
                continue
            raise RuntimeError(f"PBC collection failed after {attempts} attempts: {exc}") from exc
    raise RuntimeError(f"PBC collection failed after {attempts} attempts: {last_error}")


def _latest_monthly_report(index_html: str) -> _Report:
    parser = _AnchorParser()
    parser.feed(index_html)
    candidates: list[_Report] = []
    for href, title in parser.anchors:
        match = _REPORT_TITLE.fullmatch(title.strip())
        if not match:
            continue
        candidates.append(
            _Report(
                year=int(match.group("year")),
                month=int(match.group("month")),
                title=title.strip(),
                url=urljoin(PBC_INDEX_URL, href),
            )
        )
    if not candidates:
        raise ValueError("PBC monthly Financial Statistics Report link not found")
    return max(candidates, key=lambda item: (item.year, item.month, item.url))


def _article_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return parser.text()


def _published_at(text: str) -> str:
    match = _PUBLISHED.search(text)
    if not match:
        raise ValueError("PBC report publication timestamp missing")
    clock = match.group(2) or "00:00:00"
    local = datetime.fromisoformat(f"{match.group(1)}T{clock}+08:00")
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _freshness(published_at: str, retrieved_at: str) -> tuple[str, float]:
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    age_days = (retrieved - published).total_seconds() / 86400.0
    if age_days < -1:
        raise ValueError("PBC report publication time is in the future")
    if age_days <= 65:
        return "FRESH", 0.96
    if age_days <= 120:
        return "UNKNOWN", 0.84
    raise ValueError(f"PBC newest monthly report is stale: {age_days:.1f} days")


def _signed_delta(match: re.Match[str]) -> tuple[float, float]:
    current = float(match.group(1))
    direction_word = match.group(2)
    delta = float(match.group(3))
    return current, delta if direction_word == "多" else -delta


def _strength(current: float, signed_delta: float) -> float:
    relative = abs(signed_delta) / max(abs(current), 1e-9)
    return round(min(0.90, 0.45 + min(relative, 1.0) * 0.40), 4)


def _observation(
    *,
    report: _Report,
    published_at: str,
    retrieved_at: str,
    freshness: str,
    quality: float,
    metric: str,
    trend_id: str,
    current: float,
    signed_delta: float,
) -> RawObservation:
    direction = 1 if signed_delta > 0 else -1 if signed_delta < 0 else 0
    return RawObservation(
        evidence_id=f"pbc-financial:{report.year}-{report.month:02d}:{metric}",
        topic_keys=(trend_id,),
        family="FINANCIAL_CAPITAL",
        source_id="pbc",
        source_key=f"pbc-financial:{report.year}-{report.month:02d}:{metric}",
        source_name="中国人民银行金融统计数据报告",
        source_url=report.url,
        observed_at=published_at,
        published_at=published_at,
        retrieved_at=retrieved_at,
        freshness=freshness,
        direction=direction,
        strength=_strength(current, signed_delta),
        quality=quality,
        components={"financial_crowding": 1.0, "evidence_quality": 0.95},
    )


class PbcFinancialStatisticsCollector:
    """Collect current official macro financing-channel evidence from the PBC."""

    source_id = "pbc"

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
        report = _latest_monthly_report(self.index_fetcher(PBC_INDEX_URL))
        text = _article_text(self.article_fetcher(report.url))
        published_at = _published_at(text)
        retrieved_at = self.clock()
        freshness, quality = _freshness(published_at, retrieved_at)

        afre = _AFRE.search(text)
        entity_loans = _ENTITY_RMB_LOANS.search(text)
        corporate_bonds = _CORPORATE_BONDS.search(text)
        government_bonds = _GOVERNMENT_BONDS.search(text)
        equity = _EQUITY.search(text)
        missing = [
            name
            for name, match in (
                ("afre", afre),
                ("entity_rmb_loans", entity_loans),
                ("corporate_bonds", corporate_bonds),
                ("government_bonds", government_bonds),
                ("equity", equity),
            )
            if match is None
        ]
        if missing:
            raise ValueError(f"PBC Financial Statistics Report schema changed; missing={','.join(missing)}")

        afre_current, afre_delta = _signed_delta(afre)
        loan_current, loan_delta = _signed_delta(entity_loans)
        corp_current, corp_delta = _signed_delta(corporate_bonds)
        gov_current, gov_delta = _signed_delta(government_bonds)
        equity_current_yi, equity_delta_yi = _signed_delta(equity)
        equity_current = equity_current_yi / 10000.0
        equity_delta = equity_delta_yi / 10000.0

        rows = (
            ("aggregate_financing", "macro_financial_conditions", afre_current, afre_delta),
            ("entity_rmb_credit", "enterprise_credit_cycle", loan_current, loan_delta),
            ("government_bond_financing", "government_financing_impulse", gov_current, gov_delta),
            (
                "corporate_bond_equity_financing",
                "corporate_market_financing",
                corp_current + equity_current,
                corp_delta + equity_delta,
            ),
        )
        for metric, trend_id, current, signed_delta in rows:
            yield _observation(
                report=report,
                published_at=published_at,
                retrieved_at=retrieved_at,
                freshness=freshness,
                quality=quality,
                metric=metric,
                trend_id=trend_id,
                current=current,
                signed_delta=signed_delta,
            )
