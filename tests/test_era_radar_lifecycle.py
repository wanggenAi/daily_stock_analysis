import pytest

from src.era_radar.lifecycle import LifecycleRecord, apply_lifecycle


def test_duplicate_snapshot_is_noop():
    current = LifecycleRecord("trend-a", "CONFIRMED", "s1", "2026-08-30T00:00:00Z", 4)
    result = apply_lifecycle(
        current,
        trend_id="trend-a",
        snapshot_id="s1",
        observed_at="2026-08-30T00:00:00Z",
        proposed_state="CONFIRMED",
    )
    assert result.event == "NOOP"
    assert result.changed is False
    assert result.record.seen_count == 4


def test_out_of_order_snapshot_fails_closed():
    current = LifecycleRecord("trend-a", "CONFIRMED", "s2", "2026-08-30T02:00:00Z", 2)
    with pytest.raises(ValueError, match="out-of-order"):
        apply_lifecycle(
            current,
            trend_id="trend-a",
            snapshot_id="s1",
            observed_at="2026-08-30T01:00:00Z",
            proposed_state="WEAKENING",
        )


def test_falsified_does_not_auto_reactivate():
    current = LifecycleRecord("trend-a", "FALSIFIED", "s2", "2026-08-30T02:00:00Z", 8)
    result = apply_lifecycle(
        current,
        trend_id="trend-a",
        snapshot_id="s3",
        observed_at="2026-08-30T03:00:00Z",
        proposed_state="ACCELERATING",
    )
    assert result.event == "REACTIVATION_REVIEW_REQUIRED"
    assert result.changed is False
    assert result.record == current


def test_reseen_increments_once_for_new_snapshot():
    current = LifecycleRecord("trend-a", "CONFIRMED", "s1", "2026-08-30T00:00:00Z", 2)
    result = apply_lifecycle(
        current,
        trend_id="trend-a",
        snapshot_id="s2",
        observed_at="2026-08-30T01:00:00Z",
        proposed_state="CONFIRMED",
    )
    assert result.event == "RESEEN"
    assert result.record.seen_count == 3
