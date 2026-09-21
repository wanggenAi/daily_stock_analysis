from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    prepare_industry_alias_map,
)
from src.strategies.genge_opportunity_discovery.evidence_collectors.public_data import (
    _industry_search_terms,
    _miit_operational_article_candidates,
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
