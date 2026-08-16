"""Diagnostics for separating recurring equity earnings from financial-asset income.

When a valuation model multiplies a recurring/net-profit figure by a PE-like
multiple and then adds net cash / financial assets, it can double count income
already earned by those financial assets. This module provides a conservative,
data-conditional bridge for callers that want an asset-adjusted equity value.

The module does not guess tax rates, financing costs, or financial-asset yields.
Missing inputs remain missing.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Optional


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class FinancialIncomeBridgeResult:
    normalized_equity_profit: Optional[float]
    interest_income: Optional[float]
    interest_expense: Optional[float]
    recurring_investment_income: Optional[float]
    effective_tax_rate: Optional[float]
    after_tax_financial_income_removed: Optional[float]
    after_tax_financing_cost_added_back: Optional[float]
    asset_bridge_profit: Optional[float]
    status: str
    warning_flags: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def normalize_profit_for_financial_asset_bridge(
    *,
    normalized_equity_profit: Any,
    interest_income: Any = None,
    interest_expense: Any = None,
    recurring_investment_income: Any = None,
    effective_tax_rate: Any = None,
) -> FinancialIncomeBridgeResult:
    """Remove/add back explicit financing items before separately valuing net cash.

    This function is appropriate only when the caller intends to value operating
    earnings and then *separately* add/subtract verified non-operating financial
    assets/debt. If the caller uses a plain equity PE on reported/recurring net
    profit without a separate net-cash bridge, this adjustment is unnecessary.

    Calculation when all required inputs are available::

        after_tax_financial_income_removed =
            (interest_income + recurring_investment_income) * (1 - tax_rate)

        after_tax_financing_cost_added_back =
            interest_expense * (1 - tax_rate)

        asset_bridge_profit = normalized_equity_profit
            - after_tax_financial_income_removed
            + after_tax_financing_cost_added_back

    Only explicitly supplied interest/investment items are adjusted. FX gains,
    fair-value gains, and other finance-line components are not guessed.
    """

    profit = _finite(normalized_equity_profit)
    income = _finite(interest_income)
    expense = _finite(interest_expense)
    investment = _finite(recurring_investment_income)
    tax = _finite(effective_tax_rate)
    warnings: list[str] = []

    if profit is None:
        return FinancialIncomeBridgeResult(
            normalized_equity_profit=None,
            interest_income=income,
            interest_expense=expense,
            recurring_investment_income=investment,
            effective_tax_rate=tax,
            after_tax_financial_income_removed=None,
            after_tax_financing_cost_added_back=None,
            asset_bridge_profit=None,
            status="EQUITY_PROFIT_UNAVAILABLE",
            warning_flags=("missing_normalized_equity_profit",),
        )

    if tax is None or not 0 <= tax < 1:
        return FinancialIncomeBridgeResult(
            normalized_equity_profit=profit,
            interest_income=income,
            interest_expense=expense,
            recurring_investment_income=investment,
            effective_tax_rate=tax,
            after_tax_financial_income_removed=None,
            after_tax_financing_cost_added_back=None,
            asset_bridge_profit=None,
            status="TAX_RATE_REQUIRED_FOR_ASSET_BRIDGE",
            warning_flags=("missing_or_invalid_effective_tax_rate",),
        )

    if income is None and expense is None and investment is None:
        return FinancialIncomeBridgeResult(
            normalized_equity_profit=profit,
            interest_income=None,
            interest_expense=None,
            recurring_investment_income=None,
            effective_tax_rate=tax,
            after_tax_financial_income_removed=None,
            after_tax_financing_cost_added_back=None,
            asset_bridge_profit=None,
            status="FINANCIAL_INCOME_DETAIL_REQUIRED",
            warning_flags=("financial_income_components_unverified",),
        )

    gross_income_to_remove = (income or 0.0) + (investment or 0.0)
    gross_cost_to_add_back = expense or 0.0
    after_tax_income = gross_income_to_remove * (1.0 - tax)
    after_tax_cost = gross_cost_to_add_back * (1.0 - tax)
    asset_bridge_profit = profit - after_tax_income + after_tax_cost

    if income is None:
        warnings.append("interest_income_missing_treated_as_zero")
    if expense is None:
        warnings.append("interest_expense_missing_treated_as_zero")
    if investment is None:
        warnings.append("recurring_investment_income_missing_treated_as_zero")
    if asset_bridge_profit <= 0:
        warnings.append("asset_bridge_profit_non_positive")

    return FinancialIncomeBridgeResult(
        normalized_equity_profit=profit,
        interest_income=income,
        interest_expense=expense,
        recurring_investment_income=investment,
        effective_tax_rate=tax,
        after_tax_financial_income_removed=after_tax_income,
        after_tax_financing_cost_added_back=after_tax_cost,
        asset_bridge_profit=asset_bridge_profit,
        status="OK",
        warning_flags=tuple(warnings),
    )
