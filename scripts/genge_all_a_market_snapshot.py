#!/usr/bin/env python3
"""Persist compact All-A market facts from an existing completed scan.

No network access. The scanner owns acquisition/calculation; this adapter makes the
latest market facts durable so later GPT/research runs can consume them without
rerunning the crawler.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT = "GEN_GE_ALL_A_MARKET_SNAPSHOT_V1"
DEFAULT_REPORT_ROOT = Path("reports/all_a_full_scan")
DEFAULT_OUT = Path("data/market_snapshots")
PRICE_KEYS = ("raw_latest_close", "latest_price", "current_price", "adjusted_latest_close")
KEEP_KEYS = (
    "code", "stock_name", "exchange", "board", "industry", "latest_trade_date",
    "raw_latest_close", "adjusted_latest_close", "latest_price", "current_price",
    "liquidity", "volume", "amount", "turnover", "turnover_rate",
    "qfq_source", "raw_source", "qfq_latest_trade_date", "raw_latest_trade_date",
    "price_mapping_status", "price_adjustment_warning", "quant_status", "quant_rank",
)


def _latest_run(root: Path) -> Path:
    runs = [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    runs = [p for p in runs if any(p.rglob("*.csv"))]
    if not runs:
        raise FileNotFoundError(f"no completed All-A scan directory under {root}")
    return sorted(runs, key=lambda p: p.name)[-1]


def _candidate_csvs(run_dir: Path) -> list[tuple[int, int, Path, list[dict[str, str]]]]:
    candidates: list[tuple[int, int, Path, list[dict[str, str]]]] = []
    for path in sorted(run_dir.rglob("*.csv")):
        try:
            with path.open(encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                fields = set(reader.fieldnames or [])
                if "code" not in fields or "latest_trade_date" not in fields:
                    continue
                if not any(key in fields for key in PRICE_KEYS):
                    continue
                rows = list(reader)
        except Exception:
            continue
        if not rows:
            continue
        price_field_count = sum(key in fields for key in PRICE_KEYS)
        candidates.append((len(rows), price_field_count, path, rows))
    return candidates


def _norm_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _pick_source(run_dir: Path) -> tuple[Path, list[dict[str, str]]]:
    candidates = _candidate_csvs(run_dir)
    if not candidates:
        raise FileNotFoundError(
            f"no All-A CSV with code/latest_trade_date/price fields under {run_dir}"
        )
    # Prefer population-wide source; ties prefer richer price provenance.
    _count, _richness, path, rows = max(candidates, key=lambda item: (item[0], item[1]))
    return path, rows


def build_snapshot(report_root: Path = DEFAULT_REPORT_ROOT, output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    run_dir = _latest_run(report_root)
    source_path, source_rows = _pick_source(run_dir)
    normalized: list[dict[str, Any]] = []
    dates: set[str] = set()
    priced = 0
    for row in source_rows:
        code = _norm_code(row.get("code"))
        trade_date = str(row.get("latest_trade_date") or "")[:10]
        if not code or not trade_date:
            continue
        dates.add(trade_date)
        item = {key: row.get(key) for key in KEEP_KEYS if key in row}
        item["code"] = code
        item["latest_trade_date"] = trade_date
        price = next((row.get(key) for key in PRICE_KEYS if row.get(key) not in (None, "")), None)
        item["research_reference_price"] = price
        if price not in (None, ""):
            priced += 1
        normalized.append(item)
    if not normalized:
        raise RuntimeError("All-A source contains no usable market rows")
    latest_trade_date = max(dates)
    latest_rows = [row for row in normalized if row["latest_trade_date"] == latest_trade_date]
    if not latest_rows:
        raise RuntimeError("no rows on latest trade date")
    latest_priced = sum(row.get("research_reference_price") not in (None, "") for row in latest_rows)
    coverage = latest_priced / len(latest_rows)
    if coverage < 0.95:
        raise RuntimeError(f"latest All-A price coverage too low: {coverage:.4f}")
    latest_rows.sort(key=lambda row: row["code"])
    digest = hashlib.sha256(
        json.dumps(latest_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "contract": CONTRACT,
        "generated_at": generated_at,
        "latest_trade_date": latest_trade_date,
        "source_scan_run_dir": run_dir.as_posix(),
        "source_csv": source_path.as_posix(),
        "source_content_sha256": digest,
        "universe_row_count": len(source_rows),
        "latest_trade_date_row_count": len(latest_rows),
        "latest_trade_date_priced_count": latest_priced,
        "latest_trade_date_price_coverage_ratio": round(coverage, 6),
        "network_accessed_by_snapshot_builder": False,
        "formal_action_authority": "NONE",
        "automatic_execution_allowed": False,
        "rows": latest_rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    dated = output_dir / f"{latest_trade_date}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if dated.exists():
        existing = json.loads(dated.read_text(encoding="utf-8"))
        # A later same-day scanner may legitimately improve/fix data; keep the dated
        # file as latest same-day truth and preserve content hash provenance.
        if existing.get("source_content_sha256") != digest:
            history = output_dir / "history"
            history.mkdir(parents=True, exist_ok=True)
            old_hash = str(existing.get("source_content_sha256") or "unknown")[:12]
            (history / f"{latest_trade_date}-{old_hash}.json").write_text(
                json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    dated.write_text(text, encoding="utf-8")
    (output_dir / "latest.json").write_text(text, encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        payload = build_snapshot(args.report_root, args.output_dir)
    except Exception as exc:
        print(json.dumps({"contract": CONTRACT, "error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "contract": CONTRACT,
        "latest_trade_date": payload["latest_trade_date"],
        "rows": payload["latest_trade_date_row_count"],
        "price_coverage": payload["latest_trade_date_price_coverage_ratio"],
        "source_csv": payload["source_csv"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
