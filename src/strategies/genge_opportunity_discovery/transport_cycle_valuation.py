"""Through-cycle enterprise-value primitives for capital-intensive transport.

This module covers transport businesses whose current earnings can be dominated
by freight/yield, utilization, fuel and capacity cycles (for example container
shipping and airlines).  It is intentionally narrower than the existing yield
asset module used for mature airports/concessions.

The valuation bridge uses an explicitly prepared *through-cycle normalized
EBITDA* and an explicit EV/EBITDA multiple.  Enterprise value is then bridged to
common equity using net debt **including lease liabilities when economically
relevant**.  For an airline, the caller must therefore prepare a lease-consistent
net-debt measure rather than comparing post-IFRS-16 EBITDA with debt that omits
lease obligations.

There is no built-in freight-rate mean, passenger-yield mean, load-factor target,
fuel price, FX rate, capacity growth, cycle haircut or valuation multiple.
Those belong to point-in-time research scenarios and later out-of-time tests.

Mature airport/concession assets should generally reuse ``yield_asset_valuation``
rather than being forced through this cycle EV bridge.

Nothing here creates a Formal BUY or bypasses downstream risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class TransportEVValuationResult:
    through_cycle_normalized_ebitda: Optional[float]
    fair_ev_ebitda_multiple: Optional[float]
    fair_enterprise_value: Optional[float]
    net_debt_including_lease_liabilities: Optional[float]
    explicit_non_operating_equity_adjustment: Optional[float]
    fair_equity_value: Optional[float]
    current_market_cap: Optional[float]
    current_enterprise_value: Optional[float]
    implied_normalized_ebitda: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class TransportCycleEvidence:
    volume_or_rpk_growth: Optional[float]
    capacity_or_ask_growth: Optional[float]
    utilization_or_load_factor: Optional[float]
    utilization_or_load_factor_change: Optional[float]
    unit_revenue_or_yield_change: Optional[float]
    unit_cost_change: Optional[float]
    fuel_unit_cost_change: Optional[float]
    benchmark_rate_or_fare_index_change: Optional[float]
    fleet_capacity_growth: Optional[float]
    lease_liabilities: Optional[float]
    capital_expenditure: Optional[float]
    net_debt_including_lease_liabilities: Optional[float]
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


def value_through_cycle_transport_ev(
    *,
    through_cycle_normalized_ebitda: Any,
    fair_ev_ebitda_multiple: Any,
    net_debt_including_lease_liabilities: Any,
    explicit_non_operating_equity_adjustment: Any = None,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> TransportEVValuationResult:
    """Value a cycle-sensitive transport company on normalized enterprise value.

    ``net_debt_including_lease_liabilities`` may be negative for a net-cash
    company.  Negative net debt therefore increases equity value and is not
    floored at zero.

    The current-market reverse calculation uses the same debt/lease scope:

        current_EV = market_cap + net_debt - explicit_non_operating_adjustment
        implied_normalized_EBITDA = current_EV / fair_EV_EBITDA_multiple

    so current price can be compared with an evidence-based through-cycle EBITDA
    range without capitalizing peak-period earnings.
    """

    ebitda = _finite(through_cycle_normalized_ebitda)
    multiple = _finite(fair_ev_ebitda_multiple)
    net_debt = _finite(net_debt_including_lease_liabilities)
    adjustment = _finite(explicit_non_operating_equity_adjustment)
    market_cap = _finite(current_market_cap)
    shares = _finite(total_common_shares)

    common = dict(
        through_cycle_normalized_ebitda=ebitda,
        fair_ev_ebitda_multiple=multiple,
        net_debt_including_lease_liabilities=net_debt,
        explicit_non_operating_equity_adjustment=adjustment,
        current_market_cap=market_cap,
        total_common_shares=shares,
    )

    if ebitda is None or ebitda <= 0:
        status = "THROUGH_CYCLE_EBITDA_UNAVAILABLE"
    elif multiple is None or multiple <= 0:
        status = "FAIR_EV_EBITDA_MULTIPLE_UNAVAILABLE"
    elif net_debt is None:
        status = "LEASE_CONSISTENT_NET_DEBT_UNAVAILABLE"
    else:
        status = "OK"

    if status != "OK":
        return TransportEVValuationResult(
            **common,
            fair_enterprise_value=None,
            fair_equity_value=None,
            current_enterprise_value=None,
            implied_normalized_ebitda=None,
            fair_price=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    assert ebitda is not None and multiple is not None and net_debt is not None
    fair_ev = ebitda * multiple
    fair_equity = fair_ev - net_debt + (adjustment or 0.0)
    fair_price = fair_equity / shares if shares is not None and shares > 0 else None

    current_ev = None
    implied_ebitda = None
    margin = None
    if market_cap is not None and market_cap >= 0:
        current_ev = market_cap + net_debt - (adjustment or 0.0)
        implied_ebitda = current_ev / multiple
        if market_cap > 0:
            margin = fair_equity / market_cap - 1.0

    return TransportEVValuationResult(
        **common,
        fair_enterprise_value=fair_ev,
        fair_equity_value=fair_equity,
        current_enterprise_value=current_ev,
        implied_normalized_ebitda=implied_ebitda,
        fair_price=fair_price,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def reverse_implied_transport_ebitda(
    *,
    current_market_cap: Any,
    fair_ev_ebitda_multiple: Any,
    net_debt_including_lease_liabilities: Any,
    explicit_non_operating_equity_adjustment: Any = None,
) -> tuple[Optional[float], str]:
    """Reverse-solve normalized EBITDA required by current market value."""

    market_cap = _finite(current_market_cap)
    multiple = _finite(fair_ev_ebitda_multiple)
    net_debt = _finite(net_debt_including_lease_liabilities)
    adjustment = _finite(explicit_non_operating_equity_adjustment)
    if market_cap is None or market_cap < 0:
        return None, "MARKET_CAP_UNAVAILABLE"
    if multiple is None or multiple <= 0:
        return None, "FAIR_EV_EBITDA_MULTIPLE_UNAVAILABLE"
    if net_debt is None:
        return None, "LEASE_CONSISTENT_NET_DEBT_UNAVAILABLE"
    return (market_cap + net_debt - (adjustment or 0.0)) / multiple, "OK"


def collect_transport_cycle_evidence(
    *,
    volume_or_rpk_growth: Any = None,
    capacity_or_ask_growth: Any = None,
    utilization_or_load_factor: Any = None,
    utilization_or_load_factor_change: Any = None,
    unit_revenue_or_yield_change: Any = None,
    unit_cost_change: Any = None,
    fuel_unit_cost_change: Any = None,
    benchmark_rate_or_fare_index_change: Any = None,
    fleet_capacity_growth: Any = None,
    lease_liabilities: Any = None,
    capital_expenditure: Any = None,
    net_debt_including_lease_liabilities: Any = None,
) -> TransportCycleEvidence:
    """Keep shipping/airline cycle evidence explicit; no composite score."""

    values = {
        "volume_or_rpk_growth": _finite(volume_or_rpk_growth),
        "capacity_or_ask_growth": _finite(capacity_or_ask_growth),
        "utilization_or_load_factor": _finite(utilization_or_load_factor),
        "utilization_or_load_factor_change": _finite(utilization_or_load_factor_change),
        "unit_revenue_or_yield_change": _finite(unit_revenue_or_yield_change),
        "unit_cost_change": _finite(unit_cost_change),
        "fuel_unit_cost_change": _finite(fuel_unit_cost_change),
        "benchmark_rate_or_fare_index_change": _finite(benchmark_rate_or_fare_index_change),
        "fleet_capacity_growth": _finite(fleet_capacity_growth),
        "lease_liabilities": _finite(lease_liabilities),
        "capital_expenditure": _finite(capital_expenditure),
        "net_debt_including_lease_liabilities": _finite(net_debt_including_lease_liabilities),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    return TransportCycleEvidence(
        **values,
        evidence_completeness=round((len(values) - len(missing)) / len(values), 6),
        missing_fields=missing,
    )


def build_transport_three_scenario_valuation(
    *,
    scenarios: Mapping[str, Mapping[str, Any]],
    net_debt_including_lease_liabilities: Any,
    explicit_non_operating_equity_adjustment: Any = None,
    current_market_cap: Any = None,
    total_common_shares: Any = None,
) -> Dict[str, Any]:
    """Build explicit Bear/Base/Bull through-cycle transport valuations."""

    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing transport valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        output["scenarios"][name] = value_through_cycle_transport_ev(
            through_cycle_normalized_ebitda=raw.get("through_cycle_normalized_ebitda"),
            fair_ev_ebitda_multiple=raw.get("fair_ev_ebitda_multiple"),
            net_debt_including_lease_liabilities=raw.get(
                "net_debt_including_lease_liabilities", net_debt_including_lease_liabilities
            ),
            explicit_non_operating_equity_adjustment=raw.get(
                "explicit_non_operating_equity_adjustment", explicit_non_operating_equity_adjustment
            ),
            current_market_cap=current_market_cap,
            total_common_shares=total_common_shares,
        ).to_dict()

    base = output["scenarios"]["base"]
    output["reverse_valuation"] = {
        "current_enterprise_value": base.get("current_enterprise_value"),
        "implied_normalized_ebitda": base.get("implied_normalized_ebitda"),
        "base_through_cycle_normalized_ebitda": base.get("through_cycle_normalized_ebitda"),
        "expectation_gap_ebitda": (
            None
            if base.get("implied_normalized_ebitda") is None
            or base.get("through_cycle_normalized_ebitda") is None
            else base["implied_normalized_ebitda"] - base["through_cycle_normalized_ebitda"]
        ),
        "status": base.get("status"),
    }
    return output
