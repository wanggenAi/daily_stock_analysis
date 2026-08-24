"""Frozen V3.1 stock-selection and execution decision contract.

This module is the authoritative qualification layer for the GenGe opportunity
pipeline. Discovery/ranking code may recall names broadly, but it must not turn
a legacy research score, cheap valuation or technical setup into an A-grade
candidate or a formal long-term BUY.

V3.1 deliberately keeps judgement-heavy items explicit. Missing evidence is
UNKNOWN and blocks A-grade eligibility; it is never silently converted to PASS.

Research may cover the broader A-share universe, but actual BUY eligibility is
hard-limited to the user's execution universe: Shanghai main-board 600/601/603/
605 and Shenzhen main-board 000/001/002/003 prefixes. STAR/ChiNext/BSE names may
still appear in research outputs, but can never become V3.1 BUY-ready.

The same contract also freezes a valuation-driven exit discipline. Valuation
alone does not force liquidation when fundamentals remain intact, but it does
control staged de-risking. A broken hard logic gate overrides valuation and
forces EXIT review.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

POLICY_VERSION = "selection_framework_v3_1_frozen"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


HARD_GATE_FIELDS = {
    "predictability": "v31_predictability_status",
    "long_term_demand": "v31_long_term_demand_status",
    "moat": "v31_moat_status",
    "financial_safety": "v31_financial_safety_status",
    "earnings_authenticity": "v31_earnings_authenticity_status",
}

# Frozen V3.1 scoring weights. Predictability and financial safety are NOT
# scoring modules: they are hard gates above.
SCORE_WEIGHTS = {
    "long_term_demand": 10.0,
    "moat_direction": 20.0,
    "earnings_quality": 10.0,
    "roic_incremental_roic": 10.0,
    "capital_allocation": 8.0,
    "growth_runway": 10.0,
    "normalized_earnings_certainty": 7.0,
    "expectation_gap": 8.0,
    "valuation_margin_of_safety": 12.0,
    "market_position": 5.0,
}
SCORE_FIELDS = {name: f"v31_score_{name}" for name in SCORE_WEIGHTS}
A_TYPES = frozenset({"A1", "A2", "A3"})

# Actual execution universe. Broader names remain research-only.
SSE_EXECUTION_PREFIXES = ("600", "601", "603", "605")
SZSE_EXECUTION_PREFIXES = ("000", "001", "002", "003")

# These are V3.1 reference bands only. They are diagnostic, not universal buy
# gates; industry/capital-intensity judgement still has to explicitly pass.
REFERENCE_NEUTRAL_VALUE_BANDS = (
    (0.65, "EXTREME_MARGIN"),
    (0.75, "A_LEVEL_REFERENCE"),
    (0.85, "STAGED_BUY_REFERENCE"),
    (1.00, "WAIT_REFERENCE"),
    (1.20, "OVERVALUED_REFERENCE"),
    (math.inf, "SEVERELY_PRICED_IN_REFERENCE"),
)

# Frozen valuation-driven de-risking ladder. Ratios are current_price/base_value.
# 1.00: stop adding; 1.20: trim 25%; 1.40: cumulative 50%; 1.70: core only.
EXIT_REDUCE_25_RATIO = 1.20
EXIT_REDUCE_50_RATIO = 1.40
EXIT_CORE_ONLY_RATIO = 1.70


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _status(value: Any) -> Status:
    text = _text(value).upper()
    if text in {"PASS", "PASSED", "OK", "QUALIFIED", "TRUE", "YES", "STABLE", "STRENGTHENING"}:
        return Status.PASS
    if text in {"FAIL", "FAILED", "NO", "FALSE", "UNQUALIFIED", "RED", "STRUCTURAL_DECLINE", "WEAKENING"}:
        return Status.FAIL
    return Status.UNKNOWN


def _normalize_code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def execution_universe_status(code: Any) -> str:
    """Return EXECUTION_ELIGIBLE or RESEARCH_ONLY for a security code."""
    normalized = _normalize_code(code)
    if len(normalized) != 6 or not normalized.isdigit():
        return "UNKNOWN"
    if normalized.startswith(SSE_EXECUTION_PREFIXES):
        return "EXECUTION_ELIGIBLE"
    if normalized.startswith(SZSE_EXECUTION_PREFIXES):
        return "EXECUTION_ELIGIBLE"
    return "RESEARCH_ONLY"


def is_execution_universe_eligible(code: Any) -> bool:
    return execution_universe_status(code) == "EXECUTION_ELIGIBLE"


def merge_research_inputs(*sources: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge evidence without allowing later empty fields to erase earlier data."""
    merged: dict[str, Any] = {}
    for source in sources:
        if not source:
            continue
        for key, value in source.items():
            if key not in merged or not _text(merged.get(key)):
                merged[key] = value
    return merged


