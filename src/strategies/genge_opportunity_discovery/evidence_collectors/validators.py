"""URL validation and layout-tolerant extraction helpers for public evidence."""

from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .evidence_normalization import (
    PARSE_FAILED,
    SOURCE_DATA_ABSENT,
    STRUCTURE_RECOVERY_FAILED,
    VALUE_RECOVERED,
    VALUE_STATUSES,
    VALUE_VERIFIED,
    extract_labeled_numeric_evidence,
    normalize_evidence_text,
)


NUMBER_WITH_UNIT_RE = re.compile(
    r"(?P<value>-?\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(?P<unit>亿元|万元|元|股|万股|%|百分点|吨|万吨|台|片|GWh|MW|GW|亿|万)?"
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


def extract_text_from_response_detailed(content: bytes, content_type: str) -> dict[str, Any]:
    """Extract source text while preserving parse-vs-absence failure semantics."""
    if not content:
        return {
            "status": SOURCE_DATA_ABSENT,
            "text": "",
            "parser": "empty_response",
            "reason": "EMPTY_RESPONSE_BODY",
        }

    ctype = str(content_type or "").lower()
    if content.startswith(b"%PDF") or "pdf" in ctype:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            pages = [(page.extract_text() or "") for page in reader.pages[:PDF_EVIDENCE_PAGE_LIMIT]]
            text = "\n".join(pages)
            if not text.strip():
                return {
                    "status": STRUCTURE_RECOVERY_FAILED,
                    "text": "",
                    "parser": "pdf_pypdf",
                    "reason": "PDF_PARSED_WITHOUT_EXTRACTABLE_TEXT",
                }
            return {
                "status": VALUE_RECOVERED,
                "text": text,
                "parser": "pdf_pypdf",
                "reason": "PDF_TEXT_EXTRACTED",
            }
        except Exception as exc:
            parser = f"pdf_parse_failed:{type(exc).__name__}"
            return {
                "status": PARSE_FAILED,
                "text": "",
                "parser": parser,
                "reason": parser,
            }

    text = strip_html(content.decode("utf-8", errors="ignore"))
    if not text.strip():
        return {
            "status": SOURCE_DATA_ABSENT,
            "text": "",
            "parser": "html_text",
            "reason": "HTML_HAS_NO_EXTRACTABLE_TEXT",
        }
    return {
        "status": VALUE_VERIFIED,
        "text": text,
        "parser": "html_text",
        "reason": "HTML_TEXT_EXTRACTED",
    }


def extract_text_from_response(content: bytes, content_type: str) -> tuple[str, str]:
    """Backward-compatible text API; detailed status is available separately."""
    result = extract_text_from_response_detailed(content, content_type)
    return str(result["text"]), str(result["parser"])


def _legacy_extract_numeric_context(
    text: str,
    keywords: list[str] | None = None,
) -> dict[str, str]:
    """Preserve the old fast path so already-good inputs cannot regress."""
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


def extract_numeric_context_detailed(
    text: str,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Return typed extraction status instead of collapsing every miss to UNKNOWN."""
    legacy = _legacy_extract_numeric_context(text, keywords)
    if legacy:
        matched_label = next(
            (item for item in (keywords or []) if item and item in legacy["excerpt"]),
            "",
        )
        return {
            "status": VALUE_VERIFIED,
            "canonical_label": matched_label,
            "matched_label": matched_label,
            "raw_value": legacy["value"],
            "number_text": legacy["value"],
            "numeric_value": float(legacy["value"]),
            "unit": legacy["unit"],
            "unit_family": "",
            "normalized_value": None,
            "normalized_unit": "",
            "unit_source": "INLINE" if legacy["unit"] else "",
            "extraction_method": "LEGACY_SAME_LINE",
            "excerpt": legacy["excerpt"],
            "reason": "EXISTING_SAME_LINE_EXTRACTION_VERIFIED",
        }

    keyword_list = [item for item in (keywords or []) if item]
    if not keyword_list:
        return {
            "status": SOURCE_DATA_ABSENT if not str(text or "").strip() else STRUCTURE_RECOVERY_FAILED,
            "reason": "NO_KEYWORD_BOUND_RECOVERY_TARGET",
        }

    result = extract_labeled_numeric_evidence(
        text,
        labels=keyword_list,
        max_chars_after_label=180,
    )
    return result.to_dict()


def extract_numeric_context(text: str, keywords: list[str] | None = None) -> dict[str, str]:
    """Use the legacy fast path, then recover safe split-layout values if needed."""
    legacy = _legacy_extract_numeric_context(text, keywords)
    if legacy:
        return legacy

    detail = extract_numeric_context_detailed(text, keywords)
    if detail.get("status") not in VALUE_STATUSES:
        return {}
    value = str(detail.get("number_text") or "").replace(",", "")
    if not value:
        return {}
    return {
        "value": value,
        "unit": str(detail.get("unit") or ""),
        "excerpt": str(detail.get("excerpt") or "")[:500],
    }


def direction_from_excerpt(excerpt: str) -> str:
    text = normalize_evidence_text(excerpt)
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
