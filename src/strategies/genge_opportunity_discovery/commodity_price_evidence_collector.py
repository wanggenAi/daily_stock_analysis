"""Collect public commodity benchmark prices for GenGe research observability.

The collector deliberately separates benchmark connectivity from company exposure.
It may emit security-level Evidence Events only when an explicit, evidence-backed
security_exposures mapping exists in config. Commodity moves never create or
mutate Formal actions and never rewrite canonical value anchors.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .evidence_event_store import append_events

PROVIDER = "stooq_public_daily"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def fetch_stooq_series(symbol: str, *, days: int = 14, timeout: int = 12) -> list[dict[str, Any]]:
    end = date.today()
    start = end - timedelta(days=max(7, days * 2))
    url = (
        "https://stooq.com/q/d/l/?s=" + symbol.lower()
        + f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GenGe-commodity-research"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    for raw in csv.DictReader(io.StringIO(text)):
        try:
            close = float(raw.get("Close") or "")
        except (TypeError, ValueError):
            continue
        day = str(raw.get("Date") or "").strip()
        if not day:
            continue
        rows.append({"date": day, "close": close})
    rows.sort(key=lambda r: r["date"])
    return rows[-days:]


def summarize_series(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) < 2:
        return {"status": "INSUFFICIENT_SERIES", "latest_date": None, "latest_close": None, "change_1d_pct": None, "change_5d_pct": None}
    latest = float(rows[-1]["close"])
    previous = float(rows[-2]["close"])
    change_1d = None if previous == 0 else (latest / previous - 1.0) * 100.0
    anchor = float(rows[max(0, len(rows) - 6)]["close"])
    change_5d = None if anchor == 0 else (latest / anchor - 1.0) * 100.0
    return {
        "status": "OK",
        "latest_date": str(rows[-1]["date"]),
        "latest_close": latest,
        "change_1d_pct": round(change_1d, 4) if change_1d is not None else None,
        "change_5d_pct": round(change_5d, 4) if change_5d is not None else None,
    }


def _direction(summary: Mapping[str, Any], exposure_direction: str) -> tuple[str, str]:
    move_1d = summary.get("change_1d_pct")
    move_5d = summary.get("change_5d_pct")
    try:
        strongest = float(move_5d if abs(float(move_5d or 0)) >= abs(float(move_1d or 0)) else move_1d)
    except (TypeError, ValueError):
        return "UNKNOWN", "LOW"
    if abs(strongest) < 3.0:
        return "NEUTRAL", "LOW"
    producer_positive = str(exposure_direction or "PRODUCER_POSITIVE").upper() == "PRODUCER_POSITIVE"
    favorable = strongest > 0 if producer_positive else strongest < 0
    return ("STRENGTHENING" if favorable else "WEAKENING", "MEDIUM")


def collect(
    overlay: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    series_fetcher: Callable[[str], list[dict[str, Any]]] = fetch_stooq_series,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workset = {str(row.get("code") or "").zfill(6): row for row in overlay.get("rows") or [] if isinstance(row, Mapping)}
    benchmarks = config.get("benchmarks") or {}
    exposures = config.get("security_exposures") or {}
    series_status: dict[str, Any] = {}
    now = datetime.now(timezone.utc).isoformat()

    for benchmark_id, spec in benchmarks.items():
        if not isinstance(spec, Mapping):
            continue
        symbol = str(spec.get("symbol") or "").strip()
        if not symbol:
            continue
        try:
            rows = series_fetcher(symbol)
            summary = summarize_series(rows)
            summary["symbol"] = symbol
            summary["label"] = spec.get("label") or benchmark_id
            summary["provider"] = PROVIDER
        except Exception as exc:
            summary = {
                "status": f"FETCH_ERROR:{type(exc).__name__}",
                "symbol": symbol,
                "label": spec.get("label") or benchmark_id,
                "provider": PROVIDER,
                "latest_date": None,
                "latest_close": None,
                "change_1d_pct": None,
                "change_5d_pct": None,
            }
        series_status[str(benchmark_id)] = summary

    events: list[dict[str, Any]] = []
    mapped = 0
    for code, exposure_list in exposures.items():
        normalized = str(code).zfill(6)
        if normalized not in workset or not isinstance(exposure_list, list):
            continue
        mapped += 1
        for exposure in exposure_list:
            if not isinstance(exposure, Mapping):
                continue
            benchmark_id = str(exposure.get("benchmark_id") or "")
            summary = series_status.get(benchmark_id) or {}
            if summary.get("status") != "OK":
                continue
            direction, materiality = _direction(summary, str(exposure.get("exposure_direction") or "PRODUCER_POSITIVE"))
            latest_date = str(summary.get("latest_date") or "")
            row = workset[normalized]
            events.append({
                "code": normalized,
                "name": row.get("name") or "",
                "observed_at": now,
                "published_at": latest_date + "T00:00:00+00:00" if latest_date else now,
                "source": PROVIDER,
                "source_ref": "https://stooq.com/",
                "evidence_type": "COMMODITY_PRICE",
                "title": f"{summary.get('label') or benchmark_id} benchmark move",
                "summary": (
                    f"latest={summary.get('latest_close')}; 1d={summary.get('change_1d_pct')}%; "
                    f"5d={summary.get('change_5d_pct')}%. Exposure mapping is research-only."
                ),
                "materiality": materiality,
                "direction": direction,
                "thesis_link": f"commodity:{benchmark_id}",
                "value_anchor_impact": "REVIEW_IF_PERSISTENT",
                "sell_relevance": "RESEARCH_ONLY",
                "confidence": "PUBLIC_MARKET_DATA",
            })

    ok_count = sum(item.get("status") == "OK" for item in series_status.values())
    failed_count = sum(str(item.get("status") or "").startswith("FETCH_ERROR") for item in series_status.values())
    latest_dates = [str(item.get("latest_date") or "") for item in series_status.values() if item.get("latest_date")]
    status = {
        "contract_version": "GEN_GE_COMMODITY_PRICE_EVIDENCE_V1",
        "generated_at": now,
        "status": "CONNECTED" if ok_count else ("UNAVAILABLE" if failed_count else "NO_SERIES"),
        "provider": PROVIDER,
        "benchmark_count": len(series_status),
        "benchmark_ok_count": ok_count,
        "benchmark_failed_count": failed_count,
        "latest_market_date": max(latest_dates) if latest_dates else None,
        "configured_security_exposure_count": len(exposures),
        "mapped_workset_security_count": mapped,
        "emitted_security_event_count": len(events),
        "mapping_status": "MAPPED" if mapped else "CONNECTED_NO_EVIDENCE_BACKED_SECURITY_EXPOSURES",
        "series": series_status,
        "formal_action_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    return events, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly-overlay", type=Path, default=Path("data/hourly_deep_overlay/latest.json"))
    parser.add_argument("--config", type=Path, default=Path("config/commodity_research_benchmarks.json"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/commodity_collector_status.json"))
    args = parser.parse_args(argv)
    events, status = collect(_load_json(args.hourly_overlay), _load_json(args.config))
    if events:
        append_events(args.evidence_root, events)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
