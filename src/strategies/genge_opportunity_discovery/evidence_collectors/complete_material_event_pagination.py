"""Adaptive official-announcement pagination for material-event scans.

The base collector deliberately treats an incomplete official-announcement
window as UNKNOWN.  This module preserves that hard safety rule while avoiding
false UNKNOWN results caused only by a provider page cap: when a two-year query
hits the cap, the date range is recursively partitioned until every leaf window
is complete.  A query error or a still-truncated one-day window remains
incomplete and therefore continues to block a formal BUY.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Mapping

import requests

from . import company_announcements as base


MAX_PARTITION_QUERIES = 96
WindowQuery = Callable[[date, date], tuple[list[dict[str, Any]], dict[str, Any]]]


def _dedupe_announcements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("url") or "").strip()
        if not key:
            key = "|".join(
                [
                    str(row.get("publish_date") or ""),
                    str(row.get("title") or ""),
                    str(row.get("source_name") or ""),
                ]
            )
        by_key[key] = row
    return sorted(
        by_key.values(),
        key=lambda item: (
            str(item.get("publish_date") or ""),
            str(item.get("url") or ""),
        ),
        reverse=True,
    )


def _adaptive_partition_query(
    *,
    start_date: date,
    end_date: date,
    query_window: WindowQuery,
    max_queries: int = MAX_PARTITION_QUERIES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return complete date-partitioned metadata without ever hiding gaps."""

    pending: list[tuple[date, date]] = [(start_date, end_date)]
    collected: list[dict[str, Any]] = []
    pages_fetched = 0
    complete_reported_total = 0
    executed_queries = 0
    split_count = 0
    incomplete_reasons: list[str] = []

    while pending:
        window_start, window_end = pending.pop()
        if executed_queries >= max_queries:
            incomplete_reasons.append(
                f"partition_query_limit:{window_start.isoformat()}~{window_end.isoformat()}"
            )
            continue

        executed_queries += 1
        rows, meta = query_window(window_start, window_end)
        pages_fetched += int(meta.get("pages_fetched") or 0)
        query_error = str(meta.get("query_error") or "").strip()
        truncated = bool(meta.get("truncated"))

        if query_error:
            # Network/schema errors are genuine uncertainty.  Keep any rows we
            # did receive for auditability, but never relabel the window OK.
            collected.extend(rows)
            incomplete_reasons.append(
                f"query_error:{window_start.isoformat()}~{window_end.isoformat()}:{query_error}"
            )
            continue

        if truncated:
            if window_start >= window_end:
                # Even a one-day official filing window exceeded the provider
                # cap.  There is no safe way to infer completeness.
                collected.extend(rows)
                incomplete_reasons.append(
                    f"single_day_truncated:{window_start.isoformat()}"
                )
                continue
            midpoint = window_start + (window_end - window_start) // 2
            pending.append((midpoint + timedelta(days=1), window_end))
            pending.append((window_start, midpoint))
            split_count += 1
            continue

        collected.extend(rows)
        try:
            complete_reported_total += int(meta.get("reported_total") or 0)
        except (TypeError, ValueError):
            pass

    deduped = _dedupe_announcements(collected)
    return deduped, {
        "pages_fetched": pages_fetched,
        "reported_total": complete_reported_total,
        "query_error": ";".join(incomplete_reasons),
        "truncated": bool(incomplete_reasons),
        "partition_query_count": executed_queries,
        "partition_split_count": split_count,
        "pagination_strategy": "adaptive_date_partition_v1",
    }


