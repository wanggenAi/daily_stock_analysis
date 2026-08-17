import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import (
    FINANCIAL_COLUMNS,
    PublicFundamentalLoader,
    _normalize_financial_frame,
)
from src.strategies.genge_opportunity_discovery.fundamental_valuation import (
    normalize_core_earnings,
)


def test_normalizes_reported_recurring_profit_without_cross_wiring_net_profit():
    raw = pd.DataFrame(
        {
            "日期": ["2025-12-31"],
            "扣除非经常性损益后的净利润(元)": [80.0],
            "净利润": [100.0],
            "经营活动产生的现金流量净额": [90.0],
        }
    )

    normalized = _normalize_financial_frame(raw)

    assert list(normalized.columns) == list(FINANCIAL_COLUMNS)
    assert normalized.loc[0, "net_profit"] == 100.0
    assert normalized.loc[0, "recurring_profit"] == 80.0


def test_recurring_profit_does_not_match_growth_rate_column():
    raw = pd.DataFrame(
        {
            "日期": ["2025-12-31"],
            "净利润": [100.0],
            "扣非净利润同比增长(%)": [23.5],
        }
    )

    normalized = _normalize_financial_frame(raw)

    assert normalized.loc[0, "net_profit"] == 100.0
    assert pd.isna(normalized.loc[0, "recurring_profit"])


def test_old_financial_cache_is_forward_compatible_with_recurring_profit(tmp_path):
    cache_path = tmp_path / "financial" / "600519.csv"
    cache_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "report_date": ["2025-12-31"],
            "disclosure_date": ["2026-03-31"],
            "debt_ratio": [20.0],
            "net_profit": [100.0],
            "operating_cash_flow": [110.0],
            "roe": [30.0],
            "gross_margin": [90.0],
        }
    ).to_csv(cache_path, index=False)

    loader = PublicFundamentalLoader(cache_dir=tmp_path)
    frame, provider, errors, cache_hit = loader.load_financial("600519", years=5)

    assert cache_hit is True
    assert provider == "cache"
    assert errors == []
    assert frame is not None
    assert list(frame.columns) == list(FINANCIAL_COLUMNS)
    assert pd.isna(frame.loc[0, "recurring_profit"])


def test_normalized_recurring_profit_drives_core_earnings_method():
    raw = pd.DataFrame(
        {
            "日期": ["2025-12-31"],
            "净利润": [100.0],
            "扣除非经常性损益后的净利润(元)": [82.0],
            "经营活动产生的现金流量净额": [90.0],
        }
    )
    row = _normalize_financial_frame(raw).iloc[0]

    core = normalize_core_earnings(
        net_profit=row["net_profit"],
        recurring_profit=row["recurring_profit"],
        operating_cash_flow=row["operating_cash_flow"],
    )

    assert core.normalized_core_operating_profit == 82.0
    assert core.normalization_method == "REPORTED_RECURRING_PROFIT"
    assert core.earnings_quality_confidence == "HIGH"
