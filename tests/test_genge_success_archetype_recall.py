from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.success_archetype_recall import (
    build_priority_payload,
    enrich_growth,
    score_row,
    select_extra_financial_rows,
)


def _archetype():
    return {
        "archetype_id": "RUNBEI_TEST",
        "reference": {"code": "001316"},
        "thresholds": {"min_similarity_score": 52.0, "min_evidence_coverage": 0.60},
        "features": [
            {"id": "earnings_quality_score", "weight": 20, "reference_value": 90, "tolerance": 25, "aliases": ["earnings_quality_score"]},
            {"id": "cash_conversion_ratio", "weight": 15, "reference_value": 1.0721, "tolerance": 1.5, "aliases": ["cash_conversion_ratio"]},
            {"id": "net_profit_yoy_pct", "weight": 25, "reference_value": 44.82, "tolerance": 60, "aliases": ["net_profit_yoy_pct"]},
            {"id": "recurring_profit_yoy_pct", "weight": 25, "reference_value": 45.14, "tolerance": 60, "aliases": ["recurring_profit_yoy_pct"]},
            {"id": "operating_cash_flow_yoy_pct", "weight": 15, "reference_value": 26.52, "tolerance": 80, "aliases": ["operating_cash_flow_yoy_pct"]},
        ],
    }


def _row(**updates):
    row = {
        "code": "600001",
        "stock_name": "测试股",
        "terminal_decision": "REJECT",
        "terminal_reason_class": "EVIDENCE_INSUFFICIENT",
        "terminal_full_review_attempted": True,
        "v31_execution_universe_eligible": True,
        "v31_hard_gate_failures": "",
        "confirmed_negative_items": "",
        "conflicted_evidence_items": "",
        "financial_review_status": "OK",
        "quant_status": "HARD_REJECT",
        "earnings_quality_score": 90,
        "cash_conversion_ratio": 1.0721,
        "net_profit_yoy_pct": 44.82,
        "recurring_profit_yoy_pct": 45.14,
        "operating_cash_flow_yoy_pct": 26.52,
    }
    row.update(updates)
    return row


def test_hard_reject_can_be_recalled_for_research_without_formal_authority():
    scored = score_row(_row(), _archetype())
    assert scored["success_archetype_state"] == "ARCHETYPE_MATCH"
    assert scored["success_archetype_similarity_score"] == 100.0
    assert scored["success_archetype_formal_action_eligible"] is False
    assert scored["success_archetype_no_auto_trade"] is True


def test_confirmed_hard_gate_failure_still_blocks_recall():
    scored = score_row(_row(v31_hard_gate_failures="moat"), _archetype())
    assert scored["success_archetype_state"] == "NONE"
    assert "confirmed_hard_gate_failure" in scored["success_archetype_blockers"]


def test_missing_features_reduce_coverage_and_do_not_renormalize_score():
    scored = score_row(
        _row(
            net_profit_yoy_pct="",
            recurring_profit_yoy_pct="",
            operating_cash_flow_yoy_pct="",
        ),
        _archetype(),
    )
    assert scored["success_archetype_evidence_coverage"] == 0.35
    assert scored["success_archetype_similarity_score"] == 35.0
    assert scored["success_archetype_state"] == "NONE"


def test_growth_enrichment_uses_same_period_prior_year_and_excludes_future_disclosure():
    frame = pd.DataFrame(
        [
            {
                "report_date": "2025-06-30",
                "disclosure_date": "2025-08-20",
                "net_profit": 100,
                "recurring_profit": 90,
                "operating_cash_flow": 80,
            },
            {
                "report_date": "2026-06-30",
                "disclosure_date": "2026-08-24",
                "net_profit": 145,
                "recurring_profit": 135,
                "operating_cash_flow": 104,
            },
            {
                "report_date": "2026-09-30",
                "disclosure_date": "2026-10-30",
                "net_profit": 999,
                "recurring_profit": 999,
                "operating_cash_flow": 999,
            },
        ]
    )
    enriched = enrich_growth(_row(), frame, as_of=date(2026, 8, 26))
    assert enriched["archetype_financial_report_date"] == date(2026, 6, 30)
    assert enriched["archetype_financial_disclosure_date"] == date(2026, 8, 24)
    assert round(enriched["net_profit_yoy_pct"], 2) == 45.00
    assert round(enriched["recurring_profit_yoy_pct"], 2) == 50.00
    assert round(enriched["operating_cash_flow_yoy_pct"], 2) == 30.00
    assert enriched["earnings_quality_score"] > 0
    assert enriched["cash_conversion_ratio"] is not None


