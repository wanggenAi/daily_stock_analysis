"""Pure bank-specific valuation primitives for opportunity research.

Banks are deliberately routed away from the generic industrial ``profit * PE``
bridge.  For a deposit-taking bank, operating cash flow is not an industrial
free-cash-flow proxy and common shareholders should be valued against *common*
equity rather than total equity that may include preferred shares or perpetual
capital instruments.

This module therefore implements a small, auditable residual-income/Gordon
``P/B <-> sustainable ROE`` bridge.  It does **not** invent a cost of equity,
long-term growth rate, target CET1 ratio, target provision coverage, or target
P/B.  Those assumptions must be supplied explicitly by the caller and remain
scenario inputs.

Nothing in this module can create a Formal BUY, size a position, or bypass the
existing technical/risk gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class BankBookValueResult:
    """Common-equity price/book bridge.

    ``common_equity`` means equity attributable to ordinary/common
    shareholders.  Total parent equity is intentionally not accepted as a
    substitute because bank balance sheets may contain other equity instruments
    that do not belong to common shareholders.
    """

    common_equity: Optional[float]
    common_shares: Optional[float]
    common_bvps: Optional[float]
    current_price: Optional[float]
    current_market_cap: Optional[float]
    current_common_pb: Optional[float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BankPBValuationResult:
    common_bvps: Optional[float]
    sustainable_roe: Optional[float]
    cost_of_equity: Optional[float]
    long_term_growth: Optional[float]
    fair_common_pb: Optional[float]
    fair_price: Optional[float]
    current_price: Optional[float]
    current_common_pb: Optional[float]
    implied_sustainable_roe: Optional[float]
    excess_roe_vs_cost_of_equity: Optional[float]
    margin_of_safety: Optional[float]
    valuation_model_applicable: bool
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class BankQualityEvidence:
    """Raw bank-quality evidence carried alongside valuation.

    These fields are intentionally *not* converted into an arbitrary composite
    score.  Their economic interpretation depends on bank type, accounting
    definitions and cycle context.  The adapter records them so the research
    layer can compare scenarios and reduce confidence when evidence is missing.
    """

    net_interest_margin: Optional[float]
    net_interest_margin_change: Optional[float]
    npl_ratio: Optional[float]
    provision_coverage_ratio: Optional[float]
    common_equity_tier1_ratio: Optional[float]
    credit_cost: Optional[float]
    cost_income_ratio: Optional[float]
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


def build_common_book_value(
    *,
    common_equity: Any = None,
    common_shares: Any = None,
    common_bvps: Any = None,
    current_price: Any = None,
    current_market_cap: Any = None,
) -> BankBookValueResult:
    """Build a common-share book-value bridge without using total equity.

    At least one valid common-book-value representation is required:

    - reported common BVPS; or
    - common equity plus common shares.

    Current common P/B is derived from price/BVPS when both are available,
    otherwise market-cap/common-equity can be used.  If both forms are present,
    price/BVPS is preferred because it keeps the numerator/denominator on a
    per-common-share basis.
    """

    equity = _finite(common_equity)
    shares = _finite(common_shares)
    bvps = _finite(common_bvps)
    price = _finite(current_price)
    market_cap = _finite(current_market_cap)

    if bvps is None and equity is not None and shares is not None and shares > 0:
        bvps = equity / shares

    if bvps is None or bvps <= 0:
        return BankBookValueResult(
            common_equity=equity,
            common_shares=shares,
            common_bvps=bvps,
            current_price=price,
            current_market_cap=market_cap,
            current_common_pb=None,
            status="COMMON_BOOK_VALUE_UNAVAILABLE",
        )

    pb: Optional[float] = None
    status = "OK_BOOK_ONLY"
    if price is not None and price >= 0:
        pb = price / bvps
        status = "OK"
    elif market_cap is not None and market_cap >= 0 and equity is not None and equity > 0:
        pb = market_cap / equity
        status = "OK"

    return BankBookValueResult(
        common_equity=equity,
        common_shares=shares,
        common_bvps=bvps,
        current_price=price,
        current_market_cap=market_cap,
        current_common_pb=pb,
        status=status,
    )


def fair_pb_from_roe(
    *,
    sustainable_roe: Any,
    cost_of_equity: Any,
    long_term_growth: Any,
) -> tuple[Optional[float], str]:
    """Return Gordon/residual-income fair P/B from explicit assumptions.

    Formula::

        fair_PB = (sustainable_ROE - g) / (cost_of_equity - g)

    All rate inputs are decimal fractions (for example ``0.12`` for 12%).
    The model fails closed when ``cost_of_equity <= g`` or when the result is
    non-positive.  A non-positive residual-income P/B is not coerced into an
    arbitrary floor.
    """

    roe = _finite(sustainable_roe)
    required_return = _finite(cost_of_equity)
    growth = _finite(long_term_growth)

    if roe is None:
        return None, "SUSTAINABLE_ROE_UNAVAILABLE"
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


def implied_roe_from_pb(
    *,
    current_common_pb: Any,
    cost_of_equity: Any,
    long_term_growth: Any,
) -> tuple[Optional[float], str]:
    """Reverse-solve the sustainable ROE implied by current common P/B.

    Rearranging the same residual-income relation gives::

        implied_ROE = current_PB * (cost_of_equity - g) + g

    This is a market-expectation diagnostic, not a forecast.
    """

    pb = _finite(current_common_pb)
    required_return = _finite(cost_of_equity)
    growth = _finite(long_term_growth)

    if pb is None or pb < 0:
        return None, "COMMON_PB_UNAVAILABLE"
    if required_return is None:
        return None, "COST_OF_EQUITY_UNAVAILABLE"
    if growth is None:
        return None, "LONG_TERM_GROWTH_UNAVAILABLE"
    if required_return <= growth:
        return None, "INVALID_COST_OF_EQUITY_GROWTH_RELATION"

    implied = pb * (required_return - growth) + growth
    return implied, "OK"


def value_bank_common_equity(
    *,
    common_bvps: Any,
    sustainable_roe: Any,
    cost_of_equity: Any,
    long_term_growth: Any,
    current_price: Any = None,
    current_common_pb: Any = None,
) -> BankPBValuationResult:
    """Value one bank common share using explicit residual-income inputs."""

    bvps = _finite(common_bvps)
    price = _finite(current_price)
    observed_pb = _finite(current_common_pb)

    if bvps is None or bvps <= 0:
        return BankPBValuationResult(
            common_bvps=bvps,
            sustainable_roe=_finite(sustainable_roe),
            cost_of_equity=_finite(cost_of_equity),
            long_term_growth=_finite(long_term_growth),
            fair_common_pb=None,
            fair_price=None,
            current_price=price,
            current_common_pb=observed_pb,
            implied_sustainable_roe=None,
            excess_roe_vs_cost_of_equity=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status="COMMON_BOOK_VALUE_UNAVAILABLE",
        )

    if observed_pb is None and price is not None and price >= 0:
        observed_pb = price / bvps

    fair_pb, status = fair_pb_from_roe(
        sustainable_roe=sustainable_roe,
        cost_of_equity=cost_of_equity,
        long_term_growth=long_term_growth,
    )
    if fair_pb is None:
        return BankPBValuationResult(
            common_bvps=bvps,
            sustainable_roe=_finite(sustainable_roe),
            cost_of_equity=_finite(cost_of_equity),
            long_term_growth=_finite(long_term_growth),
            fair_common_pb=None,
            fair_price=None,
            current_price=price,
            current_common_pb=observed_pb,
            implied_sustainable_roe=None,
            excess_roe_vs_cost_of_equity=None,
            margin_of_safety=None,
            valuation_model_applicable=False,
            status=status,
        )

    fair_price = bvps * fair_pb
    implied_roe = None
    if observed_pb is not None:
        implied_roe, _ = implied_roe_from_pb(
            current_common_pb=observed_pb,
            cost_of_equity=cost_of_equity,
            long_term_growth=long_term_growth,
        )

    roe = _finite(sustainable_roe)
    required_return = _finite(cost_of_equity)
    excess_roe = None if roe is None or required_return is None else roe - required_return
    margin = None
    if price is not None and price > 0:
        margin = fair_price / price - 1.0

    return BankPBValuationResult(
        common_bvps=bvps,
        sustainable_roe=roe,
        cost_of_equity=required_return,
        long_term_growth=_finite(long_term_growth),
        fair_common_pb=fair_pb,
        fair_price=fair_price,
        current_price=price,
        current_common_pb=observed_pb,
        implied_sustainable_roe=implied_roe,
        excess_roe_vs_cost_of_equity=excess_roe,
        margin_of_safety=margin,
        valuation_model_applicable=True,
        status="OK",
    )


def collect_bank_quality_evidence(
    *,
    net_interest_margin: Any = None,
    net_interest_margin_change: Any = None,
    npl_ratio: Any = None,
    provision_coverage_ratio: Any = None,
    common_equity_tier1_ratio: Any = None,
    credit_cost: Any = None,
    cost_income_ratio: Any = None,
) -> BankQualityEvidence:
    """Record bank-specific quality evidence without arbitrary scoring."""

    values = {
        "net_interest_margin": _finite(net_interest_margin),
        "net_interest_margin_change": _finite(net_interest_margin_change),
        "npl_ratio": _finite(npl_ratio),
        "provision_coverage_ratio": _finite(provision_coverage_ratio),
        "common_equity_tier1_ratio": _finite(common_equity_tier1_ratio),
        "credit_cost": _finite(credit_cost),
        "cost_income_ratio": _finite(cost_income_ratio),
    }
    missing = tuple(name for name, value in values.items() if value is None)
    completeness = (len(values) - len(missing)) / len(values)
    return BankQualityEvidence(
        **values,
        evidence_completeness=round(completeness, 6),
        missing_fields=missing,
    )


def build_bank_three_scenario_valuation(
    *,
    common_bvps: Any,
    scenarios: Mapping[str, Mapping[str, Any]],
    current_price: Any = None,
    current_common_pb: Any = None,
) -> Dict[str, Any]:
    """Build bear/base/bull bank valuations from caller-supplied assumptions.

    Each scenario must explicitly provide ``sustainable_roe``,
    ``cost_of_equity`` and ``long_term_growth``.  Missing assumptions therefore
    fail closed rather than silently inheriting a universal bank P/B target.
    """

    missing = [name for name in ("bear", "base", "bull") if name not in scenarios]
    if missing:
        raise ValueError(f"missing bank valuation scenarios: {','.join(missing)}")

    output: Dict[str, Any] = {"scenarios": {}}
    for name in ("bear", "base", "bull"):
        raw = scenarios[name]
        result = value_bank_common_equity(
            common_bvps=common_bvps,
            sustainable_roe=raw.get("sustainable_roe"),
            cost_of_equity=raw.get("cost_of_equity"),
            long_term_growth=raw.get("long_term_growth"),
            current_price=current_price,
            current_common_pb=current_common_pb,
        )
        output["scenarios"][name] = result.to_dict()

    base = output["scenarios"]["base"]
    output["reverse_valuation"] = {
        "current_common_pb": base.get("current_common_pb"),
        "implied_sustainable_roe": base.get("implied_sustainable_roe"),
        "base_sustainable_roe": base.get("sustainable_roe"),
        "expectation_gap_roe": (
            None
            if base.get("implied_sustainable_roe") is None or base.get("sustainable_roe") is None
            else base["implied_sustainable_roe"] - base["sustainable_roe"]
        ),
        "status": base.get("status"),
    }
    return output
