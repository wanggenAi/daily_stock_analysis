#!/usr/bin/env python3
"""Build and validate the canonical GenGe realtime data-package manifest.

This module is deliberately network-free. Collectors own acquisition; this module
owns the boundary between data production and research. Freshness is derived only
from business timestamps embedded in producer data -- never checkout mtimes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT = "GEN_GE_REALTIME_DATA_PACKAGE_V1"
PACKAGE_DIR = Path("data/data_package")
LATEST_PATH = PACKAGE_DIR / "latest.json"
SNAPSHOT_DIR = PACKAGE_DIR / "snapshots"
STATE_PATH = PACKAGE_DIR / "watermarks.json"
MAX_LINEAGE_FILES = 50

EXCLUDED_ROOTS = {
    "data/data_package",
    "data/research_input",
    "data/decision_center",
    "data/investor_chatgpt_handoff",
    "data/investor_decision_dashboard",
    "data/formal_decision_history",
    "data/formal_decision_outcomes",
    "data/deep_calculation",
    "data/deep_calculation_fast",
    "data/hourly_research_state",
}

PRODUCER_ROOTS: tuple[tuple[str, str, bool, int | None], ...] = (
    ("era_radar", "data/era_radar", True, 8 * 60),
    ("global_market_pulse", "data/global_market_pulse", True, 8 * 60),
    ("evidence_events", "data/evidence_events", False, 24 * 60),
    ("opportunity_snapshots", "data/opportunity_snapshots", False, 24 * 60),
    ("production_status", "data/production_status", False, 6 * 60),
    ("production_observability", "data/production_observability", False, 6 * 60),
    ("manual_execution_quotes", "data/manual_execution_quotes", False, 60),
    ("price_value_history", "data/price_value_history", False, 24 * 60),
    ("research_mapping", "data/research_mapping", False, 24 * 60),
    ("user_supplied", "data/user_supplied", False, None),
    ("live_execution_quotes", "data/live_execution_quotes", False, 30),
)

TIMESTAMP_KEYS = {
    "collected_at", "generated_at", "updated_at", "observed_at", "as_of",
    "snapshot_at", "research_as_of", "latest_quote_observed_at",
    "latest_observation_at", "refreshed_at", "ingested_at",
}
DATE_KEYS = {
    "latest_trade_date", "last_valid_trade_date", "trade_date", "market_date",
    "effective_date", "as_of_date",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _candidate_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.as_posix()
        if any(rel == x or rel.startswith(x + "/") for x in EXCLUDED_ROOTS):
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".csv", ".md", ".parquet"}:
            continue
        files.append(path)
    return sorted(files)


def _extract_times(path: Path) -> tuple[datetime | None, str | None]:
    """Extract business time only. Filesystem mtimes are intentionally ignored."""
    if path.suffix.lower() != ".json":
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    latest_dt: datetime | None = None
    latest_date: str | None = None

    def visit(obj: Any, depth: int = 0) -> None:
        nonlocal latest_dt, latest_date
        if depth > 5:
            return
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in TIMESTAMP_KEYS:
                    parsed = _parse_dt(value)
                    if parsed and (latest_dt is None or parsed > latest_dt):
                        latest_dt = parsed
                if key in DATE_KEYS and isinstance(value, str) and len(value) >= 10:
                    date = value[:10]
                    if latest_date is None or date > latest_date:
                        latest_date = date
                if isinstance(value, (dict, list)):
                    visit(value, depth + 1)
        elif isinstance(obj, list):
            for value in obj[:1000]:
                if isinstance(value, (dict, list)):
                    visit(value, depth + 1)

    visit(payload)
    return latest_dt, latest_date


@dataclass
class DatasetManifest:
    name: str
    root: str
    required: bool
    exists: bool
    file_count: int
    content_sha256: str | None
    latest_observed_at: str | None
    latest_trade_date: str | None
    freshness_sla_minutes: int | None
    freshness_state: str
    changed_since_previous: bool | None
    watermark: str | None
    lineage_file_sample: list[dict[str, Any]]
    lineage_file_sample_truncated: bool


def _dataset_manifest(
    name: str,
    root_text: str,
    required: bool,
    sla_minutes: int | None,
    *,
    now: datetime,
    previous: dict[str, Any] | None,
) -> DatasetManifest:
    root = Path(root_text)
    files = _candidate_files(root)
    lineage_rows: list[dict[str, Any]] = []
    latest_dt: datetime | None = None
    latest_trade_date: str | None = None
    aggregate = hashlib.sha256()
    for index, path in enumerate(files):
        sha = _sha256_file(path)
        observed_at, trade_date = _extract_times(path)
        rel = path.as_posix()
        aggregate.update(rel.encode())
        aggregate.update(sha.encode())
        if index < MAX_LINEAGE_FILES:
            lineage_rows.append({
                "path": rel,
                "sha256": sha,
                "size": path.stat().st_size,
                "observed_at": _iso(observed_at) if observed_at else None,
                "trade_date": trade_date,
            })
        if observed_at and (latest_dt is None or observed_at > latest_dt):
            latest_dt = observed_at
        if trade_date and (latest_trade_date is None or trade_date > latest_trade_date):
            latest_trade_date = trade_date
    exists = bool(files)
    digest = aggregate.hexdigest() if exists else None
    if not exists:
        freshness = "MISSING"
    elif sla_minutes is None:
        freshness = "NOT_APPLICABLE"
    elif latest_dt is None:
        freshness = "UNKNOWN"
    else:
        age_minutes = max(0.0, (now - latest_dt).total_seconds() / 60.0)
        freshness = "FRESH" if age_minutes <= sla_minutes else "STALE"
    previous_sha = previous.get("content_sha256") if previous else None
    changed = None if previous_sha is None else previous_sha != digest
    watermark = (
        hashlib.sha256(
            f"{digest or 'MISSING'}|{latest_trade_date or ''}|{_iso(latest_dt) if latest_dt else ''}".encode()
        ).hexdigest()[:24]
        if exists
        else None
    )
    return DatasetManifest(
        name=name,
        root=root_text,
        required=required,
        exists=exists,
        file_count=len(files),
        content_sha256=digest,
        latest_observed_at=_iso(latest_dt) if latest_dt else None,
        latest_trade_date=latest_trade_date,
        freshness_sla_minutes=sla_minutes,
        freshness_state=freshness,
        changed_since_previous=changed,
        watermark=watermark,
        lineage_file_sample=lineage_rows,
        lineage_file_sample_truncated=len(files) > MAX_LINEAGE_FILES,
    )


def _load_previous() -> dict[str, dict[str, Any]]:
    if not LATEST_PATH.is_file():
        return {}
    try:
        payload = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(x.get("name")): x
        for x in payload.get("datasets") or []
        if isinstance(x, dict)
    }


def build_package(*, now: datetime | None = None, write: bool = True) -> dict[str, Any]:
    now = now or _utc_now()
    previous = _load_previous()
    datasets = [
        _dataset_manifest(name, root, required, sla, now=now, previous=previous.get(name))
        for name, root, required, sla in PRODUCER_ROOTS
    ]
    missing_required = [d.name for d in datasets if d.required and not d.exists]
    stale_required = [d.name for d in datasets if d.required and d.freshness_state == "STALE"]
    unknown_required = [d.name for d in datasets if d.required and d.freshness_state == "UNKNOWN"]
    dates = sorted({d.latest_trade_date for d in datasets if d.latest_trade_date})
    latest_trade_date = dates[-1] if dates else None
    if missing_required or unknown_required:
        status = "INVALID"
    elif stale_required:
        status = "STALE"
    elif any(d.freshness_state in {"MISSING", "STALE", "UNKNOWN"} for d in datasets if not d.required):
        status = "PARTIAL"
    else:
        status = "READY"
    snapshot_basis = {
        "contract": CONTRACT,
        "latest_trade_date": latest_trade_date,
        "datasets": [
            {
                "name": d.name,
                "root": d.root,
                "content_sha256": d.content_sha256,
                "watermark": d.watermark,
            }
            for d in datasets
        ],
    }
    snapshot_id = hashlib.sha256(
        json.dumps(snapshot_basis, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    external_dir = PACKAGE_DIR / "external_fresh_evidence" / "events"
    pending_external = 0
    if external_dir.is_dir():
        for path in external_dir.glob("*.json"):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if event.get("tag") == "EXTERNAL_FRESH_EVIDENCE" and event.get("backfill_status") != "CANONICAL_INGESTED":
                pending_external += 1
    payload = {
        "contract": CONTRACT,
        "generated_at": _iso(now),
        "snapshot_id": snapshot_id,
        "package_status": status,
        "latest_trade_date": latest_trade_date,
        "incremental_update_contract": {
            "mode": "CONTENT_WATERMARK_INCREMENTAL",
            "full_history_redownload_required_for_research": False,
            "research_may_fetch_network_by_default": False,
            "collector_layer_owns_acquisition": True,
            "filesystem_mtime_may_establish_freshness": False,
        },
        "missing_required_datasets": missing_required,
        "stale_required_datasets": stale_required,
        "unknown_required_datasets": unknown_required,
        "pending_external_fresh_evidence_count": pending_external,
        "datasets": [asdict(d) for d in datasets],
    }
    if write:
        PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (SNAPSHOT_DIR / f"{snapshot_id}.json").write_text(text, encoding="utf-8")
        LATEST_PATH.write_text(text, encoding="utf-8")
        STATE_PATH.write_text(
            json.dumps(
                {
                    "contract": "GEN_GE_DATA_PACKAGE_WATERMARKS_V1",
                    "updated_at": _iso(now),
                    "snapshot_id": snapshot_id,
                    "watermarks": {d.name: d.watermark for d in datasets},
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    return payload


def validate_package(*, require_fresh: bool = False) -> tuple[bool, dict[str, Any]]:
    if not LATEST_PATH.is_file():
        return False, {"error": "DATA_PACKAGE_MISSING", "path": str(LATEST_PATH)}
    try:
        payload = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, {"error": "DATA_PACKAGE_INVALID_JSON", "detail": str(exc)}
    if payload.get("contract") != CONTRACT:
        return False, {"error": "DATA_PACKAGE_CONTRACT_MISMATCH", "contract": payload.get("contract")}
    snapshot_id = str(payload.get("snapshot_id") or "")
    if not snapshot_id or not (SNAPSHOT_DIR / f"{snapshot_id}.json").is_file():
        return False, {"error": "IMMUTABLE_SNAPSHOT_MISSING", "snapshot_id": snapshot_id}
    if require_fresh and payload.get("package_status") != "READY":
        return False, {
            "error": "DATA_PACKAGE_NOT_FRESH_READY",
            "package_status": payload.get("package_status"),
            "snapshot_id": snapshot_id,
        }
    return True, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--no-write", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--require-fresh", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        payload = build_package(write=not args.no_write)
        print(json.dumps({k: payload.get(k) for k in ("contract", "snapshot_id", "package_status", "latest_trade_date", "pending_external_fresh_evidence_count")}, ensure_ascii=False))
        return 0 if payload.get("package_status") != "INVALID" else 2
    ok, payload = validate_package(require_fresh=args.require_fresh)
    print(json.dumps(payload if not ok else {k: payload.get(k) for k in ("contract", "snapshot_id", "package_status", "latest_trade_date")}, ensure_ascii=False))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
