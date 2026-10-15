"""Company-announcement collector facade with a fail-closed Shanghai annual-report fallback.

The provider implementation lives in ``_company_announcements_impl``.  This facade
keeps its public/private import surface compatible while repairing one production
failure mode: an SSE annual-report metadata query may succeed syntactically but
return no usable full annual report.  In that case only, CNINFO's official
disclosure metadata is used as the fallback.  No evidence gate, PASS threshold,
or formal-decision authority is changed here.
"""

from __future__ import annotations

from typing import Any, Mapping

from . import _company_announcements_impl as _impl


# Preserve the existing module surface, including private helpers imported by
# multi_year_predictability and regression tests.
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


_ORIGINAL_ANNOUNCEMENT_CANDIDATES = _impl._announcement_candidates
_ORIGINAL_CACHE_KEY_FOR = _impl.EvidenceCache.key_for


def _announcement_candidates(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
    cninfo_org_ids: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return full annual-report candidates without weakening source authority.

    Shanghai issuers stay SSE-first.  CNINFO is consulted only when the primary
    SSE query fails or returns no full annual report.  If neither official source
    produces a full annual report, the caller still receives an empty result (or
    the primary transport error), so UNKNOWN/MISSING remains fail-closed.
    """
    if not code.startswith("6"):
        return _ORIGINAL_ANNOUNCEMENT_CANDIDATES(
            code, as_of, session, timeout, cninfo_org_ids
        )

    primary_error: Exception | None = None
    try:
        primary = _impl._query_sse(code, as_of, session, timeout)
    except Exception as exc:  # preserve fail-closed diagnostics if fallback also fails
        primary_error = exc
        primary = []
    if primary:
        return primary

    org_id = str(cninfo_org_ids.get(code) or "").strip()
    if not org_id:
        try:
            org_id = str(
                _impl._load_cninfo_org_ids(session, timeout).get(code) or ""
            ).strip()
        except Exception:
            org_id = ""

    if org_id:
        try:
            fallback = _impl._query_cninfo(code, org_id, as_of, session, timeout)
        except Exception:
            if primary_error is not None:
                raise primary_error
            raise
        fallback = [
            row
            for row in fallback
            if _impl._is_full_annual_report_title(row.get("title"))
        ]
        if fallback:
            return fallback

    if primary_error is not None:
        raise primary_error
    return []


def _company_evidence_cache_key(
    self: EvidenceCache, payload: Mapping[str, Any]
) -> str:
    """Invalidate only the stale Shanghai annual-report MISSING cache contract."""
    normalized = dict(payload)
    if (
        normalized.get("collector") == "sse_company_announcement"
        and normalized.get("announcement_type") == "annual_report"
        and normalized.get("version") == 4
    ):
        normalized["version"] = 5
    return _ORIGINAL_CACHE_KEY_FOR(self, normalized)


# Functions defined in the implementation module resolve globals from that
# module at call time, so patch the two narrowly scoped dependencies there.
_impl._announcement_candidates = _announcement_candidates
_impl.EvidenceCache.key_for = _company_evidence_cache_key

# Keep direct imports from this facade consistent with the patched behavior.
globals()["_announcement_candidates"] = _announcement_candidates
globals()["EvidenceCache"] = _impl.EvidenceCache
