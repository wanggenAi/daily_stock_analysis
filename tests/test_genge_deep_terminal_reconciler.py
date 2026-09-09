from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-deep-terminal-reconciler.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_reconciler_is_idempotent_and_terminal_only() -> None:
    text = _workflow_text()

    assert "source_deep_lambda_run_id" in text
    assert 'if [ "$terminal_id" = "$deep_id" ]; then' in text
    assert "identical state is a no-op" in text
    assert "workflow_run:" not in text
    assert "gh workflow run genge-v31-terminal-research-decision.yml" in text
    assert "gh workflow run genge-v31-deep-calculation-lambda.yml" not in text


def test_reconciler_verifies_exact_successful_deep_artifact() -> None:
    text = _workflow_text()

    assert '.github/workflows/genge-v31-deep-calculation-lambda.yml' in text
    assert '$(printf \'%s\' "$deep_run" | jq -r \'.conclusion // empty\')" = "success"' in text
    assert '$(printf \'%s\' "$deep_run" | jq -r \'.head_branch // empty\')" = "main"' in text
    assert "genge-v31-deep-calculation-${deep_id}" in text
    assert "expected exactly one live Deep artifact" in text


def test_reconciler_preserves_research_authority_guards() -> None:
    text = _workflow_text()

    assert ".unknown_is_pass // true" in text
    assert ".formal_trading_authority // true" in text
    assert ".automatic_formal_buy_allowed // true" in text
    assert ".no_auto_trade // false" in text
    assert 'unknown_is_pass" = "false"' in text
    assert 'formal_authority" = "false"' in text
    assert 'automatic_formal_buy" = "false"' in text
    assert 'no_auto_trade" = "true"' in text


def test_reconciler_has_bounded_periodic_recovery_without_deep_rerun() -> None:
    text = _workflow_text()

    assert "schedule:" in text
    assert 'cron: "7,37 * * * *"' in text
    assert "A Terminal run is already active" in text
    assert "bounded reconciler will retry later" in text
