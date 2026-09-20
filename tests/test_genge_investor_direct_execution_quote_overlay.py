from datetime import datetime, timezone
from pathlib import Path

from src.strategies.genge_opportunity_discovery.hourly_deep_overlay import Quote
from src.strategies.genge_opportunity_discovery.investor_direct_execution_quote_overlay import (
    DIRECT_PRICE_SOURCE,
    apply_direct_execution_quote_overlay,
    execution_codes,
    market_session_state,
)


def _dashboard():
    return {
        "contract_version": "GEN_GE_INVESTOR_DECISION_DASHBOARD_V3",
        "canonical_snapshot_id": "snap-1",
        "canonical_source_run_id": "run-1",
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "market": {"status": "YELLOW", "allow_new_buy": True, "position_multiplier": 0.5},
        "stock_portfolio": {
            "rows": [
                {"code": "601318", "name": "中国平安", "quantity": 300, "average_cost": 57.0,
                 "current_price": 56.0, "formal_action": "HOLD_REVIEW", "holding_add_authorized": False,
                 "formal_action_currently_usable": True, "action_authority": "FORMAL"},
                {"code": "600406", "name": "国电南瑞", "quantity": 200, "average_cost": 23.0,
                 "current_price": 22.5, "formal_action": "ADD", "holding_add_authorized": False,
                 "formal_action_currently_usable": True, "action_authority": "FORMAL"},
            ]
        },
        "terminal_opportunities": {
            "buy_now": [{"code": "600036", "name": "招商银行", "current_price": 40.0,
                         "formal_buy_authorized": True, "neutral_value": 55.0, "buy_ratio": 0.8}],
            "wait_price": [{"code": "601899", "name": "紫金矿业", "current_price": 34.0,
                            "wait_price_max": 32.0}],
            "reject_count": 1,
        },
        "capital_deployment": {
            "status": "READY", "available_cash_cny": 70000.0,
            "capital_as_of": "2026-09-15T09:30:00+08:00",
            "planner_config": {"max_deployment_ratio": 0.7, "max_single_name_ratio_of_available_cash": 0.2,
                               "max_names": 5, "first_tranche_ratio": 0.5, "second_tranche_discount_pct": 0.02},
            "planned_immediate_cash_cny": 0,
        },
        "decision_summary": {"planned_immediate_cash_cny": 0},
    }


def _active_now():
    return datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc)  # 10:00 Beijing


def _good_provider(codes):
    prices = {"601318": 55.8, "600406": 22.0, "600036": 43.0, "601899": 31.5}
    observed = "2026-09-15T09:59:30+08:00"
    return {
        code: Quote(code, code, prices[code], prices[code], 0.0, observed, "tencent_quote", "OK")
        for code in codes
    }


def _failed_provider(codes):
    observed = "2026-09-15T10:00:00+08:00"
    return {
        code: Quote(code, code, None, None, None, observed, "tencent_quote", "FETCH_ERROR")
        for code in codes
    }


def test_execution_universe_is_dashboard_driven_not_hourly_research_driven():
    assert execution_codes(_dashboard()) == ["600036", "600406", "601318", "601899"]


def test_active_session_direct_refresh_gets_full_coverage_without_mutating_authority():
    before = _dashboard()
    payload = apply_direct_execution_quote_overlay(
        before, quote_provider=_good_provider, now=_active_now(), max_age_minutes=15, retry_attempts=1
    )
    overlay = payload["live_execution_overlay"]
    assert overlay["source"] == DIRECT_PRICE_SOURCE
    assert overlay["market_session_state"] == "ACTIVE_MORNING"
    assert overlay["market_data_status"] == "OK"
    assert overlay["applied_code_count"] == 4
    assert overlay["expected_code_count"] == 4
    assert overlay["coverage_ratio"] == 1.0
    rows = {row["code"]: row for row in payload["stock_portfolio"]["rows"]}
    assert rows["600406"]["current_price"] == 22.0
    assert rows["600406"]["price_source"] == DIRECT_PRICE_SOURCE
    assert rows["600406"]["formal_action"] == "ADD"
    assert payload["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert payload["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True
    operations = {op["code"]: op for op in payload["capital_deployment"]["operations"]}
    assert operations["600406"]["immediate_execution_eligible"] is True
    assert operations["600036"]["immediate_execution_eligible"] is True
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] > 0


def test_provider_failure_during_active_session_is_visible_and_fails_closed():
    payload = apply_direct_execution_quote_overlay(
        _dashboard(), quote_provider=_failed_provider, now=_active_now(), max_age_minutes=15, retry_attempts=1
    )
    overlay = payload["live_execution_overlay"]
    assert overlay["market_session_state"] == "ACTIVE_MORNING"
    assert overlay["market_data_status"] == "DEGRADED"
    assert overlay["applied_code_count"] == 0
    assert set(overlay["missing_codes"]) == {"600036", "600406", "601318", "601899"}
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] == 0
    assert all(
        op["immediate_execution_eligible"] is False
        and op["execution_note"] == "LIVE_EXECUTION_QUOTE_UNAVAILABLE"
        for op in payload["capital_deployment"]["operations"]
    )


def test_lunch_break_never_reports_immediate_execution_even_with_fresh_snapshot():
    lunch = datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc)  # 12:00 Beijing
    assert market_session_state(lunch) == "LUNCH_BREAK"
    payload = apply_direct_execution_quote_overlay(
        _dashboard(), quote_provider=_good_provider, now=lunch, max_age_minutes=180, retry_attempts=1
    )
    overlay = payload["live_execution_overlay"]
    assert overlay["market_data_status"] == "OFF_SESSION"
    assert overlay["market_session_active"] is False
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] == 0
    assert all(
        op["immediate_execution_eligible"] is False
        and op["execution_note"] == "MARKET_NOT_IN_CONTINUOUS_SESSION"
        for op in payload["capital_deployment"]["operations"]
    )


def test_live_quote_workflow_refreshes_final_decision_center():
    workflow = Path(".github/workflows/genge-live-execution-quote-refresh.yml").read_text(encoding="utf-8")
    assert "actions: write" in workflow
    assert "gh workflow run genge-three-pillar-decision-center.yml" in workflow
    assert "Refresh final decision center after execution-price persistence" in workflow


def test_live_quote_pr_concurrency_is_isolated_from_production():
    workflow = Path(".github/workflows/genge-live-execution-quote-refresh.yml").read_text(encoding="utf-8")
    concurrency = workflow.split("concurrency:", 1)[1].split("env:", 1)[0]
    assert "github.event_name == 'pull_request'" in concurrency
    assert "github.event.pull_request.number" in concurrency
    assert "|| 'production'" in concurrency
    assert "cancel-in-progress: false" in concurrency
