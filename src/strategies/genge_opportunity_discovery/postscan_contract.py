"""Execution-scoped helpers for the GenGe postscan production contract."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .selection_framework_v31 import execution_universe_status

UNRESOLVED_ZERO_BUY_TOKENS = frozenset(
    {
        "valuation_missing",
        "valuation_model_not_executed",
        "valuation_diagnostic_not_ready",
        "financial_review_not_ready",
        "required_profit_growth_unavailable",
    }
)


def execution_eligible_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return only rows eligible to become an actual production trade candidate."""
    return [
        row
        for row in rows
        if execution_universe_status(row.get("code")) == "EXECUTION_ELIGIBLE"
    ]


def unresolved_execution_gaps(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Find unresolved zero-BUY research gaps only inside the execution universe.

    Research-only boards remain visible in research artifacts, but their incomplete
    valuation diagnostics must not make the executable沪/深A production contract fail.
    """
    blocker_counts: Counter[str] = Counter()
    for row in execution_eligible_rows(rows):
        for token in str(row.get("long_term_blockers") or "").split(";"):
            token = token.strip()
            if token:
                blocker_counts[token] += 1
    return sorted(token for token in UNRESOLVED_ZERO_BUY_TOKENS if blocker_counts[token])
