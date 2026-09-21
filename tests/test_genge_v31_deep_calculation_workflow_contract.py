from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-v31-deep-calculation-lambda.yml")


def _partial_checkpoint_block() -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    return workflow.split("- name: Persist partial checkpoint when closure is incomplete", 1)[1].split(
        "- name: Upload Deep Calculation Lambda artifact", 1
    )[0]


def test_partial_checkpoint_persists_requested_workset_coverage() -> None:
    block = _partial_checkpoint_block()

    assert "REQUESTED_CODES: ${{ steps.resolve.outputs.requested_codes }}" in block
    assert "deep_review_profiles.json" in block
    assert "'profile_count':len(profiles)" in block
    assert "'requested_count':len(requested)" in block
    assert "'requested_profile_count':len(requested_profiles)" in block
    assert "'missing_requested_codes':missing_requested" in block
    assert "'workset_coverage_known':bool(requested)" in block
    assert "'workset_coverage_complete':not missing_requested" in block


def test_deep_lambda_contract_suite_guards_partial_checkpoint_schema() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "tests/test_genge_v31_deep_calculation_workflow_contract.py" in workflow


def test_terminal_observability_contract_allows_handoff_incomplete() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "HANDOFF_INCOMPLETE" in workflow
    assert "status['research_terminal_state'] in {'COMPLETE','EVIDENCE_EXHAUSTED','HANDOFF_INCOMPLETE'}" in workflow


def test_completed_deep_dispatches_terminal_and_provenance_not_stale_decision_center() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "gh workflow run genge-v31-deep-provenance-audit.yml" in workflow
    assert "gh workflow run genge-v31-terminal-research-decision.yml" in workflow
    assert "gh workflow run genge-three-pillar-decision-center.yml" not in workflow


def test_duplicate_deep_triggers_collapse_by_evidence_epoch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "github.event.workflow_run.head_sha || github.sha" in workflow
    assert "github.event.workflow_run.conclusion != 'success'" in workflow
    assert "github.event.workflow_run.head_branch != 'main'" in workflow
    assert "&& github.run_id || inputs.research_run_id" in workflow
    assert "inputs.requested_codes || 'default'" in workflow
    assert "cancel-in-progress: ${{ github.event_name != 'workflow_run' }}" in workflow
    assert "github.event.workflow_run.id || github.run_id" not in workflow


def test_superseded_deep_epoch_preserves_history_without_replacing_latest() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split("- name: Persist terminal deep-calculation state with optimistic replay", 1)[1].split(
        "- name: Persist partial checkpoint when closure is incomplete", 1
    )[0]

    assert 'git diff --quiet "${DEEP_CODE_EPOCH_SHA}"..origin/main --' in block
    assert "src/strategies/genge_opportunity_discovery/evidence_collectors" in block
    assert "config/industry_alias_map.yaml" in block
    assert 'superseded=true' in block
    assert 'if [ "$superseded" = false ]; then' in block
    assert 'data/deep_calculation/history/${GITHUB_RUN_ID}.json' in block
    assert "preserving history only" in block


def test_skipped_workflow_run_cannot_cancel_valid_same_epoch_deep() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    concurrency = workflow.split("concurrency:", 1)[1].split("env:", 1)[0]
    jobs = workflow.split("jobs:", 1)[1]

    assert "github.event.workflow_run.conclusion != 'success'" in concurrency
    assert "github.event.workflow_run.head_branch != 'main'" in concurrency
    assert "github.run_id" in concurrency
    assert "cancel-in-progress: ${{ github.event_name != 'workflow_run' }}" in concurrency
    assert "github.event.workflow_run.conclusion == 'success'" in jobs
    assert "github.event.workflow_run.head_branch == 'main'" in jobs


def test_successful_workflow_run_cannot_preempt_active_official_evidence_closure() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    concurrency = workflow.split("concurrency:", 1)[1].split("env:", 1)[0]

    assert "cancel-in-progress: ${{ github.event_name != 'workflow_run' }}" in concurrency
    assert "cancel-in-progress: true" not in concurrency
    assert "github.event.workflow_run.head_sha || github.sha" in concurrency


def test_deep_epoch_fence_uses_actual_checked_out_code_sha() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    checkout = workflow.split("- name: Checkout current main", 1)[1].split(
        "- name: Synchronize provenance self-verification push", 1
    )[0]
    assert 'DEEP_CODE_EPOCH_SHA=$(git rev-parse HEAD)' in checkout
    assert 'git diff --quiet "${DEEP_CODE_EPOCH_SHA}"..origin/main --' in workflow
    assert "'deep_code_epoch_sha':os.environ.get('DEEP_CODE_EPOCH_SHA','')" in workflow


def test_older_completed_deep_cannot_replace_newer_latest_or_dispatch_downstream() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split("- name: Persist terminal deep-calculation state with optimistic replay", 1)[1].split(
        "- name: Persist partial checkpoint when closure is incomplete", 1
    )[0]
    dispatch = workflow.split("- name: Dispatch provenance and terminal convergence immediately", 1)[1].split(
        "- name: Publish Lambda status", 1
    )[0]

    assert "id: persist" in workflow
    assert 'latest_run_id="0"' in block
    assert "'.lambda_run_id // \"0\"'" in block
    assert '[ "$latest_run_id" -gt "$GITHUB_RUN_ID" ]' in block
    assert "older than persisted latest Lambda" in block
    assert 'owns_latest=false' in block
    assert 'owns_latest=true' in block
    assert 'echo "owns_latest=$owns_latest" >> "$GITHUB_OUTPUT"' in block
    assert "steps.persist.outputs.owns_latest == 'true'" in dispatch
