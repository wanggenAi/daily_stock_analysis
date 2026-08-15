from __future__ import annotations

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core
from src.strategies.genge_opportunity_discovery import opportunity_report_policy as policy


def test_engine_diagnostics_are_exposed_in_fixed_candidate_reports():
    original_plan = list(core.PLAN_COLUMNS)
    original_top5 = list(core.TOP5_COLUMNS)
    try:
        policy.install()

        for column in policy.ENGINE_REPORT_COLUMNS:
            assert column in core.PLAN_COLUMNS
            assert column in core.TOP5_COLUMNS
    finally:
        core.PLAN_COLUMNS[:] = original_plan
        core.TOP5_COLUMNS[:] = original_top5


def test_report_policy_install_is_idempotent():
    original_plan = list(core.PLAN_COLUMNS)
    original_top5 = list(core.TOP5_COLUMNS)
    try:
        policy.install()
        policy.install()

        for column in policy.ENGINE_REPORT_COLUMNS:
            assert core.PLAN_COLUMNS.count(column) == 1
            assert core.TOP5_COLUMNS.count(column) == 1
    finally:
        core.PLAN_COLUMNS[:] = original_plan
        core.TOP5_COLUMNS[:] = original_top5
