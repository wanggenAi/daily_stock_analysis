from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import IndustryAliasResolver, load_industry_alias_map
from src.strategies.genge_cycle_bottom.industry_evidence import load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery import evidence_collectors
from src.strategies.genge_opportunity_discovery.evidence_collectors import company_announcements
from src.strategies.genge_opportunity_discovery.evidence_collectors.cache import EvidenceCache
from src.strategies.genge_opportunity_discovery.evidence_collectors.validators import (
    direction_from_excerpt,
    extract_numeric_context,
    extract_text_from_response,
)
from src.strategies.genge_opportunity_discovery.exit_profile import (
    REPORT_AGGREGATE_RULE_VERSION,
    _cohort_period_samples,
    _cohort_validation,
    fetch_extended_adjusted_histories,
    generate_exit_profile_from_reports,
    refresh_exit_profiles_from_price_history,
)
from src.strategies.genge_opportunity_discovery.pipeline import (
    _build_evidence_inventory,
    _company_evidence_for_strategy,
    _rank_opportunities,
    _research_queues,
    run_opportunity_discovery,
)
from src.strategies.genge_opportunity_discovery.shenzhen_full_scan import (
    ScanConfig,
    build_official_universe,
    build_price_plan,
    build_sector_summary,
    build_technology_sector_rows,
    classify_candidate,
    enrich_universe_industries,
    load_recent_universe_snapshot,
    quant_screen,
    resolve_scan_dates,
)
from src.strategies.genge_opportunity_discovery.tomorrow_watchlist import PriceContext, _plan_prices, generate_tomorrow_watchlist


def _price_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=1000, freq="D")
    closes = np.concatenate(
        [
            np.linspace(22.0, 14.0, 650),
            np.linspace(14.0, 9.5, 220),
            np.linspace(9.5, 11.2, 80),
            np.linspace(11.0, 11.8, 50),
        ]
    )
    return pd.DataFrame(
        [
            {
                "date": day.date().isoformat(),
                "open": round(float(close) * 0.995, 3),
                "high": round(float(close) * 1.02, 3),
                "low": round(float(close) * 0.98, 3),
                "close": round(float(close), 3),
                "volume": 2_000_000 + index * 100,
                "amount": 30_000_000 + index * 1000,
            }
            for index, (day, close) in enumerate(zip(dates, closes))
        ]
    )


def test_research_queue_promotes_exit_profile_priority_from_secondary() -> None:
    rows = [
        {"code": "000001", "quant_screen_status": "PRIORITY_RESEARCH", "quant_score": 90.0},
        {"code": "000088", "quant_screen_status": "SECONDARY_RESEARCH", "quant_score": 50.0},
        {"code": "000002", "quant_screen_status": "SECONDARY_RESEARCH", "quant_score": 60.0},
    ]

    priority, secondary = _research_queues(
        rows, priority_queue_size=3, secondary_queue_size=3, priority_codes=["000088"],
    )

    assert [row["code"] for row in priority][:2] == ["000088", "000001"]
    assert [row["code"] for row in secondary] == ["000002"]


def test_research_queue_capacity_retains_every_passed_profile_priority() -> None:
    normal = [
        {
            "code": f"{index:06d}", "quant_screen_status": "PRIORITY_RESEARCH",
            "quant_score": 100.0 - index / 100,
        }
        for index in range(1, 81)
    ]
    promoted = [
        {
            "code": f"9{index:05d}", "quant_screen_status": "SECONDARY_RESEARCH",
            "quant_score": 50.0 - index / 100,
        }
        for index in range(1, 91)
    ]
    promoted_codes = [row["code"] for row in promoted]

    priority, _secondary = _research_queues(
        [*normal, *promoted],
        priority_queue_size=max(80, len(promoted_codes)),
        secondary_queue_size=80,
        priority_codes=promoted_codes,
    )

    assert set(promoted_codes).issubset({row["code"] for row in priority})


def _valuation_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=900, freq="D")
    return pd.DataFrame(
        {
            "date": [day.date().isoformat() for day in dates],
            "pb": np.linspace(2.5, 1.0, len(dates)),
            "pe": np.linspace(30.0, 12.0, len(dates)),
            "ps": np.linspace(5.0, 1.5, len(dates)),
        }
    )


def _financial_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_date": "2025-12-31",
                "disclosure_date": "2026-04-20",
                "debt_ratio": 42.0,
                "net_profit": 1_000_000_000,
                "operating_cash_flow": 1_200_000_000,
                "roe": 8.5,
            }
        ]
    )


def _industry_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-15",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "主流尺寸价格较底部回升 5%",
                "evidence_direction": "POSITIVE",
                "source": "公开产业数据",
                "source_type": "official_report",
            },
            {
                "date": "2026-06-16",
                "industry": "面板",
                "evidence_name": "稼动率",
                "evidence_value": "稼动率 75%，供给维持纪律性",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-06-17",
                "industry": "面板",
                "evidence_name": "库存水位",
                "evidence_value": "库存下降 10% 至合理水平",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-07-01",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "未来数据不应参与 as-of",
                "evidence_direction": "NEGATIVE",
                "source": "未来数据",
                "source_type": "official_report",
            },
        ]
    )


def _company_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "code": "000100",
                "stock_name": "TCL科技",
                "industry": "面板",
                "evidence_name": "产能结构",
                "evidence_value": "高端产线占比提升 8%",
                "evidence_direction": "POSITIVE",
                "source": "公司公告",
                "source_type": "company_announcement",
            },
            {
                "date": "2026-06-19",
                "code": "000100",
                "stock_name": "TCL科技",
                "industry": "面板",
                "evidence_name": "库存管理",
                "evidence_value": "库存周转天数下降 12%",
                "evidence_direction": "POSITIVE",
                "source": "交易所披露",
                "source_type": "exchange_disclosure",
            },
        ]
    )


def _input(code: str = "000100", stock_name: str = "TCL科技", industry: str = "光学光电子") -> BacktestInput:
    return BacktestInput(
        code=code,
        stock_name=stock_name,
        price_df=_price_frame(),
        valuation_df=_valuation_frame(),
        financial_df=_financial_frame(),
        industry=industry,
    )


def _diagnostics() -> dict[str, object]:
    return {
        "requested_stock_records": [{"code": "000100", "stock_name": "TCL科技", "industry": "光学光电子"}],
        "source_mode": "fixture",
        "no_auto_trade": True,
    }


def _auto_company_evidence(
    code: str = "000100",
    stock_name: str = "TCL科技",
    industry: str = "面板",
    evidence_date: str = "2026-06-20",
) -> list[dict[str, object]]:
    return [
        {
            "date": evidence_date,
            "publish_date": evidence_date,
            "scope": "company",
            "code": code,
            "stock_name": stock_name,
            "industry": industry,
            "evidence_name": "定期报告原文数值",
            "indicator": "定期报告原文数值",
            "evidence_value": "营业收入增长 8%",
            "value": "8",
            "unit": "%",
            "comparison_period": evidence_date[:4],
            "evidence_direction": "POSITIVE",
            "direction": "POSITIVE",
            "source": f"https://static.cninfo.com.cn/finalpage/test/{code}.PDF",
            "original_url": f"https://static.cninfo.com.cn/finalpage/test/{code}.PDF",
            "source_domain": "static.cninfo.com.cn",
            "source_type": "EXCHANGE_DISCLOSURE",
            "confidence": "HIGH",
            "raw_excerpt": "营业收入增长 8%",
            "normalized_summary": "定期报告原文：营业收入增长 8%",
            "title": "年度报告",
            "parser": "fixture_company_announcement",
            "collector": "fixture_company_announcement",
            "parse_status": "OK",
            "evidence_status": "VERIFIED",
            "content_hash": f"hash-{code}",
            "extraction_confidence": "HIGH",
            "warning_flags": "",
        }
    ]


def _fake_auto_collector(*, company_rows: list[dict[str, object]] | None = None):
    def _collect(**_kwargs):
        rows = company_rows if company_rows is not None else _auto_company_evidence()
        return (
            [],
            rows,
            [],
            {
                "enabled": True,
                "executed": True,
                "task_count": 1,
                "actual_fetch_count": 1,
                "fetch_success_count": 1,
                "verified_count": len(rows),
                "partially_verified_count": 0,
                "failed_count": 0,
                "missing_count": 0,
                "cache_hit_count": 0,
                "cache_miss_count": 1,
                "audit_count": 0,
                "cache_dir": "fixture",
            },
        )

    return _collect


def test_pdf_fixture_extracts_text_and_numeric_context() -> None:
    content = Path("tests/fixtures/genge_opportunity_discovery/evidence_numeric.pdf").read_bytes()

    text, parser = extract_text_from_response(content, "application/pdf")
    numeric = extract_numeric_context(text, keywords=["operating revenue"])

    assert parser == "pdf_pypdf"
    assert "operating revenue" in text
    assert numeric["value"] == "123.45"
    assert numeric["unit"] == ""


def test_numeric_evidence_does_not_fall_back_to_unrelated_year() -> None:
    assert extract_numeric_context(
        "纳思达股份有限公司 2025 年年度报告全文",
        keywords=["营业收入", "净利润", "现金流"],
    ) == {}
    assert direction_from_excerpt("营业收入（元） 2,609,136,912.38 4,403,674,123.09 -40.75%") == "NEGATIVE"
    assert direction_from_excerpt("营业收入（元） 6,145,823,063.27 5,511,073,894.21 11.52%") == "POSITIVE"
    assert direction_from_excerpt("营业收入（元） 92,507,796,069.94 92,495,525,118.30 0.01%") == "NEUTRAL"


