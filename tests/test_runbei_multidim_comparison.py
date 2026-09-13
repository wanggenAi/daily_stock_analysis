from __future__ import annotations

import json

from src.strategies.genge_opportunity_discovery.runbei_multidim_comparison import (
    build_comparison,
    render_markdown,
    validate_contracts,
)


def _archetype():
    return {
        "archetype_id": "RUNBEI_001316_20260826_V1",
        "reference": {"code": "001316"},
        "features": [
            {
                "id": "earnings_quality_score",
                "aliases": ["earnings_quality_score"],
                "reference_value": 65,
                "tolerance": 65,
                "weight": 20,
                "mode": "at_least",
            },
            {
                "id": "cash_conversion_ratio",
                "aliases": ["cash_conversion_ratio"],
                "reference_value": 3.81,
                "tolerance": 4,
                "weight": 15,
                "mode": "proximity",
            },
            {
                "id": "net_profit_yoy_pct",
                "aliases": ["net_profit_yoy_pct"],
                "reference_value": 27.86,
                "tolerance": 35,
                "weight": 25,
                "mode": "at_least",
            },
            {
                "id": "recurring_profit_yoy_pct",
                "aliases": ["recurring_profit_yoy_pct"],
                "reference_value": 39.16,
                "tolerance": 45,
                "weight": 25,
                "mode": "at_least",
            },
            {
                "id": "operating_cash_flow_yoy_pct",
                "aliases": ["operating_cash_flow_yoy_pct"],
                "reference_value": 46.97,
                "tolerance": 80,
                "weight": 15,
                "mode": "at_least",
            },
        ],
    }


def _scorecard():
    dimensions = [
        ("long_term_demand", 10),
        ("moat_and_direction", 20),
        ("earnings_quality", 10),
        ("roic_incremental_roic", 10),
        ("management_capital_allocation", 8),
        ("growth_runway", 10),
        ("normalized_earnings_certainty", 7),
        ("market_expectation_gap", 8),
        ("valuation_margin_of_safety", 12),
        ("market_position", 5),
    ]
    return {
        "authority": "RESEARCH_ONLY",
        "hard_gates": ["predictability", "financial_safety", "earnings_authenticity"],
        "dimensions": [
            {"id": dimension_id, "label": dimension_id, "weight": weight}
            for dimension_id, weight in dimensions
        ],
        "rules": {
            "unknown_is_pass": False,
            "similarity_can_create_formal_buy": False,
            "no_auto_trade": True,
        },
    }


def _row(code: str, similarity: float, state: str = "ARCHETYPE_MATCH"):
    feature_scores = {
        "earnings_quality_score": 20.0,
        "cash_conversion_ratio": 10.5,
        "net_profit_yoy_pct": 25.0,
        "recurring_profit_yoy_pct": 20.0,
        "operating_cash_flow_yoy_pct": 10.4134,
    }
    feature_sources = {
        "earnings_quality_score": "earnings_quality_score",
        "cash_conversion_ratio": "cash_conversion_ratio",
        "net_profit_yoy_pct": "net_profit_yoy_pct",
        "recurring_profit_yoy_pct": "recurring_profit_yoy_pct",
        "operating_cash_flow_yoy_pct": "operating_cash_flow_yoy_pct",
    }
    return {
        "code": code,
        "stock_name": "候选" + code,
        "success_archetype_state": state,
        "success_archetype_similarity_score": str(similarity),
        "success_archetype_evidence_coverage": "1.0",
        "success_archetype_feature_scores_json": json.dumps(feature_scores),
        "success_archetype_feature_sources_json": json.dumps(feature_sources),
        "earnings_quality_score": "70",
        "cash_conversion_ratio": "2.61",
        "net_profit_yoy_pct": "35",
        "recurring_profit_yoy_pct": "30",
        "operating_cash_flow_yoy_pct": "40",
        "quant_status": "PRIORITY_RESEARCH",
        "quant_rank": "3",
        "quant_score": "77.5",
        "terminal_decision": "WAIT_PRICE",
        "terminal_current_price": "9.18",
        "wait_price_max": "8.80",
        "neutral_value": "10.17",
    }


