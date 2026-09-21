from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    prepare_industry_alias_map,
)
from src.strategies.genge_opportunity_discovery.evidence_collectors.public_data import (
    NBS_REPORT_TITLE_TOKENS,
    _extract_report_numeric_context,
    _industry_search_terms,
    _miit_operational_article_candidates,
    _report_article_candidates,
    _report_direction,
    _specialized_source_specs,
)


def test_software_industry_routes_to_miit_category():
    industry = "I65软件和信息技术服务业"
    alias_map = prepare_industry_alias_map([industry])
    terms = _industry_search_terms(industry, alias_map)
    specs = _specialized_source_specs(terms)

    assert "软件" in terms
    assert any(
        collector == "miit_software_public_data"
        and url.endswith("/gxsj/tjfx/rjy/index.html")
        for collector, url, _title in specs
    )


def test_miit_category_page_yields_dated_operational_article_not_navigation():
    html = """
    <html><body>
      <a href="/gxsj/tjfx/rjy/index.html">软件和信息技术服务业统计数据和运行分析</a>
      <a href="/gxsj/tjfx/rjy/art/2026/art_latest.html">2026年1－8月软件业运行情况</a>
      <a href="/gxsj/tjfx/rjy/art/2025/art_old.html">2025年软件业运行分析</a>
    </body></html>
    """
    rows = _miit_operational_article_candidates(
        html,
        base_url="https://www.miit.gov.cn/gxsj/tjfx/rjy/index.html",
    )

    assert [row[0] for row in rows] == [
        "2026年1－8月软件业运行情况",
        "2025年软件业运行分析",
    ]
    assert rows[0][1] == (
        "https://www.miit.gov.cn/gxsj/tjfx/rjy/art/2026/art_latest.html"
    )
    assert all("统计数据和运行分析" != row[0] for row in rows)


def test_electronic_information_industry_routes_to_miit_operating_monitoring():
    industry = "C39计算机、通信和其他电子设备制造业"
    alias_map = prepare_industry_alias_map([industry])
    terms = _industry_search_terms(industry, alias_map)
    specs = _specialized_source_specs(terms)

    assert "电子信息制造业" in terms
    assert "计算机、通信和其他电子设备制造业" in terms
    assert any(
        collector == "miit_electronic_information_public_data"
        and url.endswith("/jgsj/yxj/index.html")
        for collector, url, _title in specs
    )


def test_nbs_fixed_asset_release_is_a_cross_industry_candidate():
    html = """
    <html><body>
      <a href="/sj/zxfb/202609/t20260915_1965309.html">
        2026年1—8月份全国固定资产投资基本情况
      </a>
      <a href="/sj/zxfb/202609/unrelated.html">居民消费价格</a>
    </body></html>
    """
    rows = _report_article_candidates(
        html,
        base_url="https://www.stats.gov.cn/sj/zxfb/",
        title_tokens=NBS_REPORT_TITLE_TOKENS,
    )

    assert [row[0] for row in rows] == [
        "2026年1—8月份全国固定资产投资基本情况"
    ]
    assert rows[0][1] == (
        "https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965309.html"
    )



def test_miit_metric_extraction_ignores_title_year_and_binds_growth_value():
    text = """
    2026年1—7月电子信息制造业运行情况
    发布时间：2026-08-31 14:56
    2026年1-7月，我国电子信息制造业生产保持快速增长。
    1-7月份，规模以上电子信息制造业增加值同比增长15.4%，增速较去年同期高4.5个百分点。
    """
    extracted = _extract_report_numeric_context(text, ["电子信息制造业"])

    assert extracted["value"] == "15.4"
    assert extracted["unit"] == "%"
    assert "增加值同比增长15.4%" in extracted["excerpt"]
    assert "2026年1—7月电子信息制造业运行情况" not in extracted["excerpt"]
    assert _report_direction(
        extracted["excerpt"],
        extracted["value"],
        collector="miit_electronic_information_public_data",
        article_title="2026年1—7月电子信息制造业运行情况",
    ) == "POSITIVE"


def test_nbs_direction_is_local_to_target_industry_not_later_region_decline():
    text = """
    基础设施投资同比下降4.0%。其中，信息传输业投资增长28.4%，航空运输业投资增长16.7%，水上运输业投资增长14.7%。
    分地区看，东部地区投资同比下降9.4%，中部地区投资下降8.7%。
    """
    extracted = _extract_report_numeric_context(text, ["水上运输业"])

    assert extracted["value"] == "14.7"
    assert extracted["unit"] == "%"
    assert "水上运输业投资增长14.7%" in extracted["excerpt"]
    assert "东部地区" not in extracted["excerpt"]
    assert _report_direction(
        extracted["excerpt"],
        extracted["value"],
        collector="nbs_public_data",
        article_title="2026年1—8月份全国固定资产投资基本情况",
    ) == "POSITIVE"


def test_nbs_table_negative_value_keeps_negative_direction_without_words():
    text = """
    分行业
    专用设备制造业 -9.0
    汽车制造业 -6.0
    """
    extracted = _extract_report_numeric_context(text, ["专用设备制造业"])

    assert extracted["value"] == "-9.0"
    assert _report_direction(
        extracted["excerpt"],
        extracted["value"],
        collector="nbs_public_data",
        article_title="2026年1—8月份全国固定资产投资基本情况",
    ) == "NEGATIVE"
