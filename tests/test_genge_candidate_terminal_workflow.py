from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-candidate-terminal-review.yml")


def test_terminal_workflow_selects_a_real_unexpired_postscan_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert ".workflow_runs[0].id" not in text
    assert 'actions/runs/${candidate}/artifacts?per_page=100' in text
    assert 'select(.name == "genge-postscan-research" and .expired == false)' in text
    assert "selected smoke-validation postscan run $candidate with artifact $artifact_id" in text


def test_terminal_workflow_requires_successful_exact_workflow_run_lineage():
    text = WORKFLOW.read_text(encoding="utf-8")
    terminal_job = text.split("  terminalize:", 1)[1]

    assert "github.event.workflow_run.conclusion == 'success'" in terminal_job
    assert 'preferred="${{ github.event.workflow_run.id }}"' in terminal_job
    assert 'preferred="${{ inputs.upstream_run_id }}"' in terminal_job
    assert 'actions/runs/${preferred}/artifacts?per_page=100' in terminal_job
    assert "selected exact postscan run $preferred with artifact $artifact_id" in terminal_job
    assert "stale fallback forbidden" in terminal_job


def test_terminal_workflow_never_falls_back_from_explicit_lineage_to_older_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    resolver = text.split("      - name: Resolve upstream postscan run", 1)[1].split(
        "      - name: Download postscan research artifact", 1
    )[0]

    exact_branch = resolver.split('if [[ "$preferred" =~ ^[0-9]+$ ]]; then', 1)[1].split(
        "          else", 1
    )[0]
    assert "completed_runs" not in exact_branch
    assert "${candidate}" not in exact_branch
    assert 'actions/runs/${preferred}' in exact_branch
    assert 'upstream="$preferred"' in exact_branch


def test_push_only_smoke_may_use_latest_successful_postscan_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "genge-postscan-research.yml/runs?branch=main&status=success&per_page=20" in text
    assert "Push-triggered code smoke has no production lineage" in text
