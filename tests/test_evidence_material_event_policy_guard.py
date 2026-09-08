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
