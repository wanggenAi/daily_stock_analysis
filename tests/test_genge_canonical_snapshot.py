"""Regression tests for the shared V3.1.1 hourly/daily snapshot contract."""

import pytest

from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
    validate_snapshot,
)


def _production_row(
    code: str = "600003",
    *,
    scope: str = "CANDIDATE",
    action: str = "HOLD_REVIEW",
    **overrides,
) -> dict:
    row = {
        "code": code,
        "decision_scope": scope,
        "production_action": action,
        "production_model_version": PRODUCTION_VERSION,
        "v311_production_bridge": PRODUCTION_BRIDGE,
        "strict_pit_refresh_applied": True,
        "v311_expectation_input_status": "READY",
        "decision_date": "2026-08-27",
        "price_date": "2026-08-26",
        "current_price": "20.0",
        "v311_input_error": "",
        "upstream_policy_reused": False,
        "no_auto_trade": True,
    }
    row.update(overrides)
    return row


def test_discovery_is_not_capped_by_deep_review_or_ledger() -> None:
    discovery = [
        {"code": "600001", "quant_rank": "1", "quant_score": "90", "latest_trade_date": "2026-08-26"},
        {"code": "600002", "quant_rank": "2", "quant_score": "89", "latest_trade_date": "2026-08-26"},
        {"code": "600003", "quant_rank": "3", "quant_score": "88", "latest_trade_date": "2026-08-26"},
        # Research-only board must not enter the user's executable discovery pool.
        {"code": "688001", "quant_rank": "4", "quant_score": "99", "latest_trade_date": "2026-08-26"},
    ]
    deep_review = [
        {
            "code": "600003",
            "v31_review_rank": "1",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
        }
    ]
    production = [_production_row()]

    snapshot = build_snapshot(
        discovery,
        deep_review,
        production,
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )

    assert snapshot["discovery"]["execution_eligible_count"] == 3
    assert [row["code"] for row in snapshot["discovery"]["rows"]] == [
        "600001",
        "600002",
        "600003",
    ]
    assert snapshot["deep_review"]["execution_eligible_count"] == 1
    assert snapshot["architecture_contract"]["ledger_may_filter_discovery"] is False
    assert snapshot["architecture_contract"]["candidate_ledger_is_downstream_memory_only"] is True


def test_all_sections_share_snapshot_identity_and_run_changes_identity() -> None:
    kwargs = {
        "discovery_rows": [{"code": "600001", "latest_trade_date": "2026-08-26"}],
        "deep_review_rows": [],
        "production_rows": [],
        "source_kind": "test",
        "generated_at": "2026-08-27T00:00:00+00:00",
    }
    first = build_snapshot(source_run_id="1", **kwargs)
    second = build_snapshot(source_run_id="2", **kwargs)

    assert first["snapshot_id"] != second["snapshot_id"]
    assert {
        first[section]["snapshot_id"]
        for section in ("discovery", "deep_review", "production")
    } == {first["snapshot_id"]}
    validate_snapshot(first, expected_source_run_id="1")


def test_mixed_section_snapshot_fails_closed() -> None:
    snapshot = build_snapshot(
        [{"code": "600001"}],
        [],
        [],
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )
    snapshot["production"]["snapshot_id"] = "old-snapshot"

    with pytest.raises(ValueError, match="section mismatch"):
        validate_snapshot(snapshot)


def test_sync_contract_does_not_change_formal_buy_or_freshness_rules() -> None:
    snapshot = build_snapshot(
        [],
        [],
        [],
        source_kind="test",
        source_run_id="1",
        generated_at="2026-08-27T00:00:00+00:00",
    )

    assert snapshot["architecture_contract"]["formal_buy_thresholds_changed"] is False
    assert snapshot["freshness_contract"]["stale_or_unverified_price_may_promote_buy_add"] is False
    assert snapshot["freshness_contract"]["formal_buy_add_requires_verified_price_date"] is True
    assert snapshot["freshness_contract"]["production_rows_require_fresh_strict_pit_bridge"] is True


def test_wrong_production_version_or_authority_fails_closed() -> None:
    with pytest.raises(ValueError, match="version mismatch"):
        build_snapshot(
            [],
            [],
            [_production_row(production_model_version="OLD")],
            source_kind="test",
            source_run_id="1",
        )

    with pytest.raises(ValueError, match="bridge authority mismatch"):
        build_snapshot(
            [],
            [],
            [_production_row(v311_production_bridge="LEGACY")],
            source_kind="test",
            source_run_id="1",
        )


def test_buy_add_requires_ready_verified_price_date() -> None:
    with pytest.raises(ValueError, match="lacks READY"):
        build_snapshot(
            [],
            [],
            [_production_row(action="BUY", v311_expectation_input_status="HOLD_REVIEW_INPUT_INCOMPLETE")],
            source_kind="test",
            source_run_id="1",
        )

    with pytest.raises(ValueError, match="price date is unverified"):
        build_snapshot(
            [],
            [],
            [_production_row(action="ADD", price_date="")],
            source_kind="test",
            source_run_id="1",
        )


def test_duplicate_production_code_fails_closed() -> None:
    with pytest.raises(ValueError, match="duplicate code"):
        build_snapshot(
            [],
            [],
            [_production_row(), _production_row(scope="HOLDING")],
            source_kind="test",
            source_run_id="1",
        )


