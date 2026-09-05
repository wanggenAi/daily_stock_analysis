#!/usr/bin/env python3
"""Race-safe persistence for observer-only GenGe decision events.

This module is strictly downstream of a finalized canonical snapshot.  It does
not create, rank, recompute, or execute a trading action.  Its only job is to
append the immutable canonical decision observations produced by
``decision_outcome_evaluator`` to the durable decision ledger on the latest
remote branch.

Persistence uses optimistic *replay*, not rebase: each attempt starts from the
latest remote branch, imports the same finalized canonical snapshot, and tries
one fast-forward push.  A rejected push discards the generated worktree and
replays against the newly fetched branch, preserving concurrent writers.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from scripts.decision_outcome_evaluator import canonical_identity, import_canonical

DECISIONS_RELATIVE_PATH = Path("data/decision_outcomes/decision_events.jsonl")
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


def _read_decision_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: decision row must be an object")
        rows.append(row)
    return rows


def persist_canonical_observation_with_replay(
    *,
    canonical_path: Path,
    repo_root: Path = Path("."),
    remote: str = "origin",
    branch: str = "main",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Append one finalized canonical observation to the durable ledger.

    The same snapshot is idempotent because ``import_canonical`` derives stable
    decision ids from snapshot/source-run/symbol/action.  No execution events
    are created here, and no existing execution ledger is read or modified.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    repo_root = repo_root.resolve()
    canonical_path = canonical_path.resolve()
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    if not isinstance(canonical, dict):
        raise ValueError("canonical must be a JSON object")
    snapshot_id, source_run_id, _, _ = canonical_identity(canonical)

    _git(repo_root, "config", "user.name", "genge-decision-observer-bot")
    _git(
        repo_root,
        "config",
        "user.email",
        "31836791+wanggenAi@users.noreply.github.com",
    )

    temp_root = Path(tempfile.mkdtemp(prefix="genge-decision-observer-replay-"))
    last_push_error = ""
    try:
        for attempt in range(1, max_attempts + 1):
            _git(repo_root, "fetch", remote, branch)
            remote_ref = f"{remote}/{branch}"
            base_sha = _git_text(repo_root, "rev-parse", remote_ref)
            worktree = temp_root / f"worktree-{attempt}"
            _git(repo_root, "worktree", "add", "--detach", str(worktree), base_sha)

            try:
                decisions_path = worktree / DECISIONS_RELATIVE_PATH
                result = import_canonical(canonical_path, decisions_path)
                rows = _read_decision_rows(decisions_path)

                observed_ids = {
                    str(row.get("decision_id") or "")
                    for row in rows
                    if str(row.get("snapshot_id") or "") == snapshot_id
                    and str(row.get("source_run_id") or "") == source_run_id
                }
                if result["discovered"] != len(observed_ids):
                    raise AssertionError(
                        "durable decision ledger does not contain the complete imported canonical observation"
                    )

                _git(worktree, "add", str(DECISIONS_RELATIVE_PATH))
                diff = _git(worktree, "diff", "--cached", "--quiet", check=False)
                if diff.returncode not in {0, 1}:
                    raise RuntimeError(
                        f"git diff --cached --quiet failed: {diff.returncode}"
                    )

                if diff.returncode == 0:
                    return {
                        "status": "ALREADY_OBSERVED",
                        "snapshot_id": snapshot_id,
                        "source_run_id": source_run_id,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "base_sha": base_sha,
                        "persisted_commit_sha": base_sha,
                        "discovered": result["discovered"],
                        "appended": 0,
                        "durable_total": len(rows),
                        "replay_on_conflict": True,
                        "executions_touched": False,
                        "production_semantics_mutated": False,
                    }

                _git(
                    worktree,
                    "commit",
                    "-m",
                    f"Persist GenGe decision observation {snapshot_id} [skip ci]",
                )
                commit_sha = _git_text(worktree, "rev-parse", "HEAD")
                if _push_worktree(worktree, remote, branch):
                    return {
                        "status": "PERSISTED",
                        "snapshot_id": snapshot_id,
                        "source_run_id": source_run_id,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "base_sha": base_sha,
                        "persisted_commit_sha": commit_sha,
                        "discovered": result["discovered"],
                        "appended": result["appended"],
                        "durable_total": len(rows),
                        "replay_on_conflict": True,
                        "executions_touched": False,
                        "production_semantics_mutated": False,
                    }
                last_push_error = (
                    f"fast-forward push rejected on attempt {attempt}; replaying from latest {remote_ref}"
                )
            finally:
                _git(repo_root, "worktree", "remove", "--force", str(worktree), check=False)

        raise RuntimeError(
            last_push_error
            or f"failed to persist decision observation after {max_attempts} attempts"
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        _git(repo_root, "worktree", "prune", check=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    args = parser.parse_args(argv)

    result = persist_canonical_observation_with_replay(
        canonical_path=args.canonical,
        repo_root=args.repo_root,
        remote=args.remote,
        branch=args.branch,
        max_attempts=args.max_attempts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