def test_cninfo_uses_official_org_id_and_prefers_full_annual_report() -> None:
    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeSession:
        posted_data: dict[str, str] = {}

        def get(self, url: str, **_kwargs) -> FakeResponse:
            assert url == company_announcements.CNINFO_STOCK_LIST_URL
            return FakeResponse(
                {"stockList": [{"code": "002180", "orgId": "9900003822", "zwjc": "奔图科技"}]}
            )

        def post(self, url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            assert url == "https://www.cninfo.com.cn/new/hisAnnouncement/query"
            self.posted_data = data
            timestamp = int(datetime(2026, 4, 15, tzinfo=timezone.utc).timestamp() * 1000)
            return FakeResponse(
                {
                    "announcements": [
                        {
                            "announcementTitle": "2025年<em>年度报告</em>摘要",
                            "announcementTime": timestamp,
                            "adjunctUrl": "finalpage/2026-04-15/summary.PDF",
                        },
                        {
                            "announcementTitle": "2025年<em>年度报告</em>",
                            "announcementTime": timestamp,
                            "adjunctUrl": "finalpage/2026-04-15/full.PDF",
                        },
                    ]
                }
            )

    session = FakeSession()
    org_ids = company_announcements._load_cninfo_org_ids(session, timeout=5)
    announcements = company_announcements._query_cninfo(
        "002180",
        org_ids["002180"],
        date(2026, 7, 10),
        session,
        timeout=5,
    )

    assert session.posted_data["stock"] == "002180,9900003822"
    assert session.posted_data["column"] == "szse"
    assert session.posted_data["plate"] == "sz"
    assert announcements[0]["title"] == "2025年年度报告"
    assert announcements[0]["url"] == "https://static.cninfo.com.cn/finalpage/2026-04-15/full.PDF"

    company_announcements._query_cninfo(
        "600519",
        "gssh0600519",
        date(2026, 7, 10),
        session,
        timeout=5,
    )
    assert session.posted_data["column"] == "sse"
    assert session.posted_data["plate"] == "sh"


def test_company_collector_prefers_cninfo_official_pdf_for_shanghai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, *, payload: dict | None = None, content: bytes = b"") -> None:
            self._payload = payload
            self.content = content
            self.headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            assert self._payload is not None
            return self._payload

    class FakeSession:
        def get(self, url: str, **_kwargs) -> FakeResponse:
            if url == company_announcements.CNINFO_STOCK_LIST_URL:
                return FakeResponse(
                    payload={"stockList": [{"code": "600519", "orgId": "gssh0600519"}]},
                )
            assert url == "https://static.cninfo.com.cn/finalpage/2026-04-17/report.PDF"
            return FakeResponse(content="营业收入 100亿元，同比增长 5%".encode("utf-8"))

        def post(self, url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            assert url == "https://www.cninfo.com.cn/new/hisAnnouncement/query"
            assert data["column"] == "sse"
            timestamp = int(datetime(2026, 4, 17, tzinfo=timezone.utc).timestamp() * 1000)
            return FakeResponse(
                payload={
                    "announcements": [
                        {
                            "announcementTitle": "贵州茅台2025年年度报告",
                            "announcementTime": timestamp,
                            "adjunctUrl": "finalpage/2026-04-17/report.PDF",
                        }
                    ]
                },
            )

    monkeypatch.setattr(company_announcements.requests, "Session", lambda: FakeSession())
    evidence_rows, audit_rows, summary = company_announcements.collect_company_announcements(
        rows=[{"code": "600519", "stock_name": "贵州茅台", "normalized_industry": "白酒"}],
        as_of=date(2026, 7, 20),
        cache=EvidenceCache(tmp_path / "cache"),
        limit=1,
    )

    assert audit_rows == []
    assert summary["company_evidence_rows"] == 1
    assert evidence_rows[0]["source_domain"] == "static.cninfo.com.cn"
    assert evidence_rows[0]["collector"] == "cninfo_company_announcement"
    assert evidence_rows[0]["evidence_status"] == "VERIFIED"


def test_material_event_collector_preserves_status_timezone_and_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, *, payload: dict | None = None, content: bytes = b"") -> None:
            self._payload = payload
            self.content = content
            self.headers = {"content-type": "text/plain; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            assert self._payload is not None
            return self._payload

    class FakeSession:
        post_count = 0

        def get(self, url: str, **_kwargs) -> FakeResponse:
            if url == company_announcements.CNINFO_STOCK_LIST_URL:
                return FakeResponse(payload={"stockList": [{"code": "000088", "orgId": "gssz0000088"}]})
            if url.endswith("active.PDF"):
                return FakeResponse(content="控股股东部分股份被司法冻结，冻结事项仍在执行。".encode())
            if url.endswith("resolved.PDF"):
                return FakeResponse(content="控股股东全部冻结股份已全部解除。".encode())
            raise AssertionError(url)

        def post(self, url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            assert url == "https://www.cninfo.com.cn/new/hisAnnouncement/query"
            assert data["searchkey"] == ""
            assert data["category"] == ""
            assert data["pageNum"] == "1"
            FakeSession.post_count += 1
            active_timestamp = int(
                datetime(2026, 7, 20, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            resolved_timestamp = int(
                datetime(2026, 7, 21, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            future_timestamp = int(
                datetime(2026, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            return FakeResponse(payload={
                "totalAnnouncement": 3,
                "announcements": [
                    {
                        "announcementTitle": "关于控股股东部分股份被司法冻结的公告",
                        "announcementTime": active_timestamp,
                        "adjunctUrl": "finalpage/2026-07-20/active.PDF",
                    },
                    {
                        "announcementTitle": "关于控股股东全部股份解除冻结的公告",
                        "announcementTime": resolved_timestamp,
                        "adjunctUrl": "finalpage/2026-07-21/resolved.PDF",
                    },
                    {
                        "announcementTitle": "关于收到监管立案通知的公告",
                        "announcementTime": future_timestamp,
                        "adjunctUrl": "finalpage/2026-07-30/future.PDF",
                    },
                ],
            })

    monkeypatch.setattr(company_announcements.requests, "Session", FakeSession)
    cache = EvidenceCache(tmp_path / "cache")
    inputs = [{"code": "000088", "stock_name": "盐田港", "normalized_industry": "港口"}]
    evidence_rows, audit_rows, summary = company_announcements.collect_company_material_events(
        rows=inputs, as_of=date(2026, 7, 28), cache=cache, limit=1,
    )

    assert len(evidence_rows) == 1
    resolved = evidence_rows[0]
    assert resolved["event_status"] == "RESOLVED"
    assert resolved["event_resolution_scope"] == "FULL"
    assert resolved["direction"] == "NEUTRAL"
    assert resolved["date"] == "2026-07-21"
    assert audit_rows[0]["status"] == "OK"
    assert audit_rows[0]["issue"] == "material_event_scan_complete"
    assert summary["company_event_active_count"] == 0
    assert summary["company_event_resolved_count"] == 1

    inventory = _build_evidence_inventory(
        industry_evidence_df=None,
        company_evidence_df=pd.DataFrame(evidence_rows),
        as_of=date(2026, 7, 28),
    )
    inventory_row = inventory[0]
    assert inventory_row["evidence_status"] == "VERIFIED"
    assert inventory_row["evidence_kind"] == "material_event"
    assert inventory_row["event_type"] == "SHARE_FREEZE"
    assert inventory_row["event_severity"] == "MEDIUM"
    assert inventory_row["event_resolution_scope"] == "FULL"
    assert inventory_row["risk_valid_until"]
    assert _company_evidence_for_strategy(pd.DataFrame(evidence_rows)).empty

    company_announcements.collect_company_material_events(
        rows=inputs, as_of=date(2026, 7, 28), cache=cache, limit=1,
    )
    assert FakeSession.post_count == 1
    company_announcements.collect_company_material_events(
        rows=inputs, as_of=date(2026, 7, 29), cache=cache, limit=1,
    )
    assert FakeSession.post_count == 2


def test_material_event_classifier_does_not_treat_lawsuit_filing_as_regulatory_case() -> None:
    assert company_announcements._classify_material_event(
        "关于公司诉讼案件立案的公告",
        publish_date=date(2026, 7, 20),
        as_of=date(2026, 7, 28),
    ) is None


def test_unrelated_unfreeze_does_not_resolve_regulatory_investigation() -> None:
    classified = company_announcements._classify_material_event(
        "关于解除部分股份冻结暨收到证监会立案告知书的公告",
        publish_date=date(2026, 7, 20),
        as_of=date(2026, 7, 28),
    )
    assert classified is not None
    assert classified["event_type"] == "REGULATORY_INVESTIGATION"
    assert classified["event_status"] == "ACTIVE"
    assert classified["event_severity"] == "HIGH"


def test_material_event_classifier_returns_every_event_in_combined_notice() -> None:
    classified = company_announcements._classify_material_events(
        "关于撤销退市风险警示暨收到证监会立案告知书的公告",
        publish_date=date(2026, 7, 20),
        as_of=date(2026, 7, 28),
    )
    by_type = {row["event_type"]: row for row in classified}
    assert by_type["DELISTING_RISK"]["event_status"] == "RESOLVED"
    assert by_type["REGULATORY_INVESTIGATION"]["event_status"] == "ACTIVE"


@pytest.mark.parametrize(
    ("title", "event_type"),
    [
        ("关于公司被债权人申请破产重整的公告", "BANKRUPTCY_RESTRUCTURING"),
        ("关于公司实施其他风险警示的公告", "OTHER_RISK_WARNING"),
        ("关于控股股东非经营性资金占用的公告", "FUNDS_OCCUPATION"),
        ("关于累计诉讼、仲裁事项的公告", "MAJOR_LITIGATION_ARBITRATION"),
    ],
)
def test_material_event_classifier_covers_common_risk_families(title: str, event_type: str) -> None:
    classified = company_announcements._classify_material_events(
        title, publish_date=date(2026, 7, 20), as_of=date(2026, 7, 28),
    )
    assert event_type in {row["event_type"] for row in classified}


@pytest.mark.parametrize("title", [
    "非经营性资金占用及其他关联资金往来情况专项说明-容诚专字[2026]518Z0772号_报告",
    "年度关联方资金占用专项审计报告",
])
def test_routine_funds_occupation_review_title_is_not_an_active_event(title: str) -> None:
    classified = company_announcements._classify_material_events(
        title,
        publish_date=date(2026, 4, 20), as_of=date(2026, 7, 28),
    )
    assert "FUNDS_OCCUPATION" not in {row["event_type"] for row in classified}


def test_actual_controlling_shareholder_funds_occupation_is_high_and_active() -> None:
    classified = company_announcements._classify_material_events(
        "关于控股股东非经营性资金占用及整改进展的公告",
        publish_date=date(2026, 7, 20), as_of=date(2026, 7, 28),
    )
    event = next(row for row in classified if row["event_type"] == "FUNDS_OCCUPATION")
    assert event["event_status"] == "ACTIVE"
    assert event["event_severity"] == "HIGH"


def test_partial_share_unfreeze_remains_active() -> None:
    classified = company_announcements._classify_material_event(
        "关于控股股东部分股份解除冻结的公告",
        publish_date=date(2026, 7, 20), as_of=date(2026, 7, 28),
    )
    assert classified is not None
    assert classified["event_type"] == "SHARE_FREEZE"
    assert classified["event_status"] == "ACTIVE"
    assert classified["event_resolution_scope"] == "PARTIAL"


def test_material_event_representatives_collapse_progress_by_type() -> None:
    representatives = company_announcements._effective_material_event_representatives([
        {
            "event_type": "SHARE_FREEZE", "event_status": "ACTIVE",
            "event_severity": "MEDIUM", "publish_date": f"2026-07-{day:02d}",
            "url": f"https://example.test/freeze-{day}.pdf",
        }
        for day in range(1, 21)
    ])
    assert len(representatives) == 1
    assert representatives[0]["publish_date"] == "2026-07-20"


def test_cninfo_material_event_query_rejects_missing_response_schema() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class FakeSession:
        def post(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse()

    with pytest.raises(ValueError, match="response_schema_missing"):
        company_announcements._query_cninfo_material_events(
            "000088", "gssz0000088", date(2026, 7, 28), FakeSession(), timeout=5,
        )


def test_sse_material_event_query_rejects_missing_response_schema() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

    class FakeSession:
        def get(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse()

    with pytest.raises(ValueError, match="response_schema_missing"):
        company_announcements._query_sse_material_events(
            "600519", date(2026, 7, 28), FakeSession(), timeout=5,
        )


def test_material_event_query_caps_pagination_at_configured_limit() -> None:
    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeSession:
        pages: list[int] = []

        def post(self, _url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            page = int(data["pageNum"])
            self.pages.append(page)
            timestamp = int(
                datetime(2026, 7, 20, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            return FakeResponse({
                "totalAnnouncement": company_announcements.MATERIAL_EVENT_PAGE_SIZE * (
                    company_announcements.MATERIAL_EVENT_MAX_PAGES + 1
                ),
                "announcements": [
                    {
                        "announcementTitle": f"普通公告{page}-{index}",
                        "announcementTime": timestamp,
                        "adjunctUrl": f"finalpage/{page}-{index}.PDF",
                    }
                    for index in range(company_announcements.MATERIAL_EVENT_PAGE_SIZE)
                ],
            })

    session = FakeSession()
    rows, meta = company_announcements._query_cninfo_material_events(
        "000088", "gssz0000088", date(2026, 7, 28), session, timeout=5,
    )
    assert session.pages == list(range(1, company_announcements.MATERIAL_EVENT_MAX_PAGES + 1))
    assert len(rows) == (
        company_announcements.MATERIAL_EVENT_PAGE_SIZE
        * company_announcements.MATERIAL_EVENT_MAX_PAGES
    )
    assert meta["truncated"] is True


def test_cninfo_material_event_query_follows_provider_thirty_row_pages() -> None:
    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeSession:
        pages: list[int] = []

        def post(self, _url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            page = int(data["pageNum"])
            self.pages.append(page)
            assert data["pageSize"] == "30"
            count = 30 if page == 1 else 15
            timestamp = int(
                datetime(2026, 7, 20, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            return FakeResponse({
                "totalAnnouncement": 45,
                "announcements": [
                    {
                        "announcementTitle": f"普通公告{page}-{index}",
                        "announcementTime": timestamp,
                        "adjunctUrl": f"finalpage/{page}-{index}.PDF",
                    }
                    for index in range(count)
                ],
            })

    session = FakeSession()
    rows, meta = company_announcements._query_cninfo_material_events(
        "000088", "gssz0000088", date(2026, 7, 28), session, timeout=5,
    )
    assert session.pages == [1, 2]
    assert len(rows) == 45
    assert meta["pages_fetched"] == 2
    assert meta["reported_total"] == 45
    assert meta["truncated"] is False


def test_material_event_query_keeps_completed_pages_on_later_failure() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            timestamp = int(
                datetime(2026, 7, 20, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            return {
                "totalAnnouncement": company_announcements.MATERIAL_EVENT_PAGE_SIZE * 2,
                "announcements": [
                    {
                        "announcementTitle": f"普通公告{index}",
                        "announcementTime": timestamp,
                        "adjunctUrl": f"finalpage/{index}.PDF",
                    }
                    for index in range(company_announcements.MATERIAL_EVENT_PAGE_SIZE)
                ],
            }

    class FakeSession:
        def post(self, _url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            if data["pageNum"] == "2":
                raise RuntimeError("page two unavailable")
            return FakeResponse()

    rows, meta = company_announcements._query_cninfo_material_events(
        "000088", "gssz0000088", date(2026, 7, 28), FakeSession(), timeout=5,
    )
    assert len(rows) == company_announcements.MATERIAL_EVENT_PAGE_SIZE
    assert meta["pages_fetched"] == 1
    assert meta["truncated"] is True
    assert "page two unavailable" in meta["query_error"]


def test_partial_material_event_scan_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeSession:
        post_count = 0

        def get(self, url: str, **_kwargs) -> FakeResponse:
            assert url == company_announcements.CNINFO_STOCK_LIST_URL
            return FakeResponse({"stockList": [{"code": "000088", "orgId": "gssz0000088"}]})

        def post(self, _url: str, *, data: dict[str, str], **_kwargs) -> FakeResponse:
            FakeSession.post_count += 1
            if data["pageNum"] == "2":
                raise RuntimeError("transient page failure")
            timestamp = int(
                datetime(2026, 7, 20, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000
            )
            return FakeResponse({
                "totalAnnouncement": company_announcements.MATERIAL_EVENT_PAGE_SIZE * 2,
                "announcements": [
                    {
                        "announcementTitle": f"普通公告{index}",
                        "announcementTime": timestamp,
                        "adjunctUrl": f"finalpage/{index}.PDF",
                    }
                    for index in range(company_announcements.MATERIAL_EVENT_PAGE_SIZE)
                ],
            })

    monkeypatch.setattr(company_announcements.requests, "Session", FakeSession)
    cache = EvidenceCache(tmp_path / "cache")
    kwargs = {
        "rows": [{"code": "000088", "stock_name": "盐田港"}],
        "as_of": date(2026, 7, 28), "cache": cache, "limit": 1,
    }
    first = company_announcements.collect_company_material_events(**kwargs)
    second = company_announcements.collect_company_material_events(**kwargs)
    assert first[1][0]["status"] == "PARTIAL"
    assert second[1][0]["status"] == "PARTIAL"
    assert FakeSession.post_count == 4


def test_failed_material_event_scan_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"stockList": [{"code": "000088", "orgId": "gssz0000088"}]}

    class FakeSession:
        post_count = 0

        def get(self, url: str, **_kwargs) -> FakeResponse:
            assert url == company_announcements.CNINFO_STOCK_LIST_URL
            return FakeResponse()

        def post(self, *_args, **_kwargs) -> FakeResponse:
            FakeSession.post_count += 1
            raise RuntimeError("transient endpoint failure")

    monkeypatch.setattr(company_announcements.requests, "Session", FakeSession)
    cache = EvidenceCache(tmp_path / "cache")
    kwargs = {
        "rows": [{"code": "000088", "stock_name": "盐田港"}],
        "as_of": date(2026, 7, 28), "cache": cache, "limit": 1,
    }
    first = company_announcements.collect_company_material_events(**kwargs)
    second = company_announcements.collect_company_material_events(**kwargs)
    assert first[1][0]["status"] == "FAILED"
    assert second[1][0]["status"] == "FAILED"
    assert FakeSession.post_count == 2


def test_auto_evidence_summary_includes_material_event_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        evidence_collectors,
        "collect_company_announcements",
        lambda **_kwargs: ([], [], {
            "company_task_count": 1,
            "company_actual_fetch_count": 2,
            "company_fetch_success_count": 1,
        }),
    )
    monkeypatch.setattr(
        evidence_collectors,
        "collect_company_material_events",
        lambda **_kwargs: ([{
            "evidence_status": "VERIFIED", "event_status": "ACTIVE",
        }], [{"status": "OK"}], {
            "company_event_task_count": 1,
            "company_event_actual_fetch_count": 3,
            "company_event_document_fetch_success_count": 1,
            "company_event_evidence_rows": 1,
        }),
    )
    monkeypatch.setattr(
        evidence_collectors,
        "collect_public_industry_data",
        lambda **_kwargs: ([], [], {
            "industry_task_count": 1,
            "industry_actual_fetch_count": 4,
            "industry_fetch_success_count": 1,
        }),
    )

    _industry, company, audits, summary = evidence_collectors.collect_auto_evidence(
        priority_rows=[{"code": "000088", "normalized_industry": "港口"}],
        as_of=date(2026, 7, 28),
        cache_dir=tmp_path / "cache",
        max_companies=1,
    )
    assert company[0]["event_status"] == "ACTIVE"
    assert audits == [{"status": "OK"}]
    assert summary["task_count"] == 3
    assert summary["actual_fetch_count"] == 9
    assert summary["fetch_success_count"] == 3
    assert summary["company_event_evidence_rows"] == 1


def test_technology_sector_output_separates_core_and_extended_scope() -> None:
    quant_rows = [
        {"quant_rank": 1, "code": "002180", "stock_name": "奔图科技", "industry": "C39计算机、通信和其他电子设备制造业", "quant_status": "PRIORITY_RESEARCH"},
        {"quant_rank": 2, "code": "002268", "stock_name": "电科网安", "industry": "I65软件和信息技术服务业", "quant_status": "SECONDARY_RESEARCH"},
        {"quant_rank": 3, "code": "002129", "stock_name": "TCL中环", "industry": "C38电气机械和器材制造业", "quant_status": "PRIORITY_RESEARCH"},
        {"quant_rank": 4, "code": "000001", "stock_name": "平安银行", "industry": "J66货币金融服务", "quant_status": "LOW_PRIORITY"},
    ]
    deep_rows = [
        {
            "code": "002180",
            "quant_screen_status": "PRIORITY_RESEARCH",
            "industry_evidence_status": "MISSING",
            "company_evidence_status": "VERIFIED",
            "hard_logic_level": "WEAK",
        },
        {
            "code": "002129",
            "quant_screen_status": "HARD_REJECT",
            "hard_reject_blockers": "execution_risk_high",
            "industry_evidence_status": "MISSING",
            "company_evidence_status": "VERIFIED",
            "hard_logic_level": "WEAK",
        },
    ]

    sector_summary = {row["industry"]: row for row in build_sector_summary(quant_rows)}
    technology_rows = build_technology_sector_rows(quant_rows, deep_rows)
    by_code = {row["code"]: row for row in technology_rows}

    assert sector_summary["C39计算机、通信和其他电子设备制造业"]["priority_research_count"] == 1
    assert set(by_code) == {"002180", "002268", "002129"}
    assert by_code["002180"]["technology_scope"] == "CORE"
    assert by_code["002129"]["technology_scope"] == "EXTENDED"
    assert by_code["002129"]["research_status"] == "深度复核硬拒绝"
    assert by_code["002180"]["research_status"] == "行业证据不足，仅作研究观察"
    assert by_code["002268"]["research_status"] == "量化观察，未进入证据复核队列"


def test_public_data_homepage_number_is_not_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.strategies.genge_opportunity_discovery.evidence_collectors.public_data as public_data

    class FakeResponse:
        def __init__(self, html: str) -> None:
            self.content = html.encode("utf-8")
            self.headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, *_args, **_kwargs) -> FakeResponse:
            return FakeResponse("<html><body><p>有色 行业公开数据增长 100%</p></body></html>")

    monkeypatch.setattr(public_data.requests, "Session", lambda: FakeSession())

    evidence_rows, audit_rows, summary = public_data.collect_public_industry_data(
        industries=["有色"],
        as_of=date(2026, 7, 7),
        cache=EvidenceCache(tmp_path / "cache"),
    )

    assert evidence_rows == []
    assert summary["industry_evidence_rows"] == 0
    assert audit_rows
    assert {row["issue"] for row in audit_rows} == {"specific_article_not_found"}
    assert {row["status"] for row in audit_rows} == {"MISSING"}


def test_public_data_uses_configured_industry_alias_for_official_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.evidence_collectors.public_data as public_data

    class FakeResponse:
        def __init__(self, html: str) -> None:
            self.content = html.encode("utf-8")
            self.headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, **_kwargs) -> FakeResponse:
            if url.endswith("article.html"):
                return FakeResponse("<html><body>2026年6月30日 医疗器械行业产量增长 12%</body></html>")
            return FakeResponse('<html><body><a href="article.html">医疗器械行业运行数据</a></body></html>')

    monkeypatch.setattr(public_data.requests, "Session", lambda: FakeSession())
    monkeypatch.setattr(
        public_data,
        "PUBLIC_SOURCES",
        [("fixture_official", "https://official.example/index.html", "官方公开数据")],
    )

    evidence_rows, audit_rows, summary = public_data.collect_public_industry_data(
        industries=["医药", "UNRESOLVED"],
        as_of=date(2026, 7, 7),
        cache=EvidenceCache(tmp_path / "cache"),
        industry_alias_map={"industries": {"医药": {"aliases": ["医疗器械"]}}},
    )

    assert audit_rows == []
    assert summary["industry_task_count"] == 1
    assert summary["industry_evidence_rows"] == 1
    assert evidence_rows[0]["industry"] == "医药"
    assert evidence_rows[0]["evidence_status"] == "VERIFIED"
    assert "匹配词：医疗器械" in evidence_rows[0]["normalized_summary"]


def test_nbs_cross_industry_report_extracts_split_table_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.evidence_collectors.public_data as public_data

    class FakeResponse:
        headers = {"content-type": "text/html; charset=utf-8"}

        def __init__(self, html: str) -> None:
            self.content = html.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, **_kwargs) -> FakeResponse:
            if url.endswith("article.html"):
                return FakeResponse("<html><body>2026年7月15日 医药制造业<br/>…<br/>6.7<br/>…<br/>5.6</body></html>")
            return FakeResponse('<html><body><a href="article.html">2026年6月份规模以上工业增加值增长5.3%</a></body></html>')

    monkeypatch.setattr(public_data.requests, "Session", lambda: FakeSession())
    monkeypatch.setattr(
        public_data,
        "PUBLIC_SOURCES",
        [("nbs_public_data", "https://www.stats.gov.cn/index.html", "国家统计局")],
    )

    evidence_rows, _audit_rows, summary = public_data.collect_public_industry_data(
        industries=["医药"],
        as_of=date(2026, 7, 22),
        cache=EvidenceCache(tmp_path / "cache"),
        industry_alias_map={"industries": {"医药": {"aliases": ["医药制造业"]}}},
    )

    assert summary["industry_evidence_rows"] == 1
    assert evidence_rows[0]["value"] == "6.7"
    assert evidence_rows[0]["direction"] == "POSITIVE"
    assert evidence_rows[0]["source_type"] == "OFFICIAL_REPORT"


def test_public_data_uses_specialized_official_json_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.evidence_collectors.public_data as public_data

    class FakeResponse:
        def __init__(self, *, html: str = "", payload: dict | None = None) -> None:
            self.content = html.encode("utf-8")
            self.headers = {"content-type": "application/json" if payload is not None else "text/html"}
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            assert self._payload is not None
            return self._payload

    class FakeSession:
        def get(self, url: str, **_kwargs) -> FakeResponse:
            if url.endswith("article.shtml"):
                return FakeResponse(html="2026年7月17日 快递业务量完成1003.8亿件，同比增长5.0%")
            return FakeResponse(
                payload={
                    "data": {
                        "results": [
                            {
                                "title": "全市快递员工作会议召开",
                                "url": "https://official.example/meeting.shtml",
                            },
                            {
                                "title": "2026年上半年快递业务量运行情况",
                                "url": "https://official.example/article.shtml",
                            }
                        ]
                    }
                }
            )

    monkeypatch.setattr(public_data.requests, "Session", lambda: FakeSession())
    monkeypatch.setattr(public_data, "PUBLIC_SOURCES", [])
    monkeypatch.setattr(
        public_data,
        "SPECIALIZED_PUBLIC_SOURCES",
        {"物流": [("spb_public_data", "https://official.example/search", "官方行业数据")]},
    )

    evidence_rows, audit_rows, summary = public_data.collect_public_industry_data(
        industries=["物流"],
        as_of=date(2026, 7, 20),
        cache=EvidenceCache(tmp_path / "cache"),
        industry_alias_map={"industries": {"物流": {"aliases": ["快递"]}}},
    )

    assert audit_rows == []
    assert summary["industry_task_count"] == 1
    assert evidence_rows[0]["industry"] == "物流"
    assert evidence_rows[0]["publish_date"] == "2026-07-17"
    assert evidence_rows[0]["source_domain"] == "official.example"
    assert evidence_rows[0]["evidence_status"] == "VERIFIED"
    assert evidence_rows[0]["title"] == "2026年上半年快递业务量运行情况"


def test_transport_public_data_accepts_official_mot_subdomain_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.evidence_collectors.public_data as public_data

    class FakeResponse:
        headers = {"content-type": "text/html; charset=utf-8"}

        def __init__(self, html: str) -> None:
            self.content = html.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, **_kwargs) -> FakeResponse:
            if "xxgk.mot.gov.cn" in url:
                return FakeResponse("2026年7月22日 上半年完成水路货运量42.3亿吨，同比增长3.9%")
            return FakeResponse(
                '<a href="https://xxgk.mot.gov.cn/report.html">2026年上半年交通运输经济运行情况</a>'
            )

    monkeypatch.setattr(public_data.requests, "Session", lambda: FakeSession())
    monkeypatch.setattr(public_data, "PUBLIC_SOURCES", [])

    evidence_rows, audit_rows, summary = public_data.collect_public_industry_data(
        industries=["航运"],
        as_of=date(2026, 7, 23),
        cache=EvidenceCache(tmp_path / "cache"),
        industry_alias_map={"industries": {"航运": {"aliases": ["水路货运"]}}},
    )

    assert audit_rows == []
    assert summary["industry_evidence_rows"] == 1
    assert evidence_rows[0]["direction"] == "POSITIVE"
    assert evidence_rows[0]["source_domain"] == "xxgk.mot.gov.cn"


def test_production_alias_map_resolves_shipping_and_water_supply_industries() -> None:
    resolver = IndustryAliasResolver(load_industry_alias_map("config/industry_alias_map.yaml"))

    shipping = resolver.resolve(code="000088", stock_name="盐田港", raw_industry="G55水上运输业")
    water = resolver.resolve(code="601158", stock_name="重庆水务", raw_industry="D46水的生产和供应业")

    assert shipping.normalized_industry == "航运"
    assert shipping.match_type == "SUBSTRING_ALIAS"
    assert water.normalized_industry == "水务"
    assert water.match_type == "SUBSTRING_ALIAS"


def test_opportunity_discovery_writes_research_outputs_and_forward_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    exit_profiles = pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}])
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(company_rows=_auto_company_evidence(evidence_date="2026-06-10")),
    )

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=exit_profiles,
        ledger_path=tmp_path / "ledger.csv",
        state_dir=tmp_path / "state",
    )

    assert summary["valid_stocks"] == 1
    assert "PASS_QUANT_RESEARCH_QUEUE_GENERATED" in summary["acceptance_milestones"]
    assert "PASS_EVIDENCE_TASKS_GENERATED" in summary["acceptance_milestones"]
    assert "PASS_AUTO_EVIDENCE_COLLECTION_READY" in summary["acceptance_milestones"]
    assert (report_dir / "priority_research_queue.csv").exists()
    assert (report_dir / "evidence_gap_report.csv").exists()
    assert (report_dir / "evidence_inventory.csv").exists()
    assert (report_dir / "auto_evidence_audit.csv").exists()
    assert (report_dir / "industry_research_tasks.json").exists()
    assert (report_dir / "company_research_tasks.json").exists()
    assert (report_dir / "forward_observation_ledger.csv").exists()
    assert summary["provider_distribution"] == {"fixture": 1}
    assert summary["auto_evidence_verified_count"] == 1
    assert "opportunity_quality_top20" in summary
    assert "opportunity_proximity_top20" in summary

    tier_files = ["tier_a_candidates.csv", "tier_b_watchlist.csv", "tier_c_evidence_incomplete.csv"]
    tier_rows = []
    for file_name in tier_files:
        tier_rows.extend(csv.DictReader((report_dir / file_name).open(encoding="utf-8")))
    assert len(tier_rows) == 1
    assert tier_rows[0]["code"] == "000100"
    assert "BUY" not in tier_rows[0]["research_label"]
    assert "SELL" not in tier_rows[0]["research_label"]
    assert tier_rows[0]["opportunity_logic"]
    assert tier_rows[0]["top_risks"]
    assert tier_rows[0]["upgrade_conditions"]
    assert tier_rows[0]["downgrade_conditions"]

    evidence_rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    required_columns = {
        "evidence_date",
        "collected_at",
        "industry",
        "indicator",
        "value",
        "direction",
        "source",
        "source_type",
        "confidence",
        "freshness_days",
        "raw_excerpt",
        "normalized_summary",
        "parser",
        "parse_status",
        "evidence_status",
        "warning_flags",
    }
    assert required_columns.issubset(evidence_rows[0].keys())
    assert any(row["evidence_status"] == "PARSE_FAILED" for row in evidence_rows)
    assert any(row["evidence_status"] == "VERIFIED" and row["content_hash"] for row in evidence_rows)
    assert any("future_dated_evidence_excluded" in row["warning_flags"] for row in evidence_rows)

    quality_rows = list(csv.DictReader((report_dir / "data_quality_audit.csv").open(encoding="utf-8")))
    assert any(row["issue"] == "future_dated_evidence_excluded" for row in quality_rows)


def test_exit_profile_not_available_cannot_enter_tier_a(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    assert list(csv.DictReader((report_dir / "tier_a_candidates.csv").open(encoding="utf-8"))) == []
    watch_rows = list(csv.DictReader((report_dir / "tier_b_watchlist.csv").open(encoding="utf-8")))
    incomplete_rows = list(csv.DictReader((report_dir / "tier_c_evidence_incomplete.csv").open(encoding="utf-8")))
    combined = watch_rows + incomplete_rows
    assert combined
    assert "balanced_exit_profile_not_available" in combined[0]["soft_blockers"]


def test_missing_evidence_goes_to_gap_report_not_silent_drop(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=pd.DataFrame(),
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    assert summary["valid_stocks"] == 1
    gap_rows = list(csv.DictReader((report_dir / "evidence_gap_report.csv").open(encoding="utf-8")))
    assert gap_rows
    tier_c = list(csv.DictReader((report_dir / "tier_c_evidence_incomplete.csv").open(encoding="utf-8")))
    assert tier_c
    assert tier_c[0]["missing_evidence"]


def test_existing_ledger_does_not_upgrade_without_current_tier_a_or_b(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    ledger_path = tmp_path / "ledger.csv"
    ledger_path.write_text(
        "code,stock_name,industry,first_observation_date,first_tier,first_close,first_quant_score,"
        "first_evidence_status,rule_version,data_version,first_snapshot_json,latest_observation_date,"
        "latest_tier,latest_close,return_5d_pct,return_10d_pct,return_20d_pct,return_40d_pct,"
        "return_60d_pct,max_up_pct,max_down_pct,benchmark_return_20d_pct,status\n"
        "000999,旧观察,面板,2026-06-01,TIER_B,10,60,VERIFIED/VERIFIED,v1,fixture,{},"
        "2026-06-01,TIER_B,10,,,,,,,,OPEN\n",
        encoding="utf-8",
    )

    _report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=pd.DataFrame(),
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=ledger_path,
        run_mode="full",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    assert summary["forward_observation"]["tracked_count"] == 1
    assert summary["forward_observation"]["observed_tier_a_b_count"] == 0
    assert "PASS_FORWARD_OBSERVATION_READY" not in summary["acceptance_milestones"]
    assert summary["acceptance_enum"] == "PASS_EVIDENCE_TASKS_GENERATED"


def test_conflicting_and_stale_evidence_are_audited(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    industry_evidence = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "价格上涨 3%",
                "evidence_direction": "POSITIVE",
                "source": "官方公开数据",
                "source_type": "official_report",
            },
            {
                "date": "2025-01-02",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "价格下跌 2%",
                "evidence_direction": "NEGATIVE",
                "source": "交易所披露",
                "source_type": "exchange_disclosure",
            },
            {
                "date": "2024-01-01",
                "industry": "面板",
                "evidence_name": "库存水位",
                "evidence_value": "库存处于历史低位 1",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "research_report_summary",
            },
        ]
    )

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=industry_evidence,
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    evidence_rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    statuses = {row["indicator"]: row["evidence_status"] for row in evidence_rows}
    assert statuses["面板价格"] == "CONFLICTING"
    assert statuses["库存水位"] == "STALE"
    assert any("conflicting_evidence" in row["warning_flags"] for row in evidence_rows)


def test_single_stock_failure_does_not_block_other_outputs(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100", "000999"],
        data_errors={"000999": "RuntimeError: provider unavailable"},
        data_sources={"000100": "fixture", "000999": "failed"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
        run_mode="quant-only",
        state_dir=tmp_path / "state",
    )

    assert summary["total_stocks"] == 2
    assert summary["valid_stocks"] == 1
    assert summary["data_failure_count"] == 1
    quality_rows = list(csv.DictReader((report_dir / "data_quality_audit.csv").open(encoding="utf-8")))
    assert any(row["code"] == "000999" and row["issue"] == "data_error" for row in quality_rows)


def test_manual_authoritative_source_is_capped_at_partially_verified(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence().iloc[:1],
        company_evidence_df=_company_evidence().iloc[:1],
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    assert rows
    assert "VERIFIED" not in {row["evidence_status"] for row in rows}
    assert any(row["evidence_status"] == "PARTIALLY_VERIFIED" for row in rows)
    assert any("user_supplied_authoritative_label_capped_at_partial" in row["warning_flags"] for row in rows)


def test_exit_profile_status_controls_tier_a_for_non_sample_stock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    code = "600123"
    stock_name = "测试周期"
    industry = "有色"
    industry_evidence = pd.DataFrame(
        [
            {
                "date": "2026-06-15",
                "industry": industry,
                "evidence_name": "金属价格",
                "evidence_value": "公开原文显示价格增长 6%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry",
            },
            {
                "date": "2026-06-16",
                "industry": industry,
                "evidence_name": "库存",
                "evidence_value": "库存下降 10%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official2.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry2",
            },
            {
                "date": "2026-06-17",
                "industry": industry,
                "evidence_name": "加工费",
                "evidence_value": "加工费改善 3%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official3.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry3",
            },
        ]
    )
    company_rows = _auto_company_evidence(code=code, stock_name=stock_name, industry=industry)
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(company_rows=company_rows),
    )

    for status, should_enter_a in {
        "PASSED": True,
        "NOT_AVAILABLE": False,
        "DEGRADED": False,
        "FAILED": False,
    }.items():
        report_dir, _summary = run_opportunity_discovery(
            inputs=[_input(code=code, stock_name=stock_name, industry=industry)],
            requested_codes=[code],
            data_errors={},
            data_sources={code: "fixture"},
            benchmark_df=_price_frame(),
            industry_cycle_df=None,
            industry_evidence_df=industry_evidence,
            company_evidence_df=pd.DataFrame(),
            industry_evidence_schema=schema,
            industry_alias_map=alias_map,
            requested_as_of_date="2026-06-24",
            output_dir=tmp_path / f"reports_{status}",
            diagnostics={
                "requested_stock_records": [{"code": code, "stock_name": stock_name, "industry": industry}],
                "source_mode": "fixture",
            },
            exit_profile_df=pd.DataFrame([{"code": code, "balanced_exit_historical_profile": status}]),
            ledger_path=tmp_path / f"ledger_{status}.csv",
            state_dir=tmp_path / f"state_{status}",
        )
        tier_a_rows = list(csv.DictReader((report_dir / "tier_a_candidates.csv").open(encoding="utf-8")))
        assert bool(tier_a_rows) is should_enter_a


def test_run_modes_execute_different_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    calls = {"count": 0}

    def fake_collect(**kwargs):
        calls["count"] += 1
        return _fake_auto_collector()(**kwargs)

    monkeypatch.setattr("src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence", fake_collect)
    common = {
        "inputs": [_input()],
        "requested_codes": ["000100"],
        "data_errors": {},
        "data_sources": {"000100": "fixture"},
        "benchmark_df": _price_frame(),
        "industry_cycle_df": None,
        "industry_evidence_df": _industry_evidence(),
        "company_evidence_df": _company_evidence(),
        "industry_evidence_schema": schema,
        "industry_alias_map": alias_map,
        "requested_as_of_date": "2026-06-24",
        "diagnostics": _diagnostics(),
        "exit_profile_df": pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
    }

    q_dir, q_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "quant_only",
        run_mode="quant-only",
        ledger_path=tmp_path / "quant_only_ledger.csv",
        state_dir=tmp_path / "state_quant",
    )
    assert calls["count"] == 0
    assert q_summary["stages_executed"] == ["quant_screen", "research_queue"]
    assert not (tmp_path / "quant_only_ledger.csv").exists()
    assert list(csv.DictReader((q_dir / "tier_a_candidates.csv").open(encoding="utf-8"))) == []

    qe_dir, qe_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "quant_evidence",
        run_mode="quant-evidence",
        ledger_path=tmp_path / "quant_evidence_ledger.csv",
        state_dir=tmp_path / "state_qe",
    )
    assert calls["count"] == 1
    assert "auto_evidence_collection" in qe_summary["stages_executed"]
    assert "forward_ledger_update" not in qe_summary["stages_executed"]
    assert not (tmp_path / "quant_evidence_ledger.csv").exists()
    assert (qe_dir / "evidence_inventory.csv").exists()

    full_dir, full_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "full",
        run_mode="full",
        ledger_path=tmp_path / "full_ledger.csv",
        state_dir=tmp_path / "state_full",
    )
    assert calls["count"] == 2
    assert "forward_ledger_update" in full_summary["stages_executed"]
    assert (tmp_path / "full_ledger.csv").exists()
    assert (full_dir / "forward_observation_ledger.csv").exists()


def test_forward_ledger_preserves_first_observation_and_updates_returns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(),
    )
    ledger_path = tmp_path / "ledger.csv"

    report_1, _summary_1 = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-18",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state",
    )
    rows_1 = list(csv.DictReader((report_1 / "forward_observation_ledger.csv").open(encoding="utf-8")))
    assert len(rows_1) == 1
    assert rows_1[0]["first_observation_date"] == "2026-06-18"

    report_2, summary_2 = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state",
    )
    rows_2 = list(csv.DictReader((report_2 / "forward_observation_ledger.csv").open(encoding="utf-8")))
    assert len(rows_2) == 1
    assert rows_2[0]["first_observation_date"] == "2026-06-18"
    assert rows_2[0]["return_5d_pct"] != ""
    assert summary_2["previous_state_restored"] is True


def test_forward_ledger_closes_downgraded_observation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(),
    )
    ledger_path = tmp_path / "ledger.csv"

    run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-18",
        output_dir=tmp_path / "reports_1",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state_1",
    )

    report_2, _summary_2 = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports_2",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "FAILED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state_2",
    )

    rows = list(csv.DictReader((report_2 / "forward_observation_ledger.csv").open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["status"] == "CLOSED"
    assert rows[0]["latest_tier"] == "REJECTED"
    assert rows[0]["closed_date"] == "2026-06-24"
    assert "balanced_exit_profile_failed" in rows[0]["close_reason"]
    assert rows[0]["logic_invalidated"] == "True"
    assert rows[0]["latest_close"] != ""


def test_exit_profile_generation_from_historical_signal_details(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "sample" / "signal_details.csv"
    report.parent.mkdir(parents=True)
    rows = ["code,stock_name,as_of_date,balanced_hybrid_60d_exit_exit_adjusted_net_return_60d,balanced_hybrid_60d_exit_exit_adjusted_max_drawdown_250d"]
    dates = [item.date().isoformat() for item in pd.bdate_range(end="2026-06-30", periods=20)]
    rows.extend([f"600123,测试周期,{trade_date},2.5,-8" for trade_date in dates])
    rows.append(f"600123,测试周期,{dates[-1]},2.5,-8")  # copied duplicate must not inflate n
    rows.extend([f"600456,测试退化,{trade_date},1.0,-12" for trade_date in dates[:6]])
    rows.extend([f"600456,测试退化,{trade_date},-2.0,-14" for trade_date in dates[6:12]])
    rows.extend([f"600111,样本不足,{trade_date},3.0,-7" for trade_date in dates[:8]])
    rows.extend([f"600789,测试失败,{trade_date},-9,-25" for trade_date in dates])
    report.write_text("\n".join(rows) + "\n", encoding="utf-8")
    output, summary = generate_exit_profile_from_reports(output_file=tmp_path / "exit_profile.csv", source_dirs=[tmp_path / "reports"])
    rows = {row["code"]: row for row in csv.DictReader(output.open(encoding="utf-8"))}
    assert summary["row_count"] == 4
    assert rows["600123"]["balanced_exit_historical_profile"] == "PASSED"
    assert rows["600456"]["balanced_exit_historical_profile"] == "DEGRADED"
    assert rows["600111"]["balanced_exit_historical_profile"] == "NOT_AVAILABLE"
    assert rows["600789"]["balanced_exit_historical_profile"] == "FAILED"
    assert int(rows["600123"]["signal_count"]) == 20
    assert int(rows["600111"]["signal_count"]) == 8
    assert rows["600123"]["profile_data_end_date"] != ""
    assert rows["600123"]["profile_rule_version"] == REPORT_AGGREGATE_RULE_VERSION
    assert rows["600123"]["profile_data_version"].startswith("sha256:")
    assert rows["600123"]["profile_confidence"] == "LOW"
    assert int(rows["600123"]["recent_2y_sample_count"]) > 0


def test_proximity_rank_excludes_hard_risk_rejects() -> None:
    rows = _rank_opportunities(
        [
            {
                "code": "600001",
                "tier": "TIER_B",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 2,
                "opportunity_quality_score": 60,
                "quant_score": 70,
                "hard_blockers": "",
            },
            {
                "code": "600002",
                "tier": "TIER_C",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 1,
                "opportunity_quality_score": 55,
                "quant_score": 65,
                "hard_blockers": "",
            },
            {
                "code": "600003",
                "tier": "REJECTED",
                "quant_screen_status": "HARD_REJECT",
                "a_condition_fail_count": 0,
                "opportunity_quality_score": 80,
                "quant_score": 90,
                "hard_blockers": "financial_safety_failed",
            },
            {
                "code": "600004",
                "tier": "TIER_B",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 0,
                "opportunity_quality_score": 80,
                "quant_score": 90,
                "hard_blockers": "balanced_exit_profile_failed",
            },
        ]
    )
    by_code = {row["code"]: row for row in rows}
    assert by_code["600002"]["opportunity_proximity_rank"] == 1
    assert by_code["600001"]["opportunity_proximity_rank"] == 2
    assert by_code["600003"]["opportunity_proximity_rank"] == ""
    assert by_code["600004"]["opportunity_proximity_rank"] == ""


def test_evidence_cache_reuses_unexpired_payload(tmp_path: Path) -> None:
    cache = EvidenceCache(tmp_path / "cache", ttl_days=14)
    key = cache.key_for({"collector": "fixture", "code": "600123"})
    assert cache.get(key) is None
    cache.set(key, {"evidence_rows": [{"code": "600123"}], "audit_rows": []})
    cached = cache.get(key)
    assert cached is not None
    assert cached["cache_hit"] is True
    assert cached["evidence_rows"][0]["code"] == "600123"
    assert cache.cache_hits == 1


def test_tomorrow_watchlist_writes_conditional_price_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(),
    )
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.tomorrow_watchlist.fetch_unadjusted_history",
        lambda *_args, **_kwargs: _price_frame(),
    )
    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=tmp_path / "ledger.csv",
        state_dir=tmp_path / "state",
    )

    output_dir, watch_summary = generate_tomorrow_watchlist(
        opportunity_report_dir=report_dir,
        output_dir=tmp_path / "tomorrow_watchlist",
        as_of="2026-06-24",
        tomorrow="2026-06-25",
    )

    for file_name in [
        "tomorrow_watchlist.md",
        "tomorrow_watchlist.csv",
        "buy_sell_price_plan.csv",
        "buy_sell_price_plan.json",
        "evidence_review.md",
        "data_quality_audit.csv",
        "run_summary.json",
    ]:
        assert (output_dir / file_name).exists()
    rows = list(csv.DictReader((output_dir / "buy_sell_price_plan.csv").open(encoding="utf-8")))
    assert rows
    row = rows[0]
    entry = float(row["initial_entry_high"])
    assert float(row["technical_stop_price"]) < entry
    assert float(row["logic_invalidation_price"]) <= float(row["technical_stop_price"])
    assert float(row["target_1_price"]) > entry
    assert float(row["target_2_price"]) > float(row["target_1_price"])
    assert float(row["reward_risk_ratio"]) >= 1.0
    assert row["latest_trade_date"] == "2026-06-24"
    assert row["data_warnings"] == ""
    assert watch_summary["no_broker_integration"] is True


def test_wait_for_breakout_targets_use_breakout_entry_price() -> None:
    ctx = PriceContext(
        latest_trade_date=date(2026, 7, 7),
        latest_close=7.07,
        atr14=0.24,
        ma20=7.30,
        ma60=8.51,
        support_20d=6.66,
        support_60d=6.66,
        resistance_20d=7.85,
        resistance_60d=10.33,
        local_low=6.66,
        local_high=7.50,
        avg_volume_20d=900_000,
        latest_volume=800_000,
    )
    row = {
        "tier": "TIER_C",
        "hard_blockers": "",
        "industry_evidence_status": "PARTIALLY_VERIFIED",
        "company_evidence_status": "PARTIALLY_VERIFIED",
        "hard_logic_level": "NONE",
        "balanced_exit_historical_profile": "DEGRADED",
        "a_condition_failed": "trend_medium;hard_logic_medium",
    }

    plan = _plan_prices(row, ctx, ["https://example.com/evidence"])
    breakout = float(plan["breakout_trigger_price"])
    stop = float(plan["technical_stop_price"])
    target1 = float(plan["target_1_price"])
    target2 = float(plan["target_2_price"])

    assert plan["tomorrow_status"] == "WAIT_FOR_BREAKOUT"
    assert target1 > breakout
    assert target2 > target1
    assert float(plan["reward_risk_ratio"]) == round((target2 - breakout) / (breakout - stop), 2)


def test_shenzhen_universe_uses_official_board_fields() -> None:
    raw = pd.DataFrame(
        [
            {"板块": "主板", "A股代码": 1, "A股简称": "平安银行", "A股上市日期": "1991-04-03", "所属行业": "J 金融业"},
            {"板块": "创业板", "A股代码": 300001, "A股简称": "特锐德", "A股上市日期": "2009-10-30", "所属行业": "C 制造业"},
            {"板块": "主板", "A股代码": 5, "A股简称": "ST星源", "A股上市日期": "1990-12-10", "所属行业": "K 房地产"},
        ]
    )

    rows, counts = build_official_universe(raw, as_of=date(2026, 7, 7))

    by_code = {row["code"]: row for row in rows}
    assert counts["raw_security_count"] == 3
    assert counts["excluded_chinext_count"] == 1
    assert counts["shenzhen_mainboard_a_count"] == 2
    assert by_code["000001"]["board"] == "主板"
    assert by_code["000005"]["exclusion_reason"] == "st_or_delisting_risk"
    assert "300001" not in by_code


def test_shenzhen_universe_enriches_structured_industry_without_changing_scope() -> None:
    rows = [
        {
            "code": "000001",
            "stock_name": "平安银行",
            "exchange": "SZSE",
            "board": "主板",
            "industry": "J 金融业",
            "industry_source": "SZSE ShowReport 所属行业",
            "industry_update_date": "",
        },
        {
            "code": "000002",
            "stock_name": "万科A",
            "exchange": "SZSE",
            "board": "主板",
            "industry": "K 房地产",
            "industry_source": "SZSE ShowReport 所属行业",
            "industry_update_date": "",
        },
    ]
    enriched, count = enrich_universe_industries(
        rows,
        {
            "000001": {
                "industry": "J66货币金融服务",
                "update_date": "2026-07-06",
            }
        },
    )

    assert count == 1
    assert len(enriched) == len(rows)
    assert enriched[0]["industry"] == "J66货币金融服务"
    assert enriched[0]["industry_source"] == "baostock.query_stock_industry"
    assert enriched[0]["industry_update_date"] == "2026-07-06"
    assert enriched[1]["industry"] == "K 房地产"


def test_shenzhen_recent_snapshot_fallback_resets_runtime_exclusions(tmp_path: Path) -> None:
    pool_dir = tmp_path / "stock_pools"
    report_root = tmp_path / "reports"
    pool_dir.mkdir()
    report_dir = report_root / "20260713"
    report_dir.mkdir(parents=True)
    pool_path = pool_dir / "shenzhen_mainboard_a_full_20260710.csv"
    fieldnames = [
        "code",
        "stock_name",
        "exchange",
        "board",
        "security_type",
        "listing_status",
        "listing_date",
        "is_st",
        "is_suspended",
        "latest_trade_date",
        "latest_close",
        "avg_turnover_20d",
        "industry",
        "industry_source",
        "industry_update_date",
        "universe_source",
        "exclusion_reason",
    ]
    with pool_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {
                    "code": "000001",
                    "stock_name": "平安银行",
                    "exchange": "SZSE",
                    "board": "主板",
                    "security_type": "A_SHARE",
                    "listing_status": "listed",
                    "listing_date": "1991-04-03",
                    "is_st": "False",
                    "is_suspended": "False",
                    "latest_trade_date": "2026-07-10",
                    "latest_close": "10.0",
                    "avg_turnover_20d": "100000000",
                    "industry": "J66货币金融服务",
                    "industry_source": "baostock.query_stock_industry",
                    "industry_update_date": "2026-07-06",
                    "universe_source": "SZSE",
                    "exclusion_reason": "insufficient_history",
                },
                {
                    "code": "000005",
                    "stock_name": "ST测试",
                    "exchange": "SZSE",
                    "board": "主板",
                    "security_type": "A_SHARE",
                    "listing_status": "listed",
                    "listing_date": "1990-12-10",
                    "is_st": "True",
                    "is_suspended": "False",
                    "latest_trade_date": "2026-07-10",
                    "latest_close": "2.0",
                    "avg_turnover_20d": "50000000",
                    "industry": "C 制造业",
                    "industry_source": "baostock.query_stock_industry",
                    "industry_update_date": "2026-07-06",
                    "universe_source": "SZSE",
                    "exclusion_reason": "st_or_delisting_risk",
                },
            ]
        )
    (report_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "as_of_date": "2026-07-10",
                "raw_security_count": 2895,
                "excluded_chinext_count": 1399,
                "excluded_st_or_delist_count": 84,
                "excluded_listing_after_as_of_count": 0,
            }
        ),
        encoding="utf-8",
    )

    rows, counts, diagnostics = load_recent_universe_snapshot(
        as_of=date(2026, 7, 10),
        stock_pool_dir=pool_dir,
        report_root=report_root,
    )

    by_code = {row["code"]: row for row in rows}
    assert counts["raw_security_count"] == 2895
    assert diagnostics["listing_fallback_age_days"] == 0
    assert diagnostics["listing_source"].startswith("repository_snapshot:")
    assert by_code["000001"]["exclusion_reason"] == ""
    assert by_code["000001"]["latest_trade_date"] == ""
    assert by_code["000005"]["exclusion_reason"] == "st_or_delisting_risk"


