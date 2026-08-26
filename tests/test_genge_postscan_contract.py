from src.strategies.genge_opportunity_discovery.postscan_contract import (
    execution_eligible_rows,
    unresolved_execution_gaps,
)


def test_research_only_unresolved_valuation_does_not_block_production_zero_buy():
    rows = [
        {
            "code": "688739",
            "long_term_blockers": "valuation_model_not_executed;valuation_diagnostic_not_ready",
        }
    ]
    assert execution_eligible_rows(rows) == []
    assert unresolved_execution_gaps(rows) == []


def test_execution_eligible_unresolved_valuation_still_blocks_production_zero_buy():
    rows = [
        {
            "code": "603658",
            "long_term_blockers": "valuation_model_not_executed;valuation_diagnostic_not_ready",
        }
    ]
    assert [row["code"] for row in execution_eligible_rows(rows)] == ["603658"]
    assert unresolved_execution_gaps(rows) == [
        "valuation_diagnostic_not_ready",
        "valuation_model_not_executed",
    ]
