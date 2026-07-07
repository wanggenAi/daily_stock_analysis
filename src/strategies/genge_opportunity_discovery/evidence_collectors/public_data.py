"""Government or industry public-data collector."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .cache import EvidenceCache
from .validators import content_hash, direction_from_excerpt, extract_numeric_context, extract_text_from_response, source_domain, utc_now


PUBLIC_SOURCES = [
    ("miit_public_data", "https://www.miit.gov.cn/gxsj/index.html", "工业和信息化部公开数据"),
    ("ndrc_public_data", "https://www.ndrc.gov.cn/fgsj/", "国家发展改革委公开数据"),
]


def _extract_publish_date(text: str) -> str:
    patterns = [
        r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
        r"发布时间[:：\s]*(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
        r"发布日期[:：\s]*(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return ""


def _article_candidates(html: str, *, base_url: str, keyword: str, limit: int = 5) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for anchor in soup.find_all("a"):
        title = anchor.get_text(" ", strip=True)
        href = str(anchor.get("href") or "").strip()
        if not title or not href:
            continue
        if keyword not in title:
            continue
        url = urljoin(base_url, href)
        if source_domain(url) != source_domain(base_url):
            continue
        candidates.append((title, url))
        if len(candidates) >= limit:
            break
    return candidates


def _audit_row(
    *,
    industry: str,
    collector: str,
    status: str,
    issue: str,
    detail: str,
    url: str,
    title: str,
    cache_hit: bool = False,
) -> dict[str, Any]:
    return {
        "scope": "industry",
        "code": "",
        "stock_name": "",
        "industry": industry,
        "collector": collector,
        "status": status,
        "issue": issue,
        "detail": detail,
        "original_url": url,
        "source_domain": source_domain(url),
        "title": title,
        "collected_at": utc_now(),
        "cache_hit": cache_hit,
    }


def collect_public_industry_data(
    *,
    industries: list[str],
    as_of: date,
    cache: EvidenceCache,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    session = requests.Session()
    evidence_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    network_fetches = 0
    fetch_successes = 0
    task_count = 0

    for industry in [item for item in dict.fromkeys(industries) if item]:
        for collector, url, title in PUBLIC_SOURCES:
            task_count += 1
            key = cache.key_for({"collector": collector, "industry": industry, "source": url, "version": 2})
            cached = cache.get(key)
            if cached is not None:
                evidence_rows.extend(cached.get("evidence_rows") or [])
                for audit in cached.get("audit_rows") or []:
                    audit = dict(audit)
                    audit["cache_hit"] = True
                    audit_rows.append(audit)
                continue
            task_evidence: list[dict[str, Any]] = []
            task_audit: list[dict[str, Any]] = []
            try:
                response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
                network_fetches += 1
                response.raise_for_status()
                listing_text, parser = extract_text_from_response(response.content, response.headers.get("content-type", ""))
                listing_html = response.content.decode("utf-8", errors="ignore")
                if listing_text:
                    fetch_successes += 1
            except Exception as exc:
                task_audit.append(
                    _audit_row(
                        industry=industry,
                        collector=collector,
                        status="FAILED",
                        issue="public_data_fetch_failed",
                        detail=f"{type(exc).__name__}: {exc}",
                        url=url,
                        title=title,
                    )
                )
                audit_rows.extend(task_audit)
                cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
                continue

            article_evidence_found = False
            article_attempts = _article_candidates(listing_html, base_url=url, keyword=industry)
            for article_title, article_url in article_attempts:
                try:
                    article_response = session.get(article_url, headers={"User-Agent": "Mozilla/5.0", "Referer": url}, timeout=timeout)
                    network_fetches += 1
                    article_response.raise_for_status()
                    article_text, article_parser = extract_text_from_response(article_response.content, article_response.headers.get("content-type", ""))
                    if article_text:
                        fetch_successes += 1
                except Exception as exc:
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="FAILED",
                            issue="public_article_fetch_failed",
                            detail=f"{type(exc).__name__}: {exc}",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                publish_date = _extract_publish_date(article_text)
                if not publish_date:
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="FAILED",
                            issue="article_publish_date_missing",
                            detail="Concrete article was fetched, but a publication date was not located.",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                if publish_date > as_of.isoformat():
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="FAILED",
                            issue="future_dated_article_excluded",
                            detail=f"publish_date={publish_date} is after as_of={as_of.isoformat()}",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                if industry not in article_text:
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="MISSING",
                            issue="industry_keyword_not_found_in_article",
                            detail="Concrete article was fetched, but industry keyword was not located in article text.",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                extracted = extract_numeric_context(article_text, keywords=[industry])
                if not extracted:
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="FAILED",
                            issue="numeric_value_not_located_in_article_context",
                            detail="Industry keyword was found, but no numeric value appeared in the same paragraph or nearby context.",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                excerpt = extracted["excerpt"]
                task_evidence.append(
                    {
                        "date": publish_date,
                        "publish_date": publish_date,
                        "scope": "industry",
                        "industry": industry,
                        "code": "",
                        "stock_name": "",
                        "evidence_name": "政府或行业具体文章数据",
                        "indicator": "政府或行业具体文章数据",
                        "evidence_value": excerpt,
                        "value": extracted["value"],
                        "unit": extracted["unit"],
                        "comparison_period": publish_date,
                        "evidence_direction": direction_from_excerpt(excerpt),
                        "direction": direction_from_excerpt(excerpt),
                        "source": article_url,
                        "original_url": article_url,
                        "source_domain": source_domain(article_url),
                        "source_type": "OFFICIAL_REPORT",
                        "confidence": "MEDIUM",
                        "raw_excerpt": excerpt,
                        "normalized_summary": f"{article_title}：{excerpt}",
                        "title": article_title,
                        "parser": article_parser,
                        "collector": collector,
                        "parse_status": "OK",
                        "evidence_status": "VERIFIED",
                        "content_hash": content_hash(article_response.content),
                        "extraction_confidence": "MEDIUM",
                        "warning_flags": "",
                    }
                )
                article_evidence_found = True
                break

            if article_evidence_found:
                pass
            elif industry not in listing_text:
                task_audit.append(
                    _audit_row(
                        industry=industry,
                        collector=collector,
                        status="MISSING",
                        issue="industry_keyword_not_found",
                        detail=f"Fetched official page with {parser}, but industry keyword was not located.",
                        url=url,
                        title=title,
                    )
                )
            else:
                task_audit.append(
                    _audit_row(
                        industry=industry,
                        collector=collector,
                        status="MISSING",
                        issue="specific_article_not_found",
                        detail="Official listing page contains the industry keyword, but no concrete dated article with numeric context was verified.",
                        url=url,
                        title=title,
                    )
                )
            audit_rows.extend(task_audit)
            evidence_rows.extend(task_evidence)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})

    summary = {
        "industry_task_count": task_count,
        "industry_actual_fetch_count": network_fetches,
        "industry_fetch_success_count": fetch_successes,
        "industry_evidence_rows": len(evidence_rows),
        "industry_failure_count": sum(1 for row in audit_rows if row.get("status") == "FAILED"),
        "industry_missing_count": sum(1 for row in audit_rows if row.get("status") == "MISSING"),
    }
    return evidence_rows, audit_rows, summary
