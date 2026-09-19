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
