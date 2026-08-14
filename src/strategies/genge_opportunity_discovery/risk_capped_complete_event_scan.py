"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate. The provider
    # functions are process-global, so restore the caller's original functions
    # after this production invocation instead of leaking adaptive pagination to
    # unrelated tests or later work in a long-lived process.
    event_base = complete_material_event_pagination.base
    original_cninfo = event_base._query_cninfo_material_events
    original_sse = event_base._query_sse_material_events
    complete_material_event_pagination.install()

    try:
        # The funnel patch prevents the legacy low-price assumption from discarding
        # strong-trend/earnings research objects before final strict evaluation.
        # It never creates a formal signal or relaxes non-price hard blockers.
        opportunity_pipeline_policy.install()

        # The legacy quant score gives historic low-price positioning 26% weight.
        # Keep it unchanged for valley repair, but rank the two non-valley research
        # engines on the same legacy non-price factors renormalized to 100%. This
        # affects research truncation only and introduces no per-engine quota.
        opportunity_queue_policy.install()

        # Replace only the final universal low-price gate with explicit engine
        # admission. All existing strict safety/risk gates remain in force; the
        # risk-capped wrapper may still relax exit-history uncertainty only.
        opportunity_engine_policy.install()
        return risk_capped.main(argv)
    finally:
        event_base._query_cninfo_material_events = original_cninfo
        event_base._query_sse_material_events = original_sse


if __name__ == "__main__":
    raise SystemExit(main())
