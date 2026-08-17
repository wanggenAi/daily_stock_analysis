from types import SimpleNamespace

from src.strategies.genge_opportunity_discovery import all_a_industry_balanced
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


def test_all_a_fundamental_budget_requires_one_leader_per_industry(monkeypatch):
    rows = [
        _row("000001", "A", 1),
        _row("000002", "A", 2),
        _row("000003", "B", 3),
        _row("000004", "C", 4),
    ]
    captured = {}

    def fake_original(
        quant_rows,
        qfq_histories,
        config,
        *,
        priority_codes=(),
        required_codes=(),
    ):
        captured["fundamental_limit"] = config.fundamental_limit
        captured["priority_codes"] = set(priority_codes)
        captured["required_codes"] = set(required_codes)
        return [], {}

    monkeypatch.setattr(all_a_industry_balanced, "_ORIGINAL_FUNDAMENTALS", fake_original)
    config = SimpleNamespace(fundamental_limit=2)

    all_a_industry_balanced._balanced_fundamentals(
        rows,
        {},
        config,
        priority_codes=["000099"],
        required_codes=[],
    )

    assert captured["required_codes"] == {"000001", "000003", "000004"}
    assert {"000001", "000003", "000004"} <= captured["priority_codes"]
    assert captured["fundamental_limit"] == 5
    assert config.fundamental_limit == 2


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
