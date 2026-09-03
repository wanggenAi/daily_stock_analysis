from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-candidate-terminal-review.yml")


def test_terminal_workflow_selects_a_real_unexpired_postscan_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert ".workflow_runs[0].id" not in text
    assert 'actions/runs/${candidate}/artifacts?per_page=100' in text
    assert 'select(.name == "genge-postscan-research" and .expired == false)' in text
    assert "selected postscan run $candidate with artifact $artifact_id" in text


def test_terminal_workflow_does_not_require_upstream_success_before_artifact_probe():
    text = WORKFLOW.read_text(encoding="utf-8")
    terminal_job = text.split("  terminalize:", 1)[1]

    assert "github.event.workflow_run.conclusion == 'success'" not in terminal_job
    assert 'preferred="${{ github.event.workflow_run.id }}"' in terminal_job
    assert 'candidates+=("$preferred")' in terminal_job
