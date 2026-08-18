from datetime import date
from pathlib import Path

import pytest
import yaml

from src.strategies.genge_opportunity_discovery.insurance_embedded_value_inputs import (
    InsuranceEmbeddedValueInputRepository,
    load_insurance_embedded_value_input_repository,
)


def _write(tmp_path: Path, inputs: list[dict]) -> Path:
    path = tmp_path / "insurance.yaml"
    path.write_text(
        yaml.safe_dump({"version": 1, "inputs": inputs}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _input(**overrides):
    payload = {
        "input_id": "601628-2025-annual-ev-nbv",
        "code": "601628",
        "stock_name": "中国人寿",
        "known_at": "2026-03-26",
        "evidence_as_of": "2025-12-31",
        "report_year": 2025,
        "currency": "CNY",
        "unit": "million",
        "embedded_value": 1467876,
        "normalized_annual_nbv": 45752,
        "embedded_value_scope": "listed_company",
        "nbv_scope": "listed_company",
        "confidence": "HIGH",
        "evidence_refs": ["annual-report-2025"],
    }
    payload.update(overrides)
    return payload


def test_checked_in_inputs_are_pit_safe_and_picc_group_scope_is_not_fabricated():
    repository = load_insurance_embedded_value_input_repository()

    life_before = repository.resolve("601628", as_of=date(2026, 3, 25))
    life_after = repository.resolve("601628", as_of=date(2026, 3, 26))
    cpic_before = repository.resolve("601601", as_of=date(2026, 3, 26))
    cpic_after = repository.resolve("601601", as_of=date(2026, 3, 27))
    picc = repository.resolve("601319", as_of=date(2026, 8, 17))

    assert life_before.status == "NOT_YET_KNOWN"
    assert life_after.status == "FOUND"
    assert life_after.execution_eligible is True
    assert life_after.input is not None
    assert life_after.input.embedded_value == 1467876
    assert life_after.input.normalized_annual_nbv == 45752

    assert cpic_before.status == "NOT_YET_KNOWN"
    assert cpic_after.status == "FOUND"
    assert cpic_after.execution_eligible is True
    assert cpic_after.input is not None
    assert cpic_after.input.embedded_value == 613365
    assert cpic_after.input.normalized_annual_nbv == 18609

    assert picc.status == "NOT_FOUND"
    assert picc.execution_eligible is False


def test_low_confidence_input_is_auditable_but_not_execution_eligible(tmp_path):
    repository = load_insurance_embedded_value_input_repository(
        _write(tmp_path, [_input(confidence="LOW")])
    )
    resolution = repository.resolve("601628", as_of=date(2026, 8, 17))

    assert resolution.status == "LOW_CONFIDENCE"
    assert resolution.input is not None
    assert resolution.execution_eligible is False
    payload = resolution.to_dict()
    assert payload["formal_signal_eligible"] is False
    assert payload["automatic_promotion_allowed"] is False
    assert payload["no_auto_trade"] is True


def test_future_evidence_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        [_input(known_at="2026-03-26", evidence_as_of="2026-03-27", report_year=2026)],
    )
    with pytest.raises(ValueError, match="evidence_as_of cannot be after known_at"):
        load_insurance_embedded_value_input_repository(path)


def test_duplicate_code_known_at_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        [_input(input_id="v1"), _input(input_id="v2")],
    )
    with pytest.raises(ValueError, match="duplicate insurance input known_at"):
        load_insurance_embedded_value_input_repository(path)


def test_repository_without_inputs_returns_not_found():
    repository = InsuranceEmbeddedValueInputRepository(())
    resolution = repository.resolve("601628", as_of=date(2026, 8, 17))
    assert resolution.status == "NOT_FOUND"
    assert resolution.input is None
