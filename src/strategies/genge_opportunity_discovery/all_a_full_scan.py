"""Unified Shanghai/Shenzhen A-share daily production research scan.

Long-horizon indicators and price-plan geometry use point-in-time qfq history.
Plan levels are mapped to raw tradable prices and rounded on the one-fen raw
tick only at the plan origin. The module never connects to brokers or orders.
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
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yaml

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame
from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_cycle_bottom.industry_evidence import load_evidence_csv, load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery.pipeline import RULE_VERSION, run_opportunity_discovery
from src.strategies.genge_opportunity_discovery.exit_profile import (
    HIGH_CONFIDENCE_SAMPLE_COUNT,
    MAX_RUN_GAP_OUTCOME_RATIO,
    MIN_PROFILE_SAMPLE_COUNT,
    MIN_OUTCOME_REPLAY_COVERAGE_RATIO,
    MIN_RECENT_2Y_SAMPLE_COUNT,
    fetch_extended_adjusted_histories,
    refresh_exit_profiles_from_price_history,
)
from src.strategies.genge_opportunity_discovery.real_world_signals import (
    build_industry_regimes,
    build_market_regime,
    enrich_real_world_signals,
    history_snapshot,
    price_volume_state,
)
from src.strategies.genge_opportunity_discovery.live_exit_policy import (
    DAILY_SIGNAL_EXECUTION_TIMING,
    LIVE_BALANCED_EXIT_POLICY_VERSION,
    evaluate_live_balanced_v7_exit,
    is_one_price_bar,
    raw_tick_round,
)
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
EXIT_VALIDATION_REFERENCE_PER_BOARD = 12
EXIT_VALIDATION_REFERENCE_SELECTION_VERSION = "fixed_partition_industry_diverse_v2"
EXIT_PROFILE_EXPLORATION_LIMIT = 40
EXIT_PROFILE_EXPLORATION_SELECTION_VERSION = "weekly_industry_rotation_v1"
MIN_EXIT_HISTORY_COVERAGE_RATIO = 0.75
ENTRY_TRIGGER_WINDOW_SESSIONS = 10
SIGNAL_STATE_SCHEMA_VERSION = 4
SIGNAL_LIFECYCLE_RULE_VERSION = "all_a_signal_lifecycle_v5_executable_entry_exit"

MARKET_INDEX_RECORDS = {
    "上证指数": {"code": "000001", "exchange": "SSE"},
    "深证成指": {"code": "399001", "exchange": "SZSE"},
    "创业板指": {"code": "399006", "exchange": "SZSE"},
    "科创50": {"code": "000688", "exchange": "SSE"},
}
EXTERNAL_MARKET_SYMBOLS = {
    "纳斯达克综合": ("usIXIC", 1),
    "道琼斯工业": ("usDJI", 1),
    "恒生指数": ("hkHSI", 0),
}

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
    "actionability_rank", "actionability_score", "code", "stock_name", "exchange", "board", "industry",
    "classification", "user_visible_level", "latest_trade_date", "raw_latest_close",
    "adjusted_latest_close", "adjustment_ratio", "price_mapping_status",
    "price_adjustment_warning", "price_percentile_5y", "ma20", "ma60", "ma120", "ma250",
    "ma20_slope_pct", "ma60_slope_pct", "trend_confirmation_level", "valuation_score",
    "financial_safety_score", "industry_evidence_status", "company_evidence_status",
    "hard_logic_level", "exit_profile_status", "exit_profile_sample_count",
    "exit_profile_entry_mode", "exit_profile_confidence", "recent_2y_sample_count", "profile_data_end_date", "profile_rule_version",
    "profile_validation_scope", "profile_position_multiplier",
    "exit_profile_blocker_detail",
    "stock_profile_status", "stock_signal_count", "stock_incomplete_outcome_count",
    "stock_outcome_attempt_count", "stock_replayable_outcome_count",
    "stock_replay_excluded_outcome_count", "stock_hard_veto_outcome_count",
    "stock_corporate_action_excluded_count", "stock_run_gap_excluded_count",
    "stock_right_censored_count", "stock_outcome_replay_coverage_ratio",
    "stock_run_gap_outcome_ratio", "stock_replay_quality_passed",
    "stock_recent_2y_sample_count",
    "stock_avg_net_return_60d", "stock_recent_avg_net_return_60d",
    "stock_win_rate_60d", "stock_avg_drawdown_60d", "stock_recent_stability_passed",
    "cohort_key", "cohort_profile_status", "cohort_period_count",
    "cohort_recent_2y_period_count", "cohort_unique_code_count",
    "cohort_recent_2y_unique_code_count", "cohort_member_sample_count",
    "cohort_avg_net_return_60d", "cohort_return_lower_bound_60d",
    "cohort_positive_period_rate_60d", "cohort_avg_drawdown_60d",
    "cohort_tail_drawdown_60d", "cohort_member_win_rate_60d",
    "cohort_member_tail_return_60d", "cohort_member_tail_drawdown_60d",
    "cohort_max_code_period_share", "cohort_code_concentration_passed",
    "cohort_outcome_end_complete", "cohort_invalid_outcome_end_count",
    "cohort_outcome_attempt_count", "cohort_replayable_outcome_count",
    "cohort_replay_excluded_outcome_count", "cohort_hard_veto_outcome_count",
    "cohort_corporate_action_excluded_count", "cohort_run_gap_excluded_count",
    "cohort_right_censored_count", "cohort_outcome_replay_coverage_ratio",
    "cohort_run_gap_outcome_ratio", "cohort_replay_quality_passed",
    "cohort_excluded_target_code", "cohort_recent_avg_net_return_60d",
    "cohort_independence_passed", "cohort_recent_stability_passed",
    "stock_negative_veto_clear",
    "exit_profile_freshness_days", "exit_profile_rule_version_match",
    "exit_profile_freshness_passed", "exit_profile_data_version",
    "exit_profile_data_traceable", "exit_profile_validation_scope_valid",
    "strict_official_evidence_count",
    "strict_official_evidence_domains", "strict_official_evidence_passed",
    "market_regime_status", "market_regime_score", "market_position_multiplier",
    "external_risk_level", "industry_regime_status", "industry_regime_score",
    "industry_regime_sample_count", "price_volume_state", "price_volume_score",
    "price_volume_reasons", "event_risk_level", "event_scan_status", "event_negative_evidence_count",
    "event_critical_evidence_count", "event_conflict_count", "event_risk_reasons",
    "real_world_score", "real_world_gate_passed", "real_world_risk_flags",
    "pullback_entry_low", "pullback_entry_high",
    "pullback_stop_price", "pullback_logic_invalidation_price", "pullback_target_1",
    "pullback_target_2", "pullback_real_reward_risk", "pullback_status",
    "breakout_trigger_price", "breakout_confirmation_high", "breakout_max_chase_price",
    "breakout_required_volume", "breakout_stop_price", "breakout_logic_invalidation_price",
    "breakout_target_1", "breakout_target_2", "breakout_real_reward_risk", "breakout_status",
    "theoretical_target_1", "theoretical_target_2", "real_reward_risk_ratio",
    "preferred_plan", "risk_budget_initial_position_pct", "risk_budget_max_position_pct",
    "classification_missing_conditions", "strict_gate_fail_count", "strict_gate_failed",
    "missing_conditions", "top_risks", "upgrade_conditions", "cancel_conditions",
    "evidence_urls", "disclaimer",
]

DAILY_SIGNAL_COLUMNS = [
    "signal_date", "valid_for_trade_date", "code", "stock_name", "signal_action",
    "signal_label", "previous_level", "current_level", "signal_reason",
    "signal_data_status", "signal_bar_processed",
    "previous_lifecycle_state", "current_lifecycle_state",
    "trigger_observed_today", "breakout_confirmation_observed_today",
    "position_confirmation_required",
    "actionability_rank", "latest_trade_date", "latest_price", "threshold_observation_price",
    "preferred_plan", "plan_id", "plan_rule_version",
    "signal_plan_origin_trade_date", "signal_plan_adjustment_ratio",
    "signal_plan_adjustment_ratio_status", "signal_plan_adjustment_ratio_current",
    "signal_input_version",
    "entry_plan_age_sessions", "breakout_required_volume",
    "entry_low", "entry_high", "stop_price", "logic_invalidation_price",
    "target_1", "target_2", "real_reward_risk_ratio",
    "cancel_conditions",
    "assumed_entry_price", "entry_observation_trade_date",
    "entry_reference_adjusted_price", "exit_policy_adjusted_stop_price",
    "entry_adjustment_ratio", "entry_date_adjustment_ratio_status",
    "entry_date_adjustment_ratio_current",
    "live_exit_policy_status", "live_exit_policy_reason",
    "live_exit_holding_sessions", "live_exit_effective_stop_price",
    "live_exit_reference_price",
    "exit_earliest_trade_date", "exit_execution_timing",
    "risk_budget_initial_position_pct",
    "risk_budget_max_position_pct", "market_regime_status", "market_regime_score",
    "market_position_multiplier", "industry_regime_status", "industry_regime_score",
    "industry_regime_sample_count",
    "exit_profile_status", "exit_profile_entry_mode", "profile_validation_scope",
    "profile_position_multiplier",
    "external_risk_level", "price_volume_state", "event_risk_level", "event_scan_status",
    "real_world_score", "real_world_gate_passed", "real_world_risk_flags",
    "evidence_urls", "rule_version",
    "no_auto_trade", "disclaimer",
]

EXECUTION_LIST_COLUMNS = [
    "valid_for_trade_date", "code", "stock_name", "execution_action", "preferred_plan",
    "plan_id", "plan_rule_version",
    "trigger_condition", "entry_low", "entry_high", "max_buy_price", "required_volume",
    "stop_price", "logic_invalidation_price", "target_1", "target_2", "real_reward_risk_ratio",
    "risk_budget_initial_position_pct", "risk_budget_max_position_pct", "position_rule",
    "cancel_conditions", "industry_evidence_status", "company_evidence_status",
    "hard_logic_level", "exit_profile_status", "exit_profile_entry_mode",
    "profile_validation_scope", "profile_position_multiplier",
    "market_regime_status", "market_regime_score", "market_position_multiplier",
    "external_risk_level", "industry_regime_status", "industry_regime_score",
    "industry_regime_sample_count",
    "price_volume_state", "event_risk_level", "event_scan_status", "real_world_score",
    "real_world_gate_passed", "real_world_risk_flags",
    "evidence_urls", "rule_version", "no_auto_trade", "disclaimer",
]

TOP5_COLUMNS = [
    "candidate_rank", "candidate_action", "candidate_reason", "formal_buy_eligible",
    "strict_safety_blocker_count", "strict_gate_failure_family_count", *PLAN_COLUMNS,
]

INDUSTRY_REGIME_COLUMNS = [
    "industry", "status", "score", "sample_count", "advance_ratio",
    "median_return_1d_pct", "above_ma20_ratio", "distribution_ratio",
]

MONITORED_SIGNAL_LIFECYCLES = {"ENTRY_TRIGGER_OBSERVED", "POSITION_REVIEW"}
EXIT_CONFIRMATION_LIFECYCLES = {"EXIT_THRESHOLD_BREACHED"}
TERMINAL_ENTRY_LIFECYCLES = {"ENTRY_CANCELLED", "ENTRY_INVALIDATED"}
ACTIVE_SIGNAL_LIFECYCLES = (
    MONITORED_SIGNAL_LIFECYCLES
    | EXIT_CONFIRMATION_LIFECYCLES
    | {"BREAKOUT_CONFIRMED_ENTRY_PENDING"}
)
FROZEN_SIGNAL_PLAN_FIELDS = (
    "preferred_plan", "real_reward_risk_ratio", "cancel_conditions",
    "pullback_entry_low", "pullback_entry_high", "pullback_stop_price",
    "pullback_logic_invalidation_price", "pullback_target_1", "pullback_target_2",
    "pullback_real_reward_risk", "pullback_status",
    "breakout_trigger_price", "breakout_confirmation_high", "breakout_max_chase_price",
    "breakout_required_volume", "breakout_stop_price", "breakout_logic_invalidation_price",
    "breakout_target_1", "breakout_target_2", "breakout_real_reward_risk", "breakout_status",
    "plan_id", "plan_rule_version", "signal_plan_origin_trade_date",
    "signal_plan_adjustment_ratio",
    "entry_plan_age_sessions", "assumed_entry_price", "entry_observation_trade_date",
    "entry_reference_adjusted_price", "exit_policy_adjusted_stop_price",
    "entry_adjustment_ratio", "entry_setup_trend_confirmation_level",
    "live_exit_policy_name", "live_exit_policy_version",
)


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
    external_context_date: date | None = None
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
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


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


def fetch_tencent_symbol_history(
    symbol: str, *, as_of: date, timeout: int = 15,
) -> pd.DataFrame:
    """Fetch an index proxy while tolerating Tencent response-key aliases."""

    url = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"
    response = _get_with_retry(
        url,
        params={"param": f"{symbol},day,,{as_of:%Y-%m-%d},120"},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"},
        timeout=timeout,
    )
    payload = response.json().get("data") or {}
    if not isinstance(payload, Mapping) or not payload:
        return pd.DataFrame()
    item = payload.get(symbol)
    if not isinstance(item, Mapping):
        item = next((value for value in payload.values() if isinstance(value, Mapping)), {})
    return _parse_tencent_rows(item.get("day") or [])


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


def price_mapping_ratio_at_date(
    adjusted: pd.DataFrame, raw: pd.DataFrame, *, trade_date: Any,
) -> float | None:
    """Return the raw/qfq close ratio for one exact historical trade date."""

    target = _safe_trade_date(trade_date)
    if target is None:
        return None
    adjusted_source = adjusted.reset_index(drop=True).copy()
    if "date" in adjusted_source.columns and "adjustment_ratio" in adjusted_source.columns:
        adjusted_source["date"] = pd.to_datetime(
            adjusted_source["date"], errors="coerce",
        ).dt.date
        exact = adjusted_source.loc[adjusted_source["date"] == target]
        if len(exact) == 1:
            ratio = _safe_float(exact.iloc[0].get("adjustment_ratio"))
            return ratio if ratio is not None and ratio > 0 else None
    qfq = prepare_price_frame(adjusted)
    unadjusted = prepare_price_frame(raw)
    if qfq.empty or unadjusted.empty:
        return None
    common = qfq.loc[qfq["date"] == target, ["date", "close"]].merge(
        unadjusted.loc[unadjusted["date"] == target, ["date", "close"]],
        on="date", suffixes=("_qfq", "_raw"),
    )
    if len(common) != 1:
        return None
    adjusted_close = _safe_float(common.iloc[0]["close_qfq"])
    raw_close = _safe_float(common.iloc[0]["close_raw"])
    if adjusted_close is None or raw_close is None or adjusted_close <= 0 or raw_close <= 0:
        return None
    ratio = raw_close / adjusted_close
    return ratio if math.isfinite(ratio) and ratio > 0 else None


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
    price_candidate_count = 0
    price_failure_codes: set[str] = set()
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
        if not reason:
            price_candidate_count += 1
        if not reason and any(key.startswith(f"{code}:") for key in errors):
            reason = "price_fetch_failed"
            price_failure_codes.add(code)
        if not raw.empty:
            local["latest_trade_date"] = raw.iloc[-1]["date"].isoformat()
            local["liquidity"] = round(float(pd.to_numeric(raw.tail(20)["amount"], errors="coerce").mean()), 2)
        if not reason and (raw.empty or raw.iloc[-1]["date"] != as_of):
            reason = "suspended_or_latest_trade_date_mismatch"
            local["is_suspended"] = True
        if not reason and price_audit.get("price_mapping_status") != "OK":
            reason = "price_mapping_failed"
            price_failure_codes.add(code)
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
    recoverable_count = len(price_failure_codes)
    systemic_failure_threshold = max(50, math.floor(max(1, price_candidate_count) * .05))
    counts["recoverable_price_failure_count"] = recoverable_count
    counts["price_data_candidate_count"] = price_candidate_count
    counts["price_data_coverage_ratio"] = round(
        1.0 - recoverable_count / max(1, price_candidate_count), 6,
    )
    counts["fatal_data_failure_count"] = (
        recoverable_count if recoverable_count > systemic_failure_threshold else 0
    )
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
        adjusted_daily = history_snapshot(adjusted, as_of=as_of)
        raw_daily = history_snapshot(raw, as_of=as_of)
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
        quant_row = {
            "code": code, "stock_name": item.get("stock_name"), "exchange": item.get("exchange"),
            "board": item.get("board"), "security_type": item.get("security_type"),
            "industry": item.get("industry"), "industry_source": item.get("industry_source"),
            "latest_trade_date": raw.iloc[-1]["date"].isoformat(), "raw_latest_close": _round_price(raw_close),
            "raw_latest_open": _round_price(_safe_float(raw.iloc[-1].get("open"))),
            "raw_latest_high": _round_price(_safe_float(raw.iloc[-1].get("high"))),
            "raw_latest_low": _round_price(_safe_float(raw.iloc[-1].get("low"))),
            "raw_latest_volume": _round(_safe_float(raw.iloc[-1].get("volume"))),
            "adjusted_latest_close": _round_price(adjusted_close),
            "adjusted_latest_open": _round_price(_safe_float(adjusted.iloc[-1].get("open"))),
            "adjusted_latest_high": _round_price(_safe_float(adjusted.iloc[-1].get("high"))),
            "adjusted_latest_low": _round_price(_safe_float(adjusted.iloc[-1].get("low"))),
            "adjusted_latest_volume": _round(_safe_float(adjusted.iloc[-1].get("volume"))),
            **dict(price_audits.get(code, {})),
            "price_percentile_5y": _round(percentile_5y), "price_percentile_1y": _round(percentile_1y),
            "ma20": _round_price(ma20), "ma60": _round_price(ma60), "ma120": _round_price(ma120), "ma250": _round_price(ma250),
            "ma20_slope_pct": _round(ma20_slope), "ma60_slope_pct": _round(ma60_slope),
            "trend_confirmation_level": trend, "relative_strength_20d": _round(rs20),
            "relative_strength_60d": _round(rs60), "return_5d_pct": _round(return_5d),
            "return_10d_pct": _round(return_10d), "liquidity": round(liquidity, 2),
            # Returns and gaps use qfq data so corporate actions cannot look like
            # panic selling. Activity and intraday location use observable raw data.
            "return_1d_pct": adjusted_daily.get("return_1d_pct"),
            "gap_open_pct": adjusted_daily.get("gap_open_pct"),
            "volume_ratio_20": raw_daily.get("volume_ratio_20"),
            "amount_ratio_20": raw_daily.get("amount_ratio_20"),
            "close_location": raw_daily.get("close_location"),
            "above_ma20": adjusted_daily.get("above_ma20"),
            "above_ma60": adjusted_daily.get("above_ma60"),
            "quant_score": quant_score, "quant_status": status, "hard_blockers": ";".join(hard),
            "soft_blockers": ";".join(sorted(set(soft))), "rejection_reasons": ";".join(sorted(set(hard + soft))),
        }
        quant_row.update(price_volume_state(quant_row))
        rows.append(quant_row)
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
    evidence_urls: list[str], *, adjusted_history: pd.DataFrame | None = None,
) -> dict[str, Any]:
    raw = prepare_price_frame(raw_history)
    history = prepare_price_frame(
        adjusted_history if adjusted_history is not None else raw_history,
    )
    if raw.empty or history.empty:
        raise ValueError("price plan requires non-empty raw and qfq history")
    close = float(history.iloc[-1]["close"])
    latest_date = coerce_date(history.iloc[-1]["date"])
    raw_row = raw[raw["date"] == latest_date]
    if raw_row.empty:
        raise ValueError("price plan raw/qfq latest trade dates do not match")
    raw_close = float(raw_row.iloc[-1]["close"])
    exact_ratio = (
        _safe_float(history.iloc[-1].get("adjustment_ratio"))
        if "adjustment_ratio" in history.columns else None
    )
    adjustment_ratio = (
        exact_ratio if exact_ratio is not None and exact_ratio > 0
        else raw_close / close if close > 0 else 0.0
    )
    if not math.isfinite(adjustment_ratio) or adjustment_ratio <= 0:
        raise ValueError("price plan raw/qfq mapping ratio is invalid")

    def raw_price(adjusted_value: float) -> float:
        return raw_tick_round(adjusted_value * adjustment_ratio)

    def raw_audit(levels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **level,
                "price": raw_price(float(level["price"])),
                "prominence": round(
                    float(level.get("prominence") or 0.0) * adjustment_ratio, 4,
                ),
            }
            for level in levels
        ]

    adjusted_tick = .01 / adjustment_ratio
    atr14 = _atr(history) or max(adjusted_tick, close * .03)
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
        stop = min(entry_low - adjusted_tick, support - .75 * atr14)
        invalidation = min(stop, support - 1.05 * atr14)
        all_levels, eligible = resistance_levels(history, atr14=atr14, entry=entry_high)
        pullback_resistance_audit = raw_audit(all_levels)
        if len(eligible) >= 1:
            target_1 = eligible[0]["price"]
            target_2 = eligible[1]["price"] if len(eligible) > 1 else target_1 + max(atr14, target_1 * .02)
            values = [raw_price(value) for value in (entry_low, entry_high, stop, invalidation, target_1, target_2)]
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
        "breakout_trigger_price": raw_price(trigger),
        "breakout_confirmation_high": raw_price(confirmation_high),
        "breakout_max_chase_price": raw_price(max_chase),
        "breakout_required_volume": round(avg_volume_20 * board_rule.breakout_volume_ratio, 0),
        "breakout_stop_price": raw_price(breakout_stop),
        "breakout_logic_invalidation_price": raw_price(breakout_invalidation),
        "breakout_target_1": "", "breakout_target_2": "", "breakout_real_reward_risk": "",
        "breakout_status": "NO_ELIGIBLE_REAL_RESISTANCE",
    }
    if breakout_eligible:
        target_1 = breakout_eligible[0]["price"]
        target_2 = breakout_eligible[1]["price"] if len(breakout_eligible) > 1 else target_1 + max(atr14, target_1 * .02)
        entry_p, max_chase_p, stop_p, target_1_p, target_2_p = [
            raw_price(value) for value in (trigger, max_chase, breakout_stop, target_1, target_2)
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
    raw_max_chase = float(breakout["breakout_max_chase_price"])
    raw_breakout_stop = float(breakout["breakout_stop_price"])
    theoretical_risk = max(.01, raw_max_chase - raw_breakout_stop)
    return {
        "latest_trade_date": latest_date.isoformat(), "raw_latest_close": _round_price(raw_close),
        **pullback, **breakout,
        "theoretical_target_1": _round_price(raw_max_chase + 1.5 * theoretical_risk),
        "theoretical_target_2": _round_price(raw_max_chase + 2.5 * theoretical_risk),
        "real_reward_risk_ratio": round(preferred_rr, 2) if preferred_rr is not None else "",
        "preferred_plan": preferred,
        "pullback_resistance_audit": pullback_resistance_audit,
        "breakout_resistance_audit": raw_audit(breakout_all),
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
        confidence = str(item.get("profile_confidence") or (
            "HIGH" if sample_count >= HIGH_CONFIDENCE_SAMPLE_COUNT
            else "MEDIUM" if sample_count >= MIN_PROFILE_SAMPLE_COUNT else "LOW"
        ))
        rule_version = str(item.get("profile_rule_version") or "").strip()
        data_version = str(
            item.get("profile_data_version") or item.get("data_version")
            or item.get("source_signal_details") or ""
        ).strip()
        profile = {
            "code": code,
            "exit_profile_status": status, "exit_profile_sample_count": sample_count,
            "exit_profile_entry_mode": str(item.get("exit_profile_entry_mode") or ""),
            "recent_2y_sample_count": recent_2y,
            "60d_exit_net_return": item.get("60d_exit_net_return") or item.get("avg_balanced_exit_net_return_60d") or "",
            "60d_exit_win_rate": item.get("60d_exit_win_rate") or item.get("win_rate_balanced_exit_60d") or "",
            "60d_exit_outperform_rate": item.get("60d_exit_outperform_rate") or "",
            "60d_exit_drawdown": item.get("60d_exit_drawdown") or item.get("avg_balanced_exit_max_drawdown_60d") or item.get("avg_balanced_exit_max_drawdown_250d") or "",
            "250d_exit_drawdown": item.get("250d_exit_drawdown") or item.get("avg_balanced_exit_max_drawdown_250d") or "",
            "exit_profile_confidence": confidence, "profile_data_end_date": data_end_date,
            "profile_generated_at": generated_at, "profile_rule_version": rule_version,
            "exit_profile_data_version": data_version,
            "profile_validation_scope": str(item.get("profile_validation_scope") or ""),
            "profile_position_multiplier": _safe_float(item.get("profile_position_multiplier")),
            "stock_profile_status": str(item.get("stock_profile_status") or ""),
            "stock_signal_count": int(_safe_float(item.get("stock_signal_count")) or 0),
            "stock_incomplete_outcome_count": int(
                _safe_float(item.get("stock_incomplete_outcome_count")) or 0
            ),
            "stock_outcome_attempt_count": int(
                _safe_float(item.get("stock_outcome_attempt_count")) or 0
            ),
            "stock_replayable_outcome_count": int(
                _safe_float(item.get("stock_replayable_outcome_count")) or 0
            ),
            "stock_replay_excluded_outcome_count": int(
                _safe_float(item.get("stock_replay_excluded_outcome_count")) or 0
            ),
            "stock_hard_veto_outcome_count": int(
                _safe_float(item.get("stock_hard_veto_outcome_count")) or 0
            ),
            "stock_corporate_action_excluded_count": int(
                _safe_float(item.get("stock_corporate_action_excluded_count")) or 0
            ),
            "stock_run_gap_excluded_count": int(
                _safe_float(item.get("stock_run_gap_excluded_count")) or 0
            ),
            "stock_right_censored_count": int(
                _safe_float(item.get("stock_right_censored_count")) or 0
            ),
            "stock_outcome_replay_coverage_ratio": _safe_float(
                item.get("stock_outcome_replay_coverage_ratio")
            ),
            "stock_run_gap_outcome_ratio": _safe_float(
                item.get("stock_run_gap_outcome_ratio")
            ),
            "stock_replay_quality_passed": _bool_value(
                item.get("stock_replay_quality_passed")
            ),
            "stock_recent_2y_sample_count": int(_safe_float(item.get("stock_recent_2y_sample_count")) or 0),
            "stock_avg_net_return_60d": item.get("stock_avg_net_return_60d") or "",
            "stock_recent_avg_net_return_60d": item.get("stock_recent_avg_net_return_60d") or "",
            "stock_win_rate_60d": item.get("stock_win_rate_60d") or "",
            "stock_avg_drawdown_60d": item.get("stock_avg_drawdown_60d") or "",
            "stock_recent_stability_passed": _bool_value(item.get("stock_recent_stability_passed")),
            "cohort_key": str(item.get("cohort_key") or ""),
            "cohort_profile_status": str(item.get("cohort_profile_status") or ""),
            "cohort_period_count": int(_safe_float(item.get("cohort_period_count")) or 0),
            "cohort_recent_2y_period_count": int(_safe_float(item.get("cohort_recent_2y_period_count")) or 0),
            "cohort_unique_code_count": int(_safe_float(item.get("cohort_unique_code_count")) or 0),
            "cohort_recent_2y_unique_code_count": int(_safe_float(item.get("cohort_recent_2y_unique_code_count")) or 0),
            "cohort_member_sample_count": int(_safe_float(item.get("cohort_member_sample_count")) or 0),
            "cohort_avg_net_return_60d": item.get("cohort_avg_net_return_60d") or "",
            "cohort_return_lower_bound_60d": item.get("cohort_return_lower_bound_60d") or "",
            "cohort_positive_period_rate_60d": item.get("cohort_positive_period_rate_60d") or "",
            "cohort_avg_drawdown_60d": item.get("cohort_avg_drawdown_60d") or "",
            "cohort_tail_drawdown_60d": item.get("cohort_tail_drawdown_60d") or "",
            "cohort_member_win_rate_60d": item.get("cohort_member_win_rate_60d") or "",
            "cohort_member_tail_return_60d": item.get("cohort_member_tail_return_60d") or "",
            "cohort_member_tail_drawdown_60d": item.get("cohort_member_tail_drawdown_60d") or "",
            "cohort_max_code_period_share": item.get("cohort_max_code_period_share") or "",
            "cohort_code_concentration_passed": _bool_value(
                item.get("cohort_code_concentration_passed"),
            ),
            "cohort_outcome_end_complete": _bool_value(
                item.get("cohort_outcome_end_complete"),
            ),
            "cohort_invalid_outcome_end_count": int(
                _safe_float(item.get("cohort_invalid_outcome_end_count")) or 0
            ),
            "cohort_outcome_attempt_count": int(
                _safe_float(item.get("cohort_outcome_attempt_count")) or 0
            ),
            "cohort_replayable_outcome_count": int(
                _safe_float(item.get("cohort_replayable_outcome_count")) or 0
            ),
            "cohort_replay_excluded_outcome_count": int(
                _safe_float(item.get("cohort_replay_excluded_outcome_count")) or 0
            ),
            "cohort_hard_veto_outcome_count": int(
                _safe_float(item.get("cohort_hard_veto_outcome_count")) or 0
            ),
            "cohort_corporate_action_excluded_count": int(
                _safe_float(item.get("cohort_corporate_action_excluded_count")) or 0
            ),
            "cohort_run_gap_excluded_count": int(
                _safe_float(item.get("cohort_run_gap_excluded_count")) or 0
            ),
            "cohort_right_censored_count": int(
                _safe_float(item.get("cohort_right_censored_count")) or 0
            ),
            "cohort_outcome_replay_coverage_ratio": _safe_float(
                item.get("cohort_outcome_replay_coverage_ratio")
            ),
            "cohort_run_gap_outcome_ratio": _safe_float(
                item.get("cohort_run_gap_outcome_ratio")
            ),
            "cohort_replay_quality_passed": _bool_value(
                item.get("cohort_replay_quality_passed")
            ),
            "cohort_excluded_target_code": _normalize_code(
                item.get("cohort_excluded_target_code"),
            ),
            "cohort_recent_avg_net_return_60d": item.get("cohort_recent_avg_net_return_60d") or "",
            "cohort_independence_passed": _bool_value(item.get("cohort_independence_passed")),
            "cohort_recent_stability_passed": _bool_value(item.get("cohort_recent_stability_passed")),
            "stock_negative_veto_clear": _bool_value(item.get("stock_negative_veto_clear")),
        }
        result[code] = profile
        distribution[status] += 1
    return result, dict(distribution)


def _current_passed_profile_codes(
    candidates: Iterable[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return PASSED profile codes that are still in the current research queue."""
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        code = _normalize_code(candidate.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        if str(profiles.get(code, {}).get("exit_profile_status")) == "PASSED":
            result.append(code)
    return result


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

    def metric(field: str) -> Any:
        value = profile.get(field)
        return "NA" if value is None or str(value).strip().lower() in {"", "nan"} else value

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
    data_digest = data_version.removeprefix("sha256:")
    data_traceable = bool(
        data_version.startswith("sha256:")
        and len(data_digest) == 64
        and all(character in "0123456789abcdef" for character in data_digest.lower())
    )
    scope = str(profile.get("profile_validation_scope") or "").strip()
    position_multiplier = _safe_float(profile.get("profile_position_multiplier"))
    status = str(profile.get("exit_profile_status") or "NOT_AVAILABLE")
    stock_scope_valid = bool(
        scope == "STOCK_SPECIFIC"
        and position_multiplier == 1.0
        and str(profile.get("stock_profile_status") or "") == "PASSED"
        and int(_safe_float(profile.get("stock_signal_count")) or 0)
        >= MIN_PROFILE_SAMPLE_COUNT
        and int(_safe_float(profile.get("stock_hard_veto_outcome_count")) or 0) == 0
        and _bool_value(profile.get("stock_replay_quality_passed"))
        and int(_safe_float(profile.get("stock_recent_2y_sample_count")) or 0)
        >= MIN_RECENT_2Y_SAMPLE_COUNT
        and _bool_value(profile.get("stock_recent_stability_passed"))
    )
    excluded_target = _normalize_code(profile.get("cohort_excluded_target_code"))
    profile_code = _normalize_code(profile.get("code"))
    cohort_scope_valid = bool(
        scope == "ENTRY_MODE_COHORT_INDEPENDENT_REFERENCE"
        and position_multiplier is not None and 0.0 < position_multiplier <= .5
        and str(profile.get("cohort_profile_status") or "") == "PASSED"
        and int(_safe_float(profile.get("cohort_period_count")) or 0)
        >= MIN_PROFILE_SAMPLE_COUNT
        and int(_safe_float(profile.get("cohort_recent_2y_period_count")) or 0)
        >= MIN_RECENT_2Y_SAMPLE_COUNT
        and _bool_value(profile.get("cohort_independence_passed"))
        and _bool_value(profile.get("cohort_recent_stability_passed"))
        and _bool_value(profile.get("cohort_code_concentration_passed"))
        and int(_safe_float(profile.get("cohort_hard_veto_outcome_count")) or 0) == 0
        and _bool_value(profile.get("cohort_replay_quality_passed"))
        and _bool_value(profile.get("stock_negative_veto_clear"))
        and (not excluded_target or excluded_target == profile_code)
    )
    scope_valid = status != "PASSED" or stock_scope_valid or cohort_scope_valid
    stock_count = int(_safe_float(profile.get("stock_signal_count")) or 0)
    stock_incomplete_count = int(
        _safe_float(profile.get("stock_incomplete_outcome_count")) or 0
    )
    stock_recent_count = int(_safe_float(profile.get("stock_recent_2y_sample_count")) or 0)
    stock_replay_coverage = _safe_float(
        profile.get("stock_outcome_replay_coverage_ratio")
    )
    stock_run_gap_ratio = _safe_float(profile.get("stock_run_gap_outcome_ratio"))
    stock_hard_veto_count = int(
        _safe_float(profile.get("stock_hard_veto_outcome_count")) or 0
    )
    cohort_period_count = int(_safe_float(profile.get("cohort_period_count")) or 0)
    cohort_recent_count = int(
        _safe_float(profile.get("cohort_recent_2y_period_count")) or 0
    )
    cohort_replay_coverage = _safe_float(
        profile.get("cohort_outcome_replay_coverage_ratio")
    )
    cohort_run_gap_ratio = _safe_float(profile.get("cohort_run_gap_outcome_ratio"))
    cohort_hard_veto_count = int(
        _safe_float(profile.get("cohort_hard_veto_outcome_count")) or 0
    )
    exit_profile_blocker_detail = (
        f"status={status};scope={scope or 'NONE'};"
        f"stock[{profile.get('stock_profile_status') or 'NOT_AVAILABLE'};"
        f"samples={stock_count}/{MIN_PROFILE_SAMPLE_COUNT};"
        f"incomplete={stock_incomplete_count};"
        f"replay_coverage={stock_replay_coverage if stock_replay_coverage is not None else 'NA'}"
        f"/{MIN_OUTCOME_REPLAY_COVERAGE_RATIO};"
        f"run_gap_ratio={stock_run_gap_ratio if stock_run_gap_ratio is not None else 'NA'}"
        f"/{MAX_RUN_GAP_OUTCOME_RATIO};"
        f"hard_veto={stock_hard_veto_count};"
        f"recent={stock_recent_count}/{MIN_RECENT_2Y_SAMPLE_COUNT};"
        f"avg={metric('stock_avg_net_return_60d')}%;"
        f"recent_avg={metric('stock_recent_avg_net_return_60d')}%;"
        f"win={metric('stock_win_rate_60d')}%;"
        f"recent_stable={_bool_value(profile.get('stock_recent_stability_passed'))}];"
        f"cohort[{profile.get('cohort_key') or 'NONE'};"
        f"status={profile.get('cohort_profile_status') or 'NOT_AVAILABLE'};"
        f"periods={cohort_period_count}/{MIN_PROFILE_SAMPLE_COUNT};"
        f"recent={cohort_recent_count}/{MIN_RECENT_2Y_SAMPLE_COUNT};"
        f"replay_coverage={cohort_replay_coverage if cohort_replay_coverage is not None else 'NA'}"
        f"/{MIN_OUTCOME_REPLAY_COVERAGE_RATIO};"
        f"run_gap_ratio={cohort_run_gap_ratio if cohort_run_gap_ratio is not None else 'NA'}"
        f"/{MAX_RUN_GAP_OUTCOME_RATIO};"
        f"hard_veto={cohort_hard_veto_count};"
        f"lcb={metric('cohort_return_lower_bound_60d')}%;"
        f"member_win={metric('cohort_member_win_rate_60d')}%;"
        f"recent_avg={metric('cohort_recent_avg_net_return_60d')}%;"
        f"independent={_bool_value(profile.get('cohort_independence_passed'))};"
        f"recent_stable={_bool_value(profile.get('cohort_recent_stability_passed'))}]"
    )
    enriched.update({
        "exit_profile_freshness_days": freshness_days,
        "exit_profile_rule_version_match": rule_match,
        "exit_profile_freshness_passed": freshness_passed,
        "exit_profile_data_version": data_version,
        "exit_profile_data_traceable": data_traceable,
        "exit_profile_validation_scope_valid": scope_valid,
        "exit_profile_blocker_detail": exit_profile_blocker_detail,
    })
    return enriched


def _exit_profile_strategy_health(
    exit_profile_refresh: Mapping[str, Any],
) -> dict[str, Any]:
    cohort_validations = dict(exit_profile_refresh.get("cohort_validations") or {})
    cohort_passed_count = sum(
        str(details.get("status") or "") == "PASSED"
        for details in cohort_validations.values()
    )
    candidate_passed_count = int(
        (exit_profile_refresh.get("candidate_distribution") or {}).get("PASSED", 0)
    )
    status = (
        "CANDIDATE_VALIDATED_EDGE_AVAILABLE"
        if candidate_passed_count
        else "REFERENCE_COHORT_VALIDATED_EDGE_AVAILABLE"
        if cohort_passed_count
        else "NO_VALIDATED_EXIT_EDGE"
    )
    return {
        "status": status,
        "candidate_passed_count": candidate_passed_count,
        "cohort_passed_count": cohort_passed_count,
        "cohort_count": len(cohort_validations),
        "cohort_status_distribution": dict(Counter(
            str(details.get("status") or "NOT_AVAILABLE")
            for details in cohort_validations.values()
        )),
        "cohort_independence_passed_count": sum(
            bool(details.get("independence_passed"))
            for details in cohort_validations.values()
        ),
        "cohort_recent_stability_passed_count": sum(
            bool(details.get("recent_stability_passed"))
            for details in cohort_validations.values()
        ),
        "cohort_performance_passed_count": sum(
            bool(details.get("performance_passed"))
            for details in cohort_validations.values()
        ),
        "cohort_member_performance_passed_count": sum(
            bool(details.get("member_performance_passed"))
            for details in cohort_validations.values()
        ),
        "note": (
            "NO_VALIDATED_EXIT_EDGE means the historical entry/exit evidence failed; "
            "it is not a workflow error and new formal buys must remain disabled."
        ),
    }


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
    real_world = _safe_float(row.get("real_world_score"))
    if real_world is None:
        real_world = 50.0
    return round(
        quant * .16 + trend * .13 + industry * .12 + company * .12 + financial * .13
        + valuation * .07 + exit_score * .05 + execution * .03 + rr_score * .07
        + real_world * .12,
        4,
    )


def _status(value: Any) -> str:
    return _status_from_score(value)


def classify_candidate(
    row: Mapping[str, Any], plan: Mapping[str, Any], profile: Mapping[str, Any],
    evidence_urls: list[str], *, board_rule: BoardRule,
) -> tuple[str, list[str]]:
    strict_checks = strict_candidate_checks(row, plan, profile, board_rule=board_rule)
    if all(strict_checks.values()):
        return "STRICT_REVIEW_READY", []
    hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    percentile = _safe_float(row.get("price_percentile_5y"))
    trend = str(row.get("trend_confirmation_level") or "NONE")
    adjusted_close = _safe_float(row.get("adjusted_latest_close"))
    ma60 = _safe_float(row.get("ma60"))
    financial = _status(row.get("financial_safety_score"))
    valuation = _status(row.get("valuation_score"))
    company = str(row.get("company_evidence_status") or "MISSING")
    rr = _safe_float(plan.get("real_reward_risk_ratio")) or 0.0
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
                "exit_profile_rule_version", "exit_profile_data_traceable", "exit_profile_entry_mode_match",
                "exit_profile_validation_scope", "strict_official_evidence",
                "quant_research_queue",
                "market_regime_not_red", "industry_regime_available", "industry_regime_not_crisis",
                "event_risk_known", "event_risk_not_high",
                "price_volume_not_distribution",
            )
            if not strict_checks.get(name, False)
        ]
        return "CONDITION_WATCH", missing
    if not hard and trend in {"WEAK", "MEDIUM", "STRONG"} and company in {"VERIFIED", "PARTIALLY_VERIFIED", "LEAD_ONLY"}:
        return "RESEARCH_WATCH", [name for name, passed in condition_checks.items() if not passed]
    return "NOT_QUALIFIED", [name for name, passed in condition_checks.items() if not passed]


