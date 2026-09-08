from pathlib import Path


WORKFLOW = Path('.github/workflows/genge-v31-evidence-change-trigger.yml')


def test_evidence_change_trigger_dispatches_deep_calculation_lambda():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'src/strategies/genge_opportunity_discovery/evidence_collectors/**' in text
    assert 'config/industry_alias_map.yaml' in text
    assert '.github/workflows/genge-v31-evidence-change-trigger.yml' in text
    assert 'actions: write' in text
    assert 'gh workflow run genge-v31-deep-calculation-lambda.yml' in text
    assert 'trigger_source="EVIDENCE_LAYER_CHANGE"' in text
    assert '--ref main' in text
