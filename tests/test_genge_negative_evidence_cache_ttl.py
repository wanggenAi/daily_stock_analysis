"""Do not let cached official-source failures hide newly available evidence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.strategies.genge_opportunity_discovery.evidence_collectors.cache import EvidenceCache


def _age_cache_entry(cache: EvidenceCache, key: str, *, hours: float) -> None:
    path = cache.cache_dir / f"{key}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cached_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).isoformat()
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "status,age_hours,should_hit",
    [
        ("FAILED", 1, True),
        ("FAILED", 7, False),
        ("MISSING", 20, True),
        ("MISSING", 26, False),
        ("OK", 24 * 7, True),
        ("OK", 24 * 15, False),
    ],
)
def test_failed_and_missing_official_evidence_have_shorter_cache_lifetime(
    tmp_path, status: str, age_hours: int, should_hit: bool
) -> None:
    cache = EvidenceCache(tmp_path)
    key = cache.key_for(
        {
            "collector": "sse_company_announcement",
            "code": "688575",
            "announcement_type": "annual_report",
            "report_period": "2025",
        }
    )
    cache.set(key, {"evidence_rows": [], "audit_rows": [{"status": status}]})
    _age_cache_entry(cache, key, hours=age_hours)
    assert (cache.get(key) is not None) is should_hit


def test_failed_audit_invalidates_mixed_success_and_failure_cache(tmp_path) -> None:
    cache = EvidenceCache(tmp_path)
    cache.set(
        "mixed",
        {
            "evidence_rows": [{"verified": True}],
            "audit_rows": [{"status": "OK"}, {"status": "FAILED"}],
        },
    )
    _age_cache_entry(cache, "mixed", hours=7)
    assert cache.get("mixed") is None


def test_legacy_positive_payload_retains_original_ttl(tmp_path) -> None:
    cache = EvidenceCache(tmp_path)
    cache.set("legacy", {"evidence_rows": [{"verified": True}]})
    _age_cache_entry(cache, "legacy", hours=24 * 7)
    assert cache.get("legacy")["cache_hit"] is True


def test_explicitly_disabled_cache_remains_disabled(tmp_path) -> None:
    cache = EvidenceCache(tmp_path, ttl_days=0)
    cache.set("disabled", {"audit_rows": [{"status": "FAILED"}]})
    _age_cache_entry(cache, "disabled", hours=1)
    assert cache.get("disabled") is None
