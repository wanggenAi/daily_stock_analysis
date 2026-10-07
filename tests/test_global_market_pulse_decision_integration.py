from tools.apply_global_market_pulse_to_decision_center import apply_global_pulse, render_global_section


def _decision():
    return {
        "contract_version": "GEN_GE_THREE_PILLAR_DECISION_CENTER_V1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "executive_summary": {},
        "decision_readiness": {},
        "pillar_1_holdings_deep_analysis": {
            "rows": [{"code": "603993", "name": "洛阳钼业", "formal_action": "HOLD_REVIEW"}]
        },
        "pillar_2_world_social_market_capital_map": {},
        "pillar_3_deep_opportunities": {"research_gap": [{"code": "603993", "name": "洛阳钼业"}]},
    }


def _pulse():
    return {
        "contract_version": "GEN_GE_GLOBAL_MARKET_PULSE_V2",
        "generated_at": "2026-10-07T12:00:00+00:00",
        "clock": "GLOBAL_MARKET_INDEPENDENT_OF_A_SHARE_CALENDAR",
        "a_share_market_clock": {"last_valid_trade_date": "2026-09-30"},
        "global_research_clock": {"observed_at": "2026-10-07T12:00:00+00:00", "continues_during_a_share_holidays": True},
        "coverage": {"status": "OK"},
        "risk_regime": {"status": "NEUTRAL", "score": 45},
        "series": {
            "COPPER": {"status": "OK", "since_last_a_share_close_pct": 4.0, "change_24h_pct": 1.0, "change_5d_pct": 4.0, "market_date": "2026-10-07", "freshness": "FRESH"},
            "GOLD": {"status": "OK", "since_last_a_share_close_pct": -3.0, "change_24h_pct": -1.0, "change_5d_pct": -3.0, "market_date": "2026-10-07", "freshness": "FRESH"},
        },
        "global_context": [],
        "security_transmission": [
            {
                "code": "603993",
                "name": "洛阳钼业",
                "direction": "MIXED",
                "magnitude": "MEDIUM",
                "factors": [],
                "research_implication": "REASSESS_VALUATION_AND_DEEP_REVIEW",
                "authority": "RESEARCH_ONLY",
                "formal_action_eligible": False,
                "formal_action_mutation_allowed": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        ],
        "pre_open_intelligence": {
            "status": "AVAILABLE",
            "holiday_gap_risk": "NORMAL",
            "holiday_positive_accumulation": "MATERIAL",
            "next_a_share_open_watch": ["Re-evaluate resource producers."],
            "authority": "RESEARCH_ONLY",
            "formal_action_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        },
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "formal_action_mutation_allowed": False,
        "automatic_promotion_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def test_global_pulse_enters_pillar2_and_security_impact_without_changing_formal_action():
    result = apply_global_pulse(_decision(), _pulse())
    holding = result["pillar_1_holdings_deep_analysis"]["rows"][0]
    assert holding["formal_action"] == "HOLD_REVIEW"
    assert holding["global_market_impact"]["direction"] == "MIXED"
    pillar2 = result["pillar_2_world_social_market_capital_map"]
    assert pillar2["global_market_pulse"]["status"] == "OK"
    assert pillar2["pre_open_intelligence"]["status"] == "AVAILABLE"
    assert pillar2["global_transmission"][0]["code"] == "603993"
    assert result["decision_readiness"]["global_market_pulse_formal_authority_granted"] is False
    assert result["no_auto_trade"] is True
    assert "全球市场脉搏" in render_global_section(result)


def test_unsafe_global_pulse_is_rejected_fail_closed():
    pulse = _pulse()
    pulse["formal_trading_authority"] = True
    result = apply_global_pulse(_decision(), pulse)
    pillar2 = result["pillar_2_world_social_market_capital_map"]
    assert pillar2["global_market_pulse"]["status"] == "REJECTED_FAIL_CLOSED"
    assert pillar2["global_transmission"] == []
    assert pillar2["pre_open_intelligence"]["formal_action_eligible"] is False
    assert result["decision_readiness"]["global_market_pulse_available"] is False


def test_legacy_v1_pulse_is_normalized_fail_closed_during_merge_race():
    pulse = _pulse()
    pulse["contract_version"] = "GEN_GE_GLOBAL_MARKET_PULSE_V1"
    pulse.pop("pre_open_intelligence")
    pulse.pop("a_share_market_clock")
    pulse.pop("global_research_clock")
    for row in pulse["security_transmission"]:
        row.pop("formal_action_eligible")
        row.pop("automatic_promotion_allowed")
    result = apply_global_pulse(_decision(), pulse)
    pillar2 = result["pillar_2_world_social_market_capital_map"]
    assert pillar2["global_market_pulse"]["status"] == "OK"
    assert pillar2["pre_open_intelligence"]["status"] == "UNAVAILABLE"
    assert pillar2["pre_open_intelligence"]["formal_action_eligible"] is False
    assert pillar2["global_transmission"][0]["formal_action_eligible"] is False
    assert result["decision_readiness"]["pre_open_intelligence_available"] is False
