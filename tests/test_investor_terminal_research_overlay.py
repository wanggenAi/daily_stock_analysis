from pathlib import Path

from src.strategies.genge_opportunity_discovery.investor_terminal_research_overlay import apply_overlay, append_markdown


def _dashboard():
    return {
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "decision_summary": {"terminal_buy_count": 0},
        "data_health": {},
        "presentation_contract": {"section_order": ["market", "stock_portfolio", "capital_deployment"]},
    }


def _terminal():
    row = {
        "code": "600406",
        "name": "国电南瑞",
        "research_decision": "RESEARCH_GAP",
        "research_reason": "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY",
        "research_authority": "RESEARCH_ONLY",
        "formal_buy_authorized": False,
        "no_auto_trade": True,
        "hard_gate_unknowns": ["moat"],
        "urgent_research": True,
        "urgent_research_reasons": ["P0_EVIDENCE_BLOCKED"],
    }
    return {
        "contract": "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1",
        "all_requested_terminal": True,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "requested_count": 1,
        "decision_counts": {"BUY": 0, "WAIT_PRICE": 0, "RESEARCH_GAP": 1, "REJECT": 0},
        "terminal_rows": [row],
        "urgent_research_queue": [row],
        "source_deep_lambda_run_id": "123",
        "source_every_industry_run_id": "456",
    }


def test_overlay_exposes_research_without_mutating_formal_authority():
    out = apply_overlay(_dashboard(), _terminal())
    assert out["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert out["formal_action_recomputed"] is False
    assert out["no_auto_trade"] is True
    assert out["terminal_research_snapshot"]["research_authority"] == "RESEARCH_ONLY"
    assert out["terminal_research_snapshot"]["formal_trading_authority"] is False
    assert out["decision_summary"]["research_gap_count"] == 1
    assert out["decision_summary"]["research_reject_count"] == 0
    assert out["decision_summary"]["urgent_research_count"] == 1
    assert "terminal_research" in out["presentation_contract"]["section_order"]


def test_markdown_surfaces_holding_and_urgent_research():
    out = apply_overlay(_dashboard(), _terminal())
    md = append_markdown("# 投资决策驾驶舱\n", out)
    assert "深算研究终态" in md
    assert "国电南瑞 600406" in md
    assert "P0_EVIDENCE_BLOCKED" in md
    assert "RESEARCH_GAP" in md
    assert "RESEARCH_ONLY" in md


def test_overlay_refuses_fake_formal_buy_authority():
    terminal = _terminal()
    terminal["terminal_rows"][0]["formal_buy_authorized"] = True
    try:
        apply_overlay(_dashboard(), terminal)
    except ValueError as exc:
        assert "forbidden authority" in str(exc)
    else:
        raise AssertionError("expected authority violation")


def test_overlay_refuses_urgent_queue_that_is_not_research_gap():
    terminal = _terminal()
    terminal["terminal_rows"][0]["research_decision"] = "REJECT"
    terminal["decision_counts"] = {"BUY": 0, "WAIT_PRICE": 0, "RESEARCH_GAP": 0, "REJECT": 1}
    terminal["urgent_research_queue"][0]["research_decision"] = "REJECT"
    try:
        apply_overlay(_dashboard(), terminal)
    except ValueError as exc:
        assert "urgent research must remain RESEARCH_GAP" in str(exc)
    else:
        raise AssertionError("expected urgent research semantic violation")


def test_overlay_is_explicit_handoff_and_dispatches_three_pillar_after_persistence():
    workflow = Path(".github/workflows/genge-investor-terminal-research-overlay.yml").read_text(encoding="utf-8")
    persist_at = workflow.index("- name: Overlay latest terminal research onto investor brief with optimistic replay")
    dispatch_at = workflow.index("- name: Refresh three-pillar decision center after research overlay")

    assert "workflow_run:" not in workflow
    assert "permissions:\n  contents: write\n  actions: write" in workflow
    assert persist_at < dispatch_at
    assert "gh workflow run genge-three-pillar-decision-center.yml" in workflow[dispatch_at:]


def test_markdown_overlay_is_idempotent_across_rerenders():
    out = apply_overlay(_dashboard(), _terminal())
    first = append_markdown("# 投资决策驾驶舱\n\n## 9. 系统状态\n\n- ok\n", out)
    second = append_markdown(first, out)
    assert second.count("## 深算研究终态（Research-only，不等于正式交易授权）") == 1
    first_stock_mentions = first.count("国电南瑞 600406")
    assert first_stock_mentions >= 1
    assert second.count("国电南瑞 600406") == first_stock_mentions
    assert "## 9. 系统状态" in second
