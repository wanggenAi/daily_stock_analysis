"""Risk-capped all-A production entrypoint with complete event pagination."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from src.strategies.genge_opportunity_discovery import candidate_recovery_report
from src.strategies.genge_opportunity_discovery import execution_lot_feasibility
from src.strategies.genge_opportunity_discovery import factor_ic_monitor
from src.strategies.genge_opportunity_discovery import industry_regime_policy
from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import opportunity_report_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


EXECUTION_PORTFOLIO_CONFIG = Path("config/execution_portfolio.json")


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


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _portfolio_capital() -> float | None:
    """Read optional reporting capital; environment overrides repository config."""

    env_value = _positive_float(os.environ.get("GENGE_PORTFOLIO_CAPITAL", "").strip())
    if env_value is not None:
        return env_value
    if not EXECUTION_PORTFOLIO_CONFIG.exists():
        return None
    try:
        payload = json.loads(EXECUTION_PORTFOLIO_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _positive_float(payload.get("portfolio_capital"))


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
    original_build_industry_regimes = core.build_industry_regimes
    original_build_quant_rows = pipeline._build_quant_rows
    original_screen_blockers = pipeline._screen_blockers
    original_screen_status = pipeline._screen_status
    original_tier_row = pipeline._tier_row
    original_research_queues = pipeline._research_queues
    plan_columns = list(core.PLAN_COLUMNS)
    top5_columns = list(core.TOP5_COLUMNS)
    industry_regime_columns = list(core.INDUSTRY_REGIME_COLUMNS)
    quant_columns = list(pipeline.QUANT_COLUMNS)
    opportunity_columns = list(pipeline.OPPORTUNITY_COLUMNS)

    complete_material_event_pagination.install()
    industry_regime_policy.install()
    opportunity_pipeline_policy.install()
    # Factor IC must wrap the engine-aware quant builder so earnings fields are
    # already normalized before point-in-time observations are persisted.
    factor_ic_monitor.install()
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
                portfolio_capital=_portfolio_capital(),
            )
            factor_ic_monitor.write_report(output_dir)
        return result
    finally:
        base._query_cninfo_material_events = original_cninfo
        base._query_sse_material_events = original_sse
        core.classify_candidate = original_classify
        core._apply_position_budget = original_apply_position_budget
        core.build_daily_signals = original_build_daily_signals
        core._exit_profile_strategy_health = original_exit_profile_health
        core.strict_candidate_checks = original_strict_checks
        core.build_industry_regimes = original_build_industry_regimes
        pipeline._build_quant_rows = original_build_quant_rows
        pipeline._screen_blockers = original_screen_blockers
        pipeline._screen_status = original_screen_status
        pipeline._tier_row = original_tier_row
        pipeline._research_queues = original_research_queues
        core.PLAN_COLUMNS[:] = plan_columns
        core.TOP5_COLUMNS[:] = top5_columns
        core.INDUSTRY_REGIME_COLUMNS[:] = industry_regime_columns
        pipeline.QUANT_COLUMNS[:] = quant_columns
        pipeline.OPPORTUNITY_COLUMNS[:] = opportunity_columns


if __name__ == "__main__":
    raise SystemExit(main())
