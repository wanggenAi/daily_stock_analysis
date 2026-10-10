#!/usr/bin/env python3
"""Produce a neutral persisted live-execution quote snapshot.

This is a DATA PRODUCER. It may access the quote network but it never mutates the
investor dashboard, Formal actions, research state, or Decision Center.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery.investor_direct_execution_quote_overlay import (
    BEIJING,
    Quote,
    execution_codes,
    fetch_quotes_with_retry,
    market_session_state,
)

CONTRACT = "GEN_GE_LIVE_EXECUTION_QUOTE_SNAPSHOT_V1"
DEFAULT_OUTPUT = Path("data/live_execution_quotes/latest.json")


def build_snapshot(
    dashboard: Mapping[str, Any],
    *,
    now: datetime | None = None,
    retry_attempts: int = 3,
    provider=None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    session = market_session_state(now)
    active = session.startswith("ACTIVE_")
    codes = execution_codes(dashboard)
    if active:
        kwargs = {"attempts": retry_attempts}
        if provider is not None:
            kwargs["provider"] = provider
        quotes: dict[str, Quote] = fetch_quotes_with_retry(codes, **kwargs)
    else:
        quotes = {}
    rows = []
    for code in codes:
        q = quotes.get(code)
        rows.append(
            {
                "code": code,
                "price": q.price if q else None,
                "status": q.status if q else "OFF_SESSION",
                "observed_at": q.observed_at if q else None,
                "provider": q.provider if q else None,
            }
        )
    ok_count = sum(row["status"] == "OK" and row["price"] is not None for row in rows)
    return {
        "contract": CONTRACT,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "generated_at_beijing": now.astimezone(BEIJING).isoformat(),
        "market_session_state": session,
        "market_session_active": active,
        "canonical_snapshot_id": dashboard.get("canonical_snapshot_id"),
        "canonical_source_run_id": dashboard.get("canonical_source_run_id"),
        "expected_codes": codes,
        "expected_code_count": len(codes),
        "ok_quote_count": ok_count,
        "rows": rows,
        "formal_action_authority": "NONE",
        "formal_action_recomputed": False,
        "automatic_execution_allowed": False,
        "producer_role": "DATA_ACQUISITION_ONLY",
    }


def write_snapshot(*, dashboard_path: Path, output_path: Path, retry_attempts: int = 3) -> dict[str, Any]:
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    payload = build_snapshot(dashboard, retry_attempts=retry_attempts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=Path("data/investor_decision_dashboard/latest.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retry-attempts", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        payload = write_snapshot(dashboard_path=args.dashboard, output_path=args.output, retry_attempts=args.retry_attempts)
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"contract": CONTRACT, "session": payload["market_session_state"], "coverage": f"{payload['ok_quote_count']}/{payload['expected_code_count']}", "formal_action_authority": payload["formal_action_authority"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
