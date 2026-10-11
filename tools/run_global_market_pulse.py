#!/usr/bin/env python3
"""Collect and persist the global market pulse."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.era_radar.global_market_pulse import build_global_market_pulse, persist_if_changed  # noqa: E402


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _security_names(payload: dict) -> dict[str, str]:
    """Keep report names for holdings and current research candidates when available."""
    result: dict[str, str] = {}
    buckets = [
        (payload.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or [],
        (payload.get("pillar_3_deep_opportunities") or {}).get("research_buy") or [],
        (payload.get("pillar_3_deep_opportunities") or {}).get("research_wait_price") or [],
        (payload.get("pillar_3_deep_opportunities") or {}).get("research_gap") or [],
        (payload.get("candidate_lifecycle") or {}).get("active_candidates") or [],
    ]
    for rows in buckets:
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").zfill(6)
            if code.strip("0"):
                result[code] = str(row.get("name") or result.get(code) or "")
    return result


def _latest_completed_a_share_trade_date(now: datetime | None = None) -> str | None:
    """Return the latest completed XSHG session, independent of downstream decisions.

    The Global Pulse used to inherit ``decision_center.latest_trade_date``. That
    creates a circular stale clock: a stale formal decision can make a fresh
    upstream collector believe the last A-share close is stale as well. The
    exchange calendar is the authority for which session *should* be complete;
    market snapshots remain the authority for the actual A-share market facts.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    calendar = xcals.get_calendar("XSHG")
    shanghai_date = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    end = pd.Timestamp(shanghai_date.isoformat())
    start = end - pd.Timedelta(days=60)
    sessions = calendar.sessions_in_range(start, end)
    completed: list[pd.Timestamp] = []
    for session in sessions:
        close = calendar.session_close(session).to_pydatetime().astimezone(timezone.utc)
        if close <= now:
            completed.append(session)
    if not completed:
        return None
    return completed[-1].date().isoformat()


def _resolve_a_share_last_trade_date(decision_center: dict, now: datetime | None = None) -> str | None:
    """Resolve the A-share close anchor without allowing downstream state to lead it."""
    official = _latest_completed_a_share_trade_date(now=now)
    if official:
        return official
    # Fail-soft only when the exchange calendar itself is unavailable/out of range.
    # This preserves prior behavior without letting Decision Center override a
    # successfully resolved official calendar session.
    fallback = str(decision_center.get("latest_trade_date") or "").strip()
    return fallback[:10] if len(fallback) >= 10 else None


def _persist_validation_heartbeat(output_dir: Path, pulse: dict, persistence: dict) -> None:
    """Persist successful collection validation even when market semantics are unchanged."""
    coverage = pulse.get("coverage") or {}
    coverage_status = str(coverage.get("status") or "")
    if coverage_status == "UNAVAILABLE":
        return
    refreshed_at = str(pulse.get("generated_at") or "").strip()
    if not refreshed_at:
        return
    target = output_dir / "validation" / "latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": "GEN_GE_GLOBAL_MARKET_PULSE_VALIDATION_V1",
        "refreshed_at": refreshed_at,
        "validation_status": "SUCCESS" if coverage_status == "OK" else "PARTIAL",
        "coverage_status": coverage_status,
        "semantic_state": persistence.get("status"),
        "semantic_fingerprint": persistence.get("fingerprint"),
        "latest_observation_at": coverage.get("latest_observation_at"),
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/global_market_pulse"))
    parser.add_argument("--commodity-config", type=Path, default=Path("config/commodity_research_benchmarks.json"))
    parser.add_argument("--decision-center", type=Path, default=Path("data/decision_center/latest.json"))
    args = parser.parse_args()

    decision_center = _load_json(args.decision_center)
    pulse = build_global_market_pulse(
        commodity_config=_load_json(args.commodity_config),
        security_names=_security_names(decision_center),
        a_share_last_trade_date=_resolve_a_share_last_trade_date(decision_center),
    )
    persistence = persist_if_changed(pulse, args.output_dir)
    _persist_validation_heartbeat(args.output_dir, pulse, persistence)
    print(json.dumps({"pulse": pulse, "persistence": persistence}, ensure_ascii=False, sort_keys=True))
    # Partial coverage remains visible and useful. Complete source loss fails closed.
    return 2 if pulse["coverage"]["status"] == "UNAVAILABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
