from __future__ import annotations

from pathlib import Path


FINALIZER_WORKFLOW = Path(".github/workflows/genge-v311-production-finalizer.yml")


def test_finalizer_sole_truth_validation_uses_runtime_github_run_id() -> None:
    workflow = FINALIZER_WORKFLOW.read_text(encoding="utf-8")

    assert 'assert authority["finalizer_run_id"] == "${GITHUB_RUN_ID}"' not in workflow
    assert 'assert authority["finalizer_run_id"] == os.environ["GITHUB_RUN_ID"]' in workflow


def test_finalizer_keeps_exact_run_identity_validation() -> None:
    workflow = FINALIZER_WORKFLOW.read_text(encoding="utf-8")

    assert '--finalizer-run-id "${GITHUB_RUN_ID}"' in workflow
    assert 'Validate exact GitHub Actions provenance namespaces' in workflow
    assert 'Validate sole-truth consumer and persisted lifecycle contract' in workflow
