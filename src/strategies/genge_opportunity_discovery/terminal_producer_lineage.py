"""Exact-lineage resolution primitives for Candidate Terminal producers.

A successful workflow wrapper is not a producer. A producer exists only when the
terminal job completed successfully and a self-consistent, consumable artifact
is present. Fallback is allowed only through explicit predecessor pointers
inside the same immutable lineage key.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class TerminalProducerNode:
    run_id: str
    lineage_key: str
    predecessor_run_id: str | None = None
    wrapper_status: str = "completed"
    wrapper_conclusion: str = "success"
    terminal_status: str = "completed"
    terminal_conclusion: str = "success"
    artifact_count: int = 1
    artifact_valid: bool = True
    artifact_lineage_key: str = ""
    artifact_candidate_identity: str = ""
    rejection_reason: str = ""


@dataclass(frozen=True)
class Resolution:
    status: str
    requested_run_id: str
    selected_run_id: str | None
    lineage_key: str
    visited_run_ids: tuple[str, ...]
    log: tuple[str, ...] = field(default_factory=tuple)


class LineageResolutionError(RuntimeError):
    """Fail-closed lineage corruption or bounded-traversal error."""


def _producer_rejection(node: TerminalProducerNode, expected_lineage: str) -> str | None:
    if node.wrapper_status != "completed" or node.wrapper_conclusion != "success":
        return f"wrapper={node.wrapper_status}/{node.wrapper_conclusion}"
    if node.terminal_status != "completed" or node.terminal_conclusion != "success":
        return f"terminal={node.terminal_status}/{node.terminal_conclusion}"
    if node.artifact_count != 1:
        return f"artifact_count={node.artifact_count}"
    if not node.artifact_valid:
        return node.rejection_reason or "artifact_invalid"
    if node.artifact_lineage_key != expected_lineage:
        return (
            "artifact_lineage_mismatch:"
            f"expected={expected_lineage}:actual={node.artifact_lineage_key or 'EMPTY'}"
        )
    if not node.artifact_candidate_identity:
        return "artifact_candidate_identity_missing"
    return None


def resolve_terminal_producer(
    requested_run_id: str,
    load_node: Callable[[str], TerminalProducerNode],
    *,
    max_hops: int = 12,
) -> Resolution:
    """Resolve the nearest consumable producer on one explicit exact lineage.

    The starting node establishes the immutable lineage key. Traversal follows
    only ``predecessor_run_id``. There is deliberately no chronological or
    "latest successful run" fallback.
    """
    if max_hops < 1:
        raise ValueError("max_hops must be >= 1")

    requested = str(requested_run_id).strip()
    if not requested.isdigit():
        raise ValueError(f"invalid requested run id: {requested_run_id!r}")

    visited: list[str] = []
    seen: set[str] = set()
    logs: list[str] = []
    current = requested
    expected_lineage = ""

    for hop in range(1, max_hops + 1):
        if current in seen:
            logs.append(f"hop={hop} run={current} rejected=cycle")
            raise LineageResolutionError(
                f"exact terminal lineage cycle detected at run {current}; visited={visited}"
            )
        seen.add(current)
        visited.append(current)

        node = load_node(current)
        if str(node.run_id) != current:
            raise LineageResolutionError(
                f"loader identity mismatch: requested {current}, returned {node.run_id}"
            )
        if not node.lineage_key:
            logs.append(f"hop={hop} run={current} rejected=lineage_key_missing")
            raise LineageResolutionError(
                f"run {current} has no auditable lineage key; stale/global fallback forbidden"
            )

        if not expected_lineage:
            expected_lineage = node.lineage_key
            logs.append(f"lineage={expected_lineage} requested={requested}")
        elif node.lineage_key != expected_lineage:
            logs.append(
                f"hop={hop} run={current} rejected=node_lineage_mismatch actual={node.lineage_key}"
            )
            raise LineageResolutionError(
                f"predecessor run {current} crossed lineage: "
                f"expected {expected_lineage}, got {node.lineage_key}"
            )

        rejection = _producer_rejection(node, expected_lineage)
        if rejection is None:
            logs.append(
                f"hop={hop} run={current} selected=valid_terminal_producer "
                f"candidate_identity={node.artifact_candidate_identity}"
            )
            return Resolution(
                status="SELECTED",
                requested_run_id=requested,
                selected_run_id=current,
                lineage_key=expected_lineage,
                visited_run_ids=tuple(visited),
                log=tuple(logs),
            )

        logs.append(f"hop={hop} run={current} rejected={rejection}")
        predecessor = str(node.predecessor_run_id or "").strip()
        if not predecessor:
            logs.append("lineage_exhausted=no_valid_terminal_producer")
            return Resolution(
                status="NOT_FOUND",
                requested_run_id=requested,
                selected_run_id=None,
                lineage_key=expected_lineage,
                visited_run_ids=tuple(visited),
                log=tuple(logs),
            )
        if not predecessor.isdigit():
            raise LineageResolutionError(
                f"run {current} has invalid predecessor id {predecessor!r}"
            )
        logs.append(f"fallback={current}->{predecessor}")
        current = predecessor

    logs.append(f"max_hops_exceeded={max_hops}")
    raise LineageResolutionError(
        f"exact terminal lineage exceeded max_hops={max_hops}; visited={visited}"
    )
