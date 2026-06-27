#!/usr/bin/env python3
"""Run GenGe Cycle Bottom research on live public A-share data.

This script intentionally reuses the strategy CLI. It does not connect to any
broker, does not read account data, and does not place orders.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.strategies.genge_cycle_bottom.cli import main as strategy_main


def _repo_root() -> Path:
    return REPO_ROOT


def _read_pool_lines(path: Path, max_codes: int | None) -> List[str]:
    lines: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if max_codes and len(lines) >= max_codes:
            break
    return lines


def _latest_report_dir(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    report_dirs = sorted(path for path in output_dir.iterdir() if path.is_dir())
    return report_dirs[-1] if report_dirs else None


def _build_strategy_args(args: argparse.Namespace, pool_file: Path) -> list[str]:
    strategy_args = [
        "--stock-pool-file",
        str(pool_file),
        "--years",
        str(args.years),
        "--benchmark",
        args.benchmark,
        "--output-dir",
        str(args.output_dir),
        "--step-days",
        str(args.step_days),
        "--fee-bps",
        str(args.fee_bps),
        "--slippage-bps",
        str(args.slippage_bps),
    ]
    if args.start_date:
        strategy_args.extend(["--start-date", args.start_date])
    if args.end_date:
        strategy_args.extend(["--end-date", args.end_date])
    if args.industry_cycle_file:
        strategy_args.extend(["--industry-cycle-file", args.industry_cycle_file])
    if args.stock_industry_map:
        strategy_args.extend(["--stock-industry-map", args.stock_industry_map])
    if args.auto_fetch_valuation:
        strategy_args.append("--auto-fetch-valuation")
    if args.auto_fetch_financial:
        strategy_args.append("--auto-fetch-financial")
    if args.fundamental_cache_dir:
        strategy_args.extend(["--fundamental-cache-dir", args.fundamental_cache_dir])
    if args.fixture_smoke_passed:
        strategy_args.append("--fixture-smoke-passed")
    if args.ci_passed:
        strategy_args.append("--ci-passed")
    return strategy_args


def _write_limited_pool(lines: Iterable[str]) -> Path:
    temp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="genge_real_pool_",
        suffix=".txt",
        delete=False,
    )
    with temp:
        for line in lines:
            temp.write(line + "\n")
    return Path(temp.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GenGe real-data research on a configured A-share pool.")
    parser.add_argument(
        "--stock-pool-file",
        default=str(_repo_root() / "stock_pools" / "genge_core_pool.txt"),
        help="Pool file. Format: code or code,name,industry.",
    )
    parser.add_argument("--years", type=int, default=5, help="Historical years to scan, usually 5 or 10.")
    parser.add_argument("--benchmark", default="000300", choices=("000300", "000905", "000985"))
    parser.add_argument("--output-dir", default="reports/genge_cycle_bottom_real")
    parser.add_argument("--max-codes", type=int, default=20, help="Limit loaded pool size for local smoke runs.")
    parser.add_argument("--step-days", type=int, default=None, help="Signal scan interval. Default is 1; fast smoke uses 20 unless overridden.")
    parser.add_argument("--fast-smoke", action="store_true", help="Use step-days=20 when --step-days is not provided.")
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--auto-fetch-valuation", action="store_true")
    parser.add_argument("--auto-fetch-financial", action="store_true")
    parser.add_argument("--fundamental-cache-dir", default="data/cache/genge_fundamentals")
    parser.add_argument("--industry-cycle-file")
    parser.add_argument("--stock-industry-map")
    parser.add_argument("--fixture-smoke-passed", action="store_true", help="Pass acceptance context after fixture smoke has been verified")
    parser.add_argument("--ci-passed", action="store_true", help="Pass acceptance context after GitHub Actions fixture CI has been observed passed")
    return parser


def resolve_step_days(args: argparse.Namespace) -> int:
    if args.step_days is not None:
        return max(1, int(args.step_days))
    return 20 if bool(args.fast_smoke) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pool_path = Path(args.stock_pool_file)
    if not pool_path.exists():
        parser.error(f"stock pool file not found: {pool_path}")
    args.step_days = resolve_step_days(args)

    lines = _read_pool_lines(pool_path, args.max_codes)
    if not lines:
        parser.error(f"stock pool file is empty: {pool_path}")

    args.output_dir = Path(args.output_dir)
    start_ts = time.perf_counter()
    limited_pool = _write_limited_pool(lines)
    try:
        exit_code = strategy_main(_build_strategy_args(args, limited_pool))
    finally:
        try:
            limited_pool.unlink()
        except OSError:
            pass

    elapsed = time.perf_counter() - start_ts
    report_dir = _latest_report_dir(args.output_dir)
    if report_dir and (report_dir / "summary.json").exists():
        summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
        diagnostics = summary.get("diagnostics") or {}
        data_errors = diagnostics.get("data_errors") or {}
        provider_errors = diagnostics.get("provider_errors") or {}
        gate = summary.get("paper_trading_gate") or {}
        print(f"elapsed_seconds={elapsed:.2f}")
        print(f"report_dir={report_dir}")
        print(f"data_failures={len(data_errors)}")
        print(f"provider_error_count={len(provider_errors)}")
        print(f"pe_missing_count={summary.get('pe_missing_count', 0)}")
        print(f"pb_missing_count={summary.get('pb_missing_count', 0)}")
        print(f"financial_missing_count={summary.get('financial_missing_count', 0)}")
        print(f"valuation_coverage_rate={summary.get('valuation_coverage_rate', 0)}")
        print(f"financial_coverage_rate={summary.get('financial_coverage_rate', 0)}")
        print(f"total_signals={summary.get('total_signals', 0)}")
        print(f"risk_review_count={len(summary.get('worst_signals') or [])}")
        print(f"paper_trading_gate={gate.get('verdict', 'UNKNOWN')}")
    else:
        print(f"elapsed_seconds={elapsed:.2f}")
        print("report_dir=NONE")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
