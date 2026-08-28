"""Bridge existing industry-cycle evidence into the durable Evidence Event Store.

This module reuses the repository's audited industry/company cycle evidence instead
of inventing a second industry model. It maps current hourly-workset securities to
an industry only when a code-level company evidence row supplies that mapping.
Stale evidence remains visible as stale; it is never treated as fresh silence and
never creates or mutates Formal actions.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .evidence_event_store import append_events


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _direction(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"POSITIVE", "UP", "IMPROVING", "STRENGTHENING"}:
        return "STRENGTHENING"
    if text in {"NEGATIVE", "DOWN", "DETERIORATING", "WEAKENING"}:
        return "WEAKENING"
    if text == "NEUTRAL":
        return "NEUTRAL"
    return "UNKNOWN"


def _materiality(confidence: Any) -> str:
    # Source confidence is not the same as investment materiality. A single
    # industry datapoint is capped at MEDIUM until production re-underwrites it.
    return "MEDIUM" if str(confidence or "").strip().upper() == "HIGH" else "LOW"


def _company_industry_map(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    latest: dict[str, tuple[str, str]] = {}
    for row in rows:
        code = str(row.get("code") or "").strip().zfill(6)
        industry = str(row.get("industry") or "").strip()
        observed = str(row.get("date") or "")
        if not code or not industry:
            continue
        prior = latest.get(code)
        if prior is None or observed >= prior[0]:
            latest[code] = (observed, industry)
    return {code: item[1] for code, item in latest.items()}


def collect(
    overlay: Mapping[str, Any],
    industry_rows: list[Mapping[str, Any]],
    company_rows: list[Mapping[str, Any]],
    *,
    today: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    today = today or datetime.now(timezone.utc).date()
    workset = {str(row.get("code") or "").zfill(6): row for row in overlay.get("rows") or [] if isinstance(row, Mapping)}
    code_industry = _company_industry_map(company_rows)
    by_industry: dict[str, list[Mapping[str, Any]]] = {}
    for row in industry_rows:
        industry = str(row.get("industry") or "").strip()
        if industry:
            by_industry.setdefault(industry, []).append(row)

    events: list[dict[str, Any]] = []
    mapped_codes: dict[str, str] = {}
    latest_source_date: date | None = None
    for code, row in workset.items():
        industry = str(row.get("industry") or "").strip() or code_industry.get(code, "")
        if not industry:
            continue
        mapped_codes[code] = industry
        for evidence in by_industry.get(industry, []):
            raw_date = str(evidence.get("date") or "").strip()
            try:
                observed_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if observed_date > today:
                continue
            latest_source_date = observed_date if latest_source_date is None else max(latest_source_date, observed_date)
            value = str(evidence.get("evidence_value") or "").strip()
            note = str(evidence.get("note") or "").strip()
            evidence_name = str(evidence.get("evidence_name") or "industry evidence").strip()
            events.append({
                "code": code,
                "name": row.get("name") or "",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "published_at": observed_date.isoformat() + "T00:00:00+00:00",
                "source": "industry_cycle_evidence",
                "source_ref": str(evidence.get("source") or ""),
                "evidence_type": "INDUSTRY_SUPPLY_DEMAND",
                "title": f"{industry}: {evidence_name}",
                "summary": " ".join(part for part in (value, note) if part),
                "materiality": _materiality(evidence.get("confidence")),
                "direction": _direction(evidence.get("evidence_direction")),
                "thesis_link": f"industry:{industry}:{evidence_name}",
                "value_anchor_impact": "REVIEW_IF_PERSISTENT",
                "sell_relevance": "RESEARCH_ONLY",
                "confidence": str(evidence.get("confidence") or "UNKNOWN").upper(),
            })

    if latest_source_date is None:
        freshness = "NO_MATCHED_EVIDENCE"
        age_days = None
    else:
        age_days = (today - latest_source_date).days
        freshness = "FRESH" if age_days <= 7 else "CONNECTED_BUT_STALE"
    status = {
        "contract_version": "GEN_GE_INDUSTRY_CYCLE_EVIDENCE_BRIDGE_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "CONNECTED" if industry_rows else "SOURCE_FILE_EMPTY",
        "freshness_status": freshness,
        "latest_source_date": latest_source_date.isoformat() if latest_source_date else None,
        "latest_source_age_days": age_days,
        "workset_count": len(workset),
        "mapped_security_count": len(mapped_codes),
        "mapped_industries": sorted(set(mapped_codes.values())),
        "emitted_event_count": len(events),
        "unmapped_security_count": len(workset) - len(mapped_codes),
        "formal_action_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    return events, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly-overlay", type=Path, default=Path("data/hourly_deep_overlay/latest.json"))
    parser.add_argument("--industry-evidence", type=Path, default=Path("data/user_supplied/industry_cycle_evidence.csv"))
    parser.add_argument("--company-evidence", type=Path, default=Path("data/user_supplied/company_cycle_evidence.csv"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/industry_collector_status.json"))
    args = parser.parse_args(argv)
    events, status = collect(_load_json(args.hourly_overlay), _rows(args.industry_evidence), _rows(args.company_evidence))
    if events:
        append_events(args.evidence_root, events)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
