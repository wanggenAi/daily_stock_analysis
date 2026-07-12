"""Company announcement collectors for official exchange/public filings."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Mapping

import requests

from .cache import EvidenceCache
from .validators import content_hash, direction_from_excerpt, extract_numeric_context, extract_text_from_response, source_domain, utc_now


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
CNINFO_STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _clean_title(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _load_cninfo_org_ids(session: requests.Session, timeout: int) -> dict[str, str]:
    response = session.get(
        CNINFO_STOCK_LIST_URL,
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        timeout=timeout,
    )
    response.raise_for_status()
    stock_list = response.json().get("stockList") or []
    return {
        _normalize_code(item.get("code")): str(item.get("orgId") or "").strip()
        for item in stock_list
        if _normalize_code(item.get("code")) and str(item.get("orgId") or "").strip()
    }


def _query_cninfo(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> list[dict[str, Any]]:
    start = (as_of - timedelta(days=560)).isoformat()
    end = as_of.isoformat()
    data = {
        "pageNum": "1",
        "pageSize": "5",
        "column": "szse",
        "tabName": "fulltext",
        "plate": "sz",
        "stock": f"{code},{org_id}",
        "searchkey": "年度报告",
        "secid": "",
        "category": "category_ndbg_szsh",
        "trade": "",
        "seDate": f"{start}~{end}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = session.post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        data=data,
        timeout=timeout,
    )
    response.raise_for_status()
    announcements = (response.json().get("announcements") or [])
    result: list[dict[str, Any]] = []
    for item in announcements:
        title = _clean_title(item.get("announcementTitle"))
        if "英文" in title:
            continue
        adjunct = str(item.get("adjunctUrl") or "")
        if not adjunct:
            continue
        publish_date = date.fromtimestamp(int(item.get("announcementTime") or 0) / 1000).isoformat()
        result.append(
            {
                "title": title,
                "publish_date": publish_date,
                "url": f"https://static.cninfo.com.cn/{adjunct}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "cninfo",
            }
        )
    return sorted(
        result,
        key=lambda item: (str(item.get("publish_date") or ""), "摘要" not in str(item.get("title") or "")),
        reverse=True,
    )


def _query_sse(code: str, as_of: date, session: requests.Session, timeout: int) -> list[dict[str, Any]]:
    params = {
        "jsonCallBack": "",
        "isPagination": "true",
        "productId": code,
        "keyWord": "年度报告",
        "securityType": "0101,120100,020100,020200,120200",
        "reportType2": "DQBG",
        "pageHelp.pageSize": "5",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
    }
    response = session.get(
        "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
        params=params,
        headers={**REQUEST_HEADERS, "Referer": "https://www.sse.com.cn/"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json().get("pageHelp", {}).get("data") or []
    result: list[dict[str, Any]] = []
    for item in data:
        publish_date = str(item.get("SSEDATE") or "")[:10]
        if publish_date and publish_date > as_of.isoformat():
            continue
        url = str(item.get("URL") or "")
        if not url:
            continue
        result.append(
            {
                "title": _clean_title(item.get("TITLE")),
                "publish_date": publish_date,
                "url": f"https://www.sse.com.cn{url}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "sse",
            }
        )
    return result


def _announcement_candidates(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
    cninfo_org_ids: Mapping[str, str],
) -> list[dict[str, Any]]:
    if code.startswith(("0", "2", "3")):
        org_id = str(cninfo_org_ids.get(code) or "").strip()
        if not org_id:
            raise RuntimeError(f"cninfo_org_id_missing:{code}")
        return _query_cninfo(code, org_id, as_of, session, timeout)
    if code.startswith("6"):
        return _query_sse(code, as_of, session, timeout)
    return []


def _audit_row(
    *,
    code: str,
    stock_name: Any,
    industry: Any,
    collector: str,
    status: str,
    issue: str,
    detail: str,
    url: str = "",
    title: str = "",
    cache_hit: bool = False,
) -> dict[str, Any]:
    return {
        "scope": "company",
        "code": code,
        "stock_name": stock_name or "",
        "industry": industry or "",
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


def collect_company_announcements(
    *,
    rows: list[Mapping[str, Any]],
    as_of: date,
    cache: EvidenceCache,
    limit: int = 50,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    session = requests.Session()
    evidence_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    network_fetches = 0
    fetch_successes = 0
    task_count = 0
    cninfo_org_ids: dict[str, str] = {}
    if any(_normalize_code(row.get("code")).startswith(("0", "2", "3")) for row in rows[: max(0, int(limit))]):
        try:
            cninfo_org_ids = _load_cninfo_org_ids(session, timeout)
            network_fetches += 1
        except Exception:
            cninfo_org_ids = {}

    for row in rows[: max(0, int(limit))]:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        task_count += 1
        collector = "cninfo_company_announcement" if code.startswith(("0", "2", "3")) else "sse_company_announcement"
        report_period = str(as_of.year - 1)
        key = cache.key_for(
            {
                "collector": collector,
                "code": code,
                "announcement_type": "annual_report",
                "report_period": report_period,
                "version": 3,
            }
        )
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
            announcements = _announcement_candidates(code, as_of, session, timeout, cninfo_org_ids)
            network_fetches += 1
        except Exception as exc:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="announcement_query_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        if not announcements:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="MISSING",
                    issue="announcement_not_found",
                    detail="No annual-report announcement found on the official disclosure endpoint.",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        item = announcements[0]
        url = str(item.get("url") or "")
        try:
            response = session.get(url, headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"}, timeout=timeout)
            network_fetches += 1
            response.raise_for_status()
            text, parser = extract_text_from_response(response.content, response.headers.get("content-type", ""))
        except Exception as exc:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="announcement_fetch_or_parse_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                    url=url,
                    title=item.get("title") or "",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        if text:
            fetch_successes += 1
        extracted = extract_numeric_context(
            text,
            keywords=["营业收入", "净利润", "现金流", "revenue", "profit", "cash flow", "operating revenue"],
        )
        raw_hash = content_hash(response.content)
        if not extracted:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="numeric_value_not_located_in_original",
                    detail=f"Original fetched and parsed by {parser}, but no numeric context matched required keywords.",
                    url=url,
                    title=item.get("title") or "",
                )
            )
        else:
            excerpt = extracted["excerpt"]
            task_evidence.append(
                {
                    "date": item.get("publish_date") or as_of.isoformat(),
                    "publish_date": item.get("publish_date") or as_of.isoformat(),
                    "scope": "company",
                    "code": code,
                    "stock_name": row.get("stock_name") or "",
                    "industry": row.get("normalized_industry") or "",
                    "evidence_name": "定期报告原文数值",
                    "indicator": "定期报告原文数值",
                    "evidence_value": excerpt,
                    "value": extracted["value"],
                    "unit": extracted["unit"],
                    "comparison_period": item.get("publish_date") or "",
                    "evidence_direction": direction_from_excerpt(excerpt),
                    "direction": direction_from_excerpt(excerpt),
                    "source": url,
                    "original_url": url,
                    "source_domain": source_domain(url),
                    "source_type": item.get("source_type") or "EXCHANGE_DISCLOSURE",
                    "confidence": "HIGH",
                    "raw_excerpt": excerpt,
                    "normalized_summary": f"{item.get('title')}：{excerpt}",
                    "title": item.get("title") or "",
                    "parser": collector,
                    "collector": collector,
                    "parse_status": "OK",
                    "evidence_status": "VERIFIED",
                    "content_hash": raw_hash,
                    "extraction_confidence": "HIGH",
                    "warning_flags": "",
                }
            )
        audit_rows.extend(task_audit)
        evidence_rows.extend(task_evidence)
        cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})

    summary = {
        "company_task_count": task_count,
        "company_actual_fetch_count": network_fetches,
        "company_fetch_success_count": fetch_successes,
        "company_evidence_rows": len(evidence_rows),
        "company_failure_count": sum(1 for row in audit_rows if row.get("status") == "FAILED"),
        "company_missing_count": sum(1 for row in audit_rows if row.get("status") == "MISSING"),
    }
    return evidence_rows, audit_rows, summary
