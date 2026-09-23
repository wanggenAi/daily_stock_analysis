from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-jev-orchestration-reconciler.yml")


def test_reconciler_persists_exact_accepted_continuation_run_id_after_dispatch() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dispatch = workflow.index("- name: Dispatch lineage-keyed Jev reevaluation after full downstream convergence")
    persist = workflow.index("- name: Persist accepted continuation Jev cursor")
    summary = workflow.index("- name: Publish reconciliation summary")

    assert dispatch < persist < summary
    block = workflow[persist:summary]
    assert "steps.continuation.outputs.jev_run_id != ''" in block
    assert 'DEEP_RUN_ID: ${{ steps.inspect.outputs.deep_run_id }}' in block
    assert 'JEV_RUN_ID: ${{ steps.continuation.outputs.jev_run_id }}' in block
    assert 'payload["continuation_jev_state"] = "DISPATCH_ACCEPTED"' in block
    assert 'payload["continuation_jev_run_id"] = os.environ["JEV_RUN_ID"]' in block
    assert 'continuation_from_deep_run_id' in block
    assert 'git fetch origin main' in block
    assert 'git push origin HEAD:main' in block


def test_reconciler_cursor_persistence_refuses_to_overwrite_newer_deep_lineage() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split("- name: Persist accepted continuation Jev cursor", 1)[1].split(
        "- name: Publish reconciliation summary", 1
    )[0]

    assert 'marker_deep="$(jq -r' in block
    assert 'continuation_deep="$(jq -r' in block
    assert 'if [ "$marker_deep" != "$DEEP_RUN_ID" ] || [ "$continuation_deep" != "$DEEP_RUN_ID" ]; then' in block
    assert "A newer Jev lineage owns the cursor; not overwriting it." in block
