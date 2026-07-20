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
SPECIALIZED_PUBLIC_SOURCES = {
    "物流": [
        (
            "spb_public_data",
            "https://www.spb.gov.cn/common/search/a630715264f14e0aafa4ab2a945fd6da"
            "?_isAgg=true&_isJson=true&_pageSize=100&_template=index"
            "&_rangeTimeGte=&_channelName=&page=1",
            "国家邮政局行业要闻",
        )
    ],
}
SPB_OPERATIONAL_TITLE_TOKENS = ("行业运行情况", "行业发展情况", "业务量")


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


def _industry_search_terms(industry: str, alias_map: Mapping[str, Any] | None) -> list[str]:
    if industry.strip().lower() in {"", "unresolved", "unknown", "未知行业"}:
        return []
    config = ((alias_map or {}).get("industries") or {}).get(industry) or {}
    values = [industry, *((config or {}).get("aliases") or [])]
    return [
        value
        for value in dict.fromkeys(str(item or "").strip() for item in values)
        if len(value) >= 2
    ]


def _article_candidates(
    html: str, *, base_url: str, keywords: list[str], limit: int = 5,
) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a"):
        title = anchor.get_text(" ", strip=True)
        href = str(anchor.get("href") or "").strip()
        if not title or not href:
            continue
        matched_keyword = next((keyword for keyword in keywords if keyword in title), "")
        if not matched_keyword:
            continue
        url = urljoin(base_url, href)
        if source_domain(url) != source_domain(base_url) or url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append((title, url, matched_keyword))
        if len(candidates) >= limit:
            break
    return candidates


def _json_article_candidates(
    payload: Mapping[str, Any], *, base_url: str, keywords: list[str], limit: int = 5,
) -> tuple[str, list[tuple[str, str, str]]]:
    results = ((payload.get("data") or {}).get("results") or [])
    titles: list[str] = []
    candidates: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    for item in results:
        title = str(item.get("title") or "").strip()
        href = str(item.get("url") or "").strip()
        if title:
            titles.append(title)
        matched_keyword = next((keyword for keyword in keywords if keyword in title), "")
        operational_title = next((token for token in SPB_OPERATIONAL_TITLE_TOKENS if token in title), "")
        if not href or not operational_title:
            continue
        matched_keyword = matched_keyword or operational_title
        url = urljoin(base_url, href)
        if url.startswith("http://www.spb.gov.cn/"):
            url = "https://www.spb.gov.cn/" + url.split("http://www.spb.gov.cn/", 1)[1]
        if source_domain(url) != source_domain(base_url) or url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append((title, url, matched_keyword))
        if len(candidates) >= limit:
            break
    return "\n".join(titles), candidates


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
    industry_alias_map: Mapping[str, Any] | None = None,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    session = requests.Session()
    evidence_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    network_fetches = 0
    fetch_successes = 0
    task_count = 0

    for industry in [item for item in dict.fromkeys(industries) if item]:
        search_terms = _industry_search_terms(industry, industry_alias_map)
        if not search_terms:
            continue
        source_specs = [*PUBLIC_SOURCES, *SPECIALIZED_PUBLIC_SOURCES.get(industry, [])]
        for collector, url, title in source_specs:
            task_count += 1
            key = cache.key_for({
                "collector": collector,
                "industry": industry,
                "search_terms": search_terms,
                "source": url,
                "version": 3,
            })
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
                if collector == "spb_public_data":
                    listing_text, article_attempts = _json_article_candidates(
                        response.json(), base_url=url, keywords=search_terms,
                    )
                    listing_html = ""
                    parser = "json_search"
                else:
                    listing_text, parser = extract_text_from_response(
                        response.content, response.headers.get("content-type", ""),
                    )
                    listing_html = response.content.decode("utf-8", errors="ignore")
                    article_attempts = _article_candidates(
                        listing_html, base_url=url, keywords=search_terms,
                    )
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
            for article_title, article_url, matched_keyword in article_attempts:
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
                if not any(keyword in article_text for keyword in search_terms):
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="MISSING",
                            issue="industry_keyword_not_found_in_article",
                            detail="Concrete article was fetched, but no canonical industry or configured alias was located in article text.",
                            url=article_url,
                            title=article_title,
                        )
                    )
                    continue
                extracted = extract_numeric_context(article_text, keywords=search_terms)
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
                        "normalized_summary": f"{article_title}（匹配词：{matched_keyword}）：{excerpt}",
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
            elif not any(keyword in listing_text for keyword in search_terms):
                task_audit.append(
                    _audit_row(
                        industry=industry,
                        collector=collector,
                        status="MISSING",
                        issue="industry_keyword_not_found",
                        detail=f"Fetched official page with {parser}, but no canonical industry or configured alias was located.",
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
