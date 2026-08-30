"""Fail-closed ordering for durable state derived from finalized Canonical snapshots.

GitHub workflow_run delivery and job execution order are not a durability order.  Any
state that means "latest" must compare the authorized Canonical source run against
what is already durable before it is allowed to advance that pointer.

This module deliberately contains no investment logic.  It only classifies whether
an already-authorized Canonical snapshot is newer than, identical to, or older than
the durable snapshot identity.  Equal run ids with different snapshot ids are an
authority conflict and fail closed.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class PersistenceOrder(str, Enum):
    INITIAL = "INITIAL"
    NEWER = "NEWER"
    SAME = "SAME"
    STALE = "STALE"


class PersistenceIdentityError(ValueError):
    """Raised when durable or incoming Canonical provenance cannot be trusted."""


def canonical_run_id(value: Any, *, field: str = "source_run_id") -> int:
    """Return a positive GitHub Actions run id, rejecting lossy/coercive forms."""
    if isinstance(value, bool):
        raise PersistenceIdentityError(f"{field} must be a positive integer run id")
    if isinstance(value, int):
        run_id = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or not text.isdigit():
            raise PersistenceIdentityError(f"{field} must be a positive integer run id")
        run_id = int(text)
    else:
        raise PersistenceIdentityError(f"{field} must be a positive integer run id")
    if run_id <= 0:
        raise PersistenceIdentityError(f"{field} must be a positive integer run id")
    return run_id


def canonical_snapshot_id(value: Any, *, field: str = "snapshot_id") -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersistenceIdentityError(f"{field} must be a non-empty string")
    return value.strip()


def identity_from_mapping(
    data: Mapping[str, Any],
    *,
    snapshot_key: str,
    run_key: str,
    label: str,
) -> tuple[str, int]:
    if not isinstance(data, Mapping):
        raise PersistenceIdentityError(f"{label} must be an object")
    return (
        canonical_snapshot_id(data.get(snapshot_key), field=f"{label}.{snapshot_key}"),
        canonical_run_id(data.get(run_key), field=f"{label}.{run_key}"),
    )


def classify_persistence_order(
    *,
    incoming_snapshot_id: Any,
    incoming_source_run_id: Any,
    current_snapshot_id: Any | None = None,
    current_source_run_id: Any | None = None,
) -> PersistenceOrder:
    """Classify an incoming authorized Canonical identity against durable latest.

    Missing current identity is allowed only when *both* current fields are absent,
    which represents first persistence.  A partial current identity is corruption
    and fails closed.  Equal run ids must identify the exact same snapshot.
    """
    incoming_sid = canonical_snapshot_id(incoming_snapshot_id, field="incoming.snapshot_id")
    incoming_run = canonical_run_id(incoming_source_run_id, field="incoming.source_run_id")

    current_sid_missing = current_snapshot_id is None or current_snapshot_id == ""
    current_run_missing = current_source_run_id is None or current_source_run_id == ""
    if current_sid_missing and current_run_missing:
        return PersistenceOrder.INITIAL
    if current_sid_missing != current_run_missing:
        raise PersistenceIdentityError("durable latest Canonical identity is partial")

    current_sid = canonical_snapshot_id(current_snapshot_id, field="current.snapshot_id")
    current_run = canonical_run_id(current_source_run_id, field="current.source_run_id")

    if incoming_run < current_run:
        return PersistenceOrder.STALE
    if incoming_run > current_run:
        return PersistenceOrder.NEWER
    if incoming_sid != current_sid:
        raise PersistenceIdentityError(
            "same Canonical source run id maps to different snapshot ids: "
            f"current={current_sid!r}, incoming={incoming_sid!r}, run={incoming_run}"
        )
    return PersistenceOrder.SAME
