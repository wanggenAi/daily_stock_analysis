from src.strategies.genge_opportunity_discovery.v31_terminal_research_decision import build_terminal_decisions


def test_public_material_recovery_prevents_false_unknown_reject():
    profiles = {
        "unknown_is_pass": False,
        "automatic_formal_buy_allowed": False,
        "no_auto_trade": True,
        "profiles": {
            "603055": {
                "name": "台华新材",
                "industry": "C17纺织业",
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
    evidence = {
        "requested_codes": ["603055"],
        "public_material_gate_recovery": {
            "603055": {
                "predictability": {"status": "PASS", "sources": ["annual_report", "semiannual_report"]},
                "long_term_demand": {"status": "PASS", "sources": ["annual_report", "earnings_briefing"]},
                "moat": {"status": "PASS", "sources": ["annual_report", "company_announcement"]},
            }
        },
    }
    valuation = [{
        "code": "603055",
        "stock_name": "台华新材",
        "industry": "C17纺织业",
        "current_pe": "16.01",
        "historical_median_pe_reference": "26.73",
        "financial_review_status": "OK",
        "earnings_quality_confidence": "HIGH",
        "earnings_quality_score": "90",
        "expectation_state": "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE",
        "required_profit_growth_pct": "-40.1",
        "quant_score": "45.6517",
        "quant_status": "SECONDARY_RESEARCH",
    }]
    out = build_terminal_decisions(
        profiles_payload=profiles,
        evidence_payload=evidence,
        valuation_rows=valuation,
        priority_payload={"queue": [{"code": "603055", "priority": "P0"}]},
        deep_status={},
    )
    row = out["terminal_rows"][0]
    assert row["hard_gate_unknowns"] == []
    assert row["research_decision"] == "BUY"
    assert row["research_reason"] == "ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT"
