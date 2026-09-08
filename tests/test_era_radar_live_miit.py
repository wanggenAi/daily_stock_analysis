from src.era_radar.live_miit import MiitPolicyCollector, MiitStatisticsCollector


HTML = """
<html><body>
<a href="/jgsj/kjs/wjfb/art/2026/art_robot.html">关于公开征求《国家人形机器人产业标准体系建设指南（2026版）》意见的公示</a>
<a href="/jgsj/kjs/wjfb/art/2026/art_bci.html">关于公开征求《国家脑机接口产业标准体系建设指南（2026版）》意见的公示</a>
<a href="/jgsj/kjs/wjfb/art/2026/art_battery.html">全国动力电池回收利用标准化技术委员会组建委员名单</a>
<a href="/gxsj/tjfx/txy/art/2026/telecom.html">2026年上半年通信业经济运行情况</a>
<a href="/irrelevant.html">普通综合新闻</a>
</body></html>
"""

ARTICLE = """
<html><body>
<div>发布时间：2026-07-31 15:24 来源：运行监测协调局</div>
<p>5G用户快速发展，用户规模持续扩大。</p>
<p>移动互联网累计流量同比增长17.7%。</p>
<p>5G基站总数比上年末增加26.3万个。</p>
<p>电信业务收入同比下降2.1%。</p>
</body></html>
"""


def test_miit_policy_collector_classifies_only_policy_marked_topics():
    collector = MiitPolicyCollector(fetcher=lambda: HTML, clock=lambda: "2026-08-30T10:00:00Z")
    rows = list(collector.collect("2026-08-30T10:00:01Z"))
    topics = {row.topic_keys[0] for row in rows}
    assert topics == {"embodied_intelligence", "brain_computer_interface", "intelligent_ev_supply_chain"}
    assert all(row.family == "POLICY_CAPITAL" for row in rows)
    assert all(row.source_id == "miit" for row in rows)
    assert "digital_infrastructure" not in topics


def test_miit_duplicate_anchor_is_deduplicated():
    html = HTML + '<a href="/jgsj/kjs/wjfb/art/2026/art_robot.html">关于公开征求《国家人形机器人产业标准体系建设指南（2026版）》意见的公示</a>'
    collector = MiitPolicyCollector(fetcher=lambda: html, clock=lambda: "2026-08-30T10:00:00Z")
    rows = [row for row in collector.collect("2026-08-30T10:00:01Z") if row.topic_keys == ("embodied_intelligence",)]
    assert len(rows) == 1


def test_miit_statistics_becomes_real_demand_with_publication_time():
    collector = MiitStatisticsCollector(
        index_fetcher=lambda: HTML,
        article_fetcher=lambda _url: ARTICLE,
        clock=lambda: "2026-08-30T10:00:00Z",
    )
    rows = list(collector.collect("2026-08-30T10:00:01Z"))
    assert len(rows) == 1
    row = rows[0]
    assert row.topic_keys == ("digital_infrastructure",)
    assert row.family == "REAL_DEMAND"
    assert row.source_id == "miit_statistics"
    assert row.direction == 1
    assert row.published_at == "2026-07-31T07:24:00Z"
    assert row.observed_at == row.published_at
    assert row.strength > 0.5
