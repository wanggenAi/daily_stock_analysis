"""Truthful issuer collector coverage audit; no eligibility or trading effects.

The All-A research queue is larger than the bounded issuer/financial fetch
budgets. Distinguish never-attempted issuers, cached replies and actual
noncached collector attempts; an OK URL is NOT evidence of a newly published
official disclosure without separate stable-fingerprint comparison.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping


def issuer_collection_coverage(
    queue: Iterable[Mapping[str, Any]],
    audit_path: str | Path,
    *,
    fundamental_budget: int,
    auto_evidence_budget: int,
) -> dict[str, Any]:
    selected = {str(r.get("code") or "").strip().zfill(6)
                for r in queue if str(r.get("code") or "").strip()}
    path = Path(audit_path)
    base: dict[str, Any] = {
        "contract": "GEN_GE_ISSUER_COVERAGE_AUDIT_V1",
        "requested_queue_count": len(selected),
        "configured_fundamental_limit": fundamental_budget,
        "auto_evidence_budget": auto_evidence_budget,
        "independent_net_new_issuer_evidence_verified": False,
        "strict_eligibility_changed": False,
    }
    if not path.is_file():
        return {**base, "status": "AUDIT_MISSING",
                "issuer_audited_codes": None, "issuer_network_attempted_codes": None,
                "issuer_cached_only_codes": None, "issuer_not_audited_codes": None,
                "issuer_noncached_ok_original_url_codes": None,
                "material_event_audited_codes": None,
                "material_event_noncached_attempted_codes": None,
                "material_event_cached_only_codes": None,
                "company_any_collector_audited_codes": None,
                "company_any_collector_not_audited_codes": None}
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    issuer_rows = [
        r for r in rows
        if str(r.get("scope") or "").strip().lower() == "company"
        and "company_announcement" in str(r.get("collector") or "").strip().lower()
        and str(r.get("code") or "").strip().zfill(6) in selected
    ]
    # Material-event scanning is a different collection unit from original
    # annual-report source extraction. Account for it separately: otherwise
    # 30/80 touched issuers can be mislabeled 15/80 just because 15 have
    # annual-report collector rows.
    event_rows = [
        r for r in rows
        if str(r.get("scope") or "").strip().lower() == "company"
        and str(r.get("collector") or "").strip().lower() == "official_material_event_scan"
        and str(r.get("code") or "").strip().zfill(6) in selected
    ]
    event_audited = {str(r["code"]).strip().zfill(6) for r in event_rows}
    event_attempted = {str(r["code"]).strip().zfill(6) for r in event_rows
                       if str(r.get("cache_hit") or "").lower() not in ("true", "1", "yes")}
    audited = {str(r["code"]).strip().zfill(6) for r in issuer_rows}
    attempted = {str(r["code"]).strip().zfill(6) for r in issuer_rows
                 if str(r.get("cache_hit") or "").lower() not in ("true", "1", "yes")}
    cached_only = audited - attempted
    url_ok = {str(r["code"]).strip().zfill(6) for r in issuer_rows
              if str(r.get("cache_hit") or "").lower() not in ("true", "1", "yes")
              and str(r.get("status") or "").upper() == "OK"
              and str(r.get("original_url") or "").startswith("https://")}
    return {
        **base, "status": "AUDIT_PRESENT",
        "issuer_audited_codes": len(audited),
        "issuer_network_attempted_codes": len(attempted),
        "issuer_cached_only_codes": len(cached_only),
        "issuer_not_audited_codes": len(selected - audited),  # annual-report extraction only
        "issuer_noncached_ok_original_url_codes": len(url_ok),
        "material_event_audited_codes": len(event_audited),
        "material_event_noncached_attempted_codes": len(event_attempted),
        "material_event_cached_only_codes": len(event_audited - event_attempted),
        "company_any_collector_audited_codes": len(audited | event_audited),
        "company_any_collector_not_audited_codes": len(selected - (audited | event_audited)),
        "issuer_not_audited_code_sample": sorted(selected - audited)[:20],
        "source_file": str(path),
        "note": ("An OK original URL only establishes collection, never a net-new "
                 "source identity, new issuer reporting period or verified hard gate."),
    }
