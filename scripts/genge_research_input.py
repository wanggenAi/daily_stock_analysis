#!/usr/bin/env python3
"""Lock a research run to one immutable GenGe data-package snapshot."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_LATEST = Path("data/data_package/latest.json")
PACKAGE_SNAPSHOTS = Path("data/data_package/snapshots")
OUT_DIR = Path("data/research_input")
OUT_LATEST = OUT_DIR / "latest.json"
CONTRACT = "GEN_GE_RESEARCH_INPUT_LOCK_V1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lock_research_input(*, mode: str, allow_stale_research_only: bool = False, write: bool = True) -> dict[str, Any]:
    if not PACKAGE_LATEST.is_file():
        raise FileNotFoundError(f"missing canonical data package: {PACKAGE_LATEST}")
    package = json.loads(PACKAGE_LATEST.read_text(encoding="utf-8"))
    if package.get("contract") != "GEN_GE_REALTIME_DATA_PACKAGE_V1":
        raise ValueError("unexpected data-package contract")
    snapshot_id = str(package.get("snapshot_id") or "")
    immutable = PACKAGE_SNAPSHOTS / f"{snapshot_id}.json"
    if not snapshot_id or not immutable.is_file():
        raise FileNotFoundError(f"immutable data-package snapshot missing: {snapshot_id}")
    locked = json.loads(immutable.read_text(encoding="utf-8"))
    if locked.get("snapshot_id") != snapshot_id:
        raise ValueError("data-package snapshot id mismatch")

    status = str(locked.get("package_status") or "INVALID")
    research_allowed = status in {"READY", "PARTIAL", "STALE"}
    execution_allowed = status == "READY"
    if status != "READY" and not allow_stale_research_only:
        research_allowed = False

    payload = {
        "contract": CONTRACT,
        "locked_at": _now(),
        "research_mode": mode,
        "input_snapshot_id": snapshot_id,
        "input_package_generated_at": locked.get("generated_at"),
        "latest_trade_date": locked.get("latest_trade_date"),
        "package_status": status,
        "research_allowed": research_allowed,
        "execution_allowed": execution_allowed,
        "network_policy": "CANONICAL_PACKAGE_ONLY",
        "external_fresh_evidence_policy": "TAGGED_EXCEPTION_ONLY",
        "external_fresh_evidence_tag": "EXTERNAL_FRESH_EVIDENCE",
        "external_fresh_evidence_used": False,
        "pending_external_fresh_evidence_count": locked.get("pending_external_fresh_evidence_count", 0),
        "datasets": [
            {
                "name": row.get("name"),
                "root": row.get("root"),
                "content_sha256": row.get("content_sha256"),
                "watermark": row.get("watermark"),
                "freshness_state": row.get("freshness_state"),
                "latest_observed_at": row.get("latest_observed_at"),
                "latest_trade_date": row.get("latest_trade_date"),
            }
            for row in locked.get("datasets") or []
        ],
        "fail_closed_reason": None if execution_allowed else f"DATA_PACKAGE_{status}_NOT_EXECUTABLE",
    }
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (OUT_DIR / f"{snapshot_id}-{mode}.json").write_text(text, encoding="utf-8")
        OUT_LATEST.write_text(text, encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("hourly", "eod", "long_term", "manual"), default="hourly")
    parser.add_argument("--allow-stale-research-only", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = lock_research_input(mode=args.mode, allow_stale_research_only=args.allow_stale_research_only, write=not args.no_write)
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({k: payload.get(k) for k in ("input_snapshot_id", "package_status", "research_allowed", "execution_allowed", "latest_trade_date")}, ensure_ascii=False))
    return 0 if payload["research_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
