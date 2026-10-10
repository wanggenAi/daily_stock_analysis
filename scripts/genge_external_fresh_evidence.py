#!/usr/bin/env python3
"""Normalize urgent external evidence without granting investment authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUT_DIR = Path("data/data_package/external_fresh_evidence/events")
CONTRACT = "GEN_GE_EXTERNAL_FRESH_EVIDENCE_V1"
TAG = "EXTERNAL_FRESH_EVIDENCE"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest(payload: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    source_url = str(payload.get("source_url") or "").strip()
    observed_at = str(payload.get("observed_at") or "").strip()
    thesis = str(payload.get("thesis") or payload.get("relevance") or "").strip()
    if not source_url or not observed_at or not thesis:
        raise ValueError("source_url, observed_at and thesis/relevance are required")
    affected = sorted({str(x).zfill(6) for x in (payload.get("affected_codes") or []) if str(x).strip()})
    normalized = {
        "contract": CONTRACT,
        "tag": TAG,
        "ingested_at": _now(),
        "observed_at": observed_at,
        "source_url": source_url,
        "source_title": str(payload.get("source_title") or "").strip() or None,
        "affected_codes": affected,
        "thesis": thesis,
        "collected_by": str(payload.get("collected_by") or "GPT_OR_MANUAL_VERIFICATION"),
        "backfill_status": "PENDING_CANONICAL_INGEST",
        "formal_action_authority": "NONE",
        "automatic_execution_allowed": False,
        "notes": payload.get("notes"),
    }
    event_id = hashlib.sha256(json.dumps({"source_url": source_url, "observed_at": observed_at, "affected_codes": affected, "thesis": thesis}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    normalized["event_id"] = event_id
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{event_id}.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON file containing urgent external evidence")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        out = ingest(payload, write=not args.no_write)
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"event_id": out["event_id"], "tag": out["tag"], "backfill_status": out["backfill_status"], "formal_action_authority": out["formal_action_authority"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
