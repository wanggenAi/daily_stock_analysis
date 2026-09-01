"""Finalize one validated GenGe V3.1.1 canonical snapshot for production consumers.

This module deliberately does not rank stocks, recompute valuation, or create a
new trading decision. Its only job is to authenticate one already-built
canonical snapshot and publish read-only hourly/daily operating views from that
same snapshot.

There may be more than one legitimate production cycle per trading day (for
example premarket One Shot and post-close Every-Industry research). Each cycle
must still have exactly one formal truth: its validated canonical ``snapshot_id``.
The authority layer prevents a downstream workflow from silently becoming a
competing decision engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .actions_provenance import (
    EVERY_INDUSTRY_WORKFLOW,
    ONE_SHOT_WORKFLOW,
    require_actions_run_id,
    require_git_sha,
    require_upstream_run_ref,
)
from .canonical_operating_view import (
    DAILY_SETTLEMENT,
    HOURLY_MONITOR,
    build_operating_view,
)
from .canonical_snapshot import PRODUCTION_VERSION, validate_snapshot

AUTHORITY_CONTRACT_VERSION = "GEN_GE_V31_CANONICAL_AUTHORITY_V1"
AUTHORIZED_SOURCE_KINDS = frozenset(
    {
        "every-industry",
        "GenGe All-A V3.1.1 One Shot",
    }
)
SOURCE_WORKFLOW_BY_KIND = {
    "every-industry": EVERY_INDUSTRY_WORKFLOW,
    "GenGe All-A V3.1.1 One Shot": ONE_SHOT_WORKFLOW,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _require_source_workflow(source_kind: str, source_workflow: object) -> str:
    expected = SOURCE_WORKFLOW_BY_KIND.get(source_kind)
    if expected is None:
        raise ValueError(f"production authority rejects source_kind={source_kind!r}")
    workflow = str(source_workflow or "").strip()
    if workflow != expected:
        raise ValueError(
            f"production authority workflow/source kind mismatch: expected {expected!r}, got {workflow!r}"
        )
    return workflow


def validate_authority(
    authority: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    hourly_view: Mapping[str, Any] | None = None,
    daily_view: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed unless the receipt and every consumer view share one truth."""
    validate_snapshot(snapshot)
    if authority.get("contract_version") != AUTHORITY_CONTRACT_VERSION:
        raise ValueError("canonical authority contract version mismatch")
    if authority.get("authorized") is not True:
        raise ValueError("canonical authority is not authorized")
    if authority.get("production_version") != PRODUCTION_VERSION:
        raise ValueError("canonical authority production version mismatch")

    snapshot_id = str(snapshot.get("snapshot_id") or "")
    if authority.get("canonical_snapshot_id") != snapshot_id:
        raise ValueError("canonical authority snapshot mismatch")
    canonical_source_run_id = require_actions_run_id(
        authority.get("canonical_source_run_id"), field="canonical_source_run_id"
    )
    snapshot_source_run_id = require_actions_run_id(
        snapshot.get("source_run_id"), field="snapshot_source_run_id"
    )
    if canonical_source_run_id != snapshot_source_run_id:
        raise ValueError("canonical authority source run mismatch")

    canonical_source_kind = str(authority.get("canonical_source_kind") or "")
    snapshot_source_kind = str(snapshot.get("source_kind") or "")
    if canonical_source_kind != snapshot_source_kind:
        raise ValueError("canonical authority source kind mismatch")
    source_workflow = _require_source_workflow(
        canonical_source_kind, authority.get("source_workflow")
    )

    authority_upstream_run_id = require_upstream_run_ref(
        authority.get("upstream_run_id"),
        source_run_id=canonical_source_run_id,
        source_workflow=source_workflow,
    )
    snapshot_upstream_run_id = require_upstream_run_ref(
        snapshot.get("upstream_run_id"),
        source_run_id=snapshot_source_run_id,
        source_workflow=source_workflow,
    )
    if authority_upstream_run_id != snapshot_upstream_run_id:
        raise ValueError("canonical authority upstream run mismatch")

    require_git_sha(authority.get("source_head_sha"), field="source_head_sha")
    require_actions_run_id(authority.get("finalizer_run_id"), field="finalizer_run_id")
    require_git_sha(authority.get("finalizer_code_sha"), field="finalizer_code_sha")

    consumer_contract = authority.get("consumer_contract") or {}
    if consumer_contract.get("canonical_is_only_formal_decision_truth") is not True:
        raise ValueError("authority must designate canonical as the only formal decision truth")
    if consumer_contract.get("consumer_may_recompute_formal_action") is not False:
        raise ValueError("authority must forbid consumer formal-action recomputation")
    if consumer_contract.get("overlay_may_overwrite_formal_action") is not False:
        raise ValueError("authority must forbid overlays from overwriting formal actions")

    for expected_mode, view in ((HOURLY_MONITOR, hourly_view), (DAILY_SETTLEMENT, daily_view)):
        if view is None:
            continue
        if view.get("mode") != expected_mode:
            raise ValueError(f"canonical consumer mode mismatch: {expected_mode}")
        if view.get("canonical_snapshot_id") != snapshot_id:
            raise ValueError(f"canonical consumer snapshot mismatch: {expected_mode}")
        if str(view.get("source_run_id") or "") != str(snapshot.get("source_run_id") or ""):
            raise ValueError(f"canonical consumer source run mismatch: {expected_mode}")


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
    """Authenticate a canonical snapshot without recomputing any investment decision."""
    expected_source_run_id = require_actions_run_id(
        expected_source_run_id, field="expected_source_run_id"
    )
    snapshot = _load_json(snapshot_path)
    validate_snapshot(snapshot, expected_source_run_id=expected_source_run_id)

    source_kind = str(snapshot.get("source_kind") or "")
    if source_kind not in AUTHORIZED_SOURCE_KINDS:
        raise ValueError(
            f"production authority rejects source_kind={source_kind!r}; "
            f"allowed={sorted(AUTHORIZED_SOURCE_KINDS)!r}"
        )
    if expected_source_kind and source_kind != expected_source_kind:
        raise ValueError(
            f"production authority source kind mismatch: expected {expected_source_kind!r}, got {source_kind!r}"
        )
    source_workflow = _require_source_workflow(source_kind, source_workflow)
    upstream_run_id = require_upstream_run_ref(
        snapshot.get("upstream_run_id"),
        source_run_id=expected_source_run_id,
        source_workflow=source_workflow,
    )
    if not str(snapshot.get("latest_trade_date") or "").strip():
        raise ValueError("production authority requires a canonical latest_trade_date")

    source_head_sha = require_git_sha(source_head_sha, field="source_head_sha")
    finalizer_run_id = require_actions_run_id(finalizer_run_id, field="finalizer_run_id")
    finalizer_code_sha = require_git_sha(finalizer_code_sha, field="finalizer_code_sha")

    source_hashes = snapshot.get("source_hashes") or {}
    if not isinstance(source_hashes, Mapping) or not source_hashes:
        raise ValueError("production authority requires canonical source hashes")

    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir = output_dir / "canonical_snapshot"
    view_dir = output_dir / "operating_views"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    view_dir.mkdir(parents=True, exist_ok=True)

    canonical_copy = canonical_dir / "latest.json"
    shutil.copyfile(snapshot_path, canonical_copy)

    hourly = build_operating_view(snapshot, mode=HOURLY_MONITOR)
    daily = build_operating_view(snapshot, mode=DAILY_SETTLEMENT)
    hourly_path = view_dir / "hourly.json"
    daily_path = view_dir / "daily.json"
    hourly_path.write_text(json.dumps(hourly, ensure_ascii=False, indent=2), encoding="utf-8")
    daily_path.write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")

    finalized = finalized_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    authority = {
        "contract_version": AUTHORITY_CONTRACT_VERSION,
        "authorized": True,
        "canonical_snapshot_id": str(snapshot["snapshot_id"]),
        "canonical_sha256": _sha256(canonical_copy),
        "canonical_source_kind": source_kind,
        "canonical_source_run_id": expected_source_run_id,
        "upstream_run_id": upstream_run_id,
        "source_workflow": source_workflow,
        "source_head_sha": source_head_sha,
        "finalizer_run_id": finalizer_run_id,
        "finalizer_code_sha": finalizer_code_sha,
        "production_version": str(snapshot.get("production_version") or ""),
        "latest_trade_date": str(snapshot.get("latest_trade_date") or ""),
        "research_as_of": str(snapshot.get("research_as_of") or ""),
        "finalized_at": finalized,
        "source_hashes": dict(source_hashes),
        "consumer_contract": {
            "one_formal_truth_per_production_cycle": True,
            "canonical_is_only_formal_decision_truth": True,
            "consumer_may_recompute_formal_action": False,
            "overlay_may_overwrite_formal_action": False,
            "fresh_price_or_news_overlay_allowed": True,
            "formal_action_change_requires_new_validated_canonical_snapshot": True,
            "hourly_and_daily_must_share_snapshot_id": True,
            "candidate_ledger_may_filter_broad_discovery": False,
            "production_threshold_change_allowed": False,
        },
        "no_auto_trade": True,
    }
    validate_authority(authority, snapshot, hourly_view=hourly, daily_view=daily)

    authority_path = output_dir / "production_authority.json"
    authority_path.write_text(json.dumps(authority, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "canonical": canonical_copy,
        "authority": authority_path,
        "hourly": hourly_path,
        "daily": daily_path,
    }


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
