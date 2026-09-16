"""Read-time generation freshness contract for GenGe production consumers.

Freshness is an execution-safety overlay only.  It never changes a frozen V3.1
valuation, Formal action, rank, or position limit.  When a production consumer
is looking at an older generation than the latest completed mainland-China
weekday session, the consumer must fail closed for *new exposure* while keeping
the underlying Canonical decision visible for audit/research.

The weekday rule intentionally errs on the safe side around exchange holidays:
without an authoritative exchange calendar, an apparent holiday-session gap is
reported as stale rather than silently authorizing new risk.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
SESSION_SETTLED_AFTER = time(16, 0)
CONTRACT_VERSION = "GEN_GE_GENERATION_FRESHNESS_V1"


def _datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def expected_latest_trade_date(evaluated_at: datetime) -> date:
    """Return the minimum weekday trade date expected by this read time.

    Before the local settlement cut-off, yesterday's completed weekday session
    is sufficient.  After the cut-off, today's weekday session is expected.
    Weekends resolve to Friday.  Exchange holidays are deliberately fail-closed.
    """
    local = evaluated_at.astimezone(SHANGHAI)
    if local.weekday() < 5 and local.time() >= SESSION_SETTLED_AFTER:
        return local.date()
    candidate = local.date() - timedelta(days=1) if local.weekday() < 5 else local.date()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def evaluate_generation_freshness(
    canonical: Mapping[str, Any],
    *,
    market_regime: Mapping[str, Any] | None = None,
    evaluated_at: str | datetime | None = None,
    strict_missing_metadata: bool = False,
) -> dict[str, Any]:
    """Evaluate whether this generation may authorize new exposure.

    Synthetic/legacy fixtures without ``generated_at`` remain observable when
    ``strict_missing_metadata`` is false, but are labelled UNVERIFIABLE.  Real
    production authority calls use strict mode.
    """
    if isinstance(evaluated_at, datetime):
        now = evaluated_at
    else:
        now = _datetime(evaluated_at) if evaluated_at else datetime.now(timezone.utc)
    if now is None:
        raise ValueError("freshness evaluated_at is invalid")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    canonical_generated_at = _datetime(canonical.get("generated_at"))
    trade_date = _date(canonical.get("latest_trade_date"))
    source_run_id = str(canonical.get("source_run_id") or "").strip()
    expected = expected_latest_trade_date(now)
    reasons: list[str] = []

    metadata_complete = canonical_generated_at is not None and trade_date is not None and bool(source_run_id)
    if not metadata_complete:
        if canonical_generated_at is None:
            reasons.append("CANONICAL_GENERATED_AT_MISSING")
        if trade_date is None:
            reasons.append("CANONICAL_TRADE_DATE_MISSING")
        if not source_run_id:
            reasons.append("CANONICAL_SOURCE_RUN_ID_MISSING")
        if not strict_missing_metadata:
            return {
                "contract_version": CONTRACT_VERSION,
                "status": "UNVERIFIABLE",
                "fresh": None,
                "formal_new_exposure_allowed": True,
                "fail_closed_applied": False,
                "reasons": reasons,
                "evaluated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
                "canonical_generated_at": str(canonical.get("generated_at") or ""),
                "canonical_latest_trade_date": str(canonical.get("latest_trade_date") or ""),
                "canonical_source_run_id": source_run_id,
                "expected_min_trade_date": expected.isoformat(),
                "market_as_of": "",
                "holiday_calendar_mode": "WEEKDAY_FAIL_CLOSED",
            }

    if trade_date is not None and trade_date < expected:
        reasons.append("CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION")
    if canonical_generated_at is not None and canonical_generated_at > now + timedelta(minutes=5):
        reasons.append("CANONICAL_GENERATED_AT_IN_FUTURE")

    market_as_of = ""
    if market_regime:
        market_as_of = str(
            market_regime.get("as_of_date")
            or market_regime.get("as_of")
            or market_regime.get("latest_trade_date")
            or ""
        ).strip()
        parsed_market = _date(market_as_of)
        if market_as_of and parsed_market is None:
            reasons.append("MARKET_CONTEXT_DATE_INVALID")
        elif parsed_market is not None and parsed_market < expected:
            reasons.append("MARKET_CONTEXT_BEHIND_COMPLETED_SESSION")

    stale = bool(reasons)
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "STALE_UPSTREAM" if stale else "OK",
        "fresh": not stale,
        "formal_new_exposure_allowed": not stale,
        "fail_closed_applied": stale,
        "reasons": reasons,
        "evaluated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "canonical_generated_at": str(canonical.get("generated_at") or ""),
        "canonical_latest_trade_date": str(canonical.get("latest_trade_date") or ""),
        "canonical_source_run_id": source_run_id,
        "expected_min_trade_date": expected.isoformat(),
        "market_as_of": market_as_of,
        "holiday_calendar_mode": "WEEKDAY_FAIL_CLOSED",
    }
