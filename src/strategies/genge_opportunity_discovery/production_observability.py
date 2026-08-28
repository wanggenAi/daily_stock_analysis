"""Operational observability for the GenGe V3.1.1 production chain.

This module reports freshness, identity consistency, workflow-produced state,
durable-memory availability, and research mapping coverage. It does not calculate,
recommend, or mutate investment actions.
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


def _ratio(mapped: Any, total: Any) -> float | None:
    try:
        total_i = int(total)
        mapped_i = int(mapped)
    except (TypeError, ValueError):
        return None
    return None if total_i <= 0 else round(mapped_i / total_i, 4)


def build(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    production = _load(root / "data/production_status/latest.json")
    hourly = _load(root / "data/hourly_research_state/latest.json")
    price = _load(root / "data/hourly_deep_overlay/latest.json")
    evidence = _load(root / "data/evidence_events/index.json")
    source_registry = _load(root / "data/evidence_events/source_registry.json")
    collector = _load(root / "data/evidence_events/collector_status.json")
    transactions = _load(root / "data/transactions/holdings_projection.json")
    lifecycle = _load(root / "data/opportunity_snapshots/candidate_lifecycle_state.json")
    continuity = _load(root / "data/opportunity_snapshots/holding_valuation_continuity_state.json")
    mapping = _load(root / "data/research_mapping/coverage.json")

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
    tracked = mapping.get("tracked_security_count")

    return {
        "contract_version": "GEN_GE_V3_1_1_PRODUCTION_OBSERVABILITY_V3",
        "generated_at": now.isoformat(),
        "health": health,
        "failed_checks": failed,
        "checks": checks,
        "canonical_snapshot_ids_seen": sorted(snapshot_ids),
        "canonical_source_run_ids_seen": sorted(source_runs),
        "freshness": {
            "hourly_research_age_hours": _age_hours(hourly.get("generated_at"), now),
            "hourly_price_age_hours": _age_hours(price.get("generated_at"), now),
            "evidence_index_age_hours": _age_hours(evidence.get("generated_at"), now),
            "evidence_collector_age_hours": _age_hours(collector.get("generated_at") or collector.get("observed_at"), now),
            "mapping_coverage_age_hours": _age_hours(mapping.get("generated_at"), now),
            "source_registry_age_hours": _age_hours(source_registry.get("generated_at"), now),
        },
        "coverage": {
            "hourly_workset_count": hourly.get("workset_count"),
            "evidence_event_count": evidence.get("event_count"),
            "evidence_security_count": evidence.get("security_count"),
            "candidate_count": len(lifecycle.get("candidates") or {}),
            "transaction_holding_count": transactions.get("holding_count"),
            "evidence_source_implemented_count": source_registry.get("implemented_source_count"),
            "evidence_source_planned_count": source_registry.get("planned_source_count"),
        },
        "research_mapping": {
            "available": bool(mapping),
            "tracked_security_count": tracked,
            "industry_mapped_count": mapping.get("industry_mapped_count"),
            "industry_coverage_ratio": _ratio(mapping.get("industry_mapped_count"), tracked),
            "commodity_applicable_count": mapping.get("commodity_applicable_count"),
            "commodity_mapped_count": mapping.get("commodity_mapped_count"),
            "commodity_coverage_ratio": _ratio(mapping.get("commodity_mapped_count"), mapping.get("commodity_applicable_count")),
            "commodity_not_applicable_count": mapping.get("commodity_not_applicable_count"),
            "commodity_unresolved_count": mapping.get("commodity_unresolved_count"),
            "peer_applicable_count": mapping.get("peer_applicable_count"),
            "peer_mapped_count": mapping.get("peer_mapped_count"),
            "peer_coverage_ratio": _ratio(mapping.get("peer_mapped_count"), mapping.get("peer_applicable_count")),
            "peer_unresolved_count": mapping.get("peer_unresolved_count"),
            "industry_unmapped_codes": mapping.get("industry_unmapped_codes", []),
            "commodity_unmapped_codes": mapping.get("commodity_unmapped_codes", []),
            "peer_unmapped_codes": mapping.get("peer_unmapped_codes", []),
            "missing_mapping_is_not_inferred": True,
            "not_applicable_is_not_gap": True,
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
