"""Durable local persistence for Era Radar machine truth.

This is deliberately separate from V3.1.1 Canonical/Formal persistence.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .lifecycle import LifecycleRecord, apply_lifecycle
from .pipeline import RadarSnapshot, render_markdown

SCHEMA = "ERA_RADAR_LIFECYCLE_V1"


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def load_lifecycle(path: str | Path) -> dict[str, LifecycleRecord]:
    target = Path(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA or not isinstance(payload.get("trends"), dict):
        raise ValueError("invalid era radar lifecycle state")
    result = {}
    for trend_id, raw in payload["trends"].items():
        result[trend_id] = LifecycleRecord(**raw)
    return result


def persist_snapshot(snapshot: RadarSnapshot, output_dir: str | Path) -> dict:
    root = Path(output_dir)
    state_path = root / "trend_lifecycle_state.json"
    current = load_lifecycle(state_path)

    # A durable state can only move forward globally. Exact replay is allowed.
    latest_times = {record.latest_observed_at for record in current.values()}
    if latest_times and snapshot.research_as_of < max(latest_times):
        raise ValueError("out-of-order era radar snapshot")

    next_state = dict(current)
    events = []
    for trend in snapshot.trends:
        transition = apply_lifecycle(
            current.get(trend.trend_id),
            trend_id=trend.trend_id,
            snapshot_id=snapshot.snapshot_id,
            observed_at=snapshot.research_as_of,
            proposed_state=trend.lifecycle,
        )
        next_state[trend.trend_id] = transition.record
        events.append({"trend_id": trend.trend_id, "event": transition.event, "changed": transition.changed})

    duplicate = bool(snapshot.trends) and all(item["event"] == "NOOP" for item in events)
    status = "ALREADY_PERSISTED" if duplicate else "PERSISTED"
    if not duplicate:
        _atomic_json(root / "history" / f"{snapshot.snapshot_id}.json", snapshot.to_dict())
        _atomic_json(root / "evidence" / f"{snapshot.snapshot_id}.json", {
            "snapshot_id": snapshot.snapshot_id,
            "research_as_of": snapshot.research_as_of,
            "note": "Evidence bundle is supplied by collectors; snapshot stores scored machine truth.",
        })
        state_payload = {
            "schema_version": SCHEMA,
            "latest_snapshot_id": snapshot.snapshot_id,
            "latest_research_as_of": snapshot.research_as_of,
            "formal_trading_authority": False,
            "no_auto_trade": True,
            "trends": {key: asdict(value) for key, value in sorted(next_state.items())},
        }
        _atomic_json(state_path, state_payload)
        _atomic_json(root / "latest.json", snapshot.to_dict())
        _atomic_text(root / "ERA_CAPITAL_TREND_RADAR.md", render_markdown(snapshot))

    return {"status": status, "snapshot_id": snapshot.snapshot_id, "events": events}
