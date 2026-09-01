from pathlib import Path


def test_authority_consumer_handoff_workflow_is_deterministic() -> None:
    workflow = Path('.github/workflows/genge-v311-authority-consumer-handoff.yml').read_text(encoding='utf-8')

    assert 'GenGe V3.1.1 Authority Consumer Handoff' in workflow
    assert 'genge-v311-production-finalizer.yml' in workflow
    assert 'genge-v311-continuity-state.yml' in workflow
    assert 'genge-hourly-deep-overlay.yml' in workflow
    assert 'genge-v311-operating-ledger.yml' in workflow
    assert 'finalizer_run_id' in workflow
    assert 'Verify durable consumer identities match the exact Finalizer' in workflow
    assert 'Formal actions' in workflow
    assert 'no auto trade' in workflow


def test_hourly_overlay_accepts_and_validates_exact_finalizer_dispatch() -> None:
    workflow = Path('.github/workflows/genge-hourly-deep-overlay.yml').read_text(encoding='utf-8')

    assert 'finalizer_run_id:' in workflow
    assert 'REQUESTED_FINALIZER_RUN_ID' in workflow
    assert 'github.event.workflow_run.id' in workflow
    assert '.github/workflows/genge-v311-production-finalizer.yml' in workflow
    assert 'Production Finalizer ${run_id} is not successful' in workflow
    assert 'has no non-expired authoritative canonical artifact' in workflow
    assert '--expected-finalizer-run-id "$FINALIZER_RUN_ID"' in workflow
    assert 'overlay_may_overwrite_formal_action' in workflow
    assert "assert price['formal_action_recomputed'] is False" in workflow
