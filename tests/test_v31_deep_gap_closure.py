from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    canonical_industry_name,
    normalize_sse_attachment_url,
    prepare_industry_alias_map,
)
from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    close_profiles,
    infer_long_term_demand,
    infer_material_event_gate_failures,
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


def _material_event(
    event_type,
    *,
    code="001316",
    event_status="ACTIVE",
    severity="HIGH",
    domain="static.cninfo.com.cn",
):
    return {
        "code": code,
        "evidence_status": "VERIFIED",
        "source_type": "EXCHANGE_DISCLOSURE",
        "source_domain": domain,
        "publish_date": "2026-09-01",
        "evidence_kind": "material_event",
        "event_type": event_type,
        "event_status": event_status,
        "event_severity": severity,
        "original_url": f"https://{domain}/event.pdf",
        "normalized_summary": f"verified {event_type} event",
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
    assert status["material_event_failed_gate_count"] == 0
    assert status["material_event_pass_override_count"] == 0
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


def test_active_verified_funds_occupation_overrides_stale_financial_pass():
    event = _material_event("FUNDS_OCCUPATION")
    decisions = infer_material_event_gate_failures("001316", [event])
    assert set(decisions) == {"financial_safety"}

    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备", "stock_name": "润贝航科"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[event],
        evidence_audit=[],
        evidence_summary={"verified_count": 1},
    )
    gate = out["profiles"]["001316"]["gates"]["financial_safety"]
    assert gate["status"] == "FAIL"
    assert gate["confidence"] == "HIGH"
    assert gate["source"] == "AUTOMATIC_VERIFIED_MATERIAL_EVENT_CLOSURE"
    assert status["progressed_gate_count"] == 1
    assert status["material_event_failed_gate_count"] == 1
    assert status["material_event_pass_override_count"] == 1
    assert status["automatic_formal_buy_allowed"] is False
    assert status["formal_trading_authority"] is False
    assert status["no_auto_trade"] is True


def test_accounting_fraud_fails_authenticity_and_predictability():
    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[_material_event("ACCOUNTING_FRAUD")],
        evidence_audit=[],
        evidence_summary={"verified_count": 1},
    )
    gates = out["profiles"]["001316"]["gates"]
    assert gates["earnings_authenticity"]["status"] == "FAIL"
    assert gates["predictability"]["status"] == "FAIL"
    assert status["progressed_gate_count"] == 2
    assert status["material_event_failed_gate_count"] == 2
    assert status["material_event_pass_override_count"] == 1


def test_resolved_or_unofficial_material_event_never_creates_fail():
    resolved = _material_event("FUNDS_OCCUPATION", event_status="RESOLVED")
    unofficial = _material_event("DEBT_DEFAULT", domain="example.com")
    decisions = infer_material_event_gate_failures("001316", [resolved, unofficial])
    assert decisions == {}

    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[resolved, unofficial],
        evidence_audit=[],
        evidence_summary={"verified_count": 2},
    )
    assert out["profiles"]["001316"]["gates"]["financial_safety"]["status"] == "PASS"
    assert out["profiles"]["001316"]["gates"]["predictability"]["status"] == "UNKNOWN"
    assert status["progressed_gate_count"] == 0
    assert status["material_event_failed_gate_count"] == 0


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


def test_sse_and_classified_industry_normalization_are_part_of_gap_closure_contract():
    relative = "/disclosure/listedinfo/announcement/c/new/2026-08-20/603993_example.pdf"
    assert normalize_sse_attachment_url(relative).startswith("https://static.sse.com.cn/disclosure/")
    assert normalize_sse_attachment_url("https://www.sse.com.cn" + relative).startswith(
        "https://static.sse.com.cn/disclosure/"
    )
    raw = "B09有色金属矿采选业"
    assert canonical_industry_name(raw) == "有色金属矿采选业"
    aliases = prepare_industry_alias_map([raw])["industries"][raw]["aliases"]
    assert "有色金属矿采选业" in aliases
    assert "有色金属" in aliases
