"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate.  The installed
    # collector still returns PARTIAL/UNKNOWN whenever a leaf window cannot be
    # proven complete; only provider page-cap truncation is resolved by splitting.
    complete_material_event_pagination.install()
    return risk_capped.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
