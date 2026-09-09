import pytest

from src.strategies.genge_opportunity_discovery.terminal_urgent_evidence_reopen import (
    build_reopen_plan,
)


def _row(
    code,
    *,
    priority="P2",
    industry="C36汽车制造业",
    urgent=True,
    reason="EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY",
):
    return {
        "code": code,
        "name": f"stock-{code}",
        "industry": industry,
        "research_priority": priority,
        "research_decision": "REJECT",
        "research_reason": reason,
        "reopen_on_new_evidence": reason == "EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY",
        "urgent_research": urgent,
        "urgent_research_reasons": (
            (["P0_EVIDENCE_BLOCKED"] if priority == "P0" else ["QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED"])
            if urgent
            else []
        ),
        "hard_gate_unknowns": ["predictability", "long_term_demand", "moat"],
        "hard_gate_failures": [],
        "research_authority": "RESEARCH_ONLY",
        "formal_buy_authorized": False,
        "no_auto_trade": True,
    }


def _payload(terminal_rows, urgent_rows=None):
    urgent_rows = [row for row in terminal_rows if row.get("urgent_research")] if urgent_rows is None else urgent_rows
    counts = {"BUY": 0, "WAIT_PRICE": 0, "REJECT": 0}
    for row in terminal_rows:
        counts[row["research_decision"]] += 1
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
        "requested_count": len(terminal_rows),
        "decision_counts": counts,
        "terminal_rows": terminal_rows,
        "urgent_research_queue": urgent_rows,
    }


def test_p0_and_specialized_urgent_rows_are_reopened_without_trade_authority():
    rows = [
        _row("603596"),
        _row("601318", priority="P0", industry="J68保险业"),
        _row("603993", priority="P0", industry="B09有色金属矿采选业"),
    ]
    plan = build_reopen_plan(_payload(rows))
    assert plan["requested_codes"] == ["603596", "601318", "603993"]
    assert plan["requested_count"] == 3
    assert plan["urgent_requested_codes"] == ["601318", "603993", "603596"]
    assert plan["urgent_requested_count"] == 3
    assert plan["research_authority"] == "RESEARCH_ONLY"
    assert plan["formal_trading_authority"] is False
    assert plan["automatic_formal_buy_allowed"] is False
    assert plan["automatic_gate_inference_allowed"] is False
    assert plan["unknown_is_pass"] is False
    assert plan["no_auto_trade"] is True


def test_nonurgent_terminal_rows_are_retained_in_reopen_workset():
    urgent = _row("600406", priority="P0")
    nonurgent = _row("603233", urgent=False, reason="HARD_GATE_FAIL")
    nonurgent["reopen_on_new_evidence"] = False
    nonurgent["hard_gate_failures"] = ["financial_safety"]
    plan = build_reopen_plan(_payload([urgent, nonurgent], urgent_rows=[urgent]))
    assert plan["requested_codes"] == ["600406", "603233"]
    assert plan["requested_count"] == 2
    assert plan["urgent_requested_codes"] == ["600406"]
    assert plan["urgent_requested_count"] == 1


def test_known_hard_gate_failure_cannot_enter_urgent_reopen_subset():
    row = _row("603233")
    row["hard_gate_failures"] = ["financial_safety"]
    with pytest.raises(ValueError, match="known hard-gate failure"):
        build_reopen_plan(_payload([row]))


def test_non_evidence_reject_cannot_be_laundered_into_urgent_reopen():
    row = _row("603233", reason="HARD_GATE_FAIL")
    row["reopen_on_new_evidence"] = False
    with pytest.raises(ValueError, match="not evidence-blocked"):
        build_reopen_plan(_payload([row], urgent_rows=[row]))


def test_reopen_requires_research_only_terminal_authority():
    payload = _payload([_row("600406", priority="P0")])
    payload["formal_trading_authority"] = True
    with pytest.raises(ValueError, match="must not have Formal authority"):
        build_reopen_plan(payload)


def test_duplicate_terminal_code_is_fail_closed():
    row = _row("001316", priority="P0")
    with pytest.raises(ValueError, match="duplicate codes"):
        build_reopen_plan(_payload([row, dict(row)]))


def test_urgent_row_must_exist_in_terminal_workset():
    terminal = _row("600406", priority="P0")
    outside = _row("001316", priority="P0")
    with pytest.raises(ValueError, match="outside terminal workset"):
        build_reopen_plan(_payload([terminal], urgent_rows=[outside]))
