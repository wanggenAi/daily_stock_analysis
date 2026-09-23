from pathlib import Path


def test_jev_main_push_wakes_on_persisted_research_priority_updates():
    workflow = Path(".github/workflows/genge-jev-shadow-evaluation.yml").read_text(
        encoding="utf-8"
    )
    push_block = workflow.split("  push:\\n", 1)[1].split("\\n\\nconcurrency:", 1)[0]

    assert "- 'data/research_priority/**'" in push_block