def test_shenzhen_quant_screen_and_price_plan_are_actionable(tmp_path: Path) -> None:
    history = _price_frame().tail(900).copy()
    history["amount"] = history["close"] * history["volume"] * 100
    config = ScanConfig(
        as_of=date(2026, 6, 24),
        tomorrow=date(2026, 6, 25),
        output_dir=tmp_path / "out",
        stock_pool_output=tmp_path / "pool.csv",
    )
    universe = [
        {
            "code": "000001",
            "stock_name": "平安银行",
            "industry": "银行",
            "latest_trade_date": "2026-06-24",
            "latest_close": 11.8,
            "avg_turnover_20d": 50_000_000,
            "exclusion_reason": "",
        }
    ]

    rows = quant_screen(universe, {"000001": history}, history, config)
    plan = build_price_plan(
        {
            "code": "000001",
            "stock_name": "平安银行",
            "trend_confirmation_level": "WEAK",
            "industry_evidence_status": "PARTIALLY_VERIFIED",
            "company_evidence_status": "PARTIALLY_VERIFIED",
            "balanced_exit_historical_profile": "PASSED",
        },
        history,
        ["https://example.com/evidence"],
    )

    assert rows and rows[0]["quant_rank"] == 1
    assert rows[0]["code"] == "000001"
    assert float(plan["breakout_stop_price"]) < float(plan["breakout_trigger_price"])
    if plan["pullback_status"] == "READY":
        pullback_entry = float(plan["pullback_entry_high"])
        pullback_stop = float(plan["pullback_stop_price"])
        pullback_target = float(plan["pullback_target_1"])
        assert pullback_stop < pullback_entry < pullback_target
        assert float(plan["pullback_real_reward_risk"]) == round(
            (pullback_target - pullback_entry) / (pullback_entry - pullback_stop),
            2,
        )
    breakout_entry = float(plan["breakout_trigger_price"])
    breakout_stop = float(plan["breakout_stop_price"])
    breakout_target = float(plan["breakout_target_1"])
    assert float(plan["breakout_real_reward_risk"]) == round(
        (breakout_target - breakout_entry) / (breakout_entry - breakout_stop),
        2,
    )
    preferred = str(plan["preferred_plan"])
    assert plan["real_resistance_target_1"] == plan[f"{preferred}_target_1"]
    assert plan["real_resistance_target_2"] == plan[f"{preferred}_target_2"]
    assert plan["real_reward_risk_ratio"] == plan[f"{preferred}_real_reward_risk"]
    assert plan["theoretical_target_1"] != plan["real_resistance_target_1"]


