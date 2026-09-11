from pathlib import Path

from src.strategies.genge_opportunity_discovery.success_archetype_recall import (
    load_archetype,
    score_row,
)


ARCHETYPE = Path("data/research_archetypes/runbei_v1.json")


def _row(**updates):
    row = {
        "code": "603055",
        "stock_name": "台华新材",
        "terminal_decision": "REJECT",
        "terminal_reason_class": "EVIDENCE_INSUFFICIENT",
        "terminal_full_review_attempted": True,
        "v31_execution_universe_eligible": True,
        "v31_hard_gate_failures": "",
        "confirmed_negative_items": "",
        "conflicted_evidence_items": "",
        "financial_review_status": "OK",
        "quant_status": "PRIORITY_RESEARCH",
        "earnings_quality_score": 90.0,
        "cash_conversion_ratio": 2.7,
        "net_profit_yoy_pct": 17.96,
        "recurring_profit_yoy_pct": 73.29,
        "operating_cash_flow_yoy_pct": 267.76,
    }
    row.update(updates)
    return row


def test_taihua_like_profile_clears_high_confidence_runbei_recall_threshold():
    scored = score_row(_row(), load_archetype(ARCHETYPE))

    assert scored["success_archetype_evidence_coverage"] == 1.0
    assert scored["success_archetype_similarity_score"] >= 70.0
    assert scored["success_archetype_state"] == "ARCHETYPE_MATCH"
    assert scored["success_archetype_formal_action_eligible"] is False
    assert scored["success_archetype_no_auto_trade"] is True


def test_stronger_directional_growth_is_not_penalized_for_overshooting_reference():
    scored = score_row(
        _row(
            cash_conversion_ratio=1.0721,
            net_profit_yoy_pct=80.0,
            recurring_profit_yoy_pct=100.0,
            operating_cash_flow_yoy_pct=260.0,
            earnings_quality_score=95.0,
        ),
        load_archetype(ARCHETYPE),
    )

    assert scored["success_archetype_similarity_score"] == 100.0
    assert scored["success_archetype_state"] == "ARCHETYPE_MATCH"


def test_cash_conversion_remains_symmetric_and_does_not_reward_extreme_spikes():
    baseline = score_row(
        _row(cash_conversion_ratio=1.0721),
        load_archetype(ARCHETYPE),
    )
    extreme = score_row(
        _row(cash_conversion_ratio=5.0),
        load_archetype(ARCHETYPE),
    )

    assert extreme["success_archetype_similarity_score"] < baseline[
        "success_archetype_similarity_score"
    ]
