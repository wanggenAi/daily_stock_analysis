#!/usr/bin/env python3
"""Apply a persisted live quote snapshot to the investor dashboard.

This is a CONSUMER. It never fetches the network. It preserves Formal actions and
only updates display/execution references when lineage matches the frozen canonical
snapshot.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.strategies.genge_opportunity_discovery.investor_direct_execution_quote_overlay import (
    _code,
    _reset_to_frozen_prices,
    _zero_immediate_deployment,
)
from src.strategies.genge_opportunity_discovery.investor_live_execution_overlay import (
    apply_live_execution_overlay,
    render_live_markdown,
)

CONTRACT = "GEN_GE_LIVE_EXECUTION_QUOTE_CONSUMER_V1"
SNAPSHOT_CONTRACT = "GEN_GE_LIVE_EXECUTION_QUOTE_SNAPSHOT_V1"
SOURCE = "PERSISTED_LIVE_EXECUTION_QUOTE_SNAPSHOT"


def apply_snapshot(dashboard: dict[str, Any], snapshot: dict[str, Any], *, max_age_minutes: int = 15, now: datetime | None = None) -> dict[str, Any]:
    if snapshot.get("contract") != SNAPSHOT_CONTRACT:
        raise ValueError("unexpected live quote snapshot contract")
    if snapshot.get("formal_action_authority") != "NONE" or snapshot.get("formal_action_recomputed") is not False:
        raise ValueError("live quote snapshot attempted to claim Formal authority")
    expected = str(dashboard.get("canonical_snapshot_id") or "")
    observed = str(snapshot.get("canonical_snapshot_id") or "")
    if expected and observed and expected != observed:
        raise ValueError(f"live quote/canonical lineage mismatch: dashboard={expected} snapshot={observed}")

    baseline = _reset_to_frozen_prices(dashboard)
    before = {
        _code(row.get("code")): row.get("formal_action")
        for row in baseline.get("stock_portfolio", {}).get("rows") or []
    }
    quote_payload = {
        "canonical_snapshot_id": snapshot.get("canonical_snapshot_id"),
        "canonical_source_run_id": snapshot.get("canonical_source_run_id"),
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "rows": [
            {
                "code": row.get("code"),
                "latest_price": row.get("price"),
                "latest_price_status": row.get("status"),
                "latest_price_observed_at": row.get("observed_at"),
                "latest_price_provider": row.get("provider"),
            }
            for row in snapshot.get("rows") or []
        ],
    }
    payload = apply_live_execution_overlay(
        baseline,
        quote_payload,
        now=now or datetime.now(timezone.utc),
        max_age_minutes=max_age_minutes,
    )
    after = {
        _code(row.get("code")): row.get("formal_action")
        for row in payload.get("stock_portfolio", {}).get("rows") or []
    }
    if before != after:
        raise ValueError("persisted live quote snapshot mutated Formal actions")

    active = snapshot.get("market_session_active") is True
    if not active:
        _zero_immediate_deployment(payload, "MARKET_NOT_IN_CONTINUOUS_SESSION")
    overlay = payload.setdefault("live_execution_overlay", {})
    overlay.update(
        {
            "consumer_contract": CONTRACT,
            "source": SOURCE,
            "snapshot_contract": SNAPSHOT_CONTRACT,
            "quote_snapshot_generated_at": snapshot.get("generated_at"),
            "formal_action_recomputed": False,
            "formal_action_mutation_allowed": False,
            "quote_may_only_change_display_and_execution_reference": True,
            "missing_quote_blocks_immediate_execution": True,
            "no_auto_trade": True,
        }
    )
    payload["live_execution_overlay"] = overlay
    payload["no_auto_trade"] = True
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, default=Path("data/investor_decision_dashboard/latest.json"))
    parser.add_argument("--quotes", type=Path, default=Path("data/live_execution_quotes/latest.json"))
    parser.add_argument("--markdown", type=Path, default=Path("INVESTOR_DECISION_DASHBOARD.md"))
    parser.add_argument("--max-age-minutes", type=int, default=15)
    args = parser.parse_args(argv)
    try:
        dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
        snapshot = json.loads(args.quotes.read_text(encoding="utf-8"))
        payload = apply_snapshot(dashboard, snapshot, max_age_minutes=args.max_age_minutes)
        args.dashboard.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.markdown.write_text(render_live_markdown(payload), encoding="utf-8")
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    overlay = payload.get("live_execution_overlay") or {}
    print(json.dumps({"contract": CONTRACT, "source": overlay.get("source"), "coverage": f"{overlay.get('applied_code_count',0)}/{overlay.get('expected_code_count',0)}", "formal_action_recomputed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
