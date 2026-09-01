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
