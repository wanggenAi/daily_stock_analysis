from pathlib import Path


def test_normal_all_a_workflow_uses_structured_progress_runner() -> None:
    workflow = Path(".github/workflows/genge-opportunity-discovery.yml").read_text(encoding="utf-8")
    runner = Path(
        "src/strategies/genge_opportunity_discovery/all_a_progress_runner.py"
    ).read_text(encoding="utf-8")

    assert "Run unified all-A production scan with progress" in workflow
    assert (
        "python -m src.strategies.genge_opportunity_discovery.all_a_progress_runner"
        in workflow
    )
    assert (
        "python -m src.strategies.genge_opportunity_discovery.all_a_full_scan"
        not in workflow
    )
    assert "scan_pid=$!" not in workflow
    assert 'while kill -0 "$scan_pid"' not in workflow

    assert "[ALL-A][PROGRESS]" in runner
    assert "processed}/{total}" in runner
    assert "{pct:.1f}%" in runner
    assert "items/s" in runner
    assert "tasks/s" in runner
    assert "ETA {_eta_text(eta)}" in runner
    assert "current={code}" in runner
