"""Build the ledger-independent broad Discovery Pool for GenGe V3.1.1.

This layer deliberately knows nothing about ``V31_CANDIDATE_LEDGER.md``.  It
rebuilds high-recall current candidates only from the same-run All-A scan and
industry coverage.  Candidate metabolism is applied later in valuation/deep
research, so archived names can leave expensive downstream research without
silently disappearing from the market-discovery universe.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .industry_valuation_bridge import (
    _find_all_a_report,
    _read,
    _read_all_a,
    merge_sources,
)

DISCOVERY_CONTRACT_VERSION = "GEN_GE_V31_LEDGER_INDEPENDENT_DISCOVERY_V1"


def build_discovery_rows(
    all_a_rows: list[Mapping[str, Any]],
    industry_rows: list[Mapping[str, Any]],
    *,
    global_limit: int = 500,
    relaxed_reserve: int = 300,
    per_industry: int = 5,
) -> list[dict[str, Any]]:
    """Return broad current-run recall without durable-ledger filtering.

    No curated/ledger names are injected here and no archived/INVALIDATED names
    are removed here.  Current evidence alone determines whether a security is
    present in this Discovery Pool.  Downstream research may still suppress an
    invalidated name from valuation/deep-review recall.
    """
    rows = merge_sources(
        all_a_rows,
        industry_rows,
        global_limit=global_limit,
        relaxed_reserve=relaxed_reserve,
        per_industry=per_industry,
        curated_codes=(),
        excluded_codes=(),
    )
    for row in rows:
        row["discovery_contract_version"] = DISCOVERY_CONTRACT_VERSION
        row["discovery_ledger_filter_applied"] = False
        row["discovery_durable_recall_applied"] = False
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_discovery_report(
    all_a_report: Path,
    industry_coverage: Path,
    output_dir: Path,
    *,
    global_limit: int = 500,
    relaxed_reserve: int = 300,
    per_industry: int = 5,
) -> list[dict[str, Any]]:
    report = _find_all_a_report(all_a_report)
    all_a_rows = _read_all_a(report)
    industry_rows = _read(industry_coverage / "industry_top_candidates.csv")
    if not all_a_rows:
        raise FileNotFoundError("missing global All-A source")
    if not industry_rows:
        raise FileNotFoundError("missing industry coverage source")

    rows = build_discovery_rows(
        all_a_rows,
        industry_rows,
        global_limit=global_limit,
        relaxed_reserve=relaxed_reserve,
        per_industry=per_industry,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "ledger_independent_discovery.csv", rows)

    summary = {
        "discovery_contract_version": DISCOVERY_CONTRACT_VERSION,
        "discovery_count": len(rows),
        "global_limit": int(global_limit),
        "relaxed_reserve": int(relaxed_reserve),
        "per_industry": int(per_industry),
        "ledger_filter_applied": False,
        "durable_recall_applied": False,
        "candidate_ledger_is_input": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "ledger_independent_discovery_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-a-report", type=Path, required=True)
    parser.add_argument("--industry-coverage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--global-limit", type=int, default=500)
    parser.add_argument("--relaxed-reserve", type=int, default=300)
    parser.add_argument("--per-industry", type=int, default=5)
    args = parser.parse_args(argv)
    rows = write_discovery_report(
        args.all_a_report,
        args.industry_coverage,
        args.output_dir,
        global_limit=args.global_limit,
        relaxed_reserve=args.relaxed_reserve,
        per_industry=args.per_industry,
    )
    print(f"ledger_independent_discovery={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
