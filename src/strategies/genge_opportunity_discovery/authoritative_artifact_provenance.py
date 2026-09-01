"""Validate a downloaded V3.1.1 authoritative artifact before downstream replay.

This gate binds the files inside an authoritative Finalizer artifact to the exact
successful GitHub Actions Finalizer run selected by a downstream workflow. It
also revalidates the canonical source and producer-specific upstream run in the
workflow-run namespace, preventing stale/deleted IDs, job IDs, or cross-run
artifact mixing from becoming durable production state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .actions_provenance import (
    require_actions_run_id,
    validate_production_provenance,
)
from .canonical_authority import validate_authority


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def validate_authoritative_artifact(
    authoritative_root: Path,
    *,
    repository: str,
    token: str,
    expected_finalizer_run_id: object,
    api_get: Callable[[str, str], Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Fail closed unless one artifact is internally and externally authoritative."""
    root = Path(authoritative_root)
    authority = _read_object(root / "production_authority.json")
    snapshot = _read_object(root / "canonical_snapshot" / "latest.json")
    hourly = _read_object(root / "operating_views" / "hourly.json")
    daily = _read_object(root / "operating_views" / "daily.json")

    validate_authority(authority, snapshot, hourly_view=hourly, daily_view=daily)

    selected_finalizer_id = require_actions_run_id(
        expected_finalizer_run_id, field="expected_finalizer_run_id"
    )
    artifact_finalizer_id = require_actions_run_id(
        authority.get("finalizer_run_id"), field="artifact_finalizer_run_id"
    )
    if artifact_finalizer_id != selected_finalizer_id:
        raise ValueError(
            "authoritative artifact Finalizer run does not match the selected Finalizer run"
        )

    validate_production_provenance(
        repository=repository,
        token=token,
        source_run_id=authority.get("canonical_source_run_id"),
        source_workflow=str(authority.get("source_workflow") or ""),
        source_head_sha=str(authority.get("source_head_sha") or ""),
        upstream_run_id=authority.get("upstream_run_id"),
        finalizer_run_id=artifact_finalizer_id,
        finalizer_require_success=True,
        api_get=api_get,
    )

    if str(snapshot.get("source_run_id") or "") != str(authority.get("canonical_source_run_id") or ""):
        raise ValueError("authoritative artifact snapshot/source run mismatch")
    if str(snapshot.get("upstream_run_id") or "") != str(authority.get("upstream_run_id") or ""):
        raise ValueError("authoritative artifact snapshot/upstream run mismatch")

    return {
        "status": "VALID",
        "canonical_snapshot_id": str(authority.get("canonical_snapshot_id") or ""),
        "source_run_id": str(authority.get("canonical_source_run_id") or ""),
        "upstream_run_id": str(authority.get("upstream_run_id") or ""),
        "finalizer_run_id": artifact_finalizer_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authoritative-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--expected-finalizer-run-id", required=True)
    args = parser.parse_args(argv)

    result = validate_authoritative_artifact(
        args.authoritative_root,
        repository=args.repository,
        token=args.token,
        expected_finalizer_run_id=args.expected_finalizer_run_id,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
