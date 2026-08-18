from datetime import date
from pathlib import Path

import pytest
import yaml

from src.strategies.genge_opportunity_discovery.valuation_company_profiles import (
    CompanyValuationProfileRepository,
    load_company_valuation_profile_repository,
)
from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import (
    route_valuation_strategies,
)


def _write_profiles(tmp_path: Path, profiles: list[dict]) -> Path:
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


def _profile(**overrides) -> dict:
    payload = {
        "profile_id": "600000-bank-v1",
        "code": "600000",
        "stock_name": "浦发银行",
        "known_at": "2026-04-30",
        "evidence_as_of": "2026-04-30",
        "review_after": "2027-04-30",
        "confidence": "HIGH",
        "business_tags": ["商业银行"],
        "archetype_hints": ["BANK"],
        "disabled_strategy_ids": ["general_reverse_earnings"],
        "rationale": "Bank balance-sheet economics require the bank valuation family.",
        "evidence_refs": ["annual-report-2025"],
    }
    payload.update(overrides)
    return payload


def test_repository_resolves_only_profiles_known_at_as_of(tmp_path):
    path = _write_profiles(tmp_path, [_profile()])
    repository = load_company_valuation_profile_repository(path)

    before = repository.resolve("600000.SH", as_of=date(2026, 4, 29))
    after = repository.resolve("SH600000", as_of=date(2026, 4, 30))

    assert before.status == "NOT_YET_KNOWN"
    assert before.profile is None
    assert before.routing_eligible is False
    assert after.status == "FOUND"
    assert after.profile is not None
    assert after.profile.profile_id == "600000-bank-v1"
    assert after.routing_eligible is True
    assert after.routing_archetype_hints == ("BANK",)
    assert after.routing_confidence_cap == 1.0


def test_later_profile_version_does_not_leak_into_earlier_as_of(tmp_path):
    old = _profile(
        profile_id="000001-bank-v1",
        code="000001",
        stock_name="平安银行",
        known_at="2026-03-31",
        evidence_as_of="2026-03-31",
        review_after="2027-03-31",
        rationale="Initial reviewed bank profile.",
    )
    new = _profile(
        profile_id="000001-bank-v2",
        code="000001",
        stock_name="平安银行",
        known_at="2026-08-10",
        evidence_as_of="2026-06-30",
        review_after="2027-08-10",
        business_tags=["商业银行", "零售银行"],
        rationale="Later public evidence refined the business tags.",
    )
    repository = load_company_valuation_profile_repository(
        _write_profiles(tmp_path, [new, old])
    )

    april = repository.resolve("000001", as_of=date(2026, 4, 1))
    august = repository.resolve("000001", as_of=date(2026, 8, 11))

    assert april.profile is not None
    assert april.profile.profile_id == "000001-bank-v1"
    assert april.profile.business_tags == ("商业银行",)
    assert august.profile is not None
    assert august.profile.profile_id == "000001-bank-v2"
    assert august.profile.business_tags == ("商业银行", "零售银行")


def test_stale_profile_remains_auditable_but_cannot_route(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profiles(
            tmp_path,
            [_profile(review_after="2026-06-30")],
        )
    )

    resolution = repository.resolve("600000", as_of=date(2026, 7, 1))

    assert resolution.status == "STALE"
    assert resolution.profile is not None
    assert resolution.routing_eligible is False
    assert resolution.routing_business_tags == ()
    assert resolution.routing_archetype_hints == ()
    assert resolution.routing_disabled_strategy_ids == ()
    assert resolution.routing_confidence_cap == 0.0


def test_low_confidence_profile_cannot_route(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profiles(tmp_path, [_profile(confidence="LOW")])
    )

    resolution = repository.resolve("600000", as_of=date(2026, 5, 1))

    assert resolution.status == "LOW_CONFIDENCE"
    assert resolution.profile is not None
    assert resolution.routing_eligible is False
    assert resolution.routing_archetype_hints == ()
    assert resolution.routing_confidence_cap == 0.0


def test_medium_confidence_profile_caps_downstream_routing_confidence(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profiles(tmp_path, [_profile(confidence="MEDIUM")])
    )

    resolution = repository.resolve("600000", as_of=date(2026, 5, 1))
    decision = route_valuation_strategies(
        industry="银行",
        business_tags=resolution.routing_business_tags,
        archetype_hints=resolution.routing_archetype_hints,
    )
    effective_confidence = min(
        decision.routing_confidence,
        resolution.routing_confidence_cap,
    )

    assert resolution.status == "FOUND"
    assert decision.routing_confidence == 1.0
    assert resolution.routing_confidence_cap == 0.8
    assert effective_confidence == 0.8


