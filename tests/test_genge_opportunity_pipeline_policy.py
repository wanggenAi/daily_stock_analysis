from __future__ import annotations

from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy as policy


def test_profit_metrics_confirm_loss_to_profit_turnaround():
    financial = pd.DataFrame(
        [
            {"report_date": "2025-03-31", "net_profit": -10.0},
            {"report_date": "2025-06-30", "net_profit": -5.0},
            {"report_date": "2026-03-31", "net_profit": 3.0},
            {"report_date": "2026-06-30", "net_profit": 8.0},
        ]
    )

    result = policy.financial_inflection_metrics(financial, as_of=date(2026, 8, 14))

    assert result["earnings_inflection_confirmed"] is True
    assert result["earnings_inflection_reason"] == "loss_to_profit_turnaround"
    assert result["earnings_inflection_report_date"] == "2026-06-30"


def test_profit_metrics_exclude_future_disclosure():
    financial = pd.DataFrame(
        [
            {"report_date": "2025-06-30", "disclosure_date": "2025-08-01", "net_profit": -5.0},
            {"report_date": "2026-03-31", "disclosure_date": "2026-04-25", "net_profit": 2.0},
            {"report_date": "2026-06-30", "disclosure_date": "2026-08-30", "net_profit": 8.0},
        ]
    )

    result = policy.financial_inflection_metrics(financial, as_of=date(2026, 8, 14))

    assert result["earnings_inflection_report_date"] == "2026-03-31"


def test_strong_trend_removes_only_legacy_price_blockers(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_SCREEN_BLOCKERS",
        lambda row: (
            ["price_position_overheated", "financial_safety_failed"],
            ["price_not_low_enough", "valuation_failed"],
        ),
    )
    row = {
        "price_percentile_5y": 0.82,
        "trend_confirmation_level": "STRONG",
    }

    hard, soft = policy._screen_blockers(row)

    assert "price_position_overheated" not in hard
    assert "price_not_low_enough" not in soft
    assert "financial_safety_failed" in hard
    assert "valuation_failed" in soft


def test_plain_high_price_stock_keeps_overheated_blocker(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_SCREEN_BLOCKERS",
        lambda row: (["price_position_overheated"], ["price_not_low_enough"]),
    )
    row = {
        "price_percentile_5y": 0.82,
        "trend_confirmation_level": "MEDIUM",
        "earnings_inflection_confirmed": False,
    }

    hard, soft = policy._screen_blockers(row)

    assert hard == ["price_position_overheated"]
    assert soft == ["price_not_low_enough"]


def test_tier_promotion_removes_only_duplicated_price_condition(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_TIER_ROW",
        lambda row: {
            **row,
            "tier": "TIER_B",
            "a_condition_pass_count": 10,
            "a_condition_fail_count": 1,
            "a_condition_failed": "price_low_or_reasonable",
            "hard_blockers": "",
            "industry_evidence_status": "VERIFIED",
            "company_evidence_status": "VERIFIED",
        },
    )
    row = {
        "price_percentile_5y": 0.70,
        "trend_confirmation_level": "STRONG",
        "quant_screen_status": "SECONDARY_RESEARCH",
    }

    result = policy._tier_row(row)

    assert result["tier"] == "TIER_A"
    assert result["price_percentile_5y"] == 0.70
    assert result["a_condition_failed"] == ""


def test_tier_does_not_bypass_other_failed_condition_or_hard_blocker(monkeypatch):
    monkeypatch.setattr(
        policy,
        "_ORIGINAL_TIER_ROW",
        lambda row: {
            **row,
            "tier": "TIER_B",
            "a_condition_pass_count": 9,
            "a_condition_fail_count": 2,
            "a_condition_failed": "price_low_or_reasonable;financial_passed",
            "hard_blockers": "financial_safety_failed",
            "industry_evidence_status": "VERIFIED",
            "company_evidence_status": "VERIFIED",
        },
    )
    row = {
        "price_percentile_5y": 0.70,
        "trend_confirmation_level": "STRONG",
        "quant_screen_status": "SECONDARY_RESEARCH",
    }

    result = policy._tier_row(row)

    assert result["tier"] == "TIER_B"
    assert result["a_condition_failed"] == "financial_passed"
    assert result["hard_blockers"] == "financial_safety_failed"
