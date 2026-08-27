"""Build one canonical GenGe V3.1.1 snapshot for hourly and daily consumers.

The snapshot is a synchronization contract, not a new ranking or trading model.
Broad discovery, deep review and production decisions remain separate layers, but
all are stamped with one snapshot id/source run so downstream consumers cannot
silently mix results from different runs. The durable candidate ledger is
intentionally not an input: it is downstream memory and must never cap discovery.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .selection_framework_v31 import execution_universe_status

SCHEMA_VERSION = "genge_v31_canonical_snapshot_v1"
PRODUCTION_VERSION = "GEN_GE_V3_1_1_PRODUCTION"


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _file_sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value: Any, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = float("-inf")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _eligible(row: Mapping[str, Any]) -> bool:
    explicit = str(row.get("v31_execution_universe_status") or "").strip()
    if explicit:
        return explicit == "EXECUTION_ELIGIBLE"
    return execution_universe_status(_code(row.get("code"))) == "EXECUTION_ELIGIBLE"


def _rank(row: Mapping[str, Any], fallback: int) -> int:
    for field in (
        "master_research_rank",
        "v31_review_rank",
        "valuation_research_rank",
        "quant_rank",
        "industry_research_rank",
    ):
        value = _int(row.get(field))
        if value < 10**9:
            return value
    return fallback


def _latest_trade_date(rows: Iterable[Mapping[str, Any]]) -> str:
    values: list[str] = []
    for row in rows:
        for field in ("latest_trade_date", "raw_latest_trade_date", "qfq_latest_trade_date", "trade_date"):
            value = str(row.get(field) or "").strip()
            if len(value) >= 10 and value[:10].count("-") == 2:
                values.append(value[:10])
    return max(values, default="")


def _compact_research(row: Mapping[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "code": _code(row.get("code")),
        "stock_name": row.get("stock_name") or row.get("name") or "",
        "industry": row.get("industry") or "",
        "quant_score": row.get("quant_score") or "",
        "quant_status": row.get("quant_status") or "",
        "candidate_class": row.get("v31_candidate_class") or "",
        "v31_score_total": row.get("v31_score_total") or "",
        "valuation_confidence": row.get("valuation_confidence") or "",
        "current_price": row.get("v31_current_price") or row.get("current_price") or row.get("raw_latest_close") or "",
        "latest_trade_date": row.get("latest_trade_date") or row.get("raw_latest_trade_date") or "",
        "hard_blockers": row.get("v31_blockers") or row.get("source_hard_blockers") or row.get("hard_blockers") or "",
        "source_channel": row.get("valuation_source_channel") or row.get("master_source") or "",
    }


def build_research_pool(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    eligible: list[tuple[int, int, Mapping[str, Any]]] = []
    for index, row in enumerate(rows, start=1):
        code = _code(row.get("code"))
        if not code or not _eligible(row):
            continue
        eligible.append((_rank(row, index), index, row))
    eligible.sort(
        key=lambda item: (
            item[0],
            -_float(item[2].get("quant_score")),
            _code(item[2].get("code")),
        )
    )
    compact = [_compact_research(row, rank) for rank, _, row in eligible[: max(0, limit)]]
    return compact, len(eligible)


def _compact_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": _code(row.get("code")),
        "stock_name": row.get("stock_name") or "",
        "scope": row.get("decision_scope") or "",
        "action": row.get("production_action") or "",
        "valuation_confidence": row.get("valuation_confidence") or "",
        "current_price": row.get("current_price") or row.get("source_current_price") or "",
        "neutral_value": row.get("neutral_value") or row.get("source_neutral_value") or "",
        "expectation_gap": row.get("expectation_gap") or row.get("source_expectation_gap") or "",
        "reason_codes": row.get("reason_codes") or "",
        "hard_gate_failures": row.get("hard_gate_failures") or "",
        "hard_gate_unknowns": row.get("hard_gate_unknowns") or "",
        "confirmed_quantity": row.get("confirmed_quantity") or "",
        "display_only_average_cost": row.get("display_only_average_cost") or "",
    }


def build_snapshot(
    discovery_rows: Iterable[Mapping[str, Any]],
    deep_review_rows: Iterable[Mapping[str, Any]],
    production_rows: Iterable[Mapping[str, Any]],
    *,
    source_kind: str,
    source_run_id: str,
    upstream_run_id: str = "",
    generated_at: str | None = None,
    research_as_of: str = "",
    discovery_limit: int = 100,
    deep_review_limit: int = 50,
    source_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    discovery_list = [dict(row) for row in discovery_rows]
    deep_list = [dict(row) for row in deep_review_rows]
    production_list = [dict(row) for row in production_rows]
    discovery_pool, discovery_count = build_research_pool(discovery_list, limit=discovery_limit)
    deep_pool, deep_count = build_research_pool(deep_list, limit=deep_review_limit)
    candidate_decisions = [
        _compact_decision(row)
        for row in production_list
        if str(row.get("decision_scope") or "") == "CANDIDATE"
    ]
    holding_decisions = [
        _compact_decision(row)
        for row in production_list
        if str(row.get("decision_scope") or "") == "HOLDING"
    ]
    latest_trade_date = _latest_trade_date(discovery_list + deep_list)
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    hashes = dict(source_hashes or {})
    identity = {
        "schema_version": SCHEMA_VERSION,
        "production_version": PRODUCTION_VERSION,
        "source_kind": source_kind,
        "source_run_id": str(source_run_id),
        "upstream_run_id": str(upstream_run_id or ""),
        "latest_trade_date": latest_trade_date,
        "source_hashes": hashes,
    }
    snapshot_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:20]
    all_decisions = candidate_decisions + holding_decisions
    snapshot = {
        **identity,
        "snapshot_id": snapshot_id,
        "generated_at": generated,
        "research_as_of": research_as_of or generated,
        "freshness_contract": {
            "latest_trade_date": latest_trade_date,
            "stale_or_unverified_price_may_promote_buy_add": False,
            "sections_must_share_snapshot_id": True,
        },
        "architecture_contract": {
            "discovery_is_upstream_of_ledger": True,
            "ledger_may_filter_discovery": False,
            "formal_buy_thresholds_changed": False,
            "candidate_ledger_is_downstream_memory_only": True,
        },
        "discovery": {
            "snapshot_id": snapshot_id,
            "execution_eligible_count": discovery_count,
            "published_count": len(discovery_pool),
            "rows": discovery_pool,
        },
        "deep_review": {
            "snapshot_id": snapshot_id,
            "execution_eligible_count": deep_count,
            "published_count": len(deep_pool),
            "rows": deep_pool,
        },
        "production": {
            "snapshot_id": snapshot_id,
            "candidate_count": len(candidate_decisions),
            "holding_count": len(holding_decisions),
            "candidate_decisions": candidate_decisions,
            "holding_decisions": holding_decisions,
            "action_counts": {
                action: sum(item["action"] == action for item in all_decisions)
                for action in sorted({item["action"] for item in all_decisions if item["action"]})
            },
        },
    }
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(
    snapshot: Mapping[str, Any],
    *,
    expected_source_run_id: str | None = None,
) -> None:
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("canonical snapshot schema mismatch")
    if snapshot.get("production_version") != PRODUCTION_VERSION:
        raise ValueError("canonical snapshot production version mismatch")
    snapshot_id = str(snapshot.get("snapshot_id") or "")
    if not snapshot_id:
        raise ValueError("canonical snapshot id missing")
    if expected_source_run_id is not None and str(snapshot.get("source_run_id") or "") != str(expected_source_run_id):
        raise ValueError("canonical snapshot source run mismatch")
    for section in ("discovery", "deep_review", "production"):
        payload = snapshot.get(section)
        if not isinstance(payload, Mapping) or payload.get("snapshot_id") != snapshot_id:
            raise ValueError(f"canonical snapshot section mismatch: {section}")
    architecture = snapshot.get("architecture_contract") or {}
    if architecture.get("ledger_may_filter_discovery") is not False:
        raise ValueError("ledger must not filter discovery")
    if architecture.get("formal_buy_thresholds_changed") is not False:
        raise ValueError("canonical synchronization must not change Formal BUY thresholds")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_snapshot(
    discovery_csv: Path,
    deep_review_csv: Path,
    production_csv: Path,
    output_dir: Path,
    *,
    source_kind: str,
    source_run_id: str,
    upstream_run_id: str = "",
    generated_at: str | None = None,
    research_as_of: str = "",
    discovery_limit: int = 100,
    deep_review_limit: int = 50,
) -> dict[str, Any]:
    hashes = {
        "discovery_csv": _file_sha256(discovery_csv),
        "deep_review_csv": _file_sha256(deep_review_csv),
        "production_csv": _file_sha256(production_csv),
    }
    snapshot = build_snapshot(
        _read_csv(discovery_csv),
        _read_csv(deep_review_csv),
        _read_csv(production_csv),
        source_kind=source_kind,
        source_run_id=source_run_id,
        upstream_run_id=upstream_run_id,
        generated_at=generated_at,
        research_as_of=research_as_of,
        discovery_limit=discovery_limit,
        deep_review_limit=deep_review_limit,
        source_hashes=hashes,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "latest.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(output_dir / "discovery_pool.csv", list(snapshot["discovery"]["rows"]))
    _write_csv(output_dir / "deep_review_pool.csv", list(snapshot["deep_review"]["rows"]))
    _write_csv(
        output_dir / "production_decisions.csv",
        list(snapshot["production"]["candidate_decisions"])
        + list(snapshot["production"]["holding_decisions"]),
    )
    lines = [
        "# GenGe V3.1.1 Canonical Snapshot",
        "",
        f"- snapshot_id: `{snapshot['snapshot_id']}`",
        f"- source: `{source_kind}` run `{source_run_id}`; upstream `{upstream_run_id}`",
        f"- latest_trade_date: `{snapshot['latest_trade_date']}`",
        f"- discovery execution-eligible: {snapshot['discovery']['execution_eligible_count']}",
        f"- deep-review execution-eligible: {snapshot['deep_review']['execution_eligible_count']}",
        f"- production candidates / holdings: {snapshot['production']['candidate_count']} / {snapshot['production']['holding_count']}",
        "- ledger is downstream memory only and never filters discovery",
        "- Formal BUY/SELL thresholds are unchanged",
    ]
    (output_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-csv", type=Path, required=True)
    parser.add_argument("--deep-review-csv", type=Path, required=True)
    parser.add_argument("--production-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-kind", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--upstream-run-id", default="")
    parser.add_argument("--generated-at")
    parser.add_argument("--research-as-of", default="")
    parser.add_argument("--discovery-limit", type=int, default=100)
    parser.add_argument("--deep-review-limit", type=int, default=50)
    args = parser.parse_args(argv)
    snapshot = write_snapshot(
        args.discovery_csv,
        args.deep_review_csv,
        args.production_csv,
        args.output_dir,
        source_kind=args.source_kind,
        source_run_id=args.source_run_id,
        upstream_run_id=args.upstream_run_id,
        generated_at=args.generated_at,
        research_as_of=args.research_as_of,
        discovery_limit=args.discovery_limit,
        deep_review_limit=args.deep_review_limit,
    )
    print(
        f"canonical_snapshot={args.output_dir};snapshot_id={snapshot['snapshot_id']};"
        f"discovery={snapshot['discovery']['execution_eligible_count']};"
        f"deep_review={snapshot['deep_review']['execution_eligible_count']};"
        f"production={snapshot['production']['candidate_count']};"
        f"holdings={snapshot['production']['holding_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
