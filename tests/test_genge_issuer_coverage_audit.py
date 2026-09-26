"""Issuer coverage cannot mistake cache reuse or absent audit for fresh proof."""
import csv

from src.strategies.genge_opportunity_discovery.evidence_collectors.issuer_coverage_audit import (
    issuer_collection_coverage,
)


def _queue():
    return [{"code": x} for x in ("001316", "603993", "600406")]


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "scope", "collector", "code", "cache_hit", "status", "original_url",
        ])
        writer.writeheader()
        writer.writerows(rows)


def test_missing_audit_is_unknown_not_zero(tmp_path):
    result = issuer_collection_coverage(_queue(), tmp_path / "not-there.csv",
                                        fundamental_budget=30, auto_evidence_budget=30)
    assert result["status"] == "AUDIT_MISSING"
    assert result["issuer_network_attempted_codes"] is None
    assert result["issuer_not_audited_codes"] is None
    assert result["independent_net_new_issuer_evidence_verified"] is False


def test_cached_only_does_not_count_as_new_network_or_official_success(tmp_path):
    audit = tmp_path / "audit.csv"
    _write(audit, [
        {"scope": "company", "collector": "sse_company_announcement", "code": "603993",
         "cache_hit": "True", "status": "OK", "original_url": "https://example.org/a"},
        {"scope": "industry", "collector": "industry", "code": "001316",
         "cache_hit": "False", "status": "OK", "original_url": "https://example.org/b"},
        {"scope": "company", "collector": "szse_company_announcement", "code": "001316",
         "cache_hit": "False", "status": "FAILED", "original_url": ""},
    ])
    result = issuer_collection_coverage(_queue(), audit, fundamental_budget=30,
                                        auto_evidence_budget=30)
    assert result["issuer_audited_codes"] == 2
    assert result["issuer_network_attempted_codes"] == 1
    assert result["issuer_cached_only_codes"] == 1
    assert result["issuer_not_audited_codes"] == 1
    assert result["issuer_noncached_ok_original_url_codes"] == 0
    assert result["strict_eligibility_changed"] is False


def test_noncached_ok_url_still_not_net_new_verified(tmp_path):
    audit = tmp_path / "audit.csv"
    _write(audit, [{
        "scope": "company", "collector": "szse_company_announcement", "code": "001316",
        "cache_hit": "False", "status": "OK", "original_url": "https://example.org/document",
    }])
    result = issuer_collection_coverage(_queue(), audit, fundamental_budget=30,
                                        auto_evidence_budget=30)
    assert result["issuer_noncached_ok_original_url_codes"] == 1
    assert result["independent_net_new_issuer_evidence_verified"] is False


def test_material_event_scan_is_counted_separately_from_annual_fetch(tmp_path):
    audit = tmp_path / "audit.csv"
    _write(audit, [
        {"scope": "company", "collector": "sse_company_announcement", "code": "603993",
         "cache_hit": "True", "status": "OK", "original_url": "https://example.org/old-annual"},
        {"scope": "company", "collector": "official_material_event_scan", "code": "603993",
         "cache_hit": "True", "status": "OK", "original_url": "https://example.org/old-event"},
        {"scope": "company", "collector": "official_material_event_scan", "code": "001316",
         "cache_hit": "False", "status": "MISSING", "original_url": ""},
    ])
    result = issuer_collection_coverage(_queue(), audit, fundamental_budget=30,
                                        auto_evidence_budget=30)
    assert result["issuer_audited_codes"] == 1
    assert result["issuer_not_audited_codes"] == 2  # annual extraction
    assert result["material_event_audited_codes"] == 2
    assert result["material_event_noncached_attempted_codes"] == 1
    assert result["material_event_cached_only_codes"] == 1
    assert result["company_any_collector_audited_codes"] == 2
    assert result["company_any_collector_not_audited_codes"] == 1
    assert not result["independent_net_new_issuer_evidence_verified"]
