from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/genge-v311-decision-outcome-observer.yml")


def test_observer_runs_only_after_successful_production_finalizer() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "name: GenGe V3.1.1 Decision Outcome Observer" in text
    assert '- "GenGe V3.1.1 Production Finalizer"' in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert 'test "$WORKFLOW_PATH" = ".github/workflows/genge-v311-production-finalizer.yml"' in text
    assert 'test "$CONCLUSION" = "success"' in text


def test_observer_validates_exact_six_file_authoritative_chain_before_persistence() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "production_authority.json",
        "canonical_snapshot/latest.json",
        "operating_views/hourly.json",
        "holdings_reconciliation.json",
        "candidate_lifecycle/candidate_lifecycle_state.json",
        "candidate_lifecycle/summary.json",
    ):
        assert required in text

    # The observer deliberately does not add another Formal input beyond the
    # user's six-file authoritative truth set.
    assert "operating_views/daily.json" not in text

    assert "authoritative_artifact_provenance" in text
    assert '--expected-finalizer-run-id "$FINALIZER_RUN_ID"' in text
    assert "validate_authority(authority, snapshot, hourly_view=hourly)" in text
    assert 'assert authority["authorized"] is True' in text
    assert 'assert authority["production_version"] == "GEN_GE_V3_1_1_PRODUCTION"' in text
    assert 'assert str(authority["finalizer_run_id"]) == finalizer_run_id' in text
    assert 'assert authority["canonical_snapshot_id"] == snapshot_id' in text
    assert 'assert authority["source_hashes"] == snapshot["source_hashes"]' in text
    assert 'assert authority["canonical_sha256"] == canonical_sha' in text
    assert 'assert hourly["canonical_snapshot_id"] == snapshot_id' in text
    assert 'assert str(hourly["source_run_id"]) == source_run_id' in text


def test_observer_locates_unique_snapshot_in_downloaded_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "find authoritative_bundle -type f -path '*/canonical_snapshot/latest.json'" in text
    assert 'if [ "${#SNAPSHOTS[@]}" -ne 1 ]' in text
    assert 'echo "AUTH_ROOT=$AUTH_ROOT" >> "$GITHUB_ENV"' in text
    assert 'echo "SNAPSHOT=$SNAPSHOT" >> "$GITHUB_ENV"' in text


def test_observer_has_no_execution_or_formal_action_write_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "record-execution" not in text
    assert "execution_events.jsonl" not in text
    assert "decision_outcome_git_persistence" in text
    assert 'branch="main"' in text
    assert 'assert result["executions_touched"] is False' in text
    assert 'assert result["production_semantics_mutated"] is False' in text
    assert "Formal BUY/ADD/HOLD/REDUCE/EXIT remain canonical-only" in text
