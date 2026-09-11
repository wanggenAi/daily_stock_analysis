from pathlib import Path

WORKFLOW = Path('.github/workflows/genge-v311-learning-deep-review-reconciler.yml')
DEEP_REVIEW = Path('.github/workflows/genge-v311-event-driven-deep-review.yml')


def test_reconciler_is_exact_fail_closed_and_uses_learning_concurrency():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'group: genge-v311-research-learning' in text
    assert 'actions: write' in text
    assert 'research_learning_run_id:' in text
    assert 'Requested Research Learning run ${requested} is not current persisted main lineage ${persisted_run}; refusing stale Deep Review.' in text
    assert 'Exact Research Learning run ${persisted_run} was not workflow_dispatch.' in text
    assert 'persisted and artifact learning lineage diverged' in text
    assert "artifact['success_archetype_exact_dispatch'] is True" in text


def test_reconciler_dispatches_existing_deep_review_and_waits_for_success():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'gh workflow run genge-v311-event-driven-deep-review.yml' in text
    assert 'Could not resolve dispatched Deep Review run.' in text
    assert 'completed with ${conclusion}' in text
    assert 'genge-v311-event-driven-deep-review-${DEEP_REVIEW_RUN_ID}' in text


def test_reconciler_requires_every_eligible_runbei_candidate_in_deep_review_decision():
    text = WORKFLOW.read_text(encoding='utf-8')
    deep = DEEP_REVIEW.read_text(encoding='utf-8')

    assert "'SUCCESS_ARCHETYPE_RECALL' not in reasons" in text
    assert "success_archetype_source_quant_status" in text
    assert 'similarity >= 70.0 and coverage >= 1.0' in text
    assert "eligible exact Runbei candidates were not processed by Deep Review" in text
    assert 'RUNBEI_EXTERNAL_REUNDERWRITE_MIN_SIMILARITY = 70.0' in Path(
        'src/strategies/genge_opportunity_discovery/event_driven_deep_review_trigger.py'
    ).read_text(encoding='utf-8')
    assert 'genge-v311-event-driven-deep-review-${{ github.run_id }}' in deep


def test_reconciler_persists_verified_exact_handoff_marker():
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'genge-v311-learning-deep-review-handoff-${LEARNING_RUN_ID}' in text
    assert "'runbei_candidates_verified_in_deep_review': True" in text
    assert "'canonical_authority_unchanged': True" in text
    assert "'no_auto_trade': True" in text
