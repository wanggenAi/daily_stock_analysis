from __future__ import annotations

import json
import subprocess
from pathlib import Path

import src.strategies.genge_opportunity_discovery.candidate_lifecycle_git_persistence as git_persistence
from src.strategies.genge_opportunity_discovery.candidate_lifecycle_git_persistence import (
    publish_candidate_lifecycle_with_replay,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _snapshot(run_id: str, generated_at: str) -> dict:
    deep = [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "industry": "电网设备",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "v31_candidate_class": "WATCH / BUY_REVIEW",
            "valuation_confidence": "MEDIUM",
            "latest_trade_date": "2026-08-27",
        }
    ]
    production = [
        {
            "code": "600312",
            "stock_name": "平高电气",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
            "production_model_version": PRODUCTION_VERSION,
            "v311_production_bridge": PRODUCTION_BRIDGE,
            "strict_pit_refresh_applied": "True",
            "upstream_policy_reused": "False",
            "no_auto_trade": "True",
            "current_price": "20.43",
            "decision_date": "2026-08-27",
            "price_date": "2026-08-27",
            "valuation_confidence": "MEDIUM",
        }
    ]
    return build_snapshot(
        [],
        deep,
        production,
        source_kind="every-industry",
        source_run_id=run_id,
        upstream_run_id=f"upstream:{run_id}",
        generated_at=generated_at,
        research_as_of=generated_at,
        source_hashes={
            "discovery_csv": f"{run_id}-d",
            "deep_review_csv": f"{run_id}-r",
            "production_csv": f"{run_id}-p",
        },
    )


def _init_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    _run(tmp_path, "git", "init", "--bare", str(remote))
    seed.mkdir()
    _run(seed, "git", "init")
    _run(seed, "git", "config", "user.name", "test")
    _run(seed, "git", "config", "user.email", "test@example.com")
    (seed / "V31_CANDIDATE_LEDGER.md").write_text(
        """# V31_CANDIDATE_LEDGER

## Active candidate ledger

### 600312 平高电气
- **seen_count:** 9
- **current tier:** WATCH / BUY_REVIEW
""",
        encoding="utf-8",
    )
    _run(seed, "git", "add", "V31_CANDIDATE_LEDGER.md")
    _run(seed, "git", "commit", "-m", "seed")
    _run(seed, "git", "branch", "-M", "main")
    _run(seed, "git", "remote", "add", "origin", str(remote))
    _run(seed, "git", "push", "-u", "origin", "main")
    return seed, remote


