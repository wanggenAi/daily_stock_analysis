"""R&D capitalization diagnostics for fundamental earnings-quality research.

Capitalized R&D is not automatically aggressive or improper.  The purpose of
this module is narrower: detect when changes in capitalization policy can make
period-to-period profit growth look stronger than underlying R&D economics.

The module therefore separates three questions:

1. What share of total R&D investment is capitalized?
2. Has that share changed materially versus a prior/baseline period?
3. How large is the capitalized amount relative to reported profit?

No profit restatement is produced unless the caller explicitly supplies a
normalization capitalization rate and, for after-tax net-profit adjustment, an
effective tax rate.  Missing assumptions remain missing rather than being
invented.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    top = _finite(numerator)
    bottom = _finite(denominator)
    if top is None or bottom is None or bottom == 0:
        return None
    value = top / bottom
    return value if math.isfinite(value) else None


@dataclass(frozen=True)
class RnDCapitalizationResult:
    total_r_and_d_investment: Optional[float]
    r_and_d_expense: Optional[float]
    capitalized_r_and_d: Optional[float]
    capitalization_rate: Optional[float]
    baseline_capitalization_rate: Optional[float]
    capitalization_rate_change: Optional[float]
    capitalized_r_and_d_to_net_profit: Optional[float]
    implied_reconciliation_gap: Optional[float]
    excess_capitalized_r_and_d_vs_baseline: Optional[float]
    after_tax_profit_adjustment: Optional[float]
    normalized_net_profit: Optional[float]
    earnings_quality_penalty: float
    confidence: str
    warning_flags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def assess_r_and_d_capitalization(
    *,
    total_r_and_d_investment: Any = None,
    r_and_d_expense: Any = None,
    capitalized_r_and_d: Any = None,
    net_profit: Any = None,
    baseline_capitalization_rate: Any = None,
    effective_tax_rate: Any = None,
) -> RnDCapitalizationResult:
    """Assess whether R&D capitalization materially affects earnings quality.

    ``baseline_capitalization_rate`` should come from an auditable historical or
    peer normalization assumption.  It is never inferred automatically.

    ``normalized_net_profit`` is only produced when both a baseline rate and a
    valid effective tax rate are provided.  This makes the adjustment an
    explicit scenario/stress test rather than an accounting restatement.
    """

    total = _finite(total_r_and_d_investment)
    expense = _finite(r_and_d_expense)
    capitalized = _finite(capitalized_r_and_d)
    profit = _finite(net_profit)
    baseline_rate = _finite(baseline_capitalization_rate)
    tax_rate = _finite(effective_tax_rate)

    warnings: List[str] = []
    confidence = "LOW"

    if capitalized is None and total is not None and expense is not None:
        derived = total - expense
        if derived >= 0:
            capitalized = derived
            warnings.append("capitalized_r_and_d_derived_from_total_less_expense")
            confidence = "MEDIUM"
    elif capitalized is not None:
        confidence = "HIGH"

    capitalization_rate = _safe_ratio(capitalized, total)
    profit_share = _safe_ratio(capitalized, profit)

    reconciliation_gap = None
    if total is not None and expense is not None and capitalized is not None:
        reconciliation_gap = total - expense - capitalized
        tolerance = max(abs(total) * 0.01, 1e-9)
        if abs(reconciliation_gap) > tolerance:
            warnings.append("r_and_d_reconciliation_gap_material")
            confidence = "LOW"

    rate_change = None
    excess_capitalized = None
    after_tax_adjustment = None
    normalized_profit = None

    if baseline_rate is not None:
        if not 0 <= baseline_rate <= 1:
            warnings.append("invalid_baseline_capitalization_rate")
            baseline_rate = None
        elif capitalization_rate is not None:
            rate_change = capitalization_rate - baseline_rate
            if total is not None and capitalized is not None:
                baseline_amount = total * baseline_rate
                excess_capitalized = max(0.0, capitalized - baseline_amount)

    if tax_rate is not None and not 0 <= tax_rate < 1:
        warnings.append("invalid_effective_tax_rate")
        tax_rate = None

    if excess_capitalized is not None and profit is not None and tax_rate is not None:
        after_tax_adjustment = excess_capitalized * (1.0 - tax_rate)
        normalized_profit = profit - after_tax_adjustment

    penalty = 0.0
    if capitalization_rate is None:
        warnings.append("r_and_d_capitalization_rate_unavailable")
    else:
        if capitalization_rate >= 0.30:
            penalty += 20.0
            warnings.append("r_and_d_capitalization_rate_high")
        elif capitalization_rate >= 0.20:
            penalty += 10.0
            warnings.append("r_and_d_capitalization_rate_elevated")

    if rate_change is not None:
        if rate_change >= 0.15:
            penalty += 25.0
            warnings.append("r_and_d_capitalization_rate_jump_large")
        elif rate_change >= 0.08:
            penalty += 15.0
            warnings.append("r_and_d_capitalization_rate_jump_material")

    if profit_share is not None:
        if profit_share >= 0.30:
            penalty += 25.0
            warnings.append("capitalized_r_and_d_large_vs_net_profit")
        elif profit_share >= 0.20:
            penalty += 15.0
            warnings.append("capitalized_r_and_d_material_vs_net_profit")
        elif profit_share >= 0.10:
            penalty += 7.0

    penalty = min(60.0, penalty)

    return RnDCapitalizationResult(
        total_r_and_d_investment=total,
        r_and_d_expense=expense,
        capitalized_r_and_d=capitalized,
        capitalization_rate=capitalization_rate,
        baseline_capitalization_rate=baseline_rate,
        capitalization_rate_change=rate_change,
        capitalized_r_and_d_to_net_profit=profit_share,
        implied_reconciliation_gap=reconciliation_gap,
        excess_capitalized_r_and_d_vs_baseline=excess_capitalized,
        after_tax_profit_adjustment=after_tax_adjustment,
        normalized_net_profit=normalized_profit,
        earnings_quality_penalty=penalty,
        confidence=confidence,
        warning_flags=sorted(set(warnings)),
    )
