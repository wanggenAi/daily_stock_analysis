from src.strategies.genge_opportunity_discovery.evidence_collectors.public_data import (
    _industry_search_terms,
    _specialized_source_specs,
)

from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    _LazyCninfoOrgIdMap,
    canonical_industry_name,
    normalize_sse_attachment_url,
    prepare_industry_alias_map,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(self.payload)


class _FailingResponse:
    def raise_for_status(self):
        raise RuntimeError("topSearch transport failed")

    def json(self):
        return []


class _FallbackSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.startswith("https://"):
            return _FailingResponse()
        return _FakeResponse(self.payload)


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


def test_cninfo_orgid_map_lazily_recovers_missing_shenzhen_code():
    session = _FakeSession(
        [
            {"code": "001316", "orgId": "gssz0001316", "zwjc": "润贝航科"},
            {"code": "001317", "orgId": "gssz0001317", "zwjc": "other"},
        ]
    )
    mapping = _LazyCninfoOrgIdMap({}, session, 8)

    assert mapping.get("001316") == "gssz0001316"
    assert mapping.get("001316") == "gssz0001316"
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url.endswith("/new/information/topSearch/query")
    assert kwargs["data"] == {"keyWord": "001316", "maxNum": "10"}


def test_cninfo_orgid_map_falls_back_to_http_when_https_fails():
    session = _FallbackSession(
        [{"code": "001316", "orgId": "gssz0001316", "zwjc": "润贝航科"}]
    )
    mapping = _LazyCninfoOrgIdMap({}, session, 8)

    assert mapping.get("001316") == "gssz0001316"
    assert len(session.calls) == 2
    assert session.calls[0][0].startswith("https://")
    assert session.calls[1][0].startswith("http://")


def test_cninfo_orgid_map_fails_closed_on_nonmatching_response():
    session = _FakeSession([{"code": "001317", "orgId": "gssz0001317"}])
    mapping = _LazyCninfoOrgIdMap({}, session, 8)
    assert mapping.get("001316") is None
    assert mapping.get("001316") is None
    assert len(session.calls) == 2

def test_specialized_sources_follow_aliases_for_classified_transport_industries():
    industries = [
        "G55水上运输业",
        "G58多式联运和运输代理业",
        "G60邮政业",
    ]
    aliases = prepare_industry_alias_map(industries)

    shipping_terms = _industry_search_terms(industries[0], aliases)
    logistics_terms = _industry_search_terms(industries[1], aliases)
    postal_terms = _industry_search_terms(industries[2], aliases)

    assert "航运" in shipping_terms
    assert "物流" in logistics_terms
    assert "物流" in postal_terms
    assert [row[0] for row in _specialized_source_specs(shipping_terms)] == ["mot_public_data"]
    assert [row[0] for row in _specialized_source_specs(logistics_terms)] == ["spb_public_data"]
    assert [row[0] for row in _specialized_source_specs(postal_terms)] == ["spb_public_data"]


def test_specialized_sources_do_not_expand_unrelated_industries():
    raw = "I65软件和信息技术服务业"
    aliases = prepare_industry_alias_map([raw])
    terms = _industry_search_terms(raw, aliases)
    assert _specialized_source_specs(terms) == []

