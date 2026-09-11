from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-v311-event-driven-deferred-retry.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_retry_relay_watches_authority_handoff_completion():
    text = _text()
    assert '"GenGe V3.1.1 Event-Driven Authority Handoff"' in text
    assert "types: [completed]" in text
    assert "actions: write" in text


def test_retry_relay_redispatches_current_event_driven_review_on_main():
    text = _text()
    assert "gh workflow run genge-v311-event-driven-deep-review.yml" in text
    assert '--repo "$GITHUB_REPOSITORY"' in text
    assert "--ref main" in text


def test_retry_relay_bootstraps_when_deployed_to_main():
    text = _text()
    assert "push:" in text
    assert "branches: [main]" in text
    assert '.github/workflows/genge-v311-event-driven-deferred-retry.yml' in text


def test_failed_or_cancelled_handoff_completion_is_also_retryable():
    text = _text()
    # A blocked signal must be reconsidered after *any* handoff completion.
    # Gating on conclusion==success would lose signals when the blocker fails.
    assert "github.event.workflow_run.conclusion ==" not in text
