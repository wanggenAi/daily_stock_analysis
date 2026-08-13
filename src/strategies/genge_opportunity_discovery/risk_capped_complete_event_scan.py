"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

import sys
from pathlib import Path

from src.strategies.genge_opportunity_discovery import candidate_recovery_report
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def _explicit_output_dir(argv: list[str]) -> Path | None:
    for index, value in enumerate(argv):
        if value == "--output-dir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if value.startswith("--output-dir="):
            return Path(value.split("=", 1)[1])
    return None


def main(argv: list[str] | None = None) -> int:
    # Data completeness is a prerequisite, not a relaxed gate.  The installed
    # collector still returns PARTIAL/UNKNOWN whenever a leaf window cannot be
    # proven complete; only provider page-cap truncation is resolved by splitting.
    complete_material_event_pagination.install()
    result = risk_capped.main(argv)
    if result != 0:
        return result

    # The recovery report is research prioritization only.  It is generated
    # after the authoritative scan and cannot alter classifications or signals.
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    output_dir = _explicit_output_dir(effective_argv)
    recovery_args = ["--report-dir", str(output_dir)] if output_dir is not None else []
    candidate_recovery_report.main(recovery_args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
