import csv
from pathlib import Path

from src.strategies.genge_opportunity_discovery.specialized_valuation_authoritative_merge import merge_report
from src.strategies.genge_opportunity_discovery.v31_review_queue import write_report as write_v31_report


def _write_csv(path: Path, rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_one(path: Path):
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))[0]


def test_v31_boundary_overlays_completed_insurance_execution_over_stale_routing_state(tmp_path: Path):
    valuation_root = tmp_path / "valuation"
    report = valuation_root / "20260901"
    report.mkdir(parents=True)
    _write_csv(
        report / "valuation_research_routed.csv",
        [{
            "code": "601318",
            "stock_name": "中国平安",
            "valuation_primary_strategy_id": "insurance_embedded_value",
            "valuation_research_rank": "1",
            "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
            "valuation_model_next_action": "run_specialized_model:insurance_embedded_value",
        }],
    )
    _write_csv(
        report / "valuation_research_specialized.csv",
        [{
            "code": "601318",
            "specialized_model_executed": "False",
            "specialized_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
            "specialized_model_status": "DISCLOSED_EV_NBV_INPUTS_REQUIRED",
            "specialized_model_execution_reason": "DISCLOSED_EV_NBV_INPUTS_REQUIRED",
        }],
    )
    _write_csv(
        report / "insurance_valuation_execution.csv",
        [{
            "code": "601318",
            "insurance_model_executed": "True",
            "insurance_model_execution_state": "INSURANCE_MODEL_EXECUTED_RESEARCH_ONLY",
            "insurance_model_status": "OK",
            "insurance_model_execution_reason": "reverse_market_implied_nbv_franchise_multiple_only",
            "insurance_model_next_action": "review_market_implied_nbv_franchise_value_before_any_formal_decision",
            "insurance_evidence_status": "VALID",
            "insurance_evidence_source_url": "https://example.invalid/pingan.pdf",
            "insurance_input_evidence_as_of": "2025-12-31",
            "insurance_input_known_at": "2026-03-26",
            "insurance_embedded_value_per_share": "83.07",
            "insurance_normalized_annual_nbv_cny_million": "36897",
            "valuation_evidence_status": "VALID",
            "valuation_model_status": "EXECUTED",
            "valuation_anchor_status": "REFERENCE_AVAILABLE",
            "valuation_completion_status": "COMPLETED_WITH_REFERENCE_ANCHOR",
            "valuation_reference_anchor_kind": "DISCLOSED_EMBEDDED_VALUE",
            "valuation_reference_anchor_per_share": "83.07",
        }],
    )
    all_a = tmp_path / "all_a"
    all_a.mkdir()
    (all_a / "run_summary.json").write_text("{}", encoding="utf-8")

    rows = write_v31_report(valuation_root, all_a, tmp_path / "v31", priority_json=None, limit=10)
    row = rows[0]

    assert row["valuation_model_execution_state"] == "INSURANCE_MODEL_EXECUTED_RESEARCH_ONLY"
    assert row["specialized_model_execution_state"] == "INSURANCE_MODEL_EXECUTED_RESEARCH_ONLY"
    assert str(row["specialized_model_executed"]).lower() == "true"
    assert row["valuation_strategy_evidence_status"] == "VALID"
    assert row["valuation_strategy_model_status"] == "EXECUTED"
    assert row["valuation_strategy_anchor_status"] == "REFERENCE_AVAILABLE"
    assert row["v31_valuation_completion_status"] == "COMPLETED_WITH_REFERENCE_ANCHOR"
    assert row["v31_valuation_followup_reason"] == ""
    assert row["valuation_reference_anchor_per_share"] == "83.07"
    assert row["insurance_normalized_annual_nbv_cny_million"] == "36897"
    assert row["formal_signal_eligible"] is False
    assert row["no_auto_trade"] is True


def test_actual_bank_strategy_id_is_completion_aware(tmp_path: Path):
    report = tmp_path / "valuation" / "20260901"
    report.mkdir(parents=True)
    _write_csv(
        report / "valuation_research_routed.csv",
        [{
            "code": "600000",
            "stock_name": "测试银行",
            "valuation_primary_strategy_id": "bank_residual_income",
            "valuation_research_rank": "1",
            "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        }],
    )
    _write_csv(
        report / "bank_valuation_execution.csv",
        [{
            "code": "600000",
            "bank_model_executed": "True",
            "bank_model_state": "EXECUTED_FAIL_CLOSED",
            "bank_model_status": "NO_REFERENCE_ANCHOR",
            "bank_fair_pb": "",
            "bank_next_action": "review_bank_inputs",
        }],
    )

    merge_report(tmp_path / "valuation")
    row = _read_one(report / "valuation_research_routed.csv")
    assert row["valuation_model_execution_state"] == "EXECUTED_FAIL_CLOSED"
    assert row["valuation_strategy_model_status"] == "EXECUTED"
    assert row["valuation_strategy_anchor_status"] == "UNAVAILABLE"
    assert row["valuation_strategy_completion_status"] == "COMPLETED_NO_ANCHOR"
    assert row["valuation_strategy_followup_reason"] == "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR"


def test_missing_resource_inputs_remain_fail_closed_and_generic_reverse_is_not_regressed(tmp_path: Path):
    report = tmp_path / "valuation" / "20260901"
    report.mkdir(parents=True)
    _write_csv(
        report / "valuation_research_routed.csv",
        [
            {
                "code": "603993",
                "stock_name": "洛阳钼业",
                "valuation_primary_strategy_id": "resource_asset_nav",
                "valuation_research_rank": "1",
                "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
            },
            {
                "code": "000001",
                "stock_name": "通用估值测试",
                "valuation_primary_strategy_id": "general_reverse_earnings",
                "valuation_research_rank": "2",
                "valuation_model_execution_state": "GENERIC_REVERSE_DIAGNOSTIC_READY",
                "valuation_model_next_action": "review_reverse_earnings_expectation_gap",
            },
        ],
    )
    _write_csv(
        report / "valuation_research_resource_nav.csv",
        [{
            "code": "603993",
            "resource_nav_executed": "False",
            "resource_nav_status": "RESOURCE_INPUTS_REQUIRED",
            "resource_nav_next_action": "collect_reserves_production_cost_ownership_and_four_scenario_price_decks",
        }],
    )

    merge_report(tmp_path / "valuation")
    with (report / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        rows = {row["code"]: row for row in csv.DictReader(stream)}

    resource = rows["603993"]
    assert resource["valuation_strategy_evidence_status"] == "MISSING"
    assert resource["valuation_strategy_model_status"] == "NOT_EXECUTED"
    assert resource["valuation_strategy_completion_status"] == "UNFINISHED"
    assert resource["valuation_model_execution_state"] == "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
    assert resource["no_auto_trade"] == "True"

    generic = rows["000001"]
    assert generic["valuation_model_execution_state"] == "GENERIC_REVERSE_DIAGNOSTIC_READY"
    assert generic["valuation_model_next_action"] == "review_reverse_earnings_expectation_gap"
    assert generic["valuation_strategy_completion_status"] == "NOT_APPLICABLE"
