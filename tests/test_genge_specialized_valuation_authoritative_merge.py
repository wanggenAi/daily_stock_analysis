import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.specialized_valuation_authoritative_merge import merge_report
from src.strategies.genge_opportunity_discovery.v31_review_queue import build_review_rows


def _write_csv(path: Path, rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_insurance_and_resource_completion_are_merged_and_passed_to_v31(tmp_path: Path):
    report = tmp_path / "20260901"
    report.mkdir()
    base = [
        {"code": "601318", "stock_name": "中国平安", "valuation_primary_strategy_id": "insurance_embedded_value", "valuation_research_rank": "1"},
        {"code": "603993", "stock_name": "洛阳钼业", "valuation_primary_strategy_id": "resource_asset_nav", "valuation_research_rank": "2"},
    ]
    _write_csv(report / "valuation_research_routed.csv", base)
    _write_csv(
        report / "insurance_valuation_execution.csv",
        [
            {"code": "601318", "insurance_model_executed": "True", "valuation_evidence_status": "VALID", "valuation_model_status": "EXECUTED", "valuation_anchor_status": "REFERENCE_AVAILABLE", "valuation_completion_status": "COMPLETED_WITH_REFERENCE_ANCHOR", "valuation_reference_anchor_per_share": "83.07", "insurance_evidence_source_url": "https://example.invalid/pingan.pdf"},
            {"code": "603993", "insurance_model_executed": "False"},
        ],
    )
    _write_csv(
        report / "valuation_research_resource_nav.csv",
        [
            {"code": "601318", "resource_nav_executed": "False", "resource_nav_status": "NOT_RESOURCE_ROUTE"},
            {"code": "603993", "resource_nav_executed": "True", "resource_nav_status": "OK", "resource_nav_base_per_share": "22.50", "resource_nav_base_margin_of_safety": "0.15"},
        ],
    )

    summary = merge_report(tmp_path)
    assert summary["completed_with_anchor_count"] == 2
    with (report / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    by_code = {row["code"]: row for row in rows}
    assert by_code["601318"]["valuation_strategy_completion_status"] == "COMPLETED_WITH_REFERENCE_ANCHOR"
    assert by_code["601318"]["valuation_reference_anchor_per_share"] == "83.07"
    assert by_code["603993"]["valuation_strategy_evidence_status"] == "VALID"
    assert by_code["603993"]["valuation_strategy_anchor_status"] == "REFERENCE_AVAILABLE"

    v31 = build_review_rows(rows, plan_map={}, limit=10)
    v31_by_code = {row["code"]: row for row in v31}
    assert v31_by_code["601318"]["v31_valuation_completion_status"] == "COMPLETED_WITH_REFERENCE_ANCHOR"
    assert v31_by_code["601318"]["valuation_reference_anchor_per_share"] == "83.07"
    assert v31_by_code["603993"]["resource_nav_base_per_share"] == "22.50"
    assert all(row["formal_signal_eligible"] is False for row in v31)
    assert all(row["no_auto_trade"] is True for row in v31)


def test_executed_without_anchor_is_completed_not_unfinished(tmp_path: Path):
    report = tmp_path / "20260901"
    report.mkdir()
    _write_csv(
        report / "valuation_research_routed.csv",
        [{"code": "600000", "stock_name": "测试银行", "valuation_primary_strategy_id": "bank_book_value", "valuation_research_rank": "1"}],
    )
    _write_csv(
        report / "bank_valuation_execution.csv",
        [{"code": "600000", "bank_model_executed": "True", "bank_model_state": "EXECUTED_FAIL_CLOSED", "bank_fair_pb": ""}],
    )
    merge_report(tmp_path)
    with (report / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        row = list(csv.DictReader(stream))[0]
    assert row["valuation_strategy_model_status"] == "EXECUTED"
    assert row["valuation_strategy_anchor_status"] == "UNAVAILABLE"
    assert row["valuation_strategy_completion_status"] == "COMPLETED_NO_ANCHOR"
    assert row["valuation_strategy_followup_reason"] == "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR"


def test_missing_resource_inputs_remain_explicitly_unfinished(tmp_path: Path):
    report = tmp_path / "20260901"
    report.mkdir()
    _write_csv(
        report / "valuation_research_routed.csv",
        [{"code": "603993", "stock_name": "洛阳钼业", "valuation_primary_strategy_id": "resource_asset_nav", "valuation_research_rank": "1"}],
    )
    _write_csv(
        report / "valuation_research_resource_nav.csv",
        [{"code": "603993", "resource_nav_executed": "False", "resource_nav_status": "RESOURCE_INPUTS_REQUIRED"}],
    )
    summary = merge_report(tmp_path)
    assert summary["unfinished_count"] == 1
    with (report / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        row = list(csv.DictReader(stream))[0]
    assert row["valuation_strategy_evidence_status"] == "MISSING"
    assert row["valuation_strategy_model_status"] == "NOT_EXECUTED"
    assert row["valuation_strategy_completion_status"] == "UNFINISHED"
    assert row["valuation_strategy_followup_reason"] == "VALUATION_STRATEGY_UNFINISHED"
