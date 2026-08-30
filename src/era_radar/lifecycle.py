"""Lifecycle state machine for generic era/industry trends.

The state machine is industry-agnostic. It never embeds sector names or conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass

VALID_STATES = {
    "EMERGING",
    "ACCELERATING",
    "CONFIRMED",
    "MATURE",
    "CROWDED",
    "WEAKENING",
    "FALSIFIED",
}


@dataclass(frozen=True)
class LifecycleRecord:
    trend_id: str
    state: str
    latest_snapshot_id: str
    latest_observed_at: str
    seen_count: int = 1


@dataclass(frozen=True)
class LifecycleTransition:
    record: LifecycleRecord
    event: str
    changed: bool


def apply_lifecycle(
    current: LifecycleRecord | None,
    *,
    trend_id: str,
    snapshot_id: str,
    observed_at: str,
    proposed_state: str,
    allow_reactivation: bool = False,
) -> LifecycleTransition:
    if proposed_state not in VALID_STATES:
        raise ValueError(f"invalid state: {proposed_state}")

    if current is None:
        return LifecycleTransition(
            LifecycleRecord(trend_id, proposed_state, snapshot_id, observed_at, 1),
            "NEW",
            True,
        )

    if current.trend_id != trend_id:
        raise ValueError("trend_id mismatch")
    if snapshot_id == current.latest_snapshot_id:
        return LifecycleTransition(current, "NOOP", False)
    if observed_at < current.latest_observed_at:
        raise ValueError("out-of-order trend snapshot")

    if current.state == "FALSIFIED" and proposed_state != "FALSIFIED" and not allow_reactivation:
        return LifecycleTransition(current, "REACTIVATION_REVIEW_REQUIRED", False)

    if proposed_state == current.state:
        event = "RESEEN"
    elif proposed_state == "FALSIFIED":
        event = "FALSIFIED"
    elif proposed_state in {"ACCELERATING", "CONFIRMED"}:
        event = "STRENGTHENED"
    elif proposed_state in {"WEAKENING"}:
        event = "WEAKENED"
    elif proposed_state == "CROWDED":
        event = "CROWDING_INCREASED"
    else:
        event = "HORIZON_CHANGED"

    return LifecycleTransition(
        LifecycleRecord(
            trend_id=trend_id,
            state=proposed_state,
            latest_snapshot_id=snapshot_id,
            latest_observed_at=observed_at,
            seen_count=current.seen_count + 1,
        ),
        event,
        True,
    )
