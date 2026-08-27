"""Optimistically persist candidate lifecycle state to the latest main branch.

This module is downstream of Canonical Authority. It never changes a Formal
production action and never filters Broad Discovery. Its only responsibility is
to make lifecycle persistence race-safe when two authorized Finalizers overlap.

The key rule is replay, not rebase: each attempt creates a disposable git
worktree from the latest remote branch, folds the *same* already-authorized
canonical snapshot into that latest lifecycle state, validates the result, then
attempts one fast-forward push. A rejected push discards the generated state and
replays from the newly fetched remote branch. This prevents stale generated JSON
or Markdown from overwriting a competing lifecycle update.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .candidate_lifecycle_persistence import (
    LEDGER_PROJECTION_VERSION,
    persist_finalized_snapshot,
    render_ledger_projection,
)
from .candidate_lifecycle_state import (
    ACTIVE,
    ARCHIVED,
    INVALIDATED,
    LIFECYCLE_CONTRACT_VERSION,
    load_state,
)

STATE_RELATIVE_PATH = Path("data/opportunity_snapshots/candidate_lifecycle_state.json")
LEDGER_RELATIVE_PATH = Path("V31_CANDIDATE_LEDGER.md")
LEGACY_NOTES_RELATIVE_PATH = Path("V31_CANDIDATE_RESEARCH_NOTES_LEGACY.md")
MEANINGFUL_FORMAL_ACTIONS = {"BUY", "ADD", "REDUCE", "EXIT"}
DEFAULT_MAX_ATTEMPTS = 4


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        text=True,
        capture_output=capture_output,
    )


def _git_text(repo: Path, *args: str) -> str:
    return _git(repo, *args, capture_output=True).stdout.strip()


def _push_worktree(worktree: Path, remote: str, branch: str) -> bool:
    result = _git(worktree, "push", remote, f"HEAD:{branch}", check=False)
    return result.returncode == 0


def _preserve_legacy_notes_once(worktree: Path) -> None:
    state_path = worktree / STATE_RELATIVE_PATH
    ledger_path = worktree / LEDGER_RELATIVE_PATH
    notes_path = worktree / LEGACY_NOTES_RELATIVE_PATH
    if not state_path.exists() and ledger_path.is_file() and not notes_path.exists():
        shutil.copy2(ledger_path, notes_path)


def _is_exact_persisted_snapshot(state: Mapping[str, Any], snapshot: Mapping[str, Any]) -> bool:
    snapshot_id = str(snapshot.get("snapshot_id") or "")
    source_run_id = str(snapshot.get("source_run_id") or "")
    return bool(
        snapshot_id
        and source_run_id
        and state.get("latest_applied_snapshot_id") == snapshot_id
        and state.get("last_persisted_snapshot_id") == snapshot_id
        and str(state.get("last_persisted_source_run_id") or "") == source_run_id
    )


def _write_duplicate_outputs(
    *,
    snapshot: Mapping[str, Any],
    state: Mapping[str, Any],
    ledger_path: Path,
    events_path: Path,
    summary_path: Path,
) -> None:
    """Regenerate projections for an already-persisted snapshot without mutating state."""
    ledger_path.write_text(render_ledger_projection(state), encoding="utf-8")
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("[]\n", encoding="utf-8")

    candidates = state.get("candidates") or {}
    rows = [row for row in candidates.values() if isinstance(row, Mapping)]
    summary = {
        "contract_version": LIFECYCLE_CONTRACT_VERSION,
        "projection_version": LEDGER_PROJECTION_VERSION,
        "canonical_snapshot_id": snapshot.get("snapshot_id"),
        "canonical_source_run_id": snapshot.get("source_run_id"),
        "bootstrapped_from_legacy": False,
        "snapshot_event_count": 0,
        "candidate_count": len(candidates),
        "active_count": sum(1 for row in rows if row.get("lifecycle_state") == ACTIVE),
        "inactive_count": sum(
            1 for row in rows if row.get("lifecycle_state") in {ARCHIVED, INVALIDATED}
        ),
        "latest_applied_snapshot_id": state.get("latest_applied_snapshot_id"),
        "latest_research_as_of": state.get("latest_research_as_of"),
        "seen_count_semantics": "DISTINCT_CANONICAL_OBSERVATIONS_SINCE_MACHINE_MIGRATION",
        "no_auto_trade": True,
        "discovery_is_filtered_by_lifecycle": False,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_replayed_lifecycle(
    *,
    snapshot_path: Path,
    state_path: Path,
    events_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    events = json.loads(events_path.read_text(encoding="utf-8"))
    state = load_state(state_path)

    snapshot_id = str(snapshot.get("snapshot_id") or "")
    source_run_id = str(snapshot.get("source_run_id") or "")
    if not snapshot_id or not source_run_id:
        raise ValueError("canonical snapshot is missing snapshot_id/source_run_id")

    assert state["contract_version"] == LIFECYCLE_CONTRACT_VERSION
    assert state["latest_applied_snapshot_id"] == snapshot_id
    assert state["last_persisted_snapshot_id"] == snapshot_id
    assert state["last_persisted_source_run_id"] == source_run_id
    assert state["discovery_is_filtered_by_lifecycle"] is False
    assert state["no_auto_trade"] is True
    assert summary["canonical_snapshot_id"] == snapshot_id
    assert summary["canonical_source_run_id"] == source_run_id
    assert summary["latest_applied_snapshot_id"] == snapshot_id
    assert summary["discovery_is_filtered_by_lifecycle"] is False
    assert summary["no_auto_trade"] is True

    for event in events:
        if event.get("event") != "NEW":
            continue
        if event.get("observed_scope") == "PRODUCTION_REUNDERWRITE":
            action = str(event.get("formal_action") or "").upper()
            assert action in MEANINGFUL_FORMAL_ACTIONS, event

    return {
        "canonical_snapshot_id": snapshot_id,
        "canonical_source_run_id": source_run_id,
        "candidate_count": len(state.get("candidates") or {}),
        "snapshot_event_count": len(events),
    }


def _publish_attempt_artifacts(
    *,
    worktree: Path,
    attempt_artifacts: Path,
    authoritative_dir: Path,
    metadata: dict[str, Any],
) -> None:
    target = authoritative_dir / "candidate_lifecycle"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(worktree / STATE_RELATIVE_PATH, target / "candidate_lifecycle_state.json")
    shutil.copy2(worktree / LEDGER_RELATIVE_PATH, target / "V31_CANDIDATE_LEDGER.md")
    shutil.copy2(attempt_artifacts / "snapshot_events.json", target / "snapshot_events.json")
    shutil.copy2(attempt_artifacts / "summary.json", target / "summary.json")
    (target / "persistence_replay.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def publish_candidate_lifecycle_with_replay(
    *,
    snapshot_path: Path,
    authoritative_dir: Path,
    repo_root: Path = Path("."),
    remote: str = "origin",
    branch: str = "main",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Persist one authorized canonical lifecycle fold with optimistic replay.

    A rejected push is treated as a possible concurrent update. The stale
    worktree is destroyed, the remote branch is fetched again, and the same
    canonical snapshot is folded into the newest durable lifecycle state. The
    existing lifecycle contract remains responsible for duplicate-snapshot NOOP
    and out-of-order fail-closed behavior.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    repo_root = repo_root.resolve()
    snapshot_path = snapshot_path.resolve()
    authoritative_dir = authoritative_dir.resolve()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    canonical_id = str(snapshot.get("snapshot_id") or "")
    source_run_id = str(snapshot.get("source_run_id") or "")
    if not canonical_id or not source_run_id:
        raise ValueError("canonical snapshot is missing snapshot_id/source_run_id")

    _git(repo_root, "config", "user.name", "genge-v311-production-bot")
    _git(
        repo_root,
        "config",
        "user.email",
        "31836791+wanggenAi@users.noreply.github.com",
    )

    temp_root = Path(tempfile.mkdtemp(prefix="genge-lifecycle-replay-"))
    last_push_error = ""
    try:
        for attempt in range(1, max_attempts + 1):
            _git(repo_root, "fetch", remote, branch)
            remote_ref = f"{remote}/{branch}"
            base_sha = _git_text(repo_root, "rev-parse", remote_ref)
            worktree = temp_root / f"worktree-{attempt}"
            attempt_artifacts = temp_root / f"artifacts-{attempt}"
            attempt_artifacts.mkdir(parents=True, exist_ok=True)
            _git(repo_root, "worktree", "add", "--detach", str(worktree), base_sha)

            try:
                _preserve_legacy_notes_once(worktree)
                state_path = worktree / STATE_RELATIVE_PATH
                ledger_path = worktree / LEDGER_RELATIVE_PATH
                events_path = attempt_artifacts / "snapshot_events.json"
                summary_path = attempt_artifacts / "summary.json"

                existing_state = load_state(state_path) if state_path.exists() else None
                if existing_state is not None and _is_exact_persisted_snapshot(
                    existing_state, snapshot
                ):
                    _write_duplicate_outputs(
                        snapshot=snapshot,
                        state=existing_state,
                        ledger_path=ledger_path,
                        events_path=events_path,
                        summary_path=summary_path,
                    )
                else:
                    persist_finalized_snapshot(
                        snapshot_path=snapshot_path,
                        state_path=state_path,
                        projection_path=ledger_path,
                        legacy_ledger=ledger_path,
                        events_path=events_path,
                        summary_path=summary_path,
                    )

                validation = _validate_replayed_lifecycle(
                    snapshot_path=snapshot_path,
                    state_path=state_path,
                    events_path=events_path,
                    summary_path=summary_path,
                )

                staged_paths = [str(STATE_RELATIVE_PATH), str(LEDGER_RELATIVE_PATH)]
                notes_path = worktree / LEGACY_NOTES_RELATIVE_PATH
                if notes_path.exists():
                    staged_paths.append(str(LEGACY_NOTES_RELATIVE_PATH))
                _git(worktree, "add", *staged_paths)

                diff = _git(worktree, "diff", "--cached", "--quiet", check=False)
                if diff.returncode not in {0, 1}:
                    raise RuntimeError(f"git diff --cached --quiet failed: {diff.returncode}")

                if diff.returncode == 0:
                    metadata = {
                        **validation,
                        "status": "ALREADY_PERSISTED",
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "base_sha": base_sha,
                        "persisted_commit_sha": base_sha,
                        "replay_on_conflict": True,
                    }
                    _publish_attempt_artifacts(
                        worktree=worktree,
                        attempt_artifacts=attempt_artifacts,
                        authoritative_dir=authoritative_dir,
                        metadata=metadata,
                    )
                    return metadata

                _git(
                    worktree,
                    "commit",
                    "-m",
                    f"Persist V3.1.1 candidate lifecycle {canonical_id} [skip ci]",
                )
                commit_sha = _git_text(worktree, "rev-parse", "HEAD")
                if _push_worktree(worktree, remote, branch):
                    metadata = {
                        **validation,
                        "status": "PERSISTED",
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "base_sha": base_sha,
                        "persisted_commit_sha": commit_sha,
                        "replay_on_conflict": True,
                    }
                    _publish_attempt_artifacts(
                        worktree=worktree,
                        attempt_artifacts=attempt_artifacts,
                        authoritative_dir=authoritative_dir,
                        metadata=metadata,
                    )
                    return metadata

                last_push_error = (
                    f"push rejected on attempt {attempt}; remote {remote}/{branch} moved "
                    "or push failed"
                )
            finally:
                _git(repo_root, "worktree", "remove", "--force", str(worktree), check=False)

        raise RuntimeError(
            f"candidate lifecycle persistence failed after {max_attempts} attempts: "
            f"{last_push_error or 'no successful push'}"
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--authoritative-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    args = parser.parse_args(argv)

    result = publish_candidate_lifecycle_with_replay(
        snapshot_path=args.snapshot,
        authoritative_dir=args.authoritative_dir,
        repo_root=args.repo_root,
        remote=args.remote,
        branch=args.branch,
        max_attempts=args.max_attempts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
