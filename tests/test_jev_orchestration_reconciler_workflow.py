from pathlib import Path


RECONCILER = Path(".github/workflows/genge-jev-orchestration-reconciler.yml")
DEEP = Path(".github/workflows/genge-v31-deep-calculation-lambda.yml")
TERMINAL = Path(".github/workflows/genge-v31-terminal-research-decision.yml")
INVESTOR = Path(".github/workflows/genge-investor-terminal-research-overlay.yml")
DECISION_CENTER = Path(".github/workflows/genge-three-pillar-decision-center.yml")


def test_reconciler_tracks_the_exact_jev_deep_lineage() -> None:
    workflow = RECONCILER.read_text(encoding="utf-8")

    assert '"GenGe V3.1 Deep Calculation Lambda"' in workflow
    assert '"GenGe V3.1 Terminal Research Decision"' in workflow
    assert '"GenGe Investor Terminal Research Overlay"' in workflow
    assert '"GenGe Three-Pillar Decision Center"' in workflow
    assert "data/jev_shadow/orchestration/latest.json" in workflow
    assert "source_workflow_run_id" in workflow
    assert "deep_run_id" in workflow
    assert "JEV_ORCHESTRATOR_$source_run_id" in workflow


def test_recovery_uses_existing_exact_artifact_and_never_reruns_deep() -> None:
    workflow = RECONCILER.read_text(encoding="utf-8")

    assert 'gh run download "$deep_run_id"' in workflow
    assert 'genge-v31-deep-calculation-$deep_run_id' in workflow
    assert "initial_checkpoint_status.json" in workflow
    assert "artifact workset mismatch" in workflow
    assert "gh workflow run genge-v31-deep-calculation-lambda.yml" not in workflow
    assert "Recover exact downstream convergence without rerunning Deep" in workflow
    assert "gh workflow run genge-v31-terminal-research-decision.yml" in workflow


def test_recovery_is_monotonic_and_fail_closed() -> None:
    workflow = RECONCILER.read_text(encoding="utf-8")

    assert '[ "$current_run_id" -gt "$deep_run_id" ]' in workflow
    assert '[ "$current_run_id" -gt "$DEEP_RUN_ID" ]' in workflow
    assert "not rolling latest backward" in workflow
    assert "unknown_is_pass" in workflow
    assert "automatic_formal_buy_allowed" in workflow
    assert "formal_trading_authority" in workflow
    assert "no_auto_trade" in workflow


def test_cursor_reaches_all_downstream_stages_only_on_matching_lineage() -> None:
    workflow = RECONCILER.read_text(encoding="utf-8")

    for stage in (
        "DEEP_COMPLETE",
        "TERMINAL_COMPLETE",
        "INVESTOR_OVERLAY_COMPLETE",
        "DECISION_CENTER_REFRESHED",
    ):
        assert stage in workflow

    assert ".source_deep_lambda_run_id" in workflow
    assert ".terminal_research_snapshot.source_deep_lambda_run_id" in workflow
    assert ".deep_calculation_runtime.lambda_run_id" in workflow
    assert ".terminal_research_snapshot.current_for_deep_runtime" in workflow


def test_workflow_contract_edits_do_not_self_trigger_expensive_production_deep() -> None:
    workflow = DEEP.read_text(encoding="utf-8")
    push_block = workflow.split("  push:", 1)[1].split("  workflow_run:", 1)[0]

    assert '".github/workflows/genge-v31-deep-calculation-lambda.yml"' not in push_block
    assert '"tests/test_genge_v31_deep_calculation_workflow_contract.py"' not in push_block
    assert '"src/strategies/genge_opportunity_discovery/v31_deep_gap_closure.py"' in push_block
    assert '"src/strategies/genge_opportunity_discovery/evidence_collectors/public_data.py"' in push_block

def test_downstream_convergence_explicitly_wakes_jev_reconciler() -> None:
    dispatch = 'gh workflow run genge-jev-orchestration-reconciler.yml --repo "$GITHUB_REPOSITORY" --ref main'

    terminal = TERMINAL.read_text(encoding="utf-8")
    investor = INVESTOR.read_text(encoding="utf-8")
    center = DECISION_CENTER.read_text(encoding="utf-8")

    assert dispatch in terminal
    assert dispatch in investor
    assert dispatch in center
    assert terminal.index("Persist terminal research decisions with optimistic replay") < terminal.index(dispatch)
    assert investor.index("Overlay latest terminal research onto investor brief with optimistic replay") < investor.index(dispatch)
    assert center.index("Build and persist runtime-aware decision center with optimistic replay") < center.index(dispatch)
    assert ".production_verification_complete // false" in terminal
    assert ".production_verification_complete // false" in investor
    assert ".production_verification_complete // false" in center

    production = center.split("  production:", 1)[1]
    assert "actions: write" in production.split("    steps:", 1)[0]

