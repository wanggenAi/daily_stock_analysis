from pathlib import Path


WORKFLOW = Path(".github/workflows/era-capital-trend-radar-live.yml")


def test_semantic_era_change_refreshes_final_decision_center_after_persistence():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    persist_at = workflow.index("- name: Collect, hand off and persist with optimistic replay")
    refresh_at = workflow.index("- name: Refresh final decision center after Era Radar persistence")
    handoff_at = workflow.index("- name: Launch full authority research for new qualified Era handoffs")
    assert persist_at < refresh_at < handoff_at
    assert "echo 'state_changed=false' >> \"$GITHUB_OUTPUT\"" in workflow
    assert "echo 'state_changed=true' >> \"$GITHUB_OUTPUT\"" in workflow
    refresh = workflow[refresh_at:handoff_at]
    assert "steps.persist.outputs.state_changed == 'true'" in refresh
    assert "gh workflow run genge-three-pillar-decision-center.yml" in refresh


def test_era_live_summary_names_all_production_capital_layers():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "NBS industrial-capital" in workflow
    assert "PBC financial-capital" in workflow
    assert "MIIT policy/demand" in workflow
    assert "World Bank structural" in workflow


def test_era_live_pr_concurrency_is_isolated_from_production():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    concurrency = workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0]
    assert "github.event_name == 'pull_request'" in concurrency
    assert "github.event.pull_request.number" in concurrency
    assert "|| 'production'" in concurrency
    assert "cancel-in-progress: false" in concurrency
