"""Automatic evidence collection for GenGe opportunity discovery."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

import yaml

from . import company_announcements as _company_announcements
from .cache import EvidenceCache
from .company_announcements import collect_company_announcements, collect_company_material_events
from .company_extraction_status import install_company_extraction_status_adapter
from .public_data import collect_public_industry_data

_INDUSTRY_CLASSIFICATION_PREFIX_RE = re.compile(r"^[A-Z]\d{2}(?:\.\d+)?\s*")
_CNINFO_TOPSEARCH_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"
_ORIGINAL_QUERY_SSE = _company_announcements._query_sse
_ORIGINAL_QUERY_SSE_MATERIAL_EVENTS = _company_announcements._query_sse_material_events
_ORIGINAL_LOAD_CNINFO_ORG_IDS = _company_announcements._load_cninfo_org_ids
_ORIGINAL_CLASSIFY_MATERIAL_EVENTS = _company_announcements._classify_material_events

_FUNDS_OCCUPATION_PREVENTIVE_POLICY_RE = re.compile(
    r"(?:防范|预防|防止|规范).{0,48}(?:非经营性)?资金占用.{0,24}"
    r"(?:管理办法|管理制度|内部控制制度|制度|规定)"
    r"|(?:非经营性)?资金占用.{0,24}(?:管理办法|管理制度|内部控制制度)"
)
_FUNDS_OCCUPATION_TRUE_INCIDENT_RE = re.compile(
    r"(?:存在|发生|形成|新增|发现|涉及|违规).{0,18}(?:非经营性)?资金占用"
    r"|(?:非经营性)?资金占用(?:事项|问题|行为).{0,18}(?:整改|进展|归还|清偿|解决)"
    r"|占用(?:上市)?公司资金"
)


def normalize_sse_attachment_url(value: Any) -> str:
    """Return the direct static SSE attachment URL for disclosure files.

    The query API exposes paths such as ``/disclosure/...pdf``. Fetching those
    paths from ``www.sse.com.cn`` can return an HTML shell, which makes a real
    PDF look like ``html_text`` to the parser. SSE's disclosure attachment host
    is ``static.sse.com.cn``; only SSE disclosure URLs are rewritten.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        text = "https:" + text
    if text.startswith("/"):
        return "https://static.sse.com.cn" + text
    if "://" not in text and text.startswith("disclosure/"):
        return "https://static.sse.com.cn/" + text

    parsed = urlsplit(text)
    domain = parsed.netloc.lower()
    if domain in {"www.sse.com.cn", "static.sse.com.cn"} and parsed.path.startswith("/disclosure/"):
        return urlunsplit(("https", "static.sse.com.cn", parsed.path, parsed.query, parsed.fragment))
    return text


def _rewrite_sse_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        if row.get("url"):
            row["url"] = normalize_sse_attachment_url(row.get("url"))
        result.append(row)
    return result