def strict_candidate_checks(
    row: Mapping[str, Any], plan: Mapping[str, Any], profile: Mapping[str, Any], *, board_rule: BoardRule,
) -> dict[str, bool]:
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
    profile_entry_mode = str(profile.get("exit_profile_entry_mode") or "").lower()
    preferred_mode = str(plan.get("preferred_plan") or "").lower()
    rr = _safe_float(plan.get("real_reward_risk_ratio")) or 0.0
    ready_plan = plan.get("pullback_status") == "READY" or plan.get("breakout_status") == "READY"
    execution_high = str(row.get("execution_risk_quality") or "").upper() == "HIGH" or "execution_risk_high" in str(row.get("hard_reject_blockers") or "")
    value_trap_high = bool(row.get("value_trap_flag")) or "value_trap_high" in str(row.get("hard_reject_blockers") or "")
    return {
        "quant_research_queue": str(row.get("quant_status") or "") in {
            "PRIORITY_RESEARCH", "SECONDARY_RESEARCH",
        },
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
        "exit_profile_sample_count": sample_count >= MIN_PROFILE_SAMPLE_COUNT,
        "exit_profile_recent_2y_samples": int(_safe_float(profile.get("recent_2y_sample_count")) or 0) >= MIN_RECENT_2Y_SAMPLE_COUNT,
        "exit_profile_confidence": profile_confidence in {"MEDIUM", "HIGH"},
        "exit_profile_freshness": bool(profile.get("exit_profile_freshness_passed")),
        "exit_profile_rule_version": bool(profile.get("exit_profile_rule_version_match")),
        "exit_profile_data_traceable": bool(profile.get("exit_profile_data_traceable")),
        "exit_profile_entry_mode_match": bool(
            preferred_mode in {"pullback", "breakout"} and profile_entry_mode == preferred_mode
        ),
        "exit_profile_validation_scope": bool(profile.get("exit_profile_validation_scope_valid")),
        "real_rr_1_8": rr >= 1.8,
        "ready_plan": ready_plan,
        "strict_official_evidence": bool(row.get("strict_official_evidence_passed")),
        "market_regime_not_red": str(row.get("market_regime_status") or "UNKNOWN") in {"GREEN", "YELLOW"},
        "industry_regime_available": (
            str(row.get("industry_regime_status") or "UNKNOWN") != "UNKNOWN"
            and int(_safe_float(row.get("industry_regime_sample_count")) or 0) >= 5
        ),
        "industry_regime_not_crisis": str(row.get("industry_regime_status") or "UNKNOWN") != "CRISIS",
        "event_risk_known": str(row.get("event_scan_status") or "UNKNOWN") == "OK",
        "event_risk_not_high": str(row.get("event_risk_level") or "LOW") != "HIGH",
        "price_volume_not_distribution": str(row.get("price_volume_state") or "NEUTRAL") not in {
            "DISTRIBUTION", "CAPITULATION_RISK",
        },
        "execution_not_high": not execution_high,
        "value_trap_not_high": not value_trap_high,
        "price_mapping_ok": str(row.get("price_mapping_status")) == "OK",
    }


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
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"signal state exists but is unreadable: {path}") from exc
    rows = payload.get("by_code") if isinstance(payload, Mapping) else None
    if not isinstance(rows, Mapping):
        raise RuntimeError(f"signal state has no valid by_code mapping: {path}")
    schema_value = payload.get("state_schema_version") if isinstance(payload, Mapping) else None
    if schema_value not in {None, ""}:
        try:
            schema_version = int(schema_value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"signal state has an invalid schema version: {path}") from exc
        if schema_version > SIGNAL_STATE_SCHEMA_VERSION:
            raise RuntimeError(
                f"signal state schema {schema_version} is newer than supported "
                f"{SIGNAL_STATE_SCHEMA_VERSION}: {path}",
            )
    validated: dict[str, dict[str, Any]] = {}
    for raw_code, row in rows.items():
        code = _normalize_code(raw_code)
        if not code or not isinstance(row, Mapping):
            raise RuntimeError(f"signal state contains an invalid row: {path}")
        row_code = _normalize_code(row.get("code") or code)
        if row_code != code or code in validated:
            raise RuntimeError(f"signal state contains an inconsistent code: {path}")
        validated[code] = dict(row)
    return validated