def test_unknown_core_profit_does_not_become_synthetic_zero_quality_evidence():
    frame = pd.DataFrame(
        [
            {
                "report_date": "2026-06-30",
                "disclosure_date": "2026-08-24",
                "net_profit": None,
                "recurring_profit": None,
                "operating_cash_flow": 100,
            }
        ]
    )
    enriched = enrich_growth(
        _row(
            earnings_quality_score="",
            cash_conversion_ratio="",
            net_profit_yoy_pct="",
            recurring_profit_yoy_pct="",
            operating_cash_flow_yoy_pct="",
        ),
        frame,
        as_of=date(2026, 8, 26),
    )
    assert enriched.get("earnings_quality_score") in (None, "")
    scored = score_row(enriched, _archetype())
    assert "earnings_quality_score" in scored["success_archetype_missing_features"]
    assert scored["success_archetype_evidence_coverage"] == 0.0
    assert scored["success_archetype_state"] == "NONE"


def test_reference_stock_is_diagnostic_only_and_not_put_in_priority_queue():
    reference = score_row(
        _row(code="001316", stock_name="润贝航科"), _archetype()
    )
    peer = score_row(
        _row(code="600002", terminal_current_price="12.34"), _archetype()
    )
    payload = build_priority_payload([reference, peer], _archetype())
    assert payload["queue_count"] == 1
    assert payload["queue"][0]["code"] == "600002"
    assert payload["queue"][0]["source_price"] == 12.34
    assert payload["queue"][0]["source_price_field"] == "terminal_current_price"
    assert payload["queue"][0]["source_price_known_by_recall"] is True
    assert payload["canonical_authority_unchanged"] is True
    assert payload["unknown_evidence_is_pass"] is False


def test_not_selected_candidate_requires_real_independent_financial_evidence():
    without = score_row(
        _row(
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            archetype_financial_review_origin="ARCHETYPE_BOUNDED_FINANCIAL_FETCH",
            archetype_financial_evidence_ready=False,
        ),
        _archetype(),
    )
    assert without["success_archetype_state"] == "NONE"
    assert "financial_review_not_ok_or_independent_evidence_unavailable" in without[
        "success_archetype_blockers"
    ]

    with_evidence = score_row(
        _row(
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            archetype_financial_review_origin="ARCHETYPE_BOUNDED_FINANCIAL_FETCH",
            archetype_financial_evidence_ready=True,
        ),
        _archetype(),
    )
    assert with_evidence["success_archetype_state"] == "ARCHETYPE_MATCH"
    assert with_evidence["success_archetype_formal_action_eligible"] is False


def test_extra_financial_pool_is_bounded_prioritizes_missed_status_and_keeps_hard_gates():
    rows = [
        _row(
            code="600004",
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            quant_status="PRIORITY_RESEARCH",
        ),
        _row(
            code="600003",
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            quant_status="LOW_PRIORITY",
        ),
        _row(
            code="600002",
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            quant_status="HARD_REJECT",
        ),
        _row(
            code="600001",
            financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
            quant_status="HARD_REJECT",
            v31_hard_gate_failures="moat",
        ),
    ]
    selected, total = select_extra_financial_rows(rows, limit=2)
    assert total == 3
    assert [row["code"] for row in selected] == ["600002", "600003"]
    assert "600001" not in {row["code"] for row in selected}
