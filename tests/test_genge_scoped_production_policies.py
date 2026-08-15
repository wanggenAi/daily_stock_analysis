from __future__ import annotations

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy
from src.strategies.genge_opportunity_discovery import opportunity_queue_policy
from src.strategies.genge_opportunity_discovery import opportunity_report_policy
from src.strategies.genge_opportunity_discovery import risk_capped_all_a_full_scan as risk_capped
from src.strategies.genge_opportunity_discovery import risk_capped_complete_event_scan as entrypoint
from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination


def test_production_policy_stack_is_scoped_and_restored(monkeypatch):
    core = opportunity_engine_policy.core
    pipeline = opportunity_pipeline_policy.pipeline
    event_base = complete_material_event_pagination.base

    before = {
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
        "plan_columns": list(core.PLAN_COLUMNS),
        "top5_columns": list(core.TOP5_COLUMNS),
        "quant_columns": list(pipeline.QUANT_COLUMNS),
        "opportunity_columns": list(pipeline.OPPORTUNITY_COLUMNS),
    }
    observed = {}

    def fake_risk_capped_main(argv):
        # Mirror the real risk-capped main's install step without running a scan.
        risk_capped.install_policy()
        observed.update({
            "argv": argv,
            "cninfo": event_base._query_cninfo_material_events,
            "sse": event_base._query_sse_material_events,
            "strict": core.strict_candidate_checks,
            "classify": core.classify_candidate,
            "build_quant_rows": pipeline._build_quant_rows,
            "research_queues": pipeline._research_queues,
            "engine_columns": tuple(
                column for column in opportunity_report_policy.ENGINE_REPORT_COLUMNS
                if column in core.PLAN_COLUMNS and column in core.TOP5_COLUMNS
            ),
        })
        return 0

    monkeypatch.setattr(entrypoint.risk_capped, "main", fake_risk_capped_main)

    result = entrypoint.main(["--fixture-mode"])

    assert result == 0
    assert observed["argv"] == ["--fixture-mode"]
    assert observed["cninfo"] is complete_material_event_pagination.query_cninfo_material_events_complete
    assert observed["sse"] is complete_material_event_pagination.query_sse_material_events_complete
    assert observed["strict"] is opportunity_engine_policy.strict_candidate_checks
    assert observed["classify"] is risk_capped.classify_candidate
    assert observed["build_quant_rows"] is opportunity_pipeline_policy._build_quant_rows
    assert observed["research_queues"] is opportunity_queue_policy.research_queues
    assert observed["engine_columns"] == opportunity_report_policy.ENGINE_REPORT_COLUMNS

    assert event_base._query_cninfo_material_events is before["cninfo"]
    assert event_base._query_sse_material_events is before["sse"]
    assert core.strict_candidate_checks is before["strict_candidate_checks"]
    assert core.classify_candidate is before["classify_candidate"]
    assert core._apply_position_budget is before["apply_position_budget"]
    assert core.build_daily_signals is before["build_daily_signals"]
    assert core._exit_profile_strategy_health is before["exit_profile_strategy_health"]
    assert pipeline._build_quant_rows is before["build_quant_rows"]
    assert pipeline._screen_blockers is before["screen_blockers"]
    assert pipeline._screen_status is before["screen_status"]
    assert pipeline._tier_row is before["tier_row"]
    assert pipeline._research_queues is before["research_queues"]
    assert core.PLAN_COLUMNS == before["plan_columns"]
    assert core.TOP5_COLUMNS == before["top5_columns"]
    assert pipeline.QUANT_COLUMNS == before["quant_columns"]
    assert pipeline.OPPORTUNITY_COLUMNS == before["opportunity_columns"]
