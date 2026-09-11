from __future__ import annotations

from src.strategies.genge_opportunity_discovery.evidence_collectors.multi_year_predictability import (
    classify_multi_year_metrics,
    extract_report_metrics,
)
from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    close_profiles,
    infer_predictability,
)


def _measurement(value, unit="元", source="TABLE_HEADER"):
    return {
        "value_yuan": float(value),
        "raw_value": float(value),
        "unit": unit,
        "unit_source": source,
        "verified": True,
        "reason": "TRUSTED_UNIT_NORMALIZED_TO_YUAN",
        "excerpt": "fixture",
    }


def _record(year, revenue, profit, cash_flow):
    provenance = {
        "revenue": _measurement(revenue),
        "net_profit": _measurement(profit),
        "operating_cash_flow": _measurement(cash_flow),
    }
    return {
        "fiscal_year": year,
        "revenue": float(revenue),
        "net_profit": float(profit),
        "operating_cash_flow": float(cash_flow),
        "metric_provenance": provenance,
        "normalization_unit": "CNY_YUAN",
        "unit_provenance_required": True,
    }


def _stable_records():
    return [
        _record(2022, 100.0, 10.0, 12.0),
        _record(2023, 108.0, 11.0, 13.0),
        _record(2024, 116.0, 12.0, 14.0),
    ]


def _strict_row(code="000001", decision="PASS"):
    return {
        "code": code,
        "evidence_kind": "multi_year_predictability",
        "indicator": "predictability_multi_year_official",
        "predictability_classification": decision,
        "reason_code": "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN",
        "rule_version": "PREDICTABILITY_MULTI_YEAR_OFFICIAL_V2",
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


def test_header_unit_is_normalized_to_yuan_with_provenance():
    text = """
    主要会计数据和财务指标
    单位：万元 币种：人民币
    营业收入 12,345.60 11,000.00
    归属于上市公司股东的净利润 1,234.50 1,100.00
    经营活动产生的现金流量净额 1,500.25 1,400.00
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] == 12345.60 * 10_000
    assert metrics["net_profit"] == 1234.50 * 10_000
    assert metrics["operating_cash_flow"] == 1500.25 * 10_000
    assert metrics["metric_provenance"]["revenue"]["unit"] == "万元"
    assert metrics["metric_provenance"]["revenue"]["unit_source"] == "TABLE_HEADER"
    assert metrics["metric_provenance"]["revenue"]["verified"] is True


def test_inline_units_are_normalized_without_header():
    text = """
    营业收入 123.45亿元
    归属于上市公司股东的净利润 12.30亿元
    经营活动产生的现金流量净额 15.50亿元
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] == 123.45 * 100_000_000
    assert metrics["net_profit"] == 12.30 * 100_000_000
    assert metrics["operating_cash_flow"] == 15.50 * 100_000_000
    assert metrics["metric_provenance"]["revenue"]["unit_source"] == "INLINE"


def test_renminbi_yuan_header_is_supported():
    text = """
    单位：人民币元
    营业收入 1,234,567,890.00
    归属于上市公司股东的净利润 123,456,789.00
    经营活动产生的现金流量净额 234,567,890.00
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] == 1_234_567_890.0
    assert metrics["metric_provenance"]["revenue"]["unit"] == "元"


def test_missing_unit_provenance_makes_year_incomplete():
    text = """
    营业收入 12,345.60
    归属于上市公司股东的净利润 1,234.50
    经营活动产生的现金流量净额 1,500.25
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] is None
    assert metrics["metric_provenance"]["revenue"]["verified"] is False
    records = [
        metrics,
        extract_report_metrics(text, 2023),
        extract_report_metrics(text, 2022),
    ]
    decision, reason = classify_multi_year_metrics(
        records, cyclical_or_resource=False
    )
    assert decision == "UNKNOWN"
    assert reason == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"