def _changes(
    current: list[Mapping[str, Any]], previous_state_file: Path, *,
    state_rows: list[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    previous = _load_previous_watchlist_state(previous_state_file)
    current_by_code = {_normalize_code(row.get("code")): dict(row) for row in current}
    state_by_code = {
        _normalize_code(row.get("code")): dict(row)
        for row in (state_rows if state_rows is not None else current)
        if _normalize_code(row.get("code"))
    }
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
    state_payload = json.dumps(
        {
            "state_schema_version": SIGNAL_STATE_SCHEMA_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "by_code": state_by_code,
        },
        ensure_ascii=False, indent=2, default=str,
    )
    temporary_state_file = previous_state_file.with_suffix(
        f"{previous_state_file.suffix}.tmp",
    )
    temporary_state_file.write_text(state_payload, encoding="utf-8")
    temporary_state_file.replace(previous_state_file)
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


def _signal_context_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market_regime_status": row.get("market_regime_status"),
        "market_regime_score": row.get("market_regime_score"),
        "market_position_multiplier": row.get("market_position_multiplier"),
        "industry_regime_status": row.get("industry_regime_status"),
        "industry_regime_score": row.get("industry_regime_score"),
        "industry_regime_sample_count": row.get("industry_regime_sample_count"),
        "external_risk_level": row.get("external_risk_level"),
        "price_volume_state": row.get("price_volume_state"),
        "event_risk_level": row.get("event_risk_level"),
        "event_scan_status": row.get("event_scan_status"),
        "real_world_score": row.get("real_world_score"),
        "real_world_gate_passed": row.get("real_world_gate_passed"),
        "real_world_risk_flags": row.get("real_world_risk_flags"),
        "exit_profile_status": row.get("exit_profile_status"),
        "exit_profile_entry_mode": row.get("exit_profile_entry_mode"),
        "profile_validation_scope": row.get("profile_validation_scope"),
        "profile_position_multiplier": row.get("profile_position_multiplier"),
    }


def _previous_threshold_breached(
    before: Mapping[str, Any], latest_price: float | None, *, intraday_low: float | None = None,
) -> bool:
    plan = _signal_plan_fields(before)
    stop_price = _safe_float(plan.get("stop_price"))
    invalidation_price = _safe_float(plan.get("logic_invalidation_price"))
    stop_observation = intraday_low if intraday_low is not None else latest_price
    return bool(
        (stop_observation is not None and stop_price is not None and stop_observation <= stop_price)
        or (
            latest_price is not None
            and invalidation_price is not None
            and latest_price <= invalidation_price
        )
    )


def _safe_trade_date(value: Any) -> date | None:
    if value in {None, ""}:
        return None
    try:
        result = coerce_date(value)
    except Exception:
        return None
    return None if result is None or pd.isna(result) else result


def _market_observation_date(
    market_row: Mapping[str, Any], *, as_of: date,
) -> date | None:
    value = market_row.get("latest_trade_date")
    if value not in {None, ""}:
        return _safe_trade_date(value)
    has_price_data = any(
        market_row.get(field) not in {None, ""}
        for field in ("raw_latest_open", "raw_latest_high", "raw_latest_low", "raw_latest_close")
    )
    return as_of if has_price_data else None


def _run_gap_detected(
    before: Mapping[str, Any], market_row: Mapping[str, Any], *, as_of: date,
) -> bool:
    """Fail closed when an active plan cannot prove every intervening session was observed."""

    observed = _safe_trade_date(
        before.get("signal_observed_through_date") or before.get("latest_trade_date"),
    )
    current = _market_observation_date(market_row, as_of=as_of)
    if observed is None or current is None:
        return True
    if observed >= current:
        return bool(before.get("unresolved_signal_gap"))
    try:
        import exchange_calendars as xcals

        calendar = xcals.get_calendar("XSHG")
        sessions = calendar.sessions_in_range(observed, current)
        elapsed = sum(session.date() > observed for session in sessions)
    except Exception:
        # Fallback is deliberately conservative. It may request manual review
        # around an exchange holiday, but it cannot silently invent continuity.
        elapsed = len(pd.bdate_range(observed + timedelta(days=1), current))
    return bool(before.get("unresolved_signal_gap")) or elapsed > 1


def _new_market_bar_available(
    before: Mapping[str, Any], market_row: Mapping[str, Any], *, as_of: date,
) -> bool:
    """Do not replay the bar that was already used to create the saved plan."""

    previous_date = _safe_trade_date(
        before.get("signal_observed_through_date") or before.get("latest_trade_date"),
    )
    current_date = _market_observation_date(market_row, as_of=as_of)
    if previous_date is None or current_date is None:
        return False
    return current_date > previous_date


def _signal_input_version(
    row: Mapping[str, Any], market_row: Mapping[str, Any],
) -> str:
    plan_values = {
        field: row.get(field)
        for field in FROZEN_SIGNAL_PLAN_FIELDS
        if field not in {
            "plan_id", "plan_rule_version", "signal_plan_origin_trade_date",
            "entry_plan_age_sessions", "assumed_entry_price", "entry_observation_trade_date",
        }
    }
    payload = {
        "code": _normalize_code(row.get("code")),
        "latest_trade_date": market_row.get("latest_trade_date"),
        "ohlcv": [
            market_row.get(field)
            for field in (
                "raw_latest_open", "raw_latest_high", "raw_latest_low",
                "raw_latest_close", "raw_latest_volume",
            )
        ],
        "adjusted_bar": [
            market_row.get(field)
            for field in (
                "adjusted_latest_open", "adjusted_latest_high", "adjusted_latest_low",
                "adjusted_latest_close", "adjusted_latest_volume", "ma20", "ma60",
                "adjustment_ratio",
            )
        ],
        "historical_price_basis": {
            field: market_row.get(field)
            for field in (
                "signal_plan_adjustment_ratio_status",
                "signal_plan_adjustment_ratio_current",
                "entry_date_adjustment_ratio_status",
                "entry_date_adjustment_ratio_current",
            )
        },
        "user_visible_level": row.get("user_visible_level"),
        "missing_conditions": row.get("missing_conditions"),
        "strict_gate_failed": row.get("strict_gate_failed"),
        "preferred_plan": row.get("preferred_plan"),
        "exit_profile_entry_mode": row.get("exit_profile_entry_mode"),
        "plan": plan_values,
        "context": _signal_context_fields(row),
        "lifecycle_rule": SIGNAL_LIFECYCLE_RULE_VERSION,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"),
    ).hexdigest()
    return f"sha256:{digest}"


def _same_observation_replay(
    before: Mapping[str, Any], market_row: Mapping[str, Any], *,
    as_of: date, signal_input_version: str,
) -> bool:
    if not before.get("last_signal_action"):
        return False
    previous_date = _safe_trade_date(
        before.get("signal_observed_through_date") or before.get("latest_trade_date"),
    )
    current_date = _market_observation_date(market_row, as_of=as_of)
    if previous_date is None or current_date is None or previous_date != current_date:
        return False
    previous_input = str(before.get("last_signal_input_version") or "")
    return not previous_input or previous_input == signal_input_version


def _same_observation_input_changed(
    before: Mapping[str, Any], market_row: Mapping[str, Any], *,
    as_of: date, signal_input_version: str,
) -> bool:
    """Detect a provider correction to a bar that was already processed."""

    previous_input = str(before.get("last_signal_input_version") or "")
    if not previous_input or previous_input == signal_input_version:
        return False
    previous_date = _safe_trade_date(
        before.get("signal_observed_through_date") or before.get("latest_trade_date"),
    )
    current_date = _market_observation_date(market_row, as_of=as_of)
    return bool(previous_date is not None and previous_date == current_date)


def _signal_bar_processed(data_status: str) -> bool:
    """Whether the current market bar safely advanced the active lifecycle state."""

    return not any(
        marker in str(data_status or "")
        for marker in (
            "RUN_GAP", "LIVE_EXIT_STATE", "PRICE_BASIS",
            "SAME_OBSERVATION_DATA_CHANGED",
        )
    )


def _plan_id(row: Mapping[str, Any], *, origin_trade_date: Any) -> str:
    payload = {
        "code": _normalize_code(row.get("code")),
        "origin_trade_date": str(origin_trade_date or ""),
        "preferred_plan": row.get("preferred_plan"),
        "plan_rule_version": row.get("plan_rule_version") or RULE_VERSION,
        "plan": {
            field: row.get(field)
            for field in FROZEN_SIGNAL_PLAN_FIELDS
            if field not in {
                "plan_id", "plan_rule_version", "signal_plan_origin_trade_date",
                "entry_plan_age_sessions", "assumed_entry_price", "entry_observation_trade_date",
            }
        },
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"),
    ).hexdigest()
    return f"plan:{digest[:24]}"


def _pullback_entry_status(before: Mapping[str, Any], market_row: Mapping[str, Any]) -> str:
    """Mirror the fixed-plan historical fill convention without assuming execution."""

    preferred = str(before.get("preferred_plan") or "")
    if preferred != "pullback":
        return "NOT_APPLICABLE"
    opening = _safe_float(market_row.get("raw_latest_open"))
    low = _safe_float(market_row.get("raw_latest_low"))
    high = _safe_float(market_row.get("raw_latest_high"))
    closing = _safe_float(market_row.get("raw_latest_close"))
    entry_low = _safe_float(before.get("pullback_entry_low"))
    entry_high = _safe_float(before.get("pullback_entry_high"))
    if any(
        value is None
        for value in (opening, low, high, closing, entry_low, entry_high)
    ):
        return "UNKNOWN"
    if opening < entry_low:
        return "OPEN_BELOW_ENTRY_BAND"
    if opening <= entry_high or (low <= entry_high and high >= entry_low):
        if is_one_price_bar(
            opening=opening, high=high, low=low, close=closing,
        ):
            return "LOCKED_ONE_PRICE_UNEXECUTABLE"
        return "ENTRY_RANGE_OBSERVED"
    return "NO_TRIGGER"


def _observed_entry_price(
    before: Mapping[str, Any], market_row: Mapping[str, Any], *, entry_mode: str,
) -> float | None:
    opening = _safe_float(market_row.get("raw_latest_open"))
    if entry_mode == "breakout":
        return opening
    entry_high = _safe_float(before.get("pullback_entry_high"))
    if opening is None or entry_high is None:
        return None
    return opening if opening <= entry_high else entry_high


def _stored_live_exit_state(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return dict(parsed) if isinstance(parsed, Mapping) else None
    return None


def _market_row_with_historical_price_basis(
    source: Mapping[str, Any], market_row: Mapping[str, Any], *, code: str,
    adjusted_histories: Mapping[str, pd.DataFrame] | None,
    raw_histories: Mapping[str, pd.DataFrame] | None,
    as_of: date,
) -> dict[str, Any]:
    """Attach current raw/qfq ratios at the two frozen-plan anchor dates."""

    local = dict(market_row)
    normalized = _normalize_code(code)
    histories_available = adjusted_histories is not None and raw_histories is not None
    exact_history = (
        adjusted_histories.get(normalized, pd.DataFrame())
        if adjusted_histories is not None else pd.DataFrame()
    )
    if not exact_history.empty and "adjustment_ratio" in exact_history.columns:
        exact = prepare_price_frame(exact_history)
        observation_date = _market_observation_date(local, as_of=as_of)
        if observation_date is not None:
            exact = exact[exact["date"] <= observation_date].copy().reset_index(drop=True)
        if not exact.empty and exact.iloc[-1]["date"] == observation_date:
            exact_row = exact.iloc[-1]
            exact_ratio = _safe_float(exact_row.get("adjustment_ratio"))
            if exact_ratio is not None and exact_ratio > 0:
                local["adjustment_ratio"] = round(exact_ratio, 8)
                for field in ("open", "high", "low", "close"):
                    value = _safe_float(exact_row.get(field))
                    if value is not None:
                        local[f"adjusted_latest_{field}"] = value
                volume = _safe_float(exact_row.get("volume"))
                if volume is not None:
                    local["adjusted_latest_volume"] = volume
                exact_close = pd.to_numeric(exact["close"], errors="coerce")
                if len(exact_close) >= 20:
                    local["ma20"] = float(exact_close.tail(20).mean())
                if len(exact_close) >= 60:
                    local["ma60"] = float(exact_close.tail(60).mean())
    lifecycle = str(source.get("signal_lifecycle_state") or "")
    basis_anchors = (
        (
            "signal_plan", source.get("signal_plan_origin_trade_date"),
            lifecycle in {"ENTRY_PENDING", "BREAKOUT_CONFIRMED_ENTRY_PENDING"} or (
                not lifecycle and source.get("user_visible_level") == "STRICT_REVIEW_READY"
            ),
        ),
        (
            "entry_date", source.get("entry_observation_trade_date"),
            lifecycle in MONITORED_SIGNAL_LIFECYCLES | EXIT_CONFIRMATION_LIFECYCLES,
        ),
    )
    for prefix, trade_date, applicable in basis_anchors:
        status_field = f"{prefix}_adjustment_ratio_status"
        ratio_field = f"{prefix}_adjustment_ratio_current"
        if not applicable:
            local[status_field] = "NOT_APPLICABLE"
            local[ratio_field] = ""
            continue
        if not trade_date:
            local[status_field] = "MISSING"
            local[ratio_field] = ""
            continue
        if histories_available:
            ratio = price_mapping_ratio_at_date(
                adjusted_histories.get(normalized, pd.DataFrame()),
                raw_histories.get(normalized, pd.DataFrame()),
                trade_date=trade_date,
            )
            local[status_field] = "OK" if ratio is not None else "MISSING"
            local[ratio_field] = round(ratio, 8) if ratio is not None else ""
        else:
            local.setdefault(status_field, "MISSING")
            local.setdefault(ratio_field, "")
    return local


def _historical_price_basis_error(
    source: Mapping[str, Any], market_row: Mapping[str, Any], *, basis: str,
) -> str:
    if basis == "entry":
        stored_field = "entry_adjustment_ratio"
        current_field = "entry_date_adjustment_ratio_current"
        status_field = "entry_date_adjustment_ratio_status"
        missing_error = "entry_adjustment_basis_missing"
        changed_error = "adjustment_ratio_changed"
    elif basis == "plan":
        stored_field = "signal_plan_adjustment_ratio"
        current_field = "signal_plan_adjustment_ratio_current"
        status_field = "signal_plan_adjustment_ratio_status"
        missing_error = "signal_plan_adjustment_basis_missing"
        changed_error = "signal_plan_adjustment_ratio_changed"
    else:  # pragma: no cover - internal programming guard
        raise ValueError(f"unsupported price basis: {basis}")
    stored_ratio = _safe_float(source.get(stored_field))
    current_ratio = _safe_float(market_row.get(current_field))
    if (
        str(market_row.get(status_field) or "") != "OK"
        or stored_ratio is None or stored_ratio <= 0
        or current_ratio is None or current_ratio <= 0
    ):
        return missing_error
    if not math.isclose(stored_ratio, current_ratio, rel_tol=1e-5, abs_tol=1e-6):
        return changed_error
    return ""


def _evaluate_live_exit_policy(
    source: Mapping[str, Any], market_row: Mapping[str, Any], *,
    as_of: date, require_previous_state: bool,
) -> dict[str, Any]:
    """Advance the validated 60-session exit policy on one adjusted daily bar."""

    entry_price = _safe_float(source.get("entry_reference_adjusted_price"))
    stop_loss = _safe_float(source.get("exit_policy_adjusted_stop_price"))
    entry_ratio = _safe_float(source.get("entry_adjustment_ratio"))
    current_ratio = _safe_float(market_row.get("adjustment_ratio"))
    raw_logic_invalidation = _safe_float(
        source.get("logic_invalidation_price")
        or _signal_plan_fields(source).get("logic_invalidation_price"),
    )
    trend_level = str(source.get("entry_setup_trend_confirmation_level") or "")
    previous_state = _stored_live_exit_state(source.get("live_exit_policy_state"))
    if require_previous_state:
        basis_error = _historical_price_basis_error(source, market_row, basis="entry")
        if basis_error:
            status = (
                "CORPORATE_ACTION_REVIEW"
                if basis_error == "adjustment_ratio_changed" else "ERROR"
            )
            return {"status": status, "error": basis_error}
    if require_previous_state and previous_state is None:
        return {"status": "ERROR", "error": "live_exit_state_missing"}
    if not all(
        value is not None and value > 0
        for value in (
            entry_price, stop_loss, entry_ratio, current_ratio,
            raw_logic_invalidation,
        )
    ):
        return {"status": "ERROR", "error": "live_exit_price_basis_missing"}
    adjusted_logic_invalidation = raw_logic_invalidation / entry_ratio
    if (
        not require_previous_state
        and not math.isclose(entry_ratio, current_ratio, rel_tol=1e-5, abs_tol=1e-6)
    ):
        return {"status": "CORPORATE_ACTION_REVIEW", "error": "adjustment_ratio_changed"}
    observation_date = _market_observation_date(market_row, as_of=as_of)
    bar = {
        "date": observation_date.isoformat() if observation_date else "",
        "open": market_row.get("adjusted_latest_open"),
        "high": market_row.get("adjusted_latest_high"),
        "low": market_row.get("adjusted_latest_low"),
        "close": market_row.get("adjusted_latest_close"),
        "volume": market_row.get("adjusted_latest_volume"),
        "ma20": market_row.get("ma20"),
        "ma60": market_row.get("ma60"),
    }
    try:
        evaluation = evaluate_live_balanced_v7_exit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            logic_invalidation_price=adjusted_logic_invalidation,
            trend_confirmation_level=trend_level,
            previous_state=previous_state,
            bar=bar,
        )
    except (TypeError, ValueError) as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}:{exc}"}
    state = dict(evaluation["state"])
    return {
        "status": "EXIT_TRIGGERED" if evaluation["triggered"] else "ACTIVE",
        "state": state,
        "reason": evaluation.get("exit_reason") or "",
        "holding_sessions": state.get("reference_holding_session_count") or 0,
        "effective_stop_raw": round(float(state["effective_stop_price"]) * current_ratio, 4),
        "exit_reference_raw": (
            round(float(evaluation["exit_reference_price"]) * current_ratio, 4)
            if evaluation.get("exit_reference_price") is not None else ""
        ),
    }


def _live_hard_exit_observed_during_gap(
    source: Mapping[str, Any], market_row: Mapping[str, Any],
) -> bool:
    state = _stored_live_exit_state(source.get("live_exit_policy_state"))
    adjusted_low = _safe_float(market_row.get("adjusted_latest_low"))
    hard_stop = _safe_float((state or {}).get("hard_intraday_stop_price"))
    return bool(
        state and not _historical_price_basis_error(source, market_row, basis="entry")
        and adjusted_low is not None and hard_stop is not None
        and adjusted_low <= hard_stop
    )


def _breakout_confirmation_observed(
    before: Mapping[str, Any], market_row: Mapping[str, Any],
) -> bool:
    if str(before.get("preferred_plan") or "") != "breakout":
        return False
    trigger = _safe_float(before.get("breakout_trigger_price"))
    required_volume = _safe_float(before.get("breakout_required_volume"))
    close = _safe_float(market_row.get("raw_latest_close"))
    actual_volume = _safe_float(market_row.get("raw_latest_volume"))
    return bool(
        trigger is not None and required_volume is not None
        and close is not None and actual_volume is not None
        and close >= trigger and actual_volume >= required_volume
    )


def _breakout_next_open_status(
    before: Mapping[str, Any], market_row: Mapping[str, Any],
) -> str:
    opening = _safe_float(market_row.get("raw_latest_open"))
    high = _safe_float(market_row.get("raw_latest_high"))
    low = _safe_float(market_row.get("raw_latest_low"))
    closing = _safe_float(market_row.get("raw_latest_close"))
    trigger = _safe_float(before.get("breakout_trigger_price"))
    max_buy = _safe_float(before.get("breakout_max_chase_price"))
    if any(
        value is None
        for value in (opening, high, low, closing, trigger, max_buy)
    ):
        return "UNKNOWN"
    if opening < trigger:
        return "BELOW_TRIGGER"
    if opening > max_buy:
        return "ABOVE_MAX_CHASE"
    if is_one_price_bar(
        opening=opening, high=high, low=low, close=closing,
    ):
        return "LOCKED_ONE_PRICE_UNEXECUTABLE"
    return "ENTRY_RANGE_OBSERVED"


