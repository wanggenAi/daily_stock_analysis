from pathlib import Path


def test_jev_main_push_wakes_on_persisted_research_priority_updates():
    workflow_lines = Path(
        ".github/workflows/genge-jev-shadow-evaluation.yml"
    ).read_text(encoding="utf-8").splitlines()
    push_start = workflow_lines.index("  push:")
    concurrency_start = workflow_lines.index("concurrency:")
    push_block = workflow_lines[push_start:concurrency_start]

    assert "      - 'data/research_priority/**'" in push_block
