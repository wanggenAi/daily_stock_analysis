"""Bounded post-close recovery decision; never converts stale data to trading authority.

Reads the *persisted* investor brief as a health indicator, not as a fresh
price provider. Workflow may enqueue the EXISTING full-A producer only when
the completed mainland weekday session is not yet proven and no producer or
downstream finalizer is still active.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.strategies.genge_opportunity_discovery.generation_freshness import (
    SHANGHAI,
    expected_latest_trade_date,
)

_ACTIVE = frozenset({"queued", "in_progress", "waiting", "pending", "requested"})
_SOURCE_EVENTS = frozenset({"schedule", "workflow_dispatch"})
_MAX_POSTCLOSE_SOURCE_ATTEMPTS = 2


def _trade_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _run_after_close(run: Mapping[str, Any], expected: date) -> bool:
    timestamp = str(run.get("created_at") or "")
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    try:
        observed = datetime.fromisoformat(timestamp).astimezone(SHANGHAI)
    except (TypeError, ValueError):
        return False
    return observed.date() == expected and observed.time() >= time(16, 0)


def _fresh_dashboard(dashboard: Mapping[str, Any] | None, expected: date) -> bool:
    if not dashboard:
        return False
    freshness = dashboard.get("freshness_contract") or {}
    if not isinstance(freshness, dict) or freshness.get("fresh") is not True:
        return False
    # All three source-level dates must agree; a new generated_at is not proof.
    return (
        _trade_date(dashboard.get("latest_trade_date")) == expected
        and _trade_date(freshness.get("canonical_latest_trade_date")) == expected
        and _trade_date(freshness.get("market_as_of")) == expected
    )


def decide_recovery(
    dashboard: Mapping[str, Any] | None,
    upstream_runs: Sequence[Mapping[str, Any]],
    downstream_runs: Sequence[Mapping[str, Any]],
    *,
    evaluated_at: datetime,
    max_attempts: int = _MAX_POSTCLOSE_SOURCE_ATTEMPTS,
) -> dict[str, Any]:
    """Return SATISFIED/DEFER/DISPATCH/EXHAUSTED; fail closed on unknown health."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    local = evaluated_at.astimezone(SHANGHAI)
    expected = expected_latest_trade_date(evaluated_at)
    result: dict[str, Any] = {
        "expected_trade_date": expected.isoformat(),
        "checked_at": evaluated_at.astimezone(timezone.utc).isoformat(),
        "postclose_attempts": 0,
    }
    # The next-day 01:00 recovery still targets yesterday's completed session,
    # before today's trading has begun. Include Saturday 01:00 for Friday.
    evening = local.weekday() < 5 and local.time() >= time(19, 0)
    next_morning = local.weekday() in {1, 2, 3, 4, 5} and local.time() < time(8, 0)
    if not (evening or next_morning):
        return {**result, "action": "DEFER", "reason": "OUTSIDE_POSTCLOSE_RECOVERY_WINDOW"}
    if _fresh_dashboard(dashboard, expected):
        return {**result, "action": "SATISFIED", "reason": "MATCHED_VERIFIED_MARKET_EPOCH"}
    valid_producers = [
        run for run in upstream_runs
        if run.get("event") in _SOURCE_EVENTS and _run_after_close(run, expected)
    ]
    attempts = len({str(run.get("id")) for run in valid_producers if run.get("id") is not None})
    result["postclose_attempts"] = attempts
    all_active = list(valid_producers) + [
        run for run in downstream_runs if _run_after_close(run, expected)
    ]
    if any(str(run.get("status")) in _ACTIVE for run in all_active):
        return {**result, "action": "DEFER", "reason": "POSTCLOSE_PIPELINE_ACTIVE"}
    if attempts >= max_attempts:
        return {**result, "action": "EXHAUSTED", "reason": "POSTCLOSE_SCAN_LIMIT_REACHED_STILL_STALE"}
    return {**result, "action": "DISPATCH", "reason": "MISSING_VERIFIED_COMPLETED_SESSION"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--downstream", required=True, type=Path)
    parser.add_argument("--decision-file", required=True, type=Path)
    args = parser.parse_args()

    if args.dashboard.is_file() and args.dashboard.stat().st_size:
        dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
        if not isinstance(dashboard, dict):
            raise ValueError("published dashboard must be an object")
    else:
        dashboard = None

    def runs(path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("workflow_runs")
        if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
            raise ValueError(f"invalid workflow run response: {path}")
        return items

    decision = decide_recovery(
        dashboard, runs(args.upstream), runs(args.downstream),
        evaluated_at=datetime.now(timezone.utc),
    )
    args.decision_file.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
