from pathlib import Path


def test_near_buy_workflow_uses_local_jq_for_named_artifact_filter():
    workflow = Path(".github/workflows/genge-near-buy-research.yml").read_text(encoding="utf-8")

    assert "--jq --arg" not in workflow
    assert "artifacts_json=$(gh api" in workflow
    assert "jq -r --arg name \"$expected_artifact\"" in workflow
    assert "genge-candidate-terminal-decisions-auto-repair" in workflow
    assert "genge-candidate-terminal-decisions" in workflow
