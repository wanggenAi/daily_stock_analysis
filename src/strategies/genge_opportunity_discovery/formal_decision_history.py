"""Persist immutable Formal Decision history from finalized canonical snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.genge_v311_persistence_order import (
    PersistenceOrder,
    canonical_run_id,
    canonical_snapshot_id,
    classify_persistence_order,
)

CONTRACT_VERSION = "GEN_GE_V3_1_1_FORMAL_DECISION_HISTORY_V1"


def _code(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())[-6:]
    return text.zfill(6) if text else ""


def _record_id(snapshot_id: str, scope: str, code: str) -> str:
    raw = f"{snapshot_id}|{scope}|{code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def records_from_snapshot(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    sid = canonical_snapshot_id(snapshot.get("snapshot_id"))
    source_run_id = str(canonical_run_id(snapshot.get("source_run_id")))
    production = snapshot.get("production") or {}
    records: list[dict[str, Any]] = []
    for scope, key in (("CANDIDATE", "candidate_decisions"), ("HOLDING", "holding_decisions")):
        for raw in production.get(key) or []:
            if not isinstance(raw, Mapping):
                continue
            code = _code(raw.get("code"))
            if not code:
                continue
            records.append(
                {
                    "contract_version": CONTRACT_VERSION,
                    "record_id": _record_id(sid, scope, code),
                    "canonical_snapshot_id": sid,
                    "canonical_source_run_id": source_run_id,
                    "research_as_of": snapshot.get("research_as_of"),
                    "latest_trade_date": snapshot.get("latest_trade_date"),
                    "scope": scope,
                    "code": code,
                    "name": raw.get("stock_name") or raw.get("name") or "",
                    "formal_action": raw.get("action") or raw.get("production_action") or raw.get("formal_action") or "",
                    "valuation_confidence": raw.get("valuation_confidence"),
                    "current_price": raw.get("current_price"),
                    "neutral_value": raw.get("neutral_value"),
                    "price_to_neutral": raw.get("price_to_neutral"),
                    "normalized_earnings": raw.get("normalized_earnings"),
                    "reason_codes": raw.get("reason_codes"),
                    "decision_date": raw.get("decision_date"),
                    "confirmed_quantity": raw.get("confirmed_quantity"),
                    "formal_action_source": "FINALIZED_CANONICAL_ONLY",
                    "no_auto_trade": True,
                }
            )
    return records


def _load_history(history_path: Path) -> list[dict[str, Any]]:
    existing: list[dict[str, Any]] = []
    if not history_path.is_file():
        return existing
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"formal decision history line {line_number} must be an object")
        existing.append(row)
    return existing


def _load_summary(summary_path: Path) -> dict[str, Any]:
    if not summary_path.is_file():
        return {}
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("formal decision latest summary must be an object")
    return data


def _durable_identity(
    summary: Mapping[str, Any], existing: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Resolve current latest identity, migrating the V1 summary without guessing."""
    if summary:
        sid = summary.get("canonical_snapshot_id")
        run_id = summary.get("canonical_source_run_id")
        if run_id not in (None, ""):
            return str(sid or ""), str(run_id)
        if sid in (None, ""):
            raise ValueError("formal decision latest summary has no Canonical snapshot identity")

        # Legacy V1 summaries did not store source_run_id. The immutable records
        # already do. Only a unique matching run id is a safe migration source.
        matching_runs = {
            str(row.get("canonical_source_run_id") or "")
            for row in existing
            if str(row.get("canonical_snapshot_id") or "") == str(sid)
        }
        matching_runs.discard("")
        if len(matching_runs) != 1:
            raise ValueError(
                "cannot uniquely recover latest Formal Decision source_run_id from immutable history"
            )
        recovered = next(iter(matching_runs))
        canonical_run_id(recovered, field="history.canonical_source_run_id")
        return str(sid), recovered

    if not existing:
        return None, None

    identities: dict[int, set[str]] = {}
    for row in existing:
        sid = canonical_snapshot_id(
            row.get("canonical_snapshot_id"), field="history.canonical_snapshot_id"
        )
        run_id = canonical_run_id(
            row.get("canonical_source_run_id"), field="history.canonical_source_run_id"
        )
        identities.setdefault(run_id, set()).add(sid)
    latest_run = max(identities)
    latest_sids = identities[latest_run]
    if len(latest_sids) != 1:
        raise ValueError("latest Formal Decision run maps to multiple Canonical snapshot ids")
    return next(iter(latest_sids)), str(latest_run)


def append_snapshot(snapshot_path: Path, history_path: Path, summary_path: Path) -> dict[str, Any]:
    """Append immutable records while keeping the durable latest pointer monotonic."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be an object")
    sid = canonical_snapshot_id(snapshot.get("snapshot_id"))
    run_id = str(canonical_run_id(snapshot.get("source_run_id")))
    incoming = records_from_snapshot(snapshot)
    existing = _load_history(history_path)
    summary = _load_summary(summary_path)
    current_sid, current_run = _durable_identity(summary, existing)
    order = classify_persistence_order(
        incoming_snapshot_id=sid,
        incoming_source_run_id=run_id,
        current_snapshot_id=current_sid,
        current_source_run_id=current_run,
    )

    ids = {str(row.get("record_id") or "") for row in existing}
    added = [row for row in incoming if row["record_id"] not in ids]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if added:
        with history_path.open("a", encoding="utf-8") as out:
            for row in added:
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    total = len(existing) + len(added)
    legacy_summary_needs_run_id = bool(summary) and summary.get("canonical_source_run_id") in (
        None,
        "",
    )
    pointer_advanced = order in {PersistenceOrder.INITIAL, PersistenceOrder.NEWER}
    summary_updated = (
        pointer_advanced
        or (
            order is PersistenceOrder.SAME
            and (bool(added) or not summary or legacy_summary_needs_run_id)
        )
        # A late authorized cycle may backfill immutable audit rows. The Formal
        # latest pointer must not move backward, but aggregate history counts must
        # still describe the durable file after the append.
        or (order is PersistenceOrder.STALE and bool(added))
    )

    if summary_updated:
        if order is PersistenceOrder.STALE:
            if current_sid is None or current_run is None:
                raise ValueError("stale Formal Decision backfill has no durable latest identity")
            latest_sid, latest_run = current_sid, current_run
        else:
            latest_sid, latest_run = sid, run_id
        latest_summary = {
            "contract_version": CONTRACT_VERSION,
            "canonical_snapshot_id": latest_sid,
            "canonical_source_run_id": latest_run,
            "added_record_count": len(added),
            "total_record_count": total,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_history_append_snapshot_id": sid,
            "last_history_append_source_run_id": run_id,
            "latest_pointer_advanced": pointer_advanced,
            "no_auto_trade": True,
        }
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(latest_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        latest_summary = dict(summary)

    return {
        "contract_version": CONTRACT_VERSION,
        "incoming_canonical_snapshot_id": sid,
        "incoming_canonical_source_run_id": run_id,
        "persistence_order": order.value,
        "added_record_count": len(added),
        "total_record_count": total,
        "latest_summary_updated": summary_updated,
        "latest_pointer_advanced": pointer_advanced,
        "latest_canonical_snapshot_id": latest_summary.get("canonical_snapshot_id"),
        "latest_canonical_source_run_id": latest_summary.get("canonical_source_run_id") or current_run,
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--history", type=Path, default=Path("data/formal_decision_history/history.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("data/formal_decision_history/latest_summary.json"))
    args = parser.parse_args(argv)
    result = append_snapshot(args.snapshot, args.history, args.summary)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
