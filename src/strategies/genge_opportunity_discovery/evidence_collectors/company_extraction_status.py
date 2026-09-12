"""Typed extraction-status adapter for the legacy company announcement collector.

The collector predates the robust evidence-normalization contract and exposes a
coarse ``OK/FAILED/MISSING`` audit surface.  This adapter keeps that schema for
backward compatibility while preserving the finer extraction truth required by
research closure: source absence, fetch failure, parse failure, structure
recovery failure, ambiguity, recovery and verification are distinct states.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Mapping

from .evidence_normalization import (
    AMBIGUOUS_MATCH,
    PARSE_FAILED,
    SOURCE_DATA_ABSENT,
    SOURCE_FETCH_FAILED,
    STRUCTURE_RECOVERY_FAILED,
    VALUE_RECOVERED,
    VALUE_STATUSES,
    VALUE_VERIFIED,
)
from .validators import extract_numeric_context_detailed

_TYPED_CACHE_VERSION = 5
_EXTRACTION_META: ContextVar[dict[str, Any]] = ContextVar(
    "company_announcement_extraction_meta", default={}
)
_EXTRACTION_BY_FINGERPRINT: ContextVar[dict[tuple[str, str, str], dict[str, Any]]] = ContextVar(
    "company_announcement_extraction_by_fingerprint", default={}
)


class _TypedEvidenceCacheProxy:
    """Force one-time re-extraction after the parser contract changes."""

    def __init__(self, delegate: Any):
        self._delegate = delegate

    def key_for(self, payload: Mapping[str, Any]) -> str:
        normalized = dict(payload)
        if normalized.get("announcement_type") == "annual_report":
            normalized["version"] = _TYPED_CACHE_VERSION
            normalized["evidence_extraction_contract"] = "robust_typed_v1"
        return self._delegate.key_for(normalized)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _fingerprint(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("raw_excerpt") or row.get("excerpt") or ""),
        str(row.get("value") or ""),
        str(row.get("unit") or ""),
    )


def _typed_numeric_extractor(text: str, keywords: list[str] | None = None) -> dict[str, str]:
    detail = extract_numeric_context_detailed(text, keywords)
    _EXTRACTION_META.set(dict(detail))
    if detail.get("status") not in VALUE_STATUSES:
        return {}

    result = {
        "value": str(detail.get("number_text") or detail.get("raw_value") or "").replace(",", ""),
        "unit": str(detail.get("unit") or ""),
        "excerpt": str(detail.get("excerpt") or "")[:500],
    }
    by_fingerprint = dict(_EXTRACTION_BY_FINGERPRINT.get())
    by_fingerprint[_fingerprint(result)] = dict(detail)
    _EXTRACTION_BY_FINGERPRINT.set(by_fingerprint)
    return result


def _typed_audit_row_factory(original_audit_row: Any):
    def _typed_audit_row(**kwargs: Any) -> dict[str, Any]:
        row = original_audit_row(**kwargs)
        issue = str(kwargs.get("issue") or "")
        extraction_status = ""
        extraction_reason = ""
        extraction_method = ""

        if issue == "announcement_query_failed":
            extraction_status = SOURCE_FETCH_FAILED
            extraction_reason = "OFFICIAL_ANNOUNCEMENT_QUERY_FAILED"
        elif issue == "announcement_not_found":
            extraction_status = SOURCE_DATA_ABSENT
            extraction_reason = "OFFICIAL_ANNUAL_REPORT_NOT_FOUND"
        elif issue == "announcement_fetch_or_parse_failed":
            # The legacy collector wraps the network request in this exception
            # branch. Parser failures returned by the robust validator flow into
            # the numeric-extraction audit below instead of raising here.
            extraction_status = SOURCE_FETCH_FAILED
            extraction_reason = "OFFICIAL_ANNOUNCEMENT_FETCH_FAILED"
        elif issue == "numeric_value_not_located_in_original":
            detail = dict(_EXTRACTION_META.get())
            extraction_status = str(detail.get("status") or STRUCTURE_RECOVERY_FAILED)
            extraction_reason = str(detail.get("reason") or "NUMERIC_EVIDENCE_RECOVERY_FAILED")
            extraction_method = str(detail.get("extraction_method") or "")

        if extraction_status:
            row["extraction_status"] = extraction_status
            row["extraction_reason"] = extraction_reason
            row["extraction_method"] = extraction_method
            row["source_data_absent"] = extraction_status == SOURCE_DATA_ABSENT
            row["parse_failed"] = extraction_status == PARSE_FAILED
            row["structure_recovery_failed"] = extraction_status == STRUCTURE_RECOVERY_FAILED
            row["ambiguous_match"] = extraction_status == AMBIGUOUS_MATCH
            row["source_fetch_failed"] = extraction_status == SOURCE_FETCH_FAILED
            row["unknown_is_pass"] = False
        return row

    return _typed_audit_row


def _annotate_success_rows(rows: list[dict[str, Any]]) -> None:
    lookup = dict(_EXTRACTION_BY_FINGERPRINT.get())
    for row in rows:
        if str(row.get("evidence_name") or "") != "定期报告原文数值":
            continue
        detail = lookup.get(_fingerprint(row))
        if detail is None:
            # A legacy cache entry is still semantically verified, but the proxy
            # normally prevents old annual-report cache keys from reaching here.
            status = VALUE_VERIFIED
            method = "LEGACY_VERIFIED_COMPAT"
            reason = "LEGACY_VERIFIED_ROW_WITHOUT_TYPED_METADATA"
        else:
            status = str(detail.get("status") or VALUE_VERIFIED)
            method = str(detail.get("extraction_method") or "")
            reason = str(detail.get("reason") or "")
        row["parse_status"] = status
        row["extraction_status"] = status
        row["extraction_method"] = method
        row["extraction_reason"] = reason
        row["value_recovered"] = status == VALUE_RECOVERED
        row["value_verified"] = status == VALUE_VERIFIED
        row["unknown_is_pass"] = False


def install_company_extraction_status_adapter(company_module: Any) -> Any:
    """Patch the legacy collector globals and return a typed collector wrapper."""
    original_collect = company_module.collect_company_announcements
    original_audit_row = company_module._audit_row

    company_module.extract_numeric_context = _typed_numeric_extractor
    company_module._audit_row = _typed_audit_row_factory(original_audit_row)

    def collect_company_announcements_typed(*args: Any, **kwargs: Any):
        _EXTRACTION_META.set({})
        _EXTRACTION_BY_FINGERPRINT.set({})
        if "cache" in kwargs:
            kwargs = dict(kwargs)
            kwargs["cache"] = _TypedEvidenceCacheProxy(kwargs["cache"])
        evidence_rows, audit_rows, summary = original_collect(*args, **kwargs)
        _annotate_success_rows(evidence_rows)

        typed_counts = {
            SOURCE_DATA_ABSENT: 0,
            SOURCE_FETCH_FAILED: 0,
            PARSE_FAILED: 0,
            STRUCTURE_RECOVERY_FAILED: 0,
            AMBIGUOUS_MATCH: 0,
            VALUE_RECOVERED: 0,
            VALUE_VERIFIED: 0,
        }
        for row in audit_rows:
            status = str(row.get("extraction_status") or "")
            if status in typed_counts:
                typed_counts[status] += 1
        for row in evidence_rows:
            status = str(row.get("extraction_status") or "")
            if status in typed_counts:
                typed_counts[status] += 1
        summary = dict(summary)
        summary["company_extraction_status_counts"] = typed_counts
        summary["company_typed_extraction_contract"] = "robust_typed_v1"
        summary["unknown_is_pass"] = False
        return evidence_rows, audit_rows, summary

    company_module.collect_company_announcements = collect_company_announcements_typed
    return collect_company_announcements_typed