def build_daily_signals(
    *, current_rows: list[Mapping[str, Any]], previous: Mapping[str, Mapping[str, Any]],
    as_of: date, next_trade_date: date,
    current_market_rows: list[Mapping[str, Any]] = (),
    adjusted_histories: Mapping[str, pd.DataFrame] | None = None,
    raw_histories: Mapping[str, pd.DataFrame] | None = None,
    state_continuity_safe: bool = True,
    buy_signal_data_safe: bool = True,
) -> list[dict[str, Any]]:
    """Build idempotent research actions without assuming that the user traded.

    Production callers supply both history maps so frozen raw-price plans can
    be checked against qfq rebases at their exact origin and entry dates.
    """

    current_by_code = {_normalize_code(row.get("code")): row for row in current_rows}
    market_by_code = {
        _normalize_code(row.get("code")): row for row in (*current_market_rows, *current_rows)
    }
    signals: list[dict[str, Any]] = []
    for code, row in current_by_code.items():
        before = previous.get(code, {})
        market_row = _market_row_with_historical_price_basis(
            before, market_by_code.get(code, row), code=code,
            adjusted_histories=adjusted_histories, raw_histories=raw_histories,
            as_of=as_of,
        )
        previous_level = str(before.get("user_visible_level") or "")
        current_level = str(row.get("user_visible_level") or "")
        latest_price = _safe_float(market_row.get("raw_latest_close"))
        intraday_low = _safe_float(market_row.get("raw_latest_low"))
        before_plan = _signal_plan_fields(before)
        previous_lifecycle = str(before.get("signal_lifecycle_state") or "")
        monitored = previous_lifecycle in MONITORED_SIGNAL_LIFECYCLES
        exit_confirmation_required = previous_lifecycle in EXIT_CONFIRMATION_LIFECYCLES
        breakout_entry_pending = previous_lifecycle == "BREAKOUT_CONFIRMED_ENTRY_PENDING"
        pending = previous_lifecycle == "ENTRY_PENDING" or (
            not previous_lifecycle and previous_level == "STRICT_REVIEW_READY"
        )
        previous_mode = str(before.get("preferred_plan") or "")
        previous_plan_rule_version = str(before.get("plan_rule_version") or "")
        plan_rule_compatible = bool(
            not before or previous_plan_rule_version == RULE_VERSION
        )
        current_mode = str(row.get("preferred_plan") or "")
        current_profile_mode = str(
            row.get("exit_profile_entry_mode")
            if "exit_profile_entry_mode" in row else current_mode
        )
        mode_continuity = bool(
            previous_mode in {"pullback", "breakout"}
            and previous_mode == current_mode == current_profile_mode
        )
        freeze_input_plan = bool(before) and (
            pending or monitored or exit_confirmation_required or breakout_entry_pending
            or previous_lifecycle in TERMINAL_ENTRY_LIFECYCLES
        )
        input_row = dict(row)
        if freeze_input_plan:
            for field in FROZEN_SIGNAL_PLAN_FIELDS:
                if field in before:
                    input_row[field] = before.get(field)
        else:
            input_row["signal_plan_adjustment_ratio"] = market_row.get("adjustment_ratio")
            current_ratio = _safe_float(market_row.get("adjustment_ratio"))
            market_row["signal_plan_adjustment_ratio_status"] = (
                "OK" if current_ratio is not None and current_ratio > 0 else "MISSING"
            )
            market_row["signal_plan_adjustment_ratio_current"] = (
                round(current_ratio, 8) if current_ratio is not None and current_ratio > 0 else ""
            )
        input_version = _signal_input_version(input_row, market_row)
        replay = bool(before) and _same_observation_replay(
            before, market_row, as_of=as_of, signal_input_version=input_version,
        )
        if replay and not buy_signal_data_safe and before.get("last_signal_action") == "BUY_IF_TRIGGERED":
            replay = False
        if replay and (pending or breakout_entry_pending) and not plan_rule_compatible:
            replay = False
        same_observation_changed = bool(before) and not replay and _same_observation_input_changed(
            before, market_row, as_of=as_of, signal_input_version=input_version,
        )
        entry_basis_error = (
            _historical_price_basis_error(before, market_row, basis="entry")
            if monitored else ""
        )
        plan_basis_error = (
            _historical_price_basis_error(before, market_row, basis="plan")
            if (pending or breakout_entry_pending) and plan_rule_compatible else ""
        )
        run_gap = bool(before) and not replay and _run_gap_detected(
            before, market_row, as_of=as_of,
        )
        new_market_bar = bool(before) and not replay and _new_market_bar_available(
            before, market_row, as_of=as_of,
        )
        breached = not run_gap and new_market_bar and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        )
        logic_invalidation_price = _safe_float(before_plan.get("logic_invalidation_price"))
        logic_invalidation_breached = bool(
            latest_price is not None and logic_invalidation_price is not None
            and latest_price <= logic_invalidation_price
        )
        live_exit_evaluation = (
            _evaluate_live_exit_policy(
                before, market_row, as_of=as_of, require_previous_state=True,
            )
            if monitored and not run_gap and new_market_bar else {}
        )
        live_exit_triggered = live_exit_evaluation.get("status") == "EXIT_TRIGGERED"
        live_exit_error = str(live_exit_evaluation.get("status") or "") in {
            "ERROR", "CORPORATE_ACTION_REVIEW",
        }
        pullback_entry_status = (
            _pullback_entry_status(before, market_row)
            if pending and not run_gap and new_market_bar
            else "NOT_APPLICABLE"
        )
        trigger_observed = pullback_entry_status == "ENTRY_RANGE_OBSERVED"
        breakout_confirmation_observed = (
            pending and mode_continuity and not run_gap and new_market_bar
            and previous_mode == "breakout"
            and _breakout_confirmation_observed(before, market_row)
        )
        breakout_open_status = (
            _breakout_next_open_status(before, market_row)
            if breakout_entry_pending and not run_gap and new_market_bar
            else "NOT_APPLICABLE"
        )
        previous_thresholds = (
            _safe_float(before_plan.get("stop_price")),
            _safe_float(before_plan.get("logic_invalidation_price")),
        )
        same_day_ambiguous = (
            trigger_observed or breakout_open_status == "ENTRY_RANGE_OBSERVED"
        ) and intraday_low is not None and any(
            threshold is not None and intraday_low <= threshold for threshold in previous_thresholds
        )
        previous_age = max(0, int(_safe_float(before.get("entry_plan_age_sessions")) or 0))
        current_age = previous_age + int(pending and new_market_bar and not run_gap)
        signal_data_status = "RUN_GAP_REQUIRES_REVIEW" if run_gap else "CURRENT_DATA"
        trigger_today = trigger_observed or breakout_open_status == "ENTRY_RANGE_OBSERVED"
        breakout_confirmation_today = breakout_confirmation_observed

        if replay:
            action = str(before.get("last_signal_action") or "WATCH_ONLY")
            label = str(before.get("last_signal_label") or "重复运行/保持上一信号")
            reason = str(before.get("last_signal_reason") or "same_market_observation_replay")
            lifecycle = previous_lifecycle or "NO_POSITION_SIGNAL"
            signal_data_status = str(before.get("last_signal_data_status") or "CURRENT_DATA")
            trigger_today = bool(before.get("last_trigger_observed_today"))
            breakout_confirmation_today = bool(
                before.get("last_breakout_confirmation_observed_today"),
            )
            current_age = previous_age
        elif same_observation_changed and exit_confirmation_required:
            action = "HOLD_REVIEW"
            label = "同一交易日行情被更正/原退出信号人工确认"
            reason = "same_trade_date_input_changed_exit_review"
            lifecycle = "POSITION_REVIEW"
            signal_data_status = "SAME_OBSERVATION_DATA_CHANGED_REQUIRES_REVIEW"
        elif exit_confirmation_required:
            action = "SELL_EXIT"
            label = "若仍持仓：退出后等待人工确认"
            reason = "exit_confirmation_required_after_threshold_breach"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
        elif monitored and run_gap and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        ):
            action = "SELL_EXIT"
            label = "若已持仓：当前行情已触发硬退出（同时存在运行断档）"
            reason = "balanced_or_frozen_hard_exit_with_run_gap"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
        elif monitored and entry_basis_error:
            action = "HOLD_REVIEW"
            label = "持仓复权基准变化或缺失/人工复核"
            reason = f"live_exit_policy_review:{entry_basis_error}"
            lifecycle = "POSITION_REVIEW"
            signal_data_status = (
                "LIVE_EXIT_STATE_AND_RUN_GAP_REQUIRES_REVIEW"
                if run_gap else "LIVE_EXIT_STATE_REQUIRES_REVIEW"
            )
        elif run_gap and (pending or breakout_entry_pending) and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        ):
            action = "SELL_EXIT"
            label = "断档期间可能已成交且当前保护位触发/若持仓则退出"
            reason = "run_gap_possible_entry_and_frozen_threshold_breached"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            signal_data_status = "RUN_GAP_REQUIRES_POSITION_CONFIRMATION"
        elif run_gap and (pending or breakout_entry_pending):
            action = "HOLD_REVIEW"
            label = "运行断档期间可能已触发入场/人工确认持仓"
            reason = "run_gap_entry_execution_unknown_manual_confirmation"
            lifecycle = "POSITION_REVIEW"
            signal_data_status = "RUN_GAP_REQUIRES_POSITION_CONFIRMATION"
        elif (pending or breakout_entry_pending) and not plan_rule_compatible:
            action = "CANCEL_BUY_REVIEW"
            label = "旧入场计划规则版本不兼容"
            reason = "entry_plan_rule_version_incompatible"
            lifecycle = "ENTRY_CANCELLED"
        elif (pending or breakout_entry_pending) and plan_basis_error:
            action = "CANCEL_BUY_REVIEW"
            label = "入场计划复权基准变化或缺失/取消计划"
            reason = plan_basis_error
            lifecycle = "ENTRY_CANCELLED"
            signal_data_status = (
                "PRICE_BASIS_AND_RUN_GAP_REQUIRES_REVIEW"
                if run_gap else "PRICE_BASIS_REQUIRES_REVIEW"
            )
        elif same_observation_changed and monitored:
            action = "HOLD_REVIEW"
            label = "同一交易日行情被更正/持仓人工复核"
            reason = "same_trade_date_input_changed_position_review"
            lifecycle = "POSITION_REVIEW"
            signal_data_status = "SAME_OBSERVATION_DATA_CHANGED_REQUIRES_REVIEW"
        elif same_observation_changed and (pending or breakout_entry_pending):
            action = "CANCEL_BUY_REVIEW"
            label = "同一交易日行情被更正/取消入场计划"
            reason = "same_trade_date_input_changed_entry_cancelled"
            lifecycle = "ENTRY_CANCELLED"
            signal_data_status = "SAME_OBSERVATION_DATA_CHANGED_REQUIRES_REVIEW"
        elif run_gap:
            action = "CANCEL_BUY_REVIEW"
            label = "运行断档/人工复核"
            reason = (
                "run_gap_position_state_requires_manual_review"
                if monitored else "run_gap_entry_state_unreplayable"
            )
            lifecycle = "POSITION_REVIEW" if monitored else "ENTRY_CANCELLED"
        elif monitored and live_exit_triggered:
            action = "SELL_EXIT"
            label = "若已持仓：balanced-v7 退出条件触发"
            reason = f"balanced_exit_triggered:{live_exit_evaluation.get('reason')}"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
        elif monitored and logic_invalidation_breached:
            action = "SELL_EXIT"
            label = "若已持仓：原计划逻辑失效位触发"
            reason = "previous_logic_invalidation_breached"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
        elif monitored and live_exit_error and breached:
            action = "SELL_EXIT"
            label = "若已持仓：退出状态异常且冻结保护位已触发"
            reason = "frozen_protective_stop_breached_live_state_unavailable"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            signal_data_status = "LIVE_EXIT_STATE_REQUIRES_REVIEW"
        elif monitored and live_exit_error:
            action = "HOLD_REVIEW"
            label = "退出状态或复权口径异常/人工复核"
            reason = f"live_exit_policy_review:{live_exit_evaluation.get('error') or 'unknown'}"
            lifecycle = "POSITION_REVIEW"
            signal_data_status = "LIVE_EXIT_STATE_REQUIRES_REVIEW"
        elif monitored and current_level == "STRICT_REVIEW_READY" and not mode_continuity:
            action = "HOLD_REVIEW"
            label = "可能持仓的计划模式已变化/人工复核"
            reason = "active_position_plan_mode_changed_manual_review"
            lifecycle = "POSITION_REVIEW"
        elif monitored and current_level == "STRICT_REVIEW_READY":
            action = "HOLD_REVIEW"
            label = "触发后持仓复核（需确认已成交）"
            reason = "strict_signal_remains_valid_after_observed_trigger"
            lifecycle = "ENTRY_TRIGGER_OBSERVED"
        elif monitored:
            action = "CANCEL_BUY_REVIEW"
            label = "取消新买入/持仓复核"
            reason = f"strict_signal_lost:{row.get('missing_conditions') or 'qualification_lost'}"
            lifecycle = "POSITION_REVIEW"
        elif (pending or breakout_entry_pending) and not buy_signal_data_safe:
            action = "CANCEL_BUY_REVIEW"
            label = "退出画像长历史覆盖不足/取消本次入场"
            reason = "exit_profile_history_coverage_degraded"
            lifecycle = "ENTRY_CANCELLED"
        elif (
            breakout_entry_pending and not mode_continuity
            and breakout_open_status != "ENTRY_RANGE_OBSERVED"
        ):
            action = "CANCEL_BUY_REVIEW"
            label = "突破确认后的计划模式已变化"
            reason = "entry_plan_mode_changed"
            lifecycle = "ENTRY_CANCELLED"
        elif breakout_entry_pending:
            if breakout_open_status == "ENTRY_RANGE_OBSERVED" and same_day_ambiguous:
                action = "HOLD_REVIEW"
                label = "入场与计划保护位同日交错/确认真实成交"
                reason = "breakout_entry_and_plan_threshold_same_day_order_ambiguous"
                lifecycle = "POSITION_REVIEW"
            elif breakout_open_status == "ENTRY_RANGE_OBSERVED" and not mode_continuity:
                action = "HOLD_REVIEW"
                label = "突破开盘可能已成交但计划模式变化/人工复核"
                reason = "breakout_next_open_entry_observed_plan_mode_changed"
                lifecycle = "POSITION_REVIEW"
            elif breakout_open_status == "ENTRY_RANGE_OBSERVED":
                action = "HOLD_REVIEW"
                label = "突破确认后的开盘入场区已出现（需确认是否成交）"
                reason = (
                    "breakout_next_open_entry_observed_confirm_execution_manually"
                    if current_level == "STRICT_REVIEW_READY"
                    else "breakout_next_open_entry_observed_but_strict_signal_lost"
                )
                lifecycle = "ENTRY_TRIGGER_OBSERVED" if current_level == "STRICT_REVIEW_READY" else "POSITION_REVIEW"
            else:
                action = "CANCEL_BUY_REVIEW"
                label = "突破确认后的开盘条件未满足"
                reason = f"breakout_next_open_{breakout_open_status.lower()}"
                lifecycle = "ENTRY_CANCELLED"
        elif pending and not mode_continuity and not trigger_observed:
            action = "CANCEL_BUY_REVIEW"
            label = "入场计划模式已变化"
            reason = "entry_plan_mode_changed"
            lifecycle = "ENTRY_CANCELLED"
        elif pending and pullback_entry_status == "OPEN_BELOW_ENTRY_BAND":
            action = "CANCEL_BUY_REVIEW"
            label = "开盘低于回踩入场区/取消计划"
            reason = "pullback_open_below_entry_band"
            lifecycle = "ENTRY_CANCELLED"
        elif pending and pullback_entry_status == "LOCKED_ONE_PRICE_UNEXECUTABLE":
            action = "CANCEL_BUY_REVIEW"
            label = "一字板无法确认回踩成交/取消计划"
            reason = "pullback_locked_one_price_unexecutable"
            lifecycle = "ENTRY_CANCELLED"
        elif pending and same_day_ambiguous:
            action = "HOLD_REVIEW"
            label = "入场与计划保护位同日交错/确认真实成交"
            reason = "pullback_entry_and_plan_threshold_same_day_order_ambiguous"
            lifecycle = "POSITION_REVIEW"
        elif pending and breached:
            action = "CANCEL_BUY_REVIEW"
            label = "入场前计划失效"
            reason = "entry_invalidated_before_position_confirmation"
            lifecycle = "ENTRY_INVALIDATED"
        elif pending and breakout_confirmation_observed and current_level == "STRICT_REVIEW_READY":
            action = "BUY_IF_TRIGGERED"
            label = "突破已收盘确认/下一交易日开盘条件买入"
            reason = "breakout_close_confirmed_next_open_pending"
            lifecycle = "BREAKOUT_CONFIRMED_ENTRY_PENDING"
        elif pending and breakout_confirmation_observed:
            action = "CANCEL_BUY_REVIEW"
            label = "突破已确认但严格资格丢失"
            reason = "breakout_confirmed_but_strict_signal_lost"
            lifecycle = "ENTRY_CANCELLED"
        elif pending and trigger_observed and not mode_continuity:
            action = "HOLD_REVIEW"
            label = "回踩可能已成交但计划模式变化/人工复核"
            reason = "pullback_entry_observed_plan_mode_changed"
            lifecycle = "POSITION_REVIEW"
        elif pending and trigger_observed and current_level == "STRICT_REVIEW_READY":
            action = "HOLD_REVIEW"
            label = "入场触发已出现（需确认是否成交）"
            reason = "entry_trigger_observed_confirm_execution_manually"
            lifecycle = "ENTRY_TRIGGER_OBSERVED"
        elif pending and trigger_observed:
            action = "CANCEL_BUY_REVIEW"
            label = "触发后资格丢失/人工复核"
            reason = "entry_trigger_observed_but_strict_signal_lost"
            lifecycle = "POSITION_REVIEW"
        elif pending and current_level == "STRICT_REVIEW_READY" and current_age >= ENTRY_TRIGGER_WINDOW_SESSIONS:
            action = "CANCEL_BUY_REVIEW"
            label = "固定入场计划已到期"
            reason = "entry_trigger_window_expired"
            lifecycle = "ENTRY_CANCELLED"
        elif pending and current_level == "STRICT_REVIEW_READY":
            if previous_mode == "breakout":
                action = "WATCH_ONLY"
                label = "等待突破收盘放量确认"
                reason = "breakout_close_confirmation_pending"
            else:
                action = "BUY_IF_TRIGGERED"
                label = "条件买入信号"
                reason = "entry_trigger_still_pending"
            lifecycle = "ENTRY_PENDING"
        elif pending:
            action = "CANCEL_BUY_REVIEW"
            label = "取消新买入/持仓复核"
            reason = f"strict_signal_lost:{row.get('missing_conditions') or 'qualification_lost'}"
            lifecycle = "ENTRY_CANCELLED"
        elif previous_lifecycle in TERMINAL_ENTRY_LIFECYCLES and previous_level == "STRICT_REVIEW_READY":
            action = "CANCEL_BUY_REVIEW"
            label = "旧入场计划已终止/等待新的独立严格信号"
            reason = str(before.get("last_signal_reason") or "terminal_entry_state_awaiting_new_setup")
            lifecycle = previous_lifecycle
        elif current_level == "STRICT_REVIEW_READY":
            if not state_continuity_safe or not buy_signal_data_safe:
                action = "WATCH_ONLY"
                if not state_continuity_safe:
                    label = "状态连续性未知/本次禁止新买入"
                    reason = "state_continuity_unknown_buy_suppressed"
                else:
                    label = "退出画像长历史覆盖不足/本次禁止新买入"
                    reason = "exit_profile_history_coverage_degraded"
            elif current_mode == "breakout":
                action = "WATCH_ONLY"
                label = "等待突破收盘放量确认"
                reason = "breakout_close_confirmation_pending"
            else:
                action = "BUY_IF_TRIGGERED"
                label = "条件买入信号"
                reason = "all_strict_gates_passed"
            lifecycle = "ENTRY_PENDING"
        else:
            action = "WATCH_ONLY"
            label = "仅观察"
            reason = str(row.get("missing_conditions") or "strict_gates_not_passed")
            lifecycle = "NO_POSITION_SIGNAL"
        freeze_previous_plan = bool(before) and (
            pending or monitored or exit_confirmation_required
            or breakout_entry_pending or breached or run_gap or replay
            or previous_lifecycle in TERMINAL_ENTRY_LIFECYCLES
        )
        plan_source = before if freeze_previous_plan else row
        plan = _signal_plan_fields(plan_source)
        origin_trade_date = (
            plan_source.get("signal_plan_origin_trade_date")
            or plan_source.get("latest_trade_date")
            or market_row.get("latest_trade_date")
            or as_of.isoformat()
        )
        signal_plan_adjustment_ratio = plan_source.get("signal_plan_adjustment_ratio")
        if not freeze_previous_plan:
            signal_plan_adjustment_ratio = market_row.get("adjustment_ratio")
        plan_identity_source = {
            **dict(plan_source),
            "signal_plan_adjustment_ratio": signal_plan_adjustment_ratio,
        }
        frozen_plan_id = str(plan_source.get("plan_id") or _plan_id(
            plan_identity_source, origin_trade_date=origin_trade_date,
        ))
        plan_rule_version = str(
            plan_source.get("plan_rule_version")
            or ("LEGACY_UNVERSIONED" if freeze_previous_plan else RULE_VERSION)
        )
        # Price touching a frozen band is not enough to initialize a reference
        # position: higher-priority cancellation paths (corporate action,
        # correction, run gap, rule/mode mismatch) must remain final.  Only the
        # decision branches that explicitly accepted an observable entry may
        # start the exit state machine.
        accepted_entry_reasons = {
            "breakout_entry_and_plan_threshold_same_day_order_ambiguous",
            "breakout_next_open_entry_observed_confirm_execution_manually",
            "breakout_next_open_entry_observed_but_strict_signal_lost",
            "breakout_next_open_entry_observed_plan_mode_changed",
            "pullback_entry_and_plan_threshold_same_day_order_ambiguous",
            "entry_trigger_observed_confirm_execution_manually",
            "entry_trigger_observed_but_strict_signal_lost",
            "pullback_entry_observed_plan_mode_changed",
        }
        entry_observation_accepted = reason in accepted_entry_reasons
        observed_entry_mode = (
            "breakout" if (
                entry_observation_accepted and breakout_entry_pending
                and breakout_open_status == "ENTRY_RANGE_OBSERVED"
            )
            else "pullback" if entry_observation_accepted and pending and trigger_observed
            else ""
        )
        assumed_entry_price = plan_source.get("assumed_entry_price")
        entry_observation_trade_date = plan_source.get("entry_observation_trade_date")
        entry_reference_adjusted_price = plan_source.get("entry_reference_adjusted_price")
        exit_policy_adjusted_stop_price = plan_source.get("exit_policy_adjusted_stop_price")
        entry_adjustment_ratio = plan_source.get("entry_adjustment_ratio")
        entry_setup_trend = plan_source.get("entry_setup_trend_confirmation_level")
        if observed_entry_mode:
            assumed_entry_price = _observed_entry_price(
                before, market_row, entry_mode=observed_entry_mode,
            )
            observation_date = _market_observation_date(market_row, as_of=as_of)
            entry_observation_trade_date = observation_date.isoformat() if observation_date else ""
            current_ratio = _safe_float(market_row.get("adjustment_ratio"))
            raw_stop = _safe_float(plan.get("stop_price"))
            entry_setup_trend = str(
                plan_source.get("trend_confirmation_level") or "NONE",
            )
            if (
                assumed_entry_price is not None and current_ratio is not None
                and current_ratio > 0 and raw_stop is not None
            ):
                entry_adjustment_ratio = current_ratio
                entry_reference_adjusted_price = assumed_entry_price / current_ratio
                exit_policy_adjusted_stop_price = raw_stop / current_ratio
        live_exit_policy_state = plan_source.get("live_exit_policy_state")
        live_exit_status = str(plan_source.get("live_exit_policy_status") or "NOT_STARTED")
        live_exit_reason = str(plan_source.get("live_exit_policy_reason") or "")
        live_exit_holding_sessions = plan_source.get("live_exit_holding_sessions") or 0
        live_exit_effective_stop = plan_source.get("live_exit_effective_stop_price") or ""
        live_exit_reference_price = plan_source.get("live_exit_reference_price") or ""
        if monitored and live_exit_evaluation.get("state"):
            live_exit_policy_state = live_exit_evaluation["state"]
            live_exit_status = str(live_exit_evaluation.get("status") or "")
            live_exit_reason = str(live_exit_evaluation.get("reason") or "")
            live_exit_holding_sessions = live_exit_evaluation.get("holding_sessions") or 0
            live_exit_effective_stop = live_exit_evaluation.get("effective_stop_raw") or ""
            live_exit_reference_price = live_exit_evaluation.get("exit_reference_raw") or ""
        elif monitored and live_exit_evaluation:
            live_exit_status = str(live_exit_evaluation.get("status") or "ERROR")
            live_exit_reason = str(live_exit_evaluation.get("error") or "unknown")
        elif observed_entry_mode and not replay:
            initial_exit_source = {
                "entry_reference_adjusted_price": entry_reference_adjusted_price,
                "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
                "entry_adjustment_ratio": entry_adjustment_ratio,
                "entry_setup_trend_confirmation_level": entry_setup_trend,
                "logic_invalidation_price": plan.get("logic_invalidation_price"),
            }
            initial_exit = _evaluate_live_exit_policy(
                initial_exit_source, market_row, as_of=as_of,
                require_previous_state=False,
            )
            if initial_exit.get("state"):
                live_exit_policy_state = initial_exit["state"]
                live_exit_status = str(initial_exit.get("status") or "")
                live_exit_reason = str(initial_exit.get("reason") or "")
                live_exit_holding_sessions = initial_exit.get("holding_sessions") or 0
                live_exit_effective_stop = initial_exit.get("effective_stop_raw") or ""
                live_exit_reference_price = initial_exit.get("exit_reference_raw") or ""
                if initial_exit.get("status") == "EXIT_TRIGGERED":
                    action = "SELL_EXIT"
                    label = "若当日实际成交：A股T+1，下一交易日开盘退出"
                    reason = f"entry_and_exit_same_day_t1:{initial_exit.get('reason')}"
                    lifecycle = "EXIT_THRESHOLD_BREACHED"
            else:
                live_exit_status = str(initial_exit.get("status") or "ERROR")
                live_exit_reason = str(initial_exit.get("error") or "unknown")
                action = "CANCEL_BUY_REVIEW"
                label = "参考入场后的退出状态无法建立/人工复核"
                reason = f"live_exit_initialization_failed:{live_exit_reason}"
                lifecycle = "POSITION_REVIEW"
                signal_data_status = "LIVE_EXIT_STATE_REQUIRES_REVIEW"
        risk_budget_enabled = action in {"BUY_IF_TRIGGERED", "HOLD_REVIEW"}
        risk_source = before if freeze_previous_plan else row
        input_row.update({
            "signal_plan_adjustment_ratio": signal_plan_adjustment_ratio,
            "entry_reference_adjusted_price": entry_reference_adjusted_price,
            "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
            "entry_adjustment_ratio": entry_adjustment_ratio,
            "entry_setup_trend_confirmation_level": entry_setup_trend,
            "live_exit_policy_name": "balanced_hybrid_60d_exit",
            "live_exit_policy_version": LIVE_BALANCED_EXIT_POLICY_VERSION,
        })
        if observed_entry_mode:
            observed_ratio = _safe_float(entry_adjustment_ratio)
            market_row["signal_plan_adjustment_ratio_status"] = "NOT_APPLICABLE"
            market_row["signal_plan_adjustment_ratio_current"] = ""
            market_row["entry_date_adjustment_ratio_status"] = (
                "OK" if observed_ratio is not None and observed_ratio > 0 else "MISSING"
            )
            market_row["entry_date_adjustment_ratio_current"] = (
                round(observed_ratio, 8)
                if observed_ratio is not None and observed_ratio > 0 else ""
            )
        input_version = _signal_input_version(input_row, market_row)
        signal_context = _signal_context_fields(row)
        if freeze_previous_plan:
            for field in (
                "exit_profile_status", "exit_profile_entry_mode",
                "profile_validation_scope", "profile_position_multiplier",
            ):
                if before.get(field) not in {None, ""}:
                    signal_context[field] = before.get(field)
        signals.append({
            "signal_date": as_of.isoformat(), "valid_for_trade_date": next_trade_date.isoformat(),
            "code": code, "stock_name": row.get("stock_name"), "signal_action": action,
            "signal_label": label, "previous_level": previous_level, "current_level": current_level,
            "signal_reason": reason,
            "signal_data_status": signal_data_status,
            "signal_bar_processed": _signal_bar_processed(signal_data_status),
            "previous_lifecycle_state": previous_lifecycle or "NONE",
            "current_lifecycle_state": lifecycle,
            "trigger_observed_today": trigger_today,
            "breakout_confirmation_observed_today": breakout_confirmation_today,
            "position_confirmation_required": (
                bool(before.get("last_position_confirmation_required")) if replay
                else action in {"HOLD_REVIEW", "SELL_EXIT"} or lifecycle == "POSITION_REVIEW"
            ),
            "actionability_rank": row.get("actionability_rank"),
            "latest_trade_date": market_row.get("latest_trade_date"), "latest_price": market_row.get("raw_latest_close"),
            "threshold_observation_price": (
                market_row.get("raw_latest_low")
                if market_row.get("raw_latest_low") not in {None, ""}
                else market_row.get("raw_latest_close")
            ),
            "preferred_plan": plan_source.get("preferred_plan"),
            "plan_id": frozen_plan_id, "plan_rule_version": plan_rule_version,
            "signal_plan_origin_trade_date": origin_trade_date,
            "signal_plan_adjustment_ratio": signal_plan_adjustment_ratio,
            "signal_plan_adjustment_ratio_status": market_row.get(
                "signal_plan_adjustment_ratio_status",
            ),
            "signal_plan_adjustment_ratio_current": market_row.get(
                "signal_plan_adjustment_ratio_current",
            ),
            "signal_input_version": input_version,
            "entry_plan_age_sessions": current_age,
            **plan,
            "real_reward_risk_ratio": plan_source.get("real_reward_risk_ratio"),
            "cancel_conditions": plan_source.get("cancel_conditions"),
            "assumed_entry_price": assumed_entry_price,
            "entry_observation_trade_date": entry_observation_trade_date,
            "entry_reference_adjusted_price": entry_reference_adjusted_price,
            "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
            "entry_adjustment_ratio": entry_adjustment_ratio,
            "entry_date_adjustment_ratio_status": market_row.get(
                "entry_date_adjustment_ratio_status",
            ),
            "entry_date_adjustment_ratio_current": market_row.get(
                "entry_date_adjustment_ratio_current",
            ),
            "entry_setup_trend_confirmation_level": entry_setup_trend,
            "live_exit_policy_name": "balanced_hybrid_60d_exit",
            "live_exit_policy_version": LIVE_BALANCED_EXIT_POLICY_VERSION,
            "live_exit_policy_state": live_exit_policy_state,
            "live_exit_policy_status": live_exit_status,
            "live_exit_policy_reason": live_exit_reason,
            "live_exit_holding_sessions": live_exit_holding_sessions,
            "live_exit_effective_stop_price": live_exit_effective_stop,
            "live_exit_reference_price": live_exit_reference_price,
            "exit_earliest_trade_date": (
                next_trade_date.isoformat() if action == "SELL_EXIT" else ""
            ),
            "exit_execution_timing": (
                DAILY_SIGNAL_EXECUTION_TIMING if action == "SELL_EXIT" else ""
            ),
            "breakout_required_volume": plan_source.get("breakout_required_volume"),
            "risk_budget_initial_position_pct": (
                risk_source.get("risk_budget_initial_position_pct") or 0.0
            ) if risk_budget_enabled else 0.0,
            "risk_budget_max_position_pct": (
                risk_source.get("risk_budget_max_position_pct") or 0.0
            ) if risk_budget_enabled else 0.0,
            **signal_context,
            "evidence_urls": row.get("evidence_urls"), "rule_version": RULE_VERSION,
            "no_auto_trade": True, "disclaimer": DISCLAIMER,
            "_same_observation_replay": replay,
        })
    for code, before in previous.items():
        previous_lifecycle = str(before.get("signal_lifecycle_state") or "")
        monitored = previous_lifecycle in MONITORED_SIGNAL_LIFECYCLES
        exit_confirmation_required = previous_lifecycle in EXIT_CONFIRMATION_LIFECYCLES
        breakout_entry_pending = previous_lifecycle == "BREAKOUT_CONFIRMED_ENTRY_PENDING"
        pending = previous_lifecycle == "ENTRY_PENDING" or (
            not previous_lifecycle
            and str(before.get("user_visible_level") or "") == "STRICT_REVIEW_READY"
        )
        plan_rule_compatible = str(before.get("plan_rule_version") or "") == RULE_VERSION
        terminal_entry = previous_lifecycle in TERMINAL_ENTRY_LIFECYCLES
        if code in current_by_code:
            continue
        market_row = _market_row_with_historical_price_basis(
            before, market_by_code.get(code, {}), code=code,
            adjusted_histories=adjusted_histories, raw_histories=raw_histories,
            as_of=as_of,
        )
        input_version = _signal_input_version(before, market_row)
        replay = _same_observation_replay(
            before, market_row, as_of=as_of, signal_input_version=input_version,
        )
        if replay and (pending or breakout_entry_pending) and not plan_rule_compatible:
            replay = False
        same_observation_changed = not replay and _same_observation_input_changed(
            before, market_row, as_of=as_of, signal_input_version=input_version,
        )
        entry_basis_error = (
            _historical_price_basis_error(before, market_row, basis="entry")
            if monitored else ""
        )
        plan_basis_error = (
            _historical_price_basis_error(before, market_row, basis="plan")
            if (pending or breakout_entry_pending) and plan_rule_compatible else ""
        )
        if (
            str(before.get("user_visible_level") or "") != "STRICT_REVIEW_READY"
            and not (monitored or exit_confirmation_required or breakout_entry_pending or replay)
        ):
            continue
        if terminal_entry and not replay:
            continue
        latest_price = _safe_float(market_row.get("raw_latest_close"))
        intraday_low = _safe_float(market_row.get("raw_latest_low"))
        run_gap = not replay and _run_gap_detected(before, market_row, as_of=as_of)
        new_market_bar = not replay and _new_market_bar_available(before, market_row, as_of=as_of)
        breached = monitored and not run_gap and new_market_bar and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        )
        plan = _signal_plan_fields(before)
        logic_invalidation = _safe_float(plan.get("logic_invalidation_price"))
        logic_invalidation_breached = bool(
            latest_price is not None and logic_invalidation is not None
            and latest_price <= logic_invalidation
        )
        live_exit_evaluation = (
            _evaluate_live_exit_policy(
                before, market_row, as_of=as_of, require_previous_state=True,
            )
            if monitored and not run_gap and new_market_bar else {}
        )
        live_exit_triggered = live_exit_evaluation.get("status") == "EXIT_TRIGGERED"
        live_exit_error = str(live_exit_evaluation.get("status") or "") in {
            "ERROR", "CORPORATE_ACTION_REVIEW",
        }
        trigger_today = False
        breakout_confirmation_today = False
        breakout_open_status = (
            _breakout_next_open_status(before, market_row)
            if breakout_entry_pending and new_market_bar and not run_gap
            else "RUN_GAP" if breakout_entry_pending and run_gap else "NOT_APPLICABLE"
        )
        pullback_entry_status = (
            _pullback_entry_status(before, market_row)
            if pending and new_market_bar and not run_gap
            else "RUN_GAP" if pending and run_gap else "NOT_APPLICABLE"
        )
        previous_thresholds = (
            _safe_float(plan.get("stop_price")),
            _safe_float(plan.get("logic_invalidation_price")),
        )
        breakout_same_day_ambiguous = bool(
            breakout_open_status == "ENTRY_RANGE_OBSERVED"
            and intraday_low is not None
            and any(
                threshold is not None and intraday_low <= threshold
                for threshold in previous_thresholds
            )
        )
        pullback_same_day_ambiguous = bool(
            pullback_entry_status == "ENTRY_RANGE_OBSERVED"
            and intraday_low is not None
            and any(
                threshold is not None and intraday_low <= threshold
                for threshold in previous_thresholds
            )
        )
        if replay and before.get("last_signal_action") == "BUY_IF_TRIGGERED":
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "current_strict_evidence_missing_buy_suppressed"
            label = "当前严格证据行缺失/取消新买入"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif replay:
            action = str(before.get("last_signal_action") or "CANCEL_BUY_REVIEW")
            lifecycle = previous_lifecycle or "ENTRY_CANCELLED"
            reason = str(before.get("last_signal_reason") or "same_market_observation_replay")
            label = str(before.get("last_signal_label") or "重复运行/保持上一信号")
            data_status = str(before.get("last_signal_data_status") or "ACTIVE_EVIDENCE_STALE")
            trigger_today = bool(before.get("last_trigger_observed_today"))
            breakout_confirmation_today = bool(
                before.get("last_breakout_confirmation_observed_today"),
            )
        elif same_observation_changed and exit_confirmation_required:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = "same_trade_date_input_changed_exit_review"
            label = "同一交易日行情被更正/原退出信号人工确认"
            data_status = "SAME_OBSERVATION_DATA_CHANGED_AND_ACTIVE_EVIDENCE_STALE"
        elif exit_confirmation_required:
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = "exit_confirmation_required_after_threshold_breach"
            label = "若仍持仓：退出后等待人工确认"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif monitored and run_gap and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        ):
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = "balanced_or_frozen_hard_exit_with_run_gap"
            label = "若已持仓：当前行情已触发硬退出（同时存在运行断档）"
            data_status = "RUN_GAP_ACTIVE_EVIDENCE_STALE"
        elif monitored and entry_basis_error:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = f"live_exit_policy_review:{entry_basis_error}"
            label = "持仓复权基准变化或缺失/人工复核"
            data_status = (
                "LIVE_EXIT_STATE_AND_RUN_GAP_AND_ACTIVE_EVIDENCE_STALE"
                if run_gap else "LIVE_EXIT_STATE_AND_ACTIVE_EVIDENCE_STALE"
            )
        elif run_gap and (pending or breakout_entry_pending) and _previous_threshold_breached(
            before, latest_price, intraday_low=intraday_low,
        ):
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = "run_gap_possible_entry_and_frozen_threshold_breached"
            label = "断档期间可能已成交且当前保护位触发/若持仓则退出"
            data_status = "RUN_GAP_REQUIRES_POSITION_CONFIRMATION"
        elif run_gap and (pending or breakout_entry_pending):
            action = "HOLD_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = "run_gap_entry_execution_unknown_manual_confirmation"
            label = "运行断档期间可能已触发入场/人工确认持仓"
            data_status = "RUN_GAP_REQUIRES_POSITION_CONFIRMATION"
        elif (pending or breakout_entry_pending) and not plan_rule_compatible:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "entry_plan_rule_version_incompatible"
            label = "旧入场计划规则版本不兼容"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif (pending or breakout_entry_pending) and plan_basis_error:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = plan_basis_error
            label = "入场计划复权基准变化或缺失/取消计划"
            data_status = (
                "PRICE_BASIS_AND_RUN_GAP_AND_ACTIVE_EVIDENCE_STALE"
                if run_gap else "PRICE_BASIS_AND_ACTIVE_EVIDENCE_STALE"
            )
        elif same_observation_changed and monitored:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = "same_trade_date_input_changed_position_review"
            label = "同一交易日行情被更正/持仓人工复核"
            data_status = "SAME_OBSERVATION_DATA_CHANGED_AND_ACTIVE_EVIDENCE_STALE"
        elif same_observation_changed and (pending or breakout_entry_pending):
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "same_trade_date_input_changed_entry_cancelled"
            label = "同一交易日行情被更正/取消入场计划"
            data_status = "SAME_OBSERVATION_DATA_CHANGED_AND_ACTIVE_EVIDENCE_STALE"
        elif live_exit_triggered:
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = f"balanced_exit_triggered:{live_exit_evaluation.get('reason')}"
            label = "若已持仓：balanced-v7 退出条件触发"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif monitored and logic_invalidation_breached:
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = "previous_logic_invalidation_breached"
            label = "若已持仓：原计划逻辑失效位触发"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif monitored and live_exit_error and breached:
            action = "SELL_EXIT"
            lifecycle = "EXIT_THRESHOLD_BREACHED"
            reason = "frozen_protective_stop_breached_live_state_unavailable"
            label = "若已持仓：退出状态异常且冻结保护位已触发"
            data_status = "LIVE_EXIT_STATE_AND_ACTIVE_EVIDENCE_STALE"
        elif monitored and live_exit_error:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = f"live_exit_policy_review:{live_exit_evaluation.get('error') or 'unknown'}"
            label = "退出状态或复权口径异常/人工复核"
            data_status = "LIVE_EXIT_STATE_AND_ACTIVE_EVIDENCE_STALE"
        elif monitored:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = (
                "run_gap_position_state_requires_manual_review"
                if run_gap else "left_current_research_watchlist_active_evidence_stale"
            )
            label = "取消新买入/可能持仓人工复核"
            data_status = "RUN_GAP_ACTIVE_EVIDENCE_STALE" if run_gap else "ACTIVE_EVIDENCE_STALE"
        elif breakout_entry_pending:
            if breakout_open_status == "ENTRY_RANGE_OBSERVED" and breakout_same_day_ambiguous:
                action = "HOLD_REVIEW"
                lifecycle = "POSITION_REVIEW"
                reason = "breakout_entry_and_plan_threshold_same_day_order_ambiguous"
                label = "入场与计划保护位同日交错/确认真实成交"
                trigger_today = True
            elif breakout_open_status == "ENTRY_RANGE_OBSERVED":
                action = "HOLD_REVIEW"
                lifecycle = "POSITION_REVIEW"
                reason = "breakout_next_open_entry_observed_active_evidence_stale"
                label = "突破开盘入场区已出现/公告证据需人工复核"
                trigger_today = True
            else:
                action = "CANCEL_BUY_REVIEW"
                lifecycle = "ENTRY_CANCELLED"
                reason = f"breakout_next_open_{breakout_open_status.lower()}"
                label = "突破确认后的开盘条件未满足"
            data_status = "RUN_GAP_ACTIVE_EVIDENCE_STALE" if run_gap else "ACTIVE_EVIDENCE_STALE"
        elif pending and pullback_entry_status == "OPEN_BELOW_ENTRY_BAND":
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "pullback_open_below_entry_band"
            label = "开盘低于回踩入场区/取消计划"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif pending and pullback_entry_status == "LOCKED_ONE_PRICE_UNEXECUTABLE":
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "pullback_locked_one_price_unexecutable"
            label = "一字板无法确认回踩成交/取消计划"
            data_status = "ACTIVE_EVIDENCE_STALE"
        elif pending and pullback_entry_status == "ENTRY_RANGE_OBSERVED":
            action = "HOLD_REVIEW"
            lifecycle = "POSITION_REVIEW"
            reason = (
                "pullback_entry_and_plan_threshold_same_day_order_ambiguous"
                if pullback_same_day_ambiguous
                else "pullback_entry_observed_active_evidence_stale"
            )
            label = "回踩入场区已出现/公告证据需人工复核"
            data_status = "ACTIVE_EVIDENCE_STALE"
            trigger_today = True
        else:
            action = "CANCEL_BUY_REVIEW"
            lifecycle = "ENTRY_CANCELLED"
            reason = "run_gap_entry_state_unreplayable" if run_gap else "left_current_research_watchlist"
            label = "取消新买入/持仓复核"
            data_status = "RUN_GAP_REQUIRES_REVIEW" if run_gap else "CURRENT_MARKET_DATA"
        origin_trade_date = (
            before.get("signal_plan_origin_trade_date")
            or before.get("latest_trade_date")
            or before.get("signal_observed_through_date")
        )
        assumed_entry_price = before.get("assumed_entry_price")
        entry_observation_trade_date = before.get("entry_observation_trade_date")
        entry_reference_adjusted_price = before.get("entry_reference_adjusted_price")
        exit_policy_adjusted_stop_price = before.get("exit_policy_adjusted_stop_price")
        entry_adjustment_ratio = before.get("entry_adjustment_ratio")
        entry_setup_trend = before.get("entry_setup_trend_confirmation_level")
        reference_entry_observed = bool(
            trigger_today and (breakout_entry_pending or pending)
        )
        if reference_entry_observed:
            assumed_entry_price = _observed_entry_price(
                before, market_row,
                entry_mode="breakout" if breakout_entry_pending else "pullback",
            )
            observation_date = _market_observation_date(market_row, as_of=as_of)
            entry_observation_trade_date = observation_date.isoformat() if observation_date else ""
            current_ratio = _safe_float(market_row.get("adjustment_ratio"))
            raw_stop = _safe_float(plan.get("stop_price"))
            entry_setup_trend = str(before.get("trend_confirmation_level") or "NONE")
            if (
                assumed_entry_price is not None and current_ratio is not None
                and current_ratio > 0 and raw_stop is not None
            ):
                entry_adjustment_ratio = current_ratio
                entry_reference_adjusted_price = assumed_entry_price / current_ratio
                exit_policy_adjusted_stop_price = raw_stop / current_ratio
                market_row["signal_plan_adjustment_ratio_status"] = "NOT_APPLICABLE"
                market_row["signal_plan_adjustment_ratio_current"] = ""
                market_row["entry_date_adjustment_ratio_status"] = "OK"
                market_row["entry_date_adjustment_ratio_current"] = round(current_ratio, 8)
        live_exit_policy_state = before.get("live_exit_policy_state")
        live_exit_status = str(before.get("live_exit_policy_status") or "NOT_STARTED")
        live_exit_reason = str(before.get("live_exit_policy_reason") or "")
        live_exit_holding_sessions = before.get("live_exit_holding_sessions") or 0
        live_exit_effective_stop = before.get("live_exit_effective_stop_price") or ""
        live_exit_reference_price = before.get("live_exit_reference_price") or ""
        if live_exit_evaluation.get("state"):
            live_exit_policy_state = live_exit_evaluation["state"]
            live_exit_status = str(live_exit_evaluation.get("status") or "")
            live_exit_reason = str(live_exit_evaluation.get("reason") or "")
            live_exit_holding_sessions = live_exit_evaluation.get("holding_sessions") or 0
            live_exit_effective_stop = live_exit_evaluation.get("effective_stop_raw") or ""
            live_exit_reference_price = live_exit_evaluation.get("exit_reference_raw") or ""
        elif live_exit_evaluation:
            live_exit_status = str(live_exit_evaluation.get("status") or "ERROR")
            live_exit_reason = str(live_exit_evaluation.get("error") or "unknown")
        elif reference_entry_observed:
            initial_exit = _evaluate_live_exit_policy(
                {
                    "entry_reference_adjusted_price": entry_reference_adjusted_price,
                    "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
                    "entry_adjustment_ratio": entry_adjustment_ratio,
                    "entry_setup_trend_confirmation_level": entry_setup_trend,
                    "logic_invalidation_price": plan.get("logic_invalidation_price"),
                },
                market_row, as_of=as_of, require_previous_state=False,
            )
            if initial_exit.get("state"):
                live_exit_policy_state = initial_exit["state"]
                live_exit_status = str(initial_exit.get("status") or "")
                live_exit_reason = str(initial_exit.get("reason") or "")
                live_exit_holding_sessions = initial_exit.get("holding_sessions") or 0
                live_exit_effective_stop = initial_exit.get("effective_stop_raw") or ""
                live_exit_reference_price = initial_exit.get("exit_reference_raw") or ""
                if initial_exit.get("status") == "EXIT_TRIGGERED":
                    action = "SELL_EXIT"
                    lifecycle = "EXIT_THRESHOLD_BREACHED"
                    label = "若当日实际成交：A股T+1，下一交易日开盘退出"
                    reason = f"entry_and_exit_same_day_t1:{initial_exit.get('reason')}"
            else:
                live_exit_status = str(initial_exit.get("status") or "ERROR")
                live_exit_reason = str(initial_exit.get("error") or "unknown")
                action = "CANCEL_BUY_REVIEW"
                lifecycle = "POSITION_REVIEW"
                label = "参考入场后的退出状态无法建立/人工复核"
                reason = f"live_exit_initialization_failed:{live_exit_reason}"
                data_status = "LIVE_EXIT_STATE_AND_ACTIVE_EVIDENCE_STALE"
        version_source = dict(before)
        version_source.update({
            "entry_reference_adjusted_price": entry_reference_adjusted_price,
            "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
            "entry_adjustment_ratio": entry_adjustment_ratio,
            "entry_setup_trend_confirmation_level": entry_setup_trend,
            "live_exit_policy_name": (
                before.get("live_exit_policy_name") or "balanced_hybrid_60d_exit"
            ),
            "live_exit_policy_version": (
                before.get("live_exit_policy_version") or LIVE_BALANCED_EXIT_POLICY_VERSION
            ),
        })
        input_version = _signal_input_version(version_source, market_row)
        signals.append({
            "signal_date": as_of.isoformat(), "valid_for_trade_date": next_trade_date.isoformat(),
            "code": code, "stock_name": before.get("stock_name"), "signal_action": action,
            "signal_label": label,
            "previous_level": before.get("user_visible_level") or "", "current_level": "",
            "signal_reason": reason,
            "signal_data_status": data_status,
            "signal_bar_processed": _signal_bar_processed(data_status),
            "previous_lifecycle_state": previous_lifecycle or "NONE",
            "current_lifecycle_state": lifecycle,
            "trigger_observed_today": trigger_today,
            "breakout_confirmation_observed_today": breakout_confirmation_today,
            "position_confirmation_required": (
                bool(before.get("last_position_confirmation_required")) if replay
                else action == "SELL_EXIT" or monitored or exit_confirmation_required
                or lifecycle == "POSITION_REVIEW"
            ),
            "actionability_rank": before.get("actionability_rank"),
            "latest_trade_date": market_row.get("latest_trade_date") or before.get("latest_trade_date"),
            "latest_price": market_row.get("raw_latest_close") or before.get("raw_latest_close"),
            "threshold_observation_price": (
                market_row.get("raw_latest_low")
                if market_row.get("raw_latest_low") not in {None, ""}
                else market_row.get("raw_latest_close") or before.get("raw_latest_close")
            ),
            "preferred_plan": before.get("preferred_plan"),
            "plan_id": before.get("plan_id") or _plan_id(
                before, origin_trade_date=origin_trade_date,
            ),
            "plan_rule_version": before.get("plan_rule_version") or "LEGACY_UNVERSIONED",
            "signal_plan_origin_trade_date": origin_trade_date,
            "signal_plan_adjustment_ratio": before.get("signal_plan_adjustment_ratio"),
            "signal_plan_adjustment_ratio_status": market_row.get(
                "signal_plan_adjustment_ratio_status",
            ),
            "signal_plan_adjustment_ratio_current": market_row.get(
                "signal_plan_adjustment_ratio_current",
            ),
            "signal_input_version": input_version,
            "entry_plan_age_sessions": before.get("entry_plan_age_sessions") or 0,
            **plan,
            "real_reward_risk_ratio": before.get("real_reward_risk_ratio"),
            "cancel_conditions": before.get("cancel_conditions"),
            "assumed_entry_price": assumed_entry_price,
            "entry_observation_trade_date": entry_observation_trade_date,
            "entry_reference_adjusted_price": entry_reference_adjusted_price,
            "exit_policy_adjusted_stop_price": exit_policy_adjusted_stop_price,
            "entry_adjustment_ratio": entry_adjustment_ratio,
            "entry_date_adjustment_ratio_status": market_row.get(
                "entry_date_adjustment_ratio_status",
            ),
            "entry_date_adjustment_ratio_current": market_row.get(
                "entry_date_adjustment_ratio_current",
            ),
            "entry_setup_trend_confirmation_level": entry_setup_trend,
            "live_exit_policy_name": before.get("live_exit_policy_name") or "balanced_hybrid_60d_exit",
            "live_exit_policy_version": before.get("live_exit_policy_version") or LIVE_BALANCED_EXIT_POLICY_VERSION,
            "live_exit_policy_state": live_exit_policy_state,
            "live_exit_policy_status": live_exit_status,
            "live_exit_policy_reason": live_exit_reason,
            "live_exit_holding_sessions": live_exit_holding_sessions,
            "live_exit_effective_stop_price": live_exit_effective_stop,
            "live_exit_reference_price": live_exit_reference_price,
            "exit_earliest_trade_date": (
                next_trade_date.isoformat() if action == "SELL_EXIT" else ""
            ),
            "exit_execution_timing": (
                DAILY_SIGNAL_EXECUTION_TIMING if action == "SELL_EXIT" else ""
            ),
            "breakout_required_volume": before.get("breakout_required_volume"),
            "risk_budget_initial_position_pct": 0.0, "risk_budget_max_position_pct": 0.0,
            **_signal_context_fields(before),
            "evidence_urls": before.get("evidence_urls"), "rule_version": RULE_VERSION,
            "no_auto_trade": True, "disclaimer": DISCLAIMER,
            "_same_observation_replay": replay,
        })
    action_rank = {
        "SELL_EXIT": 0, "CANCEL_BUY_REVIEW": 1, "BUY_IF_TRIGGERED": 2,
        "HOLD_REVIEW": 3, "WATCH_ONLY": 4,
    }
    signals.sort(key=lambda row: (
        action_rank.get(str(row.get("signal_action")), 9),
        int(_safe_float(row.get("actionability_rank")) or 9999),
        str(row.get("code")),
    ))
    return signals