@dataclass(frozen=True)
class V31Assessment:
    hard_gates: dict[str, str]
    hard_gates_passed: bool
    hard_gate_failures: tuple[str, ...]
    hard_gate_unknowns: tuple[str, ...]
    score_points: dict[str, float | None]
    score_total: float | None
    score_complete: bool
    candidate_class: str
    a_eligible: bool
    execution_universe_status: str
    execution_universe_eligible: bool
    normalized_profit_ready: bool
    scenario_valuation_ready: bool
    implied_expectation_ready: bool
    expectation_gap_ready: bool
    risk_adjusted_cagr_ready: bool
    downside_ready: bool
    falsification_ready: bool
    margin_reference_band: str
    buy_conditions: dict[str, bool]
    buy_ready: bool
    exit_action: str
    exit_reason: str
    target_position_fraction: float | None
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "v31_policy_version": POLICY_VERSION,
            "v31_hard_gates_passed": self.hard_gates_passed,
            "v31_hard_gate_failures": ";".join(self.hard_gate_failures),
            "v31_hard_gate_unknowns": ";".join(self.hard_gate_unknowns),
            "v31_score_total": self.score_total,
            "v31_score_complete": self.score_complete,
            "v31_candidate_class": self.candidate_class,
            "v31_a_eligible": self.a_eligible,
            "v31_execution_universe_status": self.execution_universe_status,
            "v31_execution_universe_eligible": self.execution_universe_eligible,
            "v31_normalized_profit_ready": self.normalized_profit_ready,
            "v31_scenario_valuation_ready": self.scenario_valuation_ready,
            "v31_implied_expectation_ready": self.implied_expectation_ready,
            "v31_expectation_gap_ready": self.expectation_gap_ready,
            "v31_risk_adjusted_cagr_ready": self.risk_adjusted_cagr_ready,
            "v31_downside_ready": self.downside_ready,
            "v31_falsification_ready": self.falsification_ready,
            "v31_margin_reference_band": self.margin_reference_band,
            "v31_buy_ready": self.buy_ready,
            "v31_exit_action": self.exit_action,
            "v31_exit_reason": self.exit_reason,
            "v31_target_position_fraction": self.target_position_fraction,
            "v31_blockers": ";".join(self.blockers),
        }
        for name, status in self.hard_gates.items():
            result[f"v31_gate_{name}"] = status
        for name, points in self.score_points.items():
            result[f"v31_score_{name}"] = points
        for name, passed in self.buy_conditions.items():
            result[f"v31_buy_condition_{name}"] = passed
        return result


def _hard_gates(data: Mapping[str, Any]) -> tuple[dict[str, str], tuple[str, ...], tuple[str, ...]]:
    gates: dict[str, str] = {}
    failures: list[str] = []
    unknowns: list[str] = []
    for name, field in HARD_GATE_FIELDS.items():
        status = _status(data.get(field))
        gates[name] = status.value
        if status is Status.FAIL:
            failures.append(name)
        elif status is Status.UNKNOWN:
            unknowns.append(name)
    return gates, tuple(failures), tuple(unknowns)


def _score(data: Mapping[str, Any]) -> tuple[dict[str, float | None], float | None, bool]:
    points: dict[str, float | None] = {}
    complete = True
    for name, maximum in SCORE_WEIGHTS.items():
        value = _finite(data.get(SCORE_FIELDS[name]))
        if value is None:
            points[name] = None
            complete = False
            continue
        if value < 0.0 or value > maximum:
            points[name] = None
            complete = False
            continue
        points[name] = value
    total = round(sum(value for value in points.values() if value is not None), 2) if complete else None
    return points, total, complete


def _normalized_profit_ready(data: Mapping[str, Any]) -> bool:
    profit = _finite(data.get("v31_normalized_profit"))
    method = _text(data.get("v31_normalized_profit_method"))
    return profit is not None and profit > 0.0 and bool(method)