def test_near_ready_uses_risk_conditions_when_industry_or_exit_history_is_missing() -> None:
    row = {
        "hard_blockers": "",
        "valuation_score": 60,
        "financial_safety_score": 45,
        "industry_evidence_status": "MISSING",
        "company_evidence_status": "VERIFIED",
        "balanced_exit_historical_profile": "NOT_AVAILABLE",
        "hard_logic_level": "WEAK",
        "trend_confirmation_level": "WEAK",
        "price_percentile_5y": 0.1384,
    }
    plan = {
        "real_reward_risk_ratio": 1.11,
        "pullback_status": "REAL_RR_BELOW_1_8",
        "breakout_status": "REAL_RR_BELOW_1_8",
    }

    classification, status = classify_candidate(
        row,
        plan,
        ["https://example.com/company-report.pdf"],
        Counter(),
    )

    assert classification == "NEAR_READY"
    assert status == "WAIT_FOR_BREAKOUT"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hard_blockers", "financial_risk"),
        ("valuation_score", 39),
        ("financial_safety_score", 39),
        ("company_evidence_status", "MISSING"),
        ("trend_confirmation_level", "NONE"),
        ("price_percentile_5y", 0.51),
    ],
)
def test_near_ready_does_not_relax_risk_controls(field: str, value: object) -> None:
    row = {
        "hard_blockers": "",
        "valuation_score": 60,
        "financial_safety_score": 60,
        "industry_evidence_status": "MISSING",
        "company_evidence_status": "VERIFIED",
        "balanced_exit_historical_profile": "NOT_AVAILABLE",
        "hard_logic_level": "WEAK",
        "trend_confirmation_level": "WEAK",
        "price_percentile_5y": 0.20,
    }
    row[field] = value
    plan = {
        "real_reward_risk_ratio": 1.20,
        "pullback_status": "REAL_RR_BELOW_1_8",
        "breakout_status": "REAL_RR_BELOW_1_8",
    }

    classification, _status = classify_candidate(
        row,
        plan,
        ["https://example.com/company-report.pdf"],
        Counter(),
    )

    assert classification != "NEAR_READY"


