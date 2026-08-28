"""Persist immutable Formal Decision history from finalized canonical snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_V3_1_1_FORMAL_DECISION_HISTORY_V1"


def _code(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())[-6:]
    return text.zfill(6) if text else ""


def _record_id(snapshot_id: str, scope: str, code: str) -> str:
    raw = f"{snapshot_id}|{scope}|{code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def records_from_snapshot(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    sid = str(snapshot.get("snapshot_id") or "")
    source_run_id = str(snapshot.get("source_run_id") or "")
    if not sid or not source_run_id:
        raise ValueError("canonical snapshot identity missing")
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


def append_snapshot(snapshot_path: Path, history_path: Path) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be an object")
    incoming = records_from_snapshot(snapshot)
    existing: list[dict[str, Any]] = []
    ids: set[str] = set()
    if history_path.is_file():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                existing.append(row)
                ids.add(str(row.get("record_id") or ""))
    added = [row for row in incoming if row["record_id"] not in ids]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if added:
        with history_path.open("a", encoding="utf-8") as out:
            for row in added:
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "contract_version": CONTRACT_VERSION,
        "canonical_snapshot_id": snapshot.get("snapshot_id"),
        "added_record_count": len(added),
        "total_record_count": len(existing) + len(added),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--history", type=Path, default=Path("data/formal_decision_history/history.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("data/formal_decision_history/latest_summary.json"))
    args = parser.parse_args(argv)
    summary = append_snapshot(args.snapshot, args.history)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
