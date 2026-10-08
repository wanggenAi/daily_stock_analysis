"""Post-close watchdog for recovering a missing/stale formal canonical.

The research stack can have fresh intraday observations while the authoritative
formal canonical still points at an older completed session.  This module does
not authorize any trade and does not mutate canonical state.  It only decides
whether a completed mainland-China session is missing from the persisted
investor decision dashboard so automation may start an existing canonical
producer as a recovery action.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .generation_freshness import (
    SESSION_SETTLED_AFTER,
    SHANGHAI,
    _date,
    _is_completed_session_day,
    expected_latest_trade_date,
)

WATCHDOG_CONTRACT_VERSION = "GEN_GE_POSTCLOSE_RECOVERY_WATCHDOG_V1"


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
            raise ValueError("watchdog evaluated_at is invalid") from exc
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_postclose_recovery(
    dashboard: Mapping[str, Any],
    *,
    evaluated_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Return whether an existing full canonical producer should be recovered.

    Recovery is requested only after the local settlement boundary on an actual
    A-share session day and only when the persisted formal dashboard is behind
    the minimum completed trade date.  Holidays/weekends and pre-settlement
    periods never start a recovery run merely because the latest trade date is
    older than the wall-clock date.
    """
    now = _parse_now(evaluated_at)
    local = now.astimezone(SHANGHAI)
    expected = expected_latest_trade_date(now)
    canonical_trade_date = _date(dashboard.get("latest_trade_date"))
    completed_today = (
        _is_completed_session_day(local.date())
        and local.time() >= SESSION_SETTLED_AFTER
    )

    if not completed_today:
        reason = "NO_COMPLETED_SESSION_TODAY"
        needs_recovery = False
    elif canonical_trade_date is None:
        reason = "CANONICAL_TRADE_DATE_MISSING"
        needs_recovery = True
    elif canonical_trade_date < expected:
        reason = "CANONICAL_BEHIND_COMPLETED_SESSION"
        needs_recovery = True
    else:
        reason = "CANONICAL_CURRENT"
        needs_recovery = False

    return {
        "contract_version": WATCHDOG_CONTRACT_VERSION,
        "needs_recovery": needs_recovery,
        "reason": reason,
        "evaluated_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "shanghai_date": local.date().isoformat(),
        "shanghai_time": local.time().replace(microsecond=0).isoformat(),
        "session_day": _is_completed_session_day(local.date()),
        "settlement_after": SESSION_SETTLED_AFTER.isoformat(),
        "expected_trade_date": expected.isoformat(),
        "canonical_trade_date": canonical_trade_date.isoformat() if canonical_trade_date else "",
        "canonical_source_run_id": str(dashboard.get("canonical_source_run_id") or ""),
    }


def _write_github_output(path: str, result: Mapping[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"needs_recovery={'true' if result['needs_recovery'] else 'false'}\n")
        handle.write(f"reason={result['reason']}\n")
        handle.write(f"expected_trade_date={result['expected_trade_date']}\n")
        handle.write(f"canonical_trade_date={result['canonical_trade_date']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--evaluated-at", default="")
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    dashboard = json.loads(Path(args.dashboard).read_text(encoding="utf-8"))
    result = evaluate_postclose_recovery(
        dashboard,
        evaluated_at=args.evaluated_at or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    _write_github_output(args.github_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
