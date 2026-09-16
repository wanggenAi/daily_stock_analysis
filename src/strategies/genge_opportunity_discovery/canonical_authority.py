"""Freshness-enforcing wrapper around the frozen canonical authority core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from . import canonical_authority_core as _core
from .canonical_authority_core import *  # noqa: F401,F403
from .generation_freshness import evaluate_generation_freshness

_ORIGINAL_VALIDATE = _core.validate_authority
_ORIGINAL_FINALIZE = _core.finalize_canonical


def validate_authority(
    authority: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    hourly_view: Mapping[str, Any] | None = None,
    daily_view: Mapping[str, Any] | None = None,
) -> None:
    _ORIGINAL_VALIDATE(authority, snapshot, hourly_view=hourly_view, daily_view=daily_view)
    freshness = authority.get("freshness_contract")
    if not isinstance(freshness, Mapping):
        raise ValueError("canonical authority missing generation freshness contract")
    if freshness.get("status") != "OK" or freshness.get("formal_new_exposure_allowed") is not True:
        raise ValueError("canonical authority is stale for new exposure")
    if authority.get("formal_new_exposure_allowed") is not True:
        raise ValueError("canonical authority must explicitly allow fresh new exposure")


def finalize_canonical(
    snapshot_path: Path,
    output_dir: Path,
    *,
    expected_source_run_id: str,
    source_workflow: str,
    expected_source_kind: str = "",
    source_head_sha: str = "",
    finalizer_run_id: str = "",
    finalizer_code_sha: str = "",
    finalized_at: str | None = None,
) -> dict[str, Path]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    freshness = evaluate_generation_freshness(
        snapshot,
        evaluated_at=finalized_at,
        strict_missing_metadata=True,
    )
    if freshness["status"] != "OK":
        raise ValueError(
            "STALE_UPSTREAM canonical authority refused: " + ",".join(freshness["reasons"])
        )

    outputs = _ORIGINAL_FINALIZE(
        snapshot_path,
        output_dir,
        expected_source_run_id=expected_source_run_id,
        source_workflow=source_workflow,
        expected_source_kind=expected_source_kind,
        source_head_sha=source_head_sha,
        finalizer_run_id=finalizer_run_id,
        finalizer_code_sha=finalizer_code_sha,
        finalized_at=finalized_at,
    )
    authority = json.loads(outputs["authority"].read_text(encoding="utf-8"))
    authority["freshness_contract"] = freshness
    authority["formal_new_exposure_allowed"] = True
    outputs["authority"].write_text(json.dumps(authority, ensure_ascii=False, indent=2), encoding="utf-8")
    hourly = json.loads(outputs["hourly"].read_text(encoding="utf-8"))
    daily = json.loads(outputs["daily"].read_text(encoding="utf-8"))
    validate_authority(authority, snapshot, hourly_view=hourly, daily_view=daily)
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-run-id", required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--expected-source-kind", default="")
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--finalizer-run-id", required=True)
    parser.add_argument("--finalizer-code-sha", required=True)
    args = parser.parse_args(argv)
    outputs = finalize_canonical(
        args.snapshot,
        args.output_dir,
        expected_source_run_id=args.expected_source_run_id,
        source_workflow=args.source_workflow,
        expected_source_kind=args.expected_source_kind,
        source_head_sha=args.source_head_sha,
        finalizer_run_id=args.finalizer_run_id,
        finalizer_code_sha=args.finalizer_code_sha,
    )
    print(";".join(f"{name}={path}" for name, path in outputs.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
