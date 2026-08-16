"""Market-cap bridge for companies with multiple listed share classes.

For A/H or other dual-listed structures, multiplying one class's quote by total
company shares is only that class's *implied total equity value*, not the actual
consolidated market capitalization. Actual market cap requires each class's own
price plus an explicit FX conversion into a common reporting currency.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class ShareClassMarketCapResult:
    total_economic_shares: Optional[float]
    consolidated_market_cap: Optional[float]
    reference_class: Optional[str]
    reference_class_implied_total_equity_value: Optional[float]
    status: str
    classes: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_economic_shares": self.total_economic_shares,
            "consolidated_market_cap": self.consolidated_market_cap,
            "reference_class": self.reference_class,
            "reference_class_implied_total_equity_value": self.reference_class_implied_total_equity_value,
            "status": self.status,
            "classes": self.classes,
        }


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def aggregate_share_class_market_cap(
    share_classes: Mapping[str, Mapping[str, Any]],
    *,
    reference_class: Optional[str] = None,
) -> ShareClassMarketCapResult:
    """Aggregate actual class-level market values when all quote inputs exist.

    Each class accepts:
      - ``shares``: economic shares outstanding
      - ``price``: quote in that class's trading currency
      - ``fx_to_reporting_currency``: explicit conversion multiplier; use 1.0
        when quote currency already equals the reporting currency.

    Missing price or FX for any class makes consolidated market cap unavailable.
    If ``reference_class`` is supplied and its quote/FX are complete, the function
    also returns the value implied by applying that class's price to all economic
    shares. This is labelled separately and must not be called actual market cap.
    """

    if not share_classes:
        return ShareClassMarketCapResult(
            total_economic_shares=None,
            consolidated_market_cap=None,
            reference_class=reference_class,
            reference_class_implied_total_equity_value=None,
            status="SHARE_CLASSES_UNAVAILABLE",
            classes={},
        )

    rows: Dict[str, Dict[str, Any]] = {}
    total_shares = 0.0
    consolidated = 0.0
    incomplete_shares = False
    incomplete_quotes = False

    for name, raw in share_classes.items():
        shares = _finite(raw.get("shares"))
        price = _finite(raw.get("price"))
        fx = _finite(raw.get("fx_to_reporting_currency"))

        if shares is None or shares < 0:
            incomplete_shares = True
            class_value = None
            quote_status = "SHARES_UNAVAILABLE"
        else:
            total_shares += shares
            if price is None or price < 0 or fx is None or fx <= 0:
                incomplete_quotes = True
                class_value = None
                quote_status = "QUOTE_OR_FX_UNAVAILABLE"
            else:
                class_value = shares * price * fx
                consolidated += class_value
                quote_status = "OK"

        rows[str(name)] = {
            "shares": shares,
            "price": price,
            "fx_to_reporting_currency": fx,
            "market_cap_reporting_currency": class_value,
            "status": quote_status,
        }

    ref_implied = None
    if reference_class is not None and not incomplete_shares and total_shares > 0:
        ref = rows.get(reference_class)
        if ref is not None:
            price = _finite(ref.get("price"))
            fx = _finite(ref.get("fx_to_reporting_currency"))
            if price is not None and price >= 0 and fx is not None and fx > 0:
                ref_implied = total_shares * price * fx

    if incomplete_shares:
        status = "SHARE_COUNT_INCOMPLETE"
        actual = None
        total = None
    elif incomplete_quotes:
        status = "INCOMPLETE_SHARE_CLASS_PRICING"
        actual = None
        total = total_shares
    else:
        status = "OK"
        actual = consolidated
        total = total_shares

    return ShareClassMarketCapResult(
        total_economic_shares=total,
        consolidated_market_cap=actual,
        reference_class=reference_class,
        reference_class_implied_total_equity_value=ref_implied,
        status=status,
        classes=rows,
    )
