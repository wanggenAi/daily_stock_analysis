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

