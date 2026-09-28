from src.era_radar.live_nbs_investment import (
    NBS_RELEASE_INDEX,
    NbsFixedAssetInvestmentCollector,
)

INDEX = """
<html><body>
<a href="/sj/zxfb/202608/t20260817_old.html">2026年1—7月份全国固定资产投资基本情况</a>
<a href="/sj/zxfb/202609/t20260915_1965309.html">2026年1—8月份全国固定资产投资基本情况</a>
</body></html>
"""

ARTICLE = """
<html><body>
<p>2026/09/15 10:00</p>
<p>1—8月份，全国固定资产投资（不含农户）293092亿元，同比下降7.2%。</p>
<p>工业投资同比下降2.9%。其中，采矿业投资增长3.4%，制造业投资下降2.3%，电力、热力、燃气及水生产和供应业投资下降6.9%。</p>
<p>基础设施投资（口径详见附注1）同比下降4.0%。其中，信息传输业投资增长28.4%，航空运输业投资增长16.7%。</p>
<table><tr><td>设备工器具购置</td><td>9.3</td></tr></table>
</body></html>
"""


def _index(url: str) -> str:
    assert url == NBS_RELEASE_INDEX
    return INDEX


def _article(url: str) -> str:
    assert url.endswith("/202609/t20260915_1965309.html")
    return ARTICLE


def test_nbs_collector_emits_current_industrial_capital_and_digital_capex():
    collector = NbsFixedAssetInvestmentCollector(
        index_fetcher=_index,
        article_fetcher=_article,
        clock=lambda: "2026-09-20T12:00:00Z",
    )
    rows = list(collector.collect("2026-09-20T12:00:00Z"))
    assert len(rows) == 6
    assert {row.family for row in rows} == {"INDUSTRIAL_CAPITAL"}
    assert {row.source_id for row in rows} == {"stats_cn_investment"}
    assert all(row.published_at == "2026-09-15T02:00:00Z" for row in rows)
    by_topic = {row.topic_keys[0]: row for row in rows}
    assert by_topic["macro_industrial_capex"].direction == -1
    assert by_topic["industrial_capex_cycle"].direction == -1
    assert by_topic["manufacturing_capex"].direction == -1
    assert by_topic["infrastructure_capex"].direction == -1
    assert by_topic["equipment_investment"].direction == 1
    assert by_topic["digital_infrastructure"].direction == 1


def test_nbs_collector_fails_closed_when_required_investment_schema_changes():
    collector = NbsFixedAssetInvestmentCollector(
        index_fetcher=_index,
        article_fetcher=lambda _url: "<p>2026/09/15 10:00</p><p>schema changed</p>",
        clock=lambda: "2026-09-20T12:00:00Z",
    )
    try:
        list(collector.collect("2026-09-20T12:00:00Z"))
    except ValueError as exc:
        assert "schema changed" in str(exc)
        assert "industrial_investment" in str(exc)
    else:
        raise AssertionError("collector must fail closed on changed NBS investment schema")


def test_live_official_inline_spans_do_not_split_required_investment_metrics():
    """NBS may style numeric/text nodes separately inside the same sentence."""
    styled = (
        ARTICLE
        .replace(
            "全国固定资产投资（不含农户）293092亿元，同比下降7.2%",
            "全国固定资产投资（不含农户）<span>293092</span>亿元，"
            "<span>同比</span>下降<span>7.2</span>%",
        )
        .replace(
            "工业投资同比下降2.9%",
            "<span>工业投资</span>同比<span>下降2.9%</span>",
        )
        .replace(
            "制造业投资下降2.3%",
            "<span>制造业投资</span><span>下降2.3%</span>",
        )
        .replace(
            "基础设施投资（口径详见附注1）同比下降4.0%",
            "基础设施投资（口径详见附注1）<span>同比</span>"
            "<span>下降4.0%</span>",
        )
    )
    collector = NbsFixedAssetInvestmentCollector(
        index_fetcher=_index,
        article_fetcher=lambda _: styled,
        clock=lambda: "2026-09-27T12:00:00Z",
    )
    rows = list(collector.collect("2026-09-27T12:00:00Z"))
    assert len(rows) == 6
    assert {r.topic_keys[0] for r in rows} == {
        "macro_industrial_capex", "industrial_capex_cycle",
        "manufacturing_capex", "infrastructure_capex",
        "equipment_investment", "digital_infrastructure",
    }
    assert all(r.published_at == "2026-09-15T02:00:00Z" for r in rows)
    assert all(r.family == "INDUSTRIAL_CAPITAL" for r in rows)
    assert all(r.direction == (-1 if r.topic_keys[0] not in {
        "equipment_investment", "digital_infrastructure"} else 1) for r in rows)


def test_inline_spans_do_not_allow_missing_official_metric_to_pass():
    # Fix token boundaries, not the business requirement for every metric.
    styled = ARTICLE.replace("工业投资同比下降2.9%", "工业投资数据另发")
    collector = NbsFixedAssetInvestmentCollector(
        index_fetcher=_index,
        article_fetcher=lambda _: styled,
        clock=lambda: "2026-09-27T12:00:00Z",
    )
    try:
        list(collector.collect("2026-09-27T12:00:00Z"))
    except ValueError as exc:
        assert "industrial_investment" in str(exc)
    else:
        raise AssertionError("missing independently stated industrial metric must fail closed")
