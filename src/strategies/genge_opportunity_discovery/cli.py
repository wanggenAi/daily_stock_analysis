"""Command line entry point for GenGe opportunity discovery."""

from __future__ import annotations

import argparse
import time
from datetime import date
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.strategies.genge_cycle_bottom.cli import (
    _has_current_snapshot_provider_outage,
    _industry_cycle_source,
    _load_benchmark,
    _load_csv,
    _load_inputs,
    _normalize_code,
    _parse_codes,
    _read_stock_pool,
    _read_stock_pool_records,
)
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.features import coerce_date, date_years_ago
from src.strategies.genge_cycle_bottom.industry_evidence import (
    load_evidence_csv,
    load_industry_evidence_schema,
    normalize_evidence_source,
)

from .pipeline import run_opportunity_discovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GenGe daily opportunity discovery research workflow.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--codes", help="Comma-separated stock codes, e.g. 000001,000002")
    group.add_argument("--stock-pool-file", help="Text file with one stock code per line")
    parser.add_argument("--years", type=int, default=5, help="History years to load before as-of date")
    parser.add_argument("--benchmark", default="000905", help="Benchmark index code")
    parser.add_argument("--output-dir", default="reports/opportunity_discovery", help="Report output directory")
    parser.add_argument("--max-codes", type=int, help="Optional cap for stock codes loaded from the pool")
    parser.add_argument(
        "--run-mode",
        choices=("quant-only", "quant-evidence", "full"),
        default="full",
        help="Execution scope for schedulers; full still avoids broker/trading actions",
    )
    parser.add_argument("--as-of-date", help="Research as-of date YYYY-MM-DD; only data on or before this date is used")
    parser.add_argument("--start-date", help="Optional data start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Optional data end date YYYY-MM-DD")
    parser.add_argument("--price-data-dir", help="Optional CSV directory with <code>.csv price files")
    parser.add_argument("--benchmark-file", help="Optional benchmark CSV file")
    parser.add_argument("--valuation-data-dir", help="Optional CSV directory with valuation files")
    parser.add_argument("--financial-data-dir", help="Optional CSV directory with financial files")
    parser.add_argument("--auto-fetch-valuation", action="store_true", help="Fetch missing valuation data from public sources and cache successes")
    parser.add_argument("--auto-fetch-financial", action="store_true", help="Fetch missing financial data from public sources and cache successes")
    parser.add_argument("--fundamental-cache-dir", default="data/cache/genge_fundamentals", help="Directory for successful public valuation/financial cache")
    parser.add_argument("--industry-cycle-file", help="Optional CSV file with industry cycle scores")
    parser.add_argument("--stock-industry-map", help="Optional CSV file mapping code to industry")
    parser.add_argument("--industry-evidence-file", help="Optional CSV file with industry cycle evidence rows")
    parser.add_argument("--company-evidence-file", help="Optional CSV file with company cycle evidence rows")
    parser.add_argument("--industry-evidence-schema", default="config/industry_evidence_schema.yaml", help="YAML schema for industry evidence indicators")
    parser.add_argument("--industry-alias-map", default="config/industry_alias_map.yaml", help="YAML map for industry aliases")
    parser.add_argument("--exit-profile-file", help="Optional CSV with code and balanced_exit_historical_profile/exit_profile_status")
    parser.add_argument("--forward-ledger-file", default="data/opportunity_snapshots/forward_observation_ledger.csv", help="Persistent forward observation ledger CSV")
    parser.add_argument("--priority-queue-size", type=int, default=50, help="Max rows in priority research queue")
    parser.add_argument("--secondary-queue-size", type=int, default=150, help="Max rows in secondary research queue")
    parser.add_argument("--fixture-smoke-passed", action="store_true", help="Mark fixture smoke as already verified for acceptance context")
    parser.add_argument("--ci-passed", action="store_true", help="Mark GitHub Actions fixture CI as observed passed for acceptance context")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.current_snapshot = True
    args.output_current_snapshot = False

    codes = [_normalize_code(code) for code in (_parse_codes(args.codes) + _read_stock_pool(args.stock_pool_file))]
    codes = list(dict.fromkeys(codes))
    if args.max_codes and args.max_codes > 0:
        codes = codes[: args.max_codes]
    if not codes:
        parser.error("no stock codes provided")

    stage_timings: dict[str, float] = {}
    stage_started = time.perf_counter()
    provisional_end = coerce_date(args.as_of_date or args.end_date) if (args.as_of_date or args.end_date) else date.today()
    provisional_start = coerce_date(args.start_date) if args.start_date else date_years_ago(provisional_end, args.years + 1)
    inputs, data_sources, data_errors, fundamental_diagnostics = _load_inputs(
        codes=codes,
        args=args,
        start_date=provisional_start,
        end_date=provisional_end,
    )
    stage_timings["load_inputs_seconds"] = round(time.perf_counter() - stage_started, 4)
    end_date = coerce_date(args.as_of_date or args.end_date) if (args.as_of_date or args.end_date) else provisional_end
    start_date = coerce_date(args.start_date) if args.start_date else date_years_ago(end_date, args.years)
    stage_started = time.perf_counter()
    if not args.price_data_dir and _has_current_snapshot_provider_outage(data_errors, codes):
        benchmark_df, benchmark_source_or_error = None, "skipped_current_snapshot_price_provider_unavailable"
    else:
        benchmark_df, benchmark_source_or_error = _load_benchmark(args, start_date, end_date)
    stage_timings["load_benchmark_seconds"] = round(time.perf_counter() - stage_started, 4)

    stage_started = time.perf_counter()
    source_mode = "fixture" if args.price_data_dir else "real"
    industry_cycle_df = _load_csv(Path(args.industry_cycle_file)) if args.industry_cycle_file else None
    industry_evidence_df = load_evidence_csv(args.industry_evidence_file) if args.industry_evidence_file else None
    company_evidence_df = load_evidence_csv(args.company_evidence_file) if args.company_evidence_file else None
    industry_evidence_schema = load_industry_evidence_schema(args.industry_evidence_schema) if args.industry_evidence_schema else {}
    industry_alias_map = load_industry_alias_map(args.industry_alias_map)
    exit_profile_df = pd.read_csv(args.exit_profile_file) if args.exit_profile_file else None
    stage_timings["load_evidence_seconds"] = round(time.perf_counter() - stage_started, 4)

    diagnostics = {
        "requested_codes": codes,
        "requested_stock_records": _read_stock_pool_records(args.stock_pool_file),
        "loaded_codes": [item.code for item in inputs],
        "data_sources": data_sources,
        "data_errors": data_errors,
        "benchmark": args.benchmark,
        "benchmark_source_or_error": benchmark_source_or_error,
        "output_dir": str(args.output_dir),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "industry_cycle_file": args.industry_cycle_file,
        "industry_cycle_source": _industry_cycle_source(args.industry_cycle_file, source_mode),
        "stock_industry_map": args.stock_industry_map,
        "industry_evidence_file": args.industry_evidence_file,
        "company_evidence_file": args.company_evidence_file,
        "industry_evidence_schema": args.industry_evidence_schema,
        "industry_alias_map": args.industry_alias_map,
        "exit_profile_file": args.exit_profile_file,
        "forward_ledger_file": args.forward_ledger_file,
        "run_mode": args.run_mode,
        "stage_elapsed_seconds": stage_timings,
        "industry_evidence_source": normalize_evidence_source(args.industry_evidence_file, source_mode),
        "company_evidence_source": normalize_evidence_source(args.company_evidence_file, source_mode),
        "industry_evidence_schema_industries": sorted((industry_evidence_schema.get("industries") or {}).keys()),
        "source_mode": source_mode,
        "ci_passed": bool(args.ci_passed),
        "fixture_smoke_passed": bool(args.price_data_dir or args.fixture_smoke_passed),
        "no_lookahead_risk": True,
        "no_auto_trade": True,
        "no_broker_integration": True,
    }
    diagnostics.update(fundamental_diagnostics)

    stage_started = time.perf_counter()
    report_dir, summary = run_opportunity_discovery(
        inputs=inputs,
        requested_codes=codes,
        data_errors=data_errors,
        data_sources=data_sources,
        benchmark_df=benchmark_df,
        industry_cycle_df=industry_cycle_df,
        industry_evidence_df=industry_evidence_df,
        company_evidence_df=company_evidence_df,
        industry_evidence_schema=industry_evidence_schema,
        industry_alias_map=industry_alias_map,
        requested_as_of_date=args.as_of_date or args.end_date,
        output_dir=args.output_dir,
        diagnostics=diagnostics,
        priority_queue_size=args.priority_queue_size,
        secondary_queue_size=args.secondary_queue_size,
        exit_profile_df=exit_profile_df,
        ledger_path=args.forward_ledger_file,
    )
    stage_timings["build_report_seconds"] = round(time.perf_counter() - stage_started, 4)
    summary["diagnostics"]["stage_elapsed_seconds"] = stage_timings
    print(f"report_dir={report_dir}")
    print(f"total_stocks={summary['total_stocks']}")
    print(f"valid_stocks={summary['valid_stocks']}")
    print(f"priority_research_queue_count={summary['priority_research_queue_count']}")
    print(f"secondary_research_queue_count={summary['secondary_research_queue_count']}")
    print(f"tier_a_count={summary['tier_a_count']}")
    print(f"tier_b_count={summary['tier_b_count']}")
    print(f"tier_c_count={summary['tier_c_count']}")
    print(f"acceptance_enum={summary['acceptance_enum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
