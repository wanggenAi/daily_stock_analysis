from datetime import date

from src.strategies.genge_opportunity_discovery.evidence_collectors import company_announcements as company_module
from src.strategies.genge_opportunity_discovery.evidence_collectors import multi_year_predictability as predictability


def test_shanghai_company_disclosure_uses_sse(monkeypatch):
    calls = []

    def fake_sse(code, as_of, session, timeout):
        calls.append(code)
        return [{"title": "2025年年度报告", "url": "https://static.sse.com.cn/report.pdf"}]

    monkeypatch.setattr(company_module, "_query_sse", fake_sse)
    rows = company_module._announcement_candidates(
        "600406", date(2026, 9, 18), object(), 8, {"600406": "org"}
    )
    assert rows[0]["title"] == "2025年年度报告"
    assert calls == ["600406"]


def test_shanghai_material_events_use_sse(monkeypatch):
    calls = []

    def fake_sse(code, as_of, session, timeout):
        calls.append(code)
        return ([{"title": "重大事项公告"}], {"pages_fetched": 1})

    monkeypatch.setattr(company_module, "_query_sse_material_events", fake_sse)
    rows, summary = company_module._material_event_candidates(
        "603993", date(2026, 9, 18), object(), 8, {"603993": "org"}
    )
    assert rows[0]["title"] == "重大事项公告"
    assert summary["pages_fetched"] == 1
    assert calls == ["603993"]


def test_predictability_sse_history_keeps_distinct_complete_years(monkeypatch):
    def fake_sse(code, as_of, session, timeout):
        return [
            {"title": "公司2025年年度报告", "publish_date": "2026-03-30", "url": "https://static.sse.com.cn/2025.pdf"},
            {"title": "公司2025年年度报告摘要", "publish_date": "2026-03-30", "url": "https://static.sse.com.cn/2025-summary.pdf"},
            {"title": "公司2024年年度报告", "publish_date": "2025-03-30", "url": "https://static.sse.com.cn/2024.pdf"},
            {"title": "公司2023年年度报告", "publish_date": "2024-03-30", "url": "https://static.sse.com.cn/2023.pdf"},
        ]

    monkeypatch.setattr(predictability, "_query_sse", fake_sse)
    rows = predictability._query_sse_history(
        "600406", date(2026, 9, 18), object(), 8
    )
    assert [row["fiscal_year"] for row in rows] == [2025, 2024, 2023]
    assert all("摘要" not in row["title"] for row in rows)



def test_shenzhen_company_disclosure_uses_szse(monkeypatch):
    calls = []

    def fake_szse(code, as_of, session, timeout):
        calls.append(code)
        return [{
            "title": "2025年年度报告",
            "publish_date": "2026-03-30",
            "url": "https://disc.static.szse.cn/disc/2025.pdf",
        }]

    monkeypatch.setattr(company_module, "_query_szse", fake_szse)
    rows = company_module._announcement_candidates(
        "001316", date(2026, 9, 18), object(), 8, {"001316": "legacy-org"}
    )
    assert rows[0]["title"] == "2025年年度报告"
    assert calls == ["001316"]


def test_shenzhen_material_events_use_szse(monkeypatch):
    calls = []

    def fake_szse(code, as_of, session, timeout):
        calls.append(code)
        return ([{"title": "重大事项公告"}], {"pages_fetched": 1})

    monkeypatch.setattr(company_module, "_query_szse_material_events", fake_szse)
    rows, summary = company_module._material_event_candidates(
        "002941", date(2026, 9, 18), object(), 8, {"002941": "legacy-org"}
    )
    assert rows[0]["title"] == "重大事项公告"
    assert summary["pages_fetched"] == 1
    assert calls == ["002941"]


def test_szse_annual_query_enforces_exact_code_category_and_official_pdf():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "announceCount": 2,
                "data": [
                    {
                        "secCode": ["001316"],
                        "title": "润贝航科：2025年年度报告",
                        "publishTime": "2026-04-20 00:00:00",
                        "attachPath": "/disc/disk03/finalpage/2026-04-20/runbei.PDF",
                    },
                    {
                        "secCode": ["001317"],
                        "title": "其他公司：2025年年度报告",
                        "publishTime": "2026-04-20 00:00:00",
                        "attachPath": "/disc/disk03/finalpage/2026-04-20/other.PDF",
                    },
                ],
            }

    class Session:
        def post(self, url, *, json, headers, timeout):
            assert url == company_module.SZSE_ANNOUNCEMENT_URL
            assert json["stock"] == ["001316"]
            assert json["channelCode"] == ["fixed_disc"]
            assert json["bigCategoryId"] == ["010301"]
            assert json["seDate"] == ["2025-03-07", "2026-09-18"]
            assert headers["Referer"] == company_module.SZSE_PERIODIC_REPORT_REFERER
            assert timeout == 8
            return Response()

    rows = company_module._query_szse(
        "001316", date(2026, 9, 18), Session(), 8
    )
    assert len(rows) == 1
    assert rows[0]["title"] == "润贝航科：2025年年度报告"
    assert rows[0]["source_name"] == "szse"
    assert rows[0]["url"] == (
        "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-20/runbei.PDF"
    )


