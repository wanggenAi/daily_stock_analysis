"""Strict structural hard-logic gate for long-horizon company research.

This module intentionally separates *why the business should become more valuable*
from valuation, quant ranking, and technical timing.  A cheap PE, a high Quant
score, a clean research-candidate flag, or an earnings-quality score can never by
itself create HARD_LOGIC_PASS.

A PASS requires an auditable structural thesis chain:

    structural industry demand/driver
        -> company-specific durable edge
        -> explicit earnings/profit transmission
        -> persistence of at least ~3 years
        -> falsifiable invalidation conditions
        -> source/evidence references

Supply constraint evidence is valuable and scored, but is not mandatory for every
business archetype (for example, software network effects or brand pricing power
can be durable without a literal physical supply constraint).

Outputs are research states only and never authorize automatic trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


NON_COMPANY_GATE_TOKENS = frozenset(
    {
        "price_too_high",
        "board_5d_abnormal_move",
        "board_10d_abnormal_move",
        "ma20_not_ready",
        "ma60_not_ready",
        "price_above_ma20_limit",
        "price_above_ma60_limit",
        "too_far_from_ma20",
        "too_far_from_ma60",
        "reward_risk_below_min",
        "rr_below_min",
        "entry_not_ready",
        "market_regime_not_ready",
    }
)
NON_COMPANY_GATE_PREFIXES = (
    "exit_profile_",
    "profile_validation_",
    "profile_data_",
    "technical_",
    "timing_",
    "ma5_",
    "ma10_",
    "ma20_",
    "ma60_",
    "market_",
    "industry_timing_",
    "entry_",
    "breakout_",
    "pullback_",
    "stop_",
    "invalidation_",
    "reward_risk_",
    "risk_reward_",
    "rr_",
    "position_",
    "sizing_",
    "execution_",
    "liquidity_timing_",
    "volume_timing_",
)

COMPANY_BLOCKER_FIELDS = (
    "hard_blockers",
    "source_hard_blockers",
    "hard_reject_blockers",
)
NON_VETO_CONTEXT_FIELDS = (
    "strict_gate_failed",
    "missing_conditions",
    "classification_missing_conditions",
)

DRIVER_FIELDS = (
    "hard_logic_structural_driver",
    "hard_logic_industry_driver",
    "structural_industry_driver",
    "industry_structural_driver",
    "structural_demand_driver",
)
SUPPLY_CONSTRAINT_FIELDS = (
    "hard_logic_supply_constraint",
    "structural_supply_constraint",
    "industry_supply_constraint",
    "supply_constraint_evidence",
)
COMPANY_EDGE_FIELDS = (
    "hard_logic_company_edge",
    "company_specific_edge",
    "durable_competitive_advantage",
    "competitive_advantage_evidence",
    "moat_evidence",
)
PROFIT_TRANSMISSION_FIELDS = (
    "hard_logic_profit_transmission",
    "profit_transmission_chain",
    "earnings_transmission_chain",
    "earnings_transmission",
)
INVALIDATION_FIELDS = (
    "hard_logic_invalidation",
    "hard_logic_invalidation_conditions",
    "thesis_invalidation",
    "thesis_invalidation_conditions",
)
SOURCE_FIELDS = (
    "hard_logic_evidence_sources",
    "hard_logic_source_refs",
    "hard_logic_source_references",
    "thesis_source_refs",
    "thesis_evidence_sources",
)
DURATION_FIELDS = (
    "hard_logic_duration_years",
    "hard_logic_persistence_years",
    "thesis_duration_years",
)
PERSISTENCE_FIELDS = (
    "hard_logic_persistence",
    "hard_logic_horizon",
    "thesis_persistence",
    "thesis_horizon",
)

EXPLICIT_PASS_STATES = {"PASS", "PASSED", "STRONG", "CONFIRMED", "HARD_LOGIC_PASS"}
EXPLICIT_FAIL_STATES = {"FAIL", "FAILED", "BLOCKED", "REJECT", "HARD_REJECT"}

PERSISTENT_TOKENS = (
    "STRUCTURAL",
    "LONG_TERM",
    "LONG-TERM",
    "MULTI_YEAR",
    "MULTI-YEAR",
    "3Y",
    "3_YEAR",
    "3-YEAR",
    "5Y",
    "5_YEAR",
    "5-YEAR",
    "长期",
    "结构性",
    "三年",
    "五年",
)


@dataclass(frozen=True)
class HardLogicEvaluation:
    state: str
    score: int
    reasons: tuple[str, ...]
    structural_blockers: tuple[str, ...]
    non_veto_context: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    structural_driver: str
    supply_constraint: str
    company_edge: str
    profit_transmission: str
    invalidation: str
    evidence_sources: str
    duration_years: float | None
    persistence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "hard_logic_state": self.state,
            "hard_logic_score": self.score,
            "hard_logic_reasons": ";".join(self.reasons),
            "hard_logic_missing_evidence": ";".join(self.missing_evidence),
            "hard_logic_structural_driver": self.structural_driver,
            "hard_logic_supply_constraint": self.supply_constraint,
            "hard_logic_company_edge": self.company_edge,
            "hard_logic_profit_transmission": self.profit_transmission,
            "hard_logic_invalidation": self.invalidation,
            "hard_logic_evidence_sources": self.evidence_sources,
            "hard_logic_duration_years": self.duration_years,
            "hard_logic_persistence": self.persistence,
            "structural_blockers": ";".join(self.structural_blockers),
            "non_veto_context": ";".join(self.non_veto_context),
            "hard_logic_evidence_required": True,
            "quant_rank_is_hard_logic": False,
            "valuation_is_hard_logic": False,
            "technical_context_is_non_veto": True,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _first_text(row: Mapping[str, Any], fields: Iterable[str]) -> str:
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def _first_finite(row: Mapping[str, Any], fields: Iterable[str]) -> float | None:
    for field in fields:
        value = _finite(row.get(field))
        if value is not None:
            return value
    return None


def _split_tokens(value: Any) -> set[str]:
    return {token.strip() for token in str(value or "").split(";") if token.strip()}


def _is_non_company_gate(token: str) -> bool:
    return token in NON_COMPANY_GATE_TOKENS or token.startswith(NON_COMPANY_GATE_PREFIXES)


def _blocker_partition(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    structural: set[str] = set()
    context: set[str] = set()
    for field in COMPANY_BLOCKER_FIELDS:
        for token in _split_tokens(row.get(field)):
            if _is_non_company_gate(token):
                context.add(token)
            else:
                structural.add(token)
    for field in NON_VETO_CONTEXT_FIELDS:
        context.update(_split_tokens(row.get(field)))
    return sorted(structural), sorted(context)


def _explicit_state(row: Mapping[str, Any]) -> str:
    return str(row.get("hard_logic_state") or row.get("hard_logic_status") or "").strip().upper()


def _substantive(text: str, minimum_chars: int = 6) -> bool:
    compact = "".join(text.split())
    return len(compact) >= minimum_chars


def _durability(row: Mapping[str, Any]) -> tuple[bool, float | None, str]:
    years = _first_finite(row, DURATION_FIELDS)
    persistence = _first_text(row, PERSISTENCE_FIELDS)
    if years is not None:
        return years >= 3.0, years, persistence
    normalized = persistence.upper().replace(" ", "_")
    return any(token in normalized or token in persistence for token in PERSISTENT_TOKENS), None, persistence


def evaluate_hard_logic(row: Mapping[str, Any]) -> HardLogicEvaluation:
    """Evaluate structural thesis evidence without using valuation or Quant rank as proof."""
    structural, context = _blocker_partition(row)
    explicit = _explicit_state(row)
    reasons: list[str] = []

    if explicit in EXPLICIT_FAIL_STATES:
        structural = sorted(set(structural + [f"explicit_hard_logic_state={explicit}"]))
    if structural:
        return HardLogicEvaluation(
            state="BLOCKED",
            score=0,
            reasons=("structural_hard_risk_present",),
            structural_blockers=tuple(structural),
            non_veto_context=tuple(context),
            missing_evidence=(),
            structural_driver="",
            supply_constraint="",
            company_edge="",
            profit_transmission="",
            invalidation="",
            evidence_sources="",
            duration_years=None,
            persistence="",
        )

    driver = _first_text(row, DRIVER_FIELDS)
    supply = _first_text(row, SUPPLY_CONSTRAINT_FIELDS)
    edge = _first_text(row, COMPANY_EDGE_FIELDS)
    transmission = _first_text(row, PROFIT_TRANSMISSION_FIELDS)
    invalidation = _first_text(row, INVALIDATION_FIELDS)
    sources = _first_text(row, SOURCE_FIELDS)
    durable, years, persistence = _durability(row)

    checks = {
        "structural_driver": _substantive(driver, 8),
        "company_edge": _substantive(edge, 6),
        "profit_transmission": _substantive(transmission, 8),
        "invalidation": _substantive(invalidation, 6),
        "evidence_sources": _substantive(sources, 4),
        "durability_3y_plus": durable,
    }
    missing = [name for name, passed in checks.items() if not passed]

    score = 0
    if checks["structural_driver"]:
        score += 20
        reasons.append("structural_industry_driver_evidenced")
    if _substantive(supply, 6):
        score += 5
        reasons.append("supply_constraint_or_scarcity_evidenced")
    if checks["company_edge"]:
        score += 20
        reasons.append("company_specific_durable_edge_evidenced")
    if checks["profit_transmission"]:
        score += 20
        reasons.append("profit_transmission_chain_evidenced")
    if checks["invalidation"]:
        score += 10
        reasons.append("thesis_invalidation_defined")
    if checks["durability_3y_plus"]:
        score += 15
        reasons.append("multi_year_persistence_evidenced")
    if checks["evidence_sources"]:
        score += 10
        reasons.append("evidence_sources_present")

    quality = _finite(row.get("earnings_quality_score"))
    if quality is not None and quality < 50:
        missing.append("earnings_quality_confirmation")
        reasons.append("weak_earnings_quality_requires_review")

    if explicit in EXPLICIT_PASS_STATES and missing:
        reasons.append("explicit_pass_not_trusted_without_structured_evidence")

    if missing:
        reasons.append("hard_logic_confirmation_incomplete")
        reasons.append("valuation_or_quant_cannot_substitute_for_hard_logic")
        state = "REVIEW"
    elif score >= 90:
        state = "PASS"
        reasons.append("hard_logic_chain_complete")
    else:
        state = "REVIEW"
        reasons.append("hard_logic_score_below_pass_threshold")

    if context:
        reasons.append("execution_context_ignored_for_company_quality")

    return HardLogicEvaluation(
        state=state,
        score=score,
        reasons=tuple(reasons),
        structural_blockers=tuple(structural),
        non_veto_context=tuple(context),
        missing_evidence=tuple(sorted(set(missing))),
        structural_driver=driver,
        supply_constraint=supply,
        company_edge=edge,
        profit_transmission=transmission,
        invalidation=invalidation,
        evidence_sources=sources,
        duration_years=years,
        persistence=persistence,
    )


def hard_logic_assessment(row: Mapping[str, Any]) -> tuple[str, list[str], list[str], list[str]]:
    """Compatibility shape consumed by hard_logic_price_map.build_price_expectation_row."""
    evaluation = evaluate_hard_logic(row)
    return (
        evaluation.state,
        list(evaluation.reasons),
        list(evaluation.structural_blockers),
        list(evaluation.non_veto_context),
    )


def enrich_with_hard_logic(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output.update(evaluate_hard_logic(row).as_dict())
    return output
