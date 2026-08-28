"""Operational observability for the GenGe V3.1.1 production chain.

This module reports freshness, identity consistency, workflow-produced state,
and durable-memory availability. It does not calculate, recommend, or mutate
investment actions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _parse(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_hours(value: Any, now: datetime) -> float | None:
    dt = _parse(value)
    if dt is None:
        return None
    return round((now - dt).total_seconds() / 3600.0, 2)


def build(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    production = _load(root / "data/production_status/latest.json")
    hourly = _load(root / "data/hourly_research_state/latest.json")
    price = _load(root / "data/hourly_deep_overlay/latest.json")
    evidence = _load(root / "data/evidence_events/index.json")
    collector = _load(root / "data/evidence_events/collector_status.json")
    transactions = _load(root / "data/transactions/holdings_projection.json")
    lifecycle = _load(root / "data/opportunity_snapshots/candidate_lifecycle_state.json")
    continuity = _load(root / "data/opportunity_snapshots/holding_valuation_continuity_state.json")

    snapshot_ids = {
        str(x) for x in [
            production.get("canonical_snapshot_id"),
            hourly.get("canonical_snapshot_id"),
            price.get("canonical_snapshot_id"),
            lifecycle.get("latest_applied_snapshot_id"),
            continuity.get("latest_applied_snapshot_id"),
        ] if x
    }
    source_runs = {
        str(x) for x in [
            production.get("canonical_source_run_id"),
            hourly.get("canonical_source_run_id"),
            price.get("canonical_source_run_id"),
            lifecycle.get("last_persisted_source_run_id"),
            continuity.get("latest_applied_source_run_id"),
        ] if x
    }

    hourly_age = _age_hours(hourly.get("generated_at"), now)
    price_age = _age_hours(price.get("generated_at"), now)
    evidence_age = _age_hours(evidence.get("generated_at"), now)
    collector_age = _age_hours(collector.get("generated_at") or collector.get("observed_at"), now)

    checks = {
        "canonical_snapshot_identity_consistent": len(snapshot_ids) <= 1 and bool(snapshot_ids),
        "canonical_source_run_identity_consistent": len(source_runs) <= 1 and bool(source_runs),
        "production_status_available": bool(production),
        "hourly_research_available": bool(hourly),
        "hourly_price_overlay_available": bool(price),
        "evidence_index_available": bool(evidence),
        "candidate_lifecycle_available": bool(lifecycle),
        "holding_continuity_available": bool(continuity),
        "transaction_projection_available": bool(transactions),
    }
    failed = sorted(k for k, passed in checks.items() if not passed)
    health = "HEALTHY" if not failed else "DEGRADED"

    return {
        "contract_version": "GEN_GE_V3_1_1_PRODUCTION_OBSERVABILITY_V1",
        "generated_at": now.isoformat(),
        "health": health,
        "failed_checks": failed,
        "checks": checks,
        "canonical_snapshot_ids_seen": sorted(snapshot_ids),
        "canonical_source_run_ids_seen": sorted(source_runs),
        "freshness": {
            "hourly_research_age_hours": hourly_age,
            "hourly_price_age_hours": price_age,
            "evidence_index_age_hours": evidence_age,
            "evidence_collector_age_hours": collector_age,
        },
        "coverage": {
            "hourly_workset_count": hourly.get("workset_count"),
            "evidence_event_count": evidence.get("event_count"),
            "evidence_security_count": evidence.get("security_count"),
            "candidate_count": len(lifecycle.get("candidates") or {}),
            "transaction_holding_count": transactions.get("holding_count"),
        },
        "formal_action_recomputed": False,
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("data/production_observability/latest.json"))
    args = parser.parse_args(argv)
    payload = build(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
