from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    close_profiles,
    infer_long_term_demand,
)


def _profiles():
    return {
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "profiles": {
            "001316": {
                "name": "润贝航科",
                "industry": "航空装备",
                "gates": {
                    "predictability": {"status": "UNKNOWN"},
                    "long_term_demand": {"status": "UNKNOWN"},
                    "moat": {"status": "UNKNOWN"},
                    "financial_safety": {"status": "PASS"},
                    "earnings_authenticity": {"status": "PASS"},
                },
            }
        },
    }


def _official(domain, direction):
    return {
        "industry": "航空装备",
        "evidence_status": "VERIFIED",
        "source_type": "OFFICIAL_REPORT",
        "source_domain": domain,
        "publish_date": "2026-09-01",
        "direction": direction,
        "original_url": f"https://{domain}/report",
        "normalized_summary": "verified official numeric context",
    }


def test_long_term_demand_requires_two_independent_official_domains():
    status, _, _ = infer_long_term_demand("航空装备", [_official("stats.gov.cn", "POSITIVE")])
    assert status == "UNKNOWN"
    status, _, evidence = infer_long_term_demand(
        "航空装备",
        [_official("stats.gov.cn", "POSITIVE"), _official("miit.gov.cn", "POSITIVE")],
    )
    assert status == "PASS"
    assert len(evidence) == 2


def test_conflicting_official_evidence_stays_unknown():
    status, rationale, _ = infer_long_term_demand(
        "航空装备",
        [_official("stats.gov.cn", "POSITIVE"), _official("miit.gov.cn", "NEGATIVE")],
    )
    assert status == "UNKNOWN"
    assert "conflicts" in rationale


def test_same_lambda_terminates_evidence_exhausted_without_fake_pass_or_retry():
    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备", "stock_name": "润贝航科"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[],
        evidence_audit=[],
        evidence_summary={"verified_count": 0},
    )
    assert status["execution_status"] == "SUCCESS"
    assert status["research_terminal_state"] == "EVIDENCE_EXHAUSTED"
    assert status["immediate_retry_required"] is False
    assert status["gap_closure_attempt_count"] == 1
    assert status["progressed_gate_count"] == 0
    assert status["unresolved_requested_gate_count"] == 3
    profile = out["profiles"]["001316"]
    assert profile["research_terminal_state"] == "EVIDENCE_EXHAUSTED"
    assert profile["gates"]["predictability"]["status"] == "UNKNOWN"
    assert profile["gates"]["moat"]["status"] == "UNKNOWN"
    assert out["unknown_is_pass"] is False
    assert out["automatic_formal_buy_allowed"] is False
    assert out["no_auto_trade"] is True


def test_verified_corroboration_progresses_gate_but_does_not_invent_buy_authority():
    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备", "stock_name": "润贝航科"}],
        requested_codes=["001316"],
        industry_evidence=[_official("stats.gov.cn", "POSITIVE"), _official("miit.gov.cn", "POSITIVE")],
        company_evidence=[],
        evidence_audit=[],
        evidence_summary={"verified_count": 2},
    )
    gate = out["profiles"]["001316"]["gates"]["long_term_demand"]
    assert gate["status"] == "PASS"
    assert gate["source"] == "AUTOMATIC_OFFICIAL_EVIDENCE_CLOSURE"
    assert status["progressed_gate_count"] == 1
    assert status["research_terminal_state"] == "EVIDENCE_EXHAUSTED"
    assert status["unresolved_requested_gate_count"] == 2
    assert status["automatic_formal_buy_allowed"] is False
    assert status["formal_trading_authority"] is False
    assert status["no_auto_trade"] is True


def test_all_resolved_profiles_finish_complete():
    payload = _profiles()
    gates = payload["profiles"]["001316"]["gates"]
    for gate in gates.values():
        gate["status"] = "PASS"
    _, status = close_profiles(
        payload,
        [{"code": "001316", "industry": "航空装备"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[],
        evidence_audit=[],
        evidence_summary={},
    )
    assert status["research_terminal_state"] == "COMPLETE"
    assert status["complete_requested_count"] == 1
    assert status["evidence_exhausted_requested_count"] == 0
    assert status["unresolved_requested_gate_count"] == 0