def _scenario_values(data: Mapping[str, Any]) -> tuple[bool, float | None, float | None, float | None, float | None]:
    bear = _finite(data.get("v31_pessimistic_value"))
    base = _finite(data.get("v31_neutral_value"))
    bull = _finite(data.get("v31_optimistic_value"))
    stress = _finite(data.get("v31_extreme_stress_value"))
    ready = all(value is not None and value > 0.0 for value in (bear, base, bull, stress))
    if ready:
        ready = bool(stress <= bear <= base <= bull)
    return ready, bear, base, bull, stress


def margin_reference_band(current_price: Any, neutral_value: Any) -> str:
    current = _finite(current_price)
    neutral = _finite(neutral_value)
    if current is None or neutral is None or current <= 0.0 or neutral <= 0.0:
        return "UNKNOWN"
    ratio = current / neutral
    for upper, label in REFERENCE_NEUTRAL_VALUE_BANDS:
        if ratio <= upper:
            return label
    return "UNKNOWN"


def exit_action_from_valuation(
    *,
    current_price: Any,
    neutral_value: Any,
    hard_gate_failures: tuple[str, ...] = (),
) -> tuple[str, str, float | None]:
    """Return the frozen V3.1 valuation/fundamental exit action.

    EXIT is reserved for broken hard logic. With fundamentals intact, valuation
    drives staged de-risking rather than all-or-nothing liquidation.
    """
    if hard_gate_failures:
        return (
            "EXIT",
            "hard_logic_broken:" + ";".join(hard_gate_failures),
            0.0,
        )
    current = _finite(current_price)
    neutral = _finite(neutral_value)
    if current is None or neutral is None or current <= 0.0 or neutral <= 0.0:
        return "HOLD_REVIEW", "valuation_incomplete", None
    ratio = current / neutral
    if ratio >= EXIT_CORE_ONLY_RATIO:
        return "CORE_ONLY", f"price_to_neutral={ratio:.3f}>=1.70", 0.25
    if ratio >= EXIT_REDUCE_50_RATIO:
        return "REDUCE_50", f"price_to_neutral={ratio:.3f}>=1.40", 0.50
    if ratio >= EXIT_REDUCE_25_RATIO:
        return "REDUCE_25", f"price_to_neutral={ratio:.3f}>=1.20", 0.75
    if ratio >= 1.00:
        return "HOLD_NO_ADD", f"price_to_neutral={ratio:.3f}>=1.00", 1.00
    return "HOLD", f"price_to_neutral={ratio:.3f}<1.00", 1.00


def _explicit_pass(data: Mapping[str, Any], field: str) -> bool:
    return _status(data.get(field)) is Status.PASS


