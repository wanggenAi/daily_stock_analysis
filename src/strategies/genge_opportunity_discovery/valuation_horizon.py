"""Time-horizon semantics for forward and terminal valuation.

A future-year profit multiplied by a terminal PE is a value at that future
horizon, not automatically today's fair equity value.  This module keeps two
semantics explicit:

* ``CURRENT_FORWARD_PE``: a market multiple quoted today on a specified future
  earnings estimate.  No extra discounting is applied because the multiple is
  already a current-price / future-earnings convention.
* ``TERMINAL_PE``: an equity value assumed to exist at a future horizon.  It
  must be discounted back to the analysis date using an explicit required
  return.

The module is pure and fail-closed.  It never invents a required return, a
terminal multiple, or a growth horizon.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional


CURRENT_FORWARD_PE = "CURRENT_FORWARD_PE"
TERMINAL_PE = "TERMINAL_PE"


@dataclass(frozen=True)
class HorizonValuationResult:
    profit: Optional[float]
    pe_multiple: Optional[float]
    horizon_years: Optional[float]
    required_return: Optional[float]
    multiple_semantics: str
    horizon_equity_value: Optional[float]
    present_equity_value: Optional[float]
    discount_factor: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RequiredTerminalProfitResult:
    current_market_cap: Optional[float]
    terminal_pe: Optional[float]
    horizon_years: Optional[float]
    required_return: Optional[float]
    required_terminal_equity_value: Optional[float]
    required_terminal_profit: Optional[float]
    current_normalized_profit: Optional[float]
    required_profit_cagr: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def value_profit_at_horizon(
    *,
    profit: Any,
    pe_multiple: Any,
    horizon_years: Any = 0,
    required_return: Any = None,
    multiple_semantics: str = CURRENT_FORWARD_PE,
) -> HorizonValuationResult:
    earnings = _finite(profit)
    multiple = _finite(pe_multiple)
    years = _finite(horizon_years)
    hurdle = _finite(required_return)

    if earnings is None or earnings <= 0:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            None, None, None, "PROFIT_UNAVAILABLE_OR_NONPOSITIVE"
        )
    if multiple is None or multiple <= 0:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            None, None, None, "MULTIPLE_UNAVAILABLE_OR_NONPOSITIVE"
        )
    if years is None or years < 0:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            None, None, None, "INVALID_HORIZON"
        )

    horizon_value = earnings * multiple

    if multiple_semantics == CURRENT_FORWARD_PE:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            horizon_value, horizon_value, 1.0, "OK_CURRENT_FORWARD_MULTIPLE"
        )

    if multiple_semantics != TERMINAL_PE:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            horizon_value, None, None, "UNKNOWN_MULTIPLE_SEMANTICS"
        )

    if years == 0:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            horizon_value, horizon_value, 1.0, "OK_TERMINAL_AT_PRESENT"
        )
    if hurdle is None or hurdle <= -1:
        return HorizonValuationResult(
            earnings, multiple, years, hurdle, multiple_semantics,
            horizon_value, None, None, "REQUIRED_RETURN_REQUIRED"
        )

    discount_factor = 1.0 / ((1.0 + hurdle) ** years)
    present_value = horizon_value * discount_factor
    return HorizonValuationResult(
        earnings,
        multiple,
        years,
        hurdle,
        multiple_semantics,
        horizon_value,
        present_value,
        discount_factor,
        "OK_TERMINAL_DISCOUNTED",
    )


def required_terminal_profit(
    *,
    current_market_cap: Any,
    terminal_pe: Any,
    horizon_years: Any,
    required_return: Any,
    current_normalized_profit: Any = None,
) -> RequiredTerminalProfitResult:
    market_cap = _finite(current_market_cap)
    multiple = _finite(terminal_pe)
    years = _finite(horizon_years)
    hurdle = _finite(required_return)
    current_profit = _finite(current_normalized_profit)

    if market_cap is None or market_cap <= 0:
        status = "MARKET_CAP_UNAVAILABLE"
    elif multiple is None or multiple <= 0:
        status = "TERMINAL_MULTIPLE_UNAVAILABLE"
    elif years is None or years < 0:
        status = "INVALID_HORIZON"
    elif hurdle is None or hurdle <= -1:
        status = "REQUIRED_RETURN_REQUIRED"
    else:
        terminal_value = market_cap * ((1.0 + hurdle) ** years)
        terminal_profit = terminal_value / multiple
        cagr = None
        if current_profit is not None and current_profit > 0 and years > 0:
            cagr = (terminal_profit / current_profit) ** (1.0 / years) - 1.0
        return RequiredTerminalProfitResult(
            market_cap,
            multiple,
            years,
            hurdle,
            terminal_value,
            terminal_profit,
            current_profit,
            cagr,
            "OK",
        )

    return RequiredTerminalProfitResult(
        market_cap,
        multiple,
        years,
        hurdle,
        None,
        None,
        current_profit,
        None,
        status,
    )
