"""Bridge discovery candidates into the authoritative GenGe V3.1.1 production path.

Candidate selection and evidence provenance are deliberately separate. A narrow
Top5 CSV selects candidate codes, while an optional same-run rich evidence CSV
supplies complete qualitative/V3.1 assessment fields. Fresh strict-PIT inputs
replace valuation primitives. Confirmed holdings, when explicitly supplied,
are also refreshed and retained as production inputs. Final gate/action fields
are always recomputed by :mod:`production_decision_scan`.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_decision_scan import read_holdings_markdown, write_reports
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


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _strip_upstream_production_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Remove prior decision outputs while retaining evidence and model inputs."""
    return {
        key: value
        for key, value in row.items()
        if key not in PRODUCTION_OWNED_FIELDS
        and not any(key.startswith(prefix) for prefix in PRODUCTION_OWNED_PREFIXES)
    }


def _evidence_by_code(evidence_rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _code(row.get("code")): _strip_upstream_production_fields(row)
        for row in evidence_rows
        if _code(row.get("code"))
    }


def join_selected_candidates_with_evidence(
    candidate_rows: Iterable[Mapping[str, Any]],
    evidence_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Use candidate rows only as selected-code set and enrich from same-run evidence."""
    evidence = _evidence_by_code(evidence_rows)
    joined: list[dict[str, Any]] = []
    for candidate in candidate_rows:
        code = _code(candidate.get("code"))
        if not code:
            continue
        row = dict(evidence.get(code, {}))
        for key, value in _strip_upstream_production_fields(candidate).items():
            if _has_value(value):
                row[key] = value
        row["code"] = code
        row["v311_source_scope"] = "CANDIDATE"
        row["v311_same_run_evidence_joined"] = code in evidence
        joined.append(row)
    return joined


def add_holdings_to_source_evidence(
    source_rows: Iterable[Mapping[str, Any]],
    holding_rows: Iterable[Mapping[str, Any]],
    evidence_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Add confirmed holdings without letting them expand candidate selection.

    Same-run rich evidence is attached when available. If it is absent, only
    explicit holding metadata is added; missing hard-logic evidence remains
    missing and the downstream V3.1.1 contract must fail closed rather than
    fabricate it.
    """
    result = [dict(row) for row in source_rows]
    existing = {_code(row.get("code")) for row in result}
    evidence = _evidence_by_code(evidence_rows)
    for holding in holding_rows:
        code = _code(holding.get("code"))
        if not code or code in existing:
            continue
        row = dict(evidence.get(code, {}))
        row.update(_strip_upstream_production_fields(holding))
        row["code"] = code
        row["v311_source_scope"] = "HOLDING"
        row["v311_same_run_evidence_joined"] = code in evidence
        result.append(row)
        existing.add(code)
    return result


def merge_source_and_current_rows(
    source_rows: Iterable[Mapping[str, Any]],
    current_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve selected candidate/holding evidence and overlay fresh PIT inputs.

    Current rows intentionally overwrite source valuation values even when the
    fresh value is empty/None. Falling back to stale valuation after a current
    fetch failure would violate the production fail-closed contract.
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
    # Only explicitly selected candidates and explicitly confirmed holdings are
    # allowed into production. Current refresh rows cannot introduce securities.
    for code in sorted(source_by_code):
        row = dict(source_by_code[code])
        if code in current_by_code:
            row.update(current_by_code[code])
        row["code"] = code
        row["v311_production_bridge"] = "EXPLICIT_SOURCE_PLUS_FRESH_STRICT_PIT"
        merged.append(row)
    return merged


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _source_price_dates(source_rows: Iterable[Mapping[str, Any]]) -> dict[str, date]:
    """Return evidence-backed trade dates for upstream price observations."""
    result: dict[str, date] = {}
    for row in source_rows:
        code = _code(row.get("code"))
        if not code:
            continue
        for field in (
            "price_date",
            "raw_latest_trade_date",
            "latest_trade_date",
            "qfq_latest_trade_date",
            "trade_date",
            "data_date",
        ):
            parsed = _parse_iso_date(row.get(field))
            if parsed is not None:
                result[code] = parsed
                break
    return result


def _invalidate_price_dependent_inputs(row: dict[str, Any], error: str) -> None:
    """Remove price-dependent authority when observation time cannot be proven."""
    row["v311_expectation_input_status"] = "HOLD_REVIEW_INPUT_INCOMPLETE"
    row["v311_input_error"] = error
    row["price_date"] = ""
    # Keep financial-history evidence, but remove fields that could manufacture
    # a price-dependent BUY/ADD/REDUCE/EXIT from an unverified observation.
    for field in (
        "v31_current_price",
        "current_price",
        "v31_market_implied_profit_cagr",
        "market_implied_growth",
        "v31_expectation_gap_pct",
        "expectation_gap",
        "price_to_neutral",
    ):
        row[field] = None


def reconcile_current_price_provenance(
    source_rows: Iterable[Mapping[str, Any]],
    current_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
) -> list[dict[str, Any]]:
    """Repair or fail closed on price dates before production decisions.

    The current strict-PIT extractor historically wrote ``decision_date`` into
    ``price_date`` even when the reused upstream close belonged to the previous
    trading session.  The authoritative bridge therefore resolves upstream
    observations against their real source trade date. A price with no provable
    observation date cannot drive a production price-dependent action.
    """
    source_dates = _source_price_dates(source_rows)
    reconciled: list[dict[str, Any]] = []
    for raw in current_rows:
        row = dict(raw)
        code = _code(row.get("code"))
        source = str(row.get("current_price_source") or "").strip().upper()
        has_price = _has_value(row.get("v31_current_price")) or _has_value(row.get("current_price"))
        if not code or not has_price:
            reconciled.append(row)
            continue

        if source.startswith("UPSTREAM_"):
            observed = source_dates.get(code)
            if observed is None:
                _invalidate_price_dependent_inputs(row, "PRICE_DATE_UNVERIFIED")
            elif observed > as_of:
                _invalidate_price_dependent_inputs(row, "PRICE_DATE_AFTER_DECISION_DATE")
            else:
                row["price_date"] = observed.isoformat()
        else:
            # The legacy price loader returns only value/source, not the actual
            # observation date. Do not trust its synthetic as-of date here.
            _invalidate_price_dependent_inputs(row, "PRICE_DATE_UNVERIFIED")
        reconciled.append(row)
    return reconciled


def run_bridge(
    source_csv: Path,
    output_dir: Path,
    *,
    evidence_csv: Path | None = None,
    codes_csv: Path | None = None,
    holdings_md: Path | None = None,
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Join evidence, refresh strict-PIT inputs, and emit production decisions."""
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = _read_csv(source_csv)
    evidence_rows = _read_csv(evidence_csv) if evidence_csv is not None else []
    if evidence_csv is not None:
        source_rows = join_selected_candidates_with_evidence(candidate_rows, evidence_rows)
    else:
        source_rows = []
        for candidate in candidate_rows:
            code = _code(candidate.get("code"))
            if not code:
                continue
            row = _strip_upstream_production_fields(candidate)
            row["code"] = code
            row["v311_source_scope"] = "CANDIDATE"
            row["v311_same_run_evidence_joined"] = False
            source_rows.append(row)

    holding_rows = read_holdings_markdown(holdings_md) if holdings_md else []
    if holding_rows:
        source_rows = add_holdings_to_source_evidence(source_rows, holding_rows, evidence_rows)

    selected_source_csv = output_dir / "v311_selected_source_evidence.csv"
    _write_csv(selected_source_csv, source_rows)

    expectation_dir = output_dir / "expectation_inputs"
    effective_as_of = as_of or date.today()
    current_rows = write_current_expectation_inputs(
        selected_source_csv,
        expectation_dir,
        codes_csv=codes_csv,
        holdings_md=holdings_md,
        as_of=effective_as_of,
    )
    current_rows = reconcile_current_price_provenance(
        source_rows,
        current_rows,
        as_of=effective_as_of,
    )
    # Persist the reconciled input surface so downstream audits inspect the
    # exact rows that production consumed rather than the pre-reconciliation file.
    _write_csv(expectation_dir / "v311_current_expectation_inputs.csv", current_rows)

    merged_rows = merge_source_and_current_rows(source_rows, current_rows)
    merged_csv = output_dir / "v311_production_inputs.csv"
    _write_csv(merged_csv, merged_rows)
    return write_reports(merged_csv, output_dir, holdings_md=holdings_md)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--evidence-csv", type=Path)
    parser.add_argument("--codes-csv", type=Path)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    rows = run_bridge(
        args.source_csv,
        args.output_dir,
        evidence_csv=args.evidence_csv,
        codes_csv=args.codes_csv,
        holdings_md=args.holdings_md,
        as_of=as_of,
    )
    print(f"v311_production_bridge={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
