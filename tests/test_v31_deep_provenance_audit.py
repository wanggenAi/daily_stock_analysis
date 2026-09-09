import pytest
from pathlib import Path

from src.strategies.genge_opportunity_discovery.v31_deep_provenance_audit import (
    audit_profiles,
    augment_status,
)


def _gate(status, source="AUTOMATIC_MACHINE", evidence=True):
    return {
        "status": status,
        "source": source,
        "evidence": [{"source_type": "TEST", "reference": "fixture"}] if evidence else [],
    }


def _profiles():
    return {
        "reverified_upstream_pass_count": 4,
        "unverified_pass_downgraded_count": 2,
        "verified_pass_gate_count": 2,
        "unverified_pass_gate_count": 0,
        "profiles": {
            "001316": {
                "gates": {
                    "predictability": _gate("UNKNOWN", "AUTOMATIC_ATTEMPT", False),
                    "long_term_demand": _gate("UNKNOWN", "AUTOMATIC_ATTEMPT", False),
                    "moat": _gate("UNKNOWN", "AUTOMATIC_ATTEMPT", False),
                    "financial_safety": _gate("PASS"),
                    "earnings_authenticity": _gate("PASS"),
                }
            },
            "603993": {
                "gates": {
                    "predictability": _gate("UNKNOWN", "AUTOMATIC_ATTEMPT", False),
                    "long_term_demand": _gate("PASS", "EXPLICIT_VERIFIED", True),
                    "moat": _gate("PASS", "EXPLICIT_VERIFIED", True),
                    "financial_safety": _gate("UNKNOWN", "AUTOMATIC_MACHINE", True),
                    "earnings_authenticity": _gate("FAIL", "AUTOMATIC_MACHINE", True),
                }
            },
        },
    }


def _status():
    return {
        "lambda_run_id": "123",
        "execution_status": "SUCCESS",
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }


def test_audit_counts_all_profiles_and_requires_evidence_for_every_pass():
    audit = audit_profiles(_profiles())
    assert audit["profile_count"] == 2
    assert audit["hard_gate_count"] == 10
    assert audit["pass_gate_count"] == 4
    assert audit["unknown_gate_count"] == 5
    assert audit["fail_gate_count"] == 1
    assert audit["verified_pass_gate_count"] == 4
    assert audit["unverified_pass_gate_count"] == 0
    assert audit["all_pass_gates_have_verified_evidence"] is True
    assert audit["initial_reverified_upstream_pass_count"] == 4
    assert audit["initial_unverified_pass_downgraded_count"] == 2


def test_audit_records_runtime_lineage():
    audit = audit_profiles(
        _profiles(),
        audit_run_id="456",
        audit_workflow="GenGe V3.1 Deep Provenance Audit",
        audit_run_attempt="2",
        audit_event="workflow_run",
    )
    assert audit["audit_run_id"] == "456"
    assert audit["audit_workflow"] == "GenGe V3.1 Deep Provenance Audit"
    assert audit["audit_run_attempt"] == "2"
    assert audit["audit_event"] == "workflow_run"


def test_naked_pass_is_detected_even_when_other_gates_are_safe():
    payload = _profiles()
    payload["profiles"]["001316"]["gates"]["predictability"] = _gate(
        "PASS", "AUTOMATIC_ATTEMPT", False
    )
    audit = audit_profiles(payload)
    assert audit["pass_gate_count"] == 5
    assert audit["verified_pass_gate_count"] == 4
    assert audit["unverified_pass_gate_count"] == 1
    assert audit["all_pass_gates_have_verified_evidence"] is False
    assert audit["unverified_passes"] == [
        {
            "code": "001316",
            "gate": "predictability",
            "source": "AUTOMATIC_ATTEMPT",
            "evidence_count": 0,
        }
    ]


def test_pass_with_evidence_but_unresolved_source_is_not_verified():
    payload = _profiles()
    payload["profiles"]["603993"]["gates"]["moat"] = _gate(
        "PASS", "UNRESOLVED", True
    )
    audit = audit_profiles(payload)
    assert audit["unverified_pass_gate_count"] == 1
    assert audit["all_pass_gates_have_verified_evidence"] is False


def test_augment_status_embeds_terminal_provenance_contract_and_lineage():
    audit = audit_profiles(
        _profiles(),
        audit_run_id="456",
        audit_workflow="GenGe V3.1 Deep Provenance Audit",
        audit_run_attempt="2",
        audit_event="workflow_run",
    )
    result = augment_status(_status(), audit, expected_lambda_run_id="123")
    assert result["provenance_audit_complete"] is True
    assert result["provenance_audit_contract"] == "GEN_GE_V31_DEEP_PROVENANCE_AUDIT_V1"
    assert result["provenance_audit_run_id"] == "456"
    assert result["provenance_audit_workflow"] == "GenGe V3.1 Deep Provenance Audit"
    assert result["provenance_audit_run_attempt"] == "2"
    assert result["provenance_audit_event"] == "workflow_run"
    assert result["hard_gate_count"] == 10
    assert result["verified_pass_gate_count"] == 4
    assert result["unverified_pass_gate_count"] == 0
    assert result["all_pass_gates_have_verified_evidence"] is True
    assert result["unknown_is_pass"] is False
    assert result["automatic_formal_buy_allowed"] is False
    assert result["formal_trading_authority"] is False
    assert result["no_auto_trade"] is True


def test_augment_status_rejects_wrong_lambda_or_unverified_pass():
    good = audit_profiles(_profiles())
    with pytest.raises(ValueError, match="lambda_run_id mismatch"):
        augment_status(_status(), good, expected_lambda_run_id="999")

    payload = _profiles()
    payload["profiles"]["001316"]["gates"]["predictability"] = _gate(
        "PASS", "AUTOMATIC_ATTEMPT", False
    )
    bad = audit_profiles(payload)
    with pytest.raises(ValueError, match="unverified PASS"):
        augment_status(_status(), bad, expected_lambda_run_id="123")


def test_augment_status_rejects_any_authority_weakening():
    audit = audit_profiles(_profiles())
    unsafe = _status()
    unsafe["unknown_is_pass"] = True
    with pytest.raises(ValueError, match="UNKNOWN != PASS"):
        augment_status(unsafe, audit, expected_lambda_run_id="123")


def test_provenance_self_verification_uses_native_push_then_workflow_run():
    audit_workflow = Path(
        ".github/workflows/genge-v31-deep-provenance-audit.yml"
    ).read_text(encoding="utf-8")
    lambda_workflow = Path(
        ".github/workflows/genge-v31-deep-calculation-lambda.yml"
    ).read_text(encoding="utf-8")

    for path in (
        ".github/workflows/genge-v31-deep-provenance-audit.yml",
        "src/strategies/genge_opportunity_discovery/v31_deep_provenance_audit.py",
        "tests/test_v31_deep_provenance_audit.py",
    ):
        assert f'- "{path}"' in lambda_workflow

    assert "Synchronize provenance self-verification push" in lambda_workflow
    assert "PROVENANCE_AUDIT_PUSH_REFRESH" in lambda_workflow
    assert "GenGe V3.1 Deep Provenance Audit" in lambda_workflow
    assert "gh workflow run genge-v31-deep-calculation-lambda.yml" not in audit_workflow
