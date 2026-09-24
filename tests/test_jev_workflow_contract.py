from pathlib import Path


def test_jev_main_push_wakes_on_persisted_research_priority_updates():
    workflow_lines = Path(
        ".github/workflows/genge-jev-shadow-evaluation.yml"
    ).read_text(encoding="utf-8").splitlines()
    push_start = workflow_lines.index("  push:")
    concurrency_start = workflow_lines.index("concurrency:")
    push_block = workflow_lines[push_start:concurrency_start]

    assert "      - 'data/research_priority/**'" in push_block


def test_terminal_convergence_wakes_lineage_keyed_jev_entry_judgment():
    workflow = Path(
        ".github/workflows/genge-v31-terminal-research-decision.yml"
    ).read_text(encoding="utf-8")

    persist = workflow.index("Persist terminal research decisions with optimistic replay")
    wake = workflow.index("Wake lineage-keyed Jev entry judgment after terminal convergence")
    overlay = workflow.index("Refresh investor terminal overlay after terminal convergence")
    wake_block = workflow[wake:overlay]

    assert persist < wake < overlay
    assert 'DEEP_RUN_ID: ${{ steps.source.outputs.lambda_run_id }}' in wake_block
    assert 'title="GenGe Jev Shadow Evaluation / $DEEP_RUN_ID"' in wake_block
    assert "genge-jev-shadow-evaluation.yml/runs?branch=main&event=workflow_dispatch" in wake_block
    assert 'gh workflow run genge-jev-shadow-evaluation.yml' in wake_block
    assert '-f continuation_deep_run_id="$DEEP_RUN_ID"' in wake_block
    assert "-f scope=combined" in wake_block
    assert "-f max_entities=25" in wake_block
    assert 'gh run rerun "$existing"' in wake_block


def test_research_learning_wakes_jev_only_after_successful_persistence():
    workflow = Path(
        ".github/workflows/genge-research-learning.yml"
    ).read_text(encoding="utf-8")

    assert "  actions: write" in workflow
    assert "id: persist_learning" in workflow
    assert 'if git diff --cached --quiet; then echo "No learning state change to persist"; exit 0; fi' in workflow
    assert 'if git push origin HEAD:main; then echo "persisted=true" >> "$GITHUB_OUTPUT"; exit 0; fi' in workflow
    wake = workflow.index("Wake Jev shadow after persisted research priority update")
    persist = workflow.index("Build and persist learning state with optimistic replay")
    upload = workflow.index("Upload research learning artifact")
    assert persist < wake < upload
    wake_block = workflow[wake:upload]
    assert "if: steps.persist_learning.outputs.persisted == 'true'" in wake_block
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in wake_block
    assert "gh workflow run genge-jev-shadow-evaluation.yml" in wake_block
    assert "--ref main" in wake_block
    assert "-f scope=combined" in wake_block
    assert "-f max_entities=25" in wake_block
    assert "formal" not in wake_block.lower()
