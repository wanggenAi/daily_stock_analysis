"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import opportunity_report_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate. The production
    # collector hook is process-global, so keep it scoped to this scan invocation
    # and restore the caller's provider functions afterwards.
    base = complete_material_event_pagination.base
    original_cninfo = base._query_cninfo_material_events
    original_sse = base._query_sse_material_events
    original_build_quant_rows = opportunity_pipeline_policy.pipeline._build_quant_rows
    original_screen_blockers = opportunity_pipeline_policy.pipeline._screen_blockers
    original_screen_status = opportunity_pipeline_policy.pipeline._screen_status
    original_tier_row = opportunity_pipeline_policy.pipeline._tier_row
    original_research_queues = opportunity_queue_policy.pipeline._research_queues
    original_strict_checks = opportunity_engine_policy.core.strict_candidate_checks
    plan_columns = list(opportunity_report_policy.core.PLAN_COLUMNS)
    top5_columns = list(opportunity_report_policy.core.TOP5_COLUMNS)
    quant_columns = list(opportunity_pipeline_policy.pipeline.QUANT_COLUMNS)
    opportunity_columns = list(opportunity_pipeline_policy.pipeline.OPPORTUNITY_COLUMNS)

    complete_material_event_pagination.install()
    opportunity_pipeline_policy.install()
    opportunity_queue_policy.install()
    opportunity_engine_policy.install()
    opportunity_report_policy.install()
    try:
        return risk_capped.main(argv)
    finally:
        base._query_cninfo_material_events = original_cninfo
        base._query_sse_material_events = original_sse
        opportunity_pipeline_policy.pipeline._build_quant_rows = original_build_quant_rows
        opportunity_pipeline_policy.pipeline._screen_blockers = original_screen_blockers
        opportunity_pipeline_policy.pipeline._screen_status = original_screen_status
        opportunity_pipeline_policy.pipeline._tier_row = original_tier_row
        opportunity_queue_policy.pipeline._research_queues = original_research_queues
        opportunity_engine_policy.core.strict_candidate_checks = original_strict_checks
        opportunity_report_policy.core.PLAN_COLUMNS[:] = plan_columns
        opportunity_report_policy.core.TOP5_COLUMNS[:] = top5_columns
        opportunity_pipeline_policy.pipeline.QUANT_COLUMNS[:] = quant_columns
        opportunity_pipeline_policy.pipeline.OPPORTUNITY_COLUMNS[:] = opportunity_columns


if __name__ == "__main__":
    raise SystemExit(main())
