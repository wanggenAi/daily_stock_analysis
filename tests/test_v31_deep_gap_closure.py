import json
from datetime import date

from src.strategies.genge_opportunity_discovery.evidence_collectors import (
    canonical_industry_name,
    normalize_sse_attachment_url,
    prepare_industry_alias_map,
)
from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    _load_historical_verified_material_events,
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
    title=None,
):
    titles = {
        "ACCOUNTING_FRAUD": "关于公司财务造假事项的公告",
        "NON_STANDARD_AUDIT": "董事会关于年度审计报告非标准审计意见涉及事项的专项说明",
        "DEBT_DEFAULT": "关于部分债务到期未能清偿的进展公告",
        "BANKRUPTCY_RESTRUCTURING": "关于子公司破产清算进展情况的公告",
        "DELISTING_RISK": "关于公司股票可能被终止上市的风险提示公告",
        "FUNDS_OCCUPATION": "关于控股股东非经营性资金占用事项整改进展的公告",
        "ILLEGAL_GUARANTEE": "关于违规担保事项进展的公告",
    }
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
        "title": title or titles[event_type],
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


def test_missing_profile_is_handoff_incomplete_not_evidence_exhausted():
    _, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备", "stock_name": "润贝航科"}],
        requested_codes=["001316", "600406"],
        industry_evidence=[],
        company_evidence=[],
        evidence_audit=[],
        evidence_summary={"verified_count": 0},
    )

    assert status["execution_status"] == "SUCCESS"
    assert status["research_terminal_state"] == "HANDOFF_INCOMPLETE"
    assert status["requested_count"] == 2
    assert status["profile_count"] == 1
    assert status["requested_profile_count"] == 1
    assert status["processed_requested_count"] == 1
    assert status["complete_requested_count"] == 0
    assert status["partial_requested_count"] == 1
    assert status["evidence_exhausted_requested_count"] == 1
    assert status["handoff_incomplete_requested_count"] == 1
    assert status["missing_requested_codes"] == ["600406"]
    assert status["workset_coverage_known"] is True
    assert status["workset_coverage_complete"] is False
    assert status["unresolved_requested_gate_count"] == 3
    assert status["unresolved_reasons"]["600406"] == {
        "profile": "REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE"
    }
    assert status["immediate_retry_required"] is False


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


def test_historical_verified_material_event_survives_current_refetch_failure():
    historical = _material_event("BANKRUPTCY_RESTRUCTURING")

    out, status = close_profiles(
        _profiles(),
        [{"code": "001316", "industry": "航空装备", "stock_name": "润贝航科"}],
        requested_codes=["001316"],
        industry_evidence=[],
        company_evidence=[],
        evidence_audit=[],
        evidence_summary={"verified_count": 0},
        historical_material_event_evidence=[historical],
    )

    gates = out["profiles"]["001316"]["gates"]
    assert gates["predictability"]["status"] == "FAIL"
    assert gates["financial_safety"]["status"] == "FAIL"
    assert gates["predictability"]["source"] == "AUTOMATIC_VERIFIED_MATERIAL_EVENT_CLOSURE"
    assert gates["financial_safety"]["source"] == "AUTOMATIC_VERIFIED_MATERIAL_EVENT_CLOSURE"
    assert gates["predictability"]["evidence_persistence"] == "HISTORICAL_VERIFIED_ACTIVE_HIGH"
    assert gates["financial_safety"]["evidence_persistence"] == "HISTORICAL_VERIFIED_ACTIVE_HIGH"
    assert status["material_event_failed_gate_count"] == 2
    assert status["historical_material_event_evidence_count"] == 1
    assert status["historical_material_event_failed_gate_count"] == 2
    assert status["material_event_pass_override_count"] == 1
    assert status["automatic_formal_buy_allowed"] is False
    assert status["unknown_is_pass"] is False
    assert status["no_auto_trade"] is True


def test_historical_material_event_loader_reuses_only_strict_fail_eligible_rows(tmp_path):
    valid = _material_event("DEBT_DEFAULT")
    resolved = _material_event("FUNDS_OCCUPATION", event_status="RESOLVED")
    unofficial = _material_event("BANKRUPTCY_RESTRUCTURING", domain="example.com")
    medium = _material_event("ILLEGAL_GUARANTEE", severity="MEDIUM")
    payload = {
        "contract": "GEN_GE_V31_DEEP_GAP_CLOSURE_V1",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "company_evidence": [valid, resolved, unofficial, medium],
    }
    history = tmp_path / "history"
    history.mkdir()
    (history / "123.json").write_text(
        json.dumps({
            "material_event_failed_gate_count": 2,
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
        }),
        encoding="utf-8",
    )
    (history / "123.evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = _load_historical_verified_material_events(
        history,
        ["001316"],
        as_of=date(2026, 9, 21),
    )

    assert len(rows) == 1
    assert rows[0]["event_type"] == "DEBT_DEFAULT"
    assert rows[0]["evidence_status"] == "VERIFIED"
    assert rows[0]["event_status"] == "ACTIVE"
    assert rows[0]["event_severity"] == "HIGH"


def test_historical_loader_revalidates_old_active_label_with_current_title_semantics(tmp_path):
    stale = _material_event(
        "FUNDS_OCCUPATION",
        title="关于公司自查发现控股股东及其附属企业资金占用并已解决等情况的公告",
    )
    history = tmp_path / "history"
    history.mkdir()
    (history / "123.json").write_text(
        json.dumps({"material_event_failed_gate_count": 1}),
        encoding="utf-8",
    )
    (history / "123.evidence.json").write_text(
        json.dumps({
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
            "company_evidence": [stale],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = _load_historical_verified_material_events(
        history,
        ["001316"],
        as_of=date(2026, 9, 21),
    )

    assert rows == []


def test_newest_complete_risk_ledger_blocks_resurrection_from_older_runs(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    old = _material_event("DEBT_DEFAULT")
    (history / "100.json").write_text(
        json.dumps({"material_event_failed_gate_count": 2}),
        encoding="utf-8",
    )
    (history / "100.evidence.json").write_text(
        json.dumps({
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
            "company_evidence": [old],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (history / "200.json").write_text(
        json.dumps({
            "material_event_risk_ledger_complete": True,
            "material_event_risk_ledger_count": 0,
        }),
        encoding="utf-8",
    )
    (history / "200.evidence.json").write_text(
        json.dumps({
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "unknown_is_pass": False,
            "no_auto_trade": True,
            "material_event_risk_ledger": [],
        }),
        encoding="utf-8",
    )

    rows = _load_historical_verified_material_events(
        history,
        ["001316"],
        as_of=date(2026, 9, 21),
    )

    assert rows == []


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
