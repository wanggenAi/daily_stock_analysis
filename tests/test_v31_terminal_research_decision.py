from pathlib import Path

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
        "cash_conversion_ratio": "0.90",
        "normalized_core_operating_profit": "100",
        "operating_cash_flow": "90",
        "financial_disclosure_date": "2026-08-30",
        "expectation_state": "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE",
    }]


def _all(status):
    return {k: status for k in ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")}


def test_unknown_after_bounded_recovery_converges_to_research_gap_not_fake_pass():
    gates = _all("PASS")
    gates["moat"] = "UNKNOWN"
    out = build_terminal_decisions(profiles_payload=_profile(gates), evidence_payload=_evidence(), valuation_rows=_valuation())
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "RESEARCH_GAP"
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
    assert row["research_decision"] == "RESEARCH_GAP"
    assert row["screening_attractiveness"] == "HIGH"
    assert row["urgent_research"] is True
    assert "QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED" in row["urgent_research_reasons"]
    assert out["urgent_research_queue"][0]["code"] == "000001"



def test_terminal_snapshot_explains_exact_machine_financial_blocker_without_changing_gate():
    gates = _all("PASS")
    gates["financial_safety"] = "UNKNOWN"
    valuation = _valuation(quality="69")
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=valuation,
    )
    row = out["terminal_rows"][0]
    diagnostics = row["valuation"]["financial_gate_diagnostics"]

    assert row["research_decision"] == "RESEARCH_GAP"
    assert diagnostics["earnings_quality_score"] == 69.0
    assert diagnostics["earnings_quality_pass_threshold"] == 70.0
    assert diagnostics["cash_conversion_ratio"] == 0.90
    assert diagnostics["cash_conversion_pass_threshold"] == 0.80
    assert diagnostics["blockers"] == [
        "EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD"
    ]
    assert diagnostics["machine_financial_pass_ready"] is False


def test_terminal_snapshot_reports_missing_financial_inputs_fail_closed():
    gates = _all("PASS")
    gates["earnings_authenticity"] = "UNKNOWN"
    valuation = _valuation()
    valuation[0].pop("cash_conversion_ratio")
    valuation[0].pop("operating_cash_flow")
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=valuation,
    )
    diagnostics = out["terminal_rows"][0]["valuation"]["financial_gate_diagnostics"]

    assert "CASH_CONVERSION_RATIO_MISSING" in diagnostics["blockers"]
    assert "OPERATING_CASH_FLOW_MISSING" in diagnostics["blockers"]
    assert diagnostics["machine_financial_pass_ready"] is False

def test_specialized_industry_never_uses_generic_pe_to_create_buy():
    valuation = _valuation(pe="5", median="10")
    valuation[0]["industry"] = "J68保险业"
    out = build_terminal_decisions(profiles_payload=_profile(_all("PASS")), evidence_payload=_evidence(), valuation_rows=valuation)
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "RESEARCH_GAP"
    assert row["research_reason"] == "SPECIALIZED_VALUATION_REQUIRED"
    assert row["formal_buy_authorized"] is False


def test_p0_evidence_blocked_is_urgent_even_for_specialized_industry_without_fake_buy():
    gates = _all("PASS")
    gates["predictability"] = "UNKNOWN"
    valuation = _valuation(pe="5", median="10")
    valuation[0]["industry"] = "J68保险业"
    priority = {"queue": [{"code": "000001", "priority": "P0", "name": "样本", "industry": "J68保险业"}]}
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=valuation,
        priority_payload=priority,
    )
    row = out["terminal_rows"][0]
    assert row["research_decision"] == "RESEARCH_GAP"
    assert row["research_reason"] == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY"
    assert row["screening_attractiveness"] == "NORMAL"
    assert row["urgent_research"] is True
    assert row["urgent_research_reasons"] == ["P0_EVIDENCE_BLOCKED"]
    assert row["formal_buy_authorized"] is False
    assert out["urgent_research_queue"][0]["code"] == "000001"


def test_urgent_queue_does_not_drop_qualified_names_after_first_ten():
    codes = [f"{i:06d}" for i in range(1, 12)]
    gates = _all("PASS")
    gates["moat"] = "UNKNOWN"
    profiles = {
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
        "profiles": {
            code: {"name": f"样本{code}", "industry": "C制造业", "gates": {k: {"status": v} for k, v in gates.items()}}
            for code in codes
        },
    }
    valuations = [
        {
            "code": code,
            "stock_name": f"样本{code}",
            "industry": "C制造业",
            "quant_score": "80",
            "quant_status": "PRIORITY_RESEARCH",
            "current_pe": "8",
            "historical_median_pe_reference": "12",
            "earnings_quality_score": "90",
            "earnings_quality_confidence": "HIGH",
            "financial_review_status": "OK",
            "expectation_state": "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE",
        }
        for code in codes
    ]
    out = build_terminal_decisions(
        profiles_payload=profiles,
        evidence_payload={"requested_codes": codes},
        valuation_rows=valuations,
    )
    assert len(out["urgent_research_queue"]) == 11
    assert {row["code"] for row in out["urgent_research_queue"]} == set(codes)



