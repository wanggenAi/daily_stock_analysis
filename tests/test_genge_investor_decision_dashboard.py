import pytest

from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import (
    build_dashboard,
    render_markdown,
)


def _decision(code: str, name: str, scope: str, action: str, price: float, value: float):
    return {
        "code": code,
        "stock_name": name,
        "scope": scope,
        "action": action,
        "current_price": price,
        "neutral_value": value,
        "valuation_confidence": "HIGH",
        "reason_codes": "TEST_REASON",
        "hard_gate_failures": "",
        "hard_gate_unknowns": "",
        "price_date": "2026-09-01",
        "decision_date": "2026-09-01",
        "v311_production_bridge": "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT",
        "no_auto_trade": True,
    }


def _canonical():
    return {
        "snapshot_id": "snapshot-1",
        "source_run_id": "12345",
        "latest_trade_date": "2026-09-01",
        "production": {
            "holding_decisions": [
                _decision("600406", "国电南瑞", "HOLDING", "REDUCE_25", 22.92, 17.46),
                _decision("603993", "洛阳钼业", "HOLDING", "HOLD", 19.06, 28.13),
                _decision("001316", "润贝航科", "HOLDING", "HOLD_REVIEW", 26.88, 49.37),
                _decision("601318", "中国平安", "HOLDING", "HOLD_REVIEW", 57.23, 0.0),
            ],
            "candidate_decisions": [],
        },
        "deep_review": {
            "rows": [
                {
                    "rank": 1,
                    "code": "603986",
                    "stock_name": "兆易创新",
                    "industry": "半导体",
                    "candidate_class": "A1",
                    "valuation_confidence": "HIGH",
                    "current_price": "150",
                    "hard_blockers": "",
                },
                {
                    "rank": 2,
                    "code": "601020",
                    "stock_name": "华钰矿业",
                    "industry": "有色",
                    "candidate_class": "B",
                    "valuation_confidence": "MEDIUM",
                    "current_price": "20",
                    "hard_blockers": "valuation_wait",
                },
            ]
        },
        "discovery": {"rows": []},
    }


def _holdings():
    return {
        "601318": {"code": "601318", "name": "中国平安", "quantity": 300, "average_cost": 57.1676},
        "603993": {"code": "603993", "name": "洛阳钼业", "quantity": 600, "average_cost": 19.1087},
        "001316": {"code": "001316", "name": "润贝航科", "quantity": 200, "average_cost": 26.0950},
        "600406": {"code": "600406", "name": "国电南瑞", "quantity": 200, "average_cost": 23.1253},
    }


def test_dashboard_is_investor_first_without_recomputing_formal_actions():
    payload = build_dashboard(
        canonical=_canonical(),
        holdings=_holdings(),
        funds=[],
        market_regime={
            "as_of_date": "2026-09-01",
            "status": "YELLOW",
            "score": 54.2,
            "allow_new_buy": True,
            "position_multiplier": 0.5,
            "advance_ratio": 0.47,
            "above_ma20_ratio": 0.52,
            "above_ma60_ratio": 0.49,
            "distribution_ratio": 0.10,
            "external_risk_level": "LOW",
            "risk_reasons": [],
            "data_quality": "OK",
        },
        industry_regimes=[
            {"industry": "半导体", "status": "STRONG", "score": "82", "sample_count": "35", "advance_ratio": "0.72", "above_ma20_ratio": "0.75", "distribution_ratio": "0.05"},
            {"industry": "有色", "status": "STRONG", "score": "76", "sample_count": "28", "advance_ratio": "0.66", "above_ma20_ratio": "0.70", "distribution_ratio": "0.08"},
        ],
        research_priority={
            "queue": [
                {"code": "603986", "name": "兆易创新", "priority": "P2", "thesis_status": "STRENGTHENING_RESEARCH_SIGNAL"}
            ]
        },
        mode="DAILY",
        generated_at="2026-09-02T01:00:00+00:00",
    )

    assert payload["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert payload["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True
    assert payload["presentation_contract"]["investor_first"] is True
    assert payload["decision_summary"]["formal_action_counts"] == {
        "HOLD": 1,
        "HOLD_REVIEW": 2,
        "REDUCE_25": 1,
    }
    assert payload["stock_portfolio"]["rows"][0]["code"] == "600406"
    assert payload["stock_portfolio"]["rows"][0]["formal_action"] == "REDUCE_25"
    assert payload["stock_portfolio"]["rows"][0]["investor_action"] == "减仓25%"
    assert payload["fund_portfolio"]["status"] == "LATEST_HOLDINGS_NOT_PERSISTED"
    assert payload["market"]["status"] == "YELLOW"
    assert payload["capital_direction"]["strongest_industries"][0]["industry"] == "半导体"
    assert payload["capital_direction"]["direct_fund_flow_claimed"] is False
    assert payload["opportunities"][0]["code"] == "603986"
    assert payload["opportunities"][0]["tier"] == "NEAR_BUY_RESEARCH"
    assert payload["structural_trends"]["strengthening_signals"][0]["code"] == "603986"


def test_dashboard_rejects_non_production_decision_authority():
    canonical = _canonical()
    canonical["production"]["holding_decisions"][0]["no_auto_trade"] = False
    with pytest.raises(ValueError, match="no-auto-trade"):
        build_dashboard(canonical=canonical, holdings=_holdings(), funds=[])


def test_rendered_dashboard_leads_with_decisions_not_engineering_status():
    payload = build_dashboard(
        canonical=_canonical(),
        holdings=_holdings(),
        funds=[],
        mode="HOURLY",
        generated_at="2026-09-02T01:00:00+00:00",
    )
    text = render_markdown(payload)
    assert text.startswith("# 投资决策驾驶舱")
    assert "## 1. 我的股票：现在该怎么做" in text
    assert "减仓25%" in text
    assert "## 2. 我的基金" in text
    assert "## 3. 市场现在是什么状态" in text
    assert "## 4. 钱往哪里走" in text
    assert "## 5. 产业 / 社会发展趋势" in text
    assert "## 6. 全市场机会：哪些值得继续盯" in text
    assert "## 7. 事件触发 / 深算变化" in text
