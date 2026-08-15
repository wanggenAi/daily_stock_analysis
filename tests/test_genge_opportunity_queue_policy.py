from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_queue_policy as policy


def _quality_row(**overrides):
    row = {
        "code": "600001",
        "quant_screen_status": "SECONDARY_RESEARCH",
        "quant_score": 40.0,
        "preliminary_opportunity_engine": "STRONG_TREND_RESEARCH",
        "trend_stabilization_score": 90.0,
        "valuation_score": 80.0,
        "financial_safety_score": 90.0,
        "execution_risk_score": 10.0,
        "value_trap_score": 10.0,
        "relative_strength_20d": 10.0,
        "relative_strength_60d": 10.0,
    }
    row.update(overrides)
    return row


def test_valley_repair_keeps_legacy_quant_ranking_score():
    row = _quality_row(
        preliminary_opportunity_engine="VALLEY_REPAIR",
        quant_score=63.25,
    )

    assert policy.engine_research_score(row) == 63.25


def test_non_valley_engine_removes_legacy_low_price_weight_from_ranking():
    row = _quality_row(quant_score=40.0)

    score = policy.engine_research_score(row)

    assert score > 80.0
    assert score > row["quant_score"]


def test_secondary_queue_uses_engine_score_without_engine_quota():
    strong = _quality_row(code="600001", quant_score=40.0)
    valley = _quality_row(
        code="600002",
        quant_score=55.0,
        preliminary_opportunity_engine="VALLEY_REPAIR",
        trend_stabilization_score=30.0,
    )

    _, secondary = policy.research_queues(
        [strong, valley],
        priority_queue_size=0,
        secondary_queue_size=1,
    )

    assert [row["code"] for row in secondary] == ["600001"]
    assert strong["engine_research_score"] > valley["engine_research_score"]
    assert len(secondary) == 1


def test_priority_code_behavior_is_preserved():
    promoted = _quality_row(code="600003", quant_screen_status="SECONDARY_RESEARCH")
    normal = _quality_row(
        code="600004",
        quant_screen_status="PRIORITY_RESEARCH",
        preliminary_opportunity_engine="VALLEY_REPAIR",
        quant_score=99.0,
    )

    priority, secondary = policy.research_queues(
        [normal, promoted],
        priority_queue_size=1,
        secondary_queue_size=5,
        priority_codes=["600003"],
    )

    assert [row["code"] for row in priority] == ["600003"]
    assert all(row["code"] != "600003" for row in secondary)


def test_earnings_engine_uses_same_price_neutral_non_price_quality():
    trend = _quality_row(preliminary_opportunity_engine="STRONG_TREND_RESEARCH")
    earnings = _quality_row(preliminary_opportunity_engine="EARNINGS_INFLECTION")

    assert policy.engine_research_score(trend) == policy.engine_research_score(earnings)
