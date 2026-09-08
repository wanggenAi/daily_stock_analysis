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
from .public_data import collect_public_industry_data

_INDUSTRY_CLASSIFICATION_PREFIX_RE = re.compile(r"^[A-Z]\d{2}(?:\.\d+)?\s*")
_ORIGINAL_QUERY_SSE = _company_announcements._query_sse
_ORIGINAL_QUERY_SSE_MATERIAL_EVENTS = _company_announcements._query_sse_material_events


def normalize_sse_attachment_url(value: Any) -> str:
    """Return the direct static SSE attachment URL for disclosure files.

    The query API exposes paths such as ``/disclosure/...pdf``.  Fetching those
    paths from ``www.sse.com.cn`` can return an HTML shell, which makes a real
    PDF look like ``html_text`` to the parser.  SSE's disclosure attachment
    host is ``static.sse.com.cn``; only SSE disclosure URLs are rewritten.
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


# Keep the existing collectors and their pagination/risk rules intact; only fix
# the attachment host returned by the SSE query helpers they call at runtime.
_company_announcements._query_sse = _query_sse_with_static_attachments
_company_announcements._query_sse_material_events = _query_sse_material_events_with_static_attachments


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
    remain stable.  Only search terms are augmented with the classification-free
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
