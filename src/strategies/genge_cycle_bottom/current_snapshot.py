"""Current trading-day snapshot scanner for GenGe Cycle Bottom Strategy.

This module is intentionally separate from the walk-forward backtest path. It
uses only rows available at ``as_of_date`` and treats user evidence as current
snapshot context, never as historical future knowledge.
"""

from __future__ import annotations

import csv
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd
import yaml

from .backtest import BacktestInput
from .features import coerce_date, prepare_price_frame
from .industry_evidence import CONFIDENCE_RANK, HARD_LOGIC_RANK
from .report import write_industry_evidence_cards
from .strategy import GenGeCycleBottomStrategy


SNAPSHOT_DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入建议，不应自动交易。"
SNAPSHOT_DECISIONS = ("RESEARCH_CANDIDATE", "WATCH_ONLY", "NOT_QUALIFIED", "DATA_INSUFFICIENT")
TREND_RANK = {"NONE": 0, "WEAK": 1, "MEDIUM": 2, "STRONG": 3}
TURNING_PHASES = {"BOTTOMING", "RECOVERING", "bottom_repair", "recovering"}
HIGH_QUALITY_SOURCE_TYPES = {"OFFICIAL_REPORT", "COMPANY_ANNOUNCEMENT", "EXCHANGE_DISCLOSURE"}
DATE_COLUMNS = ("date", "trade_date", "disclosure_date", "publish_date", "ann_date", "announcement_date", "report_date", "end_date")
CURRENT_SNAPSHOT_COLUMNS = [
    "code",
    "stock_name",
    "raw_industry",
    "normalized_industry",
    "as_of_date",
    "latest_price_date",
    "price_percentile_5y",
    "distance_from_5y_low_pct",
    "valuation_score",
    "valuation_status",
    "financial_safety_score",
    "financial_status",
    "trend_confirmation_level",
    "trend_turning_point_score",
    "industry_cycle_phase",
    "industry_evidence_score",
    "industry_evidence_confidence",
    "industry_evidence_quality",
    "company_evidence_score",
    "company_evidence_confidence",
    "hard_logic_score",
    "hard_logic_level",
    "execution_risk_quality",
    "value_trap_score",
    "balanced_exit_historical_profile",
    "snapshot_decision",
    "reason",
    "blockers",
    "evidence_items",
    "missing_evidence",
    "disclaimer",
]
ALIAS_RESOLUTION_COLUMNS = [
    "code",
    "stock_name",
    "raw_industry",
    "normalized_industry",
    "matched_evidence_industry",
    "match_type",
    "match_confidence",
    "unresolved_reason",
]
DATA_FAILURE_AUDIT_COLUMNS = [
    "code",
    "stock_name",
    "stage",
    "error_type",
    "error_message",
    "provider",
    "retry_count",
    "fallback_used",
    "final_status",
]


@dataclass(frozen=True)
class AliasResolution:
    code: str
    stock_name: str
    raw_industry: str
    normalized_industry: str
    matched_evidence_industry: str
    match_type: str
    match_confidence: str
    unresolved_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "stock_name": self.stock_name,
            "raw_industry": self.raw_industry,
            "normalized_industry": self.normalized_industry,
            "matched_evidence_industry": self.matched_evidence_industry,
            "match_type": self.match_type,
            "match_confidence": self.match_confidence,
            "unresolved_reason": self.unresolved_reason,
        }


def normalize_industry_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(text.split())
    return text.lower()


def load_industry_alias_map(path: str | Path | None) -> Dict[str, Any]:
    if not path:
        return {"industries": {}}
    alias_path = Path(path)
    if not alias_path.exists():
        raise FileNotFoundError(f"industry alias map not found: {alias_path}")
    raw = yaml.safe_load(alias_path.read_text(encoding="utf-8")) or {}
    industries = raw.get("industries") or {}
    if not isinstance(industries, dict):
        raise ValueError("industry alias map must contain an industries mapping")
    return raw


