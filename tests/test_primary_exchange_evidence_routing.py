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



def test_sse_annual_query_rejects_half_year_summaries_and_notices():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "pageHelp": {
                    "data": [
                        {
                            "TITLE": "公司2026年半年度报告",
                            "SSEDATE": "2026-08-20",
                            "URL": "/half.pdf",
                        },
                        {
                            "TITLE": "公司2025年年度报告摘要",
                            "SSEDATE": "2026-03-30",
                            "URL": "/summary.pdf",
                        },
                        {
                            "TITLE": "关于公司2025年年度报告的更正公告",
                            "SSEDATE": "2026-04-01",
                            "URL": "/correction.pdf",
                        },
                        {
                            "TITLE": "公司2025年年度报告",
                            "SSEDATE": "2026-03-30",
                            "URL": "/annual.pdf",
                        },
                        {
                            "TITLE": "公司2024年年度报告（修订版）",
                            "SSEDATE": "2025-04-02",
                            "URL": "/annual-2024.pdf",
                        },
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
