"""Automatic evidence collection for GenGe opportunity discovery."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .cache import EvidenceCache
from .company_announcements import collect_company_announcements
from .public_data import collect_public_industry_data


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
    industries = [str(row.get("normalized_industry") or row.get("industry") or "") for row in targets]
    industry_evidence, industry_audit, industry_summary = collect_public_industry_data(
        industries=industries,
        as_of=as_of,
        cache=cache,
        industry_alias_map=industry_alias_map,
        timeout=timeout,
    )
    audit_rows = company_audit + industry_audit
    evidence_rows = company_evidence + industry_evidence
    verified = sum(1 for row in evidence_rows if str(row.get("evidence_status")).upper() == "VERIFIED")
    partial = sum(1 for row in evidence_rows if str(row.get("evidence_status")).upper() == "PARTIALLY_VERIFIED")
    failed = sum(1 for row in audit_rows if str(row.get("status")) == "FAILED")
    missing = sum(1 for row in audit_rows if str(row.get("status")) == "MISSING")
    task_count = int(company_summary.get("company_task_count") or 0) + int(industry_summary.get("industry_task_count") or 0)
    actual_fetch_count = int(company_summary.get("company_actual_fetch_count") or 0) + int(industry_summary.get("industry_actual_fetch_count") or 0)
    fetch_success_count = int(company_summary.get("company_fetch_success_count") or 0) + int(industry_summary.get("industry_fetch_success_count") or 0)
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
        **company_summary,
        **industry_summary,
    }
    return industry_evidence, company_evidence, audit_rows, summary
