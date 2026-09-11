from pathlib import Path

WORKFLOW = Path('.github/workflows/genge-v311-learning-deep-review-reconciler.yml')
DEEP_REVIEW = Path('.github/workflows/genge-v311-event-driven-deep-review.yml')
TRIGGER = Path('src/strategies/genge_opportunity_discovery/event_driven_deep_review_trigger.py')


def test_reconciler_discovers_unclosed_exact_learning_artifacts_without_trusting_current_lineage():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'actions: write' in text
    assert 'research_learning_run_id:' in text
    assert 'event=workflow_dispatch&branch=main&status=success' in text
    assert "date -u -d '24 hours ago'" in text
    assert 'genge-v311-learning-deep-review-handoff-${candidate}' in text
    assert "success_archetype_exact_dispatch // false" in text
    assert 'Requested Learning run ${candidate} is not a self-consistent exact Success Archetype handoff.' in text
    assert 'data/research_priority/learning_lineage.json' not in text


def test_reconciler_preserves_exact_candidate_identity_before_using_current_canonical_snapshot():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'Verify exact Runbei candidates still survive in current main' in text
    assert 'data/research_priority/latest.json' in text
    assert "'SUCCESS_ARCHETYPE_RECALL' not in reasons" in text
    assert "success_archetype_source_quant_status" in text
    assert '>= 70.0' in text
    assert '>= 1.0' in text
    assert 'success_archetype_id' in text
    assert 'math.isclose' in text
    assert 'exact Runbei candidate {code} no longer exists in current research priority' in text


def test_reconciler_dispatches_existing_deep_review_and_waits_for_success():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'gh workflow run genge-v311-event-driven-deep-review.yml' in text
    assert 'before_ids=' in text
    assert 'Could not resolve dispatched Deep Review run.' in text
    assert 'Ambiguous Deep Review dispatch' in text
    assert 'completed with ${conclusion}' in text
    assert 'genge-v311-event-driven-deep-review-${DEEP_REVIEW_RUN_ID}' in text


def test_reconciler_requires_every_eligible_exact_runbei_candidate_in_deep_review_decision():
    text = WORKFLOW.read_text(encoding='utf-8')
    deep = DEEP_REVIEW.read_text(encoding='utf-8')
    trigger = TRIGGER.read_text(encoding='utf-8')

    assert 'EXPECTED_RUNBEI_CODES' in text
    assert 'eligible exact Runbei candidates were not processed by Deep Review' in text
    assert "assert decision['dispatch_required'] is True" in text
    assert 'RUNBEI_EXTERNAL_REUNDERWRITE_MIN_SIMILARITY = 70.0' in trigger
    assert 'RUNBEI_EXTERNAL_REUNDERWRITE_MIN_EVIDENCE_COVERAGE = 1.0' in trigger
    assert 'genge-v311-event-driven-deep-review-${{ github.run_id }}' in deep


def test_reconciler_persists_verified_exact_handoff_marker():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'genge-v311-learning-deep-review-handoff-${{ env.LEARNING_RUN_ID }}' in text
    assert "'exact_learning_artifact_verified': True" in text
    assert "'current_main_candidate_identity_preserved': True" in text
    assert "'deep_review_trigger_verified': True" in text
    assert "'canonical_authority_unchanged': True" in text
    assert "'no_auto_trade': True" in text
