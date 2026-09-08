from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    canonical_industry_name,
    normalize_sse_attachment_url,
    prepare_industry_alias_map,
)


def test_sse_disclosure_attachment_uses_static_host():
    relative = "/disclosure/listedinfo/announcement/c/new/2026-08-20/example.pdf"
    assert normalize_sse_attachment_url(relative) == (
        "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-08-20/example.pdf"
    )
    assert normalize_sse_attachment_url("https://www.sse.com.cn" + relative) == (
        "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-08-20/example.pdf"
    )
    assert normalize_sse_attachment_url("https://static.sse.com.cn" + relative) == (
        "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-08-20/example.pdf"
    )


def test_sse_normalizer_does_not_rewrite_unrelated_domains():
    url = "https://static.cninfo.com.cn/finalpage/2026-01-01/example.PDF"
    assert normalize_sse_attachment_url(url) == url


def test_classified_industry_prefix_is_removed_only_for_search_terms():
    assert canonical_industry_name("B09有色金属矿采选业") == "有色金属矿采选业"
    assert canonical_industry_name("J68保险业") == "保险业"
    assert canonical_industry_name("I65软件和信息技术服务业") == "软件和信息技术服务业"


def test_default_alias_map_expands_classified_industries():
    industries = [
        "B09有色金属矿采选业",
        "J68保险业",
        "I65软件和信息技术服务业",
        "C39计算机、通信和其他电子设备制造业",
    ]
    payload = prepare_industry_alias_map(industries)
    rows = payload["industries"]

    assert "有色金属矿采选业" in rows[industries[0]]["aliases"]
    assert "有色金属" in rows[industries[0]]["aliases"]
    assert "保险业" in rows[industries[1]]["aliases"]
    assert "保险" in rows[industries[1]]["aliases"]
    assert "软件和信息技术服务业" in rows[industries[2]]["aliases"]
    assert "计算机、通信和其他电子设备制造业" in rows[industries[3]]["aliases"]


def test_original_industry_key_is_preserved_for_downstream_join():
    raw = "B09有色金属矿采选业"
    payload = prepare_industry_alias_map([raw])
    assert raw in payload["industries"]
