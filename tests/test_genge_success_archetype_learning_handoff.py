from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-success-archetype-recall.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_recall_can_dispatch_followup_learning_workflow():
    text = _workflow_text()
    assert "actions: write" in text
    assert "Dispatch Research Learning after recall artifact publication" in text
    assert "gh workflow run genge-research-learning.yml" in text
    assert '--repo "$GITHUB_REPOSITORY"' in text
    assert "--ref main" in text


def test_learning_dispatch_happens_only_after_recall_artifact_is_uploaded():
    text = _workflow_text()
    upload = text.index("- name: Upload success-archetype research artifact")
    dispatch = text.index("- name: Dispatch Research Learning after recall artifact publication")
    assert upload < dispatch


def test_noop_recall_does_not_dispatch_learning():
    text = _workflow_text()
    marker = "- name: Dispatch Research Learning after recall artifact publication"
    dispatch_block = text[text.index(marker) :]
    assert "if: env.RECALL_NOOP != 'true'" in dispatch_block.split("- name: Publish summary", 1)[0]