def _write_snapshot(tmp_path: Path, snapshot: dict, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    return path


def _remote_json(remote: Path, path: str) -> dict:
    text = _run(remote, "git", "show", f"main:{path}")
    return json.loads(text)


def _remote_commit_count(remote: Path) -> int:
    return int(_run(remote, "git", "rev-list", "--count", "main"))


def test_publish_replays_from_latest_remote_and_same_snapshot_is_noop(tmp_path: Path) -> None:
    repo, remote = _init_remote(tmp_path)
    authoritative = tmp_path / "authoritative"
    first = _snapshot("100", "2026-08-27T08:00:00+00:00")
    second = _snapshot("101", "2026-08-27T09:00:00+00:00")
    first_path = _write_snapshot(tmp_path, first, "first.json")
    second_path = _write_snapshot(tmp_path, second, "second.json")

    first_result = publish_candidate_lifecycle_with_replay(
        snapshot_path=first_path,
        authoritative_dir=authoritative,
        repo_root=repo,
        max_attempts=2,
    )
    first_commit_count = _remote_commit_count(remote)

    duplicate_result = publish_candidate_lifecycle_with_replay(
        snapshot_path=first_path,
        authoritative_dir=authoritative,
        repo_root=repo,
        max_attempts=2,
    )
    duplicate_commit_count = _remote_commit_count(remote)

    second_result = publish_candidate_lifecycle_with_replay(
        snapshot_path=second_path,
        authoritative_dir=authoritative,
        repo_root=repo,
        max_attempts=2,
    )
    state = _remote_json(
        remote,
        "data/opportunity_snapshots/candidate_lifecycle_state.json",
    )

    assert first_result["status"] == "PERSISTED"
    assert duplicate_result["status"] == "ALREADY_PERSISTED"
    assert duplicate_commit_count == first_commit_count
    assert second_result["status"] == "PERSISTED"
    assert state["latest_applied_snapshot_id"] == second["snapshot_id"]
    assert state["applied_snapshot_ids"][-2:] == [first["snapshot_id"], second["snapshot_id"]]
    assert state["candidates"]["600312"]["seen_count"] == 2
    assert state["candidates"]["600312"]["legacy_seen_count_imported"] == 9
    assert (authoritative / "candidate_lifecycle/persistence_replay.json").is_file()
    assert "GENERATED FILE — DO NOT EDIT" in _run(
        remote,
        "git",
        "show",
        "main:V31_CANDIDATE_LEDGER.md",
    )
    assert _run(
        remote,
        "git",
        "show",
        "main:V31_CANDIDATE_RESEARCH_NOTES_LEGACY.md",
    ).startswith("# V31_CANDIDATE_LEDGER")


def test_rejected_push_discards_stale_generation_and_replays(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo, remote = _init_remote(tmp_path)
    authoritative = tmp_path / "authoritative"
    baseline = _snapshot("199", "2026-08-27T09:00:00+00:00")
    snapshot = _snapshot("200", "2026-08-27T10:00:00+00:00")
    baseline_path = _write_snapshot(tmp_path, baseline, "baseline.json")
    snapshot_path = _write_snapshot(tmp_path, snapshot, "snapshot.json")

    baseline_result = publish_candidate_lifecycle_with_replay(
        snapshot_path=baseline_path,
        authoritative_dir=authoritative,
        repo_root=repo,
        max_attempts=2,
    )
    assert baseline_result["status"] == "PERSISTED"

    real_push = git_persistence._push_worktree
    calls = {"count": 0}

    def reject_once(worktree: Path, remote_name: str, branch: str) -> bool:
        calls["count"] += 1
        if calls["count"] == 1:
            competitor = tmp_path / "competitor"
            _run(tmp_path, "git", "clone", str(remote), str(competitor))
            # The bare test remote's symbolic HEAD is not guaranteed to follow the
            # renamed main branch, so explicitly check out the branch under test.
            _run(competitor, "git", "checkout", "-B", "main", "origin/main")
            _run(competitor, "git", "config", "user.name", "competitor")
            _run(competitor, "git", "config", "user.email", "competitor@example.com")
            state_path = competitor / "data/opportunity_snapshots/candidate_lifecycle_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            candidate = state["candidates"]["600312"]
            assert candidate["seen_count"] == 1
            candidate["seen_count"] = 7
            candidate["concurrent_writer_marker"] = "preserve-me"
            state_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _run(competitor, "git", "add", str(state_path.relative_to(competitor)))
            _run(competitor, "git", "commit", "-m", "concurrent lifecycle update")
            _run(competitor, "git", "push", "origin", "HEAD:main")
            return False
        return real_push(worktree, remote_name, branch)

    monkeypatch.setattr(git_persistence, "_push_worktree", reject_once)
    result = publish_candidate_lifecycle_with_replay(
        snapshot_path=snapshot_path,
        authoritative_dir=authoritative,
        repo_root=repo,
        max_attempts=3,
    )
    state = _remote_json(
        remote,
        "data/opportunity_snapshots/candidate_lifecycle_state.json",
    )

    assert calls["count"] == 2
    assert result["status"] == "PERSISTED"
    assert result["attempt"] == 2
    assert result["replay_on_conflict"] is True
    assert state["latest_applied_snapshot_id"] == snapshot["snapshot_id"]
    assert state["candidates"]["600312"]["seen_count"] == 8
    assert state["candidates"]["600312"]["concurrent_writer_marker"] == "preserve-me"
