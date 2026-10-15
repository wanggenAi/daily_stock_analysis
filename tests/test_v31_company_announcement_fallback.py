from __future__ import annotations

from datetime import date

from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    company_announcements as company_module,
)


def test_shanghai_annual_report_uses_cninfo_when_sse_returns_empty(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        company_module._impl,
        "_query_sse",
        lambda code, as_of, session, timeout: [],
    )

    def fake_load_org_ids(session, timeout):
        calls.append("load_org_ids")
        return {"600406": "gssh0600406"}

    def fake_cninfo(code, org_id, as_of, session, timeout):
        calls.append("cninfo")
        assert code == "600406"
        assert org_id == "gssh0600406"
        return [
            {
                "title": "国电南瑞2025年年度报告摘要",
                "publish_date": "2026-04-30",
                "url": "https://static.cninfo.com.cn/summary.pdf",
                "source_name": "cninfo",
            },
            {
                "title": "国电南瑞2025年年度报告",
                "publish_date": "2026-04-30",
                "url": "https://static.cninfo.com.cn/full.pdf",
                "source_name": "cninfo",
            },
        ]

    monkeypatch.setattr(company_module._impl, "_load_cninfo_org_ids", fake_load_org_ids)
    monkeypatch.setattr(company_module._impl, "_query_cninfo", fake_cninfo)

    rows = company_module._announcement_candidates(
        "600406", date(2026, 10, 15), object(), 8, {}
    )

    assert calls == ["load_org_ids", "cninfo"]
    assert [row["title"] for row in rows] == ["国电南瑞2025年年度报告"]
    assert rows[0]["source_name"] == "cninfo"


def test_shanghai_annual_report_keeps_sse_primary_when_available(monkeypatch):
    expected = [
        {
            "title": "国电南瑞2025年年度报告",
            "publish_date": "2026-04-30",
            "url": "https://static.sse.com.cn/full.pdf",
            "source_name": "sse",
        }
    ]
    monkeypatch.setattr(
        company_module._impl,
        "_query_sse",
        lambda code, as_of, session, timeout: expected,
    )

    def should_not_load(*args, **kwargs):
        raise AssertionError("CNINFO fallback must not run when SSE has a full report")

    monkeypatch.setattr(company_module._impl, "_load_cninfo_org_ids", should_not_load)

    rows = company_module._announcement_candidates(
        "600406", date(2026, 10, 15), object(), 8, {}
    )
    assert rows == expected


def test_shanghai_annual_report_missing_cache_contract_is_invalidated(tmp_path):
    cache = company_module.EvidenceCache(tmp_path)
    payload = {
        "collector": "sse_company_announcement",
        "code": "600406",
        "announcement_type": "annual_report",
        "report_period": "2025",
        "version": 4,
    }

    previous_key = company_module._ORIGINAL_CACHE_KEY_FOR(cache, payload)
    repaired_key = cache.key_for(payload)

    assert repaired_key != previous_key
    assert repaired_key == company_module._ORIGINAL_CACHE_KEY_FOR(
        cache, {**payload, "version": 5}
    )
