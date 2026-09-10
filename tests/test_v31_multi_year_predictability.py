from __future__ import annotations

from src.strategies.genge_opportunity_discovery.evidence_collectors.multi_year_predictability import (
    classify_multi_year_metrics,
)
from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    close_profiles,
    infer_predictability,
)


def _stable_records():
    return [
        {"fiscal_year": 2022, "revenue": 100.0, "net_profit": 10.0, "operating_cash_flow": 12.0},
        {"fiscal_year": 2023, "revenue": 108.0, "net_profit": 11.0, "operating_cash_flow": 13.0},
        {"fiscal_year": 2024, "revenue": 116.0, "net_profit": 12.0, "operating_cash_flow": 14.0},
    ]


def _strict_row(code="000001", decision="PASS"):
    return {
        "code": code,
        "evidence_kind": "multi_year_predictability",
        "indicator": "predictability_multi_year_official",
        "predictability_classification": decision,
        "reason_code": "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN",
        "rule_version": "PREDICTABILITY_MULTI_YEAR_OFFICIAL_V1",
        "coverage_years": [2022, 2023, 2024],
        "metrics_by_year": _stable_records(),
        "cyclical_or_resource": False,
        "evidence_status": "VERIFIED",
        "source_type": "OFFICIAL_REPORT",
        "source_domain": "static.cninfo.com.cn",
        "publish_date": "2025-03-31",
        "original_url": "https://static.cninfo.com.cn/example.pdf",
        "adopted_for_gate": True,
        "authority_crossed": False,
        "formal_decision": False,
    }


def test_non_cyclical_three_year_stable_official_metrics_can_pass():
    decision, reason = classify_multi_year_metrics(_stable_records(), cyclical_or_resource=False)
    assert decision == "PASS"
    assert reason == "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN"


def test_missing_complete_years_remain_unknown():
    records = _stable_records()[:2]
    decision, reason = classify_multi_year_metrics(records, cyclical_or_resource=False)
    assert decision == "UNKNOWN"
    assert reason == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"


def test_resource_company_cannot_pass_from_accounting_growth_alone():
    decision, reason = classify_multi_year_metrics(_stable_records(), cyclical_or_resource=True)
    assert decision == "UNKNOWN"
    assert reason == "CYCLICAL_RESOURCE_REQUIRES_EXPLICIT_CYCLE_RESILIENCE_EVIDENCE"


def test_generic_growth_evidence_cannot_resolve_predictability():
    generic = {
        "code": "000001",
        "evidence_kind": "long_term_demand",
        "evidence_status": "VERIFIED",
        "source_type": "OFFICIAL_REPORT",
        "source_domain": "gov.cn",
        "publish_date": "2025-01-01",
        "normalized_summary": "industry demand grew 20%",
        "adopted_for_gate": True,
    }
    decision, _, evidence = infer_predictability("000001", [generic])
    assert decision == "UNKNOWN"
    assert evidence == []


def test_dedicated_strict_official_row_resolves_predictability():
    decision, rationale, evidence = infer_predictability("000001", [_strict_row()])
    assert decision == "PASS"
    assert "Strict multi-year official-report" in rationale
    assert evidence[0]["coverage_years"] == [2022, 2023, 2024]


def test_close_profiles_preserves_research_only_authority_and_existing_fail():
    profiles = {
        "profiles": {
            "603233": {
                "industry": "汽车零部件",
                "gates": {
                    "predictability": {"status": "UNKNOWN"},
                    "long_term_demand": {"status": "PASS"},
                    "moat": {"status": "PASS"},
                    "financial_safety": {"status": "FAIL", "rationale": "verified funds occupation"},
                    "earnings_authenticity": {"status": "PASS"},
                },
            }
        }
    }
    closed, status = close_profiles(
        profiles,
        [{"code": "603233", "industry": "汽车零部件"}],
        requested_codes=["603233"],
        industry_evidence=[],
        company_evidence=[_strict_row("603233")],
        evidence_audit=[],
        evidence_summary={"collection_attempt_count": 1, "unique_evidence_count": 1},
    )
    gates = closed["profiles"]["603233"]["gates"]
    assert gates["predictability"]["status"] == "PASS"
    assert gates["financial_safety"]["status"] == "FAIL"
    assert status["formal_trading_authority"] is False
    assert status["automatic_formal_buy_allowed"] is False
    assert status["unknown_is_pass"] is False
    assert status["no_auto_trade"] is True