def _build_signal_state_rows(
    *, current_rows: list[Mapping[str, Any]], previous: Mapping[str, Mapping[str, Any]],
    daily_signals: list[Mapping[str, Any]], current_market_rows: list[Mapping[str, Any]],
    as_of: date,
) -> list[dict[str, Any]]:
    """Persist active lifecycle state separately from the bounded research watchlist."""

    current_by_code = {
        _normalize_code(row.get("code")): dict(row) for row in current_rows
        if _normalize_code(row.get("code"))
    }
    market_by_code = {
        _normalize_code(row.get("code")): row for row in current_market_rows
        if _normalize_code(row.get("code"))
    }
    signal_by_code = {
        _normalize_code(row.get("code")): row for row in daily_signals
        if _normalize_code(row.get("code"))
    }
    state_by_code: dict[str, dict[str, Any]] = {}
    for code, row in current_by_code.items():
        signal = signal_by_code.get(code, {})
        before = previous.get(code, {})
        lifecycle = str(signal.get("current_lifecycle_state") or "NO_POSITION_SIGNAL")
        state = dict(row)
        signal_data_status = str(signal.get("signal_data_status") or "CURRENT_DATA")
        signal_bar_processed = bool(
            signal.get("signal_bar_processed", _signal_bar_processed(signal_data_status)),
        )
        unresolved_gap = not signal_bar_processed
        previous_observed = _safe_trade_date(
            before.get("signal_observed_through_date") or before.get("latest_trade_date"),
        )
        market = market_by_code.get(code, row)
        current_observed = _market_observation_date(market, as_of=as_of)
        processed_through = previous_observed if unresolved_gap else current_observed or previous_observed
        state["state_schema_version"] = SIGNAL_STATE_SCHEMA_VERSION
        state["signal_lifecycle_rule_version"] = SIGNAL_LIFECYCLE_RULE_VERSION
        state["signal_lifecycle_state"] = lifecycle
        state["signal_observed_through_date"] = (
            processed_through.isoformat() if processed_through else ""
        )
        state["scan_as_of_date"] = as_of.isoformat()
        state["unresolved_signal_gap"] = unresolved_gap
        state["last_signal_action"] = signal.get("signal_action") or "WATCH_ONLY"
        state["last_signal_label"] = signal.get("signal_label") or ""
        state["last_signal_reason"] = signal.get("signal_reason") or ""
        state["last_signal_data_status"] = signal_data_status
        state["last_signal_bar_processed"] = signal_bar_processed
        state["last_signal_input_version"] = signal.get("signal_input_version") or ""
        state["last_trigger_observed_today"] = bool(signal.get("trigger_observed_today"))
        state["last_breakout_confirmation_observed_today"] = bool(
            signal.get("breakout_confirmation_observed_today"),
        )
        state["last_position_confirmation_required"] = bool(
            signal.get("position_confirmation_required"),
        )
        if before and lifecycle in ACTIVE_SIGNAL_LIFECYCLES | TERMINAL_ENTRY_LIFECYCLES | {
            "ENTRY_PENDING",
        }:
            for field in FROZEN_SIGNAL_PLAN_FIELDS:
                if field in before:
                    state[field] = before.get(field)
            for field in ("risk_budget_initial_position_pct", "risk_budget_max_position_pct"):
                if field in before:
                    state[field] = before.get(field)
            state["signal_plan_origin_trade_date"] = (
                before.get("signal_plan_origin_trade_date")
                or before.get("latest_trade_date")
                or before.get("signal_observed_through_date")
            )
        elif lifecycle == "ENTRY_PENDING":
            state["signal_plan_origin_trade_date"] = row.get("latest_trade_date") or as_of.isoformat()
        for field in (
            "plan_id", "plan_rule_version", "signal_plan_origin_trade_date",
            "signal_plan_adjustment_ratio", "entry_plan_age_sessions",
            "assumed_entry_price", "entry_observation_trade_date",
            "entry_reference_adjusted_price", "exit_policy_adjusted_stop_price",
            "entry_adjustment_ratio", "entry_setup_trend_confirmation_level",
            "live_exit_policy_name", "live_exit_policy_version",
            "live_exit_policy_status", "live_exit_policy_reason",
            "live_exit_holding_sessions", "live_exit_effective_stop_price",
            "live_exit_reference_price",
        ):
            if signal.get(field) not in {None, ""}:
                state[field] = signal.get(field)
        if isinstance(signal.get("live_exit_policy_state"), Mapping):
            state["live_exit_policy_state"] = dict(signal["live_exit_policy_state"])
        if lifecycle in EXIT_CONFIRMATION_LIFECYCLES | TERMINAL_ENTRY_LIFECYCLES:
            state["terminal_trade_date"] = (
                signal.get("latest_trade_date")
                or state.get("signal_observed_through_date")
            )
            state["terminal_reason"] = signal.get("signal_reason") or ""
        state_by_code[code] = state

    for code, signal in signal_by_code.items():
        if code in state_by_code:
            continue
        lifecycle = str(signal.get("current_lifecycle_state") or "")
        if lifecycle not in ACTIVE_SIGNAL_LIFECYCLES | TERMINAL_ENTRY_LIFECYCLES:
            continue
        before = previous.get(code)
        if not before:
            continue
        state = dict(before)
        market = market_by_code.get(code, {})
        signal_data_status = str(signal.get("signal_data_status") or "ACTIVE_EVIDENCE_STALE")
        signal_bar_processed = bool(
            signal.get("signal_bar_processed", _signal_bar_processed(signal_data_status)),
        )
        unresolved_gap = not signal_bar_processed
        previous_observed = _safe_trade_date(
            before.get("signal_observed_through_date") or before.get("latest_trade_date"),
        )
        current_observed = _market_observation_date(market, as_of=as_of)
        processed_through = previous_observed if unresolved_gap else current_observed or previous_observed
        state["state_schema_version"] = SIGNAL_STATE_SCHEMA_VERSION
        state["signal_lifecycle_rule_version"] = SIGNAL_LIFECYCLE_RULE_VERSION
        state["signal_lifecycle_state"] = lifecycle
        state["signal_observed_through_date"] = (
            processed_through.isoformat() if processed_through else ""
        )
        state["scan_as_of_date"] = as_of.isoformat()
        state["unresolved_signal_gap"] = unresolved_gap
        state["last_signal_action"] = signal.get("signal_action") or "CANCEL_BUY_REVIEW"
        state["last_signal_label"] = signal.get("signal_label") or ""
        state["last_signal_reason"] = signal.get("signal_reason") or ""
        state["last_signal_data_status"] = signal_data_status
        state["last_signal_bar_processed"] = signal_bar_processed
        state["last_signal_input_version"] = signal.get("signal_input_version") or ""
        state["last_trigger_observed_today"] = bool(signal.get("trigger_observed_today"))
        state["last_breakout_confirmation_observed_today"] = bool(
            signal.get("breakout_confirmation_observed_today"),
        )
        state["last_position_confirmation_required"] = bool(
            signal.get("position_confirmation_required"),
        )
        if market:
            state["latest_trade_date"] = market.get("latest_trade_date") or state.get("latest_trade_date")
            for field in ("raw_latest_open", "raw_latest_high", "raw_latest_low", "raw_latest_close", "raw_latest_volume"):
                if market.get(field) not in {None, ""}:
                    state[field] = market.get(field)
        for field in (
            "plan_id", "plan_rule_version", "signal_plan_origin_trade_date",
            "signal_plan_adjustment_ratio", "entry_plan_age_sessions",
            "assumed_entry_price", "entry_observation_trade_date",
            "entry_reference_adjusted_price", "exit_policy_adjusted_stop_price",
            "entry_adjustment_ratio", "entry_setup_trend_confirmation_level",
            "live_exit_policy_name", "live_exit_policy_version",
            "live_exit_policy_status", "live_exit_policy_reason",
            "live_exit_holding_sessions", "live_exit_effective_stop_price",
            "live_exit_reference_price",
        ):
            if signal.get(field) not in {None, ""}:
                state[field] = signal.get(field)
        if isinstance(signal.get("live_exit_policy_state"), Mapping):
            state["live_exit_policy_state"] = dict(signal["live_exit_policy_state"])
        if lifecycle in EXIT_CONFIRMATION_LIFECYCLES | TERMINAL_ENTRY_LIFECYCLES:
            state["terminal_trade_date"] = (
                signal.get("latest_trade_date")
                or state.get("signal_observed_through_date")
            )
            state["terminal_reason"] = signal.get("signal_reason") or ""
        state_by_code[code] = state
    return list(state_by_code.values())