def test_near_ready_requires_minimum_real_reward_risk_and_evidence_url() -> None:
    row = {
        "hard_blockers": "",
        "valuation_score": 60,
        "financial_safety_score": 60,
        "industry_evidence_status": "MISSING",
        "company_evidence_status": "VERIFIED",
        "balanced_exit_historical_profile": "NOT_AVAILABLE",
        "hard_logic_level": "WEAK",
        "trend_confirmation_level": "MEDIUM",
        "price_percentile_5y": 0.20,
    }
    plan = {
        "real_reward_risk_ratio": 0.99,
        "pullback_status": "REAL_RR_BELOW_1_8",
        "breakout_status": "REAL_RR_BELOW_1_8",
    }

    low_rr, _ = classify_candidate(row, plan, ["https://example.com/report.pdf"], Counter())
    plan["real_reward_risk_ratio"] = 1.20
    no_url, _ = classify_candidate(row, plan, [], Counter())

    assert low_rr != "NEAR_READY"
    assert no_url != "NEAR_READY"


class _FakeChinaCalendar:
    sessions = [date(2026, 7, 9), date(2026, 7, 10), date(2026, 7, 13)]

    def is_session(self, value: date) -> bool:
        return value in self.sessions

    def date_to_session(self, value: date, direction: str = "previous") -> date:
        assert direction == "previous"
        return max(session for session in self.sessions if session <= value)

    def previous_session(self, value: date) -> date:
        return self.sessions[self.sessions.index(value) - 1]

    def next_session(self, value: date) -> date:
        return self.sessions[self.sessions.index(value) + 1]

    def session_close(self, value: date) -> datetime:
        return datetime(value.year, value.month, value.day, 7, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("reference_time", "expected_as_of", "expected_tomorrow"),
    [
        (datetime(2026, 7, 11, 10, tzinfo=ZoneInfo("Asia/Shanghai")), date(2026, 7, 10), date(2026, 7, 13)),
        (datetime(2026, 7, 10, 14, tzinfo=ZoneInfo("Asia/Shanghai")), date(2026, 7, 9), date(2026, 7, 10)),
        (datetime(2026, 7, 10, 16, tzinfo=ZoneInfo("Asia/Shanghai")), date(2026, 7, 10), date(2026, 7, 13)),
    ],
)
def test_shenzhen_scan_dates_use_completed_china_sessions(
    reference_time: datetime,
    expected_as_of: date,
    expected_tomorrow: date,
) -> None:
    assert resolve_scan_dates(reference_time, calendar=_FakeChinaCalendar()) == (expected_as_of, expected_tomorrow)