def _query_sse_with_static_attachments(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    return _rewrite_sse_rows(_ORIGINAL_QUERY_SSE(*args, **kwargs))


def _query_sse_material_events_with_static_attachments(
    *args: Any, **kwargs: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, summary = _ORIGINAL_QUERY_SSE_MATERIAL_EVENTS(*args, **kwargs)
    return _rewrite_sse_rows(rows), summary


def is_preventive_funds_occupation_policy(title: Any) -> bool:
    """Return True only for policy/governance titles without an incident assertion.

    Preventive internal-control documents such as ``防范...资金占用管理办法``
    mention the risk vocabulary but do not establish that occupation occurred.
    A title with an explicit occurrence/violation/remediation assertion is never
    suppressed, even if it also mentions a management policy.
    """
    text = _company_announcements._clean_title(title)
    return bool(
        _FUNDS_OCCUPATION_PREVENTIVE_POLICY_RE.search(text)
        and not _FUNDS_OCCUPATION_TRUE_INCIDENT_RE.search(text)
    )


def _classify_material_events_with_policy_guard(
    title: Any, *, publish_date: date, as_of: date
) -> list[dict[str, Any]]:
    events = _ORIGINAL_CLASSIFY_MATERIAL_EVENTS(
        title, publish_date=publish_date, as_of=as_of
    )
    if not is_preventive_funds_occupation_policy(title):
        return events
    return [
        event
        for event in events
        if str(event.get("event_type") or "") != "FUNDS_OCCUPATION"
    ]


class _LazyCninfoOrgIdMap(dict[str, str]):
    """CNINFO orgId map that falls back to the official topSearch endpoint."""

    def __init__(self, initial: Mapping[str, str], session: Any, timeout: int):
        super().__init__(initial)
        self._session = session
        self._timeout = timeout
        self._attempted: set[str] = set()

    def get(self, key: Any, default: Any = None) -> Any:
        code = str(key or "").strip()
        existing = super().get(code)
        if existing or not re.fullmatch(r"\d{6}", code) or code in self._attempted:
            return existing or default
        self._attempted.add(code)
        try:
            response = self._session.post(
                _CNINFO_TOPSEARCH_URL,
                headers={
                    **_company_announcements.REQUEST_HEADERS,
                    "Referer": "https://www.cninfo.com.cn/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
                data={"keyWord": code, "maxNum": "10"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                for item in payload:
                    if str(item.get("code") or "") == code and str(item.get("orgId") or "").strip():
                        org_id = str(item["orgId"]).strip()
                        super().__setitem__(code, org_id)
                        return org_id
        except Exception:
            pass
        return default


def _load_cninfo_org_ids_with_topsearch_fallback(session: Any, timeout: int) -> _LazyCninfoOrgIdMap:
    try:
        initial = _ORIGINAL_LOAD_CNINFO_ORG_IDS(session, timeout)
    except Exception:
        initial = {}
    return _LazyCninfoOrgIdMap(initial, session, timeout)


# Keep the existing collectors and their pagination/risk rules intact; only fix
# provider adapters and false-positive policy classification at the module-global
# helpers those collectors call at runtime.
_company_announcements._query_sse = _query_sse_with_static_attachments
_company_announcements._query_sse_material_events = _query_sse_material_events_with_static_attachments
_company_announcements._load_cninfo_org_ids = _load_cninfo_org_ids_with_topsearch_fallback
_company_announcements._classify_material_events = _classify_material_events_with_policy_guard
collect_company_announcements = install_company_extraction_status_adapter(_company_announcements)


def canonical_industry_name(value: Any) -> str:
    text = str(value or "").strip()
    return _INDUSTRY_CLASSIFICATION_PREFIX_RE.sub("", text).strip()


def _default_industry_alias_map() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[4] / "config" / "industry_alias_map.yaml"
    if not path.is_file():
        return {"industries": {}}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(payload) if isinstance(payload, Mapping) else {"industries": {}}


def prepare_industry_alias_map(
    industries: list[str], alias_map: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Expand configured aliases for classified industry labels without renaming rows.

    Evidence rows retain the exact upstream industry string so downstream joins
    remain stable. Only search terms are augmented with the classification-free
    industry name and matching configured aliases.
    """
    source = dict(alias_map or _default_industry_alias_map())
    configured = source.get("industries") if isinstance(source.get("industries"), Mapping) else {}
    configured = {str(k): dict(v) for k, v in configured.items() if isinstance(v, Mapping)}
    expanded: dict[str, Any] = {**source, "industries": dict(configured)}

    for raw in [str(item or "").strip() for item in industries if str(item or "").strip()]:
        canonical = canonical_industry_name(raw)
        aliases: list[str] = []
        if canonical:
            aliases.append(canonical)
            if canonical.endswith("业") and len(canonical) > 2:
                aliases.append(canonical[:-1])

        direct = configured.get(raw) or configured.get(canonical) or {}
        aliases.extend(str(x or "").strip() for x in (direct.get("aliases") or []))

        for key, payload in configured.items():
            key_text = str(key or "").strip()
            configured_aliases = [str(x or "").strip() for x in (payload.get("aliases") or [])]
            if not canonical or not key_text:
                continue
            if (
                key_text in canonical
                or canonical in key_text
                or any(alias and alias in canonical for alias in configured_aliases)
            ):
                aliases.append(key_text)
                aliases.extend(configured_aliases)

        deduped = [
            value
            for value in dict.fromkeys(x for x in aliases if x and len(x) >= 2)
            if value != raw
        ]
        expanded["industries"][raw] = {"aliases": deduped}
    return expanded


def collect_auto_evidence(
    *,
    priority_rows: list[Mapping[str, Any]],
    as_of: date,
    cache_dir: str | Path,
    industry_alias_map: Mapping[str, Any] | None = None,
    max_companies: int = 50,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cache = EvidenceCache(cache_dir)
    targets = priority_rows[: max(0, int(max_companies))]
    company_evidence, company_audit, company_summary = collect_company_announcements(
        rows=targets,
        as_of=as_of,
        cache=cache,
        limit=max_companies,
        timeout=timeout,
    )
    event_evidence, event_audit, event_summary = collect_company_material_events(
        rows=targets,
        as_of=as_of,
        cache=cache,
        limit=max_companies,
        timeout=timeout,
    )
    company_evidence.extend(event_evidence)
    company_audit.extend(event_audit)
    industries = [str(row.get("normalized_industry") or row.get("industry") or "") for row in targets]
    effective_alias_map = prepare_industry_alias_map(industries, industry_alias_map)
    industry_evidence, industry_audit, industry_summary = collect_public_industry_data(
        industries=industries,
        as_of=as_of,
        cache=cache,
        industry_alias_map=effective_alias_map,
        timeout=timeout,
    )
    audit_rows = company_audit + industry_audit
    evidence_rows = company_evidence + industry_evidence
    verified = sum(1 for row in evidence_rows if str(row.get("evidence_status")).upper() == "VERIFIED")
    partial = sum(1 for row in evidence_rows if str(row.get("evidence_status")).upper() == "PARTIALLY_VERIFIED")
    failed = sum(1 for row in audit_rows if str(row.get("status")) == "FAILED")
    missing = sum(1 for row in audit_rows if str(row.get("status")) == "MISSING")
    task_count = (
        int(company_summary.get("company_task_count") or 0)
        + int(event_summary.get("company_event_task_count") or 0)
        + int(industry_summary.get("industry_task_count") or 0)
    )
    actual_fetch_count = (
        int(company_summary.get("company_actual_fetch_count") or 0)
        + int(event_summary.get("company_event_actual_fetch_count") or 0)
        + int(industry_summary.get("industry_actual_fetch_count") or 0)
    )
    fetch_success_count = (
        int(company_summary.get("company_fetch_success_count") or 0)
        + int(event_summary.get("company_event_document_fetch_success_count") or 0)
        + int(industry_summary.get("industry_fetch_success_count") or 0)
    )
    summary = {
        "enabled": True,
        "executed": True,
        "task_count": task_count,
        "actual_fetch_count": actual_fetch_count,
        "fetch_success_count": fetch_success_count,
        "verified_count": verified,
        "partially_verified_count": partial,
        "failed_count": failed,
        "missing_count": missing,
        "cache_hit_count": cache.cache_hits,
        "cache_miss_count": cache.cache_misses,
        "audit_count": len(audit_rows),
        "cache_dir": str(cache.cache_dir),
        "industry_alias_expansion_count": sum(
            bool((effective_alias_map.get("industries") or {}).get(industry, {}).get("aliases"))
            for industry in industries
        ),
        **company_summary,
        **event_summary,
        **industry_summary,
    }
    return industry_evidence, company_evidence, audit_rows, summary
