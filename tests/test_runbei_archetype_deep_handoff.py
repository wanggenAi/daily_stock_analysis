from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-v31-deep-calculation-lambda.yml")


def test_success_archetype_recall_is_part_of_deep_requested_workset() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "data/research_priority/latest.json" in text
    assert "SUCCESS_ARCHETYPE_RECALL" in text
    assert "success_archetype_id" in text
    assert "success_archetype_similarity_score" in text


def test_recall_handoff_does_not_relax_trading_safety_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "status['unknown_is_pass'] is False" in text
    assert "status['automatic_formal_buy_allowed'] is False" in text
    assert "status['formal_trading_authority'] is False" in text
    assert "status['no_auto_trade'] is True" in text