def _diversified_cohort_samples(
    *, member_returns: tuple[float, float, float] = (2.0, 2.0, 2.0),
) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    start = date(2023, 1, 2)
    for period_index in range(12):
        entry_date = start + timedelta(days=period_index * 100)
        for member_index, net_return in enumerate(member_returns):
            samples.append(
                {
                    "code": str(100000 + period_index * 3 + member_index),
                    "as_of_date": entry_date,
                    "outcome_end_date": entry_date + timedelta(days=80),
                    "entry_mode": "pullback",
                    "return": net_return,
                    "drawdown": -5.0,
                }
            )
    return samples


def test_extended_history_fetch_can_fall_back_to_recent_validated_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = pd.bdate_range(end="2026-07-30", periods=400)
    provider_frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.linspace(9.0, 10.0, len(dates)),
            "high": np.linspace(9.2, 10.2, len(dates)),
            "low": np.linspace(8.8, 9.8, len(dates)),
            "close": np.linspace(9.1, 10.1, len(dates)),
            "volume": np.linspace(1_000_000, 1_500_000, len(dates)),
            "amount": np.linspace(10_000_000, 15_000_000, len(dates)),
        }
    )

    class FakeAkshare:
        should_fail = False

        def stock_zh_a_daily(self, **kwargs: object) -> pd.DataFrame:
            if self.should_fail:
                raise ConnectionError("temporary provider outage")
            if kwargs.get("adjust") == "qfq-factor":
                return pd.DataFrame({
                    "date": [provider_frame.iloc[0]["date"]],
                    "qfq_factor": [1.0],
                })
            return provider_frame.copy()

    fake_akshare = FakeAkshare()
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    candidate = {"code": "600001", "stock_name": "缓存测试", "exchange": "SSE"}
    cache_dir = tmp_path / "history-cache"

    fresh_histories, fresh_summary = fetch_extended_adjusted_histories(
        candidates=[candidate],
        as_of=date(2026, 7, 30),
        cache_dir=cache_dir,
    )

    assert len(fresh_histories["600001"]) == 400
    assert fresh_summary["fresh_fetch_count"] == 1
    assert fresh_summary["cache_write_count"] == 1
    assert (cache_dir / "600001.metadata.json").is_file()

    fake_akshare.should_fail = True
    monkeypatch.setitem(
        sys.modules,
        "baostock",
        SimpleNamespace(
            login=lambda: SimpleNamespace(error_code="1", error_msg="temporary provider outage"),
        ),
    )
    cached_histories, cached_summary = fetch_extended_adjusted_histories(
        candidates=[candidate],
        as_of=date(2026, 7, 30),
        cache_dir=cache_dir,
    )

    assert len(cached_histories["600001"]) == 400
    assert cached_summary["fresh_fetch_count"] == 0
    assert cached_summary["cache_fallback_count"] == 1
    assert cached_summary["source_counts"] == {
        "validated_cache_qfq_with_raw_mapping": 1,
    }
    assert "600001" not in cached_summary["errors"]

    stale_histories, stale_summary = fetch_extended_adjusted_histories(
        candidates=[candidate],
        as_of=date(2026, 7, 31),
        cache_dir=cache_dir,
    )
    assert "600001" not in stale_histories
    assert "requested_as_of_mismatch" in stale_summary["cache_read_errors"]["600001"]


