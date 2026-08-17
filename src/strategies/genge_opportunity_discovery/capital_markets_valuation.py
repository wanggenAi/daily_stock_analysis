"""Valuation primitives for securities brokers and broker/platform hybrids.

The securities industry is not one homogeneous valuation archetype:

* a traditional balance-sheet-heavy broker is naturally anchored to common
  book value and a *mid-cycle* sustainable ROE;
* an internet broker / financial-data / fund-distribution platform may contain
  an asset-light franchise that should not be forced into the same P/B model.

This module therefore exposes two explicit paths and deliberately does not
perform automatic classification from arbitrary revenue-share thresholds.
Callers must choose the business model from point-in-time evidence.

No function creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class TraditionalBrokerValuationResult:
    common_bvps: Optional[float]
    normalized_mid_cycle_roe: Optional[float]
    cost_of_equity: Optional[float]
    long_term_growth: Optional[float]
    fair_common_pb: Optional[float]
    fair_price: Optional[float]
    current_price: Optional[float]
    current_common_pb: Optional[float]
    implied_mid_cycle_roe: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class HybridBrokerPlatformSOTPResult:
    normalized_broker_profit: Optional[float]
    broker_fair_multiple: Optional[float]
    broker_value: Optional[float]
    normalized_platform_profit: Optional[float]
    platform_fair_multiple: Optional[float]
    platform_value: Optional[float]
    explicit_equity_adjustment: Optional[float]
    fair_equity_value: Optional[float]
    current_market_cap: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class CapitalMarketsQualityEvidence:
    market_turnover_change: Optional[float]
    brokerage_fee_growth: Optional[float]
    investment_banking_fee_growth: Optional[float]
    net_interest_income_growth: Optional[float]
    proprietary_or_investment_income_share: Optional[float]
    wealth_or_fund_distribution_growth: Optional[float]
    platform_service_growth: Optional[float]
    weighted_roe: Optional[float]
    evidence_completeness: float
    missing_fields: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.__dict__)
        payload["missing_fields"] = list(self.missing_fields)
        return payload


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fair_pb(
    *, normalized_mid_cycle_roe: Any, cost_of_equity: Any, long_term_growth: Any
) -> tuple[Optional[float], str]:
    roe = _finite(normalized_mid_cycle_roe)
    required_return = _finite(cost_of_equity)
    growth = _finite(long_term_growth)
    if roe is None:
        return None, "MID_CYCLE_ROE_UNAVAILABLE"
    if required_return is None:
        return None, "COST_OF_EQUITY_UNAVAILABLE"
    if growth is None:
        return None, "LONG_TERM_GROWTH_UNAVAILABLE"
    if required_return <= growth:
        return None, "INVALID_COST_OF_EQUITY_GROWTH_RELATION"
    fair_pb = (roe - growth) / (required_return - growth)
    if not math.isfinite(fair_pb) or fair_pb <= 0:
        return None, "NON_POSITIVE_RESIDUAL_INCOME_VALUE"
    return fair_pb, "OK"


def value_traditional_broker(
    *,
    common_bvps: Any,
    normalized_mid_cycle_roe: Any,
    cost_of_equity: Any,
    long_term_growth: Any,
    current_price: Any = None,
) -> TraditionalBrokerValuationResult:
    """Value a traditional broker from common book and mid-cycle ROE.

    The caller must normalize ROE across the capital-market cycle.  This module
    intentionally does not annualize a strong Q1/Q3 or infer mid-cycle ROE from
    current market turnover.
    """

    bvps = _finite(common_bvps)
    price = _finite(current_price)
    roe = _finite(normalized_mid_cycle_roe)
    required_return = _finite(cost_of_equity)
    growth = _finite(long_term_growth)

    if bvps is None or bvps <= 0:
        return TraditionalBrokerValuationResult(
            common_bvps=bvps,
            normalized_mid_cycle_roe=roe,
            cost_of_equity=required_return,
            long_term_growth=growth,
            fair_common_pb=None,
            fair_price=None,
            current_price=price,
            current_common_pb=None,
            implied_mid_cycle_roe=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="COMMON_BOOK_VALUE_UNAVAILABLE",
        )

    fair_pb, status = _fair_pb(
        normalized_mid_cycle_roe=roe,
        cost_of_equity=required_return,
        long_term_growth=growth,
    )
    current_pb = price / bvps if price is not None and price >= 0 else None
    implied_roe = None
    if (
        current_pb is not None
        and required_return is not None
        and growth is not None
        and required_return > growth
    ):
        implied_roe = current_pb * (required_return - growth) + growth

    if fair_pb is None:
        return TraditionalBrokerValuationResult(
            common_bvps=bvps,
            normalized_mid_cycle_roe=roe,
            cost_of_equity=required_return,
            long_term_growth=growth,
            fair_common_pb=None,
            fair_price=None,
            current_price=price,
            current_common_pb=current_pb,
            implied_mid_cycle_roe=implied_roe,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    fair_price = bvps * fair_pb
    margin = fair_price / price - 1.0 if price is not None and price > 0 else None
    return TraditionalBrokerValuationResult(
        common_bvps=bvps,
        normalized_mid_cycle_roe=roe,
        cost_of_equity=required_return,
        long_term_growth=growth,
        fair_common_pb=fair_pb,
        fair_price=fair_price,
        current_price=price,
        current_common_pb=current_pb,
        implied_mid_cycle_roe=implied_roe,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK",
    )


def value_hybrid_broker_platform_sotp(
    *,
    normalized_broker_profit: Any,
    broker_fair_multiple: Any,
    normalized_platform_profit: Any,
    platform_fair_multiple: Any,
    explicit_equity_adjustment: Any = None,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> HybridBrokerPlatformSOTPResult:
    """Value a broker/platform hybrid only when segment economics are explicit.

    Revenue shares are not accepted as a substitute for segment profit.  This
    prevents a high-margin platform segment and a balance-sheet/cycle-sensitive
    securities segment from being valued by one arbitrary consolidated P/B or
    PE.  If segment profit is not available, the adapter fails closed and the
    research layer must lower confidence or use an explicitly documented
    alternative whole-company normalization.
    """

    broker_profit = _finite(normalized_broker_profit)
    broker_multiple = _finite(broker_fair_multiple)
    platform_profit = _finite(normalized_platform_profit)
    platform_multiple = _finite(platform_fair_multiple)
    adjustment = _finite(explicit_equity_adjustment)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    common = dict(
        normalized_broker_profit=broker_profit,
        broker_fair_multiple=broker_multiple,
        normalized_platform_profit=platform_profit,
        platform_fair_multiple=platform_multiple,
        explicit_equity_adjustment=adjustment,
        current_market_cap=market_cap,
        total_common_shares=shares,
    )

    if broker_profit is None or platform_profit is None:
        return HybridBrokerPlatformSOTPResult(
            **common,
            broker_value=None,
            platform_value=None,
            fair_equity_value=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="SEGMENT_PROFIT_UNAVAILABLE",
        )
    if broker_profit < 0 or platform_profit < 0:
        return HybridBrokerPlatformSOTPResult(
            **common,
            broker_value=None,
            platform_value=None,
            fair_equity_value=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="NEGATIVE_SEGMENT_PROFIT_REQUIRES_ALTERNATIVE_MODEL",
        )
    if broker_multiple is None or broker_multiple <= 0 or platform_multiple is None or platform_multiple <= 0:
        return HybridBrokerPlatformSOTPResult(
            **common,
            broker_value=None,
            platform_value=None,
            fair_equity_value=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="SEGMENT_MULTIPLE_UNAVAILABLE",
        )

    broker_value = broker_profit * broker_multiple
    platform_value = platform_profit * platform_multiple
    fair_equity_value = broker_value + platform_value + (adjustment or 0.0)
    fair_price = fair_equity_value / shares if shares is not None and shares > 0 else None
    margin = fair_equity_value / market_cap - 1.0 if market_cap is not None and market_cap > 0 else None

    return HybridBrokerPlatformSOTPResult(
        **common,
        broker_value=broker_value,
        platform_value=platform_value,
        fair_equity_value=fair_equity_value,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def collect_capital_markets_quality_evidence(
    *,
    market_turnover_change: Any = None,
    brokerage_fee_growth: Any = None,
    investment_banking_fee_growth: Any = None,
    net_interest_income_growth: Any = None,
    proprietary_or_investment_income_share: Any = None,
    wealth_or_fund_distribution_growth: Any = None,
    platform_service_growth: Any = None,
    weighted_roe: Any = None,
) -> CapitalMarketsQualityEvidence:
    values = {
        "market_turnover_change": _finite(market_turnover_change),
        "brokerage_fee_growth": _finite(brokerage_fee_growth),
        "investment_banking_fee_growth": _finite(investment_banking_fee_growth),
        "net_interest_income_growth": _finite(net_interest_income_growth),
        "proprietary_or_investment_income_share": _finite(proprietary_or_investment_income_share),
        "wealth_or_fund_distribution_growth": _finite(wealth_or_fund_distribution_growth),
        "platform_service_growth": _finite(platform_service_growth),
        "weighted_roe": _finite(weighted_roe),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return CapitalMarketsQualityEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )


def build_traditional_broker_three_scenario_valuation(
    *,
    common_bvps: Any,
    scenarios: Mapping[str, Mapping[str, Any]],
    current_price: Any = None,
) -> Dict[str, Any]:
    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing broker valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        output["scenarios"][name] = value_traditional_broker(
            common_bvps=common_bvps,
            normalized_mid_cycle_roe=raw.get("normalized_mid_cycle_roe"),
            cost_of_equity=raw.get("cost_of_equity"),
            long_term_growth=raw.get("long_term_growth"),
            current_price=current_price,
        ).to_dict()

    base = output["scenarios"]["base"]
    output["reverse_valuation"] = {
        "current_common_pb": base.get("current_common_pb"),
        "implied_mid_cycle_roe": base.get("implied_mid_cycle_roe"),
        "base_mid_cycle_roe": base.get("normalized_mid_cycle_roe"),
        "expectation_gap_roe": (
            None
            if base.get("implied_mid_cycle_roe") is None or base.get("normalized_mid_cycle_roe") is None
            else base["implied_mid_cycle_roe"] - base["normalized_mid_cycle_roe"]
        ),
        "status": base.get("status"),
    }
    return output
