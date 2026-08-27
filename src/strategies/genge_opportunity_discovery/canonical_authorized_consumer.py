"""Load finalized GenGe V3.1.1 authority artifacts for downstream consumers.

Downstream jobs must never reconstruct a formal investment decision from durable
markdown, an older raw snapshot, a different workflow run, or a fresh market-data
overlay.  This module is the read-side guard for that rule: it accepts only a
complete artifact produced by ``GenGe V3.1.1 Production Finalizer`` and returns
one validated hourly or daily operating view plus the holding-sync state bound to
that exact canonical snapshot.

It deliberately performs no stock ranking, valuation, lifecycle transition, or
trading-action recomputation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .canonical_authority import validate_authority
from .canonical_holdings_reconciliation import (
    HOLDINGS_IN_SYNC,
    HOLDINGS_OUT_OF_SYNC,
    HOLDINGS_RECONCILIATION_VERSION,
)
from .canonical_operating_view import DAILY_SETTLEMENT, HOURLY_MONITOR
from .canonical_snapshot import PRODUCTION_VERSION, validate_snapshot

AUTHORIZED_PRODUCER_KINDS = {
    "GenGe V3.1.1 Every-Industry Research": "every-industry",
    "GenGe All-A V3.1.1 One Shot": "GenGe All-A V3.1.1 One Shot",
}

_MODE_FILES = {
    HOURLY_MONITOR: "hourly.json",
    DAILY_SETTLEMENT: "daily.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"authorized canonical artifact missing required file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_holdings_reconciliation(
    reconciliation: dict[str, Any],
    *,
    snapshot_id: str,
    source_run_id: str,
) -> None:
    if reconciliation.get("contract_version") != HOLDINGS_RECONCILIATION_VERSION:
        raise ValueError("authorized holdings reconciliation contract mismatch")
    if str(reconciliation.get("canonical_snapshot_id") or "") != snapshot_id:
        raise ValueError("authorized holdings reconciliation snapshot mismatch")
    if str(reconciliation.get("canonical_source_run_id") or "") != source_run_id:
        raise ValueError("authorized holdings reconciliation source run mismatch")
    status = str(reconciliation.get("status") or "")
    if status not in {HOLDINGS_IN_SYNC, HOLDINGS_OUT_OF_SYNC}:
        raise ValueError("authorized holdings reconciliation status invalid")
    in_sync = reconciliation.get("in_sync") is True
    usable = reconciliation.get("formal_holding_actions_currently_usable") is True
    if in_sync != usable:
        raise ValueError("holdings reconciliation usability does not match sync state")
    if status == HOLDINGS_IN_SYNC and not in_sync:
        raise ValueError("HOLDINGS_IN_SYNC requires in_sync=true")
    if status == HOLDINGS_OUT_OF_SYNC and in_sync:
        raise ValueError("HOLDINGS_OUT_OF_SYNC requires in_sync=false")
    if reconciliation.get("candidate_formal_actions_affected_by_holdings_mismatch") is not False:
        raise ValueError("holdings mismatch must not invalidate canonical candidate actions")
    if reconciliation.get("no_auto_trade") is not True:
        raise ValueError("holdings reconciliation no-auto-trade contract missing")


def load_authorized_view(authority_root: Path, *, mode: str) -> dict[str, Any]:
    """Return one authenticated read-only operating view or fail closed.

    ``authority_root`` is the ``authoritative`` directory from a single
    ``genge-v311-authoritative-canonical-*`` artifact.
    """
    normalized_mode = str(mode or "").strip().upper()
    if normalized_mode not in _MODE_FILES:
        raise ValueError(f"unsupported authorized consumer mode: {mode}")

    authority_path = authority_root / "production_authority.json"
    snapshot_path = authority_root / "canonical_snapshot" / "latest.json"
    view_path = authority_root / "operating_views" / _MODE_FILES[normalized_mode]
    holdings_path = authority_root / "holdings_reconciliation.json"

    authority = _load_json(authority_path)
    snapshot = _load_json(snapshot_path)
    view = _load_json(view_path)
    holdings = _load_json(holdings_path)

    source_workflow = str(authority.get("source_workflow") or "")
    expected_kind = AUTHORIZED_PRODUCER_KINDS.get(source_workflow)
    if expected_kind is None:
        raise ValueError(f"unauthorized canonical producer workflow: {source_workflow!r}")

    canonical_source_run_id = str(authority.get("canonical_source_run_id") or "")
    if not canonical_source_run_id:
        raise ValueError("authorized canonical source run id missing")
    if not str(authority.get("finalizer_run_id") or ""):
        raise ValueError("authorized canonical finalizer run id missing")
    if not str(authority.get("finalized_at") or ""):
        raise ValueError("authorized canonical finalized_at missing")

    validate_snapshot(snapshot, expected_source_run_id=canonical_source_run_id)
    if normalized_mode == HOURLY_MONITOR:
        validate_authority(authority, snapshot, hourly_view=view)
    else:
        validate_authority(authority, snapshot, daily_view=view)

    if str(snapshot.get("source_kind") or "") != expected_kind:
        raise ValueError("canonical producer/source_kind mismatch")
    if str(authority.get("canonical_source_kind") or "") != expected_kind:
        raise ValueError("authority producer/source_kind mismatch")

    expected_digest = str(authority.get("canonical_sha256") or "")
    actual_digest = _sha256(snapshot_path)
    if not expected_digest or expected_digest != actual_digest:
        raise ValueError("canonical authority digest mismatch")

    snapshot_id = str(snapshot.get("snapshot_id") or "")
    if str(view.get("canonical_snapshot_id") or "") != snapshot_id:
        raise ValueError("authorized operating view snapshot mismatch")
    if str(view.get("source_run_id") or "") != canonical_source_run_id:
        raise ValueError("authorized operating view source run mismatch")
    if str(view.get("upstream_run_id") or "") != str(snapshot.get("upstream_run_id") or ""):
        raise ValueError("authorized operating view upstream run mismatch")
    if str(view.get("production_version") or "") != PRODUCTION_VERSION:
        raise ValueError("authorized operating view production version mismatch")
    if str(view.get("latest_trade_date") or "") != str(snapshot.get("latest_trade_date") or ""):
        raise ValueError("authorized operating view trade date mismatch")
    if authority.get("no_auto_trade") is not True:
        raise ValueError("authorized canonical no-auto-trade contract missing")

    consumer_contract = view.get("consumer_contract") or {}
    if consumer_contract.get("same_canonical_truth_required") is not True:
        raise ValueError("authorized consumer same-truth contract missing")
    if consumer_contract.get("decision_recalculation_allowed") is not False:
        raise ValueError("authorized consumer must not recalculate formal actions")
    if consumer_contract.get("decision_mutation_allowed") is not False:
        raise ValueError("authorized consumer must not mutate formal actions")
    if consumer_contract.get("research_overlay_may_overwrite_canonical_action") is not False:
        raise ValueError("authorized consumer overlay overwrite must be forbidden")

    _validate_holdings_reconciliation(
        holdings,
        snapshot_id=snapshot_id,
        source_run_id=canonical_source_run_id,
    )

    return {
        "mode": normalized_mode,
        "canonical_snapshot_id": snapshot_id,
        "canonical_source_run_id": canonical_source_run_id,
        "source_workflow": source_workflow,
        "source_kind": expected_kind,
        "latest_trade_date": str(snapshot.get("latest_trade_date") or ""),
        "research_as_of": str(snapshot.get("research_as_of") or ""),
        "finalized_at": str(authority.get("finalized_at") or ""),
        "holdings_status": str(holdings.get("status") or ""),
        "formal_holding_actions_currently_usable": bool(
            holdings.get("formal_holding_actions_currently_usable") is True
        ),
        "authority": authority,
        "canonical": snapshot,
        "view": view,
        "holdings_reconciliation": holdings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument(
        "--mode",
        required=True,
        choices=(HOURLY_MONITOR, DAILY_SETTLEMENT),
    )
    args = parser.parse_args(argv)
    bundle = load_authorized_view(args.authority_root, mode=args.mode)
    print(
        json.dumps(
            {
                "mode": bundle["mode"],
                "canonical_snapshot_id": bundle["canonical_snapshot_id"],
                "canonical_source_run_id": bundle["canonical_source_run_id"],
                "source_workflow": bundle["source_workflow"],
                "source_kind": bundle["source_kind"],
                "latest_trade_date": bundle["latest_trade_date"],
                "research_as_of": bundle["research_as_of"],
                "finalized_at": bundle["finalized_at"],
                "holdings_status": bundle["holdings_status"],
                "formal_holding_actions_currently_usable": bundle[
                    "formal_holding_actions_currently_usable"
                ],
                "formal_action_recalculation": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
