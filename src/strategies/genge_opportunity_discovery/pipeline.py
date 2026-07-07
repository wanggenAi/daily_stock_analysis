"""Daily opportunity discovery pipeline for GenGe Cycle Bottom research.

This module turns the existing GenGe feature engine into a daily research
workflow. It does not place orders, connect to broker accounts, or promise
returns. Every output row is a research object for manual review.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import time
from collections import Counter
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import (
    IndustryAliasResolver,
    _normalize_exit_profile_status,
)
from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame
from src.strategies.genge_cycle_bottom.industry_evidence import CONFIDENCE_RANK, QUALITY_RANK
from src.strategies.genge_cycle_bottom.strategy import GenGeCycleBottomStrategy

from .industry_templates import DEFAULT_PUBLIC_SOURCES, expected_industries, indicator_templates_for


RULE_VERSION = "genge_opportunity_discovery_v1"
DISCOVERY_DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入建议，不应自动交易。"
TREND_RANK = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}
HARD_LOGIC_RANK = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}
EVIDENCE_STATUS_RANK = {
    "MISSING": 0,
    "PARSE_FAILED": 0,
    "LEAD_ONLY": 1,
    "STALE": 1,
    "CONFLICTING": 1,
    "PARTIALLY_VERIFIED": 2,
    "VERIFIED": 3,
}
RESEARCH_STATUSES = {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"}
TIER_ORDER = {"TIER_A": 3, "TIER_B": 2, "TIER_C": 1, "REJECTED": 0, "DATA_INSUFFICIENT": -1}

QUANT_COLUMNS = [
    "code",
    "stock_name",
    "raw_industry",
    "normalized_industry",
    "as_of_date",
    "latest_price_date",
    "close",
    "quant_score",
    "quant_screen_status",
    "quant_reason",
    "price_position_score",
    "price_percentile_5y",
    "distance_from_5y_low_pct",
    "trend_confirmation_level",
    "trend_stabilization_score",
    "relative_strength_20d",
    "relative_strength_60d",
    "valuation_score",
    "financial_safety_score",
    "execution_risk_score",
    "execution_risk_quality",
    "value_trap_score",
    "hard_reject_blockers",
    "soft_blockers",
    "next_evidence_needed",
    "missing_fields",
    "risk_flags",
    "disclaimer",
]

OPPORTUNITY_COLUMNS = [
    "code",
    "stock_name",
    "raw_industry",
    "normalized_industry",
    "as_of_date",
    "latest_price_date",
    "close",
    "tier",
    "research_label",
    "quant_score",
    "opportunity_quality_score",
    "opportunity_quality_rank",
    "opportunity_proximity_rank",
    "a_condition_pass_count",
    "a_condition_fail_count",
    "a_condition_failed",
    "hard_blockers",
    "soft_blockers",
    "opportunity_logic",
    "top_risks",
    "upgrade_conditions",
    "downgrade_conditions",
    "improvement_flags",
    "deterioration_flags",
    "price_percentile_5y",
    "distance_from_5y_low_pct",
    "trend_confirmation_level",
    "industry_cycle_phase",
    "industry_evidence_status",
    "industry_evidence_score",
    "industry_evidence_confidence",
    "industry_evidence_quality",
    "company_evidence_status",
    "company_evidence_score",
    "company_evidence_confidence",
    "hard_logic_level",
    "balanced_exit_historical_profile",
    "next_review_trigger",
    "evidence_items",
    "missing_evidence",
    "disclaimer",
]

GAP_COLUMNS = [
    "scope",
    "industry",
    "code",
    "stock_name",
    "indicator",
    "required_or_optional",
    "evidence_status",
    "gap_type",
    "freshness_limit_days",
    "oldest_accepted_evidence_date",
    "recommended_public_sources",
    "template_status",
    "note",
]

DATA_QUALITY_COLUMNS = [
    "code",
    "stock_name",
    "stage",
    "status",
    "issue",
    "detail",
]

EVIDENCE_INVENTORY_COLUMNS = [
    "scope",
    "evidence_date",
    "collected_at",
    "industry",
    "code",
    "stock_name",
    "indicator",
    "value",
    "unit",
    "comparison_period",
    "direction",
    "source",
    "source_domain",
    "source_type",
    "confidence",
    "freshness_days",
    "raw_excerpt",
    "normalized_summary",
    "parser",
    "parse_status",
    "evidence_status",
    "warning_flags",
]

CHANGE_COLUMNS = [
    "code",
    "stock_name",
    "normalized_industry",
    "previous_tier",
    "current_tier",
    "previous_quant_score",
    "current_quant_score",
    "change_type",
    "detail",
]

EVIDENCE_CHANGE_COLUMNS = [
    "code",
    "stock_name",
    "normalized_industry",
    "previous_industry_evidence_status",
    "current_industry_evidence_status",
    "previous_company_evidence_status",
    "current_company_evidence_status",
    "change_type",
]

LEDGER_COLUMNS = [
    "code",
    "stock_name",
    "industry",
    "first_observation_date",
    "first_tier",
    "first_close",
    "first_quant_score",
    "first_evidence_status",
    "rule_version",
    "data_version",
    "first_snapshot_json",
    "latest_observation_date",
    "latest_tier",
    "latest_close",
    "return_5d_pct",
    "return_10d_pct",
    "return_20d_pct",
    "return_40d_pct",
    "return_60d_pct",
    "max_up_pct",
    "max_down_pct",
    "benchmark_return_20d_pct",
    "status",
]


def _finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 4) -> Optional[float]:
    number = _finite_float(value)
    if number is None:
        return None
    return round(number, digits)


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [token for token in str(value).split(";") if token]


def _json_items(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return []
    if isinstance(parsed, list):
        return [dict(item) for item in parsed if isinstance(item, Mapping)]
    return []


def _date_column(df: pd.DataFrame) -> Optional[str]:
    for column in ("date", "trade_date", "disclosure_date", "publish_date", "ann_date", "announcement_date", "report_date"):
        if column in df.columns:
            return column
    return None


def _source_domain(source: Any) -> str:
    text = str(source or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "")
    return parsed.netloc.lower()


def _evidence_date_value(row: Mapping[str, Any]) -> Optional[date]:
    for column in ("evidence_date", "date", "publish_date", "disclosure_date", "ann_date", "announcement_date", "report_date"):
        if column in row and row.get(column) not in (None, ""):
            parsed = pd.to_datetime(row.get(column), errors="coerce")
            if not pd.isna(parsed):
                return parsed.date()
    return None


def _inventory_confidence(source_type: str, value: Any) -> str:
    source_kind = str(source_type or "").upper()
    has_number = any(char.isdigit() for char in str(value or ""))
    if source_kind in {"OFFICIAL_REPORT", "COMPANY_ANNOUNCEMENT", "EXCHANGE_DISCLOSURE"} and has_number:
        return "MEDIUM"
    if source_kind in {"OFFICIAL_REPORT", "COMPANY_ANNOUNCEMENT", "EXCHANGE_DISCLOSURE", "RESEARCH_REPORT_SUMMARY"}:
        return "LOW" if not has_number else "MEDIUM"
    return "LOW"


def _inventory_status(
    *,
    evidence_date: Optional[date],
    as_of: date,
    source: Any,
    indicator: Any,
    value: Any,
    source_type: str,
    warning_flags: List[str],
) -> str:
    if evidence_date is None or not str(source or "").strip() or not str(indicator or "").strip():
        warning_flags.append("missing_required_field")
        return "PARSE_FAILED"
    if evidence_date > as_of:
        warning_flags.append("future_dated_evidence_excluded")
        return "PARSE_FAILED"
    freshness_days = (as_of - evidence_date).days
    if freshness_days > 180:
        warning_flags.append("stale_evidence")
        return "STALE"
    source_kind = str(source_type or "").upper()
    has_number = any(char.isdigit() for char in str(value or ""))
    if source_kind == "NEWS_SUMMARY" or not has_number:
        warning_flags.append("lead_only_needs_manual_review")
        return "LEAD_ONLY"
    if source_kind in {"OFFICIAL_REPORT", "COMPANY_ANNOUNCEMENT", "EXCHANGE_DISCLOSURE"}:
        return "VERIFIED"
    return "PARTIALLY_VERIFIED"


def _build_evidence_inventory(
    *,
    industry_evidence_df: Optional[pd.DataFrame],
    company_evidence_df: Optional[pd.DataFrame],
    as_of: date,
) -> List[Dict[str, Any]]:
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: List[Dict[str, Any]] = []
    sources = [
        ("industry", industry_evidence_df),
        ("company", company_evidence_df),
    ]
    for scope, df in sources:
        if df is None or df.empty:
            continue
        for _, raw_row in df.iterrows():
            raw = raw_row.to_dict()
            evidence_date = _evidence_date_value(raw)
            indicator = raw.get("indicator") or raw.get("evidence_name") or ""
            value = raw.get("value") or raw.get("evidence_value") or ""
            source = raw.get("source") or ""
            source_type = str(raw.get("source_type") or raw.get("evidence_source_type") or "user_supplied").upper()
            direction = str(raw.get("direction") or raw.get("evidence_direction") or "").upper()
            warning_flags = _as_list(raw.get("warning_flags"))
            status = _inventory_status(
                evidence_date=evidence_date,
                as_of=as_of,
                source=source,
                indicator=indicator,
                value=value,
                source_type=source_type,
                warning_flags=warning_flags,
            )
            freshness = (as_of - evidence_date).days if evidence_date is not None else ""
            rows.append(
                {
                    "scope": scope,
                    "evidence_date": evidence_date.isoformat() if evidence_date else "",
                    "collected_at": collected_at,
                    "industry": raw.get("industry") or "",
                    "code": _normalize_code(raw.get("code")) if raw.get("code") not in (None, "") else "",
                    "stock_name": raw.get("stock_name") or "",
                    "indicator": indicator,
                    "value": value,
                    "unit": raw.get("unit") or "",
                    "comparison_period": raw.get("comparison_period") or "",
                    "direction": direction,
                    "source": source,
                    "source_domain": raw.get("source_domain") or _source_domain(source),
                    "source_type": source_type,
                    "confidence": str(raw.get("confidence") or _inventory_confidence(source_type, value)).upper(),
                    "freshness_days": freshness,
                    "raw_excerpt": raw.get("raw_excerpt") or raw.get("evidence_value") or value,
                    "normalized_summary": raw.get("normalized_summary") or value,
                    "parser": raw.get("parser") or "user_supplied_csv_normalizer",
                    "parse_status": (
                        "OK"
                        if status in {"VERIFIED", "PARTIALLY_VERIFIED"}
                        else "NEEDS_MANUAL_REVIEW"
                    ),
                    "evidence_status": status,
                    "warning_flags": ";".join(dict.fromkeys(warning_flags)),
                }
            )

    by_key: Dict[Tuple[str, str, str, str], set[str]] = {}
    for row in rows:
        if row.get("evidence_status") == "PARSE_FAILED":
            continue
        key = (
            str(row.get("scope") or ""),
            str(row.get("industry") or ""),
            str(row.get("code") or ""),
            str(row.get("indicator") or ""),
        )
        by_key.setdefault(key, set()).add(str(row.get("direction") or "").upper())
    for row in rows:
        key = (
            str(row.get("scope") or ""),
            str(row.get("industry") or ""),
            str(row.get("code") or ""),
            str(row.get("indicator") or ""),
        )
        directions = by_key.get(key, set())
        if "POSITIVE" in directions and "NEGATIVE" in directions and row.get("evidence_status") != "PARSE_FAILED":
            flags = _as_list(row.get("warning_flags"))
            flags.append("conflicting_evidence")
            row["warning_flags"] = ";".join(dict.fromkeys(flags))
            row["evidence_status"] = "CONFLICTING"
            row["parse_status"] = "NEEDS_MANUAL_REVIEW"
    return rows


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in dict(row).items()})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _json_dump(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _latest_price(history: pd.DataFrame) -> Tuple[Optional[date], Optional[float]]:
    if history.empty:
        return None, None
    last = history.iloc[-1]
    return coerce_date(last["date"]), _finite_float(last.get("close"))


def _return_from_tail(history: pd.DataFrame, days: int) -> Optional[float]:
    if history.empty or len(history) <= days:
        return None
    current = _finite_float(history.iloc[-1].get("close"))
    previous = _finite_float(history.iloc[-days - 1].get("close"))
    if current is None or previous is None or previous <= 0:
        return None
    return (current / previous - 1.0) * 100.0


def _relative_strength(history: pd.DataFrame, benchmark: Optional[pd.DataFrame], days: int) -> Optional[float]:
    stock_return = _return_from_tail(history, days)
    if stock_return is None or benchmark is None or benchmark.empty:
        return None
    benchmark_return = _return_from_tail(benchmark, days)
    if benchmark_return is None:
        return None
    return round(stock_return - benchmark_return, 4)


def _status_from_score(value: Any) -> str:
    score = _finite_float(value)
    if score is None:
        return "NOT_AVAILABLE"
    if score >= 60:
        return "PASSED"
    if score >= 40:
        return "DEGRADED"
    return "FAILED"


def _quant_reason(row: Mapping[str, Any], hard: List[str], soft: List[str]) -> str:
    if hard:
        return "量化层硬拒绝：" + ";".join(hard)
    parts = []
    price = _finite_float(row.get("price_percentile_5y"))
    if price is not None:
        parts.append(f"5年价格分位 {round(price, 4)}")
    trend = str(row.get("trend_confirmation_level") or "NONE")
    parts.append(f"趋势确认 {trend}")
    valuation = _status_from_score(row.get("valuation_score"))
    financial = _status_from_score(row.get("financial_safety_score"))
    parts.append(f"估值 {valuation}")
    parts.append(f"财务 {financial}")
    if soft:
        parts.append("待确认：" + ";".join(soft[:3]))
    return "；".join(parts)


def _next_evidence_needed(row: Mapping[str, Any]) -> str:
    needs = []
    if _evidence_status(row, "industry") in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        needs.append("industry_cycle_evidence")
    if _evidence_status(row, "company") in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        needs.append("company_cycle_evidence")
    if _status_from_score(row.get("financial_safety_score")) != "PASSED":
        needs.append("financial_safety_review")
    if _status_from_score(row.get("valuation_score")) == "FAILED":
        needs.append("valuation_review")
    if TREND_RANK.get(str(row.get("trend_confirmation_level") or "NONE"), 0) < TREND_RANK["MEDIUM"]:
        needs.append("trend_confirmation")
    return ";".join(dict.fromkeys(needs))


def _top_risks(row: Mapping[str, Any], hard: List[str], soft: List[str]) -> str:
    risks = list(hard) + list(soft)
    risks.extend(_as_list(row.get("risk_flags")))
    if _status_from_score(row.get("financial_safety_score")) != "PASSED":
        risks.append("financial_safety_not_passed")
    if _status_from_score(row.get("valuation_score")) == "FAILED":
        risks.append("valuation_failed")
    if not risks:
        risks.append("no_major_risk_detected_by_public_data")
    return ";".join(list(dict.fromkeys(risks))[:3])


def _opportunity_logic(row: Mapping[str, Any], tier: str) -> str:
    price = _finite_float(row.get("price_percentile_5y"))
    trend = str(row.get("trend_confirmation_level") or "NONE")
    hard_logic = str(row.get("hard_logic_level") or "NONE")
    industry = str(row.get("industry_evidence_status") or "MISSING")
    company = str(row.get("company_evidence_status") or "MISSING")
    price_text = "价格位置未知" if price is None else f"5年价格分位约 {round(price, 4)}"
    return (
        f"{tier}：{price_text}，趋势 {trend}，硬逻辑 {hard_logic}，"
        f"行业证据 {industry}，公司证据 {company}。仅作为人工复核研究对象。"
    )


def _upgrade_conditions(failed: List[str], industry_status: str, company_status: str) -> str:
    conditions = []
    if "trend_medium" in failed or "no_falling_knife" in failed:
        conditions.append("趋势企稳达到 MEDIUM 且不再持续创新低")
    if industry_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        conditions.append("补齐非过期且无冲突的行业证据")
    if company_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        conditions.append("补齐公司公告/财报/经营层面的可核验证据")
    if "exit_profile_passed" in failed:
        conditions.append("历史退出画像达到 PASSED")
    if "hard_logic_medium" in failed:
        conditions.append("hard_logic_level 升至 MEDIUM 及以上")
    return "；".join(conditions) if conditions else "保持证据有效且风险不恶化，等待人工复核。"


def _downgrade_conditions(row: Mapping[str, Any]) -> str:
    return "；".join(
        [
            "行业或公司证据出现冲突/过期",
            "趋势重新转弱或跌破关键平台",
            "财务、估值陷阱或执行风险恶化",
        ]
    )


def _evidence_status(row: Mapping[str, Any], scope: str) -> str:
    if scope == "industry":
        quality = str(row.get("industry_evidence_quality") or "MISSING").upper()
        confidence = str(row.get("industry_evidence_confidence") or "LOW").upper()
        source_type = str(row.get("industry_evidence_source_type") or "MISSING").upper()
        positive = int(_finite_float(row.get("industry_evidence_positive_count")) or 0)
        negative = int(_finite_float(row.get("industry_evidence_negative_count")) or 0)
        stale = int(_finite_float(row.get("industry_evidence_stale_count")) or 0)
        warnings = _as_list(row.get("industry_evidence_warning_flags"))
        items = _json_items(row.get("industry_evidence_items"))
    else:
        quality = str(row.get("company_evidence_quality") or row.get("company_evidence_source_type") or "MISSING").upper()
        confidence = str(row.get("company_evidence_confidence") or "LOW").upper()
        source_type = str(row.get("company_evidence_source_type") or "MISSING").upper()
        positive = int(_finite_float(row.get("company_evidence_positive_count")) or 0)
        negative = int(_finite_float(row.get("company_evidence_negative_count")) or 0)
        stale = int(_finite_float(row.get("company_evidence_stale_count")) or 0)
        warnings = _as_list(row.get("company_evidence_warning_flags"))
        items = _json_items(row.get("company_evidence_items"))

    if not items and (quality == "MISSING" or source_type == "MISSING"):
        return "MISSING"
    if any("parse" in flag.lower() for flag in warnings):
        return "PARSE_FAILED"
    if any("conflict" in flag.lower() for flag in warnings) or positive < negative:
        return "CONFLICTING"
    if stale > 0:
        return "STALE"
    if _lead_only_evidence(items, source_type):
        return "LEAD_ONLY"
    quality_rank = QUALITY_RANK.get(quality, QUALITY_RANK.get(source_type, 0))
    confidence_rank = CONFIDENCE_RANK.get(confidence, 0)
    if quality_rank >= 5 and confidence_rank >= CONFIDENCE_RANK["MEDIUM"] and positive >= max(1, negative):
        return "VERIFIED"
    if quality_rank >= 3 or confidence_rank >= CONFIDENCE_RANK["MEDIUM"] or positive > negative:
        return "PARTIALLY_VERIFIED"
    return "LEAD_ONLY"


def _lead_only_evidence(items: List[Dict[str, Any]], source_type: str) -> bool:
    if source_type in {"NEWS_SUMMARY", "MANUAL_TEMPLATE"}:
        return True
    if not items:
        return False
    for item in items:
        value = str(item.get("evidence_value") or "")
        source = str(item.get("source") or "")
        source_kind = str(item.get("source_type") or source_type).upper()
        has_number = any(char.isdigit() for char in value)
        if source_kind == "NEWS_SUMMARY" and not has_number:
            return True
        if ("http://" in source or "https://" in source) and not has_number:
            return True
    return False


def _exit_profile_by_code(exit_profile_df: Optional[pd.DataFrame]) -> Dict[str, str]:
    if exit_profile_df is None or exit_profile_df.empty or "code" not in exit_profile_df.columns:
        return {}
    result: Dict[str, str] = {}
    status_column = None
    for candidate in ("balanced_exit_historical_profile", "exit_profile_status", "status"):
        if candidate in exit_profile_df.columns:
            status_column = candidate
            break
    if not status_column:
        return result
    for _, row in exit_profile_df.iterrows():
        code = _normalize_code(row.get("code"))
        if code:
            result[code] = _normalize_exit_profile_status(row.get(status_column))
    return result


def _quant_score(row: Mapping[str, Any], rs20: Optional[float], rs60: Optional[float]) -> float:
    execution = 100.0 - min(100.0, max(0.0, _finite_float(row.get("execution_risk_score")) or 0.0))
    value_trap = 100.0 - min(100.0, max(0.0, _finite_float(row.get("value_trap_score")) or 0.0))
    relative = 50.0
    relative_inputs = [value for value in (rs20, rs60) if value is not None]
    if relative_inputs:
        relative = max(0.0, min(100.0, 50.0 + sum(relative_inputs) / len(relative_inputs) * 2.0))
    score = (
        (_finite_float(row.get("price_percentile_score")) or 0.0) * 0.26
        + (_finite_float(row.get("trend_stabilization_score")) or 0.0) * 0.22
        + (_finite_float(row.get("valuation_score")) or 0.0) * 0.14
        + (_finite_float(row.get("financial_safety_score")) or 0.0) * 0.16
        + execution * 0.10
        + value_trap * 0.08
        + relative * 0.04
    )
    return round(max(0.0, min(100.0, score)), 4)


def _screen_blockers(row: Mapping[str, Any]) -> Tuple[List[str], List[str]]:
    hard: List[str] = []
    soft: List[str] = []
    risk_flags = set(_as_list(row.get("risk_flags")))
    missing_fields = set(_as_list(row.get("missing_fields")))
    price_percentile = _finite_float(row.get("price_percentile_5y"))
    execution_score = _finite_float(row.get("execution_risk_score")) or 0.0
    value_trap_score = _finite_float(row.get("value_trap_score")) or 0.0

    if row.get("close") in (None, "") or "close" in missing_fields:
        hard.append("price_data_unavailable")
    if {"st_or_delisting_risk", "loss_making"} & risk_flags:
        hard.append("listed_company_hard_risk")
    if _status_from_score(row.get("financial_safety_score")) == "FAILED":
        hard.append("financial_safety_failed")
    if str(row.get("execution_risk_quality") or "") in {"risky", "unavailable"} or execution_score >= 60:
        hard.append("execution_risk_high")
    if value_trap_score >= 70 or str(row.get("value_trap_flag")) == "True":
        hard.append("value_trap_high")
    if price_percentile is not None and price_percentile > 0.75:
        hard.append("price_position_overheated")

    if price_percentile is None:
        soft.append("price_percentile_missing")
    elif price_percentile > 0.5:
        soft.append("price_not_low_enough")
    if not _bool(row.get("no_falling_knife_filter")):
        soft.append("falling_knife_not_cleared")
    if TREND_RANK.get(str(row.get("trend_confirmation_level") or "NONE"), 0) < TREND_RANK["WEAK"]:
        soft.append("trend_not_stabilized")
    if _status_from_score(row.get("valuation_score")) == "FAILED":
        soft.append("valuation_failed")
    return sorted(set(hard)), sorted(set(soft))


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _screen_status(row: Mapping[str, Any], hard: List[str], soft: List[str]) -> str:
    if hard:
        return "HARD_REJECT"
    score = _finite_float(row.get("quant_score")) or 0.0
    price_percentile = _finite_float(row.get("price_percentile_5y"))
    if score >= 58 and (price_percentile is None or price_percentile <= 0.5) and "falling_knife_not_cleared" not in soft:
        return "PRIORITY_RESEARCH"
    if score >= 45 or (price_percentile is not None and price_percentile <= 0.6):
        return "SECONDARY_RESEARCH"
    return "LOW_PRIORITY"


def _tier_row(row: Dict[str, Any]) -> Dict[str, Any]:
    hard: List[str] = []
    soft: List[str] = list(_as_list(row.get("soft_blockers")))
    failed: List[str] = []

    industry_status = _evidence_status(row, "industry")
    company_status = _evidence_status(row, "company")
    exit_profile = _normalize_exit_profile_status(row.get("balanced_exit_historical_profile"))
    price_percentile = _finite_float(row.get("price_percentile_5y"))
    trend_rank = TREND_RANK.get(str(row.get("trend_confirmation_level") or "NONE"), 0)
    hard_logic_rank = HARD_LOGIC_RANK.get(str(row.get("hard_logic_level") or "NONE"), 0)
    industry_rank = EVIDENCE_STATUS_RANK.get(industry_status, 0)
    company_rank = EVIDENCE_STATUS_RANK.get(company_status, 0)

    conditions = {
        "quant_research_queue": str(row.get("quant_screen_status")) in RESEARCH_STATUSES,
        "price_low_or_reasonable": price_percentile is not None and price_percentile <= 0.35,
        "no_falling_knife": _bool(row.get("no_falling_knife_filter")),
        "trend_medium": trend_rank >= TREND_RANK["MEDIUM"],
        "industry_evidence_medium": industry_rank >= EVIDENCE_STATUS_RANK["PARTIALLY_VERIFIED"],
        "company_evidence_medium": company_rank >= EVIDENCE_STATUS_RANK["PARTIALLY_VERIFIED"],
        "hard_logic_medium": hard_logic_rank >= HARD_LOGIC_RANK["MEDIUM"],
        "valuation_not_failed": _status_from_score(row.get("valuation_score")) != "FAILED",
        "financial_passed": _status_from_score(row.get("financial_safety_score")) == "PASSED",
        "execution_not_high": "execution_risk_high" not in _as_list(row.get("hard_reject_blockers")),
        "value_trap_not_high": "value_trap_high" not in _as_list(row.get("hard_reject_blockers")),
        "exit_profile_passed": exit_profile == "PASSED",
    }
    failed = [key for key, passed in conditions.items() if not passed]

    hard.extend(_as_list(row.get("hard_reject_blockers")))
    if exit_profile == "FAILED":
        hard.append("balanced_exit_profile_failed")
    elif exit_profile == "DEGRADED":
        soft.append("balanced_exit_profile_degraded")
    elif exit_profile == "NOT_AVAILABLE":
        soft.append("balanced_exit_profile_not_available")
    if industry_status in {"MISSING", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        soft.append(f"industry_evidence_{industry_status.lower()}")
    if company_status in {"MISSING", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        soft.append(f"company_evidence_{company_status.lower()}")

    if hard or str(row.get("quant_screen_status")) == "HARD_REJECT":
        tier = "REJECTED"
    elif all(conditions.values()):
        tier = "TIER_A"
    elif (
        str(row.get("quant_screen_status")) in RESEARCH_STATUSES
        and hard_logic_rank >= HARD_LOGIC_RANK["WEAK"]
        and trend_rank >= TREND_RANK["WEAK"]
        and industry_rank >= EVIDENCE_STATUS_RANK["LEAD_ONLY"]
        and exit_profile != "FAILED"
    ):
        tier = "TIER_B"
    elif str(row.get("quant_screen_status")) in RESEARCH_STATUSES and (
        industry_status == "MISSING" or company_status == "MISSING" or hard_logic_rank < HARD_LOGIC_RANK["WEAK"]
    ):
        tier = "TIER_C"
    elif str(row.get("quant_screen_status")) == "LOW_PRIORITY":
        tier = "REJECTED"
    else:
        tier = "DATA_INSUFFICIENT"

    evidence_score = (industry_rank + company_rank) / 6.0 * 100.0
    quality_score = round(
        (_finite_float(row.get("quant_score")) or 0.0) * 0.55
        + evidence_score * 0.25
        + trend_rank / 3.0 * 100.0 * 0.10
        + hard_logic_rank / 3.0 * 100.0 * 0.10,
        4,
    )
    missing_evidence = []
    if industry_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        missing_evidence.append(f"industry:{industry_status}")
    if company_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        missing_evidence.append(f"company:{company_status}")

    return {
        **row,
        "tier": tier,
        "research_label": _research_label(tier),
        "industry_evidence_status": industry_status,
        "company_evidence_status": company_status,
        "balanced_exit_historical_profile": exit_profile,
        "opportunity_quality_score": quality_score,
        "a_condition_pass_count": sum(1 for passed in conditions.values() if passed),
        "a_condition_fail_count": len(failed),
        "a_condition_failed": ";".join(failed),
        "hard_blockers": ";".join(sorted(set(hard))),
        "soft_blockers": ";".join(sorted(set(soft))),
        "opportunity_logic": _opportunity_logic(
            {
                **row,
                "industry_evidence_status": industry_status,
                "company_evidence_status": company_status,
            },
            tier,
        ),
        "top_risks": _top_risks(row, hard, soft),
        "upgrade_conditions": _upgrade_conditions(failed, industry_status, company_status),
        "downgrade_conditions": _downgrade_conditions(row),
        "improvement_flags": "",
        "deterioration_flags": "",
        "next_review_trigger": _next_review_trigger(failed, industry_status, company_status),
        "missing_evidence": ";".join(missing_evidence),
        "evidence_items": json.dumps(
            {
                "industry": _json_items(row.get("industry_evidence_items")),
                "company": _json_items(row.get("company_evidence_items")),
            },
            ensure_ascii=False,
        ),
        "disclaimer": DISCOVERY_DISCLAIMER,
    }


def _research_label(tier: str) -> str:
    return {
        "TIER_A": "严格研究候选，仍需人工复核",
        "TIER_B": "观察名单，等待证据或趋势确认",
        "TIER_C": "证据不完整研究对象",
        "REJECTED": "不符合当前研究标准",
        "DATA_INSUFFICIENT": "数据不足",
    }.get(tier, "研究对象")


def _next_review_trigger(failed: List[str], industry_status: str, company_status: str) -> str:
    if "exit_profile_passed" in failed:
        return "补充历史退出画像验证，未通过前不得进入 A 类。"
    if industry_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        return "补齐行业周期证据并检查是否过期或冲突。"
    if company_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
        return "补齐公司层面公告、经营和风险证据。"
    if "trend_medium" in failed or "no_falling_knife" in failed:
        return "等待趋势稳定确认，不追单。"
    return "盘前人工复核公开数据、风险和触发条件。"


def _rank_opportunities(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    quality_sorted = sorted(
        rows,
        key=lambda row: (
            TIER_ORDER.get(str(row.get("tier")), -1),
            _finite_float(row.get("opportunity_quality_score")) or 0.0,
            _finite_float(row.get("quant_score")) or 0.0,
        ),
        reverse=True,
    )
    for index, row in enumerate(quality_sorted, start=1):
        row["opportunity_quality_rank"] = index

    proximity_sorted = sorted(
        rows,
        key=lambda row: (
            int(_finite_float(row.get("a_condition_fail_count")) or 99),
            -TIER_ORDER.get(str(row.get("tier")), -1),
            -(_finite_float(row.get("quant_score")) or 0.0),
        ),
    )
    for index, row in enumerate(proximity_sorted, start=1):
        row["opportunity_proximity_rank"] = index
    return rows


def _latest_previous_report(output_dir: Path, current_dir: Path) -> Optional[Path]:
    if not output_dir.exists():
        return None
    reports = sorted(path for path in output_dir.glob("*/daily_opportunity_report.json") if path.parent != current_dir)
    return reports[-1] if reports else None


def _load_previous_state(output_dir: Path, current_dir: Path) -> Dict[str, Dict[str, Any]]:
    previous = _latest_previous_report(output_dir, current_dir)
    if previous is None:
        return {}
    try:
        payload = json.loads(previous.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("all_opportunities") or []
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping):
            result[_normalize_code(row.get("code"))] = dict(row)
    return result


def _changes(current_rows: List[Dict[str, Any]], previous: Mapping[str, Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    opportunity_rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    current_codes = {_normalize_code(row.get("code")) for row in current_rows}
    for row in current_rows:
        code = _normalize_code(row.get("code"))
        before = previous.get(code, {})
        previous_tier = str(before.get("tier") or "")
        current_tier = str(row.get("tier") or "")
        previous_rank = TIER_ORDER.get(previous_tier, -1)
        current_rank = TIER_ORDER.get(current_tier, -1)
        previous_score = _finite_float(before.get("quant_score"))
        current_score = _finite_float(row.get("quant_score"))
        if not before:
            change_type = "NEW_IN_RESEARCH_QUEUE" if current_tier in {"TIER_A", "TIER_B", "TIER_C"} else "NEW_SCREENED"
        elif current_rank > previous_rank:
            change_type = "TIER_UP"
        elif current_rank < previous_rank:
            change_type = "TIER_DOWN"
        elif previous_score is not None and current_score is not None and current_score - previous_score >= 5:
            change_type = "SCORE_UP"
        elif previous_score is not None and current_score is not None and previous_score - current_score >= 5:
            change_type = "SCORE_DOWN"
        else:
            change_type = "UNCHANGED"
        opportunity_rows.append(
            {
                "code": code,
                "stock_name": row.get("stock_name"),
                "normalized_industry": row.get("normalized_industry"),
                "previous_tier": previous_tier,
                "current_tier": current_tier,
                "previous_quant_score": previous_score,
                "current_quant_score": current_score,
                "change_type": change_type,
                "detail": row.get("next_review_trigger"),
            }
        )
        previous_industry = str(before.get("industry_evidence_status") or "")
        previous_company = str(before.get("company_evidence_status") or "")
        current_industry = str(row.get("industry_evidence_status") or "")
        current_company = str(row.get("company_evidence_status") or "")
        evidence_change = "UNCHANGED"
        if not before:
            evidence_change = "NEW_EVIDENCE_STATE"
        elif previous_industry != current_industry or previous_company != current_company:
            evidence_change = "EVIDENCE_STATUS_CHANGED"
        evidence_rows.append(
            {
                "code": code,
                "stock_name": row.get("stock_name"),
                "normalized_industry": row.get("normalized_industry"),
                "previous_industry_evidence_status": previous_industry,
                "current_industry_evidence_status": current_industry,
                "previous_company_evidence_status": previous_company,
                "current_company_evidence_status": current_company,
                "change_type": evidence_change,
            }
        )
    for code, before in previous.items():
        if _normalize_code(code) not in current_codes and str(before.get("tier")) in {"TIER_A", "TIER_B", "TIER_C"}:
            opportunity_rows.append(
                {
                    "code": code,
                    "stock_name": before.get("stock_name"),
                    "normalized_industry": before.get("normalized_industry"),
                    "previous_tier": before.get("tier"),
                    "current_tier": "",
                    "previous_quant_score": before.get("quant_score"),
                    "current_quant_score": "",
                    "change_type": "LEFT_RESEARCH_QUEUE",
                    "detail": "本次未进入研究队列。",
                }
            )
    return opportunity_rows, evidence_rows


def _evidence_rows_for(df: Optional[pd.DataFrame], *, as_of: date, industry: str = "", code: str = "") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    local = df.copy()
    if industry and "industry" in local.columns:
        local = local[local["industry"].astype(str) == industry]
    if code and "code" in local.columns:
        local = local[local["code"].astype(str).str.zfill(6) == _normalize_code(code)]
    date_col = _date_column(local)
    if date_col:
        dates = pd.to_datetime(local[date_col], errors="coerce").dt.date
        local = local[dates <= as_of]
    return local


def _future_evidence_count(df: Optional[pd.DataFrame], *, as_of: date, industry: str = "", code: str = "") -> int:
    if df is None or df.empty:
        return 0
    local = df.copy()
    if industry and "industry" in local.columns:
        local = local[local["industry"].astype(str) == industry]
    if code and "code" in local.columns:
        local = local[local["code"].astype(str).str.zfill(6) == _normalize_code(code)]
    date_col = _date_column(local)
    if not date_col:
        return 0
    dates = pd.to_datetime(local[date_col], errors="coerce").dt.date
    return int((dates > as_of).sum())


def _build_research_tasks(
    *,
    rows: List[Dict[str, Any]],
    industry_evidence_df: Optional[pd.DataFrame],
    company_evidence_df: Optional[pd.DataFrame],
    industry_evidence_schema: Optional[Dict[str, Any]],
    as_of: date,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    observed_industries = sorted({str(row.get("normalized_industry") or "") for row in rows if row.get("normalized_industry")})
    industry_tasks: List[Dict[str, Any]] = []
    company_tasks: List[Dict[str, Any]] = []
    gap_rows: List[Dict[str, Any]] = []

    for industry in expected_industries(industry_evidence_schema, observed_industries):
        indicators, template_status = indicator_templates_for(industry, industry_evidence_schema)
        evidence_rows = _evidence_rows_for(industry_evidence_df, as_of=as_of, industry=industry)
        present = {str(value) for value in evidence_rows.get("evidence_name", pd.Series(dtype=str)).dropna().tolist()}
        missing_required = []
        for indicator in indicators:
            name = str(indicator.get("name") or "")
            required = str(indicator.get("required_or_optional") or "optional")
            freshness_days = int(_finite_float(indicator.get("freshness_limit_days")) or 180)
            oldest = as_of - timedelta(days=freshness_days)
            if name not in present:
                gap_type = "missing_required" if required == "required" else "missing_optional"
                if required == "required":
                    missing_required.append(name)
                gap_rows.append(
                    {
                        "scope": "industry",
                        "industry": industry,
                        "code": "",
                        "stock_name": "",
                        "indicator": name,
                        "required_or_optional": required,
                        "evidence_status": "MISSING",
                        "gap_type": gap_type,
                        "freshness_limit_days": freshness_days,
                        "oldest_accepted_evidence_date": oldest.isoformat(),
                        "recommended_public_sources": indicator.get("source_hint") or "; ".join(DEFAULT_PUBLIC_SOURCES),
                        "template_status": template_status,
                        "note": indicator.get("description") or "",
                    }
                )
        industry_tasks.append(
            {
                "industry": industry,
                "as_of_date": as_of.isoformat(),
                "template_status": template_status,
                "missing_required_indicators": missing_required,
                "indicators": indicators,
                "recommended_public_sources": DEFAULT_PUBLIC_SOURCES,
                "future_dated_evidence_excluded": _future_evidence_count(industry_evidence_df, as_of=as_of, industry=industry),
            }
        )

    for row in rows:
        tier = str(row.get("tier") or "")
        if tier not in {"TIER_A", "TIER_B", "TIER_C"} and str(row.get("quant_screen_status")) not in RESEARCH_STATUSES:
            continue
        code = _normalize_code(row.get("code"))
        company_status = str(row.get("company_evidence_status") or "MISSING")
        company_task = {
            "code": code,
            "stock_name": row.get("stock_name"),
            "industry": row.get("normalized_industry"),
            "as_of_date": as_of.isoformat(),
            "company_evidence_status": company_status,
            "required_evidence": [
                "最近一次定期报告或业绩预告中的利润、现金流、负债变化",
                "公司公告/交易所披露中与行业周期相关的产能、订单、价格、库存证据",
                "是否存在 ST、退市、重大诉讼、财务造假、流动性异常等硬风险",
            ],
            "recommended_public_sources": ["交易所公告", "公司公告", "定期报告", "互动易/公开调研纪要摘要"],
            "future_dated_evidence_excluded": _future_evidence_count(company_evidence_df, as_of=as_of, code=code),
        }
        company_tasks.append(company_task)
        if company_status in {"MISSING", "LEAD_ONLY", "STALE", "CONFLICTING", "PARSE_FAILED"}:
            gap_rows.append(
                {
                    "scope": "company",
                    "industry": row.get("normalized_industry"),
                    "code": code,
                    "stock_name": row.get("stock_name"),
                    "indicator": "company_cycle_evidence",
                    "required_or_optional": "required",
                    "evidence_status": company_status,
                    "gap_type": "company_evidence_incomplete",
                    "freshness_limit_days": 180,
                    "oldest_accepted_evidence_date": (as_of - timedelta(days=180)).isoformat(),
                    "recommended_public_sources": "交易所公告; 公司公告; 定期报告",
                    "template_status": "company_required",
                    "note": "公司证据不足时不得进入 A 类候选。",
                }
            )
    return industry_tasks, company_tasks, gap_rows


def _build_data_quality_rows(
    *,
    requested_codes: List[str],
    inputs: List[BacktestInput],
    data_errors: Mapping[str, str],
    rows: List[Dict[str, Any]],
    industry_evidence_df: Optional[pd.DataFrame],
    company_evidence_df: Optional[pd.DataFrame],
    as_of: date,
) -> List[Dict[str, Any]]:
    input_by_code = {_normalize_code(item.code): item for item in inputs}
    row_by_code = {_normalize_code(row.get("code")): row for row in rows}
    quality: List[Dict[str, Any]] = []
    for code in requested_codes:
        normalized = _normalize_code(code)
        item = input_by_code.get(normalized)
        row = row_by_code.get(normalized, {})
        if normalized in data_errors:
            quality.append(
                {
                    "code": normalized,
                    "stock_name": row.get("stock_name") or (item.stock_name if item else normalized),
                    "stage": "data_load",
                    "status": "FAILED",
                    "issue": "data_error",
                    "detail": data_errors[normalized],
                }
            )
        if item is None:
            quality.append(
                {
                    "code": normalized,
                    "stock_name": row.get("stock_name") or normalized,
                    "stage": "price_history",
                    "status": "NOT_AVAILABLE",
                    "issue": "price_history_missing",
                    "detail": "未加载到 as_of_date 及以前的价格序列。",
                }
            )
            continue
        future_industry = _future_evidence_count(industry_evidence_df, as_of=as_of, industry=str(row.get("normalized_industry") or item.industry or ""))
        future_company = _future_evidence_count(company_evidence_df, as_of=as_of, code=normalized)
        if future_industry or future_company:
            quality.append(
                {
                    "code": normalized,
                    "stock_name": row.get("stock_name") or item.stock_name,
                    "stage": "evidence_as_of_guard",
                    "status": "DEGRADED",
                    "issue": "future_dated_evidence_excluded",
                    "detail": f"industry={future_industry};company={future_company}; future rows were ignored.",
                }
            )
    return quality


def _update_forward_ledger(
    *,
    ledger_path: Path,
    report_dir: Path,
    rows: List[Dict[str, Any]],
    inputs: List[BacktestInput],
    benchmark_df: Optional[pd.DataFrame],
    as_of: date,
    diagnostics: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_csv_rows(ledger_path)
    by_code = {_normalize_code(row.get("code")): dict(row) for row in existing}
    input_by_code = {_normalize_code(item.code): item for item in inputs}
    observed = [row for row in rows if row.get("tier") in {"TIER_A", "TIER_B"}]
    new_records = 0

    for row in observed:
        code = _normalize_code(row.get("code"))
        if code not in by_code:
            snapshot = {
                "tier": row.get("tier"),
                "quant_score": row.get("quant_score"),
                "industry_evidence_status": row.get("industry_evidence_status"),
                "company_evidence_status": row.get("company_evidence_status"),
                "hard_logic_level": row.get("hard_logic_level"),
                "a_condition_failed": row.get("a_condition_failed"),
            }
            by_code[code] = {
                "code": code,
                "stock_name": row.get("stock_name"),
                "industry": row.get("normalized_industry"),
                "first_observation_date": as_of.isoformat(),
                "first_tier": row.get("tier"),
                "first_close": row.get("close"),
                "first_quant_score": row.get("quant_score"),
                "first_evidence_status": f"{row.get('industry_evidence_status')}/{row.get('company_evidence_status')}",
                "rule_version": RULE_VERSION,
                "data_version": str(diagnostics.get("source_mode") or "unknown"),
                "first_snapshot_json": json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                "latest_observation_date": as_of.isoformat(),
                "latest_tier": row.get("tier"),
                "latest_close": row.get("close"),
                "status": "OPEN",
            }
            new_records += 1
        else:
            by_code[code]["latest_observation_date"] = as_of.isoformat()
            by_code[code]["latest_tier"] = row.get("tier")
            by_code[code]["latest_close"] = row.get("close")
            by_code[code]["status"] = "OPEN"

    for code, record in by_code.items():
        item = input_by_code.get(code)
        if item is None:
            continue
        history = prepare_price_frame(item.price_df)
        history = history[history["date"] <= as_of].copy().reset_index(drop=True)
        first_date_text = record.get("first_observation_date")
        try:
            first_date = coerce_date(first_date_text)
        except Exception:
            continue
        first_history = history[history["date"] >= first_date].copy().reset_index(drop=True)
        if first_history.empty:
            continue
        first_close = _finite_float(record.get("first_close")) or _finite_float(first_history.iloc[0].get("close"))
        latest_close = _finite_float(first_history.iloc[-1].get("close"))
        if latest_close is not None:
            record["latest_close"] = latest_close
        if first_close is not None and first_close > 0:
            closes = pd.to_numeric(first_history["close"], errors="coerce").dropna()
            for days in (5, 10, 20, 40, 60):
                if len(first_history) > days:
                    close_at = _finite_float(first_history.iloc[days].get("close"))
                    record[f"return_{days}d_pct"] = _round((close_at / first_close - 1.0) * 100.0 if close_at is not None else None)
            if not closes.empty:
                record["max_up_pct"] = _round((float(closes.max()) / first_close - 1.0) * 100.0)
                record["max_down_pct"] = _round((float(closes.min()) / first_close - 1.0) * 100.0)
        if benchmark_df is not None and not benchmark_df.empty:
            benchmark = benchmark_df[benchmark_df["date"] >= first_date].copy().reset_index(drop=True)
            if len(benchmark) > 20:
                start = _finite_float(benchmark.iloc[0].get("close"))
                end = _finite_float(benchmark.iloc[20].get("close"))
                if start is not None and end is not None and start > 0:
                    record["benchmark_return_20d_pct"] = _round((end / start - 1.0) * 100.0)

    ledger_rows = list(by_code.values())
    ledger_rows.sort(key=lambda row: (str(row.get("first_observation_date") or ""), str(row.get("code") or "")))
    _write_csv(ledger_path, ledger_rows, LEDGER_COLUMNS)
    report_copy = report_dir / "forward_observation_ledger.csv"
    shutil.copyfile(ledger_path, report_copy)

    summary = {
        "ledger_path": str(ledger_path),
        "report_ledger_path": str(report_copy),
        "tracked_count": len(ledger_rows),
        "new_records": new_records,
        "observed_tier_a_b_count": len(observed),
        "rule_version": RULE_VERSION,
    }
    _json_dump(report_dir / "forward_performance_summary.json", summary)
    (report_dir / "forward_performance_summary.md").write_text(
        "\n".join(
            [
                "# Forward Observation Summary",
                "",
                DISCOVERY_DISCLAIMER,
                "",
                f"- tracked_count: {summary['tracked_count']}",
                f"- new_records: {summary['new_records']}",
                f"- observed_tier_a_b_count: {summary['observed_tier_a_b_count']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return ledger_rows, summary


def _summary_markdown(summary: Mapping[str, Any], rows: List[Dict[str, Any]]) -> str:
    top_rows = [row for row in rows if row.get("tier") in {"TIER_A", "TIER_B", "TIER_C"}]
    lines = [
        "# GenGe Opportunity Discovery Daily Report",
        "",
        DISCOVERY_DISCLAIMER,
        "",
        f"- as_of_date: {summary.get('resolved_as_of_date')}",
        f"- total_stocks: {summary.get('total_stocks')}",
        f"- valid_stocks: {summary.get('valid_stocks')}",
        f"- priority_research_queue_count: {summary.get('priority_research_queue_count')}",
        f"- secondary_research_queue_count: {summary.get('secondary_research_queue_count')}",
        f"- industry_evidence_coverage_rate: {summary.get('industry_evidence_coverage_rate')}",
        f"- company_evidence_coverage_rate: {summary.get('company_evidence_coverage_rate')}",
        f"- provider_distribution: {json.dumps(summary.get('provider_distribution'), ensure_ascii=False, sort_keys=True)}",
        f"- fallback_distribution: {json.dumps(summary.get('fallback_distribution'), ensure_ascii=False, sort_keys=True)}",
        f"- tier_distribution: {json.dumps(summary.get('tier_distribution'), ensure_ascii=False, sort_keys=True)}",
        f"- acceptance_enum: {summary.get('acceptance_enum')}",
        f"- acceptance_milestones: {json.dumps(summary.get('acceptance_milestones'), ensure_ascii=False)}",
        "",
        "## Research Queue",
        "",
    ]
    if not top_rows:
        lines.append("- 本次没有 A/B/C 研究对象；请优先查看 evidence_gap_report.csv 和 quant_screen_all.csv。")
    else:
        for row in sorted(top_rows, key=lambda item: int(item.get("opportunity_quality_rank") or 999))[:20]:
            lines.append(
                "- {code} {name} / {industry} / {tier} / quality_rank={quality_rank} / proximity_rank={proximity_rank} / quant={score} / evidence={industry_status}/{company_status} / trigger={trigger}".format(
                    code=row.get("code"),
                    name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    tier=row.get("tier"),
                    quality_rank=row.get("opportunity_quality_rank"),
                    proximity_rank=row.get("opportunity_proximity_rank"),
                    score=row.get("quant_score"),
                    industry_status=row.get("industry_evidence_status"),
                    company_status=row.get("company_evidence_status"),
                    trigger=row.get("next_review_trigger"),
                )
            )
    lines.append("")
    return "\n".join(lines)


def run_opportunity_discovery(
    *,
    inputs: List[BacktestInput],
    requested_codes: List[str],
    data_errors: Mapping[str, str],
    data_sources: Mapping[str, str],
    benchmark_df: Optional[pd.DataFrame],
    industry_cycle_df: Optional[pd.DataFrame],
    industry_evidence_df: Optional[pd.DataFrame],
    company_evidence_df: Optional[pd.DataFrame],
    industry_evidence_schema: Optional[Dict[str, Any]],
    industry_alias_map: Mapping[str, Any],
    requested_as_of_date: Any,
    output_dir: str | Path,
    diagnostics: Optional[Mapping[str, Any]] = None,
    priority_queue_size: int = 50,
    secondary_queue_size: int = 150,
    exit_profile_df: Optional[pd.DataFrame] = None,
    ledger_path: str | Path | None = None,
) -> Tuple[Path, Dict[str, Any]]:
    pipeline_started = time.perf_counter()
    requested_date = coerce_date(requested_as_of_date) if requested_as_of_date else None
    price_dates: Dict[str, Optional[date]] = {}
    histories: Dict[str, pd.DataFrame] = {}
    for item in inputs:
        history = prepare_price_frame(item.price_df)
        if requested_date:
            history = history[history["date"] <= requested_date].copy()
        histories[_normalize_code(item.code)] = history.reset_index(drop=True)
        price_dates[_normalize_code(item.code)] = max(history["date"]) if not history.empty else None
    available_dates = [value for value in price_dates.values() if value is not None]
    resolved_as_of = requested_date or (max(available_dates) if available_dates else date.today())
    benchmark_history = prepare_price_frame(benchmark_df) if benchmark_df is not None and not benchmark_df.empty else None
    if benchmark_history is not None:
        benchmark_history = benchmark_history[benchmark_history["date"] <= resolved_as_of].copy().reset_index(drop=True)

    output_path = Path(output_dir)
    report_dir = output_path / pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)

    resolver = IndustryAliasResolver(industry_alias_map, company_evidence_df)
    exit_profiles = _exit_profile_by_code(exit_profile_df)
    strategy = GenGeCycleBottomStrategy()
    rows: List[Dict[str, Any]] = []
    input_by_code = {_normalize_code(item.code): item for item in inputs}
    requested_records = {
        _normalize_code(record.get("code")): record
        for record in (diagnostics or {}).get("requested_stock_records", [])
        if isinstance(record, Mapping)
    }

    for code in [_normalize_code(value) for value in requested_codes]:
        item = input_by_code.get(code)
        if item is None:
            continue
        history = histories.get(code, pd.DataFrame())
        latest_date, close = _latest_price(history)
        record = requested_records.get(code, {})
        raw_industry = item.industry or record.get("industry") or ""
        resolution = resolver.resolve(code=code, stock_name=item.stock_name or record.get("stock_name") or code, raw_industry=raw_industry)
        try:
            signal = strategy.generate_signal(
                code=code,
                stock_name=item.stock_name or record.get("stock_name") or code,
                as_of_date=resolved_as_of,
                price_df=item.price_df,
                valuation_df=item.valuation_df,
                financial_df=item.financial_df,
                benchmark_df=benchmark_history,
                industry_cycle_df=industry_cycle_df,
                industry_evidence_df=industry_evidence_df,
                company_evidence_df=company_evidence_df,
                industry_evidence_schema=industry_evidence_schema,
                industry=resolution.normalized_industry if resolution.match_type != "UNRESOLVED" else resolution.raw_industry,
                extra_risk_flags=["industry_alias_unresolved"] if resolution.match_type == "UNRESOLVED" else None,
            )
            signal_row = signal.to_dict()
        except Exception as exc:
            rows.append(
                {
                    "code": code,
                    "stock_name": item.stock_name or code,
                    "raw_industry": raw_industry,
                    "normalized_industry": resolution.normalized_industry,
                    "as_of_date": resolved_as_of.isoformat(),
                    "latest_price_date": latest_date.isoformat() if latest_date else "",
                    "close": close,
                    "quant_score": 0.0,
                    "quant_screen_status": "HARD_REJECT",
                    "quant_reason": f"信号生成失败：{type(exc).__name__}",
                    "price_position_score": "",
                    "hard_reject_blockers": "signal_generation_failed",
                    "soft_blockers": "",
                    "next_evidence_needed": "price_history;signal_generation_debug",
                    "missing_fields": "signal_generation",
                    "risk_flags": type(exc).__name__,
                    "disclaimer": DISCOVERY_DISCLAIMER,
                }
            )
            continue

        rs20 = _relative_strength(history, benchmark_history, 20)
        rs60 = _relative_strength(history, benchmark_history, 60)
        row: Dict[str, Any] = {
            **signal_row,
            "raw_industry": raw_industry,
            "normalized_industry": resolution.normalized_industry,
            "as_of_date": resolved_as_of.isoformat(),
            "latest_price_date": latest_date.isoformat() if latest_date else "",
            "close": close,
            "relative_strength_20d": rs20,
            "relative_strength_60d": rs60,
            "balanced_exit_historical_profile": exit_profiles.get(code, "NOT_AVAILABLE"),
            "disclaimer": DISCOVERY_DISCLAIMER,
        }
        row["quant_score"] = _quant_score(row, rs20, rs60)
        hard, soft = _screen_blockers(row)
        row["hard_reject_blockers"] = ";".join(hard)
        row["soft_blockers"] = ";".join(soft)
        row["quant_screen_status"] = _screen_status(row, hard, soft)
        row["quant_reason"] = _quant_reason(row, hard, soft)
        row["price_position_score"] = _round(row.get("price_percentile_score"))
        row["next_evidence_needed"] = _next_evidence_needed(row)
        rows.append(row)

    valid_rows = [row for row in rows if str(row.get("quant_screen_status")) != "HARD_REJECT" or row.get("close") not in (None, "")]
    priority_queue = sorted(
        [row for row in rows if row.get("quant_screen_status") == "PRIORITY_RESEARCH"],
        key=lambda item: _finite_float(item.get("quant_score")) or 0.0,
        reverse=True,
    )[: max(0, int(priority_queue_size))]
    secondary_queue = sorted(
        [row for row in rows if row.get("quant_screen_status") == "SECONDARY_RESEARCH"],
        key=lambda item: _finite_float(item.get("quant_score")) or 0.0,
        reverse=True,
    )[: max(0, int(secondary_queue_size))]

    tier_rows = _rank_opportunities([_tier_row(dict(row)) for row in rows])
    tier_a = [row for row in tier_rows if row.get("tier") == "TIER_A"]
    tier_b = [row for row in tier_rows if row.get("tier") == "TIER_B"]
    tier_c = [row for row in tier_rows if row.get("tier") == "TIER_C"]

    industry_tasks, company_tasks, gap_rows = _build_research_tasks(
        rows=tier_rows,
        industry_evidence_df=industry_evidence_df,
        company_evidence_df=company_evidence_df,
        industry_evidence_schema=industry_evidence_schema,
        as_of=resolved_as_of,
    )
    evidence_inventory_rows = _build_evidence_inventory(
        industry_evidence_df=industry_evidence_df,
        company_evidence_df=company_evidence_df,
        as_of=resolved_as_of,
    )
    data_quality_rows = _build_data_quality_rows(
        requested_codes=requested_codes,
        inputs=inputs,
        data_errors=data_errors,
        rows=tier_rows,
        industry_evidence_df=industry_evidence_df,
        company_evidence_df=company_evidence_df,
        as_of=resolved_as_of,
    )
    previous_state = _load_previous_state(output_path, report_dir)
    opportunity_changes, evidence_changes = _changes(tier_rows, previous_state)

    target_ledger = Path(ledger_path) if ledger_path else Path("data/opportunity_snapshots/forward_observation_ledger.csv")
    ledger_rows, forward_summary = _update_forward_ledger(
        ledger_path=target_ledger,
        report_dir=report_dir,
        rows=tier_rows,
        inputs=inputs,
        benchmark_df=benchmark_history,
        as_of=resolved_as_of,
        diagnostics=diagnostics or {},
    )

    milestones = []
    if not valid_rows:
        acceptance = "FAIL_CURRENT_SNAPSHOT"
    else:
        milestones.append("PASS_CURRENT_SNAPSHOT_PIPELINE_READY")
        if priority_queue or secondary_queue:
            milestones.append("PASS_QUANT_RESEARCH_QUEUE_GENERATED")
        if industry_tasks and gap_rows is not None:
            milestones.append("PASS_EVIDENCE_ENRICHMENT_READY")
        if tier_b or tier_c or tier_a or priority_queue or secondary_queue:
            milestones.append("PASS_OPPORTUNITY_DISCOVERY_RESEARCH_READY")
        if tier_a:
            milestones.append("PASS_TIER_A_CANDIDATE_GENERATED")
        if forward_summary.get("observed_tier_a_b_count"):
            milestones.append("PASS_FORWARD_OBSERVATION_READY")
        acceptance = milestones[-1] if milestones else "FAIL_CURRENT_SNAPSHOT"

    provider_distribution = dict(Counter(str(source or "unknown") for source in data_sources.values()))
    fallback_distribution = {
        provider: count
        for provider, count in provider_distribution.items()
        if provider not in {"EfinanceFetcher", "csv", "fixture"}
    }
    industry_status_counts = Counter(str(row.get("industry_evidence_status") or "UNKNOWN") for row in tier_rows)
    company_status_counts = Counter(str(row.get("company_evidence_status") or "UNKNOWN") for row in tier_rows)
    evidence_positive_statuses = {"VERIFIED", "PARTIALLY_VERIFIED", "LEAD_ONLY", "STALE", "CONFLICTING"}
    denominator = max(1, len(valid_rows))
    industry_coverage_rate = round(
        sum(industry_status_counts.get(status, 0) for status in evidence_positive_statuses) / denominator * 100.0,
        4,
    )
    company_coverage_rate = round(
        sum(company_status_counts.get(status, 0) for status in evidence_positive_statuses) / denominator * 100.0,
        4,
    )
    quality_top20 = [
        {
            "rank": row.get("opportunity_quality_rank"),
            "code": row.get("code"),
            "stock_name": row.get("stock_name"),
            "tier": row.get("tier"),
            "quant_score": row.get("quant_score"),
            "opportunity_quality_score": row.get("opportunity_quality_score"),
            "blockers": row.get("a_condition_failed"),
        }
        for row in sorted(tier_rows, key=lambda item: int(item.get("opportunity_quality_rank") or 999))[:20]
    ]
    proximity_top20 = [
        {
            "rank": row.get("opportunity_proximity_rank"),
            "code": row.get("code"),
            "stock_name": row.get("stock_name"),
            "tier": row.get("tier"),
            "failed_conditions": row.get("a_condition_fail_count"),
            "blockers": row.get("a_condition_failed"),
        }
        for row in sorted(tier_rows, key=lambda item: int(item.get("opportunity_proximity_rank") or 999))[:20]
    ]

    summary: Dict[str, Any] = {
        "diagnostics": dict(diagnostics or {}),
        "requested_as_of_date": requested_date.isoformat() if requested_date else None,
        "resolved_as_of_date": resolved_as_of.isoformat(),
        "total_stocks": len(requested_codes),
        "valid_stocks": len(valid_rows),
        "data_failure_count": len(data_errors),
        "data_sources": dict(data_sources),
        "provider_distribution": provider_distribution,
        "fallback_distribution": fallback_distribution,
        "priority_research_queue_count": len(priority_queue),
        "secondary_research_queue_count": len(secondary_queue),
        "rejected_at_quant_stage_count": sum(1 for row in rows if row.get("quant_screen_status") == "HARD_REJECT"),
        "tier_distribution": dict(Counter(str(row.get("tier") or "UNKNOWN") for row in tier_rows)),
        "tier_a_count": len(tier_a),
        "tier_b_count": len(tier_b),
        "tier_c_count": len(tier_c),
        "industry_research_task_count": len(industry_tasks),
        "company_research_task_count": len(company_tasks),
        "evidence_gap_count": len(gap_rows),
        "evidence_inventory_count": len(evidence_inventory_rows),
        "industry_evidence_coverage_rate": industry_coverage_rate,
        "company_evidence_coverage_rate": company_coverage_rate,
        "evidence_status_distribution": {
            "industry": dict(industry_status_counts),
            "company": dict(company_status_counts),
        },
        "opportunity_quality_top20": quality_top20,
        "opportunity_proximity_top20": proximity_top20,
        "acceptance_enum": acceptance,
        "acceptance_milestones": milestones,
        "forward_observation": forward_summary,
        "pipeline_elapsed_seconds": round(time.perf_counter() - pipeline_started, 4),
        "no_auto_trade": True,
        "no_broker_integration": True,
        "candidate_semantics": "research_candidate_manual_review_only",
        "rule_version": RULE_VERSION,
    }

    _write_csv(report_dir / "quant_screen_all.csv", rows, QUANT_COLUMNS)
    _write_csv(report_dir / "priority_research_queue.csv", priority_queue, QUANT_COLUMNS)
    _write_csv(report_dir / "secondary_research_queue.csv", secondary_queue, QUANT_COLUMNS)
    _write_csv(report_dir / "tier_a_candidates.csv", tier_a, OPPORTUNITY_COLUMNS)
    _write_csv(report_dir / "tier_b_watchlist.csv", tier_b, OPPORTUNITY_COLUMNS)
    _write_csv(report_dir / "tier_c_evidence_incomplete.csv", tier_c, OPPORTUNITY_COLUMNS)
    _write_csv(report_dir / "opportunity_changes.csv", opportunity_changes, CHANGE_COLUMNS)
    _write_csv(report_dir / "evidence_changes.csv", evidence_changes, EVIDENCE_CHANGE_COLUMNS)
    _write_csv(report_dir / "evidence_gap_report.csv", gap_rows, GAP_COLUMNS)
    _write_csv(report_dir / "evidence_inventory.csv", evidence_inventory_rows, EVIDENCE_INVENTORY_COLUMNS)
    _write_csv(report_dir / "data_quality_audit.csv", data_quality_rows, DATA_QUALITY_COLUMNS)
    _json_dump(report_dir / "industry_research_tasks.json", {"tasks": industry_tasks})
    _json_dump(report_dir / "company_research_tasks.json", {"tasks": company_tasks})
    _json_dump(report_dir / "quant_screen_summary.json", summary)
    (report_dir / "quant_screen_summary.md").write_text(_summary_markdown(summary, tier_rows), encoding="utf-8")
    _json_dump(
        report_dir / "daily_opportunity_report.json",
        {
            "summary": summary,
            "priority_research_queue": priority_queue,
            "tier_a_candidates": tier_a,
            "tier_b_watchlist": tier_b,
            "tier_c_evidence_incomplete": tier_c,
            "all_opportunities": tier_rows,
        },
    )
    (report_dir / "daily_opportunity_report.md").write_text(_summary_markdown(summary, tier_rows), encoding="utf-8")

    return report_dir, summary
