import pytest

from src.strategies.genge_opportunity_discovery.terminal_urgent_evidence_reopen import (
    build_reopen_plan,
)


def _row(code, *, priority="P2", industry="C36汽车制造业"):
    return {
        "code": code,
        "name": f"stock-{code}",
        "industry": industry,
        "research_priority": priority,
        "research_decision": "REJECT",
        "research_reason": "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY",
        "reopen_on_new_evidence": True,
        "urgent_research": True,
        "urgent_research_reasons": ["P0_EVIDENCE_BLOCKED"] if priority == "P0" else ["QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED"],
        "hard_gate_unknowns": ["predictability", "long_term_demand", "moat"],
        "hard_gate_failures": [],
        "research_authority": "RESEARCH_ONLY",
        "formal_buy_authorized": False,
        "no_auto_trade": True,
    }


def _payload(rows):
    return {
        "contract": "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1",
        "all_requested_terminal": True,
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "source_deep_lambda_run_id": "12345",
        "source_every_industry_run_id": "54321",
        "urgent_research_queue": rows,
    }


def test_p0_and_specialized_urgent_rows_are_reopened_without_trade_authority():
    plan = build_reopen_plan(
        _payload(
            [
                _row("603596"),
                _row("601318", priority="P0", industry="J68保险业"),
                _row("603993", priority="P0", industry="B09有色金属矿采选业"),
            ]
        )
    )
    assert plan["requested_codes"] == ["601318", "603993", "603596"]
    assert plan["requested_count"] == 3
    assert plan["research_authority"] == "RESEARCH_ONLY"
    assert plan["formal_trading_authority"] is False
    assert plan["automatic_formal_buy_allowed"] is False
    assert plan["automatic_gate_inference_allowed"] is False
    assert plan["unknown_is_pass"] is False
    assert plan["no_auto_trade"] is True


def test_known_hard_gate_failure_cannot_enter_evidence_reopen():
    row = _row("603233")
    row["hard_gate_failures"] = ["financial_safety"]
    with pytest.raises(ValueError, match="known hard-gate failure"):
        build_reopen_plan(_payload([row]))


def test_non_evidence_reject_cannot_be_laundered_into_reopen():
    row = _row("603233")
    row["research_reason"] = "HARD_GATE_FAIL"
    with pytest.raises(ValueError, match="not evidence-blocked"):
        build_reopen_plan(_payload([row]))


def test_reopen_requires_research_only_terminal_authority():
    payload = _payload([_row("600406", priority="P0")])
    payload["formal_trading_authority"] = True
    with pytest.raises(ValueError, match="must not have Formal authority"):
        build_reopen_plan(payload)


def test_duplicate_code_is_deduplicated_deterministically():
    plan = build_reopen_plan(_payload([_row("001316", priority="P0"), _row("001316", priority="P0")]))
    assert plan["requested_codes"] == ["001316"]