def build_actionable_execution_list(
    *, strict_rows: list[Mapping[str, Any]], next_trade_date: date,
    daily_signals: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Keep every currently valid strict trigger executable, independent of prior state."""
    result: list[dict[str, Any]] = []
    signals_by_code = {
        _normalize_code(item.get("code")): item for item in daily_signals
        if str(item.get("signal_action") or "") == "BUY_IF_TRIGGERED"
    }
    for row in strict_rows:
        if (
            str(row.get("market_regime_status") or "UNKNOWN") not in {"GREEN", "YELLOW"}
            or str(row.get("industry_regime_status") or "UNKNOWN") in {"UNKNOWN", "CRISIS"}
            or int(_safe_float(row.get("industry_regime_sample_count")) or 0) < 5
            or str(row.get("event_scan_status") or "UNKNOWN") != "OK"
            or str(row.get("event_risk_level") or "LOW") == "HIGH"
            or str(row.get("price_volume_state") or "NEUTRAL") in {"DISTRIBUTION", "CAPITULATION_RISK"}
            or row.get("real_world_gate_passed") is not True
        ):
            continue
        code = _normalize_code(row.get("code"))
        signal = signals_by_code.get(code, {})
        confirmed_next_open = (
            str(signal.get("signal_reason") or "") == "breakout_close_confirmed_next_open_pending"
        )
        signal_plan_available = bool(signal)
        preferred = str((signal if signal_plan_available else row).get("preferred_plan") or "")
        plan = {
            "entry_low": signal.get("entry_low"), "entry_high": signal.get("entry_high"),
            "stop_price": signal.get("stop_price"),
            "logic_invalidation_price": signal.get("logic_invalidation_price"),
            "target_1": signal.get("target_1"), "target_2": signal.get("target_2"),
        } if signal_plan_available else _signal_plan_fields(row)
        if preferred == "pullback":
            trigger_condition = "价格进入回踩区间且未先跌破止损/失效位；不得在区间上沿之上追价"
            required_volume: Any = ""
            max_buy_price = plan.get("entry_high")
        elif preferred == "breakout":
            required_volume = signal.get("breakout_required_volume") or row.get("breakout_required_volume")
            if confirmed_next_open:
                trigger_condition = (
                    "上一完整交易日已经收盘放量确认；仅当本清单适用日开盘价位于"
                    f"{plan.get('entry_low')}-{plan.get('entry_high')} 时人工考虑，"
                    "低于原突破价或高于最高追价均取消"
                )
                max_buy_price = plan.get("entry_high")
            else:
                trigger_condition = (
                    f"收盘价突破{row.get('breakout_trigger_price')}且整日成交量达到{required_volume}；"
                    "确认日不追买，等待下一交易日开盘条件清单"
                )
                max_buy_price = row.get("breakout_max_chase_price")
        else:
            continue
        plan_entry_low = _safe_float(plan.get("entry_low"))
        plan_entry_high = _safe_float(plan.get("entry_high"))
        plan_stop = _safe_float(plan.get("stop_price"))
        plan_target = _safe_float(plan.get("target_1"))
        if not (
            plan_entry_low is not None and plan_entry_high is not None
            and plan_stop is not None and plan_target is not None
            and plan_stop < plan_entry_low <= plan_entry_high < plan_target
        ):
            continue
        reward_risk_source = signal if signal_plan_available else row
        result.append({
            "valid_for_trade_date": next_trade_date.isoformat(),
            "code": code, "stock_name": row.get("stock_name"),
            "execution_action": "BUY_IF_TRIGGERED", "preferred_plan": preferred,
            "plan_id": signal.get("plan_id") if signal_plan_available else row.get("plan_id"),
            "plan_rule_version": (
                signal.get("plan_rule_version") if signal_plan_available
                else row.get("plan_rule_version") or RULE_VERSION
            ),
            "trigger_condition": trigger_condition, **plan,
            "max_buy_price": max_buy_price, "required_volume": required_volume,
            "real_reward_risk_ratio": reward_risk_source.get("real_reward_risk_ratio"),
            "risk_budget_initial_position_pct": (
                signal.get("risk_budget_initial_position_pct") if signal_plan_available
                else row.get("risk_budget_initial_position_pct")
            ) or 0.0,
            "risk_budget_max_position_pct": (
                signal.get("risk_budget_max_position_pct") if signal_plan_available
                else row.get("risk_budget_max_position_pct")
            ) or 0.0,
            "position_rule": "仅在触发后建初始仓；已有该股仓位时不得把本清单当作重复加仓指令；总仓位不得超过单股上限",
            "cancel_conditions": reward_risk_source.get("cancel_conditions"),
            "industry_evidence_status": row.get("industry_evidence_status"),
            "company_evidence_status": row.get("company_evidence_status"),
            "hard_logic_level": row.get("hard_logic_level"),
            "exit_profile_status": row.get("exit_profile_status"),
            "exit_profile_entry_mode": row.get("exit_profile_entry_mode"),
            "profile_validation_scope": row.get("profile_validation_scope"),
            "profile_position_multiplier": row.get("profile_position_multiplier"),
            "market_regime_status": row.get("market_regime_status"),
            "market_regime_score": row.get("market_regime_score"),
            "market_position_multiplier": row.get("market_position_multiplier"),
            "external_risk_level": row.get("external_risk_level"),
            "industry_regime_status": row.get("industry_regime_status"),
            "industry_regime_score": row.get("industry_regime_score"),
            "industry_regime_sample_count": row.get("industry_regime_sample_count"),
            "price_volume_state": row.get("price_volume_state"),
            "event_risk_level": row.get("event_risk_level"),
            "event_scan_status": row.get("event_scan_status"),
            "real_world_score": row.get("real_world_score"),
            "real_world_gate_passed": row.get("real_world_gate_passed"),
            "real_world_risk_flags": row.get("real_world_risk_flags"),
            "evidence_urls": row.get("evidence_urls"), "rule_version": RULE_VERSION,
            "no_auto_trade": True, "disclaimer": DISCLAIMER,
        })
    return result


def build_daily_candidate_top5(
    *, deep_rows: list[Mapping[str, Any]], daily_signals: list[Mapping[str, Any]],
    fallback_rows: list[Mapping[str, Any]] = (), limit: int = 5,
) -> list[dict[str, Any]]:
    """Return stable, unique research candidates without weakening buy gates."""

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    signals_by_code = {
        _normalize_code(row.get("code")): row for row in daily_signals
    }

    def failed_names(row: Mapping[str, Any]) -> list[str]:
        raw = str(row.get("strict_gate_failed") or row.get("missing_conditions") or "")
        return [name for name in raw.split(";") if name]

    def failure_family(name: str) -> str:
        if name.startswith("exit_profile_"):
            return "exit_profile"
        if name.startswith("event_risk_"):
            return "event_risk"
        if name in {"real_rr_1_8", "ready_plan"}:
            return "entry_plan"
        if name in {"industry_evidence", "company_evidence", "strict_official_evidence", "hard_logic_medium"}:
            return "evidence_logic"
        if name in {"trend_medium", "above_ma60", "ma60_not_down", "not_falling_knife"}:
            return "trend"
        return name

    safety_gates = {
        "no_hard_risk", "market_regime_not_red", "industry_regime_not_crisis",
        "event_risk_known", "event_risk_not_high", "price_volume_not_distribution",
        "execution_not_high", "value_trap_not_high", "price_mapping_ok",
    }

    def proximity_key(row: Mapping[str, Any]) -> tuple[int, int, int, int]:
        names = failed_names(row)
        return (
            sum(name in safety_gates for name in names),
            len({failure_family(name) for name in names}),
            int(_safe_float(row.get("strict_gate_fail_count")) or len(names) or 10**6),
            int(_safe_float(row.get("actionability_rank")) or 10**9),
        )

    ordered_deep = sorted(
        deep_rows,
        key=lambda row: (
            0 if str(signals_by_code.get(_normalize_code(row.get("code")), {}).get("signal_action")) == "BUY_IF_TRIGGERED" else 1,
            *proximity_key(row),
        ),
    )
    ordered_fallback = sorted(
        (
            row for row in fallback_rows
            if str(row.get("quant_status") or "") != "HARD_REJECT"
            and not str(row.get("hard_blockers") or "").strip()
        ),
        key=lambda row: int(_safe_float(row.get("quant_rank")) or 10**9),
    )
    for source in (*ordered_deep, *ordered_fallback):
        code = _normalize_code(source.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        row = dict(source)
        signal = signals_by_code.get(code, {})
        action = str(signal.get("signal_action") or "WATCH_ONLY")
        formal = action == "BUY_IF_TRIGGERED"
        row["candidate_rank"] = len(result) + 1
        row["candidate_action"] = action
        row["candidate_reason"] = signal.get("signal_reason") or "deep_review_not_available"
        row["formal_buy_eligible"] = formal
        names = failed_names(row)
        row["strict_safety_blocker_count"] = sum(name in safety_gates for name in names)
        row["strict_gate_failure_family_count"] = len({failure_family(name) for name in names})
        if not formal and row.get("strict_gate_failed"):
            row["missing_conditions"] = row["strict_gate_failed"]
        if not formal:
            row["risk_budget_initial_position_pct"] = 0.0
            row["risk_budget_max_position_pct"] = 0.0
        if not row.get("user_visible_level"):
            row["user_visible_level"] = "RESEARCH_PENDING"
            row["missing_conditions"] = "deep_review_not_available"
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _execution_list_markdown(summary: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "# 次日可执行条件买入清单", "", DISCLAIMER, "",
        f"- 适用交易日: {summary.get('next_trade_date')}",
        f"- 当前有效条件买入: {len(rows)}",
        f"- 退出策略验证状态: "
        f"{(summary.get('exit_profile_strategy_health') or {}).get('status') or 'UNKNOWN'}", "",
        "只有触发条件在适用交易日真实满足时才可人工执行；未触发、超过最高买价或出现取消条件时不买。", "",
    ]
    if not rows:
        lines.extend(["当前没有通过全部严格门槛的股票，因此没有可执行买入标的。", ""])
    for row in rows:
        lines.extend([
            f"## {row.get('stock_name')} ({row.get('code')})", "",
            f"- 方案: {row.get('preferred_plan')}；触发: {row.get('trigger_condition')}",
            f"- 冻结计划: {row.get('plan_id')}（规则 {row.get('plan_rule_version')}）",
            f"- 买入区间: {row.get('entry_low')} - {row.get('entry_high')}；最高买价: {row.get('max_buy_price')}",
            f"- 止损/失效: {row.get('stop_price')} / {row.get('logic_invalidation_price')}",
            f"- 目标: {row.get('target_1')} / {row.get('target_2')}；真实盈亏比: {row.get('real_reward_risk_ratio')}",
            f"- 初始/单股最高仓位: {row.get('risk_budget_initial_position_pct')}% / {row.get('risk_budget_max_position_pct')}%",
            f"- 退出验证: {row.get('profile_validation_scope')}；画像仓位系数 {row.get('profile_position_multiplier')}",
            f"- 现实风险: 市场 {row.get('market_regime_status')} / 行业 {row.get('industry_regime_status')} / 量价 {row.get('price_volume_state')} / 事件 {row.get('event_risk_level')}",
            f"- 取消条件: {row.get('cancel_conditions')}", "",
        ])
    return "\n".join(lines) + "\n"


def _daily_signals_markdown(
    summary: Mapping[str, Any], rows: list[Mapping[str, Any]],
    candidate_top5: list[Mapping[str, Any]] | None = None,
) -> str:
    lines = [
        "# 每日买入/卖出研究信号", "", DISCLAIMER, "",
        f"- 信号日期: {summary.get('as_of_date')}",
        f"- 适用交易日: {summary.get('next_trade_date')}",
        f"- 条件买入: {summary.get('buy_signal_count')}",
        f"- 持有复核: {summary.get('hold_signal_count')}",
        f"- 退出信号: {summary.get('sell_signal_count')}",
        f"- 取消新买入/持仓复核: {summary.get('cancel_buy_review_count')}",
        f"- 仅观察: {summary.get('watch_signal_count')}", "",
        f"- 市场状态: {summary.get('market_regime_status')}（{summary.get('market_regime_score')}）",
        f"- 外围风险: {summary.get('external_risk_level')}", "",
        f"- 信号状态连续性: {summary.get('signal_state_continuity_status')}",
        f"- 退出画像长历史质量: {summary.get('exit_profile_history_data_quality')}",
        f"- 退出策略验证状态: "
        f"{(summary.get('exit_profile_strategy_health') or {}).get('status') or 'UNKNOWN'}", "",
        "买入信号只有在价格进入指定区间且盘前公告、停牌与数据核对无异常时才成立。参考入场被观察后，退出按同一套 balanced-v7 规则逐日跟踪：保护止损、确认后的趋势破坏、盈利回撤、长期未修复或第 60 个参考持有交易日都可触发；原计划逻辑失效位仍是额外保护。", "",
    ]
    actionable = [row for row in rows if row.get("signal_action") != "WATCH_ONLY"]
    if not actionable:
        lines.extend(["本次没有满足严格门槛的买入、持有或退出信号。", ""])
    for row in actionable:
        lines.extend([
            f"## {row.get('stock_name')} ({row.get('code')}) - {row.get('signal_action')}", "",
            f"- 原因: {row.get('signal_reason')}",
            f"- 数据状态/生命周期: {row.get('signal_data_status')} / {row.get('current_lifecycle_state')}",
            f"- 冻结计划: {row.get('plan_id')}（规则 {row.get('plan_rule_version')}；已观察 {row.get('entry_plan_age_sessions')} 个交易日）",
            f"- 最新价格: {row.get('latest_price')}（{row.get('latest_trade_date')}）",
            f"- 条件区间: {row.get('entry_low')}-{row.get('entry_high')}",
            f"- 止损/失效: {row.get('stop_price')} / {row.get('logic_invalidation_price')}",
            f"- 目标: {row.get('target_1')} / {row.get('target_2')}",
            f"- 风险预算参考: {row.get('risk_budget_initial_position_pct')}%-{row.get('risk_budget_max_position_pct')}%",
            f"- 退出验证: {row.get('profile_validation_scope')}；画像仓位系数 {row.get('profile_position_multiplier')}",
            f"- 参考退出状态: {row.get('live_exit_policy_status') or 'NOT_STARTED'}；参考持有 {row.get('live_exit_holding_sessions') or 0} 个交易日；当前有效保护位 {row.get('live_exit_effective_stop_price') or '未建立'}；触发原因 {row.get('live_exit_policy_reason') or 'none'}",
            f"- 现实风险: 市场 {row.get('market_regime_status')} / 行业 {row.get('industry_regime_status')} / 量价 {row.get('price_volume_state')} / 事件 {row.get('event_risk_level')}",
            f"- 现实信号分: {row.get('real_world_score')}；风险标记: {row.get('real_world_risk_flags') or 'none'}", "",
        ])
    lines.extend([
        "退出画像和逐日退出状态都不表示用户已经成交；所有 HOLD/SELL 都以“若此前实际成交且仍持有”为前提。退出触发价是收盘后研究参考，真实人工卖出通常只能在随后可交易时执行，跳空会造成价差。状态断档、复权比例变化、公告证据滞后或计划版本不兼容时，系统会取消新买入并要求人工复核。",
        "",
    ])
    lines.extend([
        "## 今日五只优先候选", "",
        "这五只是策略排序后的次日研究候选，不等于五只都可以买。只有标为 BUY_IF_TRIGGERED 且盘中真实满足触发条件的股票，才会同时进入正式可执行清单。", "",
    ])
    for candidate in candidate_top5 or []:
        lines.append(
            f"- #{candidate.get('candidate_rank')} {candidate.get('stock_name')}({candidate.get('code')}): "
            f"{candidate.get('candidate_action')}；层级 {candidate.get('user_visible_level')}；"
            f"市场/行业/量价/事件={candidate.get('market_regime_status')}/"
            f"{candidate.get('industry_regime_status')}/{candidate.get('price_volume_state')}/"
            f"{candidate.get('event_risk_level')}；严格失败 {candidate.get('strict_gate_fail_count')} 项；"
            f"尚缺 {candidate.get('missing_conditions') or 'none'}"
        )
        lines.append(
            f"  - 退出画像诊断: "
            f"{candidate.get('exit_profile_blocker_detail') or 'not_available'}"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _change_markdown(title: str, rows: list[Mapping[str, Any]], include_types: set[str]) -> str:
    selected = [row for row in rows if str(row.get("change_type")) in include_types]
    lines = [f"# {title}", "", DISCLAIMER, ""]
    if not selected:
        lines.append("本次没有对应变化。")
    for row in selected:
        lines.append(f"- {row.get('stock_name')}({row.get('code')}): {row.get('change_type')}，{row.get('detail') or ''}")
    return "\n".join(lines) + "\n"


def select_exit_profile_exploration_rows(
    quant_rows: Iterable[Mapping[str, Any]], *, exclude_codes: Iterable[str],
    as_of: date, prior_validated_codes: Iterable[str] = (),
    limit: int = EXIT_PROFILE_EXPLORATION_LIMIT,
) -> list[dict[str, Any]]:
    """Select a weekly rotating, industry-diverse profile exploration queue.

    Selection never uses newly calculated outcomes.  It first retains valid
    profiles from prior runs, then rotates across current quant-research rows
    using only ISO week, quant tier, industry and code.  This lets stocks
    outside the bounded Top80 become profile-eligible without relaxing gates.
    """

    excluded = {_normalize_code(code) for code in exclude_codes}
    prior_codes = {_normalize_code(code) for code in prior_validated_codes}
    eligible_by_code: dict[str, dict[str, Any]] = {}
    for source in quant_rows:
        row = dict(source)
        code = _normalize_code(row.get("code"))
        if (
            not code or code in excluded or code in eligible_by_code
            or str(row.get("quant_status") or "")
            not in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}
        ):
            continue
        row["code"] = code
        eligible_by_code[code] = row
    target = max(0, int(limit))
    if not target:
        return []
    iso = as_of.isocalendar()
    rotation_bucket = f"{iso.year}-W{iso.week:02d}"

    def rotating_key(row: Mapping[str, Any]) -> tuple[int, str]:
        tier = 0 if str(row.get("quant_status")) == "PRIORITY_RESEARCH" else 1
        rotation_payload = (
            f"{EXIT_PROFILE_EXPLORATION_SELECTION_VERSION}|{rotation_bucket}|"
            f"{row.get('industry')}|{row.get('code')}"
        )
        digest = hashlib.sha256(rotation_payload.encode()).hexdigest()
        return tier, digest

    selected: list[dict[str, Any]] = []
    selected_codes: set[str] = set()

    def append(source: Mapping[str, Any], reason: str) -> None:
        code = _normalize_code(source.get("code"))
        if not code or code in selected_codes or len(selected) >= target:
            return
        selected_codes.add(code)
        selected.append({
            **dict(source),
            "exit_profile_exploration_reason": reason,
            "exit_profile_exploration_rotation_bucket": rotation_bucket,
            "exit_profile_exploration_selection_version": (
                EXIT_PROFILE_EXPLORATION_SELECTION_VERSION
            ),
        })

    for row in sorted(
        (eligible_by_code[code] for code in prior_codes if code in eligible_by_code),
        key=lambda item: (
            -(_safe_float(item.get("quant_score")) or 0.0),
            _normalize_code(item.get("code")),
        ),
    ):
        append(row, "PRIOR_VALIDATED_PROFILE_REFRESH")

    remaining = [
        row for code, row in eligible_by_code.items() if code not in selected_codes
    ]
    first_by_industry: dict[str, dict[str, Any]] = {}
    selected_industries = {
        str(row.get("industry") or "UNRESOLVED") for row in selected
    }
    for row in sorted(remaining, key=rotating_key):
        industry = str(row.get("industry") or "UNRESOLVED")
        if industry in selected_industries:
            continue
        first_by_industry.setdefault(industry, row)
    for row in sorted(first_by_industry.values(), key=rotating_key):
        append(row, "WEEKLY_INDUSTRY_ROTATION")
    for row in sorted(remaining, key=rotating_key):
        append(row, "WEEKLY_ROTATION_FILL")
    return selected


def select_exit_validation_reference_rows(
    quant_rows: Iterable[Mapping[str, Any]], *, exclude_codes: Iterable[str],
    per_board: int = EXIT_VALIDATION_REFERENCE_PER_BOARD,
) -> list[dict[str, Any]]:
    """Select a fixed, industry-diverse reference partition independent of Top80.

    Selection uses only board, industry and a versioned hash of the stock code;
    it never refills from today's rank, score or outcome when a reference stock
    is also a candidate. The profile refresher applies target-code leave-one-out
    rather than changing the reference partition from day to day.
    """

    # Kept in the public signature for callers from the v1 contract. Exclusion
    # must not alter the fixed partition; target-specific leave-one-out belongs
    # in the validator, not in reference selection.
    _ = tuple(_normalize_code(code) for code in exclude_codes)
    by_board: dict[str, list[dict[str, Any]]] = {board: [] for board in ("SSE_MAIN", "SZSE_MAIN", "STAR", "CHINEXT")}
    for source in quant_rows:
        row = dict(source)
        code = _normalize_code(row.get("code"))
        board = str(row.get("board") or "")
        if not code or board not in by_board:
            continue
        row["code"] = code
        by_board[board].append(row)

    selected: list[dict[str, Any]] = []
    limit = max(0, int(per_board))
    for board, rows in by_board.items():
        ordered = sorted(
            rows,
            key=lambda row: hashlib.sha256(
                f"{EXIT_VALIDATION_REFERENCE_SELECTION_VERSION}|{board}|{row['code']}".encode()
            ).hexdigest(),
        )
        board_selected: list[dict[str, Any]] = []
        used_industries: set[str] = set()
        for row in ordered:
            industry = str(row.get("industry") or "UNKNOWN")
            if industry in used_industries:
                continue
            board_selected.append(row)
            used_industries.add(industry)
            if len(board_selected) >= limit:
                break
        selected_codes = {_normalize_code(row.get("code")) for row in board_selected}
        for row in ordered:
            if len(board_selected) >= limit:
                break
            if _normalize_code(row.get("code")) in selected_codes:
                continue
            board_selected.append(row)
            selected_codes.add(_normalize_code(row.get("code")))
        selected.extend(board_selected)
    return selected


def _add_exit_validation_reference_specs(
    entry_plan_specs: dict[str, dict[str, Any]],
    references: Iterable[Mapping[str, Any]],
    board_rules: Mapping[str, BoardRule],
) -> None:
    """Add reference defaults without replacing a live candidate's plan mode."""

    for reference in references:
        code = _normalize_code(reference.get("code"))
        board_rule = board_rules.get(str(reference.get("board")))
        if not code or board_rule is None:
            continue
        entry_plan_specs.setdefault(code, {
            "entry_mode": "pullback",
            "breakout_volume_ratio": board_rule.breakout_volume_ratio,
            "max_chase_atr_multiple": board_rule.max_chase_atr_multiple,
            "volatility_multiplier": board_rule.volatility_multiplier,
            "minimum_history_rows": board_rule.minimum_history_rows,
            "minimum_turnover": board_rule.minimum_turnover,
            "max_5d_return_pct": board_rule.max_5d_return_pct,
            "max_10d_return_pct": board_rule.max_10d_return_pct,
            "trigger_window_days": 10,
        })


def _research_queue(
    quant_rows: list[Mapping[str, Any]], *, limit: int,
) -> list[dict[str, Any]]:
    """Keep the normal queue first and use safe LOW_PRIORITY rows only for research coverage."""

    selected = [
        dict(row) for row in quant_rows
        if row.get("quant_status") in {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}
    ][:limit]
    seen = {_normalize_code(row.get("code")) for row in selected}
    for row in quant_rows:
        if len(selected) >= limit:
            break
        code = _normalize_code(row.get("code"))
        if (
            row.get("quant_status") != "LOW_PRIORITY"
            or str(row.get("hard_blockers") or "").strip()
            or not code or code in seen
        ):
            continue
        selected.append(dict(row))
        seen.add(code)
    return selected


def _fundamentals(
    quant_rows: list[dict[str, Any]], qfq_histories: Mapping[str, pd.DataFrame],
    config: AllAScanConfig, *, priority_codes: Iterable[str] = (),
    required_codes: Iterable[str] = (),
) -> tuple[list[BacktestInput], dict[str, str]]:
    selected = _research_queue(quant_rows, limit=config.evidence_queue_size)
    required = {_normalize_code(code) for code in required_codes if _normalize_code(code)}
    selected_codes = {_normalize_code(row.get("code")) for row in selected}
    for row in quant_rows:
        code = _normalize_code(row.get("code"))
        if code in required and code not in selected_codes:
            selected.append(dict(row))
            selected_codes.add(code)
    loader = PublicFundamentalLoader(config.fundamental_cache_dir)
    inputs: list[BacktestInput] = []
    errors: dict[str, str] = {}
    priority = {_normalize_code(code) for code in priority_codes} | required
    fetch_order = sorted(
        selected,
        key=lambda row: (
            _normalize_code(row.get("code")) not in priority,
            int(row.get("quant_rank") or 10**9),
        ),
    )
    required_selected_count = len(required & selected_codes)
    fetch_limit = max(config.fundamental_limit, required_selected_count)
    fetched_by_code: dict[str, tuple[pd.DataFrame | None, pd.DataFrame | None]] = {}
    for row in fetch_order[:fetch_limit]:
        code = str(row["code"])
        valuation_df = None
        financial_df = None
        try:
            fetched = loader.load(code, years=5, fetch_valuation=True, fetch_financial=True)
            valuation_df = fetched.valuation_df
            financial_df = fetched.financial_df
            if fetched.provider_errors:
                errors[code] = json.dumps(fetched.provider_errors, ensure_ascii=False, sort_keys=True)
        except Exception as exc:
            errors[code] = f"{type(exc).__name__}: {exc}"
        fetched_by_code[code] = (valuation_df, financial_df)
    for row in selected:
        code = str(row["code"])
        valuation_df, financial_df = fetched_by_code.get(code, (None, None))
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
    market_multiplier = _safe_float(row.get("market_position_multiplier"))
    if market_multiplier is None:
        market_multiplier = 1.0
    industry_multiplier = 0.75 if str(row.get("industry_regime_status")) == "WEAK" else 1.0
    event_multiplier = 0.75 if str(row.get("event_risk_level")) == "MEDIUM" else 1.0
    price_volume_multiplier = 0.8 if str(row.get("price_volume_state")) == "WEAK_DEMAND" else 1.0
    exit_profile_multiplier = _safe_float(row.get("profile_position_multiplier"))
    if exit_profile_multiplier is None:
        exit_profile_multiplier = 1.0
    multiplier = max(
        0.0,
        min(
            1.0,
            market_multiplier * industry_multiplier * event_multiplier * price_volume_multiplier
            * max(0.0, min(1.0, exit_profile_multiplier)),
        ),
    )
    row["risk_budget_initial_position_pct"] = round(initial * multiplier, 2) if strict else 0.0
    row["risk_budget_max_position_pct"] = round(maximum * multiplier, 2) if strict else 0.0


def _merge_deep_rows(
    *, quant_rows: list[dict[str, Any]], deep_report: Path,
    adjusted_histories: Mapping[str, pd.DataFrame],
    raw_histories: Mapping[str, pd.DataFrame],
    price_audits: Mapping[str, Mapping[str, Any]], board_rules: Mapping[str, BoardRule],
    exit_profiles: Mapping[str, Mapping[str, Any]], max_watchlist: int, as_of: date,
    market_regime: Mapping[str, Any], industry_regimes: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads((deep_report / "daily_opportunity_report.json").read_text(encoding="utf-8"))
    evidence_rows = list(csv.DictReader((deep_report / "evidence_inventory.csv").open(encoding="utf-8")))
    evidence_audit_path = deep_report / "auto_evidence_audit.csv"
    event_scan_rows = (
        list(csv.DictReader(evidence_audit_path.open(encoding="utf-8")))
        if evidence_audit_path.exists()
        else []
    )
    quant_by_code = {str(row["code"]): row for row in quant_rows}
    all_rows: list[dict[str, Any]] = []
    for deep in payload.get("all_opportunities") or []:
        code = _normalize_code(deep.get("code"))
        quant = quant_by_code.get(code, {})
        raw = raw_histories.get(code, pd.DataFrame())
        adjusted = adjusted_histories.get(code, pd.DataFrame())
        if raw.empty or adjusted.empty:
            continue
        urls = _evidence_urls(evidence_rows, deep)
        board = str(quant.get("board") or "")
        if board not in board_rules:
            continue
        plan = build_price_plan(
            deep, raw, board_rules[board], urls, adjusted_history=adjusted,
        )
        profile = enrich_exit_profile(exit_profiles.get(code, {}), as_of=as_of)
        official_evidence = strict_official_evidence_audit(evidence_rows, deep, as_of=as_of)
        merged = {
            **deep, **quant, **dict(price_audits.get(code, {})), **profile, **official_evidence, **plan,
            "code": code, "stock_name": deep.get("stock_name") or quant.get("stock_name"),
            "exchange": quant.get("exchange"), "board": board,
            "industry": deep.get("normalized_industry") or quant.get("industry") or deep.get("raw_industry"),
            "industry_regime_key": quant.get("industry") or deep.get("normalized_industry") or deep.get("raw_industry"),
            "industry_evidence_status": deep.get("industry_evidence_status") or "MISSING",
            "company_evidence_status": deep.get("company_evidence_status") or "MISSING",
            "hard_logic_level": deep.get("hard_logic_level") or "NONE",
            "exit_profile_status": profile.get("exit_profile_status") or "NOT_AVAILABLE",
            "evidence_urls": ";".join(urls), "disclaimer": DISCLAIMER,
        }
        merged.update(enrich_real_world_signals(
            merged,
            market_regime=market_regime,
            industry_regimes=industry_regimes,
            evidence_rows=evidence_rows,
            event_scan_rows=event_scan_rows,
            as_of=as_of,
        ))
        level, missing = classify_candidate(merged, plan, profile, urls, board_rule=board_rules[board])
        strict_checks = strict_candidate_checks(merged, plan, profile, board_rule=board_rules[board])
        strict_missing = [name for name, passed in strict_checks.items() if not passed]
        merged["classification"] = level
        merged["user_visible_level"] = level
        # `missing` explains the broad research tier. User-facing buy blockers
        # must instead name every failed strict gate; conflating the two made a
        # seven-gate miss look like a single `near_ma60` issue.
        merged["classification_missing_conditions"] = ";".join(missing)
        merged["missing_conditions"] = ";".join(strict_missing)
        merged["top_risks"] = deep.get("top_risks") or ";".join(strict_missing[:3])
        merged["upgrade_conditions"] = deep.get("upgrade_conditions") or ";".join(strict_missing)
        merged["strict_gate_pass_count"] = sum(strict_checks.values())
        merged["strict_gate_fail_count"] = sum(not passed for passed in strict_checks.values())
        merged["strict_gate_failed"] = ";".join(strict_missing)
        merged["strict_gate_checks"] = json.dumps(strict_checks, ensure_ascii=False, sort_keys=True)
        merged["actionability_score"] = actionability_score(merged, plan)
        _apply_position_budget(merged, plan, level)
        all_rows.append(merged)
    all_rows.sort(key=lambda row: (_safe_float(row.get("actionability_score")) or 0.0), reverse=True)
    for index, row in enumerate(all_rows, 1):
        row["actionability_rank"] = index
    selected: list[dict[str, Any]] = []
    level_limits = {
        "STRICT_REVIEW_READY": max_watchlist,
        "CONDITION_WATCH": 5,
        "RESEARCH_WATCH": 10,
    }
    for desired_level in ("STRICT_REVIEW_READY", "CONDITION_WATCH", "RESEARCH_WATCH"):
        added = 0
        for row in all_rows:
            if str(row.get("user_visible_level")) != desired_level or added >= level_limits[desired_level]:
                continue
            selected.append(row)
            added += 1
            if len(selected) >= max_watchlist:
                return selected, all_rows
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
        f"- 市场状态: {summary.get('market_regime_status')}（{summary.get('market_regime_score')}）",
        f"- 外围风险: {summary.get('external_risk_level')}",
        f"- 市场风险原因: {';'.join(summary.get('market_regime_risk_reasons') or []) or 'none'}", "",
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
            f"- real-world: market {row.get('market_regime_status')} / industry {row.get('industry_regime_status')} / price-volume {row.get('price_volume_state')} / event {row.get('event_risk_level')} / score {row.get('real_world_score')}",
            f"- real-world risk flags: {row.get('real_world_risk_flags') or 'none'}",
            f"- missing conditions: {row.get('missing_conditions') or 'none'}",
            f"- evidence: {row.get('evidence_urls') or 'none'}", "",
        ])
    return "\n".join(lines) + "\n"


