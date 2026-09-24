"""Small file cache for opportunity evidence collectors."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


# Recover from transient official-source failures promptly without discarding
# the longer retention window for successfully verified evidence. A missing
# report can appear on the next disclosure day and must also be rechecked.
FAILED_EVIDENCE_CACHE_HOURS = 6
MISSING_EVIDENCE_CACHE_HOURS = 24


class EvidenceCache:
    """JSON cache keyed by deterministic collection task payloads."""

    def __init__(self, cache_dir: str | Path, ttl_days: int = 14) -> None:
        self.cache_dir = Path(cache_dir)
        self.ttl_days = max(0, int(ttl_days))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_hits = 0
        self.cache_misses = 0

    def key_for(self, payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            self.cache_misses += 1
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(str(payload.get("cached_at")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.cache_misses += 1
            return None
        audits = payload.get("audit_rows") or []
        statuses = (
            {
                str(row.get("status") or "").upper()
                for row in audits
                if isinstance(row, dict)
            }
            if isinstance(audits, list)
            else set()
        )
        ttl_hours = self.ttl_days * 24
        if "FAILED" in statuses:
            ttl_hours = min(ttl_hours, FAILED_EVIDENCE_CACHE_HOURS)
        elif "MISSING" in statuses:
            ttl_hours = min(ttl_hours, MISSING_EVIDENCE_CACHE_HOURS)
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours > ttl_hours:
            self.cache_misses += 1
            return None
        self.cache_hits += 1
        payload["cache_hit"] = True
        return payload

    def set(self, key: str, payload: Mapping[str, Any]) -> None:
        path = self.cache_dir / f"{key}.json"
        data = dict(payload)
        data["cached_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