def assess_v31(data: Mapping[str, Any]) -> V31Assessment:
    gates, failures, unknowns = _hard_gates(data)
    hard_pass = not failures and not unknowns
    score_points, score_total, score_complete = _score(data)

    normalized_profit_ready = _normalized_profit_ready(data)
    scenarios_ready, bear, base, _bull, stress = _scenario_values(data)

    implied_growth = _finite(data.get("v31_market_implied_profit_cagr"))
    realistic_growth = _finite(data.get("v31_realistic_profit_cagr"))
    implied_ready = implied_growth is not None and realistic_growth is not None

    expectation_gap = _finite(data.get("v31_expectation_gap_pct"))
    expectation_gap_thesis = _text(data.get("v31_expectation_gap_thesis"))
    expectation_gap_ready = expectation_gap is not None and bool(expectation_gap_thesis)

    risk_adjusted_cagr = _finite(data.get("v31_risk_adjusted_3y_cagr"))
    risk_adjusted_cagr_ready = risk_adjusted_cagr is not None

    current = _finite(data.get("v31_current_price"))
    if current is None:
        current = _finite(data.get("raw_latest_close"))
    downside_ready = bool(
        scenarios_ready
        and current is not None
        and current > 0.0
        and bear is not None
        and stress is not None
        and _finite(data.get("v31_potential_max_fundamental_loss_pct")) is not None
    )

    why_buy = _text(data.get("v31_why_can_buy"))
    bear_case = _text(data.get("v31_strongest_bear_case"))
    falsification_ready = bool(
        why_buy and bear_case and _explicit_pass(data, "v31_falsification_status")
    )

    requested_class = _text(data.get("v31_candidate_class")).upper()
    class_is_a = requested_class in A_TYPES
    a_eligible = bool(hard_pass and class_is_a)
    if requested_class in A_TYPES and not hard_pass:
        candidate_class = "B"
    elif requested_class in {"B", "C"}:
        candidate_class = requested_class
    elif class_is_a:
        candidate_class = requested_class
    else:
        candidate_class = "PENDING"

    code = data.get("code") or data.get("stock_code") or data.get("symbol")
    exec_status = execution_universe_status(code)
    exec_eligible = exec_status == "EXECUTION_ELIGIBLE"

    margin_band = margin_reference_band(current, base)
    exit_action, exit_reason, target_position_fraction = exit_action_from_valuation(
        current_price=current,
        neutral_value=base,
        hard_gate_failures=failures,
    )

    buy_conditions = {
        "all_hard_logic_gates": hard_pass,
        "execution_universe_eligible": exec_eligible,
        "clear_margin_of_safety": scenarios_ready and _explicit_pass(data, "v31_margin_of_safety_status"),
        "attractive_risk_adjusted_3y_cagr": risk_adjusted_cagr_ready and _explicit_pass(data, "v31_cagr_attractiveness_status"),
        "pessimistic_loss_tolerable": downside_ready and _explicit_pass(data, "v31_pessimistic_loss_status"),
        "portfolio_exposure_acceptable": _explicit_pass(data, "v31_portfolio_exposure_status"),
        "market_position_not_extreme_chase": _explicit_pass(data, "v31_market_position_status"),
    }

    blockers: list[str] = []
    blockers.extend(f"hard_gate_failed:{name}" for name in failures)
    blockers.extend(f"hard_gate_unknown:{name}" for name in unknowns)
    if not class_is_a:
        blockers.append("a_class_not_proven")
    if not exec_eligible:
        blockers.append(f"execution_universe_blocked:{exec_status}")
    if not score_complete:
        blockers.append("v31_score_incomplete")
    if not normalized_profit_ready:
        blockers.append("normalized_profit_incomplete")
    if not scenarios_ready:
        blockers.append("scenario_valuation_incomplete")
    if not implied_ready:
        blockers.append("implied_expectation_incomplete")
    if not expectation_gap_ready:
        blockers.append("expectation_gap_incomplete")
    if not risk_adjusted_cagr_ready:
        blockers.append("risk_adjusted_3y_cagr_incomplete")
    if not downside_ready:
        blockers.append("downside_analysis_incomplete")
    if not falsification_ready:
        blockers.append("falsification_incomplete")
    for name, passed in buy_conditions.items():
        if not passed:
            blockers.append(f"buy_condition_failed:{name}")

    buy_ready = bool(
        a_eligible
        and exec_eligible
        and score_complete
        and normalized_profit_ready
        and scenarios_ready
        and implied_ready
        and expectation_gap_ready
        and risk_adjusted_cagr_ready
        and downside_ready
        and falsification_ready
        and all(buy_conditions.values())
    )

    return V31Assessment(
        hard_gates=gates,
        hard_gates_passed=hard_pass,
        hard_gate_failures=failures,
        hard_gate_unknowns=unknowns,
        score_points=score_points,
        score_total=score_total,
        score_complete=score_complete,
        candidate_class=candidate_class,
        a_eligible=a_eligible,
        execution_universe_status=exec_status,
        execution_universe_eligible=exec_eligible,
        normalized_profit_ready=normalized_profit_ready,
        scenario_valuation_ready=scenarios_ready,
        implied_expectation_ready=implied_ready,
        expectation_gap_ready=expectation_gap_ready,
        risk_adjusted_cagr_ready=risk_adjusted_cagr_ready,
        downside_ready=downside_ready,
        falsification_ready=falsification_ready,
        margin_reference_band=margin_band,
        buy_conditions=buy_conditions,
        buy_ready=buy_ready,
        exit_action=exit_action,
        exit_reason=exit_reason,
        target_position_fraction=target_position_fraction,
        blockers=tuple(dict.fromkeys(blockers)),
    )


def enrich_with_v31(data: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(data)
    row.update(assess_v31(row).as_dict())
    return row
