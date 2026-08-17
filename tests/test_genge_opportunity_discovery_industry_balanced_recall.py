from src.strategies.genge_opportunity_discovery import valuation_research_industry_balanced
from src.strategies.genge_opportunity_discovery.industry_balanced_recall import (
    IndustryRecallPolicy,
    coverage_audit,
    select_industry_balanced_rows,
)


def _row(
    code: str,
    industry: str,
    rank: int,
    *,
    score: float | None = None,
    status: str = "PRIORITY_RESEARCH",
    hard: str = "",
):
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "quant_rank": rank,
        "quant_score": float(100 - rank) if score is None else score,
        "quant_status": status,
        "hard_blockers": hard,
    }


def test_industry_balanced_recall_preserves_global_seed_and_every_industry():
    rows = [
        _row("000001", "A", 1),
        _row("000002", "A", 2),
        _row("000003", "A", 3),
        _row("000004", "A", 4),
        _row("000005", "B", 5),
        _row("000006", "B", 6),
        _row("000007", "C", 7, status="SECONDARY_RESEARCH"),
        _row("000008", "D", 8, status="LOW_PRIORITY"),
    ]

    selected = select_industry_balanced_rows(
        rows,
        policy=IndustryRecallPolicy(
            total_limit=7,
            global_seed=3,
            per_industry_target=2,
        ),
    )

    codes = {row["code"] for row in selected}
    assert {"000001", "000002", "000003"} <= codes
    assert {row["industry"] for row in selected} == {"A", "B", "C", "D"}
    assert any(
        row["industry"] == "D" and row["industry_recall_guaranteed"]
        for row in selected
    )
    audit = coverage_audit(rows, selected)
    assert audit["all_eligible_industries_covered"] is True
    assert audit["eligible_industry_count"] == 4
    assert audit["covered_industry_count"] == 4


def test_capacity_target_cannot_delete_an_eligible_industry():
    rows = [
        _row("000001", "A", 1),
        _row("000002", "B", 2),
        _row("000003", "C", 3),
        _row("000004", "D", 4),
    ]

    selected = select_industry_balanced_rows(
        rows,
        policy=IndustryRecallPolicy(
            total_limit=2,
            global_seed=1,
            per_industry_target=1,
        ),
    )

    assert len(selected) == 4
    assert {row["industry"] for row in selected} == {"A", "B", "C", "D"}


def test_per_industry_target_union_can_exceed_capacity_floor():
    rows = [
        _row("000001", "A", 1),
        _row("000002", "A", 2),
        _row("000003", "A", 3),
        _row("000004", "B", 4),
        _row("000005", "B", 5),
        _row("000006", "B", 6),
    ]

    selected = select_industry_balanced_rows(
        rows,
        policy=IndustryRecallPolicy(
            total_limit=2,
            global_seed=1,
            per_industry_target=3,
        ),
    )

    assert len(selected) == 6
    assert {row["code"] for row in selected} == {
        "000001", "000002", "000003", "000004", "000005", "000006"
    }


def test_true_hard_reject_is_never_revived_for_industry_coverage():
    rows = [
        _row("000001", "SAFE", 1),
        _row(
            "000002",
            "ALL_HARD",
            2,
            status="HARD_REJECT",
            hard="serious_financial_anomaly",
        ),
        _row(
            "000003",
            "MIXED",
            3,
            status="HARD_REJECT",
            hard="delisting_risk",
        ),
        _row("000004", "MIXED", 4, status="LOW_PRIORITY"),
    ]

    selected = select_industry_balanced_rows(
        rows,
        policy=IndustryRecallPolicy(
            total_limit=20,
            global_seed=10,
            per_industry_target=3,
        ),
    )

    codes = {row["code"] for row in selected}
    assert "000002" not in codes
    assert "000003" not in codes
    assert "000004" in codes
    audit = coverage_audit(rows, selected)
    assert "ALL_HARD" not in audit["eligible_industries"]
    assert audit["hard_reject_revival_allowed"] is False


def test_valuation_recall_can_recover_only_explicitly_relaxable_technical_rows():
    rows = [
        _row("000001", "NORMAL", 1),
        _row(
            "000002",
            "TECHNICAL_RECOVERY",
            2,
            status="HARD_REJECT",
            hard="price_too_high",
        ),
        _row(
            "000003",
            "TRUE_HARD",
            3,
            status="HARD_REJECT",
            hard="serious_financial_anomaly",
        ),
    ]

    selected = valuation_research_industry_balanced._balanced_select(
        rows,
        research_limit=10,
        relaxed_reserve=1,
    )

    codes = {row["code"] for row in selected}
    assert "000001" in codes
    assert "000002" in codes
    assert "000003" not in codes
    technical = next(row for row in selected if row["code"] == "000002")
    assert technical["wide_recall_reason"] == "RELAXABLE_TECHNICAL_RECOVERY"
    assert technical["industry_recall_guaranteed"] is True


def test_valuation_protected_top3_ranks_recovered_technical_row_by_quant_merit():
    rows = [
        _row(
            "000001",
            "SAME_INDUSTRY",
            1,
            status="HARD_REJECT",
            hard="price_too_high",
        ),
        _row("000002", "SAME_INDUSTRY", 2),
        _row("000003", "SAME_INDUSTRY", 3),
        _row("000004", "SAME_INDUSTRY", 4),
    ]

    selected = valuation_research_industry_balanced._balanced_select(
        rows,
        research_limit=4,
        relaxed_reserve=1,
    )
    by_code = {row["code"]: row for row in selected}

    assert by_code["000001"]["wide_recall_reason"] == (
        "RELAXABLE_TECHNICAL_RECOVERY"
    )
    assert by_code["000001"]["industry_recall_rank"] == 1
    assert by_code["000002"]["industry_recall_rank"] == 2
    assert by_code["000003"]["industry_recall_rank"] == 3
    assert by_code["000004"]["industry_recall_rank"] == ""


def test_valuation_financial_review_keeps_global_budget_plus_industry_leaders():
    rows = [
        {
            **_row("000001", "A", 1),
            "valuation_diagnostic_status": "OK",
            "required_profit_growth_vs_reference": 0.1,
        },
        {
            **_row("000002", "A", 2),
            "valuation_diagnostic_status": "OK",
            "required_profit_growth_vs_reference": 0.2,
        },
        {
            **_row("000003", "B", 3),
            "valuation_diagnostic_status": "OK",
            "required_profit_growth_vs_reference": 0.3,
        },
        {
            **_row("000004", "C", 4),
            "valuation_diagnostic_status": "OK",
            "required_profit_growth_vs_reference": 0.4,
        },
        {
            **_row("000005", "D", 5),
            "valuation_diagnostic_status": "PE_MODEL_NOT_APPLICABLE",
        },
    ]

    codes = valuation_research_industry_balanced._financial_review_codes(
        rows,
        global_limit=1,
    )

    assert codes == ["000001", "000003", "000004"]