def _query_cninfo_window(
    code: str,
    org_id: str,
    *,
    start_date: date,
    end_date: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    is_shanghai = code.startswith(("6", "9"))
    result: list[dict[str, Any]] = []
    reported_total = 0
    pages_fetched = 0
    last_page_count = 0
    query_error = ""

    for page in range(1, base.MATERIAL_EVENT_MAX_PAGES + 1):
        data = {
            "pageNum": str(page),
            "pageSize": str(base.MATERIAL_EVENT_PAGE_SIZE),
            "column": "sse" if is_shanghai else "szse",
            "tabName": "fulltext",
            "plate": "sh" if is_shanghai else "sz",
            "stock": f"{code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
            "sortName": "time",
            "sortType": "desc",
            "isHLtitle": "true",
        }
        try:
            response = session.post(
                "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                headers={**base.REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
                data=data,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("cninfo_material_event_response_not_object")
            if "announcements" not in payload or "totalAnnouncement" not in payload:
                raise ValueError("cninfo_material_event_response_schema_missing")
            page_total = int(payload.get("totalAnnouncement") or 0)
            if page_total < 0:
                raise ValueError("cninfo_material_event_total_invalid")
            raw_announcements = payload.get("announcements")
            if raw_announcements is None and page_total == 0:
                raw_announcements = []
            if not isinstance(raw_announcements, list):
                raise ValueError("cninfo_material_event_announcements_invalid")
            if raw_announcements and page_total == 0:
                raise ValueError("cninfo_material_event_total_inconsistent")
        except Exception as exc:
            if not pages_fetched:
                raise
            query_error = f"{type(exc).__name__}: {exc}"
            break

        announcements = raw_announcements
        last_page_count = len(announcements)
        pages_fetched += 1
        reported_total = max(reported_total, page_total)
        for item in announcements:
            title = base._clean_title(item.get("announcementTitle"))
            parsed_date = base._cninfo_publish_date(item.get("announcementTime"))
            adjunct = str(item.get("adjunctUrl") or "").strip()
            if (
                not title
                or "英文" in title
                or parsed_date is None
                or parsed_date < start_date
                or parsed_date > end_date
                or not adjunct
            ):
                continue
            result.append(
                {
                    "title": title,
                    "publish_date": parsed_date.isoformat(),
                    "url": f"https://static.cninfo.com.cn/{adjunct.lstrip('/')}",
                    "source_type": "EXCHANGE_DISCLOSURE",
                    "source_name": "cninfo",
                }
            )
        if len(announcements) < base.MATERIAL_EVENT_PAGE_SIZE:
            break
        if reported_total and page * base.MATERIAL_EVENT_PAGE_SIZE >= reported_total:
            break

    return _dedupe_announcements(result), {
        "pages_fetched": pages_fetched,
        "reported_total": reported_total,
        "query_error": query_error,
        "truncated": bool(
            query_error
            or (reported_total and reported_total > pages_fetched * base.MATERIAL_EVENT_PAGE_SIZE)
            or (
                pages_fetched == base.MATERIAL_EVENT_MAX_PAGES
                and last_page_count >= base.MATERIAL_EVENT_PAGE_SIZE
            )
        ),
    }


def _query_sse_window(
    code: str,
    *,
    start_date: date,
    end_date: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pages_fetched = 0
    reported_pages = 1
    query_error = ""

    for page in range(1, base.MATERIAL_EVENT_MAX_PAGES + 1):
        params = {
            "jsonCallBack": "",
            "isPagination": "true",
            "productId": code,
            "keyWord": "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType2": "",
            "pageHelp.pageSize": str(base.MATERIAL_EVENT_PAGE_SIZE),
            "pageHelp.pageNo": str(page),
            "pageHelp.beginPage": str(page),
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": str(page),
            "beginDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }
        try:
            response = session.get(
                "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
                params=params,
                headers={**base.REQUEST_HEADERS, "Referer": "https://www.sse.com.cn/"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping) or not isinstance(payload.get("pageHelp"), Mapping):
                raise ValueError("sse_material_event_response_schema_missing")
            page_help = payload["pageHelp"]
            if "data" not in page_help or "pageCount" not in page_help:
                raise ValueError("sse_material_event_page_schema_missing")
            raw_announcements = page_help.get("data")
            if raw_announcements is None:
                raw_announcements = []
            if not isinstance(raw_announcements, list):
                raise ValueError("sse_material_event_data_invalid")
            current_page_count = int(page_help.get("pageCount") or 0)
            if current_page_count < 0:
                raise ValueError("sse_material_event_page_count_invalid")
            if raw_announcements and current_page_count == 0:
                raise ValueError("sse_material_event_page_count_inconsistent")
        except Exception as exc:
            if not pages_fetched:
                raise
            query_error = f"{type(exc).__name__}: {exc}"
            break

        announcements = raw_announcements
        pages_fetched += 1
        reported_pages = max(reported_pages, current_page_count or 1)
        for item in announcements:
            title = base._clean_title(item.get("TITLE"))
            try:
                parsed_date = date.fromisoformat(str(item.get("SSEDATE") or "")[:10])
            except ValueError:
                continue
            url = str(item.get("URL") or "").strip()
            if not title or parsed_date < start_date or parsed_date > end_date or not url:
                continue
            result.append(
                {
                    "title": title,
                    "publish_date": parsed_date.isoformat(),
                    "url": url if url.startswith(("http://", "https://")) else f"https://www.sse.com.cn{url}",
                    "source_type": "EXCHANGE_DISCLOSURE",
                    "source_name": "sse",
                }
            )
        if not announcements or page >= reported_pages:
            break

    return _dedupe_announcements(result), {
        "pages_fetched": pages_fetched,
        "reported_total": "",
        "query_error": query_error,
        "truncated": bool(query_error or reported_pages > base.MATERIAL_EVENT_MAX_PAGES),
    }


def query_cninfo_material_events_complete(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start_date = as_of - timedelta(days=base.MATERIAL_EVENT_WINDOW_DAYS)
    return _adaptive_partition_query(
        start_date=start_date,
        end_date=as_of,
        query_window=lambda start, end: _query_cninfo_window(
            code,
            org_id,
            start_date=start,
            end_date=end,
            session=session,
            timeout=timeout,
        ),
    )


def query_sse_material_events_complete(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start_date = as_of - timedelta(days=base.MATERIAL_EVENT_WINDOW_DAYS)
    return _adaptive_partition_query(
        start_date=start_date,
        end_date=as_of,
        query_window=lambda start, end: _query_sse_window(
            code,
            start_date=start,
            end_date=end,
            session=session,
            timeout=timeout,
        ),
    )


def install() -> None:
    """Install complete pagination while keeping the base event hard gate intact."""

    base._query_cninfo_material_events = query_cninfo_material_events_complete
    base._query_sse_material_events = query_sse_material_events_complete
