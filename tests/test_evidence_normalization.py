from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.evidence_collectors.evidence_normalization import (
    AMBIGUOUS_MATCH,
    PARSE_FAILED,
    SOURCE_DATA_ABSENT,
    SOURCE_FETCH_FAILED,
    STRUCTURE_RECOVERY_FAILED,
    VALUE_RECOVERED,
    VALUE_VERIFIED,
    extract_labeled_numeric_evidence,
    extract_with_fallback_sources,
    failure_evidence,
    normalize_evidence_text,
    parse_numeric_value,
)
from src.strategies.genge_opportunity_discovery.evidence_collectors.validators import (
    extract_numeric_context,
    extract_numeric_context_detailed,
)


def _currency(text: str, **kwargs):
    return extract_labeled_numeric_evidence(
        text,
        labels=["营业收入"],
        expected_unit_family="CURRENCY",
        **kwargs,
    )


def test_same_line_metric_and_value_is_verified() -> None:
    result = _currency("营业收入 12,345.67万元")
    assert result.status == VALUE_VERIFIED
    assert result.numeric_value == pytest.approx(12345.67)
    assert result.normalized_value == pytest.approx(123456700.0)
    assert result.unit == "万元"


def test_metric_label_can_be_split_across_lines() -> None:
    result = _currency("单位:万元\n营业\n收入\n12,345.67")
    assert result.status == VALUE_RECOVERED
    assert result.normalized_value == pytest.approx(123456700.0)


def test_numeric_value_can_be_split_across_lines() -> None:
    result = _currency("单位:万元\n营业收入\n12,345.\n67")
    assert result.status == VALUE_RECOVERED
    assert result.numeric_value == pytest.approx(12345.67)


def test_extra_spaces_tabs_and_fullwidth_punctuation_are_normalized() -> None:
    result = _currency("单位 ： 人 民 币 万 元\n营 业 收 入\t  １２，３４５．６７")
    assert result.status == VALUE_RECOVERED
    assert result.normalized_value == pytest.approx(123456700.0)


def test_thousands_separator_is_not_mistaken_for_multiple_values() -> None:
    result = _currency("营业收入 1,234,567.89元")
    assert result.status == VALUE_VERIFIED
    assert result.numeric_value == pytest.approx(1234567.89)


def test_percentage_is_parsed_with_semantic_unit() -> None:
    result = extract_labeled_numeric_evidence(
        "毛利率 35.20%",
        labels=["毛利率"],
        expected_unit_family="PERCENT",
    )
    assert result.status == VALUE_VERIFIED
    assert result.normalized_value == pytest.approx(35.2)
    assert result.normalized_unit == "PERCENT"


def test_wan_yuan_is_normalized_to_yuan() -> None:
    result = _currency("营业收入 12.5万元")
    assert result.normalized_value == pytest.approx(125000.0)
    assert result.normalized_unit == "CNY_YUAN"


def test_yi_yuan_is_normalized_to_yuan() -> None:
    result = _currency("营业收入 1.25亿元")
    assert result.normalized_value == pytest.approx(125000000.0)


def test_parenthesized_negative_is_preserved_not_guessed() -> None:
    result = parse_numeric_value("(1,234.50)万元", expected_unit_family="CURRENCY")
    assert result.status == VALUE_VERIFIED
    assert result.numeric_value == pytest.approx(-1234.5)
    assert result.normalized_value == pytest.approx(-12345000.0)


def test_nearby_table_unit_header_can_cross_page_break() -> None:
    result = _currency(
        "金额单位:万元\n2024年度 2023年度\n--- PAGE BREAK ---\n营业收入\n12,345.67"
    )
    assert result.status == VALUE_RECOVERED
    assert result.unit_source == "DECLARED_CONTEXT"
    assert result.normalized_value == pytest.approx(123456700.0)


def test_metric_alias_resolves_to_canonical_label() -> None:
    canonical = "归属于上市公司股东的净利润"
    result = extract_labeled_numeric_evidence(
        "归属于母公司\n股东的净利润 2.30亿元",
        labels=[canonical],
        aliases={canonical: ["归属于母公司股东的净利润"]},
        expected_unit_family="CURRENCY",
    )
    assert result.status == VALUE_RECOVERED
    assert result.canonical_label == canonical
    assert result.matched_label == "归属于母公司股东的净利润"
    assert result.normalized_value == pytest.approx(230000000.0)


def test_multiple_numbers_only_semantic_unit_match_survives() -> None:
    result = _currency("营业收入 1,234.50万元，同比增长 10.2%")
    assert result.status in {VALUE_VERIFIED, VALUE_RECOVERED}
    assert result.normalized_value == pytest.approx(12345000.0)


