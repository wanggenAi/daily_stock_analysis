from pathlib import Path


LIVE = Path(".github/workflows/era-capital-trend-radar-live.yml")
CENTER = Path(".github/workflows/genge-three-pillar-decision-center.yml")


def test_era_live_completion_has_exact_final_report_consumer_without_duplicate_dispatch():
    live = LIVE.read_text(encoding="utf-8")
    center = CENTER.read_text(encoding="utf-8")
    assert '"Era Capital Trend Radar Live"' in center
    assert "workflow_run:" in center
    assert "types: [completed]" in center
    assert "gh workflow run genge-three-pillar-decision-center.yml" not in live


def test_era_live_summary_names_all_production_capital_layers():
    workflow = LIVE.read_text(encoding="utf-8")
    assert "NBS industrial-capital" in workflow
    assert "PBC financial-capital" in workflow
    assert "MIIT policy/demand" in workflow
    assert "World Bank structural" in workflow


def test_era_live_pr_concurrency_is_isolated_from_production():
    workflow = LIVE.read_text(encoding="utf-8")
    concurrency = workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0]
    assert "github.event_name == 'pull_request'" in concurrency
    assert "github.event.pull_request.number" in concurrency
    assert "|| 'production'" in concurrency
    assert "cancel-in-progress: false" in concurrency