class IndustryAliasResolver:
    def __init__(self, alias_map: Mapping[str, Any] | None, company_evidence_df: Optional[pd.DataFrame] = None):
        self.alias_map = alias_map or {"industries": {}}
        self.by_key: Dict[str, Tuple[str, str]] = {}
        for canonical, config in (self.alias_map.get("industries") or {}).items():
            canonical_text = str(canonical).strip()
            self.by_key[normalize_industry_key(canonical_text)] = (canonical_text, "EXACT")
            for alias in (config or {}).get("aliases") or []:
                self.by_key[normalize_industry_key(alias)] = (canonical_text, "ALIAS")
        self.company_industry_by_code: Dict[str, str] = {}
        if company_evidence_df is not None and not company_evidence_df.empty and {"code", "industry"}.issubset(company_evidence_df.columns):
            local = company_evidence_df.dropna(subset=["code", "industry"]).copy()
            local["code"] = local["code"].astype(str).str.zfill(6)
            for _, row in local.iterrows():
                code = str(row.get("code") or "").zfill(6)
                industry = str(row.get("industry") or "").strip()
                if code and industry and code not in self.company_industry_by_code:
                    self.company_industry_by_code[code] = industry

    def resolve(self, *, code: str, stock_name: str, raw_industry: Any) -> AliasResolution:
        normalized_code = str(code or "").strip().zfill(6)
        raw = str(raw_industry or "").strip()
        company_industry = self.company_industry_by_code.get(normalized_code)
        if company_industry:
            company_key = normalize_industry_key(company_industry)
            canonical, _match_type = self.by_key.get(company_key, (company_industry, "COMPANY_CODE"))
            return AliasResolution(
                code=normalized_code,
                stock_name=stock_name,
                raw_industry=raw,
                normalized_industry=canonical,
                matched_evidence_industry=canonical,
                match_type="COMPANY_CODE",
                match_confidence="HIGH",
            )
        key = normalize_industry_key(raw)
        if key in self.by_key:
            canonical, match_type = self.by_key[key]
            return AliasResolution(
                code=normalized_code,
                stock_name=stock_name,
                raw_industry=raw,
                normalized_industry=canonical,
                matched_evidence_industry=canonical,
                match_type=match_type,
                match_confidence="HIGH" if match_type == "EXACT" else "MEDIUM",
            )
        return AliasResolution(
            code=normalized_code,
            stock_name=stock_name,
            raw_industry=raw,
            normalized_industry="UNRESOLVED",
            matched_evidence_industry="",
            match_type="UNRESOLVED",
            match_confidence="LOW",
            unresolved_reason="no_exact_alias_or_company_code_match",
        )


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result != result else result


