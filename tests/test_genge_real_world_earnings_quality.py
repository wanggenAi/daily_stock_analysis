import pytest

from src.strategies.genge_opportunity_discovery.fundamental_valuation import (
    normalize_core_earnings,
)


def test_jiangfeng_h1_preview_does_not_promote_headline_profit_to_core_earnings():
    """Live 2026H1 preview calibration for 300666 江丰电子.

    Midpoint values are expressed in RMB 100m units.  The public preview showed
    headline attributable profit of 4.8-5.6 while recurring attributable profit
    was only 1.8-2.3, with about 3.0-3.3 of non-recurring gains.  The valuation
    layer must anchor sustainable earnings to the recurring figure rather than
    annualising headline profit.
    """

    result = normalize_core_earnings(
        net_profit=5.20,
        recurring_profit=2.05,
    )

    assert result.normalized_core_operating_profit == pytest.approx(2.05)
    assert result.normalization_method == "REPORTED_RECURRING_PROFIT"
    assert result.recurring_profit_ratio == pytest.approx(2.05 / 5.20)
    assert result.non_recurring_profit_share == pytest.approx(1.0 - 2.05 / 5.20)
    assert result.non_recurring_profit_share > 0.60
    assert result.earnings_quality_score < 30
    assert result.earnings_quality_confidence == "MEDIUM"