def test_exposes_runbei_five_feature_breakdown_and_keeps_research_only():
    payload = build_comparison(
        [_row("000526", 85.9134), _row("603055", 73.81)],
        archetype=_archetype(),
        scorecard=_scorecard(),
        source_recall_run_id="12345",
    )

    assert payload["authority"] == "RESEARCH_ONLY"
    assert payload["formal_action_eligible"] is False
    assert payload["unknown_is_pass"] is False
    assert payload["no_auto_trade"] is True
    assert payload["rows"][0]["code"] == "000526"
    assert payload["rows"][0]["runbei_similarity_score"] == 85.9134
    assert payload["rows"][0]["runbei_feature_points"]["earnings_quality_score"] == 20.0
    assert payload["rows"][0]["runbei_feature_raw_values"]["cash_conversion_ratio"] == 2.61
    assert len(payload["rows"][0]["runbei_features"]) == 5


def test_missing_v31_dimensions_remain_unknown_instead_of_being_fabricated():
    payload = build_comparison(
        [_row("603055", 73.81)],
        archetype=_archetype(),
        scorecard=_scorecard(),
    )
    row = payload["rows"][0]

    assert row["v31_multidim_complete"] is False
    assert row["v31_multidim_score"] is None
    assert row["hard_gate_unknown"] is True
    assert all(item["points"] is None for item in row["v31_dimensions"])
    assert all(item["provenance"] == "UNKNOWN_NOT_PERSISTED" for item in row["v31_dimensions"])


def test_explicit_multidim_scores_are_only_totalled_when_all_ten_are_persisted():
    row = _row("603055", 73.81)
    dimensions = _scorecard()["dimensions"]
    row["v31_multidim_scores_json"] = json.dumps(
        {item["id"]: float(item["weight"]) for item in dimensions}
    )
    row["predictability_status"] = "PASS"
    row["financial_safety_status"] = "PASS"
    row["earnings_authenticity_status"] = "PASS"
    row["long_term_demand_status"] = "PASS"
    row["moat_status"] = "PASS"

    payload = build_comparison(
        [row], archetype=_archetype(), scorecard=_scorecard()
    )
    result = payload["rows"][0]

    assert result["v31_multidim_complete"] is True
    assert result["v31_multidim_score"] == 100.0
    assert result["hard_gate_failed"] is False
    assert result["hard_gate_unknown"] is False


def test_confirmed_gate_failure_is_never_hidden_by_high_similarity():
    strong = _row("002120", 92.0)
    strong["v31_hard_gate_failures"] = "predictability"
    weaker = _row("603055", 73.81)

    payload = build_comparison(
        [strong, weaker], archetype=_archetype(), scorecard=_scorecard()
    )

    assert payload["rows"][0]["code"] == "603055"
    failed = next(row for row in payload["rows"] if row["code"] == "002120")
    assert failed["hard_gates"]["predictability"] == "FAIL"
    assert failed["hard_gate_failed"] is True
    assert failed["formal_action_eligible"] is False


def test_markdown_makes_similarity_and_multidim_semantics_visible():
    payload = build_comparison(
        [_row("000526", 85.9134)],
        archetype=_archetype(),
        scorecard=_scorecard(),
    )
    text = render_markdown(payload)

    assert "润贝相似度" in text
    assert "earnings_quality_score" in text
    assert "100分多维" in text
    assert "UNKNOWN != PASS" in text
    assert "不是 Formal BUY 清单" in text


def test_scorecard_contract_rejects_authority_relaxation():
    scorecard = _scorecard()
    scorecard["rules"]["unknown_is_pass"] = True

    try:
        validate_contracts(_archetype(), scorecard)
    except ValueError as exc:
        assert "UNKNOWN != PASS" in str(exc)
    else:
        raise AssertionError("unsafe scorecard must fail closed")
