from __future__ import annotations

from src.strategies.genge_opportunity_discovery.evidence_collectors.multi_year_predictability import (
    classify_multi_year_metrics,
    extract_report_metrics,
)


def test_metric_label_unit_year_series_maps_requested_fiscal_year():
    text = """
    主要会计数据和财务指标
    营业收入(亿元) 同比下降2.98% 2021 1,738.63 2022 1,729.91 2023 1,862.69 2024 2,130.29 2025 2,066.84
    归属于上市公司股东的净利润(亿元) 2021 51.06 2022 60.67 2023 82.50 2024 135.32 2025 203.39
    经营活动产生的现金流量净额(亿元) 2021 61.91 2022 154.54 2023 155.42 2024 323.87 2025 208.43
    """
    metrics = extract_report_metrics(text, 2025)

    assert metrics["revenue"] == 2066.84 * 100_000_000
    assert metrics["net_profit"] == 203.39 * 100_000_000
    assert metrics["operating_cash_flow"] == 208.43 * 100_000_000
    assert metrics["metric_provenance"]["revenue"]["unit_source"] == "METRIC_LABEL"
    assert metrics["metric_provenance"]["revenue"]["reason"] == "TARGET_FISCAL_YEAR_SERIES_NORMALIZED_TO_YUAN"


def test_scoped_product_revenue_before_company_series_is_not_company_total():
    text = """
    2025年公司铜产品营业收入为550.96亿元，同比增长明显。
    主要会计数据和财务指标
    营业收入（亿元） 2021 1,738.63 2022 1,729.91 2023 1,862.69 2024 2,130.29 2025 2,066.84
    归属于上市公司股东的净利润（亿元） 2021 51.06 2022 60.67 2023 82.50 2024 135.32 2025 203.39
    经营活动产生的现金流量净额（亿元） 2021 61.91 2022 154.54 2023 155.42 2024 323.87 2025 208.43
    """
    metrics = extract_report_metrics(text, 2025)

    assert metrics["revenue"] == 2066.84 * 100_000_000
    assert metrics["revenue"] != 550.96 * 100_000_000


def test_product_only_revenue_cannot_complete_company_metric():
    text = """
    铜产品营业收入550.96亿元。
    归属于上市公司股东的净利润203.39亿元。
    经营活动产生的现金流量净额208.43亿元。
    """
    metrics = extract_report_metrics(text, 2025)

    assert metrics["revenue"] is None
    assert metrics["metric_provenance"]["revenue"]["verified"] is False
    assert metrics["metric_provenance"]["revenue"]["reason"] == "SCOPED_METRIC_CONTEXT_NOT_COMPANY_TOTAL"

    decision, reason = classify_multi_year_metrics(
        [metrics, metrics, metrics], cyclical_or_resource=False
    )
    assert decision == "UNKNOWN"
    assert reason == "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"


def test_metric_label_series_missing_target_year_fails_closed():
    text = """
    营业收入(亿元) 2022 100.0 2023 110.0 2024 120.0
    归属于上市公司股东的净利润(亿元) 2022 10.0 2023 11.0 2024 12.0
    经营活动产生的现金流量净额(亿元) 2022 12.0 2023 13.0 2024 14.0
    """
    metrics = extract_report_metrics(text, 2025)

    assert metrics["revenue"] is None
    assert metrics["metric_provenance"]["revenue"]["reason"] == "TARGET_FISCAL_YEAR_VALUE_NOT_FOUND_IN_METRIC_SERIES"
