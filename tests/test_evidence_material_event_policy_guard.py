from datetime import date

from src.strategies.genge_opportunity_discovery.evidence_collectors.company_announcements import (
    _classify_material_events,
)


PUBLISH_DATE = date(2026, 8, 20)
AS_OF = date(2026, 9, 8)


def _event_types(title: str) -> set[str]:
    return {
        str(row.get("event_type") or "")
        for row in _classify_material_events(
            title,
            publish_date=PUBLISH_DATE,
            as_of=AS_OF,
        )
    }


def test_nari_preventive_funds_occupation_policy_is_not_incident():
    title = "国电南瑞关于防范控股股东及关联方资金占用管理办法(2025年修订)"
    assert "FUNDS_OCCUPATION" not in _event_types(title)


def test_cmoc_preventive_funds_occupation_policy_is_not_incident():
    title = "洛阳钼业防范控股股东、实际控制人及其他关联方资金占用管理办法"
    assert "FUNDS_OCCUPATION" not in _event_types(title)


def test_true_funds_occupation_remediation_event_is_still_detected():
    title = "关于控股股东非经营性资金占用事项及整改进展的公告"
    assert "FUNDS_OCCUPATION" in _event_types(title)


def test_policy_words_do_not_hide_explicit_real_incident():
    title = (
        "关于控股股东非经营性资金占用事项整改进展"
        "及修订防范资金占用管理办法的公告"
    )
    assert "FUNDS_OCCUPATION" in _event_types(title)

def test_routine_funds_occupation_reporting_is_not_treated_as_active_incident():
    titles = (
        "老板电器：关联方资金占用报告",
        "深城交：2025年关联方资金占用报告",
        "金禄电子：2026年半年度控股股东及其他关联方占用资金情况专项公告",
        "先锋新材：控股股东及其他关联方非经营性资金占用及清偿情况表",
    )
    for title in titles:
        assert "FUNDS_OCCUPATION" not in _event_types(title)


def test_preventive_policy_with_occupied_funds_phrase_remains_non_incident():
    title = "关于防范控股股东及关联方占用上市公司资金的管理办法"
    assert "FUNDS_OCCUPATION" not in _event_types(title)


def test_unqualified_audit_opinion_is_not_non_standard_audit():
    titles = (
        "关于2025年度审计报告带强调事项段的无保留意见涉及事项的专项说明",
        "关于对带强调事项段的无保留意见内部控制审计报告涉及事项的专项说明",
    )
    for title in titles:
        assert "NON_STANDARD_AUDIT" not in _event_types(title)


def test_true_qualified_audit_opinion_is_still_detected():
    assert "NON_STANDARD_AUDIT" in _event_types("2025年度财务报表审计报告出具保留意见")
    assert "NON_STANDARD_AUDIT" in _event_types("审计机构出具无法表示意见的审计报告")



def test_resolved_funds_occupation_title_is_not_active():
    title = "关于公司自查发现控股股东及其附属企业资金占用并已解决等情况的公告"
    events = _classify_material_events(title, publish_date=PUBLISH_DATE, as_of=AS_OF)
    funds = [row for row in events if row.get("event_type") == "FUNDS_OCCUPATION"]
    assert len(funds) == 1
    assert funds[0]["event_status"] == "RESOLVED"
    assert funds[0]["event_resolution_scope"] == "FULL"
    assert funds[0]["direction"] == "NEUTRAL"


def test_non_standard_audit_impact_eliminated_is_resolved_even_without_nearby_nonstandard_word():
    title = (
        "关于公司2024年度审计报告带强调事项段的保留意见和内部控制审计报告"
        "带强调事项段的无保留意见涉及事项影响已消除的专项说明的审核报告"
    )
    events = _classify_material_events(title, publish_date=PUBLISH_DATE, as_of=AS_OF)
    audit = [row for row in events if row.get("event_type") == "NON_STANDARD_AUDIT"]
    assert len(audit) == 1
    assert audit[0]["event_status"] == "RESOLVED"
    assert audit[0]["event_resolution_scope"] == "FULL"


def test_whether_risk_exists_due_diligence_title_is_not_incident_assertion():
    title = (
        "国联民生承销保荐关于公司是否存在财务造假、资金占用、募集资金违规"
        "等重大违法行为或公司治理是否出现重大异常且影响发行条件的核查意见"
    )
    types = _event_types(title)
    assert "ACCOUNTING_FRAUD" not in types
    assert "FUNDS_OCCUPATION" not in types

def test_production_historical_non_assertive_titles_do_not_reactivate_risk():
    cases = (
        (
            "董事会关于拟购买资产资金占用问题的说明",
            {"FUNDS_OCCUPATION"},
        ),
        (
            "关联方非经营性资金占用及清偿情况和违规担保及解除情况的专项报告",
            {"FUNDS_OCCUPATION", "ILLEGAL_GUARANTEE"},
        ),
        (
            "控股股东及其他关联方占用资金情况的专项审计说明",
            {"FUNDS_OCCUPATION"},
        ),
        (
            "防止大股东及关联方占用资金制度",
            {"FUNDS_OCCUPATION"},
        ),
        (
            "防止大股东及关联方占用资金制度（2025.8）",
            {"FUNDS_OCCUPATION"},
        ),
    )
    for title, forbidden in cases:
        assert forbidden.isdisjoint(_event_types(title)), title


def test_reversed_wording_true_funds_occupation_incident_remains_detected():
    title = "关于发现控股股东占用资金事项及整改进展的公告"
    assert "FUNDS_OCCUPATION" in _event_types(title)


def test_true_illegal_guarantee_incident_remains_detected():
    title = "关于发现违规担保事项及整改进展的公告"
    assert "ILLEGAL_GUARANTEE" in _event_types(title)

