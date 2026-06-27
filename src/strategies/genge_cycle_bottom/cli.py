"""Command line entry point for GenGe Cycle Bottom Strategy backtests."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .backtest import BacktestInput, WalkForwardBacktester
from .features import coerce_date, date_years_ago, prepare_price_frame
from .metrics import compute_summary
from .report import write_reports


def _parse_codes(raw_codes: Optional[str]) -> List[str]:
    if not raw_codes:
        return []
    return [code.strip() for code in raw_codes.split(",") if code.strip()]


def _read_stock_pool(path: Optional[str]) -> List[str]:
    if not path:
        return []
    stock_pool_path = Path(path)
    codes: List[str] = []
    for line in stock_pool_path.read_text(encoding="utf-8").splitlines():
        code = line.strip()
        if not code or code.startswith("#"):
            continue
        codes.append(code.split(",")[0].strip())
    return codes


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    return pd.read_csv(path)


def _load_optional_csv(directory: Optional[str], code: str) -> Optional[pd.DataFrame]:
    if not directory:
        return None
    path = Path(directory) / f"{code}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def _load_price_from_csv(directory: str, code: str) -> pd.DataFrame:
    return _load_csv(Path(directory) / f"{code}.csv")


def _fetch_price_live(manager, code: str, start_date: date, end_date: date, years: int) -> Tuple[pd.DataFrame, str]:
    days = int((years + 1) * 365.25)
    df, source = manager.get_daily_data(
        code,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        days=days,
    )
    return df, source


def _get_manager():
    from data_provider.base import DataFetcherManager

    return DataFetcherManager()


def _load_inputs(
    *,
    codes: List[str],
    args: argparse.Namespace,
    start_date: date,
    end_date: date,
) -> tuple[list[BacktestInput], dict[str, str], dict[str, str]]:
    inputs: List[BacktestInput] = []
    sources: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    manager = None
    manager_error = None

    if not args.price_data_dir:
        try:
            manager = _get_manager()
        except Exception as exc:
            manager_error = f"{type(exc).__name__}: {exc}"

    for code in codes:
        try:
            if manager_error:
                raise RuntimeError(f"live data provider unavailable: {manager_error}")
            if args.price_data_dir:
                price_df = _load_price_from_csv(args.price_data_dir, code)
                sources[code] = "csv"
                stock_name = code
            else:
                price_df, source = _fetch_price_live(manager, code, start_date, end_date, args.years)
                sources[code] = source
                try:
                    stock_name = manager.get_stock_name(code, allow_realtime=False) or code
                except Exception:
                    stock_name = code
            valuation_df = _load_optional_csv(args.valuation_data_dir, code)
            financial_df = _load_optional_csv(args.financial_data_dir, code)
            inputs.append(
                BacktestInput(
                    code=code,
                    stock_name=stock_name,
                    price_df=prepare_price_frame(price_df),
                    valuation_df=valuation_df,
                    financial_df=financial_df,
                )
            )
        except Exception as exc:
            errors[code] = f"{type(exc).__name__}: {exc}"
    return inputs, sources, errors


def _load_benchmark(args: argparse.Namespace, start_date: date, end_date: date) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        if args.benchmark_file:
            return prepare_price_frame(_load_csv(Path(args.benchmark_file))), "csv"
        if args.price_data_dir:
            path = Path(args.price_data_dir) / f"{args.benchmark}.csv"
            if path.exists():
                return prepare_price_frame(_load_csv(path)), "csv"
        manager = _get_manager()
        df, source = _fetch_price_live(manager, args.benchmark, start_date, end_date, args.years)
        return prepare_price_frame(df), source
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _infer_end_date(inputs: List[BacktestInput], fallback: Optional[str]) -> date:
    if fallback:
        return coerce_date(fallback)
    max_dates = []
    for item in inputs:
        df = prepare_price_frame(item.price_df)
        if not df.empty:
            max_dates.append(max(df["date"]))
    return min(max_dates) if max_dates else date.today()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GenGe Cycle Bottom walk-forward backtest.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--codes", help="Comma-separated stock codes, e.g. 002714,000100")
    group.add_argument("--stock-pool-file", help="Text file with one stock code per line")
    parser.add_argument("--years", type=int, default=5, help="Backtest years, e.g. 5 or 10")
    parser.add_argument("--benchmark", default="000300", help="Benchmark index code")
    parser.add_argument("--output-dir", default="reports/genge_cycle_bottom", help="Report output directory")
    parser.add_argument("--start-date", help="Backtest start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Backtest end date YYYY-MM-DD")
    parser.add_argument("--step-days", type=int, default=20, help="Signal scan interval in trading rows")
    parser.add_argument("--price-data-dir", help="Optional CSV directory with <code>.csv price files")
    parser.add_argument("--benchmark-file", help="Optional benchmark CSV file")
    parser.add_argument("--valuation-data-dir", help="Optional CSV directory with valuation files")
    parser.add_argument("--financial-data-dir", help="Optional CSV directory with financial files")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    codes = _parse_codes(args.codes) + _read_stock_pool(args.stock_pool_file)
    codes = list(dict.fromkeys(codes))
    if not codes:
        parser.error("no stock codes provided")

    provisional_end = coerce_date(args.end_date) if args.end_date else date.today()
    provisional_start = coerce_date(args.start_date) if args.start_date else date_years_ago(provisional_end, args.years + 1)
    inputs, data_sources, data_errors = _load_inputs(
        codes=codes,
        args=args,
        start_date=provisional_start,
        end_date=provisional_end,
    )
    end_date = _infer_end_date(inputs, args.end_date)
    start_date = coerce_date(args.start_date) if args.start_date else date_years_ago(end_date, args.years)
    benchmark_df, benchmark_source_or_error = _load_benchmark(args, start_date, end_date)

    rows = WalkForwardBacktester().run(
        inputs=inputs,
        benchmark_df=benchmark_df,
        start_date=start_date,
        end_date=end_date,
        step_days=max(1, int(args.step_days)),
    )
    diagnostics = {
        "requested_codes": codes,
        "loaded_codes": [item.code for item in inputs],
        "data_sources": data_sources,
        "data_errors": data_errors,
        "benchmark": args.benchmark,
        "benchmark_source_or_error": benchmark_source_or_error,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "step_days": max(1, int(args.step_days)),
    }
    summary = compute_summary(rows, extra_diagnostics=diagnostics)
    report_dir = write_reports(rows, summary, args.output_dir)
    print(f"report_dir={report_dir}")
    print(f"total_signals={summary['total_signals']}")
    print(f"data_failures={len(data_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
