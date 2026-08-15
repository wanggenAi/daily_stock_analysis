"""Risk-capped all-A production entrypoint with scoped production policies."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import opportunity_report_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    """Run the production policy stack without leaking monkeypatch state.

    The production policies intentionally patch the already-tested core engine
    instead of forking it. Those patches are process-global, so this entrypoint
    snapshots the caller's state, installs the complete production stack for the
    scan, and restores the snapshot in ``finally``. This makes repeated invocations,
    test suites, notebooks, and long-lived workers deterministic.
    """

    event_base = complete_material_event_pagination.base
    core = opportunity_engine_policy.core
    pipeline = opportunity_pipeline_policy.pipeline

    original_runtime = {
        "cninfo": event_base._query_cninfo_material_events,
        "sse": event_base._query_sse_material_events,
        "strict_candidate_checks": core.strict_candidate_checks,
        "classify_candidate": core.classify_candidate,
        "apply_position_budget": core._apply_position_budget,
        "build_daily_signals": core.build_daily_signals,
        "exit_profile_strategy_health": core._exit_profile_strategy_health,
        "build_quant_rows": pipeline._build_quant_rows,
        "screen_blockers": pipeline._screen_blockers,
        "screen_status": pipeline._screen_status,
        "tier_row": pipeline._tier_row,
        "research_queues": pipeline._research_queues,
    }
    original_columns = {
        "plan": list(core.PLAN_COLUMNS),
        "top5": list(core.TOP5_COLUMNS),
        "quant": list(pipeline.QUANT_COLUMNS),
        "opportunity": list(pipeline.OPPORTUNITY_COLUMNS),
    }

    complete_material_event_pagination.install()
    try:
        # Upstream discovery: remove only the legacy low-price coupling that would
        # otherwise discard strong-trend/earnings research objects too early.
        opportunity_pipeline_policy.install()

        # Research ranking: valley repair keeps the legacy score; non-valley
        # engines reuse the legacy non-price factors renormalized to 100%.
        opportunity_queue_policy.install()

        # Final opportunity shape: replace only the universal <=35% gate with the
        # explicit engine gate. All non-price strict gates remain authoritative.
        opportunity_engine_policy.install()

        # Report schema only: persist engine/factor diagnostics in fixed-column
        # candidate reports without changing eligibility or ranking.
        opportunity_report_policy.install()

        # The risk-capped layer is last because it owns classification/sizing and
        # may relax exit-history uncertainty only. It does not relax other gates.
        return risk_capped.main(argv)
    finally:
        event_base._query_cninfo_material_events = original_runtime["cninfo"]
        event_base._query_sse_material_events = original_runtime["sse"]
        core.strict_candidate_checks = original_runtime["strict_candidate_checks"]
        core.classify_candidate = original_runtime["classify_candidate"]
        core._apply_position_budget = original_runtime["apply_position_budget"]
        core.build_daily_signals = original_runtime["build_daily_signals"]
        core._exit_profile_strategy_health = original_runtime["exit_profile_strategy_health"]
        pipeline._build_quant_rows = original_runtime["build_quant_rows"]
        pipeline._screen_blockers = original_runtime["screen_blockers"]
        pipeline._screen_status = original_runtime["screen_status"]
        pipeline._tier_row = original_runtime["tier_row"]
        pipeline._research_queues = original_runtime["research_queues"]
        core.PLAN_COLUMNS[:] = original_columns["plan"]
        core.TOP5_COLUMNS[:] = original_columns["top5"]
        pipeline.QUANT_COLUMNS[:] = original_columns["quant"]
        pipeline.OPPORTUNITY_COLUMNS[:] = original_columns["opportunity"]


if __name__ == "__main__":
    raise SystemExit(main())
