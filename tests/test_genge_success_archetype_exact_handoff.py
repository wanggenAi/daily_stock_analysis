from pathlib import Path


RECALL_WORKFLOW = Path('.github/workflows/genge-success-archetype-recall.yml')
LEARNING_WORKFLOW = Path('.github/workflows/genge-research-learning.yml')


def test_recall_dispatches_research_learning_with_exact_run_id_after_artifact_upload():
    text = RECALL_WORKFLOW.read_text(encoding='utf-8')

    assert 'actions: write' in text
    upload = text.index('- name: Upload success-archetype research artifact')
    dispatch = text.index('- name: Dispatch Research Learning with exact recall lineage')
    assert upload < dispatch
    assert 'gh workflow run genge-research-learning.yml' in text
    assert 'success_archetype_run_id="${GITHUB_RUN_ID}"' in text
    assert "github.event_name == 'workflow_run'" in text


def test_research_learning_uses_dispatch_input_as_strict_exact_artifact_source():
    text = LEARNING_WORKFLOW.read_text(encoding='utf-8')

    assert 'success_archetype_run_id:' in text
    assert 'DISPATCH_SUCCESS_ARCHETYPE_RUN_ID: ${{ inputs.success_archetype_run_id }}' in text
    assert 'strict_preferred="true"' in text
    assert 'Exact dispatched Success Archetype Recall run ${preferred} has no unique live recall artifact; failing closed.' in text
    assert 'SUCCESS_ARCHETYPE_RUN_ID=$selected_run' in text


def test_research_learning_no_longer_chains_from_success_recall_workflow_run():
    text = LEARNING_WORKFLOW.read_text(encoding='utf-8')
    trigger_prefix = text.split('schedule:', 1)[0]

    assert 'GenGe Success Archetype Recall' not in trigger_prefix
    assert 'GenGe Near-BUY Evidence Recovery' in trigger_prefix
    assert 'GenGe V3.1.1 Operating Ledger' in trigger_prefix
