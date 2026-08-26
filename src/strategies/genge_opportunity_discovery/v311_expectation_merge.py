"""Merge frozen V3.1.1 expectation inputs into the existing valuation report.

The bridge changes no ranking, routing or qualitative V3.1 evidence. It merely
adds the numeric strict-PIT fields calculated by ``v311_current_expectation_inputs``
so the already-existing Formal BUY / production layers can consume them.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


EXPECTED_POLICY_SOURCE = "round6_expectation_gap_10y_strict_pit_frozen"
SIDE_CAR_FIELDS = frozenset(
    {
        "decision_date",
        "price_date",
        "fund_available_date",
        "financial_report_date",
        "current_price_source",
        "v311_expectation_input_status",
        "v311_expectation_policy_source",
        "v311_input_error",
        "v31_current_price",
        "v31_normalized_profit",
        "v31_normalized_profit_method",
        "v31_neutral_value",
        "v31_realistic_profit_cagr",
        "v31_market_implied_profit_cagr",
        "v31_expectation_gap_pct",
        "normalized_earnings",
        "realistic_growth",
        "market_implied_growth",
        "expectation_gap",
        "neutral_value",
        "price_to_neutral",
        "normalized_earnings_observation_count",
        "deduct_profit_quality_factor",
        "cash_conversion_ratio",
        "realistic_growth_four_report_range",
        "implied_growth_status",
        "eps_growth_3y_round6",
        "revenue_growth_3y_round6",
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


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _latest_routed(root: Path) -> Path:
    direct = root / "valuation_research_routed.csv"
    if direct.exists():
        return direct
    candidates = sorted(root.glob("**/valuation_research_routed.csv"), key=str)
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def merge_expectation_inputs(
    valuation_rows: list[Mapping[str, Any]],
    expectation_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sidecar = {
        _code(row.get("code")): dict(row)
        for row in expectation_rows
        if _code(row.get("code"))
    }
    merged: list[dict[str, Any]] = []
    for raw in valuation_rows:
        row = dict(raw)
        code = _code(row.get("code"))
        row["code"] = code
        extra = sidecar.get(code)
        if extra:
            source = str(extra.get("v311_expectation_policy_source") or "").strip()
            if source and source != EXPECTED_POLICY_SOURCE:
                raise ValueError(f"unexpected V3.1.1 expectation policy source for {code}: {source}")
            for field in SIDE_CAR_FIELDS:
                value = extra.get(field)
                # The current strict-PIT sidecar is authoritative for its own
                # numeric fields. Empty values intentionally remain empty rather
                # than falling back to semantically different old PE diagnostics.
                if field in extra:
                    row[field] = value
            row["v311_expectation_inputs_merged"] = True
        else:
            row["v311_expectation_inputs_merged"] = False
        merged.append(row)
    return merged


def write_enriched_valuation(
    valuation_root: Path,
    expectation_csv: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    routed_path = _latest_routed(valuation_root)
    valuation_rows = _read(routed_path)
    expectation_rows = _read(expectation_csv)
    rows = merge_expectation_inputs(valuation_rows, expectation_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with (output_dir / "valuation_research_routed.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Preserve human-facing routed report when available for audit only. The CSV
    # above remains authoritative for the downstream Formal BUY layer.
    source_dir = routed_path.parent
    routed_md = source_dir / "valuation_research_routed.md"
    if routed_md.exists():
        shutil.copy2(routed_md, output_dir / routed_md.name)

    expectation_codes = {_code(row.get("code")) for row in expectation_rows}
    valuation_codes = {_code(row.get("code")) for row in valuation_rows}
    summary = {
        "row_count": len(rows),
        "expectation_input_count": len(expectation_codes),
        "merged_count": sum(bool(row.get("v311_expectation_inputs_merged")) for row in rows),
        "expectation_codes_missing_from_valuation": sorted(expectation_codes - valuation_codes),
        "ranking_changed": False,
        "routing_changed": False,
        "qualitative_v31_fields_fabricated": False,
        "scenario_valuation_fabricated": False,
        "policy_source": EXPECTED_POLICY_SOURCE,
    }
    (output_dir / "v311_expectation_merge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--expectation-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_enriched_valuation(args.valuation_root, args.expectation_csv, args.output_dir)
    print(f"v311_enriched_valuation={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
