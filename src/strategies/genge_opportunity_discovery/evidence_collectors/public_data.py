"""Government or industry public-data collector."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import requests

from .cache import EvidenceCache
from .validators import content_hash, direction_from_excerpt, extract_numeric_context, extract_text_from_response, source_domain, utc_now


PUBLIC_SOURCES = [
    ("miit_public_data", "https://www.miit.gov.cn/gxsj/index.html", "工业和信息化部公开数据"),
    ("ndrc_public_data", "https://www.ndrc.gov.cn/fgsj/", "国家发展改革委公开数据"),
]


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
            key = cache.key_for({"collector": collector, "industry": industry, "as_of": as_of.isoformat(), "version": 1})
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
                text, parser = extract_text_from_response(response.content, response.headers.get("content-type", ""))
                if text:
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

            if industry not in text:
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
                extracted = extract_numeric_context(text, keywords=[industry])
                if extracted:
                    excerpt = extracted["excerpt"]
                    task_evidence.append(
                        {
                            "date": as_of.isoformat(),
                            "publish_date": as_of.isoformat(),
                            "scope": "industry",
                            "industry": industry,
                            "code": "",
                            "stock_name": "",
                            "evidence_name": "政府或行业公开数据",
                            "indicator": "政府或行业公开数据",
                            "evidence_value": excerpt,
                            "value": extracted["value"],
                            "unit": extracted["unit"],
                            "comparison_period": as_of.isoformat(),
                            "evidence_direction": direction_from_excerpt(excerpt),
                            "direction": direction_from_excerpt(excerpt),
                            "source": url,
                            "original_url": url,
                            "source_domain": source_domain(url),
                            "source_type": "OFFICIAL_REPORT",
                            "confidence": "MEDIUM",
                            "raw_excerpt": excerpt,
                            "normalized_summary": f"{title}：{excerpt}",
                            "title": title,
                            "parser": collector,
                            "collector": collector,
                            "parse_status": "OK",
                            "evidence_status": "VERIFIED",
                            "content_hash": content_hash(response.content),
                            "extraction_confidence": "MEDIUM",
                            "warning_flags": "",
                        }
                    )
                else:
                    task_audit.append(
                        _audit_row(
                            industry=industry,
                            collector=collector,
                            status="FAILED",
                            issue="numeric_value_not_located_in_original",
                            detail=f"Industry keyword found, but no numeric value was located in the fetched official page.",
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
