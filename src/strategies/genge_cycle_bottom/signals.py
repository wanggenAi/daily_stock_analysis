"""Signal contracts for the GenGe Cycle Bottom Strategy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalType(str, Enum):
    REJECT = "REJECT"
    WATCH = "WATCH"
    LEFT_SMALL_BUY = "LEFT_SMALL_BUY"
    CONFIRM_BUY = "CONFIRM_BUY"
    HOLD = "HOLD"
    ADD = "ADD"
    REDUCE = "REDUCE"
    SELL = "SELL"


SIGNAL_TYPES = tuple(item.value for item in SignalType)


@dataclass
class StrategySignal:
    code: str
    stock_name: str
    as_of_date: str
    signal_type: SignalType
    total_score: float
    price_percentile_score: float
    valuation_score: float
    financial_safety_score: float
    trend_stabilization_score: float
    market_environment_score: float
    risk_flags: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    invalidation_reason: str = ""
    max_position_pct: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["signal_type"] = self.signal_type.value
        data["risk_flags"] = ";".join(self.risk_flags)
        data["missing_fields"] = ";".join(self.missing_fields)
        return data