def test_cohort_independence_uses_observed_outcome_end_across_suspension() -> None:
    samples: list[dict[str, object]] = []
    for group_index, (entry_date, outcome_end_date) in enumerate(
        (
            (date(2024, 1, 2), date(2024, 4, 15)),
            # More than 60 weekdays after the first entry, but the first
            # outcome is still open because its stock history was suspended.
            (date(2024, 4, 1), date(2024, 7, 1)),
            (date(2024, 4, 16), date(2024, 7, 15)),
        )
    ):
        for member_index in range(3):
            samples.append(
                {
                    "code": str(200000 + group_index * 3 + member_index),
                    "as_of_date": entry_date,
                    "outcome_end_date": outcome_end_date,
                    "return": 2.0,
                    "drawdown": -5.0,
                }
            )

    periods = _cohort_period_samples(samples, as_of=date(2024, 12, 31))

    assert [period["as_of_date"] for period in periods] == [
        date(2024, 1, 2),
        date(2024, 4, 16),
    ]


def test_cohort_basket_median_cannot_hide_member_return_tail() -> None:
    result = _cohort_validation(
        _diversified_cohort_samples(member_returns=(-20.0, 2.0, 24.0)),
        as_of=date(2026, 7, 30),
        cohort_key="MAIN|pullback",
        data_end_by_code={},
    )

    assert result["period_count"] == 12
    assert result["avg_return"] == pytest.approx(2.0)
    assert result["performance_passed"] is True
    assert result["member_tail_return"] == pytest.approx(-20.0)
    assert result["member_performance_passed"] is False
    assert result["status"] != "PASSED"


