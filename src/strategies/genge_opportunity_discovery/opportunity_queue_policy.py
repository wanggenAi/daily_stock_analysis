"""Engine-aware research-queue ranking for opportunity discovery.

The legacy quant score allocates 26% of its weight to historic low-price
positioning. That remains appropriate for VALLEY_REPAIR, but using the same
score to truncate strong-trend and earnings-inflection research queues would
reintroduce the old low-price bias before final strict evaluation.

This module changes research prioritization and report observability only. It
does not create formal signals, reserve per-engine quotas, or relax any hard
gate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core
from src.strategies.genge_opportunity_discovery import pipeline


NON_PRICE_LEGACY_WEIGHT = 0.74
ENGINE_RESEARCH_SCORE_COLUMN = "engine_research_score"
ENGINE_RANKED_RESEARCH = frozenset({"STRONG_TREND_RESEARCH", "EARNINGS_INFLECTION"})
ENGINE_REPORT_COLUMNS = (
    "opportunity_engine",
    "opportunity_engine_eligible",
    "opportunity_engine_reason",
    "factor_validity_status",
    "factor_ic",
    "factor_ic_sample_count",
    "factor_ic_monitor_rule_version",
    "valley_factor_validity_status",
    "valley_factor_ic",
    "valley_factor_ic_sample_count",
    "trend_factor_validity_status",
    "trend_factor_ic",
    "trend_factor_ic_sample_count",
    "earnings_factor_validity_status",
    "earnings_factor_ic",
    "earnings_factor_ic_sample_count",
    "earnings_inflection_confirmed",
    ENGINE_RESEARCH_SCORE_COLUMN,
)

_ORIGINAL_RESEARCH_QUEUES = pipeline._research_queues


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def engine_research_score(row: Mapping[str, Any]) -> float:
    """Use the legacy score for valley setups and a price-neutral version otherwise.

    For the two non-valley engines we reuse the exact non-price components and
    weights from the existing quant score, then renormalize their 74% total to
    100%. No new subjective factor or bonus is introduced.
    """

    legacy = _finite_float(row.get("quant_score")) or 0.0
    engine = str(row.get("preliminary_opportunity_engine") or "").upper()
    if engine not in ENGINE_RANKED_RESEARCH:
        return round(max(0.0, min(100.0, legacy)), 4)

    execution = 100.0 - min(
        100.0,
        max(0.0, _finite_float(row.get("execution_risk_score")) or 0.0),
    )
    value_trap = 100.0 - min(
        100.0,
        max(0.0, _finite_float(row.get("value_trap_score")) or 0.0),
    )
    relative_inputs = [
        value
        for value in (
            _finite_float(row.get("relative_strength_20d")),
            _finite_float(row.get("relative_strength_60d")),
        )
        if value is not None
    ]
    relative = 50.0
    if relative_inputs:
        relative = max(
            0.0,
            min(100.0, 50.0 + sum(relative_inputs) / len(relative_inputs) * 2.0),
        )

    non_price = (
        (_finite_float(row.get("trend_stabilization_score")) or 0.0) * 0.22
        + (_finite_float(row.get("valuation_score")) or 0.0) * 0.14
        + (_finite_float(row.get("financial_safety_score")) or 0.0) * 0.16
        + execution * 0.10
        + value_trap * 0.08
        + relative * 0.04
    )
    return round(max(0.0, min(100.0, non_price / NON_PRICE_LEGACY_WEIGHT)), 4)


def _score_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    scored = list(rows)
    for row in scored:
        if isinstance(row, MutableMapping):
            row[ENGINE_RESEARCH_SCORE_COLUMN] = engine_research_score(row)
    return scored


def research_queues(
    rows: list[dict[str, Any]],
    priority_queue_size: int,
    secondary_queue_size: int,
    priority_codes: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Preserve queue membership semantics while ranking by engine-aware quality.

    There is deliberately no minimum allocation or quota for any engine. The
    existing queue sizes and priority-code behavior stay authoritative.
    """

    _score_rows(rows)
    priority_code_set = {pipeline._normalize_code(code) for code in priority_codes}
    primary_rows = [
        row for row in rows if row.get("quant_screen_status") == "PRIORITY_RESEARCH"
    ]
    promoted_rows = [
        row
        for row in rows
        if row.get("quant_screen_status") != "PRIORITY_RESEARCH"
        and pipeline._normalize_code(row.get("code")) in priority_code_set
    ]

    def score(item: Mapping[str, Any]) -> float:
        return _finite_float(item.get(ENGINE_RESEARCH_SCORE_COLUMN)) or engine_research_score(item)

    priority_queue = sorted(
        [*primary_rows, *promoted_rows],
        key=lambda item: (
            pipeline._normalize_code(item.get("code")) in priority_code_set,
            score(item),
        ),
        reverse=True,
    )[: max(0, int(priority_queue_size))]
    secondary_queue = sorted(
        [
            row
            for row in rows
            if row.get("quant_screen_status") == "SECONDARY_RESEARCH"
            and pipeline._normalize_code(row.get("code")) not in priority_code_set
        ],
        key=score,
        reverse=True,
    )[: max(0, int(secondary_queue_size))]
    return priority_queue, secondary_queue


def _append_once(columns: list[str], names: Iterable[str]) -> None:
    for name in names:
        if name not in columns:
            columns.append(name)


def install() -> None:
    """Install price-neutral ranking and expose engine diagnostics in reports."""

    if pipeline._research_queues is not research_queues:
        pipeline._research_queues = research_queues
    _append_once(pipeline.QUANT_COLUMNS, (ENGINE_RESEARCH_SCORE_COLUMN,))
    _append_once(pipeline.OPPORTUNITY_COLUMNS, (ENGINE_RESEARCH_SCORE_COLUMN,))
    _append_once(core.PLAN_COLUMNS, ENGINE_REPORT_COLUMNS)
    _append_once(core.TOP5_COLUMNS, ENGINE_REPORT_COLUMNS)
