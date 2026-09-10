"""Strict multi-year official-report evidence for the V3.1 predictability gate.

The collector is deliberately fail-closed.  It can prove PASS only for a
non-cyclical/non-resource company with at least three consecutive fiscal years
of complete, positive and reasonably stable revenue, attributable net profit
and operating cash flow extracted from official CNINFO annual reports.

Cyclical/resource companies never receive PASS from accounting history alone:
they require a separate rule proving cycle resilience (commodity-price/cost
sensitivity, operating stability and earnings/cash-flow resilience).  Until
that exists the result remains UNKNOWN.  This module is research-only.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

import requests

from .company_announcements import (
    REQUEST_HEADERS,
    _clean_title,
    _cninfo_publish_date,
    _load_cninfo_org_ids,
)
from .validators import content_hash, extract_text_from_response, source_domain, utc_now

RULE_VERSION = "PREDICTABILITY_MULTI_YEAR_OFFICIAL_V1"
HISTORY_DAYS = 2200
MAX_REPORTS = 5
MIN_COMPLETE_YEARS = 3

_RESOURCE_TOKENS = (
    "有色", "金属", "矿", "煤", "石油", "石化", "油气", "钢铁", "能源",
    "基础化工", "化工原料", "黄金", "铜", "铝", "锂", "钴", "镍", "稀土",
)
_RESOURCE_REPORT_PATTERNS = (
    re.compile(r"矿山|矿产资源|采矿|选矿"),
    re.compile(r"铜矿|金矿|钼矿|锂矿|镍矿|钴矿|铁矿"),
    re.compile(r"原油|天然气|煤炭开采"),
)
_FISCAL_YEAR_RE = re.compile(r"(20\d{2})年(?:年度报告|年报)")
_NUMBER_RE = re.compile(r"(?<!\d)([-−]?(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?)(?!\d)")
_METRIC_LABELS: Mapping[str, tuple[str, ...]] = {
    "revenue": ("营业收入",),
    "net_profit": ("归属于上市公司股东的净利润", "归属于母公司股东的净利润"),
    "operating_cash_flow": ("经营活动产生的现金流量净额",),
}


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _fiscal_year(title: Any) -> int | None:
    match = _FISCAL_YEAR_RE.search(str(title or ""))
    return int(match.group(1)) if match else None


def _query_cninfo_history(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> list[dict[str, Any]]:
    """Fetch up to ~6 years of full annual-report metadata from CNINFO."""
    start = (as_of - timedelta(days=HISTORY_DAYS)).isoformat()
    is_shanghai = code.startswith(("6", "9"))
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "sse" if is_shanghai else "szse",
        "tabName": "fulltext",
        "plate": "sh" if is_shanghai else "sz",
        "stock": f"{code},{org_id}",
        "searchkey": "年度报告",
        "secid": "",
        "category": "category_ndbg_szsh",
        "trade": "",
        "seDate": f"{start}~{as_of.isoformat()}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = session.post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        data=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    by_year: dict[int, dict[str, Any]] = {}
    for item in response.json().get("announcements") or []:
        title = _clean_title(item.get("announcementTitle"))
        if "摘要" in title or "英文" in title or "取消" in title:
            continue
        year = _fiscal_year(title)
        adjunct = str(item.get("adjunctUrl") or "").strip()
        published = _cninfo_publish_date(item.get("announcementTime"))
        if year is None or not adjunct or published is None or published > as_of:
            continue
        candidate = {
            "fiscal_year": year,
            "title": title,
            "publish_date": published.isoformat(),
            "url": f"https://static.cninfo.com.cn/{adjunct}",
        }
        previous = by_year.get(year)
        if previous is None or candidate["publish_date"] > previous["publish_date"]:
            by_year[year] = candidate
    return [by_year[year] for year in sorted(by_year, reverse=True)[:MAX_REPORTS]]


def _metric_value(text: str, labels: Iterable[str]) -> float | None:
    """Extract only an unambiguous first current-period value near an exact label."""
    normalized = str(text or "").replace("−", "-")
    for label in labels:
        start = normalized.find(label)
        if start < 0:
            continue
        # Annual-report key-data tables put the current-period value immediately
        # after the metric label.  Keep the window tight to avoid silently taking
        # a comparison-period value from elsewhere in the document.
        window = normalized[start + len(label): start + len(label) + 260]
        for match in _NUMBER_RE.finditer(window):
            token = match.group(1).replace(",", "")
            try:
                value = float(token)
            except ValueError:
                continue
            # A PDF layout can inject a year heading between a label and values.
            if value.is_integer() and 2000 <= abs(value) <= 2100:
                continue
            return value
    return None


def extract_report_metrics(text: str, fiscal_year: int) -> dict[str, Any]:
    return {
        "fiscal_year": int(fiscal_year),
        **{name: _metric_value(text, labels) for name, labels in _METRIC_LABELS.items()},
    }


def _consecutive_years(records: list[Mapping[str, Any]]) -> bool:
    years = sorted({int(row["fiscal_year"]) for row in records})
    return len(years) >= MIN_COMPLETE_YEARS and all(b - a == 1 for a, b in zip(years, years[1:]))


def _yoy_floor(values: list[float], floor: float) -> bool:
    for previous, current in zip(values, values[1:]):
        if previous <= 0 or current <= 0:
            return False
        if current / previous - 1.0 < floor:
            return False
    return True


def classify_multi_year_metrics(
    records: Iterable[Mapping[str, Any]], *, cyclical_or_resource: bool
) -> tuple[str, str]:
    """Return PASS/UNKNOWN under a conservative deterministic accounting rule."""
    complete = [
        dict(row)
        for row in records
        if row.get("fiscal_year") is not None
        and all(row.get(key) is not None for key in ("revenue", "net_profit", "operating_cash_flow"))
    ]
    complete.sort(key=lambda row: int(row["fiscal_year"]))
    if len(complete) < MIN_COMPLETE_YEARS or not _consecutive_years(complete):
        return "UNKNOWN", "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"

    if cyclical_or_resource:
        return "UNKNOWN", "CYCLICAL_RESOURCE_REQUIRES_EXPLICIT_CYCLE_RESILIENCE_EVIDENCE"

    revenue = [float(row["revenue"]) for row in complete]
    profit = [float(row["net_profit"]) for row in complete]
    cash_flow = [float(row["operating_cash_flow"]) for row in complete]
    if any(value <= 0 for value in revenue + profit + cash_flow):
        return "UNKNOWN", "MULTI_YEAR_POSITIVITY_NOT_PROVEN"

    # Fail-closed stability thresholds: a single severe contraction prevents a
    # positive predictability proof.  They are not used to manufacture FAIL.
    if not _yoy_floor(revenue, -0.20):
        return "UNKNOWN", "REVENUE_STABILITY_THRESHOLD_NOT_MET"
    if not _yoy_floor(profit, -0.50):
        return "UNKNOWN", "EARNINGS_STABILITY_THRESHOLD_NOT_MET"
    if not _yoy_floor(cash_flow, -0.50):
        return "UNKNOWN", "OPERATING_CASH_FLOW_STABILITY_THRESHOLD_NOT_MET"
    if max(profit) / min(profit) > 5.0 or max(cash_flow) / min(cash_flow) > 5.0:
        return "UNKNOWN", "MULTI_YEAR_VOLATILITY_THRESHOLD_NOT_MET"
    return "PASS", "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN"


def _is_cyclical_or_resource(industry: Any, reports_text: Iterable[str]) -> bool:
    industry_text = str(industry or "")
    if any(token in industry_text for token in _RESOURCE_TOKENS):
        return True
    sample = "\n".join(str(text or "")[:12000] for text in reports_text)
    return any(pattern.search(sample) for pattern in _RESOURCE_REPORT_PATTERNS)


def _unknown_row(code: str, industry: str, reason: str) -> dict[str, Any]:
    payload = {"code": code, "industry": industry, "reason": reason, "rule": RULE_VERSION}
    return {
        "code": code,
        "industry": industry,
        "evidence_kind": "multi_year_predictability",
        "indicator": "predictability_multi_year_official",
        "predictability_classification": "UNKNOWN",
        "reason_code": reason,
        "rule_version": RULE_VERSION,
        "coverage_years": [],
        "metrics_by_year": [],
        "evidence_status": "OBSERVED_CONTEXT",
        "source_type": "OFFICIAL_REPORT",
        "source_domain": "cninfo.com.cn",
        "publish_date": "",
        "original_url": "",
        "normalized_summary": reason,
        "content_hash": content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        "authority_crossed": False,
        "formal_decision": False,
        "adopted_for_gate": False,
        "collected_at": utc_now(),
    }


def collect_multi_year_predictability_evidence(
    *,
    priority_rows: Iterable[Mapping[str, Any]],
    as_of: date,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Collect one strict multi-year predictability evidence row per company."""
    selected = [dict(row) for row in priority_rows if _code(row.get("code"))]
    if not selected:
        return []

    session = requests.Session()
    try:
        org_ids = _load_cninfo_org_ids(session, timeout)
    except Exception as exc:
        reason = f"CNINFO_ORG_ID_FETCH_FAILED:{type(exc).__name__}"
        return [
            _unknown_row(
                _code(row.get("code")),
                str(row.get("normalized_industry") or row.get("industry") or ""),
                reason,
            )
            for row in selected
        ]

    results: list[dict[str, Any]] = []
    for row in selected:
        code = _code(row.get("code"))
        industry = str(row.get("normalized_industry") or row.get("industry") or "")
        org_id = org_ids.get(code)
        if not org_id:
            results.append(_unknown_row(code, industry, "CNINFO_ORG_ID_NOT_FOUND"))
            continue
        try:
            candidates = _query_cninfo_history(code, org_id, as_of, session, timeout)
        except Exception as exc:
            results.append(_unknown_row(code, industry, f"ANNUAL_REPORT_QUERY_FAILED:{type(exc).__name__}"))
            continue

        metrics: list[dict[str, Any]] = []
        source_rows: list[dict[str, Any]] = []
        report_texts: list[str] = []
        for candidate in candidates:
            try:
                response = session.get(
                    candidate["url"], headers=REQUEST_HEADERS, timeout=timeout
                )
                response.raise_for_status()
                text, extraction_method = extract_text_from_response(
                    response.content, response.headers.get("Content-Type", "")
                )
            except Exception:
                continue
            if not text.strip():
                continue
            parsed = extract_report_metrics(text, int(candidate["fiscal_year"]))
            metrics.append(parsed)
            report_texts.append(text)
            source_rows.append({**candidate, "extraction_method": extraction_method})

        cyclical = _is_cyclical_or_resource(industry, report_texts)
        classification, reason = classify_multi_year_metrics(
            metrics, cyclical_or_resource=cyclical
        )
        coverage_years = sorted(
            int(item["fiscal_year"])
            for item in metrics
            if all(item.get(key) is not None for key in ("revenue", "net_profit", "operating_cash_flow"))
        )
        latest = max(source_rows, key=lambda item: item["publish_date"], default={})
        digest_payload = {
            "code": code,
            "rule": RULE_VERSION,
            "classification": classification,
            "reason": reason,
            "metrics": metrics,
            "sources": [item.get("url") for item in source_rows],
        }
        results.append({
            "code": code,
            "industry": industry,
            "evidence_kind": "multi_year_predictability",
            "indicator": "predictability_multi_year_official",
            "predictability_classification": classification,
            "reason_code": reason,
            "rule_version": RULE_VERSION,
            "coverage_years": coverage_years,
            "coverage_count": len(coverage_years),
            "metrics_by_year": metrics,
            "cyclical_or_resource": cyclical,
            "source_urls": [item.get("url") for item in source_rows],
            "evidence_status": "VERIFIED" if classification in {"PASS", "FAIL"} else "OBSERVED_CONTEXT",
            "source_type": "OFFICIAL_REPORT",
            "source_domain": source_domain(latest.get("url") or "https://www.cninfo.com.cn/"),
            "publish_date": latest.get("publish_date") or "",
            "original_url": latest.get("url") or "",
            "normalized_summary": f"{classification}:{reason}; years={coverage_years}",
            "content_hash": content_hash(json.dumps(digest_payload, ensure_ascii=False, sort_keys=True)),
            "authority_crossed": False,
            "formal_decision": False,
            "adopted_for_gate": classification in {"PASS", "FAIL"},
            "collected_at": utc_now(),
        })
    return results
