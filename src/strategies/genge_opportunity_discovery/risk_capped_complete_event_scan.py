"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate. The production
    # collector hook is process-global, so keep it scoped to this scan invocation
    # and restore the caller's provider functions afterwards. This prevents test
    # suites and long-lived processes from inheriting the adaptive hook merely
    # because they invoked this entrypoint once.
    base = complete_material_event_pagination.base
    original_cninfo = base._query_cninfo_material_events
    original_sse = base._query_sse_material_events
    complete_material_event_pagination.install()
    try:
        return risk_capped.main(argv)
    finally:
        base._query_cninfo_material_events = original_cninfo
        base._query_sse_material_events = original_sse


if __name__ == "__main__":
    raise SystemExit(main())
