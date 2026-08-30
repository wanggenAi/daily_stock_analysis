from src.era_radar.live_miit import MiitPolicyCollector


HTML = """
<html><body>
<a href="/jgsj/kjs/wjfb/art/2026/art_robot.html">关于公开征求《国家人形机器人产业标准体系建设指南（2026版）》意见的公示</a>
<a href="/jgsj/kjs/wjfb/art/2026/art_bci.html">关于公开征求《国家脑机接口产业标准体系建设指南（2026版）》意见的公示</a>
<a href="/jgsj/kjs/wjfb/art/2026/art_battery.html">全国动力电池回收利用标准化技术委员会组建委员名单</a>
<a href="/irrelevant.html">普通综合新闻</a>
</body></html>
"""


def test_miit_policy_collector_classifies_only_known_policy_topics():
    collector = MiitPolicyCollector(fetcher=lambda: HTML, clock=lambda: "2026-08-30T10:00:00Z")
    rows = list(collector.collect("2026-08-30T10:00:01Z"))
    topics = {row.topic_keys[0] for row in rows}
    assert topics == {"embodied_intelligence", "brain_computer_interface", "intelligent_ev_supply_chain"}
    assert all(row.family == "POLICY_CAPITAL" for row in rows)
    assert all(row.source_id == "miit" for row in rows)
    assert all(row.observed_at == row.retrieved_at for row in rows)


def test_miit_duplicate_anchor_is_deduplicated():
    html = HTML + '<a href="/jgsj/kjs/wjfb/art/2026/art_robot.html">关于公开征求《国家人形机器人产业标准体系建设指南（2026版）》意见的公示</a>'
    collector = MiitPolicyCollector(fetcher=lambda: html, clock=lambda: "2026-08-30T10:00:00Z")
    rows = [row for row in collector.collect("2026-08-30T10:00:01Z") if row.topic_keys == ("embodied_intelligence",)]
    assert len(rows) == 1
