"""V4 P0 tests: presentation must never manufacture trade authority."""
import pytest

from src.strategies.genge_opportunity_discovery.investor_decision_v4_projection import project_v4_p0


def dashboard():
    return {
        "no_auto_trade": True, "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False, "generated_at": "2026-09-26T08:00:00Z",
        "canonical_snapshot_id": "current-verified-id", "latest_trade_date": "2026-09-24",
        "market": {"as_of_date": "2026-09-24", "status": "RED", "context_scope": "EOD_DAILY_STRUCTURE"},
        "freshness_contract": {"status": "STALE_UPSTREAM"},
        "formal_holding_actions_currently_usable": True,
        "stock_portfolio": {"rows": [{"code": "603993", "quantity": 1100,
                                      "formal_action": "BUY", "action_authority": "FORMAL",
                                      "formal_action_currently_usable": True,
                                      "action_lifecycle": "UNCHANGED"}]},
        "terminal_opportunities": {"buy_now": [{"code": "001316", "currently_actionable": True}]},
        "capital_deployment": {"available_cash_cny": 50000, "planned_immediate_cash_cny": 10000},
    }


def test_stale_does_not_expose_upstream_buy_or_let_cash_escape():
    result = project_v4_p0(dashboard())
    assert result["formal_buy_now"] == []
    assert result["formal_wait_price"] == []
    assert result["holdings"][0]["executable_shares"] == 0
    assert result["planned_immediate_cash_cny"] == 0
    assert result["upstream_terminal_counts_audit_only"]["buy_now"] == 1
    assert result["feeds"]["market"]["scope"] == "EOD_DAILY_STRUCTURE"


def test_missing_broker_funds_are_unknown_not_zero():
    result = project_v4_p0(dashboard())
    assert result["funds_status"] == "UNVERIFIED"
    assert result["feeds"]["funds"]["as_of"] is None


def test_unmatched_lineage_is_explicitly_blocked():
    result = project_v4_p0(dashboard(), {
        "no_auto_trade": True, "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False, "canonical_snapshot_id": "other",
        "latest_trade_date": "2026-09-25",
    })
    assert not result["lineage_matches"]
    assert "CROSS_FEED_LINEAGE_MISMATCH" in result["authority_blockers"]


@pytest.mark.parametrize("change", [
    {"no_auto_trade": False}, {"formal_action_source": "JEV"},
    {"formal_action_recomputed": True},
])
def test_rejects_parallel_decision_authority(change):
    source = dashboard()
    source.update(change)
    with pytest.raises(ValueError):
        project_v4_p0(source)


def test_radar_cannot_claim_formal_authority():
    with pytest.raises(ValueError):
        project_v4_p0(dashboard(), era_radar={
            "no_auto_trade": True, "formal_trading_authority": True, "trends": [],
        })


def test_holdings_reconciliation_absence_removes_formal_display():
    source = dashboard()
    source["formal_holding_actions_currently_usable"] = False
    result = project_v4_p0(source)
    assert result["holdings"][0]["recorded_action"] is None
    assert result["holdings"][0]["action_presentation_status"] == "RESEARCH_ONLY"


def test_repeated_projection_is_deterministic_and_input_unchanged():
    source = dashboard()
    before = repr(source)
    assert project_v4_p0(source) == project_v4_p0(source)
    assert repr(source) == before
