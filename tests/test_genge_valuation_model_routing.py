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