def test_specialized_valuation_evidence_survives_canonical_compaction() -> None:
    specialized = {
        "code": "601318",
        "stock_name": "中国平安",
        "v31_review_rank": "1",
        "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
        "valuation_primary_strategy_id": "insurance_appraisal",
        "valuation_strategy_evidence_status": "EVIDENCE_VALID",
        "valuation_strategy_model_status": "MODEL_EXECUTED",
        "valuation_strategy_anchor_status": "ANCHOR_AVAILABLE",
        "valuation_strategy_completion_status": "COMPLETED_WITH_ANCHOR",
        "valuation_reference_anchor_kind": "embedded_value_per_share",
        "valuation_reference_anchor_per_share": "83.07",
        "insurance_input_known_at": "2026-03-26",
        "insurance_input_evidence_as_of": "2025-12-31",
        "insurance_evidence_status": "VALID",
        "insurance_evidence_source_name": "Ping An 2025 Annual Report",
        "insurance_evidence_source_url": "https://group.pingan.com/",
        "insurance_embedded_value_cny_million": "1504288",
        "insurance_embedded_value_per_share": "83.07",
        "insurance_normalized_annual_nbv_cny_million": "36897",
        "insurance_model_executed": True,
        "insurance_model_execution_state": "EXECUTED_WITH_ANCHOR",
        "insurance_model_status": "OK",
    }
    production = _production_row(
        code="601318",
        scope="HOLDING",
        action="HOLD_REVIEW",
        stock_name="中国平安",
        **{key: value for key, value in specialized.items() if key not in {"code", "stock_name"}},
    )

    snapshot = build_snapshot(
        discovery_rows=[],
        deep_review_rows=[specialized],
        production_rows=[production],
        source_kind="test",
        source_run_id="specialized-1",
        generated_at="2026-09-02T00:00:00+00:00",
    )

    deep = snapshot["deep_review"]["rows"][0]
    holding = snapshot["production"]["holding_decisions"][0]
    for row in (deep, holding):
        assert row["valuation_primary_strategy_id"] == "insurance_appraisal"
        assert row["valuation_strategy_completion_status"] == "COMPLETED_WITH_ANCHOR"
        assert row["valuation_reference_anchor_per_share"] == "83.07"
        assert row["insurance_input_known_at"] == "2026-03-26"
        assert row["insurance_input_evidence_as_of"] == "2025-12-31"
        assert row["insurance_evidence_source_name"] == "Ping An 2025 Annual Report"
        assert row["insurance_embedded_value_cny_million"] == "1504288"
        assert row["insurance_normalized_annual_nbv_cny_million"] == "36897"
        assert row["insurance_model_executed"] is True
        assert row["insurance_model_execution_state"] == "EXECUTED_WITH_ANCHOR"


def test_dynamic_holding_valuation_survives_canonical_compaction() -> None:
    production = _production_row(
        code="001316",
        scope="HOLDING",
        action="HOLD_REVIEW",
        stock_name="润贝航科",
        valuation_confidence="LOW",
        neutral_value="49.36957125214809",
        value_low="21.644645478526556",
        value_high="70.29254879749493",
        previous_value_low="20.0",
        previous_neutral_value="49.36957125214809",
        previous_value_high="68.0",
        previous_valuation_available=True,
        valuation_change="STABLE",
        valuation_change_materiality_threshold="0.01",
        price_value_zone="FAIR_VALUE",
        upside_to_value_high="1.364364238059029",
        valuation_range_ready=True,
        valuation_range_source="V311_STRICT_PIT_GENERIC_RANGE",
        valuation_range_method="ROUND6_10Y_EARNING_POWER_REALISTIC_GROWTH_UNCERTAINTY_BAND",
        valuation_range_neutral_roundtrip_verified=True,
        valuation_range_growth_low="0.0",
        valuation_range_growth_neutral="0.20636294218718887",
        valuation_range_growth_high="0.3",
        valuation_range_growth_uncertainty_width="0.20636294218718887",
        dynamic_valuation_primary_reference=True,
        profit_alone_is_sell_reason=False,
        profit_protection_overlay_authority="RISK_CONTEXT_ONLY_NO_FORMAL_ACTION_MUTATION",
        profit_protection_overlay_eligible=False,
        profit_protection_risk_reasons="",
        profit_used_by_formal_decision=False,
        formal_sell_mechanical_valuation_only_forbidden=True,
        formal_sell_requires_explicit_rationale=True,
        valuation_confidence_reason_codes="REALISTIC_GROWTH_UNSTABLE",
    )

    snapshot = build_snapshot(
        discovery_rows=[],
        deep_review_rows=[],
        production_rows=[production],
        source_kind="test",
        source_run_id="dynamic-valuation-1",
        generated_at="2026-09-11T00:00:00+00:00",
    )

    holding = snapshot["production"]["holding_decisions"][0]
    assert holding["value_low"] == "21.644645478526556"
    assert holding["neutral_value"] == "49.36957125214809"
    assert holding["value_high"] == "70.29254879749493"
    assert holding["previous_value_low"] == "20.0"
    assert holding["previous_neutral_value"] == "49.36957125214809"
    assert holding["previous_value_high"] == "68.0"
    assert holding["valuation_change"] == "STABLE"
    assert holding["price_value_zone"] == "FAIR_VALUE"
    assert holding["valuation_range_source"] == "V311_STRICT_PIT_GENERIC_RANGE"
    assert holding["valuation_range_ready"] is True
    assert holding["dynamic_valuation_primary_reference"] is True
    assert holding["profit_alone_is_sell_reason"] is False
    assert holding["profit_protection_overlay_eligible"] is False
    assert holding["profit_used_by_formal_decision"] is False
    assert holding["formal_sell_mechanical_valuation_only_forbidden"] is True
    assert holding["formal_sell_requires_explicit_rationale"] is True
    assert snapshot["architecture_contract"]["dynamic_valuation_evidence_preserved"] is True
