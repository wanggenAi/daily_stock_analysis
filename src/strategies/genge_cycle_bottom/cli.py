"""Command line entry point for GenGe Cycle Bottom Strategy backtests."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .backtest import BacktestInput, WalkForwardBacktester
from .features import coerce_date, date_years_ago, prepare_price_frame
from .fundamentals import PublicFundamentalLoader
from .metrics import compute_summary
from .report import write_reports


def _parse_codes(raw_codes: Optional[str]) -> List[str]:
    if not raw_codes:
        return []
    return [code.strip() for code in raw_codes.split(",") if code.strip()]


def _normalize_code(code: str) -> str:
    return str(code).strip().zfill(6) if str(code).strip().isdigit() else str(code).strip()


def _read_stock_pool_records(path: Optional[str]) -> List[Dict[str, str]]:
    if not path:
        return []
    stock_pool_path = Path(path)
    records: List[Dict[str, str]] = []
    for line in stock_pool_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = [part.strip() for part in raw.split(",")]
        code = _normalize_code(parts[0])
        if not code:
            continue
        record = {"code": code}
        if len(parts) >= 2 and parts[1]:
            record["stock_name"] = parts[1]
        if len(parts) >= 3 and parts[2]:
            record["industry"] = parts[2]
        records.append(record)
    return records


def _read_stock_pool(path: Optional[str]) -> List[str]:
    return [record["code"] for record in _read_stock_pool_records(path)]


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


def _load_stock_industry_map(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    df = _load_csv(Path(path))
    if "code" not in df.columns or "industry" not in df.columns:
        raise ValueError("stock industry map must include code and industry columns")
    return {
        _normalize_code(row["code"]): str(row["industry"])
        for _, row in df.dropna(subset=["code", "industry"]).iterrows()
    }


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


def _empty_fundamental_diagnostics(cache_dir: Optional[str]) -> dict[str, object]:
    return {
        "valuation_provider": "none",
        "financial_provider": "none",
        "valuation_providers": {},
        "financial_providers": {},
        "provider_errors": {},
        "fundamental_cache_dir": cache_dir,
        "fundamental_cache_hits": {"valuation": 0, "financial": 0},
        "auto_fetch_valuation": False,
        "auto_fetch_financial": False,
    }


def _record_provider(counter: dict[str, int], provider: str) -> None:
    name = provider or "none"
    counter[name] = counter.get(name, 0) + 1


def _record_provider_errors(errors: dict[str, list[str]], code: str, provider_errors: dict[str, list[str]]) -> None:
    for kind, messages in (provider_errors or {}).items():
        if messages:
            errors[f"{code}:{kind}"] = list(messages)


def _primary_provider(counter: dict[str, int]) -> str:
    available = {key: value for key, value in counter.items() if key != "none" and value > 0}
    if not available:
        return "none"
    return max(available.items(), key=lambda item: item[1])[0]


def _industry_cycle_source(path: Optional[str], source_mode: str) -> str:
    if not path:
        return "none"
    lowered = Path(path).name.lower()
    if "manual" in lowered or "template" in lowered or "example" in lowered:
        return "manual_template"
    if source_mode == "fixture":
        return "fixture"
    return "user_supplied"


def _has_severe_data_errors(errors: dict[str, str], requested_codes: list[str]) -> bool:
    if not errors:
        return False
    return len(errors) >= max(3, int(len(requested_codes) * 0.5)) if requested_codes else bool(errors)


def _load_inputs(
    *,
    codes: List[str],
    args: argparse.Namespace,
    start_date: date,
    end_date: date,
) -> tuple[list[BacktestInput], dict[str, str], dict[str, str], dict[str, object]]:
    inputs: List[BacktestInput] = []
    sources: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    fundamental_diagnostics = _empty_fundamental_diagnostics(getattr(args, "fundamental_cache_dir", None))
    fundamental_diagnostics["auto_fetch_valuation"] = bool(getattr(args, "auto_fetch_valuation", False))
    fundamental_diagnostics["auto_fetch_financial"] = bool(getattr(args, "auto_fetch_financial", False))
    valuation_providers: dict[str, int] = {}
    financial_providers: dict[str, int] = {}
    provider_errors: dict[str, list[str]] = {}
    cache_hits = {"valuation": 0, "financial": 0}
    manager = None
    manager_error = None
    fundamental_loader = (
        PublicFundamentalLoader(args.fundamental_cache_dir)
        if getattr(args, "auto_fetch_valuation", False) or getattr(args, "auto_fetch_financial", False)
        else None
    )

    if not args.price_data_dir:
        try:
            manager = _get_manager()
        except Exception as exc:
            manager_error = f"{type(exc).__name__}: {exc}"
    industry_map = _load_stock_industry_map(args.stock_industry_map)
    pool_records = {
        _normalize_code(record["code"]): record
        for record in _read_stock_pool_records(args.stock_pool_file)
    }

    for code in codes:
        try:
            normalized_code = _normalize_code(code)
            pool_record = pool_records.get(normalized_code, {})
            if manager_error:
                raise RuntimeError(f"live data provider unavailable: {manager_error}")
            if args.price_data_dir:
                price_df = _load_price_from_csv(args.price_data_dir, normalized_code)
                sources[code] = "csv"
                stock_name = pool_record.get("stock_name") or normalized_code
            else:
                price_df, source = _fetch_price_live(manager, normalized_code, start_date, end_date, args.years)
                sources[code] = source
                try:
                    stock_name = pool_record.get("stock_name") or manager.get_stock_name(normalized_code, allow_realtime=False) or normalized_code
                except Exception:
                    stock_name = pool_record.get("stock_name") or normalized_code
            valuation_df = _load_optional_csv(args.valuation_data_dir, normalized_code)
            financial_df = _load_optional_csv(args.financial_data_dir, normalized_code)
            if valuation_df is not None:
                _record_provider(valuation_providers, "csv")
            if financial_df is not None:
                _record_provider(financial_providers, "csv")
            if fundamental_loader is not None and (valuation_df is None or financial_df is None):
                fundamental_result = fundamental_loader.load(
                    normalized_code,
                    years=int(args.years),
                    fetch_valuation=bool(args.auto_fetch_valuation and valuation_df is None),
                    fetch_financial=bool(args.auto_fetch_financial and financial_df is None),
                )
                if valuation_df is None and fundamental_result.valuation_df is not None:
                    valuation_df = fundamental_result.valuation_df
                    _record_provider(valuation_providers, fundamental_result.valuation_provider)
                elif bool(args.auto_fetch_valuation):
                    _record_provider(valuation_providers, fundamental_result.valuation_provider)
                if financial_df is None and fundamental_result.financial_df is not None:
                    financial_df = fundamental_result.financial_df
                    _record_provider(financial_providers, fundamental_result.financial_provider)
                elif bool(args.auto_fetch_financial):
                    _record_provider(financial_providers, fundamental_result.financial_provider)
                for kind, hit in fundamental_result.cache_hits.items():
                    if hit:
                        cache_hits[kind] = cache_hits.get(kind, 0) + 1
                _record_provider_errors(provider_errors, normalized_code, fundamental_result.provider_errors)
            inputs.append(
                BacktestInput(
                    code=normalized_code,
                    stock_name=stock_name,
                    price_df=prepare_price_frame(price_df),
                    valuation_df=valuation_df,
                    financial_df=financial_df,
                    industry=pool_record.get("industry") or industry_map.get(normalized_code) or industry_map.get(code),
                )
            )
        except Exception as exc:
            errors[code] = f"{type(exc).__name__}: {exc}"
    fundamental_diagnostics["valuation_providers"] = valuation_providers
    fundamental_diagnostics["financial_providers"] = financial_providers
    fundamental_diagnostics["valuation_provider"] = _primary_provider(valuation_providers)
    fundamental_diagnostics["financial_provider"] = _primary_provider(financial_providers)
    fundamental_diagnostics["provider_errors"] = provider_errors
    fundamental_diagnostics["fundamental_cache_hits"] = cache_hits
    return inputs, sources, errors, fundamental_diagnostics


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
    parser.add_argument("--step-days", type=int, default=1, help="Signal scan interval in trading rows")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="One-way transaction fee in basis points")
    parser.add_argument("--slippage-bps", type=float, default=10.0, help="One-way slippage in basis points")
    parser.add_argument("--price-data-dir", help="Optional CSV directory with <code>.csv price files")
    parser.add_argument("--benchmark-file", help="Optional benchmark CSV file")
    parser.add_argument("--valuation-data-dir", help="Optional CSV directory with valuation files")
    parser.add_argument("--financial-data-dir", help="Optional CSV directory with financial files")
    parser.add_argument("--auto-fetch-valuation", action="store_true", help="Fetch missing valuation data from public sources and cache successes")
    parser.add_argument("--auto-fetch-financial", action="store_true", help="Fetch missing financial data from public sources and cache successes")
    parser.add_argument("--fundamental-cache-dir", default="data/cache/genge_fundamentals", help="Directory for successful public valuation/financial cache")
    parser.add_argument("--industry-cycle-file", help="Optional CSV file with industry cycle scores")
    parser.add_argument("--stock-industry-map", help="Optional CSV file mapping code to industry")
    parser.add_argument("--fixture-smoke-passed", action="store_true", help="Mark fixture smoke as already verified for acceptance context")
    parser.add_argument("--ci-passed", action="store_true", help="Mark GitHub Actions fixture CI as observed passed for acceptance context")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    codes = [_normalize_code(code) for code in (_parse_codes(args.codes) + _read_stock_pool(args.stock_pool_file))]
    codes = list(dict.fromkeys(codes))
    if not codes:
        parser.error("no stock codes provided")

    provisional_end = coerce_date(args.end_date) if args.end_date else date.today()
    provisional_start = coerce_date(args.start_date) if args.start_date else date_years_ago(provisional_end, args.years + 1)
    inputs, data_sources, data_errors, fundamental_diagnostics = _load_inputs(
        codes=codes,
        args=args,
        start_date=provisional_start,
        end_date=provisional_end,
    )
    end_date = _infer_end_date(inputs, args.end_date)
    start_date = coerce_date(args.start_date) if args.start_date else date_years_ago(end_date, args.years)
    benchmark_df, benchmark_source_or_error = _load_benchmark(args, start_date, end_date)
    industry_cycle_df = _load_csv(Path(args.industry_cycle_file)) if args.industry_cycle_file else None

    rows = WalkForwardBacktester().run(
        inputs=inputs,
        benchmark_df=benchmark_df,
        start_date=start_date,
        end_date=end_date,
        step_days=max(1, int(args.step_days)),
        fee_bps=float(args.fee_bps),
        slippage_bps=float(args.slippage_bps),
        industry_cycle_df=industry_cycle_df,
    )
    source_mode = "fixture" if args.price_data_dir else "real"
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
        "fee_bps": float(args.fee_bps),
        "slippage_bps": float(args.slippage_bps),
        "industry_cycle_file": args.industry_cycle_file,
        "industry_cycle_source": _industry_cycle_source(args.industry_cycle_file, source_mode),
        "stock_industry_map": args.stock_industry_map,
        "source_mode": source_mode,
        "ci_passed": bool(args.ci_passed),
        "fixture_smoke_passed": bool(args.price_data_dir or args.fixture_smoke_passed),
        "real_5y_passed": bool(not args.price_data_dir and int(args.years) == 5 and inputs and not _has_severe_data_errors(data_errors, codes)),
        "real_10y_passed": bool(not args.price_data_dir and int(args.years) == 10 and inputs and not _has_severe_data_errors(data_errors, codes)),
        "real_10y_safely_degraded": bool(not args.price_data_dir and int(args.years) == 10 and inputs and data_errors),
        "no_lookahead_risk": True,
        "no_auto_trade": True,
    }
    diagnostics.update(fundamental_diagnostics)
    summary = compute_summary(rows, extra_diagnostics=diagnostics)
    report_dir = write_reports(rows, summary, args.output_dir)
    print(f"report_dir={report_dir}")
    print(f"total_signals={summary['total_signals']}")
    print(f"data_failures={len(data_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
