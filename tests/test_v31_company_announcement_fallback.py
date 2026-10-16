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


def test_shanghai_annual_report_stays_missing_when_both_sources_are_empty(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        company_module._impl,
        "_query_sse",
        lambda code, as_of, session, timeout: [],
    )
    monkeypatch.setattr(
        company_module._impl,
        "_load_cninfo_org_ids",
        lambda session, timeout: {"600406": "gssh0600406"},
    )

    def empty_cninfo(code, org_id, as_of, session, timeout):
        calls.append(code)
        return []

    monkeypatch.setattr(company_module._impl, "_query_cninfo", empty_cninfo)

    rows = company_module._announcement_candidates(
        "600406", date(2026, 10, 15), object(), 8, {}
    )

    assert rows == []
    assert calls == ["600406"]


def test_shenzhen_annual_report_path_is_unchanged(monkeypatch):
    calls: list[str] = []
    expected = [
        {
            "title": "润贝航科2025年年度报告",
            "publish_date": "2026-04-29",
            "url": "https://disc.static.szse.cn/download/full.pdf",
            "source_name": "szse",
        }
    ]

    def original(code, as_of, session, timeout, cninfo_org_ids):
        calls.append(code)
        return expected

    def should_not_query_sse(*args, **kwargs):
        raise AssertionError("Shanghai SSE fallback must not intercept Shenzhen issuers")

    monkeypatch.setattr(company_module, "_ORIGINAL_ANNOUNCEMENT_CANDIDATES", original)
    monkeypatch.setattr(company_module._impl, "_query_sse", should_not_query_sse)

    rows = company_module._announcement_candidates(
        "001316", date(2026, 10, 15), object(), 8, {}
    )

    assert rows == expected
    assert calls == ["001316"]


def test_only_full_annual_report_titles_are_accepted():
    assert company_module._impl._is_full_annual_report_title("国电南瑞2025年年度报告")
    rejected = (
        "国电南瑞2025年年度报告摘要",
        "国电南瑞2025年业绩预告",
        "国电南瑞2025年第一季度报告",
        "国电南瑞2025年半年度报告",
    )
    for title in rejected:
        assert not company_module._impl._is_full_annual_report_title(title), title


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
