from __future__ import annotations

from datetime import date
from pathlib import Path

from src.strategies.genge_opportunity_discovery import evidence_collectors
from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    company_announcements,
    company_extraction_status,
)
from src.strategies.genge_opportunity_discovery.evidence_collectors.cache import EvidenceCache
from src.strategies.genge_opportunity_discovery.evidence_collectors.evidence_normalization import (
    PARSE_FAILED,
    SOURCE_DATA_ABSENT,
    SOURCE_FETCH_FAILED,
    STRUCTURE_RECOVERY_FAILED,
    VALUE_RECOVERED,
    VALUE_VERIFIED,
)


def _audit(issue: str):
    return company_announcements._audit_row(
        code="000001",
        stock_name="fixture",
        industry="fixture",
        collector="fixture",
        status="FAILED",
        issue=issue,
        detail="fixture",
    )


def test_production_package_exports_typed_company_collector() -> None:
    assert evidence_collectors.collect_company_announcements is company_announcements.collect_company_announcements
    assert evidence_collectors.collect_company_announcements.__name__ == "collect_company_announcements_typed"


def test_production_company_extractor_recovers_split_layout() -> None:
    result = company_announcements.extract_numeric_context(
        "金额单位:万元\n营业\n收入\n1,234.50",
        ["营业收入"],
    )
    assert result["value"] == "1234.50"
    assert result["unit"] == "万元"


def test_numeric_recovery_failure_is_typed_not_collapsed_to_missing() -> None:
    assert company_announcements.extract_numeric_context("营业收入 未披露", ["营业收入"]) == {}
    row = _audit("numeric_value_not_located_in_original")
    assert row["extraction_status"] == STRUCTURE_RECOVERY_FAILED
    assert row["structure_recovery_failed"] is True
    assert row["source_data_absent"] is False
    assert row["unknown_is_pass"] is False


def test_document_parse_failure_survives_numeric_stage(monkeypatch) -> None:
    monkeypatch.setattr(
        company_extraction_status,
        "extract_text_from_response_detailed",
        lambda _content, _content_type, _source_url="": {
            "status": PARSE_FAILED,
            "text": "",
            "parser": "pdf_parse_failed:FixtureError",
            "reason": "pdf_parse_failed:FixtureError",
        },
    )
    text, parser = company_announcements.extract_text_from_response(b"fixture", "application/pdf")
    assert text == ""
    assert parser == "pdf_parse_failed:FixtureError"
    assert company_announcements.extract_numeric_context(text, ["营业收入"]) == {}
    row = _audit("numeric_value_not_located_in_original")
    assert row["extraction_status"] == PARSE_FAILED
    assert row["parse_failed"] is True
    assert row["source_data_absent"] is False
    assert row["unknown_is_pass"] is False


def test_fetch_failure_and_true_absence_are_distinct() -> None:
    fetch_failed = _audit("announcement_query_failed")
    absent = _audit("announcement_not_found")
    assert fetch_failed["extraction_status"] == SOURCE_FETCH_FAILED
    assert fetch_failed["source_fetch_failed"] is True
    assert absent["extraction_status"] == SOURCE_DATA_ABSENT
    assert absent["source_data_absent"] is True
    assert fetch_failed["extraction_status"] != absent["extraction_status"]


def test_empty_collection_summary_preserves_typed_contract(tmp_path: Path) -> None:
    evidence, audit, summary = evidence_collectors.collect_company_announcements(
        rows=[],
        as_of=date(2026, 9, 12),
        cache=EvidenceCache(tmp_path),
        limit=0,
        timeout=1,
    )
    assert evidence == []
    assert audit == []
    assert summary["company_typed_extraction_contract"] == "robust_typed_v1"
    assert summary["unknown_is_pass"] is False
    counts = summary["company_extraction_status_counts"]
    assert set(counts) == {
        SOURCE_DATA_ABSENT,
        SOURCE_FETCH_FAILED,
        PARSE_FAILED,
        STRUCTURE_RECOVERY_FAILED,
        "AMBIGUOUS_MATCH",
        VALUE_RECOVERED,
        VALUE_VERIFIED,
    }
    assert all(value == 0 for value in counts.values())


def test_adapter_has_no_candidate_or_historical_run_hardcode() -> None:
    for path in (
        Path("src/strategies/genge_opportunity_discovery/evidence_collectors/company_extraction_status.py"),
        Path("src/strategies/genge_opportunity_discovery/evidence_collectors/__init__.py"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "603055" not in text
        assert "34565436187" not in text
        assert "34586652294" not in text


def test_company_collector_retries_negative_cached_observations(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def no_annual_report(code, *_args, **_kwargs):
        calls.append(code)
        return []

    monkeypatch.setattr(company_announcements, "_announcement_candidates", no_annual_report)
    cache = EvidenceCache(tmp_path)
    kwargs = {
        "rows": [
            {
                "code": "600048",
                "stock_name": "保利发展",
                "normalized_industry": "房地产业",
            }
        ],
        "as_of": date(2026, 9, 22),
        "cache": cache,
        "limit": 1,
        "timeout": 1,
    }

    first_evidence, first_audit, first_summary = (
        evidence_collectors.collect_company_announcements(**kwargs)
    )
    second_evidence, second_audit, second_summary = (
        evidence_collectors.collect_company_announcements(**kwargs)
    )

    assert first_evidence == second_evidence == []
    assert [row["issue"] for row in first_audit] == ["announcement_not_found"]
    assert [row["issue"] for row in second_audit] == ["announcement_not_found"]
    assert calls == ["600048", "600048"]
    assert first_summary["company_actual_fetch_count"] == 1
    assert second_summary["company_actual_fetch_count"] == 1
    assert cache.cache_hits == 0
    assert cache.cache_misses == 2


def test_company_collector_reuses_positive_cached_evidence(monkeypatch, tmp_path: Path) -> None:
    cache = EvidenceCache(tmp_path)
    typed_cache = company_extraction_status._TypedEvidenceCacheProxy(cache)
    key = typed_cache.key_for(
        {
            "collector": "sse_company_announcement",
            "code": "600048",
            "announcement_type": "annual_report",
            "report_period": "2025",
            "version": 4,
        }
    )
    cached_evidence = [
        {
            "scope": "company",
            "code": "600048",
            "stock_name": "保利发展",
            "industry": "房地产业",
            "evidence_name": "fixture_verified_company_evidence",
            "evidence_status": "VERIFIED",
        }
    ]
    cache.set(key, {"evidence_rows": cached_evidence, "audit_rows": []})

    monkeypatch.setattr(
        company_announcements,
        "_announcement_candidates",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("positive cache should suppress provider query")
        ),
    )

    evidence, audit, summary = evidence_collectors.collect_company_announcements(
        rows=[
            {
                "code": "600048",
                "stock_name": "保利发展",
                "normalized_industry": "房地产业",
            }
        ],
        as_of=date(2026, 9, 22),
        cache=cache,
        limit=1,
        timeout=1,
    )

    assert evidence == cached_evidence
    assert audit == []
    assert summary["company_actual_fetch_count"] == 0
    assert cache.cache_hits == 1
    assert cache.cache_misses == 0
