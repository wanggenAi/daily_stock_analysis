"""Build the bounded input set for authoritative V3.1.1 production refresh.

The broad Discovery/Deep-Review pools are research surfaces, not live valuation
refresh queues.  Re-fetching strict-PIT financials for hundreds of UNKNOWN
research rows makes the hourly production chain both slow and provider-fragile.

This module narrows production refresh to:
- candidates that have already reached V3.1 A-eligibility / BUY-readiness; and
- explicitly confirmed holdings, which must always be re-underwritten.

For those codes it reuses same-run All-A evidence, especially dated raw price
observations, before the strict-PIT bridge considers an external provider.
Nothing here promotes a stock: it only selects which already-qualified rows are
allowed to consume the expensive production refresh.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_decision_scan import read_holdings_markdown
from .selection_framework_v31 import execution_universe_status


DATE_FIELDS = (
    "raw_latest_trade_date",
    "qfq_latest_trade_date",
    "latest_trade_date",
    "trade_date",
    "price_date",
    "data_date",
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


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _row_observation_date(row: Mapping[str, Any]) -> date | None:
    for field in DATE_FIELDS:
        parsed = _parse_date(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _candidate_is_production_worthy(row: Mapping[str, Any]) -> bool:
    """Return True only after the qualitative V3.1 qualification boundary.

    A broad/deep-review row with UNKNOWN moat/demand gates must never trigger an
    expensive live production refresh.  A-eligibility is intentionally enough:
    current strict-PIT valuation may still change BUY-ready status.
    """
    if _truthy(row.get("v31_buy_ready")) or _truthy(row.get("v31_a_eligible")):
        return True
    candidate_class = str(row.get("v31_candidate_class") or "").strip().upper()
    failures = str(row.get("v31_hard_gate_failures") or "").strip()
    unknowns = str(row.get("v31_hard_gate_unknowns") or "").strip()
    return candidate_class in {"A1", "A2", "A3"} and not failures and not unknowns


def _merge_nonempty(target: dict[str, Any], source: Mapping[str, Any], *, overwrite: bool) -> None:
    for key, value in source.items():
        if not _has_value(value):
            continue
        if overwrite or not _has_value(target.get(key)):
            target[key] = value


def _index_best_evidence(
    rows: Iterable[Mapping[str, Any]],
    selected_codes: set[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    best_date: dict[str, date | None] = {}
    for raw in rows:
        code = _code(raw.get("code"))
        if code not in selected_codes:
            continue
        observed = _row_observation_date(raw)
        current = best_date.get(code)
        if code not in result or (observed is not None and (current is None or observed > current)):
            result[code] = dict(raw)
            best_date[code] = observed
        elif observed == current:
            _merge_nonempty(result[code], raw, overwrite=False)
    return result


def _scan_local_evidence(root: Path | None, selected_codes: set[str]) -> dict[str, dict[str, Any]]:
    """Find same-run evidence for selected codes without loading all rows into memory."""
    if root is None or not root.exists() or not selected_codes:
        return {}
    result: dict[str, dict[str, Any]] = {}
    best_date: dict[str, date | None] = {}
    for path in sorted(root.rglob("*.csv")):
        try:
            with path.open(encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or "code" not in reader.fieldnames:
                    continue
                for raw in reader:
                    code = _code(raw.get("code"))
                    if code not in selected_codes:
                        continue
                    observed = _row_observation_date(raw)
                    current = best_date.get(code)
                    if code not in result or (observed is not None and (current is None or observed > current)):
                        result[code] = dict(raw)
                        best_date[code] = observed
                    elif observed == current:
                        _merge_nonempty(result[code], raw, overwrite=False)
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
    return result


def build_shortlist(
    candidate_rows: Iterable[Mapping[str, Any]],
    *,
    holding_rows: Iterable[Mapping[str, Any]] = (),
    evidence_rows: Iterable[Mapping[str, Any]] = (),
    directory_evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates = {
        _code(row.get("code")): dict(row)
        for row in candidate_rows
        if _code(row.get("code")) and _candidate_is_production_worthy(row)
    }
    # Never allow a research-only board to become a formal candidate merely by
    # passing upstream labels. Holdings are retained regardless of board because
    # they require explicit re-underwriting and downstream policy handles action.
    candidates = {
        code: row
        for code, row in candidates.items()
        if execution_universe_status(code) == "EXECUTION_ELIGIBLE"
    }
    holdings = {
        _code(row.get("code")): dict(row)
        for row in holding_rows
        if _code(row.get("code"))
    }
    selected_codes = set(candidates) | set(holdings)
    evidence = _index_best_evidence(evidence_rows, selected_codes)
    directory_evidence = dict(directory_evidence or {})

    rows: list[dict[str, Any]] = []
    for code in sorted(selected_codes):
        merged: dict[str, Any] = {}
        _merge_nonempty(merged, directory_evidence.get(code, {}), overwrite=True)
        _merge_nonempty(merged, evidence.get(code, {}), overwrite=True)
        _merge_nonempty(merged, candidates.get(code, {}), overwrite=True)
        _merge_nonempty(merged, holdings.get(code, {}), overwrite=True)
        merged["code"] = code
        merged["production_shortlist_scope"] = "HOLDING" if code in holdings else "CANDIDATE"
        merged["production_shortlist_reason"] = (
            "CONFIRMED_HOLDING" if code in holdings else "V31_A_ELIGIBLE_OR_BUY_READY"
        )
        observed = _row_observation_date(merged)
        merged["production_shortlist_price_provenance"] = (
            "DATED_SAME_RUN_EVIDENCE" if observed is not None else "PROVIDER_FALLBACK_REQUIRED"
        )
        rows.append(merged)
    return rows


def write_shortlist(
    candidate_csv: Path,
    output_dir: Path,
    *,
    holdings_md: Path | None = None,
    evidence_csv: Path | None = None,
    all_a_report_root: Path | None = None,
) -> list[dict[str, Any]]:
    candidate_rows = _read_csv(candidate_csv)
    holding_rows = read_holdings_markdown(holdings_md) if holdings_md else []
    preliminary_codes = {
        _code(row.get("code"))
        for row in candidate_rows
        if _code(row.get("code")) and _candidate_is_production_worthy(row)
    } | {_code(row.get("code")) for row in holding_rows if _code(row.get("code"))}
    directory_evidence = _scan_local_evidence(all_a_report_root, preliminary_codes)
    rows = build_shortlist(
        candidate_rows,
        holding_rows=holding_rows,
        evidence_rows=_read_csv(evidence_csv),
        directory_evidence=directory_evidence,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "production_shortlist.csv"
    fields = sorted({key for row in rows for key in row})
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "broad_candidate_count": len(candidate_rows),
        "shortlist_count": len(rows),
        "candidate_refresh_count": sum(row["production_shortlist_scope"] == "CANDIDATE" for row in rows),
        "holding_refresh_count": sum(row["production_shortlist_scope"] == "HOLDING" for row in rows),
        "dated_same_run_price_count": sum(
            row["production_shortlist_price_provenance"] == "DATED_SAME_RUN_EVIDENCE" for row in rows
        ),
        "provider_fallback_required_count": sum(
            row["production_shortlist_price_provenance"] == "PROVIDER_FALLBACK_REQUIRED" for row in rows
        ),
        "broad_research_rows_are_production_refresh_inputs": False,
        "no_auto_trade": True,
    }
    (output_dir / "production_shortlist_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--evidence-csv", type=Path)
    parser.add_argument("--all-a-report-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_shortlist(
        args.candidate_csv,
        args.output_dir,
        holdings_md=args.holdings_md,
        evidence_csv=args.evidence_csv,
        all_a_report_root=args.all_a_report_root,
    )
    print(f"production_shortlist={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