def test_conflicting_inline_and_header_units_are_rejected():
    text = """
    单位：万元
    营业收入 123.45亿元
    归属于上市公司股东的净利润 12.30亿元
    经营活动产生的现金流量净额 15.50亿元
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] is None
    assert metrics["metric_provenance"]["revenue"]["verified"] is False
    assert (
        metrics["metric_provenance"]["revenue"]["reason"]
        == "INLINE_HEADER_UNIT_CONFLICT"
    )


def test_dates_years_and_percentages_are_not_selected_as_metric_values():
    text = """
    单位：万元
    营业收入 2024年12月31日 同比增长 25.3% 12,345.60
    归属于上市公司股东的净利润 2024年12月31日 1,234.50
    经营活动产生的现金流量净额 2024年12月31日 1,500.25
    """
    metrics = extract_report_metrics(text, 2024)
    assert metrics["revenue"] == 12345.60 * 10_000
    assert metrics["net_profit"] == 1234.50 * 10_000
    assert metrics["operating_cash_flow"] == 1500.25 * 10_000


def test_metric_label_unit_year_series_beats_scoped_product_revenue():
    text = """
    报告期内，铜产品营业收入为550.96亿元，同比增长18%。
    主要会计数据和财务指标
    营业收入(亿元) 2021 1,738.63 2022 1,729.91 2023 1,862.69 2024 2,130.29 2025 2,066.84
    归属于上市公司股东的净利润(亿元) 2021 51.06 2022 60.67 2023 82.50 2024 135.32 2025 203.39
    经营活动产生的现金流量净额(亿元) 2021 61.91 2022 154.54 2023 155.42 2024 323.87 2025 208.43
    """
    metrics = extract_report_metrics(text, 2025)
    assert metrics["revenue"] == 2066.84 * 100_000_000
    assert metrics["net_profit"] == 203.39 * 100_000_000
    assert metrics["operating_cash_flow"] == 208.43 * 100_000_000
    assert metrics["metric_provenance"]["revenue"]["unit_source"] == "METRIC_LABEL"
    assert "550.96" not in metrics["metric_provenance"]["revenue"]["excerpt"]


def test_scoped_product_revenue_cannot_stand_in_for_company_revenue():
    text = "报告期内，铜产品营业收入为550.96亿元，同比增长18%。"
    metrics = extract_report_metrics(text, 2025)
    assert metrics["revenue"] is None
    assert metrics["metric_provenance"]["revenue"]["verified"] is False
    assert (
        metrics["metric_provenance"]["revenue"]["reason"]
        == "SCOPED_SUBTOTAL_NOT_COMPANY_METRIC"
    )


def test_non_cyclical_three_year_stable_official_metrics_can_pass():
    decision, reason = classify_multi_year_metrics(
        _stable_records(), cyclical_or_resource=False
    )
    assert decision == "PASS"
    assert reason == "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN"


def test_untrusted_metric_provenance_cannot_pass():
    records = _stable_records()
    records[1]["metric_provenance"]["revenue"]["verified"] = False
    decision, reason = classify_multi_year_metrics(
        records, cyclical_or_resource=False
    )
    assert decision == "UNKNOWN"
    assert reason == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"


def test_missing_complete_years_remain_unknown():
    records = _stable_records()[:2]
    decision, reason = classify_multi_year_metrics(
        records, cyclical_or_resource=False
    )
    assert decision == "UNKNOWN"
    assert reason == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"


def test_resource_company_cannot_pass_from_accounting_growth_alone():
    decision, reason = classify_multi_year_metrics(
        _stable_records(), cyclical_or_resource=True
    )
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
                    "financial_safety": {
                        "status": "FAIL",
                        "rationale": "verified funds occupation",
                    },
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
        evidence_summary={
            "collection_attempt_count": 1,
            "unique_evidence_count": 1,
        },
    )
    gates = closed["profiles"]["603233"]["gates"]
    assert gates["predictability"]["status"] == "PASS"
    assert gates["financial_safety"]["status"] == "FAIL"
    assert status["formal_trading_authority"] is False
    assert status["automatic_formal_buy_allowed"] is False
    assert status["unknown_is_pass"] is False
    assert status["no_auto_trade"] is True
