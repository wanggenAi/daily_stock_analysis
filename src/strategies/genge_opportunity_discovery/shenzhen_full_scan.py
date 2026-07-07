"""Shenzhen mainboard A-share full-universe opportunity scan.

This module is a production runner for a specific daily research job. It keeps
the universe build, low-cost quant screen, focused evidence review, and
next-day conditional price plan in one reproducible command. It never connects
to broker systems or produces orders.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame
from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_cycle_bottom.industry_evidence import load_evidence_csv, load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery.exit_profile import load_exit_profile_distribution
from src.strategies.genge_opportunity_discovery.pipeline import run_opportunity_discovery


DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入建议，不应自动交易。"
SZSE_LIST_URL = "https://www.szse.cn/api/report/ShowReport"
MIN_HISTORY_ROWS = 800
MIN_AVG_TURNOVER_20D = 20_000_000.0
TRADING_DAYS_1Y = 250
TRADING_DAYS_5Y = 1250
EVIDENCE_ORDER = {
    "VERIFIED": 100.0,
    "PARTIALLY_VERIFIED": 70.0,
    "LEAD_ONLY": 35.0,
    "STALE": 25.0,
    "MISSING": 0.0,
    "CONFLICTING": 0.0,
    "PARSE_FAILED": 0.0,
}
TREND_ORDER = {"NONE": 0.0, "WEAK": 35.0, "MEDIUM": 70.0, "STRONG": 100.0}
EXIT_ORDER = {"PASSED": 100.0, "DEGRADED": 45.0, "NOT_AVAILABLE": 20.0, "FAILED": 0.0}
HARD_LOGIC_ORDER = {"NONE": 0.0, "WEAK": 35.0, "MEDIUM": 70.0, "STRONG": 100.0}


UNIVERSE_COLUMNS = [
    "code",
    "stock_name",
    "exchange",
    "board",
    "security_type",
    "listing_status",
    "listing_date",
    "is_st",
    "is_suspended",
    "latest_trade_date",
    "latest_close",
    "avg_turnover_20d",
    "industry",
    "universe_source",
    "exclusion_reason",
]

QUANT_COLUMNS = [
    "quant_rank",
    "code",
    "stock_name",
    "industry",
    "latest_trade_date",
    "latest_close",
    "price_percentile_5y",
    "price_percentile_1y",
    "distance_from_52w_low_pct",
    "ma20",
    "ma60",
    "ma120",
    "ma250",
    "ma20_slope_pct",
    "ma60_slope_pct",
    "trend_confirmation_level",
    "atr14",
    "relative_strength_20d",
    "relative_strength_60d",
    "avg_turnover_20d",
    "quant_score",
    "quant_status",
    "hard_blockers",
    "soft_blockers",
    "rejection_reasons",
]

PLAN_COLUMNS = [
    "actionability_rank",
    "quant_rank",
    "proximity_rank",
    "code",
    "stock_name",
    "industry",
    "classification",
    "tomorrow_status",
    "tier",
    "actionability_score",
    "latest_trade_date",
    "latest_close",
    "price_percentile_5y",
    "pullback_entry_low",
    "pullback_entry_high",
    "pullback_stop_price",
    "pullback_logic_invalidation_price",
    "pullback_target_1",
    "pullback_target_2",
    "pullback_real_reward_risk",
    "pullback_status",
    "breakout_trigger_price",
    "breakout_required_volume",
    "breakout_max_chase_price",
    "breakout_stop_price",
    "breakout_logic_invalidation_price",
    "breakout_target_1",
    "breakout_target_2",
    "breakout_real_reward_risk",
    "breakout_status",
    "theoretical_target_1",
    "theoretical_target_2",
    "real_resistance_target_1",
    "real_resistance_target_2",
    "real_reward_risk_ratio",
    "preferred_plan",
    "pullback_initial_position_pct",
    "pullback_max_position_pct",
    "breakout_initial_position_pct",
    "breakout_max_position_pct",
    "max_loss_pct_of_risk_capital",
    "industry_evidence_status",
    "company_evidence_status",
    "exit_profile_status",
    "hard_logic_level",
    "main_logic",
    "top_risks",
    "missing_conditions",
    "upgrade_conditions",
    "cancel_conditions",
    "evidence_urls",
    "data_warnings",
    "disclaimer",
]


@dataclass
class ScanConfig:
    as_of: date
    tomorrow: date
    output_dir: Path
    stock_pool_output: Path
    max_workers: int = 12
    evidence_queue_size: int = 80
    deep_review_size: int = 30
    max_watchlist: int = 12
    buy_ready_limit: int = 3
    near_ready_limit: int = 5
    deep_watch_limit: int = 4
    liquidity_threshold: float = MIN_AVG_TURNOVER_20D
    cache_dir: Path = Path("data/cache/shenzhen_full_scan")
    opportunity_cache_dir: Path = Path("data/cache/opportunity_evidence")
    fundamental_cache_dir: Path = Path("data/cache/genge_fundamentals")
    auto_fetch_fundamentals: bool = True
    fundamental_limit: int = 30


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _safe_float(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 4) -> Any:
    number = _safe_float(value)
    return "" if number is None else round(number, digits)


def _round_price(value: Any) -> Any:
    number = _safe_float(value)
    return "" if number is None or number <= 0 else round(number, 2)


def _percentile(series: pd.Series, current: float) -> float | None:
    local = pd.to_numeric(series, errors="coerce").dropna()
    if local.empty:
        return None
    return float((local <= current).sum() / len(local))


def _status_from_score(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "UNKNOWN"
    if number >= 60:
        return "PASSED"
    if number >= 40:
        return "DEGRADED"
    return "FAILED"


def fetch_szse_listing() -> pd.DataFrame:
    params = {"SHOWTYPE": "xlsx", "CATALOGID": "1110", "TABKEY": "tab1", "random": str(time.time())}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
    }
    response = requests.get(SZSE_LIST_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return pd.read_excel(io.BytesIO(response.content))


def build_official_universe(raw_df: pd.DataFrame, *, as_of: date) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = {
        "raw_security_count": int(len(raw_df)),
        "excluded_chinext_count": 0,
        "excluded_st_or_delist_count": 0,
        "excluded_listing_after_as_of_count": 0,
    }
    for _, item in raw_df.iterrows():
        board = str(item.get("板块") or "").strip()
        code = _normalize_code(item.get("A股代码"))
        name = str(item.get("A股简称") or "").strip()
        listing_date = pd.to_datetime(item.get("A股上市日期"), errors="coerce")
        if board == "创业板":
            counts["excluded_chinext_count"] += 1
        if not code or code.lower() == "nan":
            continue
        if board != "主板":
            continue
        is_st = "ST" in name.upper()
        is_delist = "退" in name or "退市" in name
        listing_status = "delisting_risk" if is_delist else "listed"
        exclusion = ""
        if is_st or is_delist:
            exclusion = "st_or_delisting_risk"
            counts["excluded_st_or_delist_count"] += 1
        if pd.notna(listing_date) and listing_date.date() > as_of:
            exclusion = "listing_after_as_of"
            counts["excluded_listing_after_as_of_count"] += 1
        rows.append(
            {
                "code": code,
                "stock_name": name,
                "exchange": "SZSE",
                "board": board,
                "security_type": "A_SHARE",
                "listing_status": listing_status,
                "listing_date": listing_date.date().isoformat() if pd.notna(listing_date) else "",
                "is_st": bool(is_st),
                "is_suspended": "",
                "latest_trade_date": "",
                "latest_close": "",
                "avg_turnover_20d": "",
                "industry": str(item.get("所属行业") or "").strip(),
                "universe_source": "SZSE ShowReport CATALOGID=1110 TABKEY=tab1",
                "exclusion_reason": exclusion,
            }
        )
    counts["shenzhen_mainboard_a_count"] = len(rows)
    return rows, counts


def _tencent_symbol(code: str) -> str:
    return f"sz{_normalize_code(code)}"


def fetch_unadjusted_history(code: str, *, as_of: date, timeout: int = 12) -> pd.DataFrame:
    symbol = _tencent_symbol(code)
    response = requests.get(
        "https://web.ifzq.gtimg.cn/appstock/app/kline/kline",
        params={"param": f"{symbol},day,,{as_of:%Y-%m-%d},2000"},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = (((payload.get("data") or {}).get(symbol) or {}).get("day") or [])
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        close = _safe_float(row[2])
        volume_lots = _safe_float(row[5])
        parsed.append(
            {
                "date": row[0],
                "open": _safe_float(row[1]),
                "close": close,
                "high": _safe_float(row[3]),
                "low": _safe_float(row[4]),
                "volume": volume_lots,
                "amount": (close or 0.0) * (volume_lots or 0.0) * 100.0,
            }
        )
    frame = pd.DataFrame(parsed)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _cache_path(config: ScanConfig, code: str) -> Path:
    return config.cache_dir / "kline" / f"{_normalize_code(code)}.csv"


def load_or_fetch_history(code: str, config: ScanConfig) -> tuple[str, pd.DataFrame, str]:
    path = _cache_path(config, code)
    if path.exists():
        try:
            cached = prepare_price_frame(pd.read_csv(path))
            if not cached.empty and cached["date"].max() >= config.as_of:
                return code, cached[cached["date"] <= config.as_of].copy(), "cache"
        except Exception:
            pass
    frame = fetch_unadjusted_history(code, as_of=config.as_of)
    if not frame.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    return code, frame, "tencent_unadjusted"


def fetch_histories(rows: list[dict[str, Any]], config: ScanConfig) -> tuple[dict[str, pd.DataFrame], dict[str, str], dict[str, str]]:
    histories: dict[str, pd.DataFrame] = {}
    sources: dict[str, str] = {}
    errors: dict[str, str] = {}
    candidates = [row for row in rows if not row.get("exclusion_reason")]
    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        future_map = {executor.submit(load_or_fetch_history, str(row["code"]), config): row for row in candidates}
        for future in as_completed(future_map):
            code = str(future_map[future]["code"])
            try:
                result_code, frame, source = future.result()
                histories[result_code] = prepare_price_frame(frame) if frame is not None and not frame.empty else pd.DataFrame()
                sources[result_code] = source
            except Exception as exc:
                histories[code] = pd.DataFrame()
                sources[code] = "failed"
                errors[code] = f"{type(exc).__name__}: {exc}"
    return histories, sources, errors


def enrich_universe_with_history(
    rows: list[dict[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    errors: Mapping[str, str],
    config: ScanConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    audit: list[dict[str, Any]] = []
    counts = {
        "excluded_suspended_count": 0,
        "excluded_insufficient_history_count": 0,
        "excluded_insufficient_liquidity_count": 0,
        "data_fetch_failure_count": 0,
        "effective_scan_count": 0,
    }
    enriched: list[dict[str, Any]] = []
    for row in rows:
        local = dict(row)
        code = str(local["code"])
        reason = str(local.get("exclusion_reason") or "")
        history = prepare_price_frame(histories.get(code, pd.DataFrame()))
        if code in errors and not reason:
            reason = "price_fetch_failed"
            counts["data_fetch_failure_count"] += 1
        if not history.empty:
            history = history[history["date"] <= config.as_of].copy()
            latest = history.iloc[-1] if not history.empty else None
            if latest is not None:
                local["latest_trade_date"] = latest["date"].isoformat()
                local["latest_close"] = _round_price(latest.get("close"))
                local["avg_turnover_20d"] = _round(float(pd.to_numeric(history.tail(20)["amount"], errors="coerce").mean()), 2)
        if not reason:
            latest_date = coerce_date(local["latest_trade_date"]) if local.get("latest_trade_date") else None
            if latest_date != config.as_of:
                reason = "suspended_or_no_latest_trade"
                local["is_suspended"] = True
                counts["excluded_suspended_count"] += 1
            elif len(history) < MIN_HISTORY_ROWS:
                reason = "insufficient_history"
                counts["excluded_insufficient_history_count"] += 1
            elif (_safe_float(local.get("avg_turnover_20d")) or 0.0) < config.liquidity_threshold:
                reason = "insufficient_liquidity"
                counts["excluded_insufficient_liquidity_count"] += 1
            else:
                counts["effective_scan_count"] += 1
                local["is_suspended"] = False
        local["exclusion_reason"] = reason
        if reason:
            audit.append(
                {
                    "code": code,
                    "stock_name": local.get("stock_name"),
                    "stage": "universe_filter",
                    "reason": reason,
                    "detail": errors.get(code, ""),
                }
            )
        enriched.append(local)
    return enriched, audit, counts


def _ma(history: pd.DataFrame, days: int) -> float | None:
    if len(history) < days:
        return None
    return float(pd.to_numeric(history["close"], errors="coerce").tail(days).mean())


def _slope(history: pd.DataFrame, days: int) -> float | None:
    if len(history) < days + 5:
        return None
    ma_now = _ma(history, days)
    ma_prev = float(pd.to_numeric(history["close"], errors="coerce").iloc[-days - 5 : -5].mean())
    if ma_now is None or not ma_prev:
        return None
    return (ma_now / ma_prev - 1.0) * 100.0


def _atr(history: pd.DataFrame, days: int = 14) -> float | None:
    if len(history) < days + 1:
        return None
    high = pd.to_numeric(history["high"], errors="coerce")
    low = pd.to_numeric(history["low"], errors="coerce")
    close = pd.to_numeric(history["close"], errors="coerce")
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    value = float(tr.tail(days).mean())
    return value if math.isfinite(value) and value > 0 else None


def _relative_strength(history: pd.DataFrame, benchmark: pd.DataFrame, days: int) -> float | None:
    if history.empty or benchmark.empty or len(history) <= days or len(benchmark) <= days:
        return None
    left = history.tail(days + 1)
    right = benchmark[benchmark["date"].isin(left["date"])]
    if len(right) < max(5, days // 2):
        return None
    stock_start = _safe_float(left.iloc[0].get("close"))
    stock_end = _safe_float(left.iloc[-1].get("close"))
    bench_start = _safe_float(right.iloc[0].get("close"))
    bench_end = _safe_float(right.iloc[-1].get("close"))
    if not stock_start or not bench_start or stock_end is None or bench_end is None:
        return None
    return ((stock_end / stock_start - 1.0) - (bench_end / bench_start - 1.0)) * 100.0


def quant_screen(
    universe_rows: list[dict[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    config: ScanConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    effective = [row for row in universe_rows if not row.get("exclusion_reason")]
    for item in effective:
        code = str(item["code"])
        history = prepare_price_frame(histories.get(code, pd.DataFrame()))
        if history.empty:
            continue
        history = history[history["date"] <= config.as_of].copy().reset_index(drop=True)
        close = float(history.iloc[-1]["close"])
        closes = pd.to_numeric(history["close"], errors="coerce")
        one_year = history.tail(TRADING_DAYS_1Y)
        five_year = history.tail(TRADING_DAYS_5Y)
        percentile_1y = _percentile(one_year["close"], close)
        percentile_5y = _percentile(five_year["close"], close)
        low_52w = float(pd.to_numeric(one_year["close"], errors="coerce").min())
        ma20 = _ma(history, 20)
        ma60 = _ma(history, 60)
        ma120 = _ma(history, 120)
        ma250 = _ma(history, 250)
        ma20_slope = _slope(history, 20)
        ma60_slope = _slope(history, 60)
        atr14 = _atr(history)
        rs20 = _relative_strength(history, benchmark, 20)
        rs60 = _relative_strength(history, benchmark, 60)
        avg_turnover = _safe_float(item.get("avg_turnover_20d")) or 0.0
        hard: list[str] = []
        soft: list[str] = []
        if percentile_5y is not None and percentile_5y > 0.75:
            hard.append("price_too_high")
        if avg_turnover < config.liquidity_threshold:
            hard.append("insufficient_liquidity")
        if ma250 and close < ma250 * 0.82 and (ma20_slope or 0) < 0:
            soft.append("falling_knife")
        if ma20 and close >= ma20 and (ma20_slope or 0) >= -0.2:
            trend = "WEAK"
            if ma60 and close >= ma60 and (ma60_slope or 0) >= -0.2:
                trend = "MEDIUM"
            if ma60 and ma120 and close >= ma60 and ma20 >= ma60 and ma60 >= ma120 and (ma60_slope or 0) > 0:
                trend = "STRONG"
        else:
            trend = "NONE"
            soft.append("trend_unconfirmed")
        price_score = 90.0 if (percentile_5y or 1) <= 0.2 else 75.0 if (percentile_5y or 1) <= 0.35 else 55.0 if (percentile_5y or 1) <= 0.5 else 35.0 if (percentile_5y or 1) <= 0.65 else 15.0
        trend_score = TREND_ORDER[trend]
        liquidity_score = min(100.0, math.log10(max(avg_turnover, 1.0) / config.liquidity_threshold + 1.0) * 70.0)
        relative_score = 50.0
        relative_inputs = [v for v in (rs20, rs60) if v is not None]
        if relative_inputs:
            relative_score = max(0.0, min(100.0, 50.0 + sum(relative_inputs) / len(relative_inputs) * 2.0))
        quant_score = round(price_score * 0.34 + trend_score * 0.28 + liquidity_score * 0.18 + relative_score * 0.10 + 50.0 * 0.10, 4)
        if hard:
            status = "HARD_REJECT"
        elif quant_score >= 58 and "falling_knife" not in soft:
            status = "PRIORITY_RESEARCH"
        elif quant_score >= 45:
            status = "SECONDARY_RESEARCH"
        else:
            status = "LOW_PRIORITY"
        rows.append(
            {
                "code": code,
                "stock_name": item.get("stock_name"),
                "industry": item.get("industry"),
                "latest_trade_date": item.get("latest_trade_date"),
                "latest_close": _round_price(close),
                "price_percentile_5y": _round(percentile_5y),
                "price_percentile_1y": _round(percentile_1y),
                "distance_from_52w_low_pct": _round((close / low_52w - 1.0) * 100.0 if low_52w else None),
                "ma20": _round_price(ma20),
                "ma60": _round_price(ma60),
                "ma120": _round_price(ma120),
                "ma250": _round_price(ma250),
                "ma20_slope_pct": _round(ma20_slope),
                "ma60_slope_pct": _round(ma60_slope),
                "trend_confirmation_level": trend,
                "atr14": _round_price(atr14),
                "relative_strength_20d": _round(rs20),
                "relative_strength_60d": _round(rs60),
                "avg_turnover_20d": _round(avg_turnover, 2),
                "quant_score": quant_score,
                "quant_status": status,
                "hard_blockers": ";".join(hard),
                "soft_blockers": ";".join(sorted(set(soft))),
                "rejection_reasons": ";".join(sorted(set(hard + soft))),
            }
        )
    rows.sort(key=lambda row: (_safe_float(row.get("quant_score")) or 0.0), reverse=True)
    for index, row in enumerate(rows, 1):
        row["quant_rank"] = index
    return rows


def _load_exit_profiles(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def _fundamentals_for_top(rows: list[dict[str, Any]], config: ScanConfig) -> dict[str, tuple[pd.DataFrame | None, pd.DataFrame | None]]:
    result: dict[str, tuple[pd.DataFrame | None, pd.DataFrame | None]] = {}
    if not config.auto_fetch_fundamentals:
        return result
    loader = PublicFundamentalLoader(config.fundamental_cache_dir)
    for row in rows[: max(0, int(config.fundamental_limit))]:
        code = str(row["code"])
        fetched = loader.load(code, years=5, fetch_valuation=True, fetch_financial=True)
        result[code] = (fetched.valuation_df, fetched.financial_df)
    return result


def run_deep_opportunity_review(
    *,
    quant_rows: list[dict[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    config: ScanConfig,
    industry_evidence_file: str,
    company_evidence_file: str,
    industry_evidence_schema_file: str,
    industry_alias_map_file: str,
    exit_profile_file: str,
) -> tuple[Path, dict[str, Any]]:
    top80 = [row for row in quant_rows if row.get("quant_status") in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}][: config.evidence_queue_size]
    fundamentals = _fundamentals_for_top(top80, config)
    inputs: list[BacktestInput] = []
    for row in top80:
        code = str(row["code"])
        valuation_df, financial_df = fundamentals.get(code, (None, None))
        inputs.append(
            BacktestInput(
                code=code,
                stock_name=str(row.get("stock_name") or code),
                industry=str(row.get("industry") or ""),
                price_df=histories[code],
                valuation_df=valuation_df,
                financial_df=financial_df,
            )
        )
    benchmark = fetch_unadjusted_history("399001", as_of=config.as_of) if top80 else pd.DataFrame()
    report_dir, summary = run_opportunity_discovery(
        inputs=inputs,
        requested_codes=[item.code for item in inputs],
        data_errors={},
        data_sources={item.code: "shenzhen_full_scan_tencent_unadjusted" for item in inputs},
        benchmark_df=benchmark,
        industry_cycle_df=None,
        industry_evidence_df=load_evidence_csv(industry_evidence_file),
        company_evidence_df=load_evidence_csv(company_evidence_file),
        industry_evidence_schema=load_industry_evidence_schema(industry_evidence_schema_file),
        industry_alias_map=load_industry_alias_map(industry_alias_map_file),
        requested_as_of_date=config.as_of.isoformat(),
        output_dir=config.output_dir / "_opportunity_deep_review",
        diagnostics={
            "source_mode": "real_shenzhen_full_scan",
            "requested_codes": [item.code for item in inputs],
            "industry_evidence_file": industry_evidence_file,
            "company_evidence_file": company_evidence_file,
            "exit_profile_file": exit_profile_file,
            "no_auto_trade": True,
            "no_broker_integration": True,
        },
        priority_queue_size=config.evidence_queue_size,
        secondary_queue_size=config.evidence_queue_size,
        exit_profile_df=_load_exit_profiles(Path(exit_profile_file)),
        ledger_path=config.output_dir / "forward_observation_ledger.csv",
        run_mode="full",
        evidence_cache_dir=config.opportunity_cache_dir,
        auto_evidence_limit=min(50, config.evidence_queue_size),
        state_dir=config.output_dir / "state",
    )
    return report_dir, summary


def _evidence_urls(evidence_rows: Iterable[Mapping[str, Any]], row: Mapping[str, Any]) -> list[str]:
    code = _normalize_code(row.get("code"))
    industry = str(row.get("normalized_industry") or row.get("industry") or "")
    urls: list[str] = []
    for evidence in evidence_rows:
        scope = str(evidence.get("scope") or "")
        evidence_code = _normalize_code(evidence.get("code")) if evidence.get("code") else ""
        evidence_industry = str(evidence.get("industry") or "")
        if (scope == "company" and evidence_code == code) or (scope == "industry" and evidence_industry == industry):
            url = str(evidence.get("original_url") or evidence.get("source") or "").strip()
            if url.startswith(("http://", "https://")):
                urls.append(url)
    return list(dict.fromkeys(urls))


def _cluster_levels(values: list[float], tolerance: float) -> list[tuple[float, int]]:
    levels: list[list[float]] = []
    for value in sorted(v for v in values if v > 0):
        for group in levels:
            center = sum(group) / len(group)
            if abs(value - center) <= tolerance:
                group.append(value)
                break
        else:
            levels.append([value])
    return [(sum(group) / len(group), len(group)) for group in levels]


def _support_candidates(history: pd.DataFrame, atr14: float, close: float) -> list[tuple[float, int, str]]:
    recent = history.tail(120)
    lows = pd.to_numeric(recent["low"], errors="coerce").dropna().tolist()
    tolerance = max(atr14 * 0.45, close * 0.015)
    candidates = [(level, touches, "low_cluster") for level, touches in _cluster_levels(lows, tolerance) if touches >= 2 and level <= close * 1.02]
    for days in (20, 60):
        ma = _ma(history, days)
        if ma and ma <= close * 1.02:
            touches = int((pd.to_numeric(recent["low"], errors="coerce").sub(ma).abs() <= tolerance).sum())
            if touches >= 2:
                candidates.append((ma, touches, f"ma{days}_verified"))
    candidates.sort(key=lambda item: (abs(close - item[0]), -item[1]))
    return candidates


def _resistance_levels(history: pd.DataFrame, atr14: float, entry: float) -> list[tuple[float, str]]:
    levels: list[tuple[float, str]] = []
    for days in (20, 60, 120, 250):
        if len(history) >= days:
            high = float(pd.to_numeric(history["high"], errors="coerce").tail(days).max())
            if high > entry * 1.005:
                levels.append((high, f"{days}d_high"))
    clusters = _cluster_levels(pd.to_numeric(history.tail(250)["high"], errors="coerce").dropna().tolist(), max(atr14 * 0.5, entry * 0.015))
    for level, touches in clusters:
        if touches >= 2 and level > entry * 1.005:
            levels.append((level, "high_cluster"))
    unique: dict[float, str] = {}
    for value, label in sorted(levels):
        rounded = round(value, 2)
        unique.setdefault(rounded, label)
    return [(price, label) for price, label in sorted(unique.items())]


def _position_pct(entry: float, stop: float, *, enabled: bool) -> tuple[float, float]:
    if not enabled or entry <= 0 or stop <= 0 or stop >= entry:
        return 0.0, 0.0
    stop_distance_pct = (entry - stop) / entry * 100.0
    if stop_distance_pct <= 0:
        return 0.0, 0.0
    initial = min(5.0, 0.5 / stop_distance_pct * 100.0)
    maximum = min(8.0, initial * 1.6)
    return round(initial, 2), round(maximum, 2)


def build_price_plan(row: Mapping[str, Any], history: pd.DataFrame, evidence_urls: list[str]) -> dict[str, Any]:
    history = prepare_price_frame(history)
    close = float(history.iloc[-1]["close"])
    latest_date = coerce_date(history.iloc[-1]["date"])
    atr14 = _atr(history) or max(0.01, close * 0.03)
    avg_volume_20 = float(pd.to_numeric(history.tail(20)["volume"], errors="coerce").mean())
    supports = _support_candidates(history, atr14, close)
    support = supports[0][0] if supports else None
    pullback_status = "NO_CONFIRMED_SUPPORT"
    pullback: dict[str, Any] = {
        "pullback_entry_low": "",
        "pullback_entry_high": "",
        "pullback_stop_price": "",
        "pullback_logic_invalidation_price": "",
        "pullback_target_1": "",
        "pullback_target_2": "",
        "pullback_real_reward_risk": "",
        "pullback_status": pullback_status,
    }
    real_rr_values: list[float] = []
    if support:
        entry_low = max(0.01, support - 0.30 * atr14)
        entry_high = min(close, support + 0.20 * atr14)
        if entry_low > entry_high:
            pullback["pullback_status"] = "NO_VALID_PULLBACK_ZONE"
        else:
            stop = min(entry_low - 0.01, support - 0.75 * atr14)
            logic = min(stop, support - 1.05 * atr14)
            targets = [value for value, _label in _resistance_levels(history, atr14, entry_high) if value > entry_high]
            target1 = targets[0] if targets else None
            target2 = targets[1] if len(targets) > 1 else None
            if target1 and stop < entry_high:
                rr = (target1 - entry_high) / (entry_high - stop)
                real_rr_values.append(rr)
                pullback_status = "READY" if rr >= 1.8 else "REAL_RR_BELOW_1_8"
                pullback.update(
                    {
                        "pullback_entry_low": _round_price(entry_low),
                        "pullback_entry_high": _round_price(entry_high),
                        "pullback_stop_price": _round_price(stop),
                        "pullback_logic_invalidation_price": _round_price(logic),
                        "pullback_target_1": _round_price(target1),
                        "pullback_target_2": _round_price(target2 or (entry_high + 2.5 * (entry_high - stop))),
                        "pullback_real_reward_risk": round(rr, 2),
                        "pullback_status": pullback_status,
                    }
                )
            else:
                pullback["pullback_status"] = "NO_REAL_RESISTANCE_TARGET"
    resistance_20 = float(pd.to_numeric(history.tail(20)["high"], errors="coerce").max())
    breakout = resistance_20 + 0.10 * atr14
    breakout_stop = breakout - max(1.20 * atr14, breakout * 0.025)
    breakout_logic = min(breakout_stop, resistance_20 - 0.30 * atr14)
    breakout_targets = [value for value, _label in _resistance_levels(history, atr14, breakout) if value > breakout * 1.005]
    breakout_t1 = breakout_targets[0] if breakout_targets else None
    breakout_t2 = breakout_targets[1] if len(breakout_targets) > 1 else None
    breakout_rr = ""
    breakout_status = "NO_REAL_RESISTANCE_TARGET"
    if breakout_t1 and breakout_stop < breakout:
        breakout_rr_float = (breakout_t1 - breakout) / (breakout - breakout_stop)
        breakout_rr = round(breakout_rr_float, 2)
        real_rr_values.append(breakout_rr_float)
        breakout_status = "READY" if breakout_rr_float >= 1.8 else "REAL_RR_BELOW_1_8"
    real_target_1 = breakout_t1 or (pullback.get("pullback_target_1") if pullback.get("pullback_target_1") else "")
    real_target_2 = breakout_t2 or (pullback.get("pullback_target_2") if pullback.get("pullback_target_2") else "")
    theoretical_target_1 = breakout + 1.5 * (breakout - breakout_stop)
    theoretical_target_2 = breakout + 2.5 * (breakout - breakout_stop)
    best_rr = max(real_rr_values) if real_rr_values else None
    return {
        "latest_trade_date": latest_date.isoformat(),
        "latest_close": _round_price(close),
        **pullback,
        "breakout_trigger_price": _round_price(breakout),
        "breakout_required_volume": round(avg_volume_20 * 1.2, 0),
        "breakout_max_chase_price": _round_price(breakout * 1.015),
        "breakout_stop_price": _round_price(breakout_stop),
        "breakout_logic_invalidation_price": _round_price(breakout_logic),
        "breakout_target_1": _round_price(breakout_t1),
        "breakout_target_2": _round_price(breakout_t2 or theoretical_target_2),
        "breakout_real_reward_risk": breakout_rr,
        "breakout_status": breakout_status,
        "theoretical_target_1": _round_price(theoretical_target_1),
        "theoretical_target_2": _round_price(theoretical_target_2),
        "real_resistance_target_1": _round_price(real_target_1),
        "real_resistance_target_2": _round_price(real_target_2),
        "real_reward_risk_ratio": round(best_rr, 2) if best_rr is not None else "",
        "preferred_plan": "breakout" if (breakout_rr or 0) and (not pullback.get("pullback_real_reward_risk") or float(breakout_rr) >= float(pullback.get("pullback_real_reward_risk") or 0)) else "pullback",
        "cancel_conditions": "高开超过最高追价；低开跌破对应止损；新增重大负面公告；行业或公司证据被证伪；停牌或流动性异常；价格数据不一致",
        "evidence_urls": ";".join(evidence_urls),
    }


def actionability_score(row: Mapping[str, Any], plan: Mapping[str, Any]) -> float:
    quant = _safe_float(row.get("quant_score") or row.get("opportunity_quality_score")) or 0.0
    trend = TREND_ORDER.get(str(row.get("trend_confirmation_level") or "NONE"), 0.0)
    percentile = _safe_float(row.get("price_percentile_5y"))
    price_score = 50.0 if percentile is None else max(0.0, min(100.0, (1.0 - percentile) * 100.0))
    industry = EVIDENCE_ORDER.get(str(row.get("industry_evidence_status") or "MISSING"), 0.0)
    company = EVIDENCE_ORDER.get(str(row.get("company_evidence_status") or "MISSING"), 0.0)
    exit_score = EXIT_ORDER.get(str(row.get("balanced_exit_historical_profile") or "NOT_AVAILABLE"), 0.0)
    liquidity = min(100.0, max(0.0, (_safe_float(row.get("execution_risk_score")) or 0.0)))
    liquidity = 100.0 - liquidity
    rr = _safe_float(plan.get("real_reward_risk_ratio"))
    rr_score = 0.0 if rr is None else max(0.0, min(100.0, rr / 2.5 * 100.0))
    score = quant * 0.25 + trend * 0.15 + price_score * 0.10 + industry * 0.10 + company * 0.15 + exit_score * 0.10 + liquidity * 0.05 + rr_score * 0.10
    return round(score, 4)


def classify_candidate(row: Mapping[str, Any], plan: Mapping[str, Any], evidence_urls: list[str], counts: Counter[str]) -> tuple[str, str]:
    hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    industry_status = str(row.get("industry_evidence_status") or "MISSING")
    company_status = str(row.get("company_evidence_status") or "MISSING")
    exit_profile = str(row.get("balanced_exit_historical_profile") or "NOT_AVAILABLE")
    hard_logic = str(row.get("hard_logic_level") or "NONE")
    trend = str(row.get("trend_confirmation_level") or "NONE")
    financial = _status_from_score(row.get("financial_safety_score"))
    failed = [item for item in str(row.get("a_condition_failed") or "").split(";") if item]
    real_rr = _safe_float(plan.get("real_reward_risk_ratio")) or 0.0
    has_ready_plan = plan.get("pullback_status") == "READY" or plan.get("breakout_status") == "READY"
    buy_ready = (
        not hard
        and financial == "PASSED"
        and industry_status in {"VERIFIED", "PARTIALLY_VERIFIED"}
        and company_status in {"VERIFIED", "PARTIALLY_VERIFIED"}
        and exit_profile == "PASSED"
        and hard_logic in {"MEDIUM", "STRONG"}
        and trend in {"MEDIUM", "STRONG"}
        and real_rr >= 1.8
        and has_ready_plan
        and bool(evidence_urls)
    )
    if buy_ready and counts["BUY_READY"] < 3:
        counts["BUY_READY"] += 1
        return "BUY_READY", "BUY_READY"
    if not hard and len(failed) <= 2 and counts["NEAR_READY"] < 5:
        counts["NEAR_READY"] += 1
        if plan.get("breakout_status") == "READY" or plan.get("breakout_status") == "REAL_RR_BELOW_1_8":
            return "NEAR_READY", "WAIT_FOR_BREAKOUT"
        return "NEAR_READY", "WAIT_FOR_PULLBACK"
    if not hard and counts["DEEP_WATCH"] < 4:
        counts["DEEP_WATCH"] += 1
        return "DEEP_WATCH", "WATCH_ONLY"
    return "", ""


def build_final_watchlist(
    *,
    opportunity_report_dir: Path,
    quant_by_code: Mapping[str, Mapping[str, Any]],
    histories: Mapping[str, pd.DataFrame],
    config: ScanConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    payload = json.loads((opportunity_report_dir / "daily_opportunity_report.json").read_text(encoding="utf-8"))
    opportunities = payload.get("all_opportunities") or []
    evidence_rows = list(csv.DictReader((opportunity_report_dir / "evidence_inventory.csv").open(encoding="utf-8"))) if (opportunity_report_dir / "evidence_inventory.csv").exists() else []
    candidates: list[dict[str, Any]] = []
    rejection_reasons: list[dict[str, Any]] = []
    for row in opportunities:
        code = _normalize_code(row.get("code"))
        history = histories.get(code, pd.DataFrame())
        if history.empty:
            continue
        hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
        if hard:
            rejection_reasons.append({"code": code, "stock_name": row.get("stock_name"), "reason": "hard risk rejection", "detail": hard})
            continue
        urls = _evidence_urls(evidence_rows, row)
        plan = build_price_plan(row, history, urls)
        score = actionability_score(row, plan)
        combined = {
            **row,
            **plan,
            "code": code,
            "stock_name": row.get("stock_name"),
            "industry": row.get("normalized_industry") or quant_by_code.get(code, {}).get("industry") or row.get("raw_industry"),
            "quant_rank": quant_by_code.get(code, {}).get("quant_rank", ""),
            "proximity_rank": row.get("opportunity_proximity_rank", ""),
            "actionability_score": score,
        }
        candidates.append(combined)
    candidates.sort(key=lambda item: (_safe_float(item.get("actionability_score")) or 0.0), reverse=True)
    counts: Counter[str] = Counter()
    final_rows: list[dict[str, Any]] = []
    for item in candidates:
        item_urls = [url for url in str(item.get("evidence_urls") or "").split(";") if url]
        classification, status = classify_candidate(item, item, item_urls, counts)
        if not classification:
            continue
        enabled = classification == "BUY_READY"
        pullback_initial, pullback_max = _position_pct(
            float(item.get("pullback_entry_high") or 0),
            float(item.get("pullback_stop_price") or 0),
            enabled=enabled and item.get("pullback_status") == "READY",
        )
        breakout_initial, breakout_max = _position_pct(
            float(item.get("breakout_trigger_price") or 0),
            float(item.get("breakout_stop_price") or 0),
            enabled=enabled and item.get("breakout_status") == "READY",
        )
        item.update(
            {
                "classification": classification,
                "tomorrow_status": status,
                "main_logic": item.get("opportunity_logic") or item.get("main_logic") or "",
                "exit_profile_status": item.get("balanced_exit_historical_profile") or item.get("exit_profile_status") or "NOT_AVAILABLE",
                "pullback_initial_position_pct": pullback_initial,
                "pullback_max_position_pct": pullback_max,
                "breakout_initial_position_pct": breakout_initial,
                "breakout_max_position_pct": breakout_max,
                "max_loss_pct_of_risk_capital": 0.5 if enabled else 0.0,
                "missing_conditions": item.get("a_condition_failed") or "",
                "disclaimer": DISCLAIMER,
            }
        )
        final_rows.append(item)
        if len(final_rows) >= config.max_watchlist:
            break
    for index, item in enumerate(final_rows, 1):
        item["actionability_rank"] = index
    return final_rows, rejection_reasons, counts


def rejection_summary(
    universe_audit: list[dict[str, Any]],
    quant_rows: list[dict[str, Any]],
    watch_rejections: list[dict[str, Any]],
    final_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    buckets = Counter()
    mapping = {
        "st_or_delisting_risk": "hard risk rejection",
        "suspended_or_no_latest_trade": "hard risk rejection",
        "price_fetch_failed": "hard risk rejection",
        "financial_safety_failed": "financial safety failure",
        "value_trap_high": "valuation trap",
        "falling_knife": "falling knife",
        "price_too_high": "price too high",
        "trend_unconfirmed": "trend unconfirmed",
        "industry_evidence_missing": "industry evidence missing",
        "company_evidence_missing": "company evidence missing",
        "balanced_exit_profile_not_available": "exit profile unavailable",
        "insufficient_liquidity": "insufficient liquidity",
        "insufficient_history": "insufficient history",
        "REAL_RR_BELOW_1_8": "real reward risk below 1.8",
    }
    for row in universe_audit:
        buckets[mapping.get(str(row.get("reason")), str(row.get("reason") or "other"))] += 1
    for row in quant_rows:
        for reason in str(row.get("rejection_reasons") or "").split(";"):
            if reason:
                buckets[mapping.get(reason, reason)] += 1
    for row in watch_rejections:
        buckets[str(row.get("reason") or "other")] += 1
    for row in final_rows or []:
        if str(row.get("industry_evidence_status") or "") == "MISSING":
            buckets["industry evidence missing"] += 1
        if str(row.get("company_evidence_status") or "") == "MISSING":
            buckets["company evidence missing"] += 1
        if str(row.get("exit_profile_status") or "") in {"", "NOT_AVAILABLE", "DEGRADED"}:
            buckets["exit profile unavailable"] += 1
        if str(row.get("pullback_status") or "") == "REAL_RR_BELOW_1_8" or str(row.get("breakout_status") or "") == "REAL_RR_BELOW_1_8":
            buckets["real reward risk below 1.8"] += 1
    required = [
        "hard risk rejection",
        "financial safety failure",
        "valuation trap",
        "falling knife",
        "price too high",
        "trend unconfirmed",
        "industry evidence missing",
        "company evidence missing",
        "exit profile unavailable",
        "insufficient liquidity",
        "insufficient history",
        "real reward risk below 1.8",
    ]
    return [{"reason": reason, "count": buckets.get(reason, 0)} for reason in required]


def _write_csv(path: Path, rows: list[Mapping[str, Any]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = columns or sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _markdown(rows: list[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# Shenzhen Mainboard Full Scan Watchlist",
        "",
        DISCLAIMER,
        "",
        f"- as_of_date: {summary.get('as_of_date')}",
        f"- tomorrow: {summary.get('tomorrow')}",
        f"- raw_security_count: {summary.get('raw_security_count')}",
        f"- shenzhen_mainboard_a_count: {summary.get('shenzhen_mainboard_a_count')}",
        f"- excluded_chinext_count: {summary.get('excluded_chinext_count')}",
        f"- excluded_st_or_delist_count: {summary.get('excluded_st_or_delist_count')}",
        f"- excluded_suspended_count: {summary.get('excluded_suspended_count')}",
        f"- excluded_insufficient_history_count: {summary.get('excluded_insufficient_history_count')}",
        f"- excluded_insufficient_liquidity_count: {summary.get('excluded_insufficient_liquidity_count')}",
        f"- effective_scan_count: {summary.get('effective_scan_count')}",
        f"- actual_scanned_count: {summary.get('actual_scanned_count')}",
        f"- top80_evidence_queue_count: {summary.get('top80_evidence_queue_count')}",
        f"- top30_deep_review_count: {summary.get('top30_deep_review_count')}",
        f"- BUY_READY: {summary.get('buy_ready_count')}",
        f"- NEAR_READY: {summary.get('near_ready_count')}",
        f"- DEEP_WATCH: {summary.get('deep_watch_count')}",
        "",
        "| 排名 | 代码 | 股票 | 分类 | 最新价 | 回踩区间 | 回踩止损 | 突破价 | 突破止损 | 第一真实目标 | 第二真实目标 | 真实收益风险比 |",
        "| -- | -- | -- | -- | --: | ---: | ---: | --: | ---: | -----: | -----: | ------: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('actionability_rank')} | {row.get('code')} | {row.get('stock_name')} | {row.get('classification')} | {row.get('latest_close')} | "
            f"{row.get('pullback_entry_low')}-{row.get('pullback_entry_high')} | {row.get('pullback_stop_price')} | "
            f"{row.get('breakout_trigger_price')} | {row.get('breakout_stop_price')} | {row.get('real_resistance_target_1')} | "
            f"{row.get('real_resistance_target_2')} | {row.get('real_reward_risk_ratio')} |"
        )
    lines.append("")
    if not any(row.get("classification") == "BUY_READY" for row in rows):
        lines.append("2026年7月8日没有达到 BUY_READY 的深市主板股票。")
    lines.append("")
    lines.append("## 个股观察细节")
    lines.append("")
    for row in rows:
        buy_allowed = "是" if row.get("classification") == "BUY_READY" else "否"
        lines.extend(
            [
                f"### {row.get('stock_name')} ({row.get('code')})",
                "",
                f"- 入选依据：{row.get('main_logic') or '无'}",
                f"- 是否允许 {summary.get('tomorrow')} 买入：{buy_allowed}",
                f"- 更适合：{row.get('preferred_plan') or '人工复核'}",
                f"- 回踩计划：{row.get('pullback_status')}，区间 {row.get('pullback_entry_low')}-{row.get('pullback_entry_high')}，止损 {row.get('pullback_stop_price')}，目标 {row.get('pullback_target_1')}/{row.get('pullback_target_2')}，RR {row.get('pullback_real_reward_risk')}",
                f"- 突破计划：{row.get('breakout_status')}，触发 {row.get('breakout_trigger_price')}，最高追价 {row.get('breakout_max_chase_price')}，止损 {row.get('breakout_stop_price')}，目标 {row.get('breakout_target_1')}/{row.get('breakout_target_2')}，RR {row.get('breakout_real_reward_risk')}",
                f"- 技术止损/逻辑失效：回踩 {row.get('pullback_stop_price')}/{row.get('pullback_logic_invalidation_price')}；突破 {row.get('breakout_stop_price')}/{row.get('breakout_logic_invalidation_price')}",
                f"- 真实压力位：{row.get('real_resistance_target_1')} / {row.get('real_resistance_target_2')}；真实收益风险比：{row.get('real_reward_risk_ratio')}",
                f"- 动态仓位：回踩 {row.get('pullback_initial_position_pct')}%-{row.get('pullback_max_position_pct')}%；突破 {row.get('breakout_initial_position_pct')}%-{row.get('breakout_max_position_pct')}%；单笔最大亏损 {row.get('max_loss_pct_of_risk_capital')}%",
                f"- 行业证据：{row.get('industry_evidence_status')}；公司证据：{row.get('company_evidence_status')}；退出画像：{row.get('exit_profile_status')}",
                f"- 三项主要风险：{row.get('top_risks') or row.get('data_warnings') or '证据不完整'}",
                f"- 取消交易条件：{row.get('cancel_conditions') or row.get('missing_conditions') or '证据/趋势/价格条件未满足'}",
                "",
            ]
        )
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _evidence_markdown(rows: list[Mapping[str, Any]]) -> str:
    lines = ["# Evidence Review", "", DISCLAIMER, ""]
    for row in rows:
        lines.extend(
            [
                f"## {row.get('stock_name')} ({row.get('code')})",
                "",
                f"- industry_evidence_status: {row.get('industry_evidence_status')}",
                f"- company_evidence_status: {row.get('company_evidence_status')}",
                f"- exit_profile_status: {row.get('balanced_exit_historical_profile')}",
                f"- evidence_urls: {row.get('evidence_urls') or '无'}",
                f"- missing_conditions: {row.get('missing_conditions') or '无'}",
                "",
            ]
        )
    return "\n".join(lines)


def run_scan(
    config: ScanConfig,
    *,
    industry_evidence_file: str,
    company_evidence_file: str,
    industry_evidence_schema_file: str,
    industry_alias_map_file: str,
    exit_profile_file: str,
) -> tuple[Path, dict[str, Any]]:
    started = time.perf_counter()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    raw = fetch_szse_listing()
    official_rows, official_counts = build_official_universe(raw, as_of=config.as_of)
    histories, sources, errors = fetch_histories(official_rows, config)
    universe_rows, universe_audit, history_counts = enrich_universe_with_history(official_rows, histories, errors, config)
    benchmark = fetch_unadjusted_history("399001", as_of=config.as_of)
    quant_rows = quant_screen(universe_rows, histories, benchmark, config)
    if history_counts["effective_scan_count"] <= 100:
        raise RuntimeError(f"effective_scan_count={history_counts['effective_scan_count']} <= 100; shenzhen full scan universe failed")
    _write_csv(config.stock_pool_output, universe_rows, UNIVERSE_COLUMNS)
    _write_csv(config.output_dir / "shenzhen_universe.csv", universe_rows, UNIVERSE_COLUMNS)
    _write_csv(config.output_dir / "universe_exclusion_audit.csv", universe_audit)
    _write_csv(config.output_dir / "shenzhen_quant_screen_all.csv", quant_rows, QUANT_COLUMNS)
    top80 = [row for row in quant_rows if row.get("quant_status") in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}][: config.evidence_queue_size]
    _write_csv(config.output_dir / "top80_evidence_queue.csv", top80, QUANT_COLUMNS)
    deep_report, deep_summary = run_deep_opportunity_review(
        quant_rows=quant_rows,
        histories=histories,
        config=config,
        industry_evidence_file=industry_evidence_file,
        company_evidence_file=company_evidence_file,
        industry_evidence_schema_file=industry_evidence_schema_file,
        industry_alias_map_file=industry_alias_map_file,
        exit_profile_file=exit_profile_file,
    )
    quant_by_code = {str(row["code"]): row for row in quant_rows}
    final_rows, watch_rejections, class_counts = build_final_watchlist(
        opportunity_report_dir=deep_report,
        quant_by_code=quant_by_code,
        histories=histories,
        config=config,
    )
    top30 = sorted(final_rows + top80, key=lambda row: (_safe_float(row.get("actionability_score")) or _safe_float(row.get("quant_score")) or 0.0), reverse=True)[: config.deep_review_size]
    _write_csv(config.output_dir / "top30_deep_review.csv", top30)
    _write_csv(config.output_dir / "buy_ready.csv", [row for row in final_rows if row.get("classification") == "BUY_READY"], PLAN_COLUMNS)
    _write_csv(config.output_dir / "near_ready.csv", [row for row in final_rows if row.get("classification") == "NEAR_READY"], PLAN_COLUMNS)
    _write_csv(config.output_dir / "deep_watch.csv", [row for row in final_rows if row.get("classification") == "DEEP_WATCH"], PLAN_COLUMNS)
    _write_csv(config.output_dir / "tomorrow_watchlist_top12.csv", final_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "buy_sell_price_plan.csv", final_rows, PLAN_COLUMNS)
    plan_json = {"disclaimer": DISCLAIMER, "as_of_date": config.as_of.isoformat(), "tomorrow": config.tomorrow.isoformat(), "plans": final_rows}
    (config.output_dir / "buy_sell_price_plan.json").write_text(json.dumps(plan_json, ensure_ascii=False, indent=2), encoding="utf-8")
    rejection_rows = rejection_summary(universe_audit, quant_rows, watch_rejections, final_rows)
    _write_csv(config.output_dir / "rejection_summary.csv", rejection_rows, ["reason", "count"])
    summary = {
        **official_counts,
        **history_counts,
        "as_of_date": config.as_of.isoformat(),
        "tomorrow": config.tomorrow.isoformat(),
        "actual_scanned_count": len(quant_rows),
        "top80_evidence_queue_count": len(top80),
        "top30_deep_review_count": len(top30),
        "buy_ready_count": sum(1 for row in final_rows if row.get("classification") == "BUY_READY"),
        "near_ready_count": sum(1 for row in final_rows if row.get("classification") == "NEAR_READY"),
        "deep_watch_count": sum(1 for row in final_rows if row.get("classification") == "DEEP_WATCH"),
        "watchlist_count": len(final_rows),
        "stock_pool_output": str(config.stock_pool_output),
        "opportunity_report_dir": str(deep_report),
        "deep_review_report_dir": str(deep_report),
        "industry_evidence_file": industry_evidence_file,
        "company_evidence_file": company_evidence_file,
        "opportunity_acceptance_enum": deep_summary.get("acceptance_enum"),
        "exit_profile_distribution": load_exit_profile_distribution(exit_profile_file),
        "history_source_distribution": dict(Counter(sources.values())),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "price_adjustment": "unadjusted/tencent_kline",
        "no_auto_trade": True,
        "no_broker_integration": True,
        "disclaimer": DISCLAIMER,
    }
    (config.output_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.output_dir / "tomorrow_watchlist.md").write_text(_markdown(final_rows, summary), encoding="utf-8")
    (config.output_dir / "evidence_review.md").write_text(_evidence_markdown(final_rows), encoding="utf-8")
    return config.output_dir, summary


def _format_range(low: Any, high: Any) -> str:
    return f"{low}-{high}" if low != "" or high != "" else ""


def _pick_best(rows: list[Mapping[str, Any]], field: str) -> Mapping[str, Any] | None:
    scored = [(row, _safe_float(row.get(field))) for row in rows]
    scored = [(row, score) for row, score in scored if score is not None]
    if not scored:
        return None
    return max(scored, key=lambda item: item[1])[0]


def _print_terminal_report(output_dir: Path, summary: Mapping[str, Any]) -> None:
    rows = list(csv.DictReader((output_dir / "buy_sell_price_plan.csv").open(encoding="utf-8")))
    rejection_rows = list(csv.DictReader((output_dir / "rejection_summary.csv").open(encoding="utf-8")))

    print("\n## 深市主板全量扫描")
    print(f"原始证券数：{summary.get('raw_security_count')}")
    print(f"深市主板A股数：{summary.get('shenzhen_mainboard_a_count')}")
    print(f"排除创业板数量：{summary.get('excluded_chinext_count')}")
    print(f"排除ST和退市风险数量：{summary.get('excluded_st_or_delist_count')}")
    print(f"排除停牌数量：{summary.get('excluded_suspended_count')}")
    print(f"排除历史不足数量：{summary.get('excluded_insufficient_history_count')}")
    print(f"排除流动性不足数量：{summary.get('excluded_insufficient_liquidity_count')}")
    print(f"有效深市主板A股数：{summary.get('effective_scan_count')}")
    print(f"实际扫描数：{summary.get('actual_scanned_count')}")
    print(f"量化前80数量：{summary.get('top80_evidence_queue_count')}")
    print(f"深度研究数量：{summary.get('top30_deep_review_count')}")
    print(f"BUY_READY数量：{summary.get('buy_ready_count')}")
    print(f"NEAR_READY数量：{summary.get('near_ready_count')}")
    print(f"DEEP_WATCH数量：{summary.get('deep_watch_count')}")
    print("")
    print("| 排名 | 代码 | 股票 | 分类 | 最新价 | 回踩区间 | 回踩止损 | 突破价 | 突破止损 | 第一真实目标 | 第二真实目标 | 真实收益风险比 |")
    print("| -- | -- | -- | -- | --: | ---: | ---: | --: | ---: | -----: | -----: | ------: |")
    for row in rows:
        print(
            f"| {row.get('actionability_rank')} | {row.get('code')} | {row.get('stock_name')} | {row.get('classification')} | "
            f"{row.get('latest_close')} | {_format_range(row.get('pullback_entry_low'), row.get('pullback_entry_high'))} | "
            f"{row.get('pullback_stop_price')} | {row.get('breakout_trigger_price')} | {row.get('breakout_stop_price')} | "
            f"{row.get('real_resistance_target_1')} | {row.get('real_resistance_target_2')} | {row.get('real_reward_risk_ratio')} |"
        )

    print("")
    for row in rows:
        buy_allowed = "是" if row.get("classification") == "BUY_READY" else "否"
        print(f"### {row.get('stock_name')} ({row.get('code')})")
        print(f"为什么进入自选：{row.get('main_logic')}")
        print(f"是否允许{summary.get('tomorrow')}买入：{buy_allowed}")
        print(f"最适合回踩还是突破：{row.get('preferred_plan') or '人工复核'}")
        print(
            f"回踩计划：{row.get('pullback_status')}，区间 {_format_range(row.get('pullback_entry_low'), row.get('pullback_entry_high'))}，"
            f"止损 {row.get('pullback_stop_price')}，目标 {row.get('pullback_target_1')}/{row.get('pullback_target_2')}"
        )
        print(
            f"突破计划：{row.get('breakout_status')}，触发 {row.get('breakout_trigger_price')}，最高追价 {row.get('breakout_max_chase_price')}，"
            f"止损 {row.get('breakout_stop_price')}，目标 {row.get('breakout_target_1')}/{row.get('breakout_target_2')}"
        )
        print(
            f"技术止损：回踩 {row.get('pullback_stop_price')}；突破 {row.get('breakout_stop_price')}；"
            f"逻辑失效条件：回踩 {row.get('pullback_logic_invalidation_price')}；突破 {row.get('breakout_logic_invalidation_price')}"
        )
        print(f"真实压力位：{row.get('real_resistance_target_1')} / {row.get('real_resistance_target_2')}")
        print(f"真实收益风险比：{row.get('real_reward_risk_ratio')}")
        print(
            f"动态仓位：回踩 {row.get('pullback_initial_position_pct')}%-{row.get('pullback_max_position_pct')}%；"
            f"突破 {row.get('breakout_initial_position_pct')}%-{row.get('breakout_max_position_pct')}%；"
            f"单笔最大亏损 {row.get('max_loss_pct_of_risk_capital')}%"
        )
        print(f"行业证据：{row.get('industry_evidence_status')}")
        print(f"公司证据：{row.get('company_evidence_status')}")
        print(f"退出画像：{row.get('exit_profile_status')}")
        print(f"三项主要风险：{row.get('top_risks') or row.get('data_warnings') or '证据不完整'}")
        print(f"取消交易条件：{row.get('cancel_conditions') or row.get('missing_conditions') or '证据/趋势/价格条件未满足'}")
        print("")

    buy_ready = [f"{row.get('stock_name')}({row.get('code')})" for row in rows if row.get("classification") == "BUY_READY"]
    best_pullback = _pick_best(rows, "pullback_real_reward_risk")
    best_breakout = _pick_best(rows, "breakout_real_reward_risk")
    evidence_scored = sorted(
        rows,
        key=lambda row: (
            EVIDENCE_ORDER.get(str(row.get("industry_evidence_status") or "MISSING"), 0.0)
            + EVIDENCE_ORDER.get(str(row.get("company_evidence_status") or "MISSING"), 0.0)
            + EXIT_ORDER.get(str(row.get("exit_profile_status") or "NOT_AVAILABLE"), 0.0)
        ),
        reverse=True,
    )
    price_low = min(rows, key=lambda row: _safe_float(row.get("price_percentile_5y")) or 999.0) if rows else None
    rejection_text = "；".join(f"{row.get('reason')}={row.get('count')}" for row in rejection_rows)
    print(f"2026年7月8日BUY_READY股票：{', '.join(buy_ready) if buy_ready else '无'}")
    print(f"最值得等待回踩的股票：{best_pullback.get('stock_name')}({best_pullback.get('code')})" if best_pullback else "最值得等待回踩的股票：无")
    print(f"最值得等待突破的股票：{best_breakout.get('stock_name')}({best_breakout.get('code')})" if best_breakout else "最值得等待突破的股票：无")
    print(f"证据最完整的股票：{evidence_scored[0].get('stock_name')}({evidence_scored[0].get('code')})，但仍需人工复核" if evidence_scored else "证据最完整的股票：无")
    print(f"价格位置最低但仍未企稳的股票：{price_low.get('stock_name')}({price_low.get('code')})" if price_low else "价格位置最低但仍未企稳的股票：无")
    print(f"为什么最终没有选其他深市主板股票：{rejection_text}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Shenzhen mainboard full-universe opportunity scan.")
    parser.add_argument("--as-of-date", default="2026-07-07")
    parser.add_argument("--tomorrow", default="2026-07-08")
    parser.add_argument("--output-dir", default="reports/shenzhen_full_scan/20260708")
    parser.add_argument("--stock-pool-output", default="stock_pools/shenzhen_mainboard_a_full_20260707.csv")
    parser.add_argument("--max-workers", type=int, default=12)
    parser.add_argument("--evidence-queue-size", type=int, default=80)
    parser.add_argument("--deep-review-size", type=int, default=30)
    parser.add_argument("--max-watchlist", type=int, default=12)
    parser.add_argument("--fundamental-limit", type=int, default=30)
    parser.add_argument("--skip-fundamentals", action="store_true")
    parser.add_argument("--industry-evidence-file", default="data/user_supplied/industry_cycle_evidence.csv")
    parser.add_argument("--company-evidence-file", default="data/user_supplied/company_cycle_evidence.csv")
    parser.add_argument("--industry-evidence-schema", default="config/industry_evidence_schema.yaml")
    parser.add_argument("--industry-alias-map", default="config/industry_alias_map.yaml")
    parser.add_argument("--exit-profile-file", default="data/opportunity_snapshots/exit_profile.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ScanConfig(
        as_of=coerce_date(args.as_of_date),
        tomorrow=coerce_date(args.tomorrow),
        output_dir=Path(args.output_dir),
        stock_pool_output=Path(args.stock_pool_output),
        max_workers=args.max_workers,
        evidence_queue_size=args.evidence_queue_size,
        deep_review_size=args.deep_review_size,
        max_watchlist=args.max_watchlist,
        auto_fetch_fundamentals=not args.skip_fundamentals,
        fundamental_limit=args.fundamental_limit,
    )
    output_dir, summary = run_scan(
        config,
        industry_evidence_file=args.industry_evidence_file,
        company_evidence_file=args.company_evidence_file,
        industry_evidence_schema_file=args.industry_evidence_schema,
        industry_alias_map_file=args.industry_alias_map,
        exit_profile_file=args.exit_profile_file,
    )
    _print_terminal_report(output_dir, summary)
    print(f"\noutput_dir={output_dir}")
    print(f"stock_pool_output={summary.get('stock_pool_output')}")
    print(f"elapsed_seconds={summary.get('elapsed_seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
