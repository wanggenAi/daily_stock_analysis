import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import (
    FINANCIAL_CACHE_KIND,
    _normalize_financial_frame,
)
from src.strategies.genge_opportunity_discovery.fundamental_valuation import normalize_core_earnings


def test_per_share_operating_cash_flow_is_not_used_as_total_cash_flow():
    raw = pd.DataFrame(
        [
            {
                "日期": "2025-12-31",
                "扣非净利润": 2_000_000_000,
                "每股经营性现金流": 1.2962,
            }
        ]
    )

    normalized = _normalize_financial_frame(raw)

    assert len(normalized) == 1
    assert normalized.iloc[0]["recurring_profit"] == 2_000_000_000
    assert pd.isna(normalized.iloc[0]["operating_cash_flow"])


def test_total_operating_cash_flow_is_preserved_when_provider_supplies_total_units():
    raw = pd.DataFrame(
        [
            {
                "报告期": "2025-12-31",
                "扣除非经常性损益后的净利润": 2_000_000_000,
                "经营活动产生的现金流量净额": 2_400_000_000,
                "每股经营性现金流": 1.2962,
            }
        ]
    )

    normalized = _normalize_financial_frame(raw)

    assert normalized.iloc[0]["operating_cash_flow"] == 2_400_000_000


def test_missing_total_cash_flow_does_not_create_microscopic_conversion_penalty():
    result = normalize_core_earnings(
        net_profit=None,
        recurring_profit=2_000_000_000,
        operating_cash_flow=None,
    )

    assert result.cash_conversion_ratio is None
    assert result.earnings_quality_score == 50.0
    assert result.earnings_quality_confidence == "MEDIUM"


def test_financial_cache_schema_does_not_reuse_legacy_unit_ambiguous_cache():
    assert FINANCIAL_CACHE_KIND != "financial"
    assert "cashflow_units" in FINANCIAL_CACHE_KIND
