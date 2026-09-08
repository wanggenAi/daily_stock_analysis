from src.strategies.genge_opportunity_discovery.three_pillar_decision_center import build_decision_center, render_markdown


def _dashboard():
    return {
        "no_auto_trade": True,
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "latest_trade_date": "2026-09-07",
        "canonical_snapshot_id": "snap-1",
        "stock_portfolio": {
            "status": "CONFIRMED",
            "rows": [
                {
                    "code": "603993",
                    "name": "洛阳钼业",
                    "quantity": 900,
                    "average_cost": 18.9,
                    "current_price": 19.0,
                    "pnl_pct": 0.5,
                    "formal_action": "HOLD",
                    "investor_action": "继续持有；可分批加仓1手",
                    "neutral_value": 28.1,
                    "valuation_confidence": "HIGH",
                    "reason_codes": "FUNDAMENTALS_INTACT",
                    "holding_add_authorized": True,
                },
                {
                    "code": "001316",
                    "name": "润贝航科",
                    "quantity": 200,
                    "average_cost": 25.7,
                    "current_price": 29.6,
                    "pnl_pct": 15.0,
                    "formal_action": "HOLD_REVIEW",
                    "investor_action": "持有观察",
                    "neutral_value": 49.3,
                    "valuation_confidence": "LOW",
                    "reason_codes": "VALUATION_CONFIDENCE_LOW",
                    "holding_add_authorized": False,
                },
            ],
        },
        "capital_direction": {
            "direct_fund_flow_claimed": False,
            "method": "MARKET_BEHAVIOR_PROXY",
            "strongest_industries": [{"industry": "电力设备", "status": "STRONG", "score": 92.0}],
        },
        "terminal_opportunities": {
            "available": True,
            "buy_now": [],
            "wait_price": [
                {
                    "code": "600000",
                    "name": "测试机会",
                    "industry": "银行",
                    "terminal_decision": "WAIT_PRICE",
                    "current_price": 10.0,
                    "wait_price_max": 9.0,
                    "neutral_value": 12.0,
                    "valuation_confidence": "HIGH",
                    "reason_class": "PRICE_NOT_READY",
                    "formal_buy_authorized": False,
                }
            ],
            "reject_count": 499,
            "invalid_unauthorized_buy_count": 0,
        },
    }


def _era():
    return {
        "formal_trading_authority": False,
        "no_auto_trade": True,
        "research_as_of": "2026-09-08T02:57:40Z",
        "trends": [
            {
                "trend_id": "digital_infrastructure",
                "lifecycle": "EMERGING",
                "confidence_score": 33.69,
                "structural_score": 57.06,
                "industrial_score": 62.5,
                "cyclical_score": 67.5,
                "evidence_count": 3,
                "independent_families": 2,
                "components": {"real_demand_confirmation": 100.0},
            }
        ],
    }


def _deep_reviews():
    return {
        "profiles": {
            "603993": {
                "gates": {
                    "predictability": {"status": "UNKNOWN", "confidence": "HIGH", "rationale": "cycle risk", "evidence": [{"url": "https://example.com"}]},
                    "long_term_demand": {"status": "PASS", "confidence": "HIGH", "rationale": "demand", "evidence": [{"url": "https://example.com"}]},
                }
            }
        }
    }


def test_three_pillars_are_first_class_and_fail_closed_on_deep_review_gaps():
    out = build_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        deep_review_config=_deep_reviews(),
        industry_links={"links": {"digital_infrastructure": ["电力设备", "通信"]}},
        era_handoff={"queue": []},
        generated_at="2026-09-08T04:00:00+00:00",
    )
    assert out["contract_version"] == "GEN_GE_THREE_PILLAR_DECISION_CENTER_V1"
    assert out["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert out["formal_action_recomputed"] is False
    assert out["no_auto_trade"] is True
    assert set(out) >= {
        "pillar_1_holdings_deep_analysis",
        "pillar_2_world_social_market_capital_map",
        "pillar_3_deep_opportunities",
    }
    holdings = out["pillar_1_holdings_deep_analysis"]
    assert holdings["holding_count"] == 2
    assert holdings["explicit_deep_review_count"] == 1
    assert holdings["complete_deep_review_count"] == 0
    assert holdings["deep_review_gap_count"] == 2
    assert holdings["rows"][0]["deep_review"]["status"] == "DEEP_REVIEW_PARTIAL"
    assert holdings["rows"][1]["deep_review"]["status"] == "DEEP_REVIEW_MISSING"
    assert out["decision_readiness"]["all_holdings_explicit_deep_review_complete"] is False


def test_world_social_trend_and_tactical_proxy_remain_separate():
    out = build_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        deep_review_config=_deep_reviews(),
        industry_links={"links": {"digital_infrastructure": ["电力设备", "通信"]}},
        era_handoff={"queue": []},
    )
    capital = out["pillar_2_world_social_market_capital_map"]
    assert capital["direct_fund_flow_claimed"] is False
    assert capital["structural_world_social_trends"][0]["trend_id"] == "digital_infrastructure"
    assert capital["structural_world_social_trends"][0]["a_share_research_industries"] == ["电力设备", "通信"]
    assert capital["tactical_market_behavior_proxy"][0]["industry"] == "电力设备"
    assert capital["validated_handoff_count"] == 0
    assert capital["intersection_status"] == "NO_VALIDATED_A_SHARE_HANDOFF"


def test_terminal_opportunities_do_not_invent_buy_authority():
    out = build_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        deep_review_config={},
        industry_links={},
        era_handoff={"queue": []},
    )
    opportunities = out["pillar_3_deep_opportunities"]
    assert opportunities["buy_now"] == []
    assert len(opportunities["wait_price"]) == 1
    assert opportunities["wait_price"][0]["terminal_decision"] == "WAIT_PRICE"
    assert opportunities["terminal_reject_count"] == 499
    assert opportunities["actionable_count"] == 1


def test_markdown_leads_with_three_investor_questions():
    out = build_decision_center(
        dashboard=_dashboard(),
        era_radar=_era(),
        deep_review_config=_deep_reviews(),
        industry_links={"links": {"digital_infrastructure": ["电力设备"]}},
        era_handoff={"queue": []},
    )
    md = render_markdown(out)
    assert "## 1. 我的持仓：深算后到底怎么办" in md
    assert "## 2. 世界/社会/市场：钱可能在哪里" in md
    assert "## 3. 新机会：润贝型以及其他机会深算结果" in md
    assert "UNKNOWN != PASS" in md
