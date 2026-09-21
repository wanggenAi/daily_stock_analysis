from src.era_radar.live_pbc import (
    PBC_INDEX_URL,
    PbcFinancialStatisticsCollector,
)

INDEX = """
<html><body>
<a href="/diaochatongjisi/116219/116225/old/index.html">2026年7月金融统计数据报告</a>
<a href="/diaochatongjisi/116219/116225/2026091417020862747/index.html">2026年8月金融统计数据报告</a>
</body></html>
"""

ARTICLE = """
<html><body>
<h2>2026年8月金融统计数据报告</h2>
<p>文章来源： 2026-09-14 17:00:00</p>
<p>
二、前八个月社会融资规模增量累计为23.91万亿元
初步统计，2026年前八个月社会融资规模增量累计为23.91万亿元，比上年同期少2.64万亿元。
其中，对实体经济发放的人民币贷款增加10.23万亿元，同比少增2.71万亿元；
企业债券净融资2.79万亿元，同比多1.23万亿元；
政府债券净融资8.77万亿元，同比少1.5万亿元；
非金融企业境内股票融资4700亿元，同比多2031亿元。
</p>
</body></html>
"""


def _index(url: str) -> str:
    assert url == PBC_INDEX_URL
    return INDEX


def _article(url: str) -> str:
    assert url.endswith("/2026091417020862747/index.html")
    return ARTICLE


def test_pbc_collector_emits_current_financial_capital_channels_from_official_monthly_report():
    collector = PbcFinancialStatisticsCollector(
        index_fetcher=_index,
        article_fetcher=_article,
        clock=lambda: "2026-09-20T12:00:00Z",
    )
    rows = list(collector.collect("2026-09-20T12:00:00Z"))
    assert len(rows) == 4
    assert {row.family for row in rows} == {"FINANCIAL_CAPITAL"}
    assert {row.source_id for row in rows} == {"pbc"}
    assert all(row.source_url.startswith("https://www.pbc.gov.cn/") for row in rows)
    assert all(row.published_at == "2026-09-14T09:00:00Z" for row in rows)
    assert all(row.freshness == "FRESH" for row in rows)
    by_topic = {row.topic_keys[0]: row for row in rows}
    assert by_topic["macro_financial_conditions"].direction == -1
    assert by_topic["enterprise_credit_cycle"].direction == -1
    assert by_topic["government_financing_impulse"].direction == -1
    assert by_topic["corporate_market_financing"].direction == 1


def test_pbc_collector_fails_closed_when_required_report_schema_changes():
    collector = PbcFinancialStatisticsCollector(
        index_fetcher=_index,
        article_fetcher=lambda _url: "<p>文章来源： 2026-09-14 17:00:00</p><p>schema changed</p>",
        clock=lambda: "2026-09-20T12:00:00Z",
    )
    try:
        list(collector.collect("2026-09-20T12:00:00Z"))
    except ValueError as exc:
        assert "schema changed" in str(exc)
        assert "afre" in str(exc)
    else:
        raise AssertionError("collector must fail closed on changed PBC report schema")


def test_pbc_collector_rejects_stale_latest_monthly_report():
    collector = PbcFinancialStatisticsCollector(
        index_fetcher=_index,
        article_fetcher=_article,
        clock=lambda: "2027-02-20T12:00:00Z",
    )
    try:
        list(collector.collect("2027-02-20T12:00:00Z"))
    except ValueError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale PBC monthly report must not enter live Radar truth")
