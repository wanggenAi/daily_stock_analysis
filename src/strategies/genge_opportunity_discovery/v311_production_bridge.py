"""Bridge discovery candidates into the authoritative GenGe V3.1.1 production path.

The discovery row remains the source of qualitative/hard-logic evidence.  Fresh
strict-PIT expectation inputs replace valuation primitives, including with
missing values when current evidence is unavailable.  Final gate/action fields
are always recomputed by :mod:`production_decision_scan`.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_decision_scan import write_reports
from .v311_current_expectation_inputs import write_current_expectation_inputs


PRODUCTION_OWNED_PREFIXES = ("production_",)
PRODUCTION_OWNED_FIELDS = frozenset(
    {
        "valuation_confidence",
        "valuation_confidence_reason_codes",
        "reason_codes",
        "normalized_earnings",
        "realistic_growth",
        "market_implied_growth",
        "expectation_gap",
        "neutral_value",
        "current_price",
        "price_to_neutral",
        "upstream_policy_reused",
        "upstream_policy_matches",
    }
)


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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _strip_upstream_production_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Remove prior decision outputs while retaining evidence and model inputs."""
    return {
        key: value
        for key, value in row.items()
        if key not in PRODUCTION_OWNED_FIELDS
        and not any(key.startswith(prefix) for prefix in PRODUCTION_OWNED_PREFIXES)
    }


def merge_source_and_current_rows(
    source_rows: Iterable[Mapping[str, Any]],
    current_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve source evidence and overlay fresh strict-PIT numeric inputs.

    Current rows intentionally overwrite source values even when the fresh
    value is empty/None.  Falling back to a stale valuation when a current
    fetch failed would violate the production fail-closed contract.
    """
    source_by_code = {
        _code(row.get("code")): _strip_upstream_production_fields(row)
        for row in source_rows
        if _code(row.get("code"))
    }
    current_by_code = {
        _code(row.get("code")): dict(row)
        for row in current_rows
        if _code(row.get("code"))
    }
    merged: list[dict[str, Any]] = []
    for code in sorted(set(source_by_code) | set(current_by_code)):
        row = dict(source_by_code.get(code, {}))
        row.update(current_by_code.get(code, {}))
        row["code"] = code
        row["v311_production_bridge"] = "SOURCE_EVIDENCE_PLUS_FRESH_STRICT_PIT"
        merged.append(row)
    return merged


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_bridge(
    source_csv: Path,
    output_dir: Path,
    *,
    codes_csv: Path | None = None,
    holdings_md: Path | None = None,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Refresh strict-PIT inputs, merge evidence, and emit production decisions."""
    output_dir.mkdir(parents=True, exist_ok=True)
    expectation_dir = output_dir / "expectation_inputs"
    current_rows = write_current_expectation_inputs(
        source_csv,
        expectation_dir,
        codes_csv=codes_csv,
        holdings_md=holdings_md,
        as_of=as_of,
    )
    source_rows = _read_csv(source_csv)
    merged_rows = merge_source_and_current_rows(source_rows, current_rows)
    merged_csv = output_dir / "v311_production_inputs.csv"
    _write_csv(merged_csv, merged_rows)
    return write_reports(merged_csv, output_dir, holdings_md=holdings_md)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--codes-csv", type=Path)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    rows = run_bridge(
        args.source_csv,
        args.output_dir,
        codes_csv=args.codes_csv,
        holdings_md=args.holdings_md,
        as_of=as_of,
    )
    print(f"v311_production_bridge={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
