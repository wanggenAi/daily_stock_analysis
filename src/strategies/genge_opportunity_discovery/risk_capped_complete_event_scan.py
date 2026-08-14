"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate.
    complete_material_event_pagination.install()

    # The funnel patch prevents the legacy low-price assumption from discarding
    # strong-trend/earnings research objects before final strict evaluation.
    # It never creates a formal signal or relaxes non-price hard blockers.
    opportunity_pipeline_policy.install()

    # Replace only the final universal low-price gate with explicit engine
    # admission. All existing strict safety/risk gates remain in force; the
    # risk-capped wrapper may still relax exit-history uncertainty only.
    opportunity_engine_policy.install()
    return risk_capped.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