def test_predictability_szse_history_keeps_distinct_full_annual_reports(monkeypatch):
    def fake_szse(code, *, start, as_of, session, timeout, **kwargs):
        assert code == "001316"
        assert kwargs["big_category_id"] == "010301"
        assert kwargs["channel_code"] == "fixed_disc"
        assert kwargs["referer"] == company_module.SZSE_PERIODIC_REPORT_REFERER
        return ([
            {
                "title": "润贝航科：2025年年度报告",
                "publish_date": "2026-04-20",
                "url": "https://disc.static.szse.cn/disc/2025.pdf",
            },
            {
                "title": "润贝航科：2025年年度报告摘要",
                "publish_date": "2026-04-20",
                "url": "https://disc.static.szse.cn/disc/2025-summary.pdf",
            },
            {
                "title": "润贝航科：2024年年度报告",
                "publish_date": "2025-04-20",
                "url": "https://disc.static.szse.cn/disc/2024.pdf",
            },
            {
                "title": "润贝航科：2023年年度报告",
                "publish_date": "2024-04-20",
                "url": "https://disc.static.szse.cn/disc/2023.pdf",
            },
        ], {"pages_fetched": 1})

    monkeypatch.setattr(predictability, "_query_szse_announcements", fake_szse)
    rows = predictability._query_szse_history(
        "001316", date(2026, 9, 18), object(), 8
    )
    assert [row["fiscal_year"] for row in rows] == [2025, 2024, 2023]
    assert all("摘要" not in row["title"] for row in rows)



def test_sse_annual_query_rejects_half_year_summaries_and_notices():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "pageHelp": {
                    "data": [
                        {"TITLE": "公司2026年半年度报告", "SSEDATE": "2026-08-20", "URL": "/half.pdf"},
                        {"TITLE": "公司2025年年度报告摘要", "SSEDATE": "2026-03-30", "URL": "/summary.pdf"},
                        {"TITLE": "关于公司2025年年度报告的更正公告", "SSEDATE": "2026-04-01", "URL": "/correction.pdf"},
                        {"TITLE": "公司2025年年度报告", "SSEDATE": "2026-03-30", "URL": "/annual.pdf"},
                        {"TITLE": "公司2024年年度报告（修订版）", "SSEDATE": "2025-04-02", "URL": "/annual-2024.pdf"},
                    ]
                }
            }

    class Session:
        def get(self, _url, *, params, **_kwargs):
            assert params["pageHelp.pageSize"] == "30"
            return Response()

    rows = company_module._query_sse(
        "600406", date(2026, 9, 18), Session(), 8
    )
    assert [row["title"] for row in rows] == [
        "公司2025年年度报告",
        "公司2024年年度报告（修订版）",
    ]



def test_szse_relative_attachment_uses_download_endpoint():
    assert company_module._szse_attachment_url(
        "/disc/disk03/finalpage/2026-04-20/example.PDF"
    ) == (
        "https://disc.static.szse.cn/download/disc/disk03/finalpage/"
        "2026-04-20/example.PDF"
    )


def test_szse_missing_announce_count_keeps_paging_until_short_page():
    class Response:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": self._rows}

    class Session:
        pages = []

        def post(self, _url, *, json, **_kwargs):
            page = int(json["pageNum"])
            self.pages.append(page)
            count = 30 if page == 1 else 2
            return Response([
                {
                    "secCode": ["001316"],
                    "title": f"普通公告{page}-{index}",
                    "publishTime": "2026-09-10 00:00:00",
                    "attachPath": f"/disc/page-{page}-{index}.PDF",
                }
                for index in range(count)
            ])

    session = Session()
    rows, meta = company_module._query_szse_announcements(
        "001316",
        start=date(2026, 1, 1),
        as_of=date(2026, 9, 18),
        session=session,
        timeout=8,
        max_pages=5,
        page_size=30,
    )

    assert session.pages == [1, 2]
    assert len(rows) == 32
    assert meta["truncated"] is False
    assert meta["reported_total"] == 0


def test_szse_history_rejects_annual_report_correction_notice(monkeypatch):
    def fake_szse(code, **_kwargs):
        assert code == "001316"
        return ([
            {
                "title": "关于2025年年度报告的更正公告",
                "publish_date": "2026-04-21",
                "url": "https://disc.static.szse.cn/download/disc/correction.pdf",
            },
            {
                "title": "润贝航科2025年年度报告",
                "publish_date": "2026-04-20",
                "url": "https://disc.static.szse.cn/download/disc/annual.pdf",
            },
        ], {"pages_fetched": 1})

    monkeypatch.setattr(predictability, "_query_szse_announcements", fake_szse)
    rows = predictability._query_szse_history(
        "001316", date(2026, 9, 18), object(), 8
    )

    assert [row["title"] for row in rows] == ["润贝航科2025年年度报告"]



def test_primary_exchange_predictability_does_not_load_cninfo_org_ids(monkeypatch):
    monkeypatch.setattr(
        predictability,
        "_load_cninfo_org_ids",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("CNINFO orgId lookup must not run for SZSE")
        ),
    )
    monkeypatch.setattr(
        predictability,
        "_query_szse_history",
        lambda *_args, **_kwargs: [],
    )

    rows = predictability.collect_multi_year_predictability_evidence(
        priority_rows=[
            {
                "code": "001316",
                "stock_name": "润贝航科",
                "normalized_industry": "批发业",
            }
        ],
        as_of=date(2026, 9, 18),
        timeout=1,
    )

    assert len(rows) == 1
    assert rows[0]["reason_code"] == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"
