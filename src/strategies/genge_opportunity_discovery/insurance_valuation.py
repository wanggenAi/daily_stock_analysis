"""Pure life-insurance embedded-value / new-business-value valuation primitives.

Life insurers are deliberately routed away from a generic ``net profit * PE``
model.  Reported earnings can swing with investment markets, while embedded
value (EV) is an actuarial estimate of the economic value of existing in-force
business and adjusted net assets.  EV, by definition, excludes the value of
future new business written after the valuation date.

A common appraisal-value bridge is therefore represented explicitly as::

    fair equity value = embedded value + normalized annual NBV * franchise multiple

The NBV franchise multiple is *never invented* here.  It must be supplied by a
scenario and can be reverse-solved from the market for expectation analysis.
Quarterly NBV must not be mechanically annualized by this module.

For diversified insurance groups, callers should pass a group-level embedded
value (or an explicitly constructed sum-of-parts EV) whose scope already
includes the adjusted net asset value of non-life businesses.  Do not add book
value again on top of such an EV.

Nothing in this module creates a Formal BUY or changes execution/risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class InsuranceAppraisalValueResult:
    embedded_value: Optional[float]
    normalized_annual_nbv: Optional[float]
    nbv_franchise_multiple: Optional[float]
    future_new_business_value: Optional[float]
    explicit_equity_adjustment: Optional[float]
    fair_equity_value: Optional[float]
    total_common_shares: Optional[float]
    fair_price: Optional[float]
    current_market_cap: Optional[float]
    current_p_ev: Optional[float]
    implied_nbv_franchise_multiple: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class InsuranceQualityEvidence:
    """Raw life/P&C quality evidence without an arbitrary composite score."""

    nbv_growth: Optional[float]
    nbv_margin: Optional[float]
    persistency_13m: Optional[float]
    persistency_25m: Optional[float]
    surrender_rate: Optional[float]
    net_investment_yield: Optional[float]
    total_or_comprehensive_investment_yield: Optional[float]
    core_solvency_ratio: Optional[float]
    comprehensive_solvency_ratio: Optional[float]
    p_and_c_combined_ratio: Optional[float]
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


def value_insurance_appraisal(
    *,
    embedded_value: Any,
    normalized_annual_nbv: Any,
    nbv_franchise_multiple: Any,
    current_market_cap: Any = None,
    explicit_equity_adjustment: Any = None,
    total_common_shares: Any = None,
) -> InsuranceAppraisalValueResult:
    """Bridge EV and future-new-business franchise value to common equity.

    ``normalized_annual_nbv`` must be an explicitly prepared annual/forward
    measure.  The function intentionally has no quarterly-NBV annualization
    argument, preventing accidental ``Q1 * 4`` extrapolation.

    ``explicit_equity_adjustment`` is reserved for a separately verified
    holding-company or equity adjustment that is *not already inside EV*.
    Callers are responsible for avoiding double counting.
    """

    ev = _finite(embedded_value)
    nbv = _finite(normalized_annual_nbv)
    franchise_multiple = _finite(nbv_franchise_multiple)
    market_cap = _finite(current_market_cap)
    adjustment = _finite(explicit_equity_adjustment)
    shares = _finite(total_common_shares)

    common = dict(
        embedded_value=ev,
        normalized_annual_nbv=nbv,
        nbv_franchise_multiple=franchise_multiple,
        explicit_equity_adjustment=adjustment,
        total_common_shares=shares,
        current_market_cap=market_cap,
    )

    if ev is None or ev <= 0:
        return InsuranceAppraisalValueResult(
            **common,
            future_new_business_value=None,
            fair_equity_value=None,
            fair_price=None,
            current_p_ev=None,
            implied_nbv_franchise_multiple=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="EMBEDDED_VALUE_UNAVAILABLE",
        )
    if nbv is None or nbv <= 0:
        return InsuranceAppraisalValueResult(
            **common,
            future_new_business_value=None,
            fair_equity_value=None,
            fair_price=None,
            current_p_ev=(market_cap / ev if market_cap is not None and market_cap >= 0 else None),
            implied_nbv_franchise_multiple=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="NORMALIZED_ANNUAL_NBV_UNAVAILABLE",
        )
    if franchise_multiple is None or franchise_multiple < 0:
        return InsuranceAppraisalValueResult(
            **common,
            future_new_business_value=None,
            fair_equity_value=None,
            fair_price=None,
            current_p_ev=(market_cap / ev if market_cap is not None and market_cap >= 0 else None),
            implied_nbv_franchise_multiple=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="NBV_FRANCHISE_MULTIPLE_UNAVAILABLE",
        )

    future_new_business_value = nbv * franchise_multiple
    fair_equity_value = ev + future_new_business_value + (adjustment or 0.0)
    fair_price = fair_equity_value / shares if shares is not None and shares > 0 else None

    current_p_ev = market_cap / ev if market_cap is not None and market_cap >= 0 else None
    implied_multiple = None
    margin = None
    if market_cap is not None and market_cap >= 0:
        implied_multiple = (market_cap - ev - (adjustment or 0.0)) / nbv
        if market_cap > 0:
            margin = fair_equity_value / market_cap - 1.0

    return InsuranceAppraisalValueResult(
        **common,
        future_new_business_value=future_new_business_value,
        fair_equity_value=fair_equity_value,
        fair_price=fair_price,
        current_p_ev=current_p_ev,
        implied_nbv_franchise_multiple=implied_multiple,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK" if fair_price is not None else "OK_PRICE_UNAVAILABLE",
    )


def reverse_implied_nbv_franchise_multiple(
    *,
    current_market_cap: Any,
    embedded_value: Any,
    normalized_annual_nbv: Any,
    explicit_equity_adjustment: Any = None,
) -> tuple[Optional[float], str]:
    """Reverse-solve the market value assigned to future new business.

    A negative result is deliberately preserved.  It means market capitalization
    is below the supplied EV (after explicit adjustment); it does not mean the
    arithmetic should be floored at zero.
    """

    market_cap = _finite(current_market_cap)
    ev = _finite(embedded_value)
    nbv = _finite(normalized_annual_nbv)
    adjustment = _finite(explicit_equity_adjustment)

    if market_cap is None or market_cap < 0:
        return None, "MARKET_CAP_UNAVAILABLE"
    if ev is None or ev <= 0:
        return None, "EMBEDDED_VALUE_UNAVAILABLE"
    if nbv is None or nbv <= 0:
        return None, "NORMALIZED_ANNUAL_NBV_UNAVAILABLE"
    return (market_cap - ev - (adjustment or 0.0)) / nbv, "OK"


def collect_insurance_quality_evidence(
    *,
    nbv_growth: Any = None,
    nbv_margin: Any = None,
    persistency_13m: Any = None,
    persistency_25m: Any = None,
    surrender_rate: Any = None,
    net_investment_yield: Any = None,
    total_or_comprehensive_investment_yield: Any = None,
    core_solvency_ratio: Any = None,
    comprehensive_solvency_ratio: Any = None,
    p_and_c_combined_ratio: Any = None,
) -> InsuranceQualityEvidence:
    """Carry insurance-specific evidence without manufacturing one score."""

    values = {
        "nbv_growth": _finite(nbv_growth),
        "nbv_margin": _finite(nbv_margin),
        "persistency_13m": _finite(persistency_13m),
        "persistency_25m": _finite(persistency_25m),
        "surrender_rate": _finite(surrender_rate),
        "net_investment_yield": _finite(net_investment_yield),
        "total_or_comprehensive_investment_yield": _finite(total_or_comprehensive_investment_yield),
        "core_solvency_ratio": _finite(core_solvency_ratio),
        "comprehensive_solvency_ratio": _finite(comprehensive_solvency_ratio),
        "p_and_c_combined_ratio": _finite(p_and_c_combined_ratio),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    completeness = (len(values) - len(missing)) / len(values)
    return InsuranceQualityEvidence(
        **values,
        evidence_completeness=round(completeness, 6),
        missing_fields=missing,
    )


def build_insurance_three_scenario_valuation(
    *,
    embedded_value: Any,
    scenarios: Mapping[str, Mapping[str, Any]],
    current_market_cap: Any = None,
    explicit_equity_adjustment: Any = None,
    total_common_shares: Any = None,
) -> Dict[str, Any]:
    """Build explicit bear/base/bull EV+NBV appraisal valuations.

    Every scenario must provide its own ``normalized_annual_nbv`` and
    ``nbv_franchise_multiple``.  This prevents a quarterly NBV growth print from
    silently becoming a permanent annual franchise value.
    """

    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing insurance valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        result = value_insurance_appraisal(
            embedded_value=raw.get("embedded_value", embedded_value),
            normalized_annual_nbv=raw.get("normalized_annual_nbv"),
            nbv_franchise_multiple=raw.get("nbv_franchise_multiple"),
            current_market_cap=current_market_cap,
            explicit_equity_adjustment=raw.get("explicit_equity_adjustment", explicit_equity_adjustment),
            total_common_shares=total_common_shares,
        )
        output["scenarios"][name] = result.to_dict()

    base = output["scenarios"]["base"]
    output["reverse_valuation"] = {
        "current_p_ev": base.get("current_p_ev"),
        "implied_nbv_franchise_multiple": base.get("implied_nbv_franchise_multiple"),
        "base_nbv_franchise_multiple": base.get("nbv_franchise_multiple"),
        "expectation_gap_multiple": (
            None
            if base.get("implied_nbv_franchise_multiple") is None
            or base.get("nbv_franchise_multiple") is None
            else base["implied_nbv_franchise_multiple"] - base["nbv_franchise_multiple"]
        ),
        "status": base.get("status"),
    }
    return output
