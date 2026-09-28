"""Fail closed before replacing a newer investment report with an older market session.

A later GitHub workflow run is not necessarily a later exchange-market epoch.
This script is read-only; it does not promote any research conclusion to Formal.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping


def _market_date(payload: Mapping[str, Any], label: str) -> date:
    value = payload.get("latest_trade_date")
    if not isinstance(value, str):
        raise ValueError(f"{label}: latest_trade_date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: invalid latest_trade_date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label}: noncanonical latest_trade_date")
    return parsed


def assert_no_regressive_epoch(
    previous: Mapping[str, Any] | None, candidate: Mapping[str, Any]
) -> None:
    """Retain the latest previously published source session, not run order.

    A same-date rerender remains allowed; an earlier candidate session must
    never silently replace a newer published market epoch.
    """
    new_date = _market_date(candidate, "candidate")
    if previous is None:
        return
    old_date = _market_date(previous, "previous")
    if new_date < old_date:
        raise ValueError(
            f"regressive_market_epoch: candidate={new_date.isoformat()} "
            f"previous={old_date.isoformat()}; retain existing published report"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args(argv)
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous.is_file() and args.previous.stat().st_size else None
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    if previous is not None and not isinstance(previous, dict):
        raise ValueError("previous published dashboard is not a JSON object")
    if not isinstance(candidate, dict):
        raise ValueError("candidate dashboard is not a JSON object")
    assert_no_regressive_epoch(previous, candidate)
    print(f"Investor published market-epoch guard PASS: {candidate['latest_trade_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
