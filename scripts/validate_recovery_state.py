#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MAX_BYTES = 16 * 1024
MAX_LIST_ITEMS = 20
MAX_STRING = 2048
TASK_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
ALLOWED_STATUS = {
    "IDLE", "IN_PROGRESS", "WAITING_CI", "WAITING_PRODUCTION", "BLOCKED", "DONE"
}
ALLOWED_OPERATION_PHASE = {"PREPARED", "UNKNOWN_OUTCOME", "OBSERVED_COMMITTED"}
REQUIRED = {
    "schema_version", "generation", "repository", "status", "task_key", "stage",
    "last_observed_main_sha", "work_branch", "work_head_sha", "active_pr", "ci",
    "production_or_artifact", "pending_operation", "health", "completed",
    "next_action", "do_not_repeat",
}
SECRET_KEY_FRAGMENTS = {
    "token", "secret", "password", "credential", "authorization", "cookie", "private_key"
}
SECRET_VALUE_PREFIXES = ("ghp_", "github_pat_", "sk-", "AKIA", "-----BEGIN PRIVATE KEY-----")


def fail(message: str) -> None:
    raise SystemExit(f"[recovery-state] ERROR: {message}")


def walk(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
                fail(f"sensitive key is forbidden at {path}.{key}")
            walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        if len(value) > MAX_LIST_ITEMS:
            fail(f"list exceeds {MAX_LIST_ITEMS} items at {path}")
        for index, child in enumerate(value):
            walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > MAX_STRING:
            fail(f"string exceeds {MAX_STRING} characters at {path}")
        if value.startswith(SECRET_VALUE_PREFIXES):
            fail(f"secret-like value is forbidden at {path}")


def validate(data: dict[str, Any], raw_size: int) -> None:
    if raw_size > MAX_BYTES:
        fail(f"state file is {raw_size} bytes; maximum is {MAX_BYTES}")
    missing = sorted(REQUIRED - set(data))
    if missing:
        fail(f"missing required fields: {', '.join(missing)}")
    if data["schema_version"] != 2:
        fail("schema_version must be 2")
    if not isinstance(data["generation"], int) or data["generation"] < 0:
        fail("generation must be a non-negative integer")
    if not isinstance(data["repository"], str) or "/" not in data["repository"]:
        fail("repository must be owner/name")
    if data["status"] not in ALLOWED_STATUS:
        fail(f"unsupported status: {data['status']!r}")
    task_key = data["task_key"]
    if task_key is not None:
        if not isinstance(task_key, str) or not TASK_KEY_RE.fullmatch(task_key):
            fail("task_key must be filesystem-safe lowercase [a-z0-9._-], maximum 96 chars")
    elif data["status"] not in {"IDLE", "DONE"}:
        fail("active recovery state requires a task_key")
    if not isinstance(data["ci"], dict):
        fail("ci must be an object")
    if not isinstance(data["production_or_artifact"], dict):
        fail("production_or_artifact must be an object")
    if not isinstance(data["health"], dict):
        fail("health must be an object")
    for name in ("completed", "do_not_repeat"):
        if not isinstance(data[name], list):
            fail(f"{name} must be a list")
    op = data["pending_operation"]
    if op is not None:
        if not isinstance(op, dict):
            fail("pending_operation must be null or an object")
        required_op = {
            "operation_id", "kind", "target", "phase", "idempotency", "prepared_generation"
        }
        missing_op = sorted(required_op - set(op))
        if missing_op:
            fail(f"pending_operation missing: {', '.join(missing_op)}")
        if op["phase"] not in ALLOWED_OPERATION_PHASE:
            fail(f"unsupported pending_operation phase: {op['phase']!r}")
        if not isinstance(op["prepared_generation"], int):
            fail("pending_operation.prepared_generation must be an integer")
        if op["prepared_generation"] > data["generation"]:
            fail("pending operation cannot be prepared in a future generation")
    walk(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    raw = args.path.read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        fail("top-level JSON must be an object")
    validate(data, len(raw))
    print("[recovery-state] OK")


if __name__ == "__main__":
    main()
