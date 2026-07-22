"""Unified Shanghai/Shenzhen A-share daily production research scan.

Long-horizon indicators use point-in-time qfq history. Displayed price plans
use raw history. The module never connects to brokers or creates orders.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

import pandas as pd
import requests
import yaml

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame
from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_cycle_bottom.industry_evidence import load_evidence_csv, load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery.pipeline import RULE_VERSION, run_opportunity_discovery
from src.strategies.genge_opportunity_discovery.shenzhen_full_scan import (
    _atr,
    _ma,
    _position_pct,
    _relative_strength,
    _round,
    _round_price,
    _safe_float,
    _slope,
    _status_from_score,
    _support_candidates,
    fetch_baostock_industry_map,
    resolve_scan_dates,
)


DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入或卖出建议，不应自动交易。"
SSE_LIST_URL = "https://query.sse.com.cn/sseQuery/commonQuery.do"
SZSE_LIST_URL = "https://www.szse.cn/api/report/ShowReport"
ACCEPTANCE_FAIL = "FAIL_ALL_A_PRODUCTION"
ACCEPTANCE_RESEARCH = "PASS_ALL_A_PRODUCTION_RESEARCH_READY"
ACCEPTANCE_STRICT = "PASS_STRICT_REVIEW_CANDIDATE_GENERATED"
EXIT_PROFILE_MAX_AGE_DAYS = 90

USER_LEVELS = {
    "BUY_READY": "STRICT_REVIEW_READY",
    "NEAR_READY": "CONDITION_WATCH",
    "DEEP_WATCH": "RESEARCH_WATCH",
}

UNIVERSE_COLUMNS = [
    "code", "stock_name", "exchange", "board", "security_type", "listing_status",
    "listing_date", "is_st", "is_suspended", "latest_trade_date", "liquidity",
    "industry", "industry_source", "universe_source", "exclusion_reason",
]

PRICE_AUDIT_COLUMNS = [
    "code", "adjusted_latest_close", "raw_latest_close", "adjustment_ratio",
    "corporate_action_detected", "price_mapping_status", "price_adjustment_warning",
    "qfq_source", "raw_source", "qfq_latest_trade_date", "raw_latest_trade_date",
]

PLAN_COLUMNS = [
    "actionability_rank", "code", "stock_name", "exchange", "board", "industry",
    "classification", "user_visible_level", "latest_trade_date", "raw_latest_close",
    "adjusted_latest_close", "adjustment_ratio", "price_mapping_status",
    "price_adjustment_warning", "price_percentile_5y", "ma20", "ma60", "ma120", "ma250",
    "ma20_slope_pct", "ma60_slope_pct", "trend_confirmation_level", "valuation_score",
    "financial_safety_score", "industry_evidence_status", "company_evidence_status",
    "hard_logic_level", "exit_profile_status", "exit_profile_sample_count",
    "exit_profile_confidence", "recent_2y_sample_count", "profile_data_end_date", "profile_rule_version",
    "exit_profile_freshness_days", "exit_profile_rule_version_match",
    "exit_profile_freshness_passed", "exit_profile_data_version",
    "exit_profile_data_traceable", "strict_official_evidence_count",
    "strict_official_evidence_domains", "strict_official_evidence_passed",
    "pullback_entry_low", "pullback_entry_high",
    "pullback_stop_price", "pullback_logic_invalidation_price", "pullback_target_1",
    "pullback_target_2", "pullback_real_reward_risk", "pullback_status",
    "breakout_trigger_price", "breakout_confirmation_high", "breakout_max_chase_price",
    "breakout_required_volume", "breakout_stop_price", "breakout_logic_invalidation_price",
    "breakout_target_1", "breakout_target_2", "breakout_real_reward_risk", "breakout_status",
    "theoretical_target_1", "theoretical_target_2", "real_reward_risk_ratio",
    "preferred_plan", "risk_budget_initial_position_pct", "risk_budget_max_position_pct",
    "missing_conditions", "top_risks", "upgrade_conditions", "cancel_conditions",
    "evidence_urls", "disclaimer",
]

DAILY_SIGNAL_COLUMNS = [
    "signal_date", "valid_for_trade_date", "code", "stock_name", "signal_action",
    "signal_label", "previous_level", "current_level", "signal_reason",
    "signal_data_status", "latest_trade_date", "latest_price", "preferred_plan",
    "entry_low", "entry_high", "stop_price", "logic_invalidation_price",
    "target_1", "target_2", "risk_budget_initial_position_pct",
    "risk_budget_max_position_pct", "evidence_urls", "rule_version",
    "no_auto_trade", "disclaimer",
]


@dataclass(frozen=True)
class BoardRule:
    daily_price_limit: float
    max_gap_open_pct: float
    max_5d_return_pct: float
    max_10d_return_pct: float
    breakout_volume_ratio: float
    max_chase_atr_multiple: float
    minimum_turnover: float
    minimum_history_rows: int
    valuation_mode: str
    volatility_multiplier: float
    abnormal_move_threshold: float


@dataclass
class AllAScanConfig:
    as_of: date
    next_trade_date: date
    output_dir: Path
    stock_pool_output: Path
    board_rules_file: Path = Path("config/board_risk_rules.yaml")
    cache_dir: Path = Path("data/cache/all_a_full_scan")
    fundamental_cache_dir: Path = Path("data/cache/genge_fundamentals")
    evidence_cache_dir: Path = Path("data/cache/opportunity_evidence")
    state_dir: Path = Path("data/opportunity_snapshots/all_a_state")
    forward_ledger_file: Path = Path("data/opportunity_snapshots/all_a_forward_observation_ledger.csv")
    max_workers: int = 20
    evidence_queue_size: int = 80
    deep_review_size: int = 30
    max_watchlist: int = 15
    fundamental_limit: int = 30
    fixture_mode: bool = False


def load_board_rules(path: Path | str) -> dict[str, BoardRule]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    result: dict[str, BoardRule] = {}
    for board, raw in (payload.get("boards") or {}).items():
        result[str(board)] = BoardRule(**raw)
    required = {"SSE_MAIN", "SZSE_MAIN", "STAR", "CHINEXT"}
    if set(result) != required:
        raise ValueError(f"board rules must define exactly {sorted(required)}")
    return result


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _is_st_name(name: str) -> bool:
    normalized = str(name or "").upper().replace(" ", "")
    return "ST" in normalized or "退" in normalized


def _get_with_retry(url: str, *, attempts: int = 3, **kwargs: Any) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"public data request failed after {attempts} attempts: {url}") from last_error


def _board_from_exchange_row(*, exchange: str, board_text: str, code: str) -> str:
    if exchange == "SSE":
        if board_text == "STAR":
            return "STAR"
        return "SSE_MAIN"
    normalized = str(board_text or "").strip()
    if "创业板" in normalized:
        return "CHINEXT"
    if "主板" in normalized:
        return "SZSE_MAIN"
    return "UNRESOLVED"


def _listing_row(
    *, code: str, name: str, exchange: str, board: str, listing_date: Any,
    industry: str = "", industry_source: str = "", universe_source: str,
) -> dict[str, Any]:
    normalized_code = _normalize_code(code)
    try:
        listed = coerce_date(listing_date).isoformat()
    except Exception:
        listed = ""
    resolved_board = _board_from_exchange_row(exchange=exchange, board_text=board, code=normalized_code)
    reason = ""
    if resolved_board == "UNRESOLVED":
        reason = "security_type_unconfirmed"
    elif _is_st_name(name):
        reason = "st_or_delisting_risk"
    return {
        "code": normalized_code,
        "stock_name": str(name or "").strip(),
        "exchange": exchange,
        "board": resolved_board,
        "security_type": "ORDINARY_A_SHARE" if resolved_board != "UNRESOLVED" else "UNCONFIRMED",
        "listing_status": "LISTED",
        "listing_date": listed,
        "is_st": _is_st_name(name),
        "is_suspended": "",
        "latest_trade_date": "",
        "liquidity": "",
        "industry": str(industry or "").strip(),
        "industry_source": industry_source,
        "universe_source": universe_source,
        "exclusion_reason": reason,
    }


def mark_listings_after_as_of(
    rows: list[dict[str, Any]], *, as_of: date,
) -> list[dict[str, Any]]:
    """Exclude announced listings that have no tradable history by the cutoff."""
    result: list[dict[str, Any]] = []
    for row in rows:
        local = dict(row)
        if not local.get("exclusion_reason"):
            try:
                listing_date = coerce_date(local.get("listing_date"))
            except Exception:
                listing_date = None
            if listing_date is not None and listing_date > as_of:
                local["exclusion_reason"] = "listing_after_as_of"
        result.append(local)
    return result


def fetch_exchange_universe(as_of: date, *, timeout: int = 20) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.sse.com.cn/assortment/stock/list/share/",
    }
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for board_name, stock_type in (("SSE_MAIN", "1"), ("STAR", "8")):
        params = {
            "STOCK_TYPE": stock_type, "REG_PROVINCE": "", "CSRC_CODE": "", "STOCK_CODE": "",
            "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L", "COMPANY_STATUS": "2,4,5,7,8",
            "type": "inParams", "isPagination": "true", "pageHelp.pageSize": "10000",
            "pageHelp.pageNo": "1", "pageHelp.beginPage": "1", "pageHelp.endPage": "1",
        }
        response = _get_with_retry(SSE_LIST_URL, params=params, headers=headers, timeout=timeout)
        result = response.json().get("result") or []
        for item in result:
            rows.append(_listing_row(
                code=item.get("A_STOCK_CODE"), name=item.get("SEC_NAME_CN"), exchange="SSE",
                board=board_name, listing_date=item.get("LIST_DATE"),
                universe_source=f"SSE official commonQuery STOCK_TYPE={stock_type}",
            ))
        sources.append({"exchange": "SSE", "board": board_name, "status": "OK", "row_count": len(result)})

    response = _get_with_retry(
        SZSE_LIST_URL,
        params={"SHOWTYPE": "xlsx", "CATALOGID": "1110", "TABKEY": "tab1", "random": "0.5"},
        headers={"User-Agent": headers["User-Agent"], "Referer": "https://www.szse.cn/"},
        timeout=timeout,
    )
    frame = pd.read_excel(io.BytesIO(response.content))
    for _, item in frame.iterrows():
        rows.append(_listing_row(
            code=item.get("A股代码"), name=item.get("A股简称"), exchange="SZSE",
            board=str(item.get("板块") or ""), listing_date=item.get("A股上市日期"),
            industry=item.get("所属行业") or "", industry_source="SZSE official listing",
            universe_source="SZSE ShowReport CATALOGID=1110 TABKEY=tab1",
        ))
    sources.append({"exchange": "SZSE", "board": "ALL_A", "status": "OK", "row_count": len(frame)})
    rows = sorted({row["code"]: row for row in rows if row.get("code")}.values(), key=lambda row: row["code"])
    return rows, {
        "status": "OK", "snapshot_date": as_of.isoformat(), "fallback_age_days": 0,
        "sources": sources, "raw_security_count": len(rows),
    }


def write_universe_snapshot(path: Path, rows: Iterable[Mapping[str, Any]], audit: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(path, rows, UNIVERSE_COLUMNS)
    audit_path = path.with_suffix(".source.json")
    audit_path.write_text(json.dumps(dict(audit), ensure_ascii=False, indent=2), encoding="utf-8")


def load_recent_universe_snapshot(
    *, as_of: date, stock_pool_dir: Path = Path("stock_pools"), max_age_days: int = 7,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[tuple[date, Path]] = []
    for path in stock_pool_dir.glob("all_a_universe_*.csv"):
        try:
            snapshot_date = datetime.strptime(path.stem.rsplit("_", 1)[-1], "%Y%m%d").date()
        except ValueError:
            continue
        if snapshot_date <= as_of:
            candidates.append((snapshot_date, path))
    if not candidates:
        raise RuntimeError("no repository all-A universe snapshot available")
    snapshot_date, path = max(candidates, key=lambda item: item[0])
    age = (as_of - snapshot_date).days
    if age > max_age_days:
        raise RuntimeError(f"all-A universe snapshot age {age} exceeds {max_age_days} days")
    with path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    return rows, {
        "status": "SNAPSHOT_FALLBACK", "snapshot_date": snapshot_date.isoformat(),
        "fallback_age_days": age, "sources": [{"path": str(path), "status": "SNAPSHOT_FALLBACK"}],
        "raw_security_count": len(rows),
    }


def build_all_a_universe(
    *, as_of: date, stock_pool_dir: Path = Path("stock_pools"), fetcher=fetch_exchange_universe,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows, audit = fetcher(as_of)
        audit["fetch_error"] = ""
        return rows, audit
    except Exception as exc:
        rows, audit = load_recent_universe_snapshot(as_of=as_of, stock_pool_dir=stock_pool_dir)
        audit["fetch_error"] = f"{type(exc).__name__}: {exc}"
        return rows, audit


def _symbol(row: Mapping[str, Any]) -> str:
    prefix = "sh" if str(row.get("exchange")) == "SSE" else "sz"
    return f"{prefix}{_normalize_code(row.get('code'))}"


def _parse_tencent_rows(rows: Iterable[Any]) -> pd.DataFrame:
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        close = _safe_float(row[2])
        volume_lots = _safe_float(row[5])
        amount = _safe_float(row[6]) if len(row) > 6 else None
        parsed.append({
            "date": row[0], "open": _safe_float(row[1]), "close": close,
            "high": _safe_float(row[3]), "low": _safe_float(row[4]),
            "volume": (volume_lots or 0.0) * 100.0,
            "amount": amount if amount is not None else (close or 0.0) * (volume_lots or 0.0) * 100.0,
        })
    frame = pd.DataFrame(parsed)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    return frame.dropna(subset=["date"]).drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def fetch_tencent_history(
    row: Mapping[str, Any], *, as_of: date, adjusted: bool, timeout: int = 15,
) -> pd.DataFrame:
    symbol = _symbol(row)
    if adjusted:
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        param = f"{symbol},day,,{as_of:%Y-%m-%d},2000,qfq"
        key = "qfqday"
    else:
        url = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"
        param = f"{symbol},day,,{as_of:%Y-%m-%d},2000"
        key = "day"
    response = _get_with_retry(
        url, params={"param": param},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"},
        timeout=timeout,
    )
    response.raise_for_status()
    item = ((response.json().get("data") or {}).get(symbol) or {})
    return _parse_tencent_rows(item.get(key) or [])


def fetch_akshare_qfq_history(
    row: Mapping[str, Any], *, as_of: date,
) -> pd.DataFrame:
    """Fetch point-in-time qfq history without silently substituting raw prices."""
    import akshare as ak

    last_error: Exception | None = None
    frame = pd.DataFrame()
    for attempt in range(3):
        try:
            frame = ak.stock_zh_a_hist(
                symbol=_normalize_code(row.get("code")),
                period="daily",
                start_date=(as_of - timedelta(days=365 * 6)).strftime("%Y%m%d"),
                end_date=as_of.strftime("%Y%m%d"),
                adjust="qfq",
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    if frame is None or frame.empty:
        if last_error is not None:
            raise RuntimeError("AKShare qfq history failed after 3 attempts") from last_error
        return pd.DataFrame()
    renamed = frame.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount",
    })
    required = ["date", "open", "close", "high", "low", "volume", "amount"]
    if any(column not in renamed.columns for column in required):
        return pd.DataFrame()
    result = renamed[required].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.date
    for column in required[1:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def fetch_akshare_sina_qfq_history(row: Mapping[str, Any], *, as_of: date) -> pd.DataFrame:
    import akshare as ak

    frame = ak.stock_zh_a_daily(
        symbol=_symbol(row),
        start_date=(as_of - timedelta(days=365 * 6)).strftime("%Y%m%d"),
        end_date=as_of.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if frame is None or frame.empty:
        return pd.DataFrame()
    required = ["date", "open", "close", "high", "low", "volume", "amount"]
    if any(column not in frame.columns for column in required):
        return pd.DataFrame()
    result = frame[required].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.date
    for column in required[1:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def _cache_path(config: AllAScanConfig, code: str, adjusted: bool) -> Path:
    return config.cache_dir / ("qfq" if adjusted else "raw") / f"{code}.csv"


def load_or_fetch_history(
    row: Mapping[str, Any], config: AllAScanConfig, *, adjusted: bool,
) -> tuple[str, pd.DataFrame, str]:
    code = _normalize_code(row.get("code"))
    path = _cache_path(config, code, adjusted)
    if path.exists():
        try:
            cached = prepare_price_frame(pd.read_csv(path))
            if not cached.empty and cached["date"].max() >= config.as_of:
                return code, cached[cached["date"] <= config.as_of].copy(), "cache"
        except Exception:
            pass
    if adjusted:
        frame = fetch_akshare_sina_qfq_history(row, as_of=config.as_of)
        source = "akshare_sina_qfq"
        if not frame.empty:
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
        return code, frame, source
    frame = fetch_tencent_history(row, as_of=config.as_of, adjusted=adjusted)
    source = "tencent_raw"
    if not frame.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    return code, frame, source


def audit_price_mapping(
    adjusted: pd.DataFrame, raw: pd.DataFrame, *, as_of: date, qfq_source: str, raw_source: str,
) -> dict[str, Any]:
    qfq = prepare_price_frame(adjusted)
    unadjusted = prepare_price_frame(raw)
    warning = ""
    status = "OK"
    if qfq.empty or unadjusted.empty:
        status = "MISSING_SERIES"
        warning = "qfq_or_raw_history_missing"
        return {
            "adjusted_latest_close": "", "raw_latest_close": "", "adjustment_ratio": "",
            "corporate_action_detected": "", "price_mapping_status": status,
            "price_adjustment_warning": warning, "qfq_source": qfq_source, "raw_source": raw_source,
            "qfq_latest_trade_date": "", "raw_latest_trade_date": "",
        }
    qfq = qfq[qfq["date"] <= as_of]
    unadjusted = unadjusted[unadjusted["date"] <= as_of]
    qfq_date = qfq.iloc[-1]["date"]
    raw_date = unadjusted.iloc[-1]["date"]
    adjusted_close = float(qfq.iloc[-1]["close"])
    raw_close = float(unadjusted.iloc[-1]["close"])
    ratio = raw_close / adjusted_close if adjusted_close > 0 else None
    if qfq_date != raw_date:
        status = "DATE_MISMATCH"
        warning = "latest_trade_date_mismatch"
    elif qfq_date != as_of:
        status = "NO_ASOF_TRADE"
        warning = "suspended_or_no_asof_trade"
    elif ratio is None or not math.isfinite(ratio) or ratio <= 0:
        status = "INVALID_RATIO"
        warning = "invalid_adjustment_ratio"
    common = qfq[["date", "close"]].merge(
        unadjusted[["date", "close"]], on="date", suffixes=("_qfq", "_raw")
    ).tail(1250)
    ratios = common["close_raw"] / common["close_qfq"].replace(0, pd.NA)
    ratios = pd.to_numeric(ratios, errors="coerce").dropna()
    corporate_action = bool(len(ratios) > 1 and ratios.pct_change().abs().max() > 0.005)
    return {
        "adjusted_latest_close": round(adjusted_close, 4),
        "raw_latest_close": round(raw_close, 4),
        "adjustment_ratio": round(ratio, 8) if ratio is not None else "",
        "corporate_action_detected": corporate_action,
        "price_mapping_status": status,
        "price_adjustment_warning": warning,
        "qfq_source": qfq_source, "raw_source": raw_source,
        "qfq_latest_trade_date": qfq_date.isoformat(), "raw_latest_trade_date": raw_date.isoformat(),
    }


def _fetch_baostock_qfq_chunk(
    rows: list[dict[str, Any]], *, as_of_text: str, cache_dir_text: str,
) -> tuple[list[str], dict[str, str]]:
    import baostock as bs

    completed: list[str] = []
    failures: dict[str, str] = {}
    as_of = coerce_date(as_of_text)
    login = bs.login()
    if login.error_code != "0":
        return completed, {"__login__": login.error_msg}
    try:
        for row in rows:
            code = _normalize_code(row.get("code"))
            symbol = ("sh." if row.get("exchange") == "SSE" else "sz.") + code
            try:
                query = bs.query_history_k_data_plus(
                    symbol, "date,open,high,low,close,volume,amount",
                    start_date=(as_of - timedelta(days=365 * 6)).isoformat(),
                    end_date=as_of.isoformat(), frequency="d", adjustflag="2",
                )
                records: list[list[str]] = []
                while query.error_code == "0" and query.next():
                    records.append(query.get_row_data())
                if query.error_code != "0" or not records:
                    failures[code] = query.error_msg or "empty qfq history"
                    continue
                frame = pd.DataFrame(records, columns=["date", "open", "high", "low", "close", "volume", "amount"])
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
                for column in ("open", "high", "low", "close", "volume", "amount"):
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")
                frame = frame.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
                if frame.empty:
                    failures[code] = "normalized qfq history empty"
                    continue
                path = Path(cache_dir_text) / "qfq" / f"{code}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                frame.to_csv(path, index=False)
                completed.append(code)
            except Exception as exc:
                failures[code] = f"{type(exc).__name__}: {exc}"
    finally:
        bs.logout()
    return completed, failures


def _fetch_sina_qfq_chunk(
    rows: list[dict[str, Any]], *, as_of_text: str, cache_dir_text: str,
) -> tuple[list[str], dict[str, str]]:
    completed: list[str] = []
    failures: dict[str, str] = {}
    as_of = coerce_date(as_of_text)
    for row in rows:
        code = _normalize_code(row.get("code"))
        try:
            frame = fetch_akshare_sina_qfq_history(row, as_of=as_of)
            if frame.empty:
                failures[code] = "empty qfq history"
                continue
            path = Path(cache_dir_text) / "qfq" / f"{code}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False)
            completed.append(code)
        except Exception as exc:
            failures[code] = f"{type(exc).__name__}: {exc}"
    return completed, failures


def fetch_dual_histories(
    rows: list[dict[str, Any]], config: AllAScanConfig,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, dict[str, Any]], dict[str, str]]:
    qfq_histories: dict[str, pd.DataFrame] = {}
    raw_histories: dict[str, pd.DataFrame] = {}
    sources: dict[tuple[str, bool], str] = {}
    errors: dict[str, str] = {}
    candidates = [row for row in rows if not row.get("exclusion_reason")]
    for row in candidates:
        code = _normalize_code(row.get("code"))
        path = _cache_path(config, code, True)
        if not path.exists():
            continue
        try:
            cached = prepare_price_frame(pd.read_csv(path))
            if not cached.empty and cached["date"].max() >= config.as_of:
                qfq_histories[code] = cached[cached["date"] <= config.as_of].copy()
                sources[(code, True)] = "qfq_cache"
        except Exception:
            continue
    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        future_map = {
            executor.submit(load_or_fetch_history, row, config, adjusted=False): (row, False)
            for row in candidates
        }
        for future in as_completed(future_map):
            row, adjusted = future_map[future]
            code = _normalize_code(row.get("code"))
            try:
                _, frame, source = future.result()
                target = qfq_histories if adjusted else raw_histories
                target[code] = prepare_price_frame(frame) if not frame.empty else pd.DataFrame()
                sources[(code, adjusted)] = source
            except Exception as exc:
                errors[f"{code}:{'qfq' if adjusted else 'raw'}"] = f"{type(exc).__name__}: {exc}"
                (qfq_histories if adjusted else raw_histories)[code] = pd.DataFrame()
                sources[(code, adjusted)] = "failed"

    missing_qfq = [
        row for row in candidates
        if qfq_histories.get(_normalize_code(row.get("code")), pd.DataFrame()).empty
    ]
    if missing_qfq:
        worker_count = min(16, max(1, config.max_workers), len(missing_qfq))
        chunks = [missing_qfq[index::worker_count] for index in range(worker_count)]
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    _fetch_sina_qfq_chunk, chunk,
                    as_of_text=config.as_of.isoformat(), cache_dir_text=str(config.cache_dir),
                )
                for chunk in chunks if chunk
            ]
            for future in as_completed(futures):
                completed, failures = future.result()
                for code in completed:
                    qfq_histories[code] = prepare_price_frame(pd.read_csv(_cache_path(config, code, True)))
                    sources[(code, True)] = "akshare_sina_qfq"
                    errors.pop(f"{code}:qfq", None)
                for code, detail in failures.items():
                    errors[f"{code}:qfq"] = f"akshare_sina: {detail}"
    missing_qfq = [
        row for row in candidates
        if qfq_histories.get(_normalize_code(row.get("code")), pd.DataFrame()).empty
    ]
    if missing_qfq:
        completed, failures = _fetch_baostock_qfq_chunk(
            missing_qfq, as_of_text=config.as_of.isoformat(), cache_dir_text=str(config.cache_dir),
        )
        for code in completed:
            frame = prepare_price_frame(pd.read_csv(_cache_path(config, code, True)))
            qfq_histories[code] = frame
            sources[(code, True)] = "baostock_qfq"
            errors.pop(f"{code}:qfq", None)
        for code, detail in failures.items():
            errors[f"{code}:qfq"] = f"baostock: {detail}"
    audits: dict[str, dict[str, Any]] = {}
    for row in candidates:
        code = _normalize_code(row.get("code"))
        audits[code] = audit_price_mapping(
            qfq_histories.get(code, pd.DataFrame()), raw_histories.get(code, pd.DataFrame()),
            as_of=config.as_of, qfq_source=sources.get((code, True), "failed"),
            raw_source=sources.get((code, False), "failed"),
        )
    return qfq_histories, raw_histories, audits, errors


def enrich_industries(
    rows: list[dict[str, Any]], industry_map: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, Any]], int]:
    result: list[dict[str, Any]] = []
    matched = 0
    for row in rows:
        local = dict(row)
        item = industry_map.get(_normalize_code(local.get("code")))
        if item and item.get("industry"):
            local["industry"] = item["industry"]
            local["industry_source"] = "baostock.query_stock_industry"
            matched += 1
        result.append(local)
    return result, matched


def apply_universe_filters(
    rows: list[dict[str, Any]], qfq_histories: Mapping[str, pd.DataFrame],
    raw_histories: Mapping[str, pd.DataFrame], price_audits: Mapping[str, Mapping[str, Any]],
    errors: Mapping[str, str], *, as_of: date, board_rules: Mapping[str, BoardRule],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    result: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        local = dict(row)
        code = _normalize_code(local.get("code"))
        reason = str(local.get("exclusion_reason") or "")
        qfq = prepare_price_frame(qfq_histories.get(code, pd.DataFrame()))
        raw = prepare_price_frame(raw_histories.get(code, pd.DataFrame()))
        price_audit = price_audits.get(code, {})
        rule = board_rules.get(str(local.get("board")))
        if not reason and rule is None:
            reason = "security_type_unconfirmed"
        if not reason and any(key.startswith(f"{code}:") for key in errors):
            reason = "price_fetch_failed"
            counts["fatal_data_failure_count"] += 1
        if not raw.empty:
            local["latest_trade_date"] = raw.iloc[-1]["date"].isoformat()
            local["liquidity"] = round(float(pd.to_numeric(raw.tail(20)["amount"], errors="coerce").mean()), 2)
        if not reason and (raw.empty or raw.iloc[-1]["date"] != as_of):
            reason = "suspended_or_latest_trade_date_mismatch"
            local["is_suspended"] = True
        if not reason and price_audit.get("price_mapping_status") != "OK":
            reason = "price_mapping_failed"
            counts["fatal_data_failure_count"] += 1
        if not reason and len(qfq) < int(rule.minimum_history_rows):
            reason = "insufficient_adjusted_history"
        if not reason and len(raw) < min(120, int(rule.minimum_history_rows)):
            reason = "insufficient_raw_history"
        if not reason and (_safe_float(local.get("liquidity")) or 0.0) < rule.minimum_turnover:
            reason = "insufficient_liquidity"
        local["exclusion_reason"] = reason
        counts[reason or "effective_scan_count"] += 1
        if reason:
            audit_rows.append({
                "code": code, "stock_name": local.get("stock_name"), "exchange": local.get("exchange"),
                "board": local.get("board"), "stage": "universe_filter", "reason": reason,
                "detail": ";".join(value for key, value in errors.items() if key.startswith(f"{code}:")),
            })
        result.append(local)
    return result, audit_rows, counts


def _percentile(series: pd.Series, current: float) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return None if values.empty else float((values <= current).sum() / len(values))


def quant_screen(
    universe_rows: list[dict[str, Any]], qfq_histories: Mapping[str, pd.DataFrame],
    raw_histories: Mapping[str, pd.DataFrame], price_audits: Mapping[str, Mapping[str, Any]],
    benchmark_qfq: pd.DataFrame, *, as_of: date, board_rules: Mapping[str, BoardRule],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in universe_rows:
        if item.get("exclusion_reason"):
            continue
        code = _normalize_code(item.get("code"))
        adjusted = prepare_price_frame(qfq_histories.get(code, pd.DataFrame()))
        raw = prepare_price_frame(raw_histories.get(code, pd.DataFrame()))
        adjusted = adjusted[adjusted["date"] <= as_of].copy().reset_index(drop=True)
        raw = raw[raw["date"] <= as_of].copy().reset_index(drop=True)
        if adjusted.empty or raw.empty:
            continue
        rule = board_rules[str(item["board"])]
        adjusted_close = float(adjusted.iloc[-1]["close"])
        raw_close = float(raw.iloc[-1]["close"])
        one_year = adjusted.tail(250)
        five_year = adjusted.tail(1250)
        percentile_1y = _percentile(one_year["close"], adjusted_close)
        percentile_5y = _percentile(five_year["close"], adjusted_close)
        ma20, ma60, ma120, ma250 = (_ma(adjusted, days) for days in (20, 60, 120, 250))
        ma20_slope, ma60_slope = _slope(adjusted, 20), _slope(adjusted, 60)
        rs20 = _relative_strength(adjusted, benchmark_qfq, 20)
        rs60 = _relative_strength(adjusted, benchmark_qfq, 60)
        return_5d = (adjusted_close / float(adjusted.iloc[-6]["close"]) - 1) * 100 if len(adjusted) > 5 else None
        return_10d = (adjusted_close / float(adjusted.iloc[-11]["close"]) - 1) * 100 if len(adjusted) > 10 else None
        hard: list[str] = []
        soft: list[str] = []
        if percentile_5y is None:
            hard.append("adjusted_percentile_missing")
        elif percentile_5y > 0.75:
            hard.append("price_too_high")
        if return_5d is not None and return_5d > rule.max_5d_return_pct:
            hard.append("board_5d_abnormal_move")
        if return_10d is not None and return_10d > rule.max_10d_return_pct:
            hard.append("board_10d_abnormal_move")
        if ma250 and adjusted_close < ma250 * 0.82 and (ma20_slope or 0) < 0:
            soft.append("falling_knife")
        if ma20 and adjusted_close >= ma20 and (ma20_slope or 0) >= -0.2:
            trend = "WEAK"
            if ma60 and adjusted_close >= ma60 and (ma60_slope or 0) >= -0.2:
                trend = "MEDIUM"
            if ma60 and ma120 and adjusted_close >= ma60 and ma20 >= ma60 and ma60 >= ma120 and (ma60_slope or 0) > 0:
                trend = "STRONG"
        else:
            trend = "NONE"
            soft.append("trend_unconfirmed")
        price_score = 90 if (percentile_5y or 1) <= .2 else 75 if (percentile_5y or 1) <= .35 else 55 if (percentile_5y or 1) <= .5 else 35 if (percentile_5y or 1) <= .65 else 15
        trend_score = {"NONE": 0, "WEAK": 35, "MEDIUM": 70, "STRONG": 100}[trend]
        liquidity = _safe_float(item.get("liquidity")) or 0.0
        liquidity_score = min(100.0, math.log10(max(liquidity, 1.0) / rule.minimum_turnover + 1.0) * 70.0)
        relatives = [value for value in (rs20, rs60) if value is not None]
        relative_score = 50.0 if not relatives else max(0.0, min(100.0, 50.0 + sum(relatives) / len(relatives) * 2.0))
        quant_score = round(price_score * .35 + trend_score * .35 + liquidity_score * .20 + relative_score * .10, 4)
        status = "HARD_REJECT" if hard else "PRIORITY_RESEARCH" if quant_score >= 58 and "falling_knife" not in soft else "SECONDARY_RESEARCH" if quant_score >= 45 else "LOW_PRIORITY"
        rows.append({
            "code": code, "stock_name": item.get("stock_name"), "exchange": item.get("exchange"),
            "board": item.get("board"), "security_type": item.get("security_type"),
            "industry": item.get("industry"), "industry_source": item.get("industry_source"),
            "latest_trade_date": raw.iloc[-1]["date"].isoformat(), "raw_latest_close": _round_price(raw_close),
            "adjusted_latest_close": _round_price(adjusted_close),
            **dict(price_audits.get(code, {})),
            "price_percentile_5y": _round(percentile_5y), "price_percentile_1y": _round(percentile_1y),
            "ma20": _round_price(ma20), "ma60": _round_price(ma60), "ma120": _round_price(ma120), "ma250": _round_price(ma250),
            "ma20_slope_pct": _round(ma20_slope), "ma60_slope_pct": _round(ma60_slope),
            "trend_confirmation_level": trend, "relative_strength_20d": _round(rs20),
            "relative_strength_60d": _round(rs60), "return_5d_pct": _round(return_5d),
            "return_10d_pct": _round(return_10d), "liquidity": round(liquidity, 2),
            "quant_score": quant_score, "quant_status": status, "hard_blockers": ";".join(hard),
            "soft_blockers": ";".join(sorted(set(soft))), "rejection_reasons": ";".join(sorted(set(hard + soft))),
        })
    rows.sort(key=lambda row: (_safe_float(row.get("quant_score")) or 0.0), reverse=True)
    for index, row in enumerate(rows, 1):
        row["quant_rank"] = index
    return rows


def _cluster_pivots(
    values: list[tuple[float, float]], tolerance: float,
) -> list[dict[str, Any]]:
    groups: list[list[tuple[float, float]]] = []
    for price, prominence in sorted(values):
        for group in groups:
            center = sum(item[0] for item in group) / len(group)
            if abs(price - center) <= tolerance:
                group.append((price, prominence))
                break
        else:
            groups.append([(price, prominence)])
    return [
        {
            "price": sum(item[0] for item in group) / len(group),
            "touches": len(group),
            "prominence": sum(item[1] for item in group) / len(group),
        }
        for group in groups
    ]


def resistance_levels(
    raw_history: pd.DataFrame, *, atr14: float, entry: float, pivot_window: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    history = prepare_price_frame(raw_history).tail(500).reset_index(drop=True)
    highs = pd.to_numeric(history["high"], errors="coerce")
    lows = pd.to_numeric(history["low"], errors="coerce")
    pivots: list[tuple[float, float]] = []
    for index in range(pivot_window, len(history) - pivot_window):
        price = float(highs.iloc[index])
        local_highs = highs.iloc[index - pivot_window : index + pivot_window + 1]
        if not math.isfinite(price) or price < float(local_highs.max()):
            continue
        shoulders = pd.concat([
            lows.iloc[index - pivot_window : index],
            lows.iloc[index + 1 : index + pivot_window + 1],
        ]).dropna()
        if shoulders.empty:
            continue
        prominence = price - float(shoulders.mean())
        if prominence >= max(atr14 * .35, price * .008):
            pivots.append((price, prominence))
    tolerance = max(atr14 * .35, entry * .01)
    clusters = _cluster_pivots(pivots, tolerance)
    for cluster in clusters:
        cluster["kind"] = "major_resistance" if cluster["touches"] >= 3 and cluster["prominence"] >= atr14 else "minor_resistance"
    above = sorted((item for item in clusters if item["price"] > entry), key=lambda item: item["price"])
    minimum_distance = max(atr14, entry * .02)
    eligible = [item for item in above if item["touches"] >= 2 and item["price"] - entry >= minimum_distance]
    return above, eligible


def build_price_plan(
    row: Mapping[str, Any], raw_history: pd.DataFrame, board_rule: BoardRule,
    evidence_urls: list[str],
) -> dict[str, Any]:
    history = prepare_price_frame(raw_history)
    close = float(history.iloc[-1]["close"])
    latest_date = coerce_date(history.iloc[-1]["date"])
    atr14 = _atr(history) or max(.01, close * .03)
    avg_volume_20 = float(pd.to_numeric(history.tail(20)["volume"], errors="coerce").mean())
    supports = _support_candidates(history, atr14, close)
    support = supports[0][0] if supports else None
    pullback = {
        "pullback_entry_low": "", "pullback_entry_high": "", "pullback_stop_price": "",
        "pullback_logic_invalidation_price": "", "pullback_target_1": "", "pullback_target_2": "",
        "pullback_real_reward_risk": "", "pullback_status": "NO_CONFIRMED_SUPPORT",
    }
    pullback_resistance_audit: list[dict[str, Any]] = []
    if support:
        entry_low = support - .30 * atr14
        entry_high = min(close, support + .20 * atr14)
        stop = min(entry_low - .01, support - .75 * atr14)
        invalidation = min(stop, support - 1.05 * atr14)
        all_levels, eligible = resistance_levels(history, atr14=atr14, entry=entry_high)
        pullback_resistance_audit = all_levels
        if len(eligible) >= 1:
            target_1 = eligible[0]["price"]
            target_2 = eligible[1]["price"] if len(eligible) > 1 else target_1 + max(atr14, target_1 * .02)
            values = [float(_round_price(value)) for value in (entry_low, entry_high, stop, invalidation, target_1, target_2)]
            entry_low_p, entry_high_p, stop_p, invalidation_p, target_1_p, target_2_p = values
            if stop_p < entry_low_p <= entry_high_p < target_1_p:
                rr = (target_1_p - entry_high_p) / (entry_high_p - stop_p)
                pullback.update({
                    "pullback_entry_low": entry_low_p, "pullback_entry_high": entry_high_p,
                    "pullback_stop_price": stop_p, "pullback_logic_invalidation_price": invalidation_p,
                    "pullback_target_1": target_1_p, "pullback_target_2": target_2_p,
                    "pullback_real_reward_risk": round(rr, 2),
                    "pullback_status": "READY" if rr >= 1.8 else "VALID_RR_BELOW_STRICT",
                })
            else:
                pullback["pullback_status"] = "INVALID_PRICE_RELATION"
        else:
            pullback["pullback_status"] = "NO_ELIGIBLE_REAL_RESISTANCE"

    recent_high = float(pd.to_numeric(history.tail(20)["high"], errors="coerce").max())
    trigger = recent_high + .10 * atr14
    confirmation_high = trigger + .20 * atr14
    max_chase = confirmation_high + board_rule.max_chase_atr_multiple * atr14
    breakout_stop = trigger - max(1.20 * atr14 * board_rule.volatility_multiplier, trigger * .025)
    breakout_invalidation = min(breakout_stop, recent_high - .30 * atr14)
    breakout_all, breakout_eligible = resistance_levels(history, atr14=atr14, entry=max_chase)
    breakout = {
        "breakout_trigger_price": _round_price(trigger),
        "breakout_confirmation_high": _round_price(confirmation_high),
        "breakout_max_chase_price": _round_price(max_chase),
        "breakout_required_volume": round(avg_volume_20 * board_rule.breakout_volume_ratio, 0),
        "breakout_stop_price": _round_price(breakout_stop),
        "breakout_logic_invalidation_price": _round_price(breakout_invalidation),
        "breakout_target_1": "", "breakout_target_2": "", "breakout_real_reward_risk": "",
        "breakout_status": "NO_ELIGIBLE_REAL_RESISTANCE",
    }
    if breakout_eligible:
        target_1 = breakout_eligible[0]["price"]
        target_2 = breakout_eligible[1]["price"] if len(breakout_eligible) > 1 else target_1 + max(atr14, target_1 * .02)
        entry_p, max_chase_p, stop_p, target_1_p, target_2_p = [
            float(_round_price(value)) for value in (trigger, max_chase, breakout_stop, target_1, target_2)
        ]
        if stop_p < entry_p <= max_chase_p < target_1_p:
            rr = (target_1_p - max_chase_p) / (max_chase_p - stop_p)
            breakout.update({
                "breakout_target_1": target_1_p, "breakout_target_2": target_2_p,
                "breakout_real_reward_risk": round(rr, 2),
                "breakout_status": "READY" if rr >= 1.8 else "VALID_RR_BELOW_STRICT",
            })
        else:
            breakout["breakout_status"] = "INVALID_PRICE_RELATION"
    pullback_rr = _safe_float(pullback.get("pullback_real_reward_risk"))
    breakout_rr = _safe_float(breakout.get("breakout_real_reward_risk"))
    if breakout_rr is not None and (pullback_rr is None or breakout_rr >= pullback_rr):
        preferred, preferred_rr = "breakout", breakout_rr
    elif pullback_rr is not None:
        preferred, preferred_rr = "pullback", pullback_rr
    else:
        preferred, preferred_rr = "", None
    theoretical_risk = max(.01, max_chase - breakout_stop)
    return {
        "latest_trade_date": latest_date.isoformat(), "raw_latest_close": _round_price(close),
        **pullback, **breakout,
        "theoretical_target_1": _round_price(max_chase + 1.5 * theoretical_risk),
        "theoretical_target_2": _round_price(max_chase + 2.5 * theoretical_risk),
        "real_reward_risk_ratio": round(preferred_rr, 2) if preferred_rr is not None else "",
        "preferred_plan": preferred,
        "pullback_resistance_audit": pullback_resistance_audit,
        "breakout_resistance_audit": breakout_all,
        "cancel_conditions": "盘前新增重大负面公告；停牌或数据不一致；高开超过最高追价；跌破对应失效区；行业或公司证据被证伪",
        "evidence_urls": ";".join(evidence_urls),
    }


def _exit_profiles(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    if not path.exists():
        return {}, {"NOT_AVAILABLE": 0}
    frame = pd.read_csv(path, dtype={"code": str})
    result: dict[str, dict[str, Any]] = {}
    distribution: Counter[str] = Counter()
    for _, item in frame.iterrows():
        code = _normalize_code(item.get("code"))
        status = str(item.get("balanced_exit_historical_profile") or item.get("exit_profile_status") or "NOT_AVAILABLE")
        sample_count = int(_safe_float(item.get("exit_profile_sample_count") or item.get("signal_count")) or 0)
        recent_2y = int(_safe_float(item.get("recent_2y_sample_count")) or 0)
        data_end_date = str(item.get("profile_data_end_date") or "").strip()
        generated_at = str(item.get("generated_at") or "").strip()
        confidence = str(item.get("profile_confidence") or ("HIGH" if sample_count >= 100 else "MEDIUM" if sample_count >= 30 else "LOW"))
        rule_version = str(item.get("profile_rule_version") or "").strip()
        data_version = str(
            item.get("profile_data_version") or item.get("data_version")
            or item.get("source_signal_details") or ""
        ).strip()
        profile = {
            "exit_profile_status": status, "exit_profile_sample_count": sample_count,
            "recent_2y_sample_count": recent_2y,
            "60d_exit_net_return": item.get("60d_exit_net_return") or item.get("avg_balanced_exit_net_return_60d") or "",
            "60d_exit_win_rate": item.get("60d_exit_win_rate") or item.get("win_rate_balanced_exit_60d") or "",
            "60d_exit_outperform_rate": item.get("60d_exit_outperform_rate") or "",
            "250d_exit_drawdown": item.get("250d_exit_drawdown") or item.get("avg_balanced_exit_max_drawdown_250d") or "",
            "exit_profile_confidence": confidence, "profile_data_end_date": data_end_date,
            "profile_generated_at": generated_at, "profile_rule_version": rule_version,
            "exit_profile_data_version": data_version,
        }
        result[code] = profile
        distribution[status] += 1
    return result, dict(distribution)


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


def _evidence_matches_candidate(evidence: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    code = _normalize_code(row.get("code"))
    industry = str(row.get("normalized_industry") or row.get("industry") or "")
    scope = str(evidence.get("scope") or "").lower()
    evidence_code = _normalize_code(evidence.get("code")) if evidence.get("code") else ""
    evidence_industry = str(evidence.get("industry") or "")
    return (scope == "company" and evidence_code == code) or (scope == "industry" and evidence_industry == industry)


def _is_strict_official_domain(domain: str, evidence: Mapping[str, Any]) -> bool:
    normalized = domain.lower().strip(".")
    official_suffixes = ("gov.cn", "sse.com.cn", "szse.cn", "cninfo.com.cn")
    if any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in official_suffixes):
        return True
    declared = str(
        evidence.get("company_official_domain") or evidence.get("official_company_domain") or ""
    ).lower().strip().removeprefix("www.").strip(".")
    comparable = normalized.removeprefix("www.")
    return bool(declared and (comparable == declared or comparable.endswith(f".{declared}")))


def strict_official_evidence_audit(
    evidence_rows: Iterable[Mapping[str, Any]], row: Mapping[str, Any], *, as_of: date,
) -> dict[str, Any]:
    allowed_source_types = {
        "OFFICIAL_REPORT", "COMPANY_ANNOUNCEMENT", "EXCHANGE_DISCLOSURE", "OFFICIAL_GOVERNMENT",
    }
    allowed_statuses = {"PARTIALLY_VERIFIED", "VERIFIED"}
    domains: list[str] = []
    for evidence in evidence_rows:
        if not _evidence_matches_candidate(evidence, row):
            continue
        source_type = str(evidence.get("source_type") or "").strip().upper()
        evidence_status = str(evidence.get("evidence_status") or "").strip().upper()
        parse_status = str(evidence.get("parse_status") or "").strip().upper()
        if source_type not in allowed_source_types or evidence_status not in allowed_statuses or parse_status != "OK":
            continue
        if evidence_status == "LEAD_ONLY" or "lead_only" in str(evidence.get("warning_flags") or "").lower():
            continue
        try:
            evidence_date = coerce_date(evidence.get("evidence_date") or evidence.get("date"))
        except Exception:
            continue
        if evidence_date > as_of:
            continue
        url = str(evidence.get("original_url") or evidence.get("source") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            continue
        if not _is_strict_official_domain(parsed.hostname, evidence):
            continue
        verified_content = any(
            str(evidence.get(key) or "").strip()
            for key in ("raw_excerpt", "normalized_summary", "content_hash", "extracted_value")
        )
        if not verified_content:
            continue
        domains.append(parsed.hostname.lower())
    unique_domains = list(dict.fromkeys(domains))
    return {
        "strict_official_evidence_count": len(domains),
        "strict_official_evidence_domains": ";".join(unique_domains),
        "strict_official_evidence_passed": bool(domains),
    }


def enrich_exit_profile(profile: Mapping[str, Any], *, as_of: date) -> dict[str, Any]:
    enriched = dict(profile)
    freshness_days: int | str = ""
    data_end_date = str(profile.get("profile_data_end_date") or "").strip()
    if data_end_date:
        try:
            freshness_days = (as_of - coerce_date(data_end_date)).days
        except Exception:
            freshness_days = ""
    rule_match = str(profile.get("profile_rule_version") or "") == RULE_VERSION
    freshness_passed = (
        isinstance(freshness_days, int) and 0 <= freshness_days <= EXIT_PROFILE_MAX_AGE_DAYS
    )
    data_version = str(profile.get("exit_profile_data_version") or "").strip()
    enriched.update({
        "exit_profile_freshness_days": freshness_days,
        "exit_profile_rule_version_match": rule_match,
        "exit_profile_freshness_passed": freshness_passed,
        "exit_profile_data_version": data_version,
        "exit_profile_data_traceable": bool(data_version),
    })
    return enriched


def actionability_score(row: Mapping[str, Any], plan: Mapping[str, Any]) -> float:
    quant = _safe_float(row.get("quant_score")) or 0.0
    trend = {"NONE": 0, "WEAK": 35, "MEDIUM": 70, "STRONG": 100}.get(str(row.get("trend_confirmation_level")), 0)
    industry = {"VERIFIED": 100, "PARTIALLY_VERIFIED": 70, "LEAD_ONLY": 30}.get(str(row.get("industry_evidence_status")), 0)
    company = {"VERIFIED": 100, "PARTIALLY_VERIFIED": 70, "LEAD_ONLY": 30}.get(str(row.get("company_evidence_status")), 0)
    financial = _safe_float(row.get("financial_safety_score")) or 0.0
    valuation = _safe_float(row.get("valuation_score")) or 0.0
    exit_score = {"PASSED": 100, "DEGRADED": 45, "NOT_AVAILABLE": 0, "FAILED": 0}.get(str(row.get("exit_profile_status")), 0)
    execution = max(0.0, 100.0 - (_safe_float(row.get("execution_risk_score")) or 0.0))
    rr = _safe_float(plan.get("real_reward_risk_ratio")) or 0.0
    rr_score = max(0.0, min(100.0, rr / 2.5 * 100.0))
    return round(
        quant * .20 + trend * .15 + industry * .15 + company * .15 + financial * .15
        + valuation * .08 + exit_score * .05 + execution * .03 + rr_score * .04,
        4,
    )


def _status(value: Any) -> str:
    return _status_from_score(value)


def classify_candidate(
    row: Mapping[str, Any], plan: Mapping[str, Any], profile: Mapping[str, Any],
    evidence_urls: list[str], *, board_rule: BoardRule,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    percentile = _safe_float(row.get("price_percentile_5y"))
    trend = str(row.get("trend_confirmation_level") or "NONE")
    ma60_slope = _safe_float(row.get("ma60_slope_pct"))
    adjusted_close = _safe_float(row.get("adjusted_latest_close"))
    ma60 = _safe_float(row.get("ma60"))
    financial = _status(row.get("financial_safety_score"))
    valuation = _status(row.get("valuation_score"))
    industry = str(row.get("industry_evidence_status") or "MISSING")
    company = str(row.get("company_evidence_status") or "MISSING")
    hard_logic = str(row.get("hard_logic_level") or "NONE")
    exit_status = str(profile.get("exit_profile_status") or "NOT_AVAILABLE")
    sample_count = int(_safe_float(profile.get("exit_profile_sample_count")) or 0)
    profile_confidence = str(profile.get("exit_profile_confidence") or "LOW")
    rr = _safe_float(plan.get("real_reward_risk_ratio")) or 0.0
    ready_plan = plan.get("pullback_status") == "READY" or plan.get("breakout_status") == "READY"
    execution_high = str(row.get("execution_risk_quality") or "").upper() == "HIGH" or "execution_risk_high" in str(row.get("hard_reject_blockers") or "")
    value_trap_high = bool(row.get("value_trap_flag")) or "value_trap_high" in str(row.get("hard_reject_blockers") or "")
    strict_checks = {
        "no_hard_risk": not hard,
        "price_percentile_le_35": percentile is not None and percentile <= .35,
        "trend_medium": trend in {"MEDIUM", "STRONG"},
        "above_ma60": adjusted_close is not None and ma60 is not None and adjusted_close >= ma60,
        "ma60_not_down": ma60_slope is not None and ma60_slope >= -.2,
        "not_falling_knife": "falling_knife" not in str(row.get("soft_blockers") or row.get("risk_flags") or ""),
        "financial_passed": financial == "PASSED",
        "valuation_not_failed": valuation in {"PASSED", "DEGRADED"},
        "industry_evidence": industry in {"VERIFIED", "PARTIALLY_VERIFIED"},
        "company_evidence": company in {"VERIFIED", "PARTIALLY_VERIFIED"},
        "hard_logic_medium": hard_logic in {"MEDIUM", "STRONG"},
        "exit_profile_passed": exit_status == "PASSED",
        "exit_profile_sample_count": sample_count >= 30,
        "exit_profile_recent_2y_samples": int(_safe_float(profile.get("recent_2y_sample_count")) or 0) >= 10,
        "exit_profile_confidence": profile_confidence in {"MEDIUM", "HIGH"},
        "exit_profile_freshness": bool(profile.get("exit_profile_freshness_passed")),
        "exit_profile_rule_version": bool(profile.get("exit_profile_rule_version_match")),
        "exit_profile_data_traceable": bool(profile.get("exit_profile_data_traceable")),
        "real_rr_1_8": rr >= 1.8,
        "ready_plan": ready_plan,
        "strict_official_evidence": bool(row.get("strict_official_evidence_passed")),
        "execution_not_high": not execution_high,
        "value_trap_not_high": not value_trap_high,
        "price_mapping_ok": str(row.get("price_mapping_status")) == "OK",
    }
    if all(strict_checks.values()):
        return "STRICT_REVIEW_READY", []
    blockers = [name for name, passed in strict_checks.items() if not passed]
    ma20_slope = _safe_float(row.get("ma20_slope_pct"))
    distance_to_ma60 = None if adjusted_close is None or ma60 in (None, 0) else abs(adjusted_close / ma60 - 1.0)
    valid_plan = plan.get("pullback_status") in {"READY", "VALID_RR_BELOW_STRICT"} or plan.get("breakout_status") in {"READY", "VALID_RR_BELOW_STRICT"}
    condition_checks = {
        "no_hard_risk": not hard,
        "price_percentile_le_50": percentile is not None and percentile <= .50,
        "trend_weak": trend in {"WEAK", "MEDIUM", "STRONG"},
        "ma20_slope_not_down": ma20_slope is not None and ma20_slope >= -.2,
        "near_ma60": distance_to_ma60 is not None and distance_to_ma60 <= .08 * board_rule.volatility_multiplier,
        "financial_passed": financial == "PASSED",
        "valuation_not_failed": valuation in {"PASSED", "DEGRADED"},
        "company_evidence": company in {"VERIFIED", "PARTIALLY_VERIFIED"},
        "official_url": bool(evidence_urls),
        "real_rr_1_3": rr >= 1.3,
        "valid_plan": valid_plan,
        "no_below_ma250_deep_risk": "below_ma250_deep_risk" not in str(row.get("risk_flags") or ""),
        "price_mapping_ok": str(row.get("price_mapping_status")) == "OK",
    }
    if all(condition_checks.values()):
        missing = [
            name for name in (
                "industry_evidence", "hard_logic_medium", "trend_medium", "exit_profile_passed",
                "exit_profile_sample_count", "exit_profile_recent_2y_samples", "exit_profile_confidence", "exit_profile_freshness",
                "exit_profile_rule_version", "exit_profile_data_traceable", "strict_official_evidence",
            )
            if not strict_checks.get(name, False)
        ]
        return "CONDITION_WATCH", missing
    if not hard and trend in {"WEAK", "MEDIUM", "STRONG"} and company in {"VERIFIED", "PARTIALLY_VERIFIED", "LEAD_ONLY"}:
        return "RESEARCH_WATCH", [name for name, passed in condition_checks.items() if not passed]
    return "NOT_QUALIFIED", [name for name, passed in condition_checks.items() if not passed]


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], columns: list[str] | None = None) -> None:
    values = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = columns or sorted({key for row in values for key in row})
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in values:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def _distribution(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "UNKNOWN") for row in rows))


def _coverage(rows: list[Mapping[str, Any]], predicate) -> float:
    return 0.0 if not rows else round(sum(1 for row in rows if predicate(row)) / len(rows), 6)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_previous_watchlist_state(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("by_code") if isinstance(payload, Mapping) else None
    if not isinstance(rows, Mapping):
        return {}
    return {
        _normalize_code(code): dict(row)
        for code, row in rows.items()
        if isinstance(row, Mapping)
    }


def _changes(
    current: list[Mapping[str, Any]], previous_state_file: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    previous = _load_previous_watchlist_state(previous_state_file)
    current_by_code = {_normalize_code(row.get("code")): dict(row) for row in current}
    changes: list[dict[str, Any]] = []
    evidence_changes: list[dict[str, Any]] = []
    level_rank = {"NOT_QUALIFIED": 0, "RESEARCH_WATCH": 1, "CONDITION_WATCH": 2, "STRICT_REVIEW_READY": 3}
    for code, row in current_by_code.items():
        before = previous.get(code, {})
        old_level, new_level = str(before.get("user_visible_level") or ""), str(row.get("user_visible_level") or "")
        old_trend, new_trend = str(before.get("trend_confirmation_level") or ""), str(row.get("trend_confirmation_level") or "")
        old_rr, new_rr = _safe_float(before.get("real_reward_risk_ratio")), _safe_float(row.get("real_reward_risk_ratio"))
        if not before and new_level == "STRICT_REVIEW_READY":
            change_type = "NEW_STRICT_REVIEW_READY"
        elif not before and new_level == "CONDITION_WATCH":
            change_type = "NEW_CONDITION_WATCH"
        elif level_rank.get(new_level, 0) > level_rank.get(old_level, 0):
            change_type = "UPGRADED_FROM_RESEARCH"
        elif old_trend == "NONE" and new_trend == "WEAK":
            change_type = "TREND_NONE_TO_WEAK"
        elif old_trend == "WEAK" and new_trend in {"MEDIUM", "STRONG"}:
            change_type = "TREND_WEAK_TO_MEDIUM"
        elif old_rr is not None and new_rr is not None and new_rr - old_rr >= .3:
            change_type = "REAL_RR_IMPROVED"
        elif level_rank.get(new_level, 0) < level_rank.get(old_level, 0):
            change_type = "DOWNGRADED"
        elif str(row.get("hard_blockers") or "") and not str(before.get("hard_blockers") or ""):
            change_type = "HARD_RISK_NEW"
        else:
            change_type = "UNCHANGED"
        changes.append({
            "code": code, "stock_name": row.get("stock_name"), "previous_level": old_level,
            "current_level": new_level, "previous_trend": old_trend, "current_trend": new_trend,
            "previous_real_rr": old_rr if old_rr is not None else "", "current_real_rr": new_rr if new_rr is not None else "",
            "change_type": change_type, "detail": row.get("missing_conditions") or row.get("top_risks") or "",
        })
        old_industry = str(before.get("industry_evidence_status") or "")
        new_industry = str(row.get("industry_evidence_status") or "")
        old_company = str(before.get("company_evidence_status") or "")
        new_company = str(row.get("company_evidence_status") or "")
        evidence_type = "UNCHANGED"
        if old_industry in {"", "MISSING", "LEAD_ONLY"} and new_industry in {"PARTIALLY_VERIFIED", "VERIFIED"}:
            evidence_type = "NEW_INDUSTRY_EVIDENCE"
        elif old_company in {"", "MISSING", "LEAD_ONLY"} and new_company in {"PARTIALLY_VERIFIED", "VERIFIED"}:
            evidence_type = "NEW_COMPANY_EVIDENCE"
        evidence_changes.append({
            "code": code, "stock_name": row.get("stock_name"),
            "previous_industry_evidence_status": old_industry, "current_industry_evidence_status": new_industry,
            "previous_company_evidence_status": old_company, "current_company_evidence_status": new_company,
            "change_type": evidence_type,
        })
    for code, before in previous.items():
        if code not in current_by_code and str(before.get("user_visible_level")) in {"STRICT_REVIEW_READY", "CONDITION_WATCH", "RESEARCH_WATCH"}:
            changes.append({
                "code": code, "stock_name": before.get("stock_name"), "previous_level": before.get("user_visible_level"),
                "current_level": "", "previous_trend": before.get("trend_confirmation_level"), "current_trend": "",
                "previous_real_rr": before.get("real_reward_risk_ratio"), "current_real_rr": "",
                "change_type": "REMOVED", "detail": "left_current_research_watchlist",
            })
    previous_state_file.parent.mkdir(parents=True, exist_ok=True)
    previous_state_file.write_text(json.dumps({"saved_at": datetime.now(timezone.utc).isoformat(), "by_code": current_by_code}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return changes, evidence_changes


def _signal_plan_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    preferred = str(row.get("preferred_plan") or "")
    if preferred == "pullback":
        return {
            "entry_low": row.get("pullback_entry_low"),
            "entry_high": row.get("pullback_entry_high"),
            "stop_price": row.get("pullback_stop_price"),
            "logic_invalidation_price": row.get("pullback_logic_invalidation_price"),
            "target_1": row.get("pullback_target_1"),
            "target_2": row.get("pullback_target_2"),
        }
    if preferred == "breakout":
        return {
            "entry_low": row.get("breakout_trigger_price"),
            "entry_high": row.get("breakout_max_chase_price"),
            "stop_price": row.get("breakout_stop_price"),
            "logic_invalidation_price": row.get("breakout_logic_invalidation_price"),
            "target_1": row.get("breakout_target_1"),
            "target_2": row.get("breakout_target_2"),
        }
    return {
        "entry_low": "", "entry_high": "", "stop_price": "",
        "logic_invalidation_price": "", "target_1": "", "target_2": "",
    }


def build_daily_signals(
    *, current_rows: list[Mapping[str, Any]], previous: Mapping[str, Mapping[str, Any]],
    as_of: date, next_trade_date: date,
) -> list[dict[str, Any]]:
    """Build deterministic daily research actions without account or broker state."""

    current_by_code = {_normalize_code(row.get("code")): row for row in current_rows}
    signals: list[dict[str, Any]] = []
    for code, row in current_by_code.items():
        before = previous.get(code, {})
        previous_level = str(before.get("user_visible_level") or "")
        current_level = str(row.get("user_visible_level") or "")
        latest_price = _safe_float(row.get("raw_latest_close"))
        before_plan = _signal_plan_fields(before)
        previous_stop = _safe_float(before_plan.get("stop_price"))
        previous_invalidation = _safe_float(before_plan.get("logic_invalidation_price"))
        breached = (
            latest_price is not None
            and any(
                threshold is not None and latest_price <= threshold
                for threshold in (previous_stop, previous_invalidation)
            )
        )
        if previous_level == "STRICT_REVIEW_READY" and (current_level != "STRICT_REVIEW_READY" or breached):
            action = "SELL_EXIT"
            label = "退出信号"
            reason = "previous_stop_or_invalidation_breached" if breached else (
                f"strict_signal_lost:{row.get('missing_conditions') or 'qualification_lost'}"
            )
        elif current_level == "STRICT_REVIEW_READY":
            action = "HOLD_REVIEW" if previous_level == "STRICT_REVIEW_READY" else "BUY_IF_TRIGGERED"
            label = "持有复核" if action == "HOLD_REVIEW" else "条件买入信号"
            reason = "strict_signal_remains_valid" if action == "HOLD_REVIEW" else "all_strict_gates_passed"
        else:
            action = "WATCH_ONLY"
            label = "仅观察"
            reason = str(row.get("missing_conditions") or "strict_gates_not_passed")
        plan = _signal_plan_fields(row)
        risk_budget_enabled = action in {"BUY_IF_TRIGGERED", "HOLD_REVIEW"}
        signals.append({
            "signal_date": as_of.isoformat(), "valid_for_trade_date": next_trade_date.isoformat(),
            "code": code, "stock_name": row.get("stock_name"), "signal_action": action,
            "signal_label": label, "previous_level": previous_level, "current_level": current_level,
            "signal_reason": reason, "signal_data_status": "CURRENT_DATA",
            "latest_trade_date": row.get("latest_trade_date"), "latest_price": row.get("raw_latest_close"),
            "preferred_plan": row.get("preferred_plan"), **plan,
            "risk_budget_initial_position_pct": (
                row.get("risk_budget_initial_position_pct") or 0.0
            ) if risk_budget_enabled else 0.0,
            "risk_budget_max_position_pct": (
                row.get("risk_budget_max_position_pct") or 0.0
            ) if risk_budget_enabled else 0.0,
            "evidence_urls": row.get("evidence_urls"), "rule_version": RULE_VERSION,
            "no_auto_trade": True, "disclaimer": DISCLAIMER,
        })
    for code, before in previous.items():
        if code in current_by_code or str(before.get("user_visible_level") or "") != "STRICT_REVIEW_READY":
            continue
        plan = _signal_plan_fields(before)
        signals.append({
            "signal_date": as_of.isoformat(), "valid_for_trade_date": next_trade_date.isoformat(),
            "code": code, "stock_name": before.get("stock_name"), "signal_action": "SELL_EXIT",
            "signal_label": "退出信号", "previous_level": "STRICT_REVIEW_READY", "current_level": "",
            "signal_reason": "left_current_research_watchlist", "signal_data_status": "CURRENT_ROW_MISSING",
            "latest_trade_date": before.get("latest_trade_date"), "latest_price": before.get("raw_latest_close"),
            "preferred_plan": before.get("preferred_plan"), **plan,
            "risk_budget_initial_position_pct": 0.0, "risk_budget_max_position_pct": 0.0,
            "evidence_urls": before.get("evidence_urls"), "rule_version": RULE_VERSION,
            "no_auto_trade": True, "disclaimer": DISCLAIMER,
        })
    action_rank = {"SELL_EXIT": 0, "BUY_IF_TRIGGERED": 1, "HOLD_REVIEW": 2, "WATCH_ONLY": 3}
    signals.sort(key=lambda row: (action_rank.get(str(row.get("signal_action")), 9), str(row.get("code"))))
    return signals


def _daily_signals_markdown(summary: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "# 每日买入/卖出研究信号", "", DISCLAIMER, "",
        f"- 信号日期: {summary.get('as_of_date')}",
        f"- 适用交易日: {summary.get('next_trade_date')}",
        f"- 条件买入: {summary.get('buy_signal_count')}",
        f"- 持有复核: {summary.get('hold_signal_count')}",
        f"- 退出信号: {summary.get('sell_signal_count')}",
        f"- 仅观察: {summary.get('watch_signal_count')}", "",
        "买入信号只有在价格进入指定区间且盘前公告/停牌/数据核对无异常时才成立；退出信号表示策略资格丢失或失效位触发，不读取实际持仓。", "",
    ]
    actionable = [row for row in rows if row.get("signal_action") != "WATCH_ONLY"]
    if not actionable:
        lines.extend(["本次没有满足严格门槛的买入、持有或退出信号。", ""])
    for row in actionable:
        lines.extend([
            f"## {row.get('stock_name')} ({row.get('code')}) - {row.get('signal_action')}", "",
            f"- 原因: {row.get('signal_reason')}",
            f"- 最新价格: {row.get('latest_price')}（{row.get('latest_trade_date')}）",
            f"- 条件区间: {row.get('entry_low')}-{row.get('entry_high')}",
            f"- 止损/失效: {row.get('stop_price')} / {row.get('logic_invalidation_price')}",
            f"- 目标: {row.get('target_1')} / {row.get('target_2')}",
            f"- 风险预算参考: {row.get('risk_budget_initial_position_pct')}%-{row.get('risk_budget_max_position_pct')}%", "",
        ])
    return "\n".join(lines) + "\n"


def _change_markdown(title: str, rows: list[Mapping[str, Any]], include_types: set[str]) -> str:
    selected = [row for row in rows if str(row.get("change_type")) in include_types]
    lines = [f"# {title}", "", DISCLAIMER, ""]
    if not selected:
        lines.append("本次没有对应变化。")
    for row in selected:
        lines.append(f"- {row.get('stock_name')}({row.get('code')}): {row.get('change_type')}，{row.get('detail') or ''}")
    return "\n".join(lines) + "\n"


def _fundamentals(
    quant_rows: list[dict[str, Any]], qfq_histories: Mapping[str, pd.DataFrame],
    config: AllAScanConfig,
) -> tuple[list[BacktestInput], dict[str, str]]:
    selected = [
        row for row in quant_rows if row.get("quant_status") in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}
    ][: config.evidence_queue_size]
    loader = PublicFundamentalLoader(config.fundamental_cache_dir)
    inputs: list[BacktestInput] = []
    errors: dict[str, str] = {}
    for index, row in enumerate(selected):
        code = str(row["code"])
        valuation_df = None
        financial_df = None
        if index < config.fundamental_limit:
            try:
                fetched = loader.load(code, years=5, fetch_valuation=True, fetch_financial=True)
                valuation_df = fetched.valuation_df
                financial_df = fetched.financial_df
                if fetched.provider_errors:
                    errors[code] = json.dumps(fetched.provider_errors, ensure_ascii=False, sort_keys=True)
            except Exception as exc:
                errors[code] = f"{type(exc).__name__}: {exc}"
        inputs.append(BacktestInput(
            code=code, stock_name=str(row.get("stock_name") or code),
            industry=str(row.get("industry") or ""), price_df=qfq_histories[code],
            valuation_df=valuation_df, financial_df=financial_df,
        ))
    return inputs, errors


def _apply_position_budget(row: dict[str, Any], plan: Mapping[str, Any], level: str) -> None:
    strict = level == "STRICT_REVIEW_READY"
    preferred = str(plan.get("preferred_plan") or "")
    entry = _safe_float(
        plan.get(f"{preferred}_entry_high") or plan.get("breakout_max_chase_price")
    ) or 0.0
    stop = _safe_float(plan.get(f"{preferred}_stop_price")) or 0.0
    initial, maximum = _position_pct(entry, stop, enabled=strict)
    row["risk_budget_initial_position_pct"] = initial if strict else 0.0
    row["risk_budget_max_position_pct"] = maximum if strict else 0.0


def _merge_deep_rows(
    *, quant_rows: list[dict[str, Any]], deep_report: Path, raw_histories: Mapping[str, pd.DataFrame],
    price_audits: Mapping[str, Mapping[str, Any]], board_rules: Mapping[str, BoardRule],
    exit_profiles: Mapping[str, Mapping[str, Any]], max_watchlist: int, as_of: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads((deep_report / "daily_opportunity_report.json").read_text(encoding="utf-8"))
    evidence_rows = list(csv.DictReader((deep_report / "evidence_inventory.csv").open(encoding="utf-8")))
    quant_by_code = {str(row["code"]): row for row in quant_rows}
    all_rows: list[dict[str, Any]] = []
    for deep in payload.get("all_opportunities") or []:
        code = _normalize_code(deep.get("code"))
        quant = quant_by_code.get(code, {})
        raw = raw_histories.get(code, pd.DataFrame())
        if raw.empty:
            continue
        urls = _evidence_urls(evidence_rows, deep)
        board = str(quant.get("board") or "")
        if board not in board_rules:
            continue
        plan = build_price_plan(deep, raw, board_rules[board], urls)
        profile = enrich_exit_profile(exit_profiles.get(code, {}), as_of=as_of)
        official_evidence = strict_official_evidence_audit(evidence_rows, deep, as_of=as_of)
        merged = {
            **deep, **quant, **dict(price_audits.get(code, {})), **profile, **official_evidence, **plan,
            "code": code, "stock_name": deep.get("stock_name") or quant.get("stock_name"),
            "exchange": quant.get("exchange"), "board": board,
            "industry": deep.get("normalized_industry") or quant.get("industry") or deep.get("raw_industry"),
            "industry_evidence_status": deep.get("industry_evidence_status") or "MISSING",
            "company_evidence_status": deep.get("company_evidence_status") or "MISSING",
            "hard_logic_level": deep.get("hard_logic_level") or "NONE",
            "exit_profile_status": profile.get("exit_profile_status") or "NOT_AVAILABLE",
            "evidence_urls": ";".join(urls), "disclaimer": DISCLAIMER,
        }
        level, missing = classify_candidate(merged, plan, profile, urls, board_rule=board_rules[board])
        merged["classification"] = level
        merged["user_visible_level"] = level
        merged["missing_conditions"] = ";".join(missing)
        merged["top_risks"] = deep.get("top_risks") or ";".join(missing[:3])
        merged["upgrade_conditions"] = deep.get("upgrade_conditions") or ";".join(missing)
        merged["actionability_score"] = actionability_score(merged, plan)
        _apply_position_budget(merged, plan, level)
        all_rows.append(merged)
    all_rows.sort(key=lambda row: (_safe_float(row.get("actionability_score")) or 0.0), reverse=True)
    selected: list[dict[str, Any]] = []
    level_limits = {"STRICT_REVIEW_READY": 3, "CONDITION_WATCH": 5, "RESEARCH_WATCH": 10}
    counts: Counter[str] = Counter()
    for row in all_rows:
        level = str(row.get("user_visible_level"))
        if level not in level_limits or counts[level] >= level_limits[level]:
            continue
        counts[level] += 1
        selected.append(row)
        if len(selected) >= max_watchlist:
            break
    for index, row in enumerate(selected, 1):
        row["actionability_rank"] = index
    return selected, all_rows


def _watchlist_markdown(summary: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "# 沪深全 A 每日公开数据研究报告", "", DISCLAIMER, "",
        f"- 最近完整行情日: {summary.get('as_of_date')}",
        f"- 下一交易日: {summary.get('next_trade_date')}",
        f"- 有效扫描: {summary.get('effective_scan_count')}",
        f"- STRICT_REVIEW_READY: {summary.get('strict_review_ready_count')}",
        f"- CONDITION_WATCH: {summary.get('condition_watch_count')}",
        f"- RESEARCH_WATCH: {summary.get('research_watch_count')}", "",
        "只有 STRICT_REVIEW_READY 才显示非零风险预算参考仓位；它仍不是交易指令，必须盘前公告复核、券商客户端价格核对和当日条件确认。", "",
    ]
    for row in rows:
        lines.extend([
            f"## {row.get('stock_name')} ({row.get('code')}) - {row.get('user_visible_level')}", "",
            f"- board/exchange: {row.get('board')} / {row.get('exchange')}",
            f"- raw latest close: {row.get('raw_latest_close')}",
            f"- qfq MA20/60/120/250: {row.get('ma20')} / {row.get('ma60')} / {row.get('ma120')} / {row.get('ma250')}",
            f"- qfq 5y percentile: {row.get('price_percentile_5y')}",
            f"- pullback: {row.get('pullback_status')} {row.get('pullback_entry_low')}-{row.get('pullback_entry_high')} stop {row.get('pullback_stop_price')} target {row.get('pullback_target_1')}/{row.get('pullback_target_2')} RR {row.get('pullback_real_reward_risk')}",
            f"- breakout: {row.get('breakout_status')} trigger {row.get('breakout_trigger_price')}-{row.get('breakout_confirmation_high')} max chase {row.get('breakout_max_chase_price')} stop {row.get('breakout_stop_price')} target {row.get('breakout_target_1')}/{row.get('breakout_target_2')} RR {row.get('breakout_real_reward_risk')}",
            f"- risk budget reference: {row.get('risk_budget_initial_position_pct')}%-{row.get('risk_budget_max_position_pct')}%",
            f"- missing conditions: {row.get('missing_conditions') or 'none'}",
            f"- evidence: {row.get('evidence_urls') or 'none'}", "",
        ])
    return "\n".join(lines) + "\n"


def run_scan(
    config: AllAScanConfig, *, industry_evidence_file: str, company_evidence_file: str,
    industry_evidence_schema_file: str, industry_alias_map_file: str, exit_profile_file: str,
) -> tuple[Path, dict[str, Any]]:
    started = time.perf_counter()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    board_rules = load_board_rules(config.board_rules_file)
    universe_rows, source_audit = build_all_a_universe(as_of=config.as_of)
    universe_rows = mark_listings_after_as_of(universe_rows, as_of=config.as_of)
    industry_map, industry_diagnostics = fetch_baostock_industry_map()
    universe_rows, industry_enriched_count = enrich_industries(universe_rows, industry_map)
    write_universe_snapshot(config.stock_pool_output, universe_rows, source_audit)
    qfq_histories, raw_histories, price_audits, price_errors = fetch_dual_histories(universe_rows, config)
    universe_rows, universe_audit, filter_counts = apply_universe_filters(
        universe_rows, qfq_histories, raw_histories, price_audits, price_errors,
        as_of=config.as_of, board_rules=board_rules,
    )
    benchmark_record = {"code": "000905", "exchange": "SSE"}
    # Equity indexes have no split/dividend adjustment; raw index history is the
    # point-in-time comparable series for relative-strength calculations.
    benchmark_qfq = fetch_tencent_history(benchmark_record, as_of=config.as_of, adjusted=False)
    quant_rows = quant_screen(
        universe_rows, qfq_histories, raw_histories, price_audits, benchmark_qfq,
        as_of=config.as_of, board_rules=board_rules,
    )
    if not quant_rows or filter_counts["effective_scan_count"] <= 100:
        raise RuntimeError("all-A effective universe is unexpectedly small")
    top80 = [row for row in quant_rows if row.get("quant_status") in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}][: config.evidence_queue_size]
    inputs, fundamental_errors = _fundamentals(quant_rows, qfq_histories, config)
    deep_report, deep_summary = run_opportunity_discovery(
        inputs=inputs,
        requested_codes=[item.code for item in inputs],
        data_errors={},
        data_sources={item.code: "all_a_qfq_tencent" for item in inputs},
        benchmark_df=benchmark_qfq,
        industry_cycle_df=None,
        industry_evidence_df=load_evidence_csv(industry_evidence_file),
        company_evidence_df=load_evidence_csv(company_evidence_file),
        industry_evidence_schema=load_industry_evidence_schema(industry_evidence_schema_file),
        industry_alias_map=load_industry_alias_map(industry_alias_map_file),
        requested_as_of_date=config.as_of.isoformat(),
        output_dir=config.output_dir / "_deep_review",
        diagnostics={
            "source_mode": "real_all_a_full_scan", "requested_stock_records": top80,
            "industry_evidence_file": industry_evidence_file,
            "company_evidence_file": company_evidence_file,
            "exit_profile_file": exit_profile_file,
            "no_auto_trade": True, "no_broker_integration": True,
        },
        priority_queue_size=config.evidence_queue_size,
        secondary_queue_size=config.evidence_queue_size,
        exit_profile_df=pd.read_csv(exit_profile_file, dtype={"code": str}) if Path(exit_profile_file).exists() else None,
        ledger_path=config.forward_ledger_file,
        run_mode="full",
        evidence_cache_dir=config.evidence_cache_dir,
        auto_evidence_limit=min(config.deep_review_size, 30),
        state_dir=config.state_dir / "deep_pipeline",
    )
    profiles, input_exit_distribution = _exit_profiles(Path(exit_profile_file))
    watchlist, deep_rows = _merge_deep_rows(
        quant_rows=quant_rows, deep_report=deep_report, raw_histories=raw_histories,
        price_audits=price_audits, board_rules=board_rules, exit_profiles=profiles,
        max_watchlist=config.max_watchlist, as_of=config.as_of,
    )
    strict_rows = [row for row in watchlist if row.get("user_visible_level") == "STRICT_REVIEW_READY"]
    condition_rows = [row for row in watchlist if row.get("user_visible_level") == "CONDITION_WATCH"]
    research_rows = [row for row in watchlist if row.get("user_visible_level") == "RESEARCH_WATCH"]
    previous_state_file = config.state_dir / "last_all_a_state.json"
    previous_watchlist = _load_previous_watchlist_state(previous_state_file)
    daily_signals = build_daily_signals(
        current_rows=watchlist, previous=previous_watchlist,
        as_of=config.as_of, next_trade_date=config.next_trade_date,
    )
    changes, evidence_changes = _changes(watchlist, previous_state_file)
    board_distribution = _distribution(universe_rows, "board")
    exchange_distribution = _distribution(universe_rows, "exchange")
    price_source_distribution = dict(Counter(
        str(audit.get("raw_source") or "unknown") for audit in price_audits.values()
    ))
    adjustment_source_distribution = dict(Counter(
        str(audit.get("qfq_source") or "unknown") for audit in price_audits.values()
    ))
    matched_exit_distribution = dict(Counter(str(row.get("exit_profile_status") or "NOT_AVAILABLE") for row in deep_rows))
    summary = {
        "as_of_date": config.as_of.isoformat(), "next_trade_date": config.next_trade_date.isoformat(),
        "raw_security_count": len(universe_rows), "official_universe_count": len(universe_rows),
        "valid_stock_count": filter_counts["effective_scan_count"],
        "fatal_data_failure_count": filter_counts["fatal_data_failure_count"],
        "skipped_stock_count": len(universe_rows) - filter_counts["effective_scan_count"],
        "exchange_distribution": exchange_distribution, "board_distribution": board_distribution,
        "price_source_distribution": price_source_distribution,
        "adjustment_source_distribution": adjustment_source_distribution,
        "effective_scan_count": len(quant_rows),
        "priority_research_count": sum(row.get("quant_status") == "PRIORITY_RESEARCH" for row in quant_rows),
        "secondary_research_count": sum(row.get("quant_status") == "SECONDARY_RESEARCH" for row in quant_rows),
        "strict_review_ready_count": len(strict_rows), "condition_watch_count": len(condition_rows),
        "research_watch_count": len(research_rows),
        "buy_signal_count": sum(row.get("signal_action") == "BUY_IF_TRIGGERED" for row in daily_signals),
        "hold_signal_count": sum(row.get("signal_action") == "HOLD_REVIEW" for row in daily_signals),
        "sell_signal_count": sum(row.get("signal_action") == "SELL_EXIT" for row in daily_signals),
        "watch_signal_count": sum(row.get("signal_action") == "WATCH_ONLY" for row in daily_signals),
        "industry_evidence_coverage": _coverage(deep_rows, lambda row: row.get("industry_evidence_status") in {"VERIFIED", "PARTIALLY_VERIFIED"}),
        "company_evidence_coverage": _coverage(deep_rows, lambda row: row.get("company_evidence_status") in {"VERIFIED", "PARTIALLY_VERIFIED"}),
        "exit_profile_coverage": _coverage(deep_rows, lambda row: row.get("exit_profile_status") in {"PASSED", "DEGRADED", "FAILED"}),
        "financial_coverage": _coverage(deep_rows, lambda row: _status(row.get("financial_safety_score")) != "UNKNOWN"),
        "valuation_coverage": _coverage(deep_rows, lambda row: _status(row.get("valuation_score")) != "UNKNOWN"),
        "input_exit_profile_distribution": input_exit_distribution,
        "matched_candidate_exit_profile_distribution": matched_exit_distribution,
        "universe_source_audit": source_audit, "industry_enriched_count": industry_enriched_count,
        "industry_enrichment_diagnostics": industry_diagnostics,
        "price_mapping_status_distribution": dict(Counter(str(row.get("price_mapping_status") or "UNKNOWN") for row in price_audits.values())),
        "corporate_action_detected_count": sum(bool(row.get("corporate_action_detected")) for row in price_audits.values()),
        "fundamental_fetch_warning_count": len(fundamental_errors),
        "deep_pipeline_acceptance": deep_summary.get("acceptance_enum"),
        "industry_evidence_file": str(industry_evidence_file),
        "company_evidence_file": str(company_evidence_file),
        "runtime_seconds": round(time.perf_counter() - started, 2),
        "no_auto_trade": True, "no_broker_integration": True,
        "disclaimer": DISCLAIMER,
    }
    summary["acceptance_enum"] = ACCEPTANCE_FAIL if summary["fatal_data_failure_count"] else ACCEPTANCE_STRICT if strict_rows else ACCEPTANCE_RESEARCH

    _write_csv(config.output_dir / "all_a_universe.csv", universe_rows, UNIVERSE_COLUMNS)
    _write_csv(config.output_dir / "universe_exclusion_audit.csv", universe_audit)
    (config.output_dir / "universe_source_audit.json").write_text(json.dumps(source_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(config.output_dir / "board_distribution.csv", [{"board": key, "count": value} for key, value in board_distribution.items()], ["board", "count"])
    _write_csv(config.output_dir / "price_mapping_audit.csv", [{"code": code, **audit} for code, audit in price_audits.items()], ["code", *PRICE_AUDIT_COLUMNS[1:]])
    _write_csv(config.output_dir / "all_a_quant_screen.csv", quant_rows)
    _write_csv(config.output_dir / "top80_evidence_queue.csv", top80)
    _write_csv(config.output_dir / "top30_deep_review.csv", deep_rows[: config.deep_review_size])
    _write_csv(config.output_dir / "strict_review_ready.csv", strict_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "condition_watch.csv", condition_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "research_watch.csv", research_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "tomorrow_watchlist.csv", watchlist, PLAN_COLUMNS)
    _write_csv(config.output_dir / "daily_signals.csv", daily_signals, DAILY_SIGNAL_COLUMNS)
    _write_csv(
        config.output_dir / "buy_signals.csv",
        [row for row in daily_signals if row.get("signal_action") == "BUY_IF_TRIGGERED"],
        DAILY_SIGNAL_COLUMNS,
    )
    _write_csv(
        config.output_dir / "sell_signals.csv",
        [row for row in daily_signals if row.get("signal_action") == "SELL_EXIT"],
        DAILY_SIGNAL_COLUMNS,
    )
    (config.output_dir / "daily_signals.json").write_text(
        json.dumps({"summary": summary, "signals": daily_signals}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (config.output_dir / "daily_signals.md").write_text(
        _daily_signals_markdown(summary, daily_signals), encoding="utf-8",
    )
    _write_csv(config.output_dir / "opportunity_changes.csv", changes)
    _write_csv(config.output_dir / "evidence_changes.csv", evidence_changes)
    (config.output_dir / "candidate_upgrade_report.md").write_text(_change_markdown("候选升级变化", changes, {"NEW_STRICT_REVIEW_READY", "NEW_CONDITION_WATCH", "UPGRADED_FROM_RESEARCH", "TREND_NONE_TO_WEAK", "TREND_WEAK_TO_MEDIUM", "REAL_RR_IMPROVED"}), encoding="utf-8")
    (config.output_dir / "candidate_downgrade_report.md").write_text(_change_markdown("候选降级变化", changes, {"DOWNGRADED", "REMOVED", "HARD_RISK_NEW", "LOGIC_INVALIDATED"}), encoding="utf-8")
    (config.output_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.output_dir / "tomorrow_watchlist.md").write_text(_watchlist_markdown(summary, watchlist), encoding="utf-8")
    if config.forward_ledger_file.exists():
        shutil.copyfile(config.forward_ledger_file, config.output_dir / "forward_observation_ledger.csv")
    else:
        _write_csv(config.output_dir / "forward_observation_ledger.csv", [])
    quality_rows = [
        {"stage": "price", "code": key.split(":")[0], "status": "FAILED", "issue": key, "detail": value}
        for key, value in price_errors.items()
    ] + [
        {"stage": "fundamental", "code": code, "status": "WARNING", "issue": "provider_warning", "detail": value}
        for code, value in fundamental_errors.items()
    ] + universe_audit
    _write_csv(config.output_dir / "data_quality_audit.csv", quality_rows)
    manifest = {path.name: _hash_file(path) for path in sorted(config.output_dir.iterdir()) if path.is_file()}
    (config.output_dir / "report_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return config.output_dir, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run unified Shanghai/Shenzhen all-A production research scan.")
    parser.add_argument("--as-of-date")
    parser.add_argument("--next-trade-date")
    parser.add_argument("--output-dir")
    parser.add_argument("--stock-pool-output")
    parser.add_argument("--board-rules", default="config/board_risk_rules.yaml")
    parser.add_argument("--max-workers", type=int, default=20)
    parser.add_argument("--evidence-queue-size", type=int, default=80)
    parser.add_argument("--deep-review-size", type=int, default=30)
    parser.add_argument("--max-watchlist", type=int, default=15)
    parser.add_argument("--fundamental-limit", type=int, default=30)
    parser.add_argument("--industry-evidence-file", default="data/user_supplied/industry_cycle_evidence.csv")
    parser.add_argument("--company-evidence-file", default="data/user_supplied/company_cycle_evidence.csv")
    parser.add_argument("--industry-evidence-schema", default="config/industry_evidence_schema.yaml")
    parser.add_argument("--industry-alias-map", default="config/industry_alias_map.yaml")
    parser.add_argument("--exit-profile-file", default="data/opportunity_snapshots/exit_profile.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.as_of_date) != bool(args.next_trade_date):
        raise SystemExit("--as-of-date and --next-trade-date must be supplied together")
    if args.as_of_date:
        as_of = coerce_date(args.as_of_date)
        next_trade_date = coerce_date(args.next_trade_date)
    else:
        as_of, next_trade_date = resolve_scan_dates()
    if next_trade_date <= as_of:
        raise SystemExit("--next-trade-date must be later than --as-of-date")
    output_dir = Path(args.output_dir or f"reports/all_a_full_scan/{next_trade_date:%Y%m%d}")
    stock_pool_output = Path(args.stock_pool_output or f"stock_pools/all_a_universe_{as_of:%Y%m%d}.csv")
    config = AllAScanConfig(
        as_of=as_of, next_trade_date=next_trade_date, output_dir=output_dir,
        stock_pool_output=stock_pool_output, board_rules_file=Path(args.board_rules),
        max_workers=args.max_workers, evidence_queue_size=args.evidence_queue_size,
        deep_review_size=args.deep_review_size, max_watchlist=args.max_watchlist,
        fundamental_limit=args.fundamental_limit,
    )
    output, summary = run_scan(
        config, industry_evidence_file=args.industry_evidence_file,
        company_evidence_file=args.company_evidence_file,
        industry_evidence_schema_file=args.industry_evidence_schema,
        industry_alias_map_file=args.industry_alias_map,
        exit_profile_file=args.exit_profile_file,
    )
    print(f"output_dir={output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("acceptance_enum") != ACCEPTANCE_FAIL else 2


if __name__ == "__main__":
    raise SystemExit(main())
