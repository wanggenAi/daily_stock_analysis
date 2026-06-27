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
    industry_cycle_score: float
    industry: Optional[str] = None
    industry_cycle_phase: Optional[str] = None
    market_environment_state: Optional[str] = None
    price_percentile_3y: Optional[float] = None
    price_percentile_5y: Optional[float] = None
    price_percentile_10y: Optional[float] = None
    distance_from_5y_low_pct: Optional[float] = None
    distance_from_5y_high_pct: Optional[float] = None
    distance_from_10y_low_pct: Optional[float] = None
    distance_from_10y_high_pct: Optional[float] = None
    entry_price: Optional[float] = None
    entry_date: Optional[str] = None
    entry_mode: str = "next_open"
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