def test_cohort_rejects_single_code_period_concentration() -> None:
    samples: list[dict[str, object]] = []
    start = date(2023, 1, 2)
    for period_index in range(12):
        entry_date = start + timedelta(days=period_index * 100)
        for code in (
            "600001",
            str(300000 + period_index * 2),
            str(300001 + period_index * 2),
        ):
            samples.append(
                {
                    "code": code,
                    "as_of_date": entry_date,
                    "outcome_end_date": entry_date + timedelta(days=80),
                    "return": 2.0,
                    "drawdown": -5.0,
                }
            )

    result = _cohort_validation(
        samples,
        as_of=date(2026, 7, 30),
        cohort_key="MAIN|pullback",
        data_end_by_code={},
    )

    assert result["period_count"] == 12
    assert result["unique_code_count"] >= 8
    assert result["performance_passed"] is True
    assert result["member_performance_passed"] is True
    assert result["max_code_period_share"] == pytest.approx(1.0)
    assert result["code_concentration_passed"] is False
    assert result["status"] != "PASSED"


def test_cohort_missing_outcome_end_fails_closed() -> None:
    samples = _diversified_cohort_samples()
    samples[0] = {key: value for key, value in samples[0].items() if key != "outcome_end_date"}

    result = _cohort_validation(
        samples,
        as_of=date(2026, 7, 30),
        cohort_key="MAIN|pullback",
        data_end_by_code={},
    )

    assert result["invalid_outcome_end_count"] == 1
    assert result["outcome_end_complete"] is False
    assert result["independence_passed"] is False
    assert result["status"] != "PASSED"


def test_candidate_reference_overlap_uses_target_code_leave_one_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_code = "600001"
    samples_by_code: dict[str, list[dict[str, object]]] = {}
    references: list[dict[str, str]] = []
    start = date(2023, 1, 2)
    for period_index in range(12):
        entry_date = start + timedelta(days=period_index * 100)
        codes = (
            [target_code, str(400000 + period_index * 2), str(400001 + period_index * 2)]
            if period_index < 6
            else [str(500000 + period_index * 3 + offset) for offset in range(3)]
        )
        for code in codes:
            if code not in samples_by_code:
                samples_by_code[code] = []
                references.append({"code": code, "stock_name": code, "board": "SSE_MAIN"})
            samples_by_code[code].append(
                {
                    "code": code,
                    "as_of_date": entry_date,
                    "outcome_end_date": entry_date + timedelta(days=80),
                    "entry_mode": "pullback",
                    "return": 2.0,
                    "drawdown": -5.0,
                }
            )

    def fake_price_setup_samples(**kwargs: object) -> list[dict[str, object]]:
        if kwargs["entry_mode"] != "pullback":
            return []
        return list(samples_by_code.get(str(kwargs["code"]), []))

    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.exit_profile._price_setup_samples",
        fake_price_setup_samples,
    )
    history = pd.DataFrame(
        {
            "date": ["2026-07-28", "2026-07-29"],
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.8, 9.9],
            "close": [10.1, 10.2],
            "volume": [1_000_000, 1_100_000],
            "amount": [10_000_000, 11_000_000],
        }
    )
    histories = {code: history for code in samples_by_code}

    output, summary = refresh_exit_profiles_from_price_history(
        output_file=tmp_path / "exit_profile.csv",
        candidates=[{"code": target_code, "stock_name": "目标股", "board": "SSE_MAIN"}],
        validation_candidates=references,
        histories=histories,
        as_of=date(2026, 7, 30),
    )
    with output.open(encoding="utf-8") as file:
        row = next(csv.DictReader(file))

    assert summary["cohort_validations"]["MAIN|pullback"]["status"] == "PASSED"
    assert summary["cohort_leave_one_out_candidate_count"] == 1
    assert row["cohort_excluded_target_code"] == target_code
    assert int(row["cohort_period_count"]) == 6
    assert row["cohort_profile_status"] != "PASSED"
    assert row["balanced_exit_historical_profile"] != "PASSED"


def test_github_actions_opportunity_workflow_contract() -> None:
    workflow = Path(".github/workflows/genge-opportunity-discovery.yml").read_text(encoding="utf-8")
    cycle_workflow = Path(".github/workflows/genge-cycle-bottom.yml").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    ci_requirements = Path(".github/requirements-ci.txt").read_text(encoding="utf-8")
    assert "cron:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "actions/cache/save@v4" in workflow
    assert "data/opportunity_snapshots" in workflow
    assert "data/cache/opportunity_evidence" in workflow
    assert "data/cache/shenzhen_full_scan" in workflow
    assert "tests/test_genge_opportunity_discovery_*.py" in workflow
    assert "--run-mode" in workflow
    assert "--exit-profile-file" in workflow
    assert "data/opportunity_snapshots/exit_profile.csv" in workflow
    assert "cp data/opportunity_snapshots/exit_profile_seed.csv" in workflow
    assert "daily_signals.csv" in workflow
    assert "buy_signals.csv" in workflow
    assert "actionable_execution_list.csv" in workflow
    assert "all-A scan heartbeat" in workflow
    assert "timeout --signal=TERM 100m" in workflow
    assert "--max-workers 12" in workflow
    assert "Run production strategy tests" in workflow
    assert "tests/test_genge_all_a_full_scan.py" in workflow
    assert "tests/test_genge_real_world_signals.py" in workflow
    assert "Run full pytest" not in workflow
    assert "sell_signals.csv" in workflow
    assert "market_regime.json" in workflow
    assert "industry_regimes.csv" in workflow
    assert "real_world_signal_audit.csv" in workflow
    assert "daily_candidate_top5.csv" in workflow
    assert "daily_candidate_top5_count" in workflow
    assert "CANCEL_BUY_REVIEW" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "--prefer-binary --retries 5 --timeout 60" in workflow
    assert "src.strategies.genge_opportunity_discovery.shenzhen_full_scan" in workflow
    assert "genge_broad_pool.txt" not in workflow
    assert "--max-codes" not in workflow
    assert 'summary["effective_scan_count"] > 100' in workflow
    assert 'summary["data_fetch_failure_count"] == 0' in workflow
    assert 'summary["industry_enrichment_status"] in {"OK", "SNAPSHOT_FALLBACK"}' in workflow
    assert 'summary["industry_enriched_count"] > 1000' in workflow
    assert 'summary["listing_fallback_age_days"] <= 7' in workflow
    assert "genge-shenzhen-full-scan-report" in workflow
    assert "daily-opportunity-report:" in workflow
    assert "PASS_EVIDENCE_ENRICHMENT_READY" not in workflow
    assert "timeout-minutes: 35" in cycle_workflow
    assert "exchange-calendars" in requirements
    assert "pypdf" in requirements
    assert "beautifulsoup4" in requirements
    assert "pypdf" in ci_requirements
    assert "beautifulsoup4" in ci_requirements
