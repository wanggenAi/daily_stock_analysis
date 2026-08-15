"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from src.strategies.genge_opportunity_discovery import candidate_recovery_report
from src.strategies.genge_opportunity_discovery import execution_lot_feasibility
from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import opportunity_report_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def _explicit_output_dir(argv: list[str]) -> Path | None:
    for index, value in enumerate(argv):
        if value == "--output-dir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if value.startswith("--output-dir="):
            return Path(value.split("=", 1)[1])
    return None


def _resolved_report_dir(argv: list[str]) -> Path | None:
    explicit = _explicit_output_dir(argv)
    if explicit is not None:
        return explicit
    root = Path("reports/all_a_full_scan")
    if not root.exists():
        return None
    candidates = sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / "run_summary.json").exists()
    )
    return candidates[-1] if candidates else None


def _portfolio_capital_from_env() -> float | None:
    """Return optional reporting capital without changing any position policy."""

    raw = os.environ.get("GENGE_PORTFOLIO_CAPITAL", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def main(argv: list[str] | None = None) -> int:
    # Every production hook in this wrapper is process-global. Capture the full
    # caller state, install only for this scan, then restore in finally.
    base = complete_material_event_pagination.base
    core = risk_capped.core
    pipeline = opportunity_pipeline_policy.pipeline

    original_cninfo = base._query_cninfo_material_events
    original_sse = base._query_sse_material_events
    original_classify = core.classify_candidate
    original_apply_position_budget = core._apply_position_budget
    original_build_daily_signals = core.build_daily_signals
    original_exit_profile_health = core._exit_profile_strategy_health
    original_strict_checks = core.strict_candidate_checks
    original_build_quant_rows = pipeline._build_quant_rows
    original_screen_blockers = pipeline._screen_blockers
    original_screen_status = pipeline._screen_status
    original_tier_row = pipeline._tier_row
    original_research_queues = pipeline._research_queues
    plan_columns = list(core.PLAN_COLUMNS)
    top5_columns = list(core.TOP5_COLUMNS)
    quant_columns = list(pipeline.QUANT_COLUMNS)
    opportunity_columns = list(pipeline.OPPORTUNITY_COLUMNS)

    complete_material_event_pagination.install()
    opportunity_pipeline_policy.install()
    opportunity_queue_policy.install()
    opportunity_engine_policy.install()
    opportunity_report_policy.install()
    try:
        result = risk_capped.main(argv)
        if result != 0:
            return result
        effective_argv = list(sys.argv[1:] if argv is None else argv)
        output_dir = _resolved_report_dir(effective_argv)
        if output_dir is not None:
            candidate_recovery_report.write_report(output_dir)
            execution_lot_feasibility.write_report(
                output_dir,
                portfolio_capital=_portfolio_capital_from_env(),
            )
        return result
    finally:
        base._query_cninfo_material_events = original_cninfo
        base._query_sse_material_events = original_sse
        core.classify_candidate = original_classify
        core._apply_position_budget = original_apply_position_budget
        core.build_daily_signals = original_build_daily_signals
        core._exit_profile_strategy_health = original_exit_profile_health
        core.strict_candidate_checks = original_strict_checks
        pipeline._build_quant_rows = original_build_quant_rows
        pipeline._screen_blockers = original_screen_blockers
        pipeline._screen_status = original_screen_status
        pipeline._tier_row = original_tier_row
        pipeline._research_queues = original_research_queues
        core.PLAN_COLUMNS[:] = plan_columns
        core.TOP5_COLUMNS[:] = top5_columns
        pipeline.QUANT_COLUMNS[:] = quant_columns
        pipeline.OPPORTUNITY_COLUMNS[:] = opportunity_columns


if __name__ == "__main__":
    raise SystemExit(main())