def _json_items(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _status_from_score(value: Any, *, threshold: float = 45.0) -> str:
    score = _number(value)
    if score is None:
        return "MISSING"
    if score < 35:
        return "RISK"
    if score < threshold:
        return "WEAK"
    return "PASS"


def _latest_date(df: Optional[pd.DataFrame], as_of_date: date) -> Optional[date]:
    if df is None or df.empty:
        return None
    for column in DATE_COLUMNS:
        if column not in df.columns:
            continue
        series = pd.to_datetime(df[column], errors="coerce").dt.date
        series = series.dropna()
        if series.empty:
            continue
        eligible = [item for item in series if item <= as_of_date]
        if eligible:
            return max(eligible)
    return None


def _company_evidence_counts(row: Dict[str, Any]) -> Tuple[int, int, int, int]:
    items = _json_items(row.get("company_evidence_items"))
    positive = sum(1 for item in items if item.get("evidence_direction") == "POSITIVE")
    negative = sum(1 for item in items if item.get("evidence_direction") == "NEGATIVE")
    neutral = sum(1 for item in items if item.get("evidence_direction") == "NEUTRAL")
    stale = sum(1 for item in items if (_number(item.get("freshness_days")) or 0) > 180)
    return positive, negative, neutral, stale


def _source_types(row: Dict[str, Any]) -> set[str]:
    types = {
        str(item.get("source_type") or "").strip()
        for item in _json_items(row.get("industry_evidence_items")) + _json_items(row.get("company_evidence_items"))
        if str(item.get("source_type") or "").strip()
    }
    return types


def _current_hard_logic(row: Dict[str, Any], resolution: AliasResolution) -> Tuple[float, str, str, List[str]]:
    blockers: List[str] = []
    industry_quality = str(row.get("industry_evidence_quality") or "MISSING")
    industry_confidence = str(row.get("industry_evidence_confidence") or "LOW")
    industry_phase = str(row.get("industry_cycle_phase") or "UNKNOWN")
    industry_score = _number(row.get("industry_evidence_score")) or 50.0
    company_score = _number(row.get("company_evidence_score")) or 50.0
    company_confidence = str(row.get("company_evidence_confidence") or "LOW")
    industry_positive = int(_number(row.get("industry_evidence_positive_count")) or 0)
    industry_negative = int(_number(row.get("industry_evidence_negative_count")) or 0)
    industry_stale = int(_number(row.get("industry_evidence_stale_count")) or 0)
    industry_item_count = len(_json_items(row.get("industry_evidence_items")))
    company_positive, company_negative, _, company_stale = _company_evidence_counts(row)
    trend_level = str(row.get("trend_confirmation_level") or "NONE")
    financial_status = _status_from_score(row.get("financial_safety_score"))
    execution_quality = str(row.get("execution_risk_quality") or "good")
    execution_score = _number(row.get("execution_risk_score")) or 0.0
    price_percentile = _number(row.get("price_percentile_5y"))
    risk_flags = str(row.get("risk_flags") or "")

    has_industry = industry_quality != "MISSING" and resolution.match_type != "UNRESOLVED"
    has_company = str(row.get("company_evidence_source_type") or "MISSING") != "MISSING"
    negative_industry = industry_negative > industry_positive or industry_score < 45 or industry_phase == "DECLINING"
    evidence_expired = bool(industry_item_count and industry_stale >= industry_item_count)
    severe_financial = financial_status == "RISK" or "debt_ratio_extreme" in risk_flags or "loss_making" in risk_flags
    if not has_industry:
        blockers.append("industry_evidence_missing_or_unresolved")
    if negative_industry:
        blockers.append("negative_industry_evidence")
    if evidence_expired:
        blockers.append("stale_industry_evidence")
    if severe_financial:
        blockers.append("severe_financial_risk")
    if blockers:
        return min(industry_score * 0.75 + company_score * 0.25, 49.0), "NONE", "当前截面缺少有效行业证据、行业映射失败、证据过期或存在严重风险，硬逻辑为 NONE。", blockers

    source_types = _source_types(row)
    medium_conditions = {
        "phase": industry_phase in {"BOTTOMING", "RECOVERING"},
        "confidence": CONFIDENCE_RANK.get(industry_confidence, 0) >= CONFIDENCE_RANK["MEDIUM"],
        "positive": industry_positive > industry_negative,
        "trend": TREND_RANK.get(trend_level, 0) >= TREND_RANK["MEDIUM"],
        "financial": financial_status != "RISK",
        "execution": execution_quality != "risky" and execution_score < 60,
    }
    score = max(0.0, min(100.0, industry_score * 0.72 + company_score * 0.20 + (_number(row.get("trend_stabilization_score")) or 0.0) * 0.08))
    if not all(medium_conditions.values()):
        failed = [key for key, passed in medium_conditions.items() if not passed]
        return min(score, 58.0), "WEAK", f"具备行业证据但当前截面 MEDIUM 条件未全满足：{','.join(failed)}。", failed

    level = "MEDIUM"
    strong_conditions = {
        "company_evidence": has_company,
        "company_confidence": CONFIDENCE_RANK.get(company_confidence, 0) >= CONFIDENCE_RANK["MEDIUM"],
        "direction_consistent": company_positive >= company_negative and industry_positive > industry_negative,
        "source_types": len(source_types) >= 2,
        "high_quality_source": bool(source_types & HIGH_QUALITY_SOURCE_TYPES),
        "fresh": industry_stale == 0 and company_stale == 0,
        "no_conflict": "evidence_conflict" not in str(row.get("industry_evidence_warning_flags") or "") and "company_evidence_conflict" not in risk_flags,
        "low_price": price_percentile is not None and price_percentile <= 0.35,
    }
    if all(strong_conditions.values()):
        level = "STRONG"
    else:
        blockers.extend([key for key, passed in strong_conditions.items() if not passed])
    reason = (
        f"当前截面硬逻辑分 {score:.1f}，等级 {level}；行业阶段 {industry_phase}，"
        f"行业证据 {industry_quality}/{industry_confidence}，公司证据置信度 {company_confidence}。"
    )
    return score, level, reason, blockers


def _current_candidate_blockers(row: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if HARD_LOGIC_RANK.get(str(row.get("hard_logic_level") or "NONE"), 0) < HARD_LOGIC_RANK["MEDIUM"]:
        blockers.append("hard_logic_below_medium")
    if str(row.get("industry_cycle_phase") or "") not in {"BOTTOMING", "RECOVERING"}:
        blockers.append("cycle_phase_not_turning")
    if TREND_RANK.get(str(row.get("trend_confirmation_level") or "NONE"), 0) < TREND_RANK["MEDIUM"]:
        blockers.append("trend_below_medium")
    price_percentile = _number(row.get("price_percentile_5y"))
    if price_percentile is None or price_percentile > 0.35:
        blockers.append("price_not_low")
    if row.get("valuation_status") == "RISK":
        blockers.append("valuation_risk")
    if row.get("financial_status") == "RISK":
        blockers.append("financial_risk")
    if str(row.get("execution_risk_quality") or "") in {"risky", "unavailable"} or (_number(row.get("execution_risk_score")) or 0.0) >= 60:
        blockers.append("execution_risk_high")
    if (_number(row.get("value_trap_score")) or 0.0) >= 70:
        blockers.append("value_trap_high")
    if not row.get("latest_price_date"):
        blockers.append("latest_price_missing")
    if str(row.get("balanced_exit_historical_profile") or "").startswith("failed"):
        blockers.append("balanced_exit_profile_failed")
    return blockers


def _decision(blockers: List[str], row: Dict[str, Any]) -> str:
    if "latest_price_missing" in blockers or "close" in str(row.get("missing_fields") or ""):
        return "DATA_INSUFFICIENT"
    if not blockers:
        return "RESEARCH_CANDIDATE"
    if HARD_LOGIC_RANK.get(str(row.get("hard_logic_level") or "NONE"), 0) >= HARD_LOGIC_RANK["WEAK"]:
        return "WATCH_ONLY"
    return "NOT_QUALIFIED"


def _classify_loader_error(message: str) -> Tuple[str, str, str]:
    lower = str(message or "").lower()
    if any(token in lower for token in ("delist", "退市", "invalid", "不存在", "not found")):
        return "price_fetch", "invalid_or_delisted", "SKIPPED_INVALID_OR_DELISTED"
    if any(token in lower for token in ("timeout", "timed out", "connection", "network", "remote", "provider failures", "provider unavailable")):
        return "price_fetch", "network_or_provider_error", "SKIPPED_DATA_UNAVAILABLE"
    if any(token in lower for token in ("empty", "no data", "无数据")):
        return "price_fetch", "no_valid_history", "DATA_INSUFFICIENT"
    return "price_fetch", "provider_or_parse_error", "SKIPPED_DATA_UNAVAILABLE"


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _is_user_supplied_evidence_path(value: Any) -> bool:
    text = str(value or "").replace("\\", "/")
    return "data/user_supplied/" in text and "data/examples/" not in text and "tests/fixtures/" not in text


def _normalize_requested_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _requested_record_map(requested_codes: List[str], diagnostics: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, str]]:
    records: Dict[str, Dict[str, str]] = {
        _normalize_requested_code(code): {"code": _normalize_requested_code(code)}
        for code in requested_codes
    }
    for raw in (diagnostics or {}).get("requested_stock_records") or []:
        if not isinstance(raw, Mapping):
            continue
        code = _normalize_requested_code(raw.get("code"))
        if not code:
            continue
        records.setdefault(code, {"code": code}).update(
            {
                "code": code,
                "stock_name": str(raw.get("stock_name") or code),
                "industry": str(raw.get("industry") or ""),
            }
        )
    return records


def _output_row(signal_row: Dict[str, Any], *, resolution: AliasResolution, resolved_as_of_date: date, latest_price_date: Optional[date]) -> Dict[str, Any]:
    row = dict(signal_row)
    row["raw_industry"] = resolution.raw_industry
    row["normalized_industry"] = resolution.normalized_industry
    row["as_of_date"] = resolved_as_of_date.isoformat()
    row["latest_price_date"] = latest_price_date.isoformat() if latest_price_date else ""
    row["valuation_status"] = _status_from_score(row.get("valuation_score"))
    row["financial_status"] = _status_from_score(row.get("financial_safety_score"))
    row["trend_turning_point_score"] = row.get("trend_stabilization_score")
    row["execution_risk_quality"] = row.get("execution_risk_quality") or "good"
    hard_score, hard_level, hard_reason, hard_blockers = _current_hard_logic(row, resolution)
    row["hard_logic_score"] = round(hard_score, 2)
    row["hard_logic_level"] = hard_level
    row["hard_logic_reason"] = hard_reason
    row["balanced_exit_historical_profile"] = row.get("balanced_exit_historical_profile") or "not_available_current_snapshot"
    candidate_blockers = sorted(set(_current_candidate_blockers(row) + hard_blockers))
    row["snapshot_decision"] = _decision(candidate_blockers, row)
    row["blockers"] = ";".join(candidate_blockers)
    row["reason"] = hard_reason if row["snapshot_decision"] != "RESEARCH_CANDIDATE" else f"符合当前研究观察候选条件；{hard_reason}"
    row["evidence_items"] = json.dumps(
        {
            "industry": _json_items(row.get("industry_evidence_items")),
            "company": _json_items(row.get("company_evidence_items")),
        },
        ensure_ascii=False,
    )
    missing = []
    if resolution.match_type == "UNRESOLVED":
        missing.append("industry_alias_resolution")
    if str(row.get("industry_evidence_quality") or "MISSING") == "MISSING":
        missing.append("industry_evidence")
    if str(row.get("company_evidence_source_type") or "MISSING") == "MISSING":
        missing.append("company_evidence")
    row["missing_evidence"] = ";".join(missing)
    row["disclaimer"] = SNAPSHOT_DISCLAIMER
    return row


def _summary_markdown(summary: Mapping[str, Any], candidate_rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# Current Snapshot Scanner Summary",
        "",
        SNAPSHOT_DISCLAIMER,
        "",
        f"- requested_as_of_date: {summary.get('requested_as_of_date')}",
        f"- resolved_as_of_date: {summary.get('resolved_as_of_date')}",
        f"- snapshot_total_stocks: {summary.get('snapshot_total_stocks')}",
        f"- snapshot_valid_stocks: {summary.get('snapshot_valid_stocks')}",
        f"- fatal_data_failures: {summary.get('fatal_data_failures')}",
        f"- skipped_invalid_or_delisted: {summary.get('skipped_invalid_or_delisted')}",
        f"- skipped_data_unavailable: {summary.get('skipped_data_unavailable')}",
        f"- current_industry_evidence_coverage: {summary.get('current_industry_evidence_coverage')}",
        f"- current_company_evidence_coverage: {summary.get('current_company_evidence_coverage')}",
        f"- industry_alias_matched_stocks: {summary.get('industry_alias_matched_stocks')}",
        f"- unresolved_industry_stocks: {summary.get('unresolved_industry_stocks')}",
        f"- hard_logic_level_distribution: {json.dumps(summary.get('hard_logic_level_distribution'), ensure_ascii=False)}",
        f"- current_cycle_turning_point_candidate_count: {summary.get('current_cycle_turning_point_candidate_count')}",
        f"- acceptance_enum: {summary.get('acceptance_enum')}",
        "",
        "## Candidates",
        "",
    ]
    if not candidate_rows:
        lines.append("- 本次没有产生 current cycle turning point 研究观察候选。")
        lines.append(f"- blocker_distribution: {json.dumps(summary.get('zero_candidate_blockers'), ensure_ascii=False)}")
    else:
        for row in candidate_rows:
            lines.append(f"- {row.get('code')} {row.get('stock_name')} / {row.get('normalized_industry')} / {row.get('hard_logic_level')}")
    lines.append("")
    return "\n".join(lines)


def run_current_snapshot_report(
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
) -> Tuple[Path, Dict[str, Any]]:
    record_map = _requested_record_map(requested_codes, diagnostics)
    price_dates: Dict[str, Optional[date]] = {_normalize_requested_code(code): None for code in requested_codes}
    requested_date = coerce_date(requested_as_of_date) if requested_as_of_date else None
    for item in inputs:
        price_df = prepare_price_frame(item.price_df)
        if requested_date:
            price_df = price_df[price_df["date"] <= requested_date]
        price_dates[item.code] = max(price_df["date"]) if not price_df.empty else None
    available_dates = [item for item in price_dates.values() if item is not None]
    resolved_as_of = requested_date or (max(available_dates) if available_dates else date.today())

    resolver = IndustryAliasResolver(industry_alias_map, company_evidence_df)
    strategy = GenGeCycleBottomStrategy()
    rows: List[Dict[str, Any]] = []
    alias_rows: List[Dict[str, Any]] = []
    evidence_audit_rows: List[Dict[str, Any]] = []
    failure_rows: List[Dict[str, Any]] = []

    input_by_code = {item.code: item for item in inputs}
    alias_by_code: Dict[str, AliasResolution] = {}
    for code in price_dates:
        item = input_by_code.get(code)
        record = record_map.get(code, {"code": code})
        stock_name = (item.stock_name if item else None) or record.get("stock_name") or code
        raw_industry = (item.industry if item else None) or record.get("industry") or ""
        resolution = resolver.resolve(code=code, stock_name=stock_name, raw_industry=raw_industry)
        alias_by_code[code] = resolution
        alias_rows.append(resolution.to_dict())

    for code, message in data_errors.items():
        normalized_code = _normalize_requested_code(code)
        stage, error_type, final_status = _classify_loader_error(message)
        record = record_map.get(normalized_code, {"code": normalized_code})
        failure_rows.append(
            {
                "code": normalized_code,
                "stock_name": record.get("stock_name") or normalized_code,
                "stage": stage,
                "error_type": error_type,
                "error_message": message,
                "provider": data_sources.get(normalized_code, data_sources.get(code, "public_data_provider")),
                "retry_count": 0,
                "fallback_used": False,
                "final_status": final_status,
            }
        )

    for item in inputs:
        latest_price_date = price_dates.get(item.code)
        resolution = alias_by_code.get(item.code) or resolver.resolve(code=item.code, stock_name=item.stock_name, raw_industry=item.industry)
        if latest_price_date is None:
            failure_rows.append(
                {
                    "code": item.code,
                    "stock_name": item.stock_name,
                    "stage": "price_history",
                    "error_type": "no_valid_history",
                    "error_message": "no price row on or before requested as_of_date",
                    "provider": data_sources.get(item.code, "unknown"),
                    "retry_count": 0,
                    "fallback_used": False,
                    "final_status": "DATA_INSUFFICIENT",
                }
            )
            continue
        try:
            signal = strategy.generate_signal(
                code=item.code,
                stock_name=item.stock_name,
                as_of_date=resolved_as_of,
                price_df=item.price_df,
                valuation_df=item.valuation_df,
                financial_df=item.financial_df,
                benchmark_df=benchmark_df,
                industry_cycle_df=industry_cycle_df,
                industry_evidence_df=industry_evidence_df,
                company_evidence_df=company_evidence_df,
                industry_evidence_schema=industry_evidence_schema,
                industry=resolution.normalized_industry if resolution.match_type != "UNRESOLVED" else resolution.raw_industry,
                extra_risk_flags=["industry_alias_unresolved"] if resolution.match_type == "UNRESOLVED" else None,
            )
            row = _output_row(signal.to_dict(), resolution=resolution, resolved_as_of_date=resolved_as_of, latest_price_date=latest_price_date)
            rows.append(row)
            evidence_audit_rows.append(
                {
                    "code": row.get("code"),
                    "stock_name": row.get("stock_name"),
                    "raw_industry": resolution.raw_industry,
                    "normalized_industry": resolution.normalized_industry,
                    "matched_evidence_industry": resolution.matched_evidence_industry,
                    "industry_match_type": resolution.match_type,
                    "industry_evidence_matched": str(row.get("industry_evidence_quality") != "MISSING"),
                    "industry_evidence_score": row.get("industry_evidence_score"),
                    "industry_evidence_confidence": row.get("industry_evidence_confidence"),
                    "company_evidence_matched": str(row.get("company_evidence_source_type") != "MISSING"),
                    "company_evidence_score": row.get("company_evidence_score"),
                    "company_evidence_confidence": row.get("company_evidence_confidence"),
                    "evidence_item_count": len(_json_items(row.get("industry_evidence_items"))) + len(_json_items(row.get("company_evidence_items"))),
                    "missing_evidence": row.get("missing_evidence"),
                    "hard_logic_level": row.get("hard_logic_level"),
                    "hard_logic_reason": row.get("hard_logic_reason"),
                }
            )
        except Exception as exc:
            failure_rows.append(
                {
                    "code": item.code,
                    "stock_name": item.stock_name,
                    "stage": "snapshot_signal",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "provider": data_sources.get(item.code, "unknown"),
                    "retry_count": 0,
                    "fallback_used": False,
                    "final_status": "FATAL_ERROR",
                }
            )

    output_path = Path(output_dir)
    timestamp_path = output_path / pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    timestamp_path.mkdir(parents=True, exist_ok=True)
    candidates = [row for row in rows if row.get("snapshot_decision") == "RESEARCH_CANDIDATE"]
    watch_only = [row for row in rows if row.get("snapshot_decision") == "WATCH_ONLY"]
    blocker_counter = Counter()
    for row in rows:
        if row.get("snapshot_decision") != "RESEARCH_CANDIDATE":
            blocker_counter.update(token for token in str(row.get("blockers") or "").split(";") if token)

    valid_count = len(rows)
    industry_matched = sum(1 for row in rows if row.get("industry_evidence_quality") != "MISSING")
    company_matched = sum(1 for row in rows if row.get("company_evidence_source_type") != "MISSING")
    alias_matched = sum(1 for row in alias_rows if row.get("match_type") != "UNRESOLVED")
    unresolved = sum(1 for row in alias_rows if row.get("match_type") == "UNRESOLVED")
    stale_financial_count = sum(
        1
        for item in inputs
        if _latest_date(item.financial_df, resolved_as_of) is None or (resolved_as_of - (_latest_date(item.financial_df, resolved_as_of) or resolved_as_of)).days > 540
    )
    stale_evidence_count = sum(
        1
        for row in rows
        if int(_number(row.get("industry_evidence_stale_count")) or 0) > 0
        or any((_number(item.get("freshness_days")) or 0) > 180 for item in _json_items(row.get("company_evidence_items")))
    )
    fatal_data_failures = sum(1 for row in failure_rows if str(row.get("final_status")) == "FATAL_ERROR")
    skipped_invalid_or_delisted = sum(1 for row in failure_rows if str(row.get("final_status")).startswith("SKIPPED_INVALID"))
    skipped_data_unavailable = sum(1 for row in failure_rows if str(row.get("final_status")) == "SKIPPED_DATA_UNAVAILABLE")
    summary: Dict[str, Any] = {
        "diagnostics": dict(diagnostics or {}),
        "requested_as_of_date": requested_date.isoformat() if requested_date else None,
        "resolved_as_of_date": resolved_as_of.isoformat(),
        "latest_price_date_by_stock": {code: value.isoformat() if value else None for code, value in price_dates.items()},
        "stale_price_count": sum(1 for value in price_dates.values() if value is not None and value < resolved_as_of),
        "stale_financial_count": stale_financial_count,
        "stale_evidence_count": stale_evidence_count,
        "snapshot_total_stocks": len(requested_codes),
        "snapshot_valid_stocks": valid_count,
        "industry_evidence_matched_stocks": industry_matched,
        "company_evidence_matched_stocks": company_matched,
        "unresolved_industry_stocks": unresolved,
        "industry_alias_matched_stocks": alias_matched,
        "current_industry_evidence_coverage": round(industry_matched / valid_count * 100, 4) if valid_count else 0.0,
        "current_company_evidence_coverage": round(company_matched / valid_count * 100, 4) if valid_count else 0.0,
        "evidence_covered_industries": sorted({str(row.get("normalized_industry")) for row in rows if row.get("industry_evidence_quality") != "MISSING"}),
        "evidence_covered_codes": sorted({str(row.get("code")) for row in rows if row.get("company_evidence_source_type") != "MISSING"}),
        "hard_logic_level_distribution": dict(Counter(str(row.get("hard_logic_level") or "NONE") for row in rows)),
        "snapshot_decision_distribution": dict(Counter(str(row.get("snapshot_decision") or "UNKNOWN") for row in rows)),
        "current_cycle_turning_point_candidate_count": len(candidates),
        "current_cycle_turning_point_candidate_count_by_industry": dict(Counter(str(row.get("normalized_industry") or "UNKNOWN") for row in candidates)),
        "zero_candidate_blockers": dict(blocker_counter),
        "fatal_data_failures": fatal_data_failures,
        "skipped_invalid_or_delisted": skipped_invalid_or_delisted,
        "skipped_data_unavailable": skipped_data_unavailable,
        "data_failure_status_distribution": dict(Counter(str(row.get("final_status") or "UNKNOWN") for row in failure_rows)),
        "data_failure_audit_count": len(failure_rows),
        "industry_evidence_rows": int(len(industry_evidence_df)) if industry_evidence_df is not None else 0,
        "company_evidence_rows": int(len(company_evidence_df)) if company_evidence_df is not None else 0,
        "industry_evidence_file": (diagnostics or {}).get("industry_evidence_file"),
        "company_evidence_file": (diagnostics or {}).get("company_evidence_file"),
        "industry_alias_map": (diagnostics or {}).get("industry_alias_map"),
        "no_auto_trade": True,
        "current_snapshot_mode": True,
        "sample_hardcoded_status": "sample industries/stocks are not hardcoded as candidates; aliases only normalize industry labels",
    }
    acceptance = "FAIL_CURRENT_SNAPSHOT"
    if (
        fatal_data_failures == 0
        and valid_count > 0
        and alias_matched > 0
        and _is_user_supplied_evidence_path(summary["industry_evidence_file"])
        and _is_user_supplied_evidence_path(summary["company_evidence_file"])
        and alias_rows
    ):
        acceptance = "PASS_CURRENT_SNAPSHOT_CANDIDATE_GENERATED" if candidates else "PASS_CURRENT_SNAPSHOT_RESEARCH_READY"
    summary["acceptance_enum"] = acceptance

    _write_csv(timestamp_path / "current_snapshot_all.csv", rows, CURRENT_SNAPSHOT_COLUMNS)
    candidate_rows = candidates or [
        {
            "reason": "本次未产生符合规则的当前周期拐点研究观察候选",
            "blockers": json.dumps(dict(blocker_counter), ensure_ascii=False, sort_keys=True),
            "disclaimer": SNAPSHOT_DISCLAIMER,
        }
    ]
    _write_csv(timestamp_path / "current_cycle_turning_point_candidates.csv", candidate_rows, CURRENT_SNAPSHOT_COLUMNS)
    _write_csv(timestamp_path / "current_watch_only_candidates.csv", watch_only, CURRENT_SNAPSHOT_COLUMNS)
    _write_csv(timestamp_path / "industry_alias_resolution.csv", alias_rows, ALIAS_RESOLUTION_COLUMNS)
    _write_csv(
        timestamp_path / "evidence_match_audit.csv",
        evidence_audit_rows,
        [
            "code",
            "stock_name",
            "raw_industry",
            "normalized_industry",
            "matched_evidence_industry",
            "industry_match_type",
            "industry_evidence_matched",
            "industry_evidence_score",
            "industry_evidence_confidence",
            "company_evidence_matched",
            "company_evidence_score",
            "company_evidence_confidence",
            "evidence_item_count",
            "missing_evidence",
            "hard_logic_level",
            "hard_logic_reason",
        ],
    )
    _write_csv(timestamp_path / "data_failure_audit.csv", failure_rows, DATA_FAILURE_AUDIT_COLUMNS)
    write_industry_evidence_cards(rows, timestamp_path / "industry_evidence_cards.json", timestamp_path / "industry_evidence_cards.md")
    (timestamp_path / "current_snapshot_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (timestamp_path / "current_snapshot_summary.md").write_text(_summary_markdown(summary, candidates), encoding="utf-8")
    return timestamp_path, summary
