from src.strategies.genge_opportunity_discovery.v31_terminal_research_decision import build_terminal_decisions


def _profile(gates):
    return {
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
        "profiles": {"000001": {"name": "样本", "industry": "C制造业", "gates": {k: {"status": v} for k, v in gates.items()}}},
    }


def _evidence():
    return {"requested_codes": ["000001"]}


def _valuation(pe="8", median="12", quality="90", confidence="HIGH", status="OK"):
    return [{
        "code": "000001",
        "stock_name": "样本",
        "industry": "C制造业",
        "quant_score": "80",
        "quant_status": "PRIORITY_RESEARCH",
        "current_pe": pe,
        "historical_median_pe_reference": median,
        "earnings_quality_score": quality,
        "earnings_quality_confidence": confidence,
        "financial_review_status": status,
        "expectation_state": "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE",
    }]


def _all(status):
    return {k: status for k in ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")}


def test_unknown_after_bounded_recovery_converges_to_reject_not_fake_pass():
    gates = _all("PASS")
    gates["moat"] = "UNKNOWN"
    out = build_terminal_decisions(profiles_payload=_profile(gates), evidence_payload=_evidence(), valuation_rows=_valuation())
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "REJECT"
    assert row["research_reason"] == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
    assert row["hard_gate_unknowns"] == ["moat"]
    assert row["reopen_on_new_evidence"] is True
    assert out["all_requested_terminal"] is True
    assert out["unknown_is_pass"] is False
    assert out["automatic_formal_buy_allowed"] is False
    assert out["formal_trading_authority"] is False
    assert out["no_auto_trade"] is True


def test_hard_gate_failure_converges_to_reject():
    gates = _all("PASS")
    gates["financial_safety"] = "FAIL"
    out = build_terminal_decisions(profiles_payload=_profile(gates), evidence_payload=_evidence(), valuation_rows=_valuation())
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "REJECT"
    assert row["research_reason"] == "HARD_GATE_FAIL"
    assert row["hard_gate_failures"] == ["financial_safety"]


def test_all_pass_plus_material_pe_discount_can_create_research_buy_only():
    out = build_terminal_decisions(profiles_payload=_profile(_all("PASS")), evidence_payload=_evidence(), valuation_rows=_valuation(pe="8", median="12"))
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "BUY"
    assert row["research_authority"] == "RESEARCH_ONLY"
    assert row["formal_buy_authorized"] is False
    assert out["automatic_formal_buy_allowed"] is False
    assert out["formal_trading_authority"] is False


def test_all_pass_but_price_not_discounted_converges_to_wait_price():
    out = build_terminal_decisions(profiles_payload=_profile(_all("PASS")), evidence_payload=_evidence(), valuation_rows=_valuation(pe="11", median="12"))
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "WAIT_PRICE"
    assert row["formal_buy_authorized"] is False


def test_evidence_blocked_but_attractive_screen_is_prioritized_without_buying():
    gates = _all("PASS")
    gates["predictability"] = "UNKNOWN"
    out = build_terminal_decisions(profiles_payload=_profile(gates), evidence_payload=_evidence(), valuation_rows=_valuation(pe="8", median="12"))
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "REJECT"
    assert row["screening_attractiveness"] == "HIGH"
    assert out["urgent_research_queue"][0]["code"] == "000001"


def test_specialized_industry_never_uses_generic_pe_to_create_buy():
    valuation = _valuation(pe="5", median="10")
    valuation[0]["industry"] = "J68保险业"
    out = build_terminal_decisions(profiles_payload=_profile(_all("PASS")), evidence_payload=_evidence(), valuation_rows=valuation)
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "REJECT"
    assert row["research_reason"] == "SPECIALIZED_VALUATION_REQUIRED"
    assert row["formal_buy_authorized"] is False
