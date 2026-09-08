from src.strategies.genge_opportunity_discovery.v31_automatic_deep_calculation import calculate_rows


def _candidate(code: str, name: str = "测试") -> dict:
    return {
        "code": code,
        "stock_name": name,
        "industry": "测试行业",
        "v31_predictability_status": "",
        "v31_long_term_demand_status": "",
        "v31_moat_status": "",
        "v31_financial_safety_status": "",
        "v31_earnings_authenticity_status": "",
    }


def _strong_valuation(code: str) -> dict:
    return {
        "code": code,
        "financial_review_status": "OK",
        "cash_conversion_ratio": "1.10",
        "earnings_quality_score": "82",
        "earnings_quality_confidence": "HIGH",
        "normalized_core_operating_profit": "120",
        "operating_cash_flow": "150",
        "financial_disclosure_date": "2026-08-31",
    }


def _explicit_config() -> dict:
    return {
        "contract": "GEN_GE_V31_EXPLICIT_DEEP_REVIEW_V1",
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "profiles": {
            "603993": {
                "research_as_of": "2026-09-07",
                "gates": {
                    "long_term_demand": {
                        "status": "PASS",
                        "confidence": "HIGH",
                        "rationale": "verified structural demand",
                        "evidence": [
                            {
                                "source_type": "INTERNATIONAL_AUTHORITY",
                                "url": "https://example.com/authority",
                                "published_date": "2026-08-01",
                            }
                        ],
                    }
                },
            }
        },
    }


def test_machine_financial_gates_resolve_but_qualitative_gates_fail_closed():
    reviewed, profiles, status = calculate_rows(
        [_candidate("600406")],
        [_strong_valuation("600406")],
        _explicit_config(),
        requested_codes=["600406"],
        source_run_id="123",
        trigger_source="TEST",
    )
    row = reviewed[0]
    assert row["v31_financial_safety_status"] == "PASS"
    assert row["v31_earnings_authenticity_status"] == "PASS"
    assert row["v31_predictability_status"] == "UNKNOWN"
    assert row["v31_long_term_demand_status"] == "UNKNOWN"
    assert row["v31_moat_status"] == "UNKNOWN"
    assert row["v31_hard_gates_passed"] is False
    assert row["v31_auto_deep_calculation_unknown_is_pass"] is False
    assert profiles["unknown_is_pass"] is False
    assert profiles["profiles"]["600406"]["gates"]["financial_safety"]["status"] == "PASS"
    assert status["execution_status"] == "SUCCESS"
    assert status["research_outcome"] == "PARTIAL_GAPS_REMAIN"
    assert status["unresolved_requested_gate_count"] == 3
    assert status["no_auto_trade"] is True


def test_verified_explicit_profile_reverifies_upstream_pass_with_provenance():
    candidate = _candidate("603993", "洛阳钼业")
    candidate["v31_long_term_demand_status"] = "PASS"
    reviewed, profiles, status = calculate_rows(
        [candidate],
        [_strong_valuation("603993")],
        _explicit_config(),
        requested_codes=["603993"],
    )
    row = reviewed[0]
    gate = profiles["profiles"]["603993"]["gates"]["long_term_demand"]
    assert row["v31_long_term_demand_status"] == "PASS"
    assert row["v31_financial_safety_status"] == "PASS"
    assert row["v31_earnings_authenticity_status"] == "PASS"
    assert gate["source"] == "EXPLICIT_VERIFIED"
    assert gate["rationale"] == "verified structural demand"
    assert gate["evidence"]
    assert status["explicit_profile_applied_count"] == 1
    assert status["reverified_upstream_pass_count"] == 1
    assert status["unresolved_requested_gate_count"] == 2
    assert status["automatic_formal_buy_allowed"] is False


def test_profile_unknown_downgrades_upstream_pass_instead_of_preserving_unproven_pass():
    config = _explicit_config()
    config["profiles"]["603993"]["gates"]["long_term_demand"]["status"] = "UNKNOWN"
    candidate = _candidate("603993", "洛阳钼业")
    candidate["v31_long_term_demand_status"] = "PASS"

    reviewed, profiles, status = calculate_rows(
        [candidate],
        [_strong_valuation("603993")],
        config,
        requested_codes=["603993"],
    )

    assert reviewed[0]["v31_long_term_demand_status"] == "UNKNOWN"
    gate = profiles["profiles"]["603993"]["gates"]["long_term_demand"]
    assert gate["status"] == "UNKNOWN"
    assert gate["source"] == "EXPLICIT_VERIFIED"
    assert status["reverified_upstream_pass_count"] == 1
    assert status["unknown_is_pass"] is False


def test_profile_reverification_never_clears_existing_fail():
    candidate = _candidate("603993", "洛阳钼业")
    candidate["v31_long_term_demand_status"] = "FAIL"

    reviewed, _profiles, status = calculate_rows(
        [candidate],
        [_strong_valuation("603993")],
        _explicit_config(),
        requested_codes=["603993"],
    )

    assert reviewed[0]["v31_long_term_demand_status"] == "FAIL"
    assert status["reverified_upstream_pass_count"] == 0
    assert status["unknown_is_pass"] is False


def test_missing_requested_code_is_visible_not_silently_dropped():
    _, _, status = calculate_rows(
        [_candidate("600406")],
        [_strong_valuation("600406")],
        _explicit_config(),
        requested_codes=["600406", "001316"],
    )
    assert status["missing_requested_codes"] == ["001316"]
    assert status["research_outcome"] == "PARTIAL_GAPS_REMAIN"
    assert status["processed_requested_count"] == 1