def test_company_profile_can_drive_strategy_router_without_industry_guessing(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profiles(
            tmp_path,
            [
                _profile(
                    profile_id="000100-panel-v1",
                    code="000100",
                    stock_name="TCL科技",
                    business_tags=["面板", "显示产能周期"],
                    archetype_hints=["CAPACITY_CYCLE"],
                    disabled_strategy_ids=[],
                    rationale="Reviewed display-panel capacity-cycle economics.",
                    evidence_refs=["reviewed-company-evidence-000100"],
                )
            ],
        )
    )
    resolution = repository.resolve("000100", as_of=date(2026, 5, 1))

    decision = route_valuation_strategies(
        industry="电子",
        business_tags=resolution.routing_business_tags,
        archetype_hints=resolution.routing_archetype_hints,
    )

    assert resolution.status == "FOUND"
    assert decision.strategy_ids == (
        "capacity_cycle_normalizer",
        "general_reverse_earnings",
    )
    assert decision.status == "EXPLICIT_ARCHETYPE_ROUTE"
    assert decision.routing_confidence == 1.0


def test_future_evidence_date_is_rejected(tmp_path):
    path = _write_profiles(
        tmp_path,
        [_profile(known_at="2026-04-30", evidence_as_of="2026-05-01")],
    )

    with pytest.raises(ValueError, match="evidence_as_of cannot be after known_at"):
        load_company_valuation_profile_repository(path)


def test_missing_review_after_is_rejected(tmp_path):
    payload = _profile()
    payload.pop("review_after")
    path = _write_profiles(tmp_path, [payload])

    with pytest.raises(ValueError, match="review_after is required"):
        load_company_valuation_profile_repository(path)


def test_unknown_archetype_is_rejected(tmp_path):
    path = _write_profiles(tmp_path, [_profile(archetype_hints=["MAGIC_MODEL"])])

    with pytest.raises(ValueError, match="unknown valuation profile archetype"):
        load_company_valuation_profile_repository(path)


def test_unknown_disabled_strategy_is_rejected(tmp_path):
    path = _write_profiles(
        tmp_path,
        [_profile(disabled_strategy_ids=["not_a_registered_strategy"])],
    )

    with pytest.raises(ValueError, match="unknown disabled valuation strategy ids"):
        load_company_valuation_profile_repository(path)


def test_duplicate_profile_date_for_same_code_is_rejected(tmp_path):
    path = _write_profiles(
        tmp_path,
        [
            _profile(profile_id="600000-v1"),
            _profile(profile_id="600000-v2"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate valuation profile known_at"):
        load_company_valuation_profile_repository(path)


def test_missing_company_profile_is_explicit_not_found():
    repository = CompanyValuationProfileRepository(())

    resolution = repository.resolve("300750", as_of=date(2026, 8, 17))

    assert resolution.status == "NOT_FOUND"
    assert resolution.profile is None
    assert resolution.routing_eligible is False


def test_profile_resolution_metadata_never_promotes_to_trade_signal(tmp_path):
    repository = load_company_valuation_profile_repository(
        _write_profiles(tmp_path, [_profile()])
    )
    payload = repository.resolve("600000", as_of=date(2026, 5, 1)).to_dict()

    assert payload["formal_signal_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["no_auto_trade"] is True


def test_checked_in_profile_registry_contains_pit_safe_new_natural_gas_profile():
    repository = load_company_valuation_profile_repository(
        "config/valuation_company_profiles.yaml"
    )

    assert len(repository.profiles) >= 1
    before = repository.resolve("603393", as_of=date(2026, 7, 27))
    current = repository.resolve("603393", as_of=date(2026, 8, 17))
    assert before.status == "NOT_YET_KNOWN"
    assert current.status == "FOUND"
    assert current.profile is not None
    assert current.profile.profile_id == "603393-resource-cycle-v1"
    assert current.profile.confidence == "HIGH"
    assert current.routing_archetype_hints == ("CAPACITY_CYCLE", "GENERAL_EARNINGS")
    assert current.routing_disabled_strategy_ids == ("yield_asset",)
