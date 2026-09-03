from pathlib import Path


def _workflow() -> str:
    return Path(".github/workflows/genge-investor-decision-dashboard.yml").read_text(encoding="utf-8")


def test_market_context_selects_latest_usable_artifact_even_during_rerun() -> None:
    workflow = _workflow()
    block = workflow.split("- name: Download latest usable full-A market context", 1)[1].split(
        "- name: Download event context when applicable", 1
    )[0]

    assert "genge-opportunity-discovery.yml/runs?per_page=60" in block
    assert "genge-opportunity-discovery.yml/runs?status=success" not in block
    assert 'select(.event == "schedule" or .event == "workflow_dispatch")' in block
    assert '.expired == false and .name == "genge-all-a-production-report"' in block
    assert "sort_by(.created_at) | reverse | .[0].id // empty" in block
    assert "actions/artifacts/${artifact_id}/zip" in block
    assert "MARKET_ARTIFACT_ID=${artifact_id}" in block