def test_noncritical_unknown_can_create_bounded_probe_without_fake_pass():
    gates = _all("PASS")
    gates["moat"] = "UNKNOWN"
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=_valuation(pe="8", median="12"),
    )
    row = out["terminal_rows"][0]
    capital = row["capital_allocation"]

    assert row["research_decision"] == "RESEARCH_GAP"
    assert row["hard_gate_unknowns"] == ["moat"]
    assert capital["action"] == "PROBE"
    assert capital["authority"] == "ADVISORY_ONLY"
    assert capital["critical_capital_gates_pass"] is True
    assert 0.5 <= capital["suggested_max_portfolio_pct"] <= 1.5
    assert capital["automatic_execution_allowed"] is False
    assert capital["formal_buy_authorized"] is False
    assert capital["no_auto_trade"] is True
    assert out["unknown_is_pass"] is False
    assert out["capital_action_counts"]["PROBE"] == 1
    assert out["capital_probe_queue"][0]["code"] == "000001"


def test_unknown_critical_capital_gate_blocks_probe_even_when_valuation_is_cheap():
    gates = _all("PASS")
    gates["financial_safety"] = "UNKNOWN"
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=_valuation(pe="6", median="12"),
    )
    row = out["terminal_rows"][0]
    capital = row["capital_allocation"]

    assert row["research_decision"] == "RESEARCH_GAP"
    assert capital["action"] == "BLOCK"
    assert capital["reason"] == "CRITICAL_CAPITAL_GATES_NOT_PROVEN"
    assert capital["suggested_max_portfolio_pct"] == 0.0


def test_all_pass_research_buy_maps_to_build_advisory_without_formal_authority():
    out = build_terminal_decisions(
        profiles_payload=_profile(_all("PASS")),
        evidence_payload=_evidence(),
        valuation_rows=_valuation(pe="8", median="12"),
    )
    row = out["terminal_rows"][0]
    capital = row["capital_allocation"]

    assert row["research_decision"] == "BUY"
    assert row["formal_buy_authorized"] is False
    assert capital["action"] == "BUILD"
    assert 1.0 <= capital["suggested_max_portfolio_pct"] <= 3.0
    assert out["capital_action_counts"]["BUILD"] == 1
    assert out["capital_advisory_authority"] == "ADVISORY_ONLY"
    assert out["capital_advisory_automatic_execution_allowed"] is False


def test_three_noncritical_unknowns_remain_watch_even_with_discount():
    gates = _all("PASS")
    gates["predictability"] = "UNKNOWN"
    gates["long_term_demand"] = "UNKNOWN"
    gates["moat"] = "UNKNOWN"
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=_valuation(pe="7", median="12"),
    )
    capital = out["terminal_rows"][0]["capital_allocation"]

    assert capital["action"] == "WATCH"
    assert capital["suggested_max_portfolio_pct"] == 0.0



def test_growth_expectation_blocks_probe_until_price_compensates():
    gates = _all("PASS")
    gates["moat"] = "UNKNOWN"
    valuation = _valuation(pe="8", median="12")
    valuation[0]["expectation_state"] = "EARNINGS_GROWTH_REQUIRED"
    out = build_terminal_decisions(
        profiles_payload=_profile(gates),
        evidence_payload=_evidence(),
        valuation_rows=valuation,
    )
    capital = out["terminal_rows"][0]["capital_allocation"]

    assert capital["action"] == "WATCH"
    assert capital["reason"] == "EXPECTATION_REQUIRES_GROWTH"
    assert capital["suggested_max_portfolio_pct"] == 0.0

def test_specialized_industry_stays_watch_without_specialized_valuation_model():
    valuation = _valuation(pe="5", median="10")
    valuation[0]["industry"] = "J68保险业"
    out = build_terminal_decisions(
        profiles_payload=_profile(_all("PASS")),
        evidence_payload=_evidence(),
        valuation_rows=valuation,
    )
    row = out["terminal_rows"][0]

    assert row["research_decision"] == "RESEARCH_GAP"
    assert row["capital_allocation"]["action"] == "WATCH"
    assert row["capital_allocation"]["reason"] == "SPECIALIZED_VALUATION_REQUIRED"
    assert row["capital_allocation"]["suggested_max_portfolio_pct"] == 0.0

def test_terminal_workflow_refreshes_investor_overlay_only_after_persistence() -> None:
    workflow = Path(".github/workflows/genge-v31-terminal-research-decision.yml").read_text(encoding="utf-8")

    persist_at = workflow.index("- name: Persist terminal research decisions with optimistic replay")
    refresh_at = workflow.index("- name: Refresh investor terminal overlay after terminal convergence")
    assert persist_at < refresh_at
    assert "gh workflow run genge-investor-terminal-research-overlay.yml" in workflow[refresh_at:]
    assert "gh workflow run genge-three-pillar-decision-center.yml" not in workflow[refresh_at:]


def test_terminal_production_has_actions_write_for_explicit_dispatch() -> None:
    workflow = Path(".github/workflows/genge-v31-terminal-research-decision.yml").read_text(encoding="utf-8")
    production = workflow.split("  production:", 1)[1]
    assert "permissions:\n      actions: write\n      contents: write" in production
