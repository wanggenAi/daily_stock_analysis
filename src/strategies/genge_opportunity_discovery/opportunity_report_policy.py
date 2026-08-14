"""Fixed-column report contract for multi-engine opportunity diagnostics.

The engine evaluator already records its decision on mutable candidate rows.
This module makes those diagnostics survive the fixed-column CSV writers used
by the all-A production reports. It changes report schema only; it does not
change candidate classification, ranking, sizing, or signal eligibility.
"""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core


ENGINE_REPORT_COLUMNS = (
    "opportunity_engine",
    "opportunity_engine_eligible",
    "opportunity_engine_reason",
    "factor_validity_status",
    "earnings_inflection_confirmed",
)


def install() -> None:
    """Expose engine diagnostics in all fixed candidate report schemas.

    ``TOP5_COLUMNS`` was constructed from ``PLAN_COLUMNS`` at module import, so
    both lists must be extended explicitly. Membership checks keep repeated
    installation idempotent in tests and long-lived processes.
    """

    for columns in (core.PLAN_COLUMNS, core.TOP5_COLUMNS):
        for column in ENGINE_REPORT_COLUMNS:
            if column not in columns:
                columns.append(column)
