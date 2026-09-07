from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.decision_outcome_git_persistence as persistence
from scripts.decision_outcome_git_persistence import (
    persist_canonical_observation_with_replay,
)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _canonical(snapshot_id: str, run_id: str, action: str = "HOLD") -> dict:
    return {
        "snapshot_id": snapshot_id,
        "source_run_id": run_id,
        "latest_trade_date": "2026-09-05",
        "research_as_of": "2026-09-05T00:00:00Z",
        "holding_decisions": [
            {
                "symbol": "603993",
                "name": "洛阳钼业",
                "formal_action": action,
            }
        ],
        "candidate_decisions": [
            {
                "symbol": "600309",
                "name": "万华化学",
                "formal_action": "WAIT_PRICE",
            }
        ],
    }


def _init_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    _run(tmp_path, "git", "init", "--bare", str(remote))
    seed.mkdir()
    _run(seed, "git", "init")
    _run(seed, "git", "config", "user.name", "test")
    _run(seed, "git", "config", "user.email", "test@example.com")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _run(seed, "git", "add", "README.md")
    _run(seed, "git", "commit", "-m", "seed")
    _run(seed, "git", "branch", "-M", "main")
    _run(seed, "git", "remote", "add", "origin", str(remote))
    _run(seed, "git", "push", "-u", "origin", "main")
    return seed, remote


def _write_canonical(tmp_path: Path, payload: dict, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _remote_lines(remote: Path, path: str) -> list[dict]:
    text = _run(remote, "git", "show", f"main:{path}")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _remote_commit_count(remote: Path) -> int:
    return int(_run(remote, "git", "rev-list", "--count", "main"))


def test_same_snapshot_is_idempotent_and_never_creates_execution_ledger(tmp_path: Path) -> None:
    repo, remote = _init_remote(tmp_path)
    canonical_path = _write_canonical(
        tmp_path,
        _canonical("snap-1", "1001"),
        "canonical.json",
    )

    first = persist_canonical_observation_with_replay(
        canonical_path=canonical_path,
        repo_root=repo,
        max_attempts=2,
    )
    first_count = _remote_commit_count(remote)
    second = persist_canonical_observation_with_replay(
        canonical_path=canonical_path,
        repo_root=repo,
        max_attempts=2,
    )
    second_count = _remote_commit_count(remote)
    rows = _remote_lines(remote, "data/decision_outcomes/decision_events.jsonl")

    assert first["status"] == "PERSISTED"
    assert first["appended"] == 2
    assert second["status"] == "ALREADY_OBSERVED"
    assert second["appended"] == 0
    assert second_count == first_count
    assert len(rows) == 2
    assert {row["snapshot_id"] for row in rows} == {"snap-1"}
    assert _run(remote, "git", "ls-tree", "-r", "--name-only", "main").find(
        "data/decision_outcomes/execution_events.jsonl"
    ) == -1


def test_new_snapshot_appends_without_rewriting_prior_observation(tmp_path: Path) -> None:
    repo, remote = _init_remote(tmp_path)
    first_path = _write_canonical(tmp_path, _canonical("snap-1", "1001"), "first.json")
    second_path = _write_canonical(tmp_path, _canonical("snap-2", "1002", "ADD"), "second.json")

    persist_canonical_observation_with_replay(
        canonical_path=first_path,
        repo_root=repo,
        max_attempts=2,
    )
    result = persist_canonical_observation_with_replay(
        canonical_path=second_path,
        repo_root=repo,
        max_attempts=2,
    )
    rows = _remote_lines(remote, "data/decision_outcomes/decision_events.jsonl")

    assert result["status"] == "PERSISTED"
    assert result["appended"] == 2
    assert len(rows) == 4
    assert [row["snapshot_id"] for row in rows].count("snap-1") == 2
    assert [row["snapshot_id"] for row in rows].count("snap-2") == 2


def test_rejected_push_replays_and_preserves_concurrent_decision_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo, remote = _init_remote(tmp_path)
    baseline_path = _write_canonical(tmp_path, _canonical("snap-1", "1001"), "baseline.json")
    target_path = _write_canonical(tmp_path, _canonical("snap-2", "1002"), "target.json")
    persist_canonical_observation_with_replay(
        canonical_path=baseline_path,
        repo_root=repo,
        max_attempts=2,
    )

    real_push = persistence._push_worktree
    calls = {"count": 0}

    def reject_once(worktree: Path, remote_name: str, branch: str) -> bool:
        calls["count"] += 1
        if calls["count"] == 1:
            competitor = tmp_path / "competitor"
            _run(tmp_path, "git", "clone", str(remote), str(competitor))
            _run(competitor, "git", "checkout", "-B", "main", "origin/main")
            _run(competitor, "git", "config", "user.name", "competitor")
            _run(competitor, "git", "config", "user.email", "competitor@example.com")
            ledger = competitor / "data/decision_outcomes/decision_events.jsonl"
            concurrent_row = {
                "event_type": "CANONICAL_DECISION_OBSERVED",
                "decision_id": "dec_concurrent",
                "snapshot_id": "snap-concurrent",
                "source_run_id": "1999",
                "symbol": "601318",
                "action": "HOLD_REVIEW",
                "observed_at": "2026-09-05T00:01:00Z",
            }
            with ledger.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(concurrent_row, ensure_ascii=False, sort_keys=True) + "\n")
            _run(competitor, "git", "add", "data/decision_outcomes/decision_events.jsonl")
            _run(competitor, "git", "commit", "-m", "concurrent decision observation")
            _run(competitor, "git", "push", "origin", "HEAD:main")
            return False
        return real_push(worktree, remote_name, branch)

    monkeypatch.setattr(persistence, "_push_worktree", reject_once)
    result = persist_canonical_observation_with_replay(
        canonical_path=target_path,
        repo_root=repo,
        max_attempts=3,
    )
    rows = _remote_lines(remote, "data/decision_outcomes/decision_events.jsonl")

    assert calls["count"] == 2
    assert result["status"] == "PERSISTED"
    assert result["attempt"] == 2
    assert result["replay_on_conflict"] is True
    assert any(row["decision_id"] == "dec_concurrent" for row in rows)
    assert [row["snapshot_id"] for row in rows].count("snap-1") == 2
    assert [row["snapshot_id"] for row in rows].count("snap-2") == 2