def _candidate_top5_markdown(summary: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    lines = [
        "# 每日五只优先候选", "", DISCLAIMER, "",
        f"- 信号日期: {summary.get('as_of_date')}",
        f"- 适用交易日: {summary.get('next_trade_date')}",
        f"- 市场状态: {summary.get('market_regime_status')}（{summary.get('market_regime_score')}）", "",
        f"- 退出策略验证状态: "
        f"{(summary.get('exit_profile_strategy_health') or {}).get('status') or 'UNKNOWN'}", "",
        "本表固定展示策略最优先复核的五只股票：正式买入优先，其余先避开安全阻断，再按失败门槛族和失败总数排序；不等于强行给出五只正式买入。只有 BUY_IF_TRIGGERED 同时出现在 actionable_execution_list 时，才具备条件执行资格。", "",
    ]
    for row in rows:
        lines.extend([
            f"## #{row.get('candidate_rank')} {row.get('stock_name')} ({row.get('code')}) - {row.get('candidate_action')}", "",
            f"- 层级/得分: {row.get('user_visible_level')} / {row.get('actionability_score')}",
            f"- 严格差距: 安全阻断 {row.get('strict_safety_blocker_count')}；失败门槛族 {row.get('strict_gate_failure_family_count')}；失败门槛 {row.get('strict_gate_fail_count')}",
            f"- 退出验证: {row.get('profile_validation_scope')}；自身样本 {row.get('stock_signal_count')}；参考时期 {row.get('cohort_period_count')}；画像仓位系数 {row.get('profile_position_multiplier')}",
            f"- 退出画像诊断: {row.get('exit_profile_blocker_detail') or 'not_available'}",
            f"- 现实风险: 市场 {row.get('market_regime_status')} / 行业 {row.get('industry_regime_status')} / 量价 {row.get('price_volume_state')} / 事件 {row.get('event_risk_level')}",
            f"- 尚缺条件: {row.get('missing_conditions') or 'none'}",
            f"- 计划: {row.get('preferred_plan')}；仓位参考: {row.get('risk_budget_initial_position_pct')}%-{row.get('risk_budget_max_position_pct')}%", "",
        ])
    return "\n".join(lines) + "\n"


def _merge_exact_exit_histories(
    qfq_histories: Mapping[str, pd.DataFrame],
    extended_exit_histories: Mapping[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Prefer every successfully validated exact raw/qfq history.

    Row count is not an integrity signal: a recently listed stock commonly has
    equal-length normal and extended histories. The extended fetcher only
    returns frames that passed its as-of, mapping, and cache-integrity checks,
    so any non-empty returned frame is the authoritative price basis.
    """

    merged = dict(qfq_histories)
    merged.update({
        code: history for code, history in extended_exit_histories.items()
        if history is not None and not history.empty
    })
    return merged


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
    market_data_errors: dict[str, str] = {}
    index_histories: dict[str, pd.DataFrame] = {}
    for index_name, record in MARKET_INDEX_RECORDS.items():
        try:
            frame = fetch_tencent_history(record, as_of=config.as_of, adjusted=False)
            if frame.empty:
                raise RuntimeError("empty_index_history")
            index_histories[index_name] = frame
        except Exception as exc:
            market_data_errors[f"index:{index_name}"] = f"{type(exc).__name__}: {exc}"
    external_context_date = config.external_context_date or config.as_of
    external_histories: dict[str, pd.DataFrame] = {}
    for market_name, (symbol, lag_days) in EXTERNAL_MARKET_SYMBOLS.items():
        cutoff = external_context_date - timedelta(days=lag_days)
        try:
            frame = fetch_tencent_symbol_history(symbol, as_of=cutoff)
            if frame.empty:
                raise RuntimeError("empty_external_history")
            external_histories[market_name] = frame
        except Exception as exc:
            market_data_errors[f"external:{market_name}"] = f"{type(exc).__name__}: {exc}"
    market_regime = build_market_regime(
        quant_rows,
        index_histories=index_histories,
        external_histories=external_histories,
        as_of=config.as_of,
        external_as_of=external_context_date,
    )
    industry_regimes = build_industry_regimes(quant_rows)
    previous_state_file = config.state_dir / "last_all_a_state.json"
    state_file_existed = previous_state_file.exists()
    state_integrity_error = ""
    try:
        previous_watchlist = _load_previous_watchlist_state(previous_state_file)
        state_continuity_status = "VALID" if state_file_existed else "MISSING_INITIALIZED_SAFE"
    except RuntimeError as exc:
        state_continuity_status = "CORRUPT_REINITIALIZED_SAFE"
        state_integrity_error = str(exc)
        previous_watchlist = {}
        corrupt_backup = previous_state_file.with_name(
            f"{previous_state_file.stem}.corrupt.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{previous_state_file.suffix}",
        )
        previous_state_file.replace(corrupt_backup)
    state_continuity_safe = state_continuity_status == "VALID"
    active_review_codes = {
        _normalize_code(code)
        for code, state in previous_watchlist.items()
        if str(state.get("signal_lifecycle_state") or "")
        in ACTIVE_SIGNAL_LIFECYCLES | {"ENTRY_PENDING"}
    }
    quant_by_code = {_normalize_code(row.get("code")): row for row in quant_rows}
    active_review_rows = [
        dict(quant_by_code[code]) for code in sorted(active_review_codes)
        if code in quant_by_code
    ]
    active_review_missing_codes = sorted(active_review_codes - set(quant_by_code))
    top80 = _research_queue(quant_rows, limit=config.evidence_queue_size)
    top80_codes = {_normalize_code(row.get("code")) for row in top80}
    existing_profiles, _existing_profile_distribution = _exit_profiles(
        Path(exit_profile_file),
    )
    prior_validated_profile_codes: set[str] = set()
    for code, profile in existing_profiles.items():
        enriched_profile = enrich_exit_profile(profile, as_of=config.as_of)
        if (
            str(profile.get("exit_profile_status") or "") == "PASSED"
            and bool(enriched_profile.get("exit_profile_rule_version_match"))
            and bool(enriched_profile.get("exit_profile_freshness_passed"))
            and bool(enriched_profile.get("exit_profile_data_traceable"))
            and bool(enriched_profile.get("exit_profile_validation_scope_valid"))
        ):
            prior_validated_profile_codes.add(code)
    exploration_rows = select_exit_profile_exploration_rows(
        quant_rows,
        exclude_codes=top80_codes | active_review_codes,
        as_of=config.as_of,
        prior_validated_codes=prior_validated_profile_codes,
    )
    analysis_candidates = [
        *top80,
        *(row for row in active_review_rows if _normalize_code(row.get("code")) not in top80_codes),
        *exploration_rows,
    ]
    exit_validation_references = select_exit_validation_reference_rows(
        quant_rows,
        # The partition is fixed. Per-candidate independence is enforced by
        # target-code leave-one-out inside the profile validator.
        exclude_codes=(),
    )
    analysis_candidate_codes = {
        _normalize_code(row.get("code")) for row in analysis_candidates
    }
    history_request_rows = [
        *analysis_candidates,
        *(
            row for row in exit_validation_references
            if _normalize_code(row.get("code")) not in analysis_candidate_codes
        ),
    ]
    extended_exit_histories, exit_history_fetch = fetch_extended_adjusted_histories(
        candidates=history_request_rows,
        as_of=config.as_of,
        cache_dir=config.cache_dir / "exit_profile_qfq",
    )
    exit_history_fetch["candidate_requested_count"] = len(analysis_candidates)
    exit_history_fetch["normal_candidate_requested_count"] = len(top80)
    exit_history_fetch["active_review_requested_count"] = len(active_review_rows)
    exit_history_fetch["exploration_candidate_requested_count"] = len(exploration_rows)
    exit_history_fetch["validation_reference_requested_count"] = len(exit_validation_references)
    exit_history_fetch["unique_history_request_count"] = len(history_request_rows)
    extended_history_codes = set(extended_exit_histories)
    candidate_history_success_count = sum(
        _normalize_code(row.get("code")) in extended_history_codes
        for row in analysis_candidates
    )
    reference_history_success_count = sum(
        _normalize_code(row.get("code")) in extended_history_codes
        for row in exit_validation_references
    )
    candidate_history_coverage_ratio = (
        candidate_history_success_count / len(analysis_candidates)
        if analysis_candidates else 0.0
    )
    reference_history_coverage_ratio = (
        reference_history_success_count / len(exit_validation_references)
        if exit_validation_references else 0.0
    )
    exit_history_data_quality = (
        "OK"
        if candidate_history_coverage_ratio >= MIN_EXIT_HISTORY_COVERAGE_RATIO
        and reference_history_coverage_ratio >= MIN_EXIT_HISTORY_COVERAGE_RATIO
        else "DEGRADED"
    )
    exit_history_fetch.update({
        "candidate_success_count": candidate_history_success_count,
        "candidate_coverage_ratio": round(candidate_history_coverage_ratio, 6),
        "validation_reference_success_count": reference_history_success_count,
        "validation_reference_coverage_ratio": round(reference_history_coverage_ratio, 6),
        "data_quality": exit_history_data_quality,
        "minimum_coverage_ratio": MIN_EXIT_HISTORY_COVERAGE_RATIO,
    })
    exit_histories = _merge_exact_exit_histories(
        qfq_histories, extended_exit_histories,
    )
    entry_plan_specs: dict[str, dict[str, Any]] = {}
    for candidate in analysis_candidates:
        code = _normalize_code(candidate.get("code"))
        board_rule = board_rules.get(str(candidate.get("board")))
        raw_history = raw_histories.get(code, pd.DataFrame())
        if board_rule is None or raw_history.empty:
            continue
        adjusted_history = exit_histories.get(code, pd.DataFrame())
        if adjusted_history.empty:
            continue
        current_plan = build_price_plan(
            candidate, raw_history, board_rule, [], adjusted_history=adjusted_history,
        )
        entry_plan_specs[code] = {
            # The mode is fixed from today's live price plan before either
            # historical mode's outcome is inspected, preventing cherry-pick.
            "entry_mode": current_plan.get("preferred_plan") or "pullback",
            "breakout_volume_ratio": board_rule.breakout_volume_ratio,
            "max_chase_atr_multiple": board_rule.max_chase_atr_multiple,
            "volatility_multiplier": board_rule.volatility_multiplier,
            "minimum_history_rows": board_rule.minimum_history_rows,
            "minimum_turnover": board_rule.minimum_turnover,
            "max_5d_return_pct": board_rule.max_5d_return_pct,
            "max_10d_return_pct": board_rule.max_10d_return_pct,
            "trigger_window_days": 10,
        }
    _add_exit_validation_reference_specs(
        entry_plan_specs, exit_validation_references, board_rules,
    )
    _exit_profile_path, exit_profile_refresh = refresh_exit_profiles_from_price_history(
        output_file=exit_profile_file,
        candidates=analysis_candidates,
        histories=exit_histories,
        as_of=config.as_of,
        entry_plan_specs=entry_plan_specs,
        validation_candidates=exit_validation_references,
    )
    refreshed_profiles, _refreshed_profile_distribution = _exit_profiles(Path(exit_profile_file))
    exit_profile_priority_codes = _current_passed_profile_codes(
        analysis_candidates, refreshed_profiles,
    )
    exit_profile_priority_code_set = set(exit_profile_priority_codes)
    inputs, fundamental_errors = _fundamentals(
        quant_rows, qfq_histories, config,
        priority_codes=[*exit_profile_priority_codes, *active_review_codes],
        required_codes=[*exit_profile_priority_codes, *active_review_codes],
    )
    deep_priority_queue_size = max(
        config.evidence_queue_size + len(active_review_codes),
        len(exit_profile_priority_code_set | active_review_codes),
    )
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
            "source_mode": "real_all_a_full_scan", "requested_stock_records": analysis_candidates,
            "industry_evidence_file": industry_evidence_file,
            "company_evidence_file": company_evidence_file,
            "exit_profile_file": exit_profile_file,
            "exit_profile_priority_codes": [*exit_profile_priority_codes, *sorted(active_review_codes)],
            "active_review_codes": sorted(active_review_codes),
            "no_auto_trade": True, "no_broker_integration": True,
        },
        priority_queue_size=deep_priority_queue_size,
        secondary_queue_size=config.evidence_queue_size,
        exit_profile_df=pd.read_csv(exit_profile_file, dtype={"code": str}) if Path(exit_profile_file).exists() else None,
        ledger_path=config.forward_ledger_file,
        run_mode="full",
        evidence_cache_dir=config.evidence_cache_dir,
        auto_evidence_limit=min(50, max(
            config.deep_review_size,
            len(active_review_codes) + 10,
            len(exit_profile_priority_codes) + len(active_review_codes),
        )),
        state_dir=config.state_dir / "deep_pipeline",
    )
    profiles, input_exit_distribution = _exit_profiles(Path(exit_profile_file))
    watchlist, deep_rows = _merge_deep_rows(
        quant_rows=quant_rows, deep_report=deep_report,
        adjusted_histories=exit_histories, raw_histories=raw_histories,
        price_audits=price_audits, board_rules=board_rules, exit_profiles=profiles,
        max_watchlist=config.max_watchlist, as_of=config.as_of,
        market_regime=market_regime, industry_regimes=industry_regimes,
    )
    watchlist_codes = {_normalize_code(row.get("code")) for row in watchlist}
    active_deep_rows = {
        _normalize_code(row.get("code")): row for row in deep_rows
        if _normalize_code(row.get("code")) in active_review_codes
    }
    for code in sorted(active_review_codes):
        if code not in watchlist_codes and code in active_deep_rows:
            watchlist.append(active_deep_rows[code])
            watchlist_codes.add(code)
    strict_rows = [row for row in watchlist if row.get("user_visible_level") == "STRICT_REVIEW_READY"]
    condition_rows = [row for row in watchlist if row.get("user_visible_level") == "CONDITION_WATCH"]
    research_rows = [row for row in watchlist if row.get("user_visible_level") == "RESEARCH_WATCH"]
    daily_signals = build_daily_signals(
        current_rows=watchlist, previous=previous_watchlist,
        as_of=config.as_of, next_trade_date=config.next_trade_date,
        current_market_rows=quant_rows,
        adjusted_histories=extended_exit_histories, raw_histories=raw_histories,
        state_continuity_safe=state_continuity_safe,
        buy_signal_data_safe=exit_history_data_quality == "OK",
    )
    signals_by_code = {_normalize_code(row.get("code")): row for row in daily_signals}
    for row in watchlist:
        signal = signals_by_code.get(_normalize_code(row.get("code")), {})
        row["signal_lifecycle_state"] = signal.get("current_lifecycle_state") or "NO_POSITION_SIGNAL"
    signal_state_rows = _build_signal_state_rows(
        current_rows=watchlist,
        previous=previous_watchlist,
        daily_signals=daily_signals,
        current_market_rows=quant_rows,
        as_of=config.as_of,
    )
    execution_codes = {
        code for code, signal in signals_by_code.items()
        if signal.get("signal_action") == "BUY_IF_TRIGGERED"
    }
    execution_strict_rows = [
        row for row in strict_rows if _normalize_code(row.get("code")) in execution_codes
    ]
    actionable_execution_list = build_actionable_execution_list(
        strict_rows=execution_strict_rows, next_trade_date=config.next_trade_date,
        daily_signals=daily_signals,
    )
    daily_candidate_top5 = build_daily_candidate_top5(
        deep_rows=deep_rows, daily_signals=daily_signals,
        fallback_rows=quant_rows, limit=5,
    )
    changes, evidence_changes = _changes(
        watchlist, previous_state_file, state_rows=signal_state_rows,
    )
    board_distribution = _distribution(universe_rows, "board")
    exchange_distribution = _distribution(universe_rows, "exchange")
    price_source_distribution = dict(Counter(
        str(audit.get("raw_source") or "unknown") for audit in price_audits.values()
    ))
    adjustment_source_distribution = dict(Counter(
        str(audit.get("qfq_source") or "unknown") for audit in price_audits.values()
    ))
    matched_exit_distribution = dict(Counter(str(row.get("exit_profile_status") or "NOT_AVAILABLE") for row in deep_rows))
    strict_gate_names = list(json.loads(deep_rows[0].get("strict_gate_checks") or "{}").keys()) if deep_rows else []
    strict_gate_audit = []
    for row in deep_rows:
        checks = json.loads(row.get("strict_gate_checks") or "{}")
        strict_gate_audit.append({
            "code": row.get("code"),
            "stock_name": row.get("stock_name"),
            "user_visible_level": row.get("user_visible_level"),
            **checks,
            "passed_gate_count": sum(bool(value) for value in checks.values()),
            "failed_gate_count": sum(not bool(value) for value in checks.values()),
            "failed_gates": ";".join(name for name, passed in checks.items() if not passed),
        })
    strict_gate_failure_counts = {
        name: sum(not bool(row.get(name)) for row in strict_gate_audit) for name in strict_gate_names
    }
    exit_profile_strategy_health = _exit_profile_strategy_health(exit_profile_refresh)
    summary = {
        "as_of_date": config.as_of.isoformat(), "next_trade_date": config.next_trade_date.isoformat(),
        "raw_security_count": len(universe_rows), "official_universe_count": len(universe_rows),
        "valid_stock_count": filter_counts["effective_scan_count"],
        "fatal_data_failure_count": filter_counts["fatal_data_failure_count"],
        "recoverable_price_failure_count": filter_counts["recoverable_price_failure_count"],
        "price_data_coverage_ratio": filter_counts["price_data_coverage_ratio"],
        "skipped_stock_count": len(universe_rows) - filter_counts["effective_scan_count"],
        "exchange_distribution": exchange_distribution, "board_distribution": board_distribution,
        "price_source_distribution": price_source_distribution,
        "adjustment_source_distribution": adjustment_source_distribution,
        "effective_scan_count": len(quant_rows),
        "priority_research_count": sum(row.get("quant_status") == "PRIORITY_RESEARCH" for row in quant_rows),
        "secondary_research_count": sum(row.get("quant_status") == "SECONDARY_RESEARCH" for row in quant_rows),
        "evidence_queue_count": len(top80),
        "analysis_candidate_count_including_active_review": len(analysis_candidates),
        "active_signal_review_count": len(active_review_codes),
        "active_signal_review_refreshed_count": len(active_review_rows),
        "active_signal_review_missing_codes": active_review_missing_codes,
        "exit_profile_exploration_count": len(exploration_rows),
        "exit_profile_exploration_prior_validated_count": sum(
            row.get("exit_profile_exploration_reason")
            == "PRIOR_VALIDATED_PROFILE_REFRESH"
            for row in exploration_rows
        ),
        "exit_profile_exploration_industry_count": len({
            str(row.get("industry") or "UNRESOLVED") for row in exploration_rows
        }),
        "exit_profile_exploration_rotation_bucket": (
            exploration_rows[0].get("exit_profile_exploration_rotation_bucket")
            if exploration_rows else ""
        ),
        "exit_profile_exploration_selection_version": (
            EXIT_PROFILE_EXPLORATION_SELECTION_VERSION
        ),
        "signal_state_continuity_status": state_continuity_status,
        "signal_state_integrity_error": state_integrity_error,
        "exit_profile_validation_reference_count": len(exit_validation_references),
        "exit_profile_validation_reference_board_distribution": _distribution(
            exit_validation_references, "board"
        ),
        "exit_profile_validation_reference_selection_version": EXIT_VALIDATION_REFERENCE_SELECTION_VERSION,
        "deep_review_count": len(deep_rows),
        "strict_review_ready_count": len(strict_rows), "condition_watch_count": len(condition_rows),
        "research_watch_count": len(research_rows),
        "actionable_execution_count": len(actionable_execution_list),
        "execution_suppressed_count": len(strict_rows) - len(actionable_execution_list),
        "market_regime_status": market_regime.get("status"),
        "market_regime_score": market_regime.get("score"),
        "market_regime_risk_reasons": market_regime.get("risk_reasons"),
        "market_position_multiplier": market_regime.get("position_multiplier"),
        "external_risk_level": market_regime.get("external_risk_level"),
        "external_context_date": market_regime.get("external_context_date"),
        "external_market_available_count": market_regime.get("external_available_count"),
        "external_market_data_quality": market_regime.get("external_data_quality"),
        "market_signal_data_quality": market_regime.get("data_quality"),
        "industry_regime_count": len(industry_regimes),
        "industry_regime_data_quality": "OK" if industry_regimes else "PARTIAL",
        "event_scan_ok_count": sum(row.get("event_scan_status") == "OK" for row in deep_rows),
        "real_world_gate_pass_count": sum(bool(row.get("real_world_gate_passed")) for row in deep_rows),
        "market_data_warning_count": len(market_data_errors),
        "daily_candidate_top5_count": len(daily_candidate_top5),
        "buy_signal_count": sum(row.get("signal_action") == "BUY_IF_TRIGGERED" for row in daily_signals),
        "hold_signal_count": sum(row.get("signal_action") == "HOLD_REVIEW" for row in daily_signals),
        "sell_signal_count": sum(row.get("signal_action") == "SELL_EXIT" for row in daily_signals),
        "cancel_buy_review_count": sum(row.get("signal_action") == "CANCEL_BUY_REVIEW" for row in daily_signals),
        "watch_signal_count": sum(row.get("signal_action") == "WATCH_ONLY" for row in daily_signals),
        "industry_evidence_coverage": _coverage(deep_rows, lambda row: row.get("industry_evidence_status") in {"VERIFIED", "PARTIALLY_VERIFIED"}),
        "company_evidence_coverage": _coverage(deep_rows, lambda row: row.get("company_evidence_status") in {"VERIFIED", "PARTIALLY_VERIFIED"}),
        "exit_profile_coverage": _coverage(deep_rows, lambda row: row.get("exit_profile_status") in {"PASSED", "DEGRADED", "FAILED"}),
        "financial_coverage": _coverage(deep_rows, lambda row: _status(row.get("financial_safety_score")) != "UNKNOWN"),
        "valuation_coverage": _coverage(deep_rows, lambda row: _status(row.get("valuation_score")) != "UNKNOWN"),
        "input_exit_profile_distribution": input_exit_distribution,
        "matched_candidate_exit_profile_distribution": matched_exit_distribution,
        "exit_profile_refresh": exit_profile_refresh,
        "exit_profile_strategy_health": exit_profile_strategy_health,
        "exit_profile_history_fetch": exit_history_fetch,
        "exit_profile_history_data_quality": exit_history_data_quality,
        "exit_profile_candidate_history_coverage_ratio": round(
            candidate_history_coverage_ratio, 6,
        ),
        "exit_profile_reference_history_coverage_ratio": round(
            reference_history_coverage_ratio, 6,
        ),
        "strict_gate_feasibility": {
            "audited_candidate_count": len(strict_gate_audit),
            "all_gates_passed_count": sum(row.get("failed_gate_count") == 0 for row in strict_gate_audit),
            "failure_counts_by_gate": strict_gate_failure_counts,
            "note": "Each gate is reported independently; the workflow never relaxes a failed gate to force a buy list.",
        },
        "universe_source_audit": source_audit, "industry_enriched_count": industry_enriched_count,
        "industry_enrichment_diagnostics": industry_diagnostics,
        "price_mapping_status_distribution": dict(Counter(str(row.get("price_mapping_status") or "UNKNOWN") for row in price_audits.values())),
        "corporate_action_detected_count": sum(bool(row.get("corporate_action_detected")) for row in price_audits.values()),
        "fundamental_fetch_warning_count": len(fundamental_errors),
        "exit_profile_priority_candidate_count": len(exit_profile_priority_codes),
        "exit_profile_priority_codes": exit_profile_priority_codes,
        "deep_priority_queue_size": deep_priority_queue_size,
        "exit_profile_priority_deep_reviewed_count": sum(
            _normalize_code(row.get("code")) in exit_profile_priority_code_set
            for row in deep_rows
        ),
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
    (config.output_dir / "market_regime.json").write_text(
        json.dumps(market_regime, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    _write_csv(
        config.output_dir / "industry_regimes.csv",
        industry_regimes.values(),
        INDUSTRY_REGIME_COLUMNS,
    )
    _write_csv(config.output_dir / "real_world_signal_audit.csv", deep_rows)
    _write_csv(config.output_dir / "top80_evidence_queue.csv", top80)
    _write_csv(config.output_dir / "active_signal_review_queue.csv", active_review_rows)
    _write_csv(
        config.output_dir / "exit_profile_exploration_queue.csv",
        exploration_rows,
    )
    _write_csv(config.output_dir / "exit_profile_validation_reference.csv", exit_validation_references)
    _write_csv(config.output_dir / "top30_deep_review.csv", deep_rows[: config.deep_review_size])
    _write_csv(config.output_dir / "strict_gate_audit.csv", strict_gate_audit)
    _write_csv(config.output_dir / "strict_review_ready.csv", strict_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "condition_watch.csv", condition_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "research_watch.csv", research_rows, PLAN_COLUMNS)
    _write_csv(config.output_dir / "tomorrow_watchlist.csv", watchlist, PLAN_COLUMNS)
    _write_csv(config.output_dir / "daily_candidate_top5.csv", daily_candidate_top5, TOP5_COLUMNS)
    (config.output_dir / "daily_candidate_top5.md").write_text(
        _candidate_top5_markdown(summary, daily_candidate_top5), encoding="utf-8",
    )
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
    _write_csv(
        config.output_dir / "actionable_execution_list.csv",
        actionable_execution_list,
        EXECUTION_LIST_COLUMNS,
    )
    (config.output_dir / "actionable_execution_list.json").write_text(
        json.dumps(
            {"valid_for_trade_date": config.next_trade_date.isoformat(), "stocks": actionable_execution_list},
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )
    (config.output_dir / "actionable_execution_list.md").write_text(
        _execution_list_markdown(summary, actionable_execution_list), encoding="utf-8",
    )
    (config.output_dir / "daily_signals.json").write_text(
        json.dumps({"summary": summary, "signals": daily_signals}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (config.output_dir / "daily_signals.md").write_text(
        _daily_signals_markdown(summary, daily_signals, daily_candidate_top5), encoding="utf-8",
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
    ] + [
        {"stage": "market_signal", "code": "", "status": "WARNING", "issue": key, "detail": value}
        for key, value in market_data_errors.items()
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
        external_context_date = as_of
    else:
        as_of, next_trade_date = resolve_scan_dates()
        external_context_date = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if next_trade_date <= as_of:
        raise SystemExit("--next-trade-date must be later than --as-of-date")
    output_dir = Path(args.output_dir or f"reports/all_a_full_scan/{next_trade_date:%Y%m%d}")
    stock_pool_output = Path(args.stock_pool_output or f"stock_pools/all_a_universe_{as_of:%Y%m%d}.csv")
    config = AllAScanConfig(
        as_of=as_of, next_trade_date=next_trade_date, output_dir=output_dir,
        stock_pool_output=stock_pool_output, external_context_date=external_context_date,
        board_rules_file=Path(args.board_rules),
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
