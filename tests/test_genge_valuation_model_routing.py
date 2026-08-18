from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import yaml

from src.strategies.genge_opportunity_discovery.valuation_company_profiles import (
    CompanyValuationProfileRepository,
    load_company_valuation_profile_repository,
)
from src.strategies.genge_opportunity_discovery.valuation_model_routing import (
    annotate_valuation_routes,
    write_routing_sidecar,
)


def _row(**overrides):
    payload = {
        "valuation_research_rank": "1",
        "code": "600549",
        "stock_name": "厦门钨业",
        "industry": "稀有金属",
        "valuation_diagnostic_status": "OK",
        "formal_signal_eligible": "False",
        "automatic_promotion_allowed": "False",
        "no_auto_trade": "True",
    }
    payload.update(overrides)
    return payload


def _write_profile_config(tmp_path: Path, profiles: list[dict]) -> Path:
    path = tmp_path / "valuation_company_profiles.yaml"
    path.write_text(
        yaml.safe_dump(
            {"version": 1, "profiles": profiles},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _profile(**overrides):
    payload = {
        "profile_id": "600549-cycle-v1",
        "code": "600549",
        "stock_name": "厦门钨业",
        "known_at": "2026-08-10",
        "evidence_as_of": "2026-06-30",
        "review_after": "2027-02-10",
        "confidence": "MEDIUM",
        "business_tags": ["钨钼", "资源深加工"],
        "archetype_hints": ["CAPACITY_CYCLE"],
        "disabled_strategy_ids": [],
        "rationale": "Reviewed cycle-sensitive tungsten economics.",
        "evidence_refs": ["official-company-report-2026h1"],
    }
    payload.update(overrides)
    return payload


def test_rare_metal_industry_routes_to_cycle_normalization_before_generic():
    rows = annotate_valuation_routes(
        [_row()],
        as_of=date(2026, 8, 17),
        profile_repository=CompanyValuationProfileRepository(()),
    )

    routed = rows[0]
    assert routed["valuation_profile_status"] == "NOT_FOUND"
    assert routed["valuation_strategy_ids"] == (
        "capacity_cycle_normalizer;general_reverse_earnings"
    )
    assert routed["valuation_primary_strategy_id"] == "general_reverse_earnings"
    assert routed["valuation_routing_confidence"] == 0.85
    assert routed["valuation_model_execution_state"] == (
        "NORMALIZATION_REQUIRED_BEFORE_GENERIC_VALUATION"
    )


def test_bank_route_uses_specialized_non_pe_model_family():
    rows = annotate_valuation_routes(
        [
            _row(
                code="600000",
                stock_name="浦发银行",
                industry="银行",
                valuation_diagnostic_status="OK",
            )
        ],
        as_of=date(2026, 8, 17),
        profile_repository=CompanyValuationProfileRepository(()),
    )

    routed = rows[0]
    assert routed["valuation_strategy_ids"] == "bank_residual_income"
    assert routed["valuation_primary_strategy_id"] == "bank_residual_income"
    assert routed["valuation_model_execution_state"] == (
        "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
    )


def test_broad_gas_industry_remains_yield_asset_without_company_profile():
    routed = annotate_valuation_routes(
        [
            _row(
                code="603393",
                stock_name="新天然气",
                industry="燃气",
                valuation_diagnostic_status="OK",
            )
        ],
        as_of=date(2026, 8, 17),
        profile_repository=CompanyValuationProfileRepository(()),
    )[0]

    assert routed["valuation_profile_status"] == "NOT_FOUND"
    assert routed["valuation_primary_strategy_id"] == "yield_asset"
    assert routed["valuation_model_execution_state"] == (
        "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
    )


def test_mixed_gas_resource_profile_overrides_yield_prior_with_cycle_normalization(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profile_config(
            tmp_path,
            [
                _profile(
                    profile_id="603393-resource-cycle-v1",
                    code="603393",
                    stock_name="新天然气",
                    known_at="2026-07-28",
                    evidence_as_of="2026-07-28",
                    review_after="2027-04-30",
                    confidence="HIGH",
                    business_tags=["城市燃气", "煤层气勘探开发", "上游资源开发"],
                    archetype_hints=["CAPACITY_CYCLE", "GENERAL_EARNINGS"],
                    disabled_strategy_ids=["yield_asset"],
                    rationale="Upstream coalbed-methane resource economics make a pure yield-asset route unsafe.",
                    evidence_refs=["2025-annual-report", "2025-report-inquiry-response"],
                )
            ],
        )
    )

    routed = annotate_valuation_routes(
        [
            _row(
                code="603393",
                stock_name="新天然气",
                industry="燃气",
                valuation_diagnostic_status="OK",
            )
        ],
        as_of=date(2026, 8, 17),
        profile_repository=repository,
    )[0]

    assert routed["valuation_profile_status"] == "FOUND"
    assert routed["valuation_profile_used_for_routing"] is True
    assert routed["valuation_disabled_strategy_ids"] == "yield_asset"
    assert routed["valuation_strategy_ids"] == (
        "capacity_cycle_normalizer;general_reverse_earnings"
    )
    assert routed["valuation_primary_strategy_id"] == "general_reverse_earnings"
    assert routed["valuation_model_execution_state"] == (
        "NORMALIZATION_REQUIRED_BEFORE_GENERIC_VALUATION"
    )
    assert routed["formal_signal_eligible"] is False
    assert routed["automatic_promotion_allowed"] is False
    assert routed["no_auto_trade"] is True


def test_checked_in_gas_profiles_split_resource_and_city_gas_economics():
    repository = load_company_valuation_profile_repository(
        "config/valuation_company_profiles.yaml"
    )
    rows = annotate_valuation_routes(
        [
            _row(code="603393", stock_name="新天然气", industry="燃气"),
            _row(code="600903", stock_name="贵州燃气", industry="燃气"),
            _row(code="600681", stock_name="百川能源", industry="燃气"),
        ],
        as_of=date(2026, 8, 17),
        profile_repository=repository,
    )
    by_code = {row["code"]: row for row in rows}

    resource = by_code["603393"]
    assert resource["valuation_profile_status"] == "FOUND"
    assert resource["valuation_profile_used_for_routing"] is True
    assert resource["valuation_disabled_strategy_ids"] == "yield_asset"
    assert resource["valuation_strategy_ids"] == (
        "capacity_cycle_normalizer;general_reverse_earnings"
    )
    assert resource["valuation_primary_strategy_id"] == "general_reverse_earnings"

    for code in ("600903", "600681"):
        city_gas = by_code[code]
        assert city_gas["valuation_profile_status"] == "FOUND"
        assert city_gas["valuation_profile_used_for_routing"] is True
        assert city_gas["valuation_profile_archetype_hints"] == "YIELD_ASSET"
        assert city_gas["valuation_disabled_strategy_ids"] == ""
        assert city_gas["valuation_strategy_ids"] == "yield_asset"
        assert city_gas["valuation_primary_strategy_id"] == "yield_asset"
        assert city_gas["valuation_model_execution_state"] == (
            "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
        )
        assert city_gas["formal_signal_eligible"] is False
        assert city_gas["automatic_promotion_allowed"] is False
        assert city_gas["no_auto_trade"] is True


def test_profile_driven_route_is_capped_by_profile_confidence(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profile_config(tmp_path, [_profile()])
    )

    rows = annotate_valuation_routes(
        [_row(industry="其他")],
        as_of=date(2026, 8, 17),
        profile_repository=repository,
    )

    routed = rows[0]
    assert routed["valuation_profile_status"] == "FOUND"
    assert routed["valuation_profile_used_for_routing"] is True
    assert routed["valuation_profile_archetype_hints"] == "CAPACITY_CYCLE"
    assert routed["valuation_routing_confidence"] == 0.8
    assert "point_in_time_company_profile_applied" in routed[
        "valuation_route_reasons"
    ]


def test_stale_profile_cannot_force_specialized_route(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profile_config(
            tmp_path,
            [_profile(review_after="2026-08-16")],
        )
    )

    rows = annotate_valuation_routes(
        [_row(industry="其他")],
        as_of=date(2026, 8, 17),
        profile_repository=repository,
    )

    routed = rows[0]
    assert routed["valuation_profile_status"] == "STALE"
    assert routed["valuation_profile_used_for_routing"] is False
    assert routed["valuation_strategy_ids"] == "general_reverse_earnings"
    assert routed["valuation_routing_confidence"] == 0.5
    assert "company_profile_not_used:stale" in routed["valuation_route_reasons"]


def test_profile_can_fail_closed_by_disabling_all_selected_valuation_models(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profile_config(
            tmp_path,
            [
                _profile(
                    profile_id="600000-bank-v1",
                    code="600000",
                    stock_name="浦发银行",
                    confidence="HIGH",
                    business_tags=["商业银行"],
                    archetype_hints=["BANK"],
                    disabled_strategy_ids=["bank_residual_income"],
                    rationale="Temporary profile block pending model review.",
                )
            ],
        )
    )

    rows = annotate_valuation_routes(
        [_row(code="600000", stock_name="浦发银行", industry="其他")],
        as_of=date(2026, 8, 17),
        profile_repository=repository,
    )

    routed = rows[0]
    assert routed["valuation_route_status"] == (
        "PROFILE_DISABLED_ALL_VALUATION_STRATEGIES"
    )
    assert routed["valuation_primary_strategy_id"] == ""
    assert routed["valuation_model_execution_state"] == "ROUTING_BLOCKED"
    assert routed["valuation_routing_confidence"] == 0.0


def test_write_routing_sidecar_preserves_ranking_and_research_only_contract(tmp_path):
    report_dir = tmp_path / "20260817"
    report_dir.mkdir()
    source = _row()
    fields = list(source)
    with (report_dir / "valuation_research_queue.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(source)
    (report_dir / "valuation_research_summary.json").write_text(
        json.dumps({"as_of_date": "2026-08-17"}),
        encoding="utf-8",
    )
    profile_config = _write_profile_config(tmp_path, [])

    rows = write_routing_sidecar(
        report_dir,
        profile_config=profile_config,
    )

    assert len(rows) == 1
    assert rows[0]["valuation_research_rank"] == "1"
    assert rows[0]["formal_signal_eligible"] is False
    assert rows[0]["automatic_promotion_allowed"] is False
    assert rows[0]["no_auto_trade"] is True
    assert (report_dir / "valuation_research_routed.csv").exists()
    assert (report_dir / "valuation_research_routed.md").exists()
    summary = json.loads(
        (report_dir / "valuation_routing_summary.json").read_text(encoding="utf-8")
    )
    assert summary["routed_count"] == 1
    assert summary["ranking_changed"] is False
    assert summary["formal_signal_eligible"] is False
    assert summary["automatic_promotion_allowed"] is False
    assert summary["no_auto_trade"] is True
