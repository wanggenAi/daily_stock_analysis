"""Apply user-confirmed broker intraday quotes to the investor dashboard.

This is an execution/display overlay only.  It never grants or recomputes Formal,
Canonical, Terminal, or trading authority.  A broker quote snapshot is accepted
only when it is explicitly user-confirmed, fail-closed on authority fields, bound
to the exact Canonical lineage, and fresh enough for execution-reference use.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.strategies.genge_opportunity_discovery.investor_live_execution_overlay import (
    DEFAULT_MAX_QUOTE_AGE_MINUTES,
    apply_live_execution_overlay,
    render_live_markdown,
)

MANUAL_QUOTE_CONTRACT = "GEN_GE_USER_CONFIRMED_BROKER_INTRADAY_QUOTES_V1"
MANUAL_EVIDENCE_AUTHORITY = "USER_CONFIRMED_BROKER_SCREENSHOT"
MANUAL_PRICE_SOURCE = "USER_CONFIRMED_BROKER_INTRADAY_QUOTE"


def _validate_authority(manual: Mapping[str, Any]) -> None:
    if manual.get("contract") != MANUAL_QUOTE_CONTRACT:
        raise ValueError("unexpected manual broker quote contract")
    if manual.get("evidence_authority") != MANUAL_EVIDENCE_AUTHORITY:
        raise ValueError("manual broker quotes lack explicit user-confirmed evidence authority")
    if manual.get("formal_trading_authority") is not False:
        raise ValueError("manual broker quotes may not gain Formal trading authority")
    if manual.get("automatic_formal_buy_allowed") is not False:
        raise ValueError("manual broker quotes may not authorize Formal BUY")
    if manual.get("no_auto_trade") is not True:
        raise ValueError("manual broker quotes lost no-auto-trade contract")


def _lineage_matches(dashboard: Mapping[str, Any], manual: Mapping[str, Any]) -> bool:
    expected_snapshot = str(dashboard.get("canonical_snapshot_id") or "").strip()
    expected_source = str(dashboard.get("canonical_source_run_id") or "").strip()
    actual_snapshot = str(manual.get("canonical_snapshot_id") or "").strip()
    actual_source = str(manual.get("canonical_source_run_id") or "").strip()
    return bool(
        expected_snapshot
        and expected_source
        and actual_snapshot == expected_snapshot
        and actual_source == expected_source
    )


def _as_hourly_payload(manual: Mapping[str, Any]) -> dict[str, Any]:
    default_observed_at = str(manual.get("observed_at") or "")
    broker = str(manual.get("broker") or "USER_CONFIRMED_BROKER").strip()
    rows: list[dict[str, Any]] = []
    for raw in manual.get("quotes") or []:
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            {
                "code": raw.get("code"),
                "latest_price": raw.get("latest_price"),
                "latest_price_status": raw.get("status") or "UNKNOWN",
                "latest_price_observed_at": raw.get("observed_at") or default_observed_at,
                "latest_price_provider": broker,
            }
        )
    return {
        "canonical_snapshot_id": manual.get("canonical_snapshot_id"),
        "canonical_source_run_id": manual.get("canonical_source_run_id"),
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "rows": rows,
    }


def apply_manual_broker_quote_overlay(
    dashboard: Mapping[str, Any],
    manual: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
) -> dict[str, Any]:
    """Overlay fresh user-confirmed broker quotes without changing authority.

    Stale or superseded Canonical lineage is a safe no-op so an old screenshot
    can remain as audit evidence without breaking future production refreshes.
    Authority-contract violations remain hard failures.
    """
    _validate_authority(manual)
    if not _lineage_matches(dashboard, manual):
        return copy.deepcopy(dict(dashboard))

    before = copy.deepcopy(dict(dashboard))
    payload = apply_live_execution_overlay(
        dashboard,
        _as_hourly_payload(manual),
        now=now or datetime.now(timezone.utc),
        max_age_minutes=max_age_minutes,
    )
    overlay = payload.get("live_execution_overlay") or {}
    if int(overlay.get("applied_code_count") or 0) <= 0:
        # Do not erase a previously valid hourly overlay with a stale manual one.
        return before

    applied_codes = set(overlay.get("applied_codes") or [])
    for row in payload.get("stock_portfolio", {}).get("rows") or []:
        code = str(row.get("code") or "").strip().zfill(6)
        if code in applied_codes:
            row["price_source"] = MANUAL_PRICE_SOURCE
    terminal = payload.get("terminal_opportunities") or {}
    for bucket in ("buy_now", "wait_price"):
        for row in terminal.get(bucket) or []:
            code = str(row.get("code") or "").strip().zfill(6)
            if code in applied_codes:
                row["price_source"] = MANUAL_PRICE_SOURCE

    overlay.update(
        {
            "source": MANUAL_PRICE_SOURCE,
            "manual_quote_contract": MANUAL_QUOTE_CONTRACT,
            "evidence_authority": MANUAL_EVIDENCE_AUTHORITY,
            "broker": manual.get("broker") or "",
            "formal_trading_authority": False,
            "automatic_formal_buy_allowed": False,
            "quote_may_only_change_display_and_execution_reference": True,
            "no_auto_trade": True,
        }
    )
    payload["live_execution_overlay"] = overlay
    return payload


def write_overlay(
    *,
    dashboard_json: Path,
    manual_quotes_json: Path,
    markdown_output: Path,
    max_age_minutes: int = DEFAULT_MAX_QUOTE_AGE_MINUTES,
) -> dict[str, Any]:
    dashboard = json.loads(dashboard_json.read_text(encoding="utf-8"))
    manual = json.loads(manual_quotes_json.read_text(encoding="utf-8"))
    payload = apply_manual_broker_quote_overlay(
        dashboard, manual, max_age_minutes=max_age_minutes
    )
    dashboard_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown_output.write_text(render_live_markdown(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--manual-quotes-json", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument(
        "--max-age-minutes", type=int, default=DEFAULT_MAX_QUOTE_AGE_MINUTES
    )
    args = parser.parse_args(argv)
    payload = write_overlay(
        dashboard_json=args.dashboard_json,
        manual_quotes_json=args.manual_quotes_json,
        markdown_output=args.markdown_output,
        max_age_minutes=args.max_age_minutes,
    )
    overlay = payload.get("live_execution_overlay") or {}
    print(
        "investor_manual_execution_quote_overlay=OK;"
        f"applied={overlay.get('applied_code_count', 0)};"
        "formal_action_recomputed=false;no_auto_trade=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
