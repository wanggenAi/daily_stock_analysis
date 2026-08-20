"""Bridge *executed* specialized valuation evidence into price-map fair values.

This module does not invent missing valuation scenarios.  It only performs
algebraic unit conversion when an already-executed specialized model publishes
both a current valuation unit and a fair valuation unit.

Currently supported:

* ``capital_markets_cycle``: the specialized executor values brokers/securities
  firms in normalized book-value units and publishes ``current PB`` and
  ``fair PB``.  Given an observed share price, the corresponding per-share base
  fair value is exactly ``price * fair_pb / current_pb``.

Bear/bull values are deliberately left blank because the executed model does not
publish bear/bull PB assumptions.  Other specialized routes remain unavailable
until their own auditable model produces a per-share/equity fair value.  A route
selection or reverse-implied diagnostic is never enough to create a fair price.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

CAPITAL_MARKETS_STRATEGY_ID = "capital_markets_cycle"


@dataclass(frozen=True)
class SpecializedScenarioBridge:
    status: str
    strategy_id: str
    fair_price_bear: float | None
    fair_price_base: float | None
    fair_price_bull: float | None
    basis: str


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def bridge_specialized_scenario(
    specialized_row: Mapping[str, Any] | None,
    *,
    current_price: Any,
) -> SpecializedScenarioBridge:
    """Return only fair values directly implied by an executed specialized model."""
    if not specialized_row:
        return SpecializedScenarioBridge(
            "SPECIALIZED_EXECUTION_UNAVAILABLE", "", None, None, None, ""
        )

    strategy_id = str(specialized_row.get("valuation_primary_strategy_id") or "").strip()
    if not strategy_id:
        return SpecializedScenarioBridge(
            "SPECIALIZED_STRATEGY_UNAVAILABLE", "", None, None, None, ""
        )

    if strategy_id != CAPITAL_MARKETS_STRATEGY_ID:
        return SpecializedScenarioBridge(
            "SPECIALIZED_MODEL_HAS_NO_AUDITABLE_PER_SHARE_FAIR_VALUE_BRIDGE",
            strategy_id,
            None,
            None,
            None,
            f"strategy={strategy_id};no_per_share_fair_value_bridge",
        )

    executed = str(specialized_row.get("specialized_model_executed") or "").strip().lower()
    execution_state = str(
        specialized_row.get("specialized_model_execution_state") or ""
    ).strip()
    model_status = str(specialized_row.get("specialized_model_status") or "").strip().upper()
    if executed not in {"true", "1", "yes"} or execution_state != "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY":
        return SpecializedScenarioBridge(
            "SPECIALIZED_MODEL_NOT_EXECUTED",
            strategy_id,
            None,
            None,
            None,
            f"execution_state={execution_state or 'MISSING'}",
        )
    if model_status != "OK":
        return SpecializedScenarioBridge(
            "SPECIALIZED_MODEL_NOT_APPLICABLE",
            strategy_id,
            None,
            None,
            None,
            f"specialized_model_status={model_status or 'MISSING'}",
        )

    price = _positive(current_price)
    current_pb = _positive(specialized_row.get("specialized_current_pb"))
    fair_pb = _positive(specialized_row.get("specialized_fair_pb"))
    if price is None or current_pb is None or fair_pb is None:
        return SpecializedScenarioBridge(
            "SPECIALIZED_FAIR_VALUE_INPUTS_INCOMPLETE",
            strategy_id,
            None,
            None,
            None,
            "requires_positive_share_price_current_pb_and_fair_pb",
        )

    base = price * fair_pb / current_pb
    if not math.isfinite(base) or base <= 0:
        return SpecializedScenarioBridge(
            "SPECIALIZED_FAIR_VALUE_INVALID",
            strategy_id,
            None,
            None,
            None,
            "price_x_fair_pb_div_current_pb_invalid",
        )

    return SpecializedScenarioBridge(
        "OK_BASE_ONLY",
        strategy_id,
        None,
        round(base, 4),
        None,
        (
            "capital_markets_cycle_normalized_book_units;"
            f"share_price={price:.6f};current_pb={current_pb:.6f};fair_pb={fair_pb:.6f};"
            "base_fair_price=share_price*fair_pb/current_pb;bear_bull_not_invented"
        ),
    )
