import json

import pytest

from src.strategies.genge_opportunity_discovery.v31_explicit_deep_review import (
    CONTRACT,
    _machine_checks,
    apply_explicit_reviews,
)


def _evidence(url="https://example.com/official"):
    return [{"source_type": "PRIMARY_COMPANY", "url": url, "published_date": "2026-08-20"}]


def _valuation(**overrides):
    row = {
        "code": "603993",
        "financial_review_status": "OK",
        "financial_disclosure_date": "2026-08-20",
        "cash_conversion_ratio": "0.8853",
        "earnings_quality_score": "77.0",
        "earnings_quality_confidence": "HIGH",
        "normalized_core_operating_profit": "15605833000.0",
        "operating_cash_flow": "16333690735.41",
    }
    row.update(overrides)
    return row


def _config(gates):
    return {
        "contract": CONTRACT,
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "profiles": {
            "603993": {
                "name": "洛阳钼业",
                "research_as_of": "2026-09-07",
                "gates": gates,
            }
        },
    }


def test_verified_explicit_reviews_resolve_only_supported_gates():
    gates = {
        "predictability": {
            "status": "UNKNOWN",
            "confidence": "HIGH",
            "rationale": "Commodity cyclicality remains material.",
            "evidence": _evidence(),
        },
        "long_term_demand": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Long-term primary evidence supports demand.",
            "evidence": _evidence("https://www.iea.org/official"),
        },
        "moat": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Reviewed primary evidence supports asset-scale moat.",
            "evidence": _evidence(),
        },
        "financial_safety": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Reviewed financial evidence passes current checks.",
            "evidence": _evidence(),
            "machine_checks": {
                "financial_review_status": "OK",
                "disclosure_not_after_research_as_of": True,
                "minimum_cash_conversion_ratio": 0.8,
                "minimum_earnings_quality_score": 70.0,
                "required_earnings_quality_confidence": "HIGH",
            },
        },
        "earnings_authenticity": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Normalized profit and operating cash flow are verified.",
            "evidence": _evidence(),
            "machine_checks": {
                "financial_review_status": "OK",
                "disclosure_not_after_research_as_of": True,
                "minimum_cash_conversion_ratio": 0.8,
                "minimum_earnings_quality_score": 70.0,
                "required_earnings_quality_confidence": "HIGH",
                "normalized_core_operating_profit_positive": True,
                "operating_cash_flow_positive": True,
            },
        },
    }
    rows, summary = apply_explicit_reviews([{"code": "603993"}], [_valuation()], _config(gates))
    row = rows[0]
    assert row["v31_predictability_status"] == "UNKNOWN"
    assert row["v31_long_term_demand_status"] == "PASS"
    assert row["v31_moat_status"] == "PASS"
    assert row["v31_financial_safety_status"] == "PASS"
    assert row["v31_earnings_authenticity_status"] == "PASS"
    assert row["v31_hard_gates_passed"] is False
    assert "predictability" in row["v31_hard_gate_unknowns"]
    assert row["v31_buy_ready"] is False
    assert summary["verified_pass_counts"]["long_term_demand"] == 1
    assert summary["formal_trading_authority"] is False
    assert summary["automatic_formal_buy_allowed"] is False
    assert summary["unknown_is_pass"] is False
    assert summary["no_auto_trade"] is True


def test_failed_machine_check_downgrades_requested_pass_to_unknown():
    gates = {
        "earnings_authenticity": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Requires current financial evidence.",
            "evidence": _evidence(),
            "machine_checks": {
                "minimum_cash_conversion_ratio": 0.8,
                "minimum_earnings_quality_score": 70.0,
            },
        }
    }
    rows, _summary = apply_explicit_reviews(
        [{"code": "603993"}],
        [_valuation(cash_conversion_ratio="0.40")],
        _config(gates),
    )
    row = rows[0]
    assert row["v31_earnings_authenticity_status"] == "UNKNOWN"
    provenance = json.loads(row["v31_deep_review_earnings_authenticity_provenance"])
    assert provenance["machine_checks_passed"] is False
    assert "cash_conversion_ratio" in provenance["machine_check_failures"]


def test_low_confidence_or_missing_https_evidence_never_becomes_pass():
    gates = {
        "moat": {
            "status": "PASS",
            "confidence": "MEDIUM",
            "rationale": "Not strong enough.",
            "evidence": _evidence("http://example.com/not-https"),
        }
    }
    rows, _summary = apply_explicit_reviews([{"code": "603993"}], [_valuation()], _config(gates))
    assert rows[0]["v31_moat_status"] == "UNKNOWN"


def test_existing_upstream_explicit_fail_is_never_overwritten_by_profile_pass():
    gates = {
        "moat": {
            "status": "PASS",
            "confidence": "HIGH",
            "rationale": "Profile would otherwise pass.",
            "evidence": _evidence(),
        }
    }
    rows, _summary = apply_explicit_reviews(
        [{"code": "603993", "v31_moat_status": "FAIL"}],
        [_valuation()],
        _config(gates),
    )
    assert rows[0]["v31_moat_status"] == "FAIL"
    assert rows[0]["v31_hard_gates_passed"] is False


def test_unknown_machine_check_key_fails_closed():
    with pytest.raises(ValueError, match="unsupported machine checks"):
        _machine_checks({"pretend_safe": True}, _valuation(), research_as_of=None)


def test_future_disclosure_fails_pit_machine_check():
    ok, failures = _machine_checks(
        {"disclosure_not_after_research_as_of": True},
        _valuation(financial_disclosure_date="2026-09-08"),
        research_as_of=__import__("datetime").date(2026, 9, 7),
    )
    assert ok is False
    assert failures == ["financial_disclosure_date"]
