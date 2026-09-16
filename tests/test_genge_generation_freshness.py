from datetime import datetime, timezone

from src.strategies.genge_opportunity_discovery.generation_freshness import evaluate_generation_freshness
from src.strategies.genge_opportunity_discovery.investor_decision_dashboard import build_dashboard
from src.strategies.genge_opportunity_discovery.investor_live_execution_overlay import apply_live_execution_overlay


def _canonical(trade_date="2026-09-16", generated_at="2026-09-16T10:00:00+00:00"):
    return {
        "snapshot_id": "freshness-test",
        "source_run_id": "35000000000",
        "generated_at": generated_at,
        "latest_trade_date": trade_date,
        "production": {"holding_decisions": [], "candidate_decisions": []},
    }


def _stale_dashboard():
    canonical = _canonical("2026-09-14", "2026-09-14T10:00:00+00:00")
    canonical["production"]["candidate_decisions"] = [{
        "code": "600036",
        "stock_name": "招商银行",
        "scope": "CANDIDATE",
        "action": "BUY",
        "current_price": 41.0,
        "neutral_value": 55.0,
        "v311_production_bridge": "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT",
        "no_auto_trade": True,
    }]
    terminal = [{
        "code": "600036",
        "stock_name": "招商银行",
        "terminal_decision": "BUY",
        "terminal_current_price": "41",
        "terminal_formal_buy_authorized": "True",
        "decision_authority": "RESEARCH_TERMINAL_VIEW",
        "source_valuation_confidence": "HIGH",
        "v31_neutral_value": "55",
        "formal_buy_max_price_to_neutral": "0.8",
        "no_auto_trade": "True",
    }]
    return build_dashboard(
        canonical=canonical,
        holdings={},
        funds=[],
        capital={"status": "TEST", "planning_cash_cny": 70000.0, "planner": {}, "no_auto_trade": True},
        terminal_decisions=terminal,
        market_regime={"as_of_date": "2026-09-15", "status": "GREEN", "allow_new_buy": True, "position_multiplier": 1.0},
        generated_at="2026-09-16T13:50:00+00:00",
    )


def test_freshness_rejects_two_session_old_canonical_after_close():
    freshness = evaluate_generation_freshness(
        _canonical("2026-09-14", "2026-09-14T10:00:00+00:00"),
        market_regime={"as_of_date": "2026-09-15"},
        evaluated_at="2026-09-16T13:50:00+00:00",
        strict_missing_metadata=True,
    )
    assert freshness["status"] == "STALE_UPSTREAM"
    assert freshness["formal_new_exposure_allowed"] is False
    assert "CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION" in freshness["reasons"]
    assert "MARKET_CONTEXT_BEHIND_COMPLETED_SESSION" in freshness["reasons"]


def test_before_close_accepts_previous_completed_weekday():
    freshness = evaluate_generation_freshness(
        _canonical("2026-09-15", "2026-09-16T02:00:00+00:00"),
        evaluated_at="2026-09-16T03:00:00+00:00",
        strict_missing_metadata=True,
    )
    assert freshness["status"] == "OK"
    assert freshness["expected_min_trade_date"] == "2026-09-15"


def test_legacy_fixture_without_generation_metadata_is_labelled_but_not_rewritten():
    canonical = _canonical()
    canonical.pop("generated_at")
    freshness = evaluate_generation_freshness(canonical, evaluated_at="2026-09-16T13:50:00+00:00")
    assert freshness["status"] == "UNVERIFIABLE"
    assert freshness["fail_closed_applied"] is False


def test_dashboard_stale_generation_keeps_truth_visible_but_blocks_new_capital():
    payload = _stale_dashboard()
    assert payload["freshness_contract"]["status"] == "STALE_UPSTREAM"
    assert payload["formal_new_exposure_allowed"] is False
    assert payload["market"]["allow_new_buy"] is False
    assert payload["capital_deployment"]["operations"] == []
    assert payload["capital_deployment"]["deployment_budget_cny"] == 0.0
    assert payload["capital_deployment"]["planned_immediate_cash_cny"] == 0.0
    assert payload["terminal_opportunities"]["buy_now"][0]["currently_actionable"] is False
    assert payload["headline"].endswith("计划立即投入≈¥0")


def test_live_execution_overlay_cannot_resurrect_stale_new_exposure():
    payload = _stale_dashboard()
    hourly = {
        "canonical_snapshot_id": "freshness-test",
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "rows": [],
    }
    live = apply_live_execution_overlay(
        payload,
        hourly,
        now=datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc),
    )
    assert live["formal_new_exposure_allowed"] is False
    assert live["capital_deployment"]["operations"] == []
    assert live["capital_deployment"]["deployment_budget_cny"] == 0.0
    assert live["decision_summary"]["planned_immediate_cash_cny"] == 0.0
    assert live["live_execution_overlay"]["freshness_blocks_new_exposure"] is True
    assert live["headline"].startswith("数据代际=STALE_UPSTREAM；禁止新增仓位；")
    assert live["headline"].endswith("计划立即投入≈¥0")