def test_two_materially_possible_values_fail_closed() -> None:
    result = _currency("营业收入 1,234.50万元 1,300.00万元")
    assert result.status == AMBIGUOUS_MATCH
    assert result.normalized_value is None


def test_truly_absent_source_data_stays_absent() -> None:
    result = _currency("净利润 10.0万元")
    assert result.status == SOURCE_DATA_ABSENT
    assert result.normalized_value is None


def test_failed_primary_parser_can_recover_from_public_fallback_source() -> None:
    result = extract_with_fallback_sources(
        [
            {
                "status": PARSE_FAILED,
                "source_url": "https://primary.example/report.pdf",
                "document_id": "primary",
                "report_period": "2025",
            },
            {
                "text": "营业收入 8.88亿元",
                "source_url": "https://backup.example/report.html",
                "document_id": "backup",
                "report_period": "2025",
            },
        ],
        labels=["营业收入"],
        expected_unit_family="CURRENCY",
    )
    assert result.status in {VALUE_VERIFIED, VALUE_RECOVERED}
    assert result.normalized_value == pytest.approx(888000000.0)
    assert result.document_id == "backup"


def test_unknown_or_parse_failure_is_never_pass() -> None:
    absent = _currency("营业收入 未披露")
    failed = parse_numeric_value("not-a-number", expected_unit_family="CURRENCY")
    fetch_failed = failure_evidence(SOURCE_FETCH_FAILED, reason="timeout")
    assert absent.status == STRUCTURE_RECOVERY_FAILED
    assert failed.status == PARSE_FAILED
    assert fetch_failed.status == SOURCE_FETCH_FAILED
    assert all(item.status not in {"PASS", VALUE_VERIFIED, VALUE_RECOVERED}
               for item in (absent, failed, fetch_failed))


def test_authority_invariants_remain_fail_closed() -> None:
    payload = json.loads(
        Path("data/deep_calculation/latest_research_decisions.json").read_text(encoding="utf-8")
    )
    assert payload["research_authority"] == "RESEARCH_ONLY"
    assert payload["formal_trading_authority"] is False
    assert payload["automatic_formal_buy_allowed"] is False
    assert payload["unknown_is_pass"] is False
    assert payload["no_auto_trade"] is True


def test_robust_layer_contains_no_candidate_specific_hardcode() -> None:
    for path in (
        Path("src/strategies/genge_opportunity_discovery/evidence_collectors/evidence_normalization.py"),
        Path("src/strategies/genge_opportunity_discovery/evidence_collectors/validators.py"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "603055" not in text
        assert "34565436187" not in text
        assert "34586652294" not in text


def test_existing_good_numeric_context_is_byte_for_byte_compatible() -> None:
    text = "营业收入 1,234.50万元"
    assert extract_numeric_context(text, ["营业收入"]) == {
        "value": "1234.50",
        "unit": "万元",
        "excerpt": text,
    }
    detail = extract_numeric_context_detailed(text, ["营业收入"])
    assert detail["status"] == VALUE_VERIFIED
    assert detail["extraction_method"] == "LEGACY_SAME_LINE"


def test_legacy_numeric_context_recovers_split_label_and_value() -> None:
    result = extract_numeric_context("营业\n收入\n1,234.50\n万元", ["营业收入"])
    assert result["value"] == "1234.50"
    assert result["unit"] == "万元"


def test_bp_and_percentage_point_units_are_not_conflated() -> None:
    bp = parse_numeric_value("25bp", expected_unit_family="BASIS_POINT")
    pp = parse_numeric_value("0.25个百分点", expected_unit_family="PERCENTAGE_POINT")
    assert bp.status == VALUE_VERIFIED
    assert bp.normalized_unit == "BASIS_POINT"
    assert pp.status == VALUE_VERIFIED
    assert pp.normalized_unit == "PERCENTAGE_POINT"


def test_conflicting_fallback_sources_fail_closed() -> None:
    result = extract_with_fallback_sources(
        [
            {"text": "营业收入 1.00亿元", "document_id": "a", "report_period": "2025"},
            {"text": "营业收入 1.20亿元", "document_id": "b", "report_period": "2025"},
        ],
        labels=["营业收入"],
        expected_unit_family="CURRENCY",
    )
    assert result.status == AMBIGUOUS_MATCH
    assert result.reason == "CROSS_SOURCE_VALUE_CONFLICT"


def test_normalizer_repairs_only_representation_not_missing_digits() -> None:
    normalized = normalize_evidence_text("１２，３４５．６７ 万 元")
    assert normalized == "12,345.67 万元"
    failed = parse_numeric_value("12,34万元", expected_unit_family="CURRENCY")
    assert failed.status == PARSE_FAILED
