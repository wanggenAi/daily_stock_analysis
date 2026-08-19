from __future__ import annotations

from src.strategies.genge_opportunity_discovery.drawdown_risk_policy import DrawdownRiskPolicy
from src.strategies.genge_opportunity_discovery.formal_portfolio_allocator import (
    AllocationState,
    allocate_candidates,
)


def _row(code: str, industry: str, classification: str = "LONG_TERM_BUY_READY") -> dict[str, object]:
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "long_term_classification": classification,
        "long_term_formal_buy_eligible": True,
        "entry_low": 95.0,
        "entry_high": 105.0,
        "risk_invalidation_price": 90.0,
    }


def test_open_risk_cap_is_shared_across_candidates():
    rows = [_row(f"60000{i}", f"Industry{i}") for i in range(1, 7)]
    allocated = allocate_candidates(rows)

    assert [round(float(row["portfolio_allocated_pct"]), 4) for row in allocated[:4]] == [12.5] * 4
    assert round(float(allocated[4]["portfolio_allocated_pct"]), 4) == 10.0
    assert float(allocated[5]["portfolio_allocated_pct"]) == 0.0
    assert round(float(allocated[4]["portfolio_open_risk_pct_after"]), 6) == 6.0
    assert allocated[5]["portfolio_allocation_status"] == "NO_PORTFOLIO_RISK_CAPACITY"


def test_industry_cap_is_consumed_sequentially():
    rows = [_row(f"60001{i}", "SameIndustry") for i in range(1, 5)]
    allocated = allocate_candidates(rows)

    assert round(float(allocated[0]["portfolio_allocated_pct"]), 4) == 12.5
    assert round(float(allocated[1]["portfolio_allocated_pct"]), 4) == 12.5
    assert round(float(allocated[2]["portfolio_allocated_pct"]), 4) == 10.0
    assert float(allocated[3]["portfolio_allocated_pct"]) == 0.0
    assert round(float(allocated[2]["portfolio_industry_pct_after"]), 4) == 35.0


def test_try_position_uses_half_of_available_single_trade_budget():
    result = allocate_candidates([_row("600100", "A", "LONG_TERM_TRY_POSITION")])
    assert round(float(result[0]["portfolio_allocated_pct"]), 4) == 6.25


def test_hard_portfolio_drawdown_freezes_all_new_allocations():
    result = allocate_candidates(
        [_row("600101", "A")],
        state=AllocationState(portfolio_drawdown_pct=20.0),
    )
    assert float(result[0]["portfolio_allocated_pct"]) == 0.0
    assert result[0]["portfolio_allocation_status"] == "NO_PORTFOLIO_RISK_CAPACITY"


def test_total_gross_cap_keeps_cash_buffer_even_when_open_risk_is_relaxed():
    policy = DrawdownRiskPolicy(
        risk_per_trade_pct=5.0,
        max_total_open_risk_pct=100.0,
    )
    rows = [_row(f"60020{i}", f"I{i}") for i in range(1, 6)]
    allocated = allocate_candidates(rows, policy=policy)

    assert [round(float(row["portfolio_allocated_pct"]), 4) for row in allocated] == [20.0, 20.0, 20.0, 20.0, 10.0]
    assert round(float(allocated[-1]["portfolio_total_pct_after"]), 4) == 90.0
