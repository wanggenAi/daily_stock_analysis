"""Scenario-based valuation odds diagnostics.

This module compares caller-supplied bear/base/bull equity values against a
verified current market cap.  It deliberately does not invent scenario
probabilities or an expected return.  Its purpose is to make cross-sector
asymmetry auditable: how much upside exists in the bull case, how much downside
exists in the bear case, and whether the base case provides a margin of safety.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ScenarioOddsResult:
    current_market_cap: Optional[float]
    bear_fair_equity_value: Optional[float]
    base_fair_equity_value: Optional[float]
    bull_fair_equity_value: Optional[float]
    bear_return: Optional[float]
    base_margin_of_safety: Optional[float]
    bull_return: Optional[float]
    downside_risk: Optional[float]
    upside_potential: Optional[float]
    upside_downside_ratio: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def compute_scenario_odds(
    *,
    current_market_cap: Any,
    bear_fair_equity_value: Any,
    base_fair_equity_value: Any,
    bull_fair_equity_value: Any,
) -> ScenarioOddsResult:
    """Compute raw scenario asymmetry without invented probabilities.

    ``base_margin_of_safety`` is the Base fair-value return versus today's
    market cap.  Positive means Base fair value exceeds the current market cap;
    negative means the current market already exceeds Base fair value.

    ``downside_risk`` clips Bear return at zero on the upside side.  Likewise
    ``upside_potential`` clips Bull return at zero on the downside side.

    If Bear fair value is at or above current market cap, the conventional
    upside/downside ratio has a zero denominator.  The function returns ``None``
    rather than infinity and labels the status explicitly.
    """

    current = _finite(current_market_cap)
    bear = _finite(bear_fair_equity_value)
    base = _finite(base_fair_equity_value)
    bull = _finite(bull_fair_equity_value)

    if current is None or current <= 0:
        return ScenarioOddsResult(
            current_market_cap=current,
            bear_fair_equity_value=bear,
            base_fair_equity_value=base,
            bull_fair_equity_value=bull,
            bear_return=None,
            base_margin_of_safety=None,
            bull_return=None,
            downside_risk=None,
            upside_potential=None,
            upside_downside_ratio=None,
            status="CURRENT_MARKET_CAP_UNAVAILABLE",
        )

    if bear is None or base is None or bull is None:
        return ScenarioOddsResult(
            current_market_cap=current,
            bear_fair_equity_value=bear,
            base_fair_equity_value=base,
            bull_fair_equity_value=bull,
            bear_return=None,
            base_margin_of_safety=None,
            bull_return=None,
            downside_risk=None,
            upside_potential=None,
            upside_downside_ratio=None,
            status="SCENARIO_VALUE_INCOMPLETE",
        )

    if min(bear, base, bull) < 0:
        return ScenarioOddsResult(
            current_market_cap=current,
            bear_fair_equity_value=bear,
            base_fair_equity_value=base,
            bull_fair_equity_value=bull,
            bear_return=None,
            base_margin_of_safety=None,
            bull_return=None,
            downside_risk=None,
            upside_potential=None,
            upside_downside_ratio=None,
            status="INVALID_NEGATIVE_SCENARIO_VALUE",
        )

    bear_return = bear / current - 1.0
    base_return = base / current - 1.0
    bull_return = bull / current - 1.0
    downside = max(0.0, -bear_return)
    upside = max(0.0, bull_return)

    if downside == 0:
        ratio = None
        status = "NO_BEAR_DOWNSIDE_RATIO_UNDEFINED"
    else:
        ratio = upside / downside
        status = "OK"

    return ScenarioOddsResult(
        current_market_cap=current,
        bear_fair_equity_value=bear,
        base_fair_equity_value=base,
        bull_fair_equity_value=bull,
        bear_return=bear_return,
        base_margin_of_safety=base_return,
        bull_return=bull_return,
        downside_risk=downside,
        upside_potential=upside,
        upside_downside_ratio=ratio,
        status=status,
    )
