"""Primary-equity financing dilution bridge.

A financing issuance is economically different from incentive/zero-proceeds
share dilution because new shares normally bring cash into the company. Forward
per-share valuation must therefore bridge both the new denominator and verified
net financing proceeds.

The module is intentionally conservative: if financing shares are assumed but
net proceeds (or an issue price from which proceeds can be derived) are unknown,
it does not invent a diluted fair price.
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
class FinancingDilutionResult:
    pre_financing_equity_value: Optional[float]
    current_shares: Optional[float]
    financing_shares: Optional[float]
    issue_price: Optional[float]
    explicit_net_proceeds: Optional[float]
    derived_gross_proceeds: Optional[float]
    financing_costs: Optional[float]
    net_proceeds_used: Optional[float]
    post_financing_equity_value: Optional[float]
    post_financing_shares: Optional[float]
    pre_financing_fair_price: Optional[float]
    post_financing_fair_price: Optional[float]
    per_share_impact: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def bridge_primary_financing_dilution(
    *,
    pre_financing_equity_value: Any,
    current_shares: Any,
    financing_shares: Any,
    net_proceeds: Any = None,
    issue_price: Any = None,
    financing_costs: Any = None,
) -> FinancingDilutionResult:
    """Bridge primary financing into post-issue equity value and fair price.

    Net proceeds can be supplied directly. Otherwise they are derived from
    ``financing_shares * issue_price - financing_costs``. This calculation only
    recognizes cash entering the company; it does not assume future ROIC or
    earnings uplift from deployment of the proceeds.
    """

    value = _finite(pre_financing_equity_value)
    current = _finite(current_shares)
    new_shares = _finite(financing_shares)
    explicit_proceeds = _finite(net_proceeds)
    price = _finite(issue_price)
    costs = _finite(financing_costs)

    pre_price = None
    if value is not None and current is not None and current > 0:
        pre_price = value / current

    common = dict(
        pre_financing_equity_value=value,
        current_shares=current,
        financing_shares=new_shares,
        issue_price=price,
        explicit_net_proceeds=explicit_proceeds,
        financing_costs=costs,
        pre_financing_fair_price=pre_price,
    )

    if value is None or value < 0:
        return FinancingDilutionResult(
            **common,
            derived_gross_proceeds=None,
            net_proceeds_used=None,
            post_financing_equity_value=None,
            post_financing_shares=None,
            post_financing_fair_price=None,
            per_share_impact=None,
            status="EQUITY_VALUE_UNAVAILABLE",
        )
    if current is None or current <= 0:
        return FinancingDilutionResult(
            **common,
            derived_gross_proceeds=None,
            net_proceeds_used=None,
            post_financing_equity_value=None,
            post_financing_shares=None,
            post_financing_fair_price=None,
            per_share_impact=None,
            status="CURRENT_SHARE_COUNT_UNAVAILABLE",
        )
    if new_shares is None or new_shares < 0:
        return FinancingDilutionResult(
            **common,
            derived_gross_proceeds=None,
            net_proceeds_used=None,
            post_financing_equity_value=None,
            post_financing_shares=None,
            post_financing_fair_price=None,
            per_share_impact=None,
            status="FINANCING_SHARE_COUNT_UNAVAILABLE",
        )

    gross = None
    proceeds_used = explicit_proceeds
    if proceeds_used is None and price is not None and price >= 0:
        gross = new_shares * price
        cost_value = costs or 0.0
        proceeds_used = gross - cost_value
    elif price is not None and price >= 0:
        gross = new_shares * price

    if new_shares > 0 and proceeds_used is None:
        return FinancingDilutionResult(
            **common,
            derived_gross_proceeds=gross,
            net_proceeds_used=None,
            post_financing_equity_value=None,
            post_financing_shares=current + new_shares,
            post_financing_fair_price=None,
            per_share_impact=None,
            status="FINANCING_PROCEEDS_REQUIRED",
        )
    if proceeds_used is not None and proceeds_used < 0:
        return FinancingDilutionResult(
            **common,
            derived_gross_proceeds=gross,
            net_proceeds_used=proceeds_used,
            post_financing_equity_value=None,
            post_financing_shares=current + new_shares,
            post_financing_fair_price=None,
            per_share_impact=None,
            status="INVALID_NEGATIVE_NET_PROCEEDS",
        )

    proceeds_used = proceeds_used or 0.0
    post_value = value + proceeds_used
    post_shares = current + new_shares
    post_price = post_value / post_shares
    impact = post_price / pre_price - 1.0 if pre_price not in (None, 0) else None

    return FinancingDilutionResult(
        **common,
        derived_gross_proceeds=gross,
        net_proceeds_used=proceeds_used,
        post_financing_equity_value=post_value,
        post_financing_shares=post_shares,
        post_financing_fair_price=post_price,
        per_share_impact=impact,
        status="OK",
    )
