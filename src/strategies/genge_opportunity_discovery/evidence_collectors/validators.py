"""URL validation and text extraction helpers for public evidence."""

from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


NUMBER_WITH_UNIT_RE = re.compile(
    r"(?P<value>-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>亿元|万元|元|股|万股|%|百分点|吨|万吨|台|片|GWh|MW|GW|亿|万)?"
)
PDF_EVIDENCE_PAGE_LIMIT = 20


def source_domain(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "")
    return parsed.netloc.lower()


def content_hash(content: bytes | str) -> str:
    raw = content.encode("utf-8", errors="ignore") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def extract_text_from_response(content: bytes, content_type: str) -> tuple[str, str]:
    ctype = str(content_type or "").lower()
    if content.startswith(b"%PDF") or "pdf" in ctype:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            pages = []
            for page in reader.pages[:PDF_EVIDENCE_PAGE_LIMIT]:
                pages.append(page.extract_text() or "")
            return "\n".join(pages), "pdf_pypdf"
        except Exception as exc:
            return "", f"pdf_parse_failed:{type(exc).__name__}"
    text = content.decode("utf-8", errors="ignore")
    return strip_html(text), "html_text"


def extract_numeric_context(text: str, keywords: list[str] | None = None) -> dict[str, str]:
    if not text:
        return {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    preferred: list[str] = []
    keyword_list = [item for item in (keywords or []) if item]
    if keyword_list:
        for line in lines:
            if any(keyword in line for keyword in keyword_list) and NUMBER_WITH_UNIT_RE.search(line):
                preferred.append(line)
                break
    if keyword_list and not preferred:
        return {}
    candidates = preferred or [line for line in lines if NUMBER_WITH_UNIT_RE.search(line)]
    if not candidates:
        return {}
    excerpt = candidates[0][:500]
    match = NUMBER_WITH_UNIT_RE.search(excerpt)
    if not match:
        return {}
    value = match.group("value").replace(",", "")
    unit = match.group("unit") or ""
    return {"value": value, "unit": unit, "excerpt": excerpt}


def direction_from_excerpt(excerpt: str) -> str:
    text = str(excerpt or "")
    if any(token in text for token in ("亏损", "下降", "减少", "下滑", "降低", "decrease", "decline", "loss")):
        return "NEGATIVE"
    if any(token in text for token in ("增长", "增加", "提升", "回升", "改善", "盈利", "achieved", "increase", "growth")):
        return "POSITIVE"
    percentage_values = [float(value) for value in re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", text)]
    if any(value <= -1.0 for value in percentage_values):
        return "NEGATIVE"
    if any(value >= 1.0 for value in percentage_values):
        return "POSITIVE"
    return "NEUTRAL"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
