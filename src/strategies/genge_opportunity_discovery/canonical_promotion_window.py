"""Session gate for promoting research output into formal canonical truth.

Research may legitimately use the previous completed close before or during an
A-share session. That does *not* mean a producer carrying the previous close may
overwrite the formal canonical during the still-open trading day. This module
keeps those two concepts separate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .generation_freshness import (
    OFFICIAL_CALENDAR_SOURCE,
    OFFICIAL_CALENDAR_URL,
    SESSION_SETTLED_AFTER,
    SHANGHAI,
    _calendar_mode,
    _is_completed_session_day,
)

PROMOTION_CONTRACT_VERSION = "GEN_GE_CANONICAL_PROMOTION_WINDOW_V1"


def _parse_now(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("promotion evaluated_at is invalid") from exc
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_canonical_promotion_window(
    *, evaluated_at: str | datetime | None = None
) -> dict[str, Any]:
    """Return whether a new formal canonical may be promoted at this instant.

    On an actual A-share trading day, promotion is closed until the 16:00
    Asia/Shanghai settlement boundary. On weekends and official 2026 exchange
    closures this gate remains open because there is no same-day session waiting
    to settle; ordinary generation freshness still decides whether the candidate
    trade date itself is current enough.
    """
    now = _parse_now(evaluated_at)
    local = now.astimezone(SHANGHAI)
    session_day = _is_completed_session_day(local.date())
    pending_session = session_day and local.time() < SESSION_SETTLED_AFTER
    calendar_mode = _calendar_mode(local.date())
    reasons = ["CURRENT_ASHARE_SESSION_NOT_SETTLED"] if pending_session else []
    return {
        "contract_version": PROMOTION_CONTRACT_VERSION,
        "status": "BLOCKED_PENDING_SESSION" if pending_session else "OPEN",
        "canonical_promotion_allowed": not pending_session,
        "reasons": reasons,
        "evaluated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "shanghai_date": local.date().isoformat(),
        "shanghai_time": local.time().replace(microsecond=0).isoformat(),
        "session_day": session_day,
        "settlement_after": SESSION_SETTLED_AFTER.isoformat(),
        "holiday_calendar_mode": calendar_mode,
        "holiday_calendar_source": (
            OFFICIAL_CALENDAR_SOURCE if calendar_mode == "OFFICIAL_SSE_2026" else None
        ),
        "holiday_calendar_url": (
            OFFICIAL_CALENDAR_URL if calendar_mode == "OFFICIAL_SSE_2026" else None
        ),
    }


def assert_canonical_promotion_window_open(
    *, evaluated_at: str | datetime | None = None
) -> dict[str, Any]:
    result = evaluate_canonical_promotion_window(evaluated_at=evaluated_at)
    if result["canonical_promotion_allowed"] is not True:
        raise ValueError(
            "PRE_SETTLEMENT_CANONICAL_PROMOTION_REFUSED: "
            "current A-share session is not settled; research output may not "
            "overwrite formal canonical truth"
        )
    return result
