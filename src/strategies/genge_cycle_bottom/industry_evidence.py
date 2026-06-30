"""Industry cycle evidence scoring for GenGe Cycle Bottom Strategy.

The helpers in this module are deliberately data-only. They never fetch live
data, never inspect future rows, and treat manual/template rows as research
material rather than authoritative conclusions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pandas as pd
import yaml


class CyclePhase(str, Enum):
    UNKNOWN = "UNKNOWN"
    DECLINING = "DECLINING"
    BOTTOMING = "BOTTOMING"
    RECOVERING = "RECOVERING"
    EXPANDING = "EXPANDING"
    OVERHEATING = "OVERHEATING"


class EvidenceQuality(str, Enum):
    MISSING = "MISSING"
    MANUAL_TEMPLATE = "MANUAL_TEMPLATE"
    USER_SUPPLIED = "USER_SUPPLIED"
    PROVIDER_DERIVED = "PROVIDER_DERIVED"
    VERIFIED_MULTI_SOURCE = "VERIFIED_MULTI_SOURCE"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceDirection(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class HardLogicLevel(str, Enum):
    NONE = "NONE"
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


QUALITY_RANK = {
    EvidenceQuality.MISSING.value: 0,
    EvidenceQuality.MANUAL_TEMPLATE.value: 1,
    EvidenceQuality.USER_SUPPLIED.value: 2,
    EvidenceQuality.PROVIDER_DERIVED.value: 3,
    EvidenceQuality.VERIFIED_MULTI_SOURCE.value: 4,
}
CONFIDENCE_RANK = {
    ConfidenceLevel.LOW.value: 0,
    ConfidenceLevel.MEDIUM.value: 1,
    ConfidenceLevel.HIGH.value: 2,
}
HARD_LOGIC_RANK = {
    HardLogicLevel.NONE.value: 0,
    HardLogicLevel.WEAK.value: 1,
    HardLogicLevel.MEDIUM.value: 2,
    HardLogicLevel.STRONG.value: 3,
}
DEFAULT_SCHEMA_FRESHNESS_DAYS = 180


@dataclass(frozen=True)
class EvidenceItem:
    evidence_name: str
    evidence_value: str
    evidence_direction: str
    evidence_date: str
    source: str
    source_type: str
    freshness_days: Optional[int]
    weight: float
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndustryEvidence:
    industry: str
    as_of_date: str
    cycle_phase: str
    evidence_score: float
    evidence_quality: str
    evidence_source_type: str
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    positive_evidence_count: int = 0
    negative_evidence_count: int = 0
    neutral_evidence_count: int = 0
    confidence_level: str = ConfidenceLevel.LOW.value
    stale_evidence_count: int = 0
    missing_evidence_fields: List[str] = field(default_factory=list)
    warning_flags: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["evidence_items"] = [item.to_dict() for item in self.evidence_items]
        return data


@dataclass
class CompanyEvidence:
    code: str
    stock_name: str = ""
    industry: str = ""
    as_of_date: str = ""
    evidence_score: float = 50.0
    evidence_quality: str = EvidenceQuality.MISSING.value
    evidence_source_type: str = EvidenceQuality.MISSING.value
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    positive_evidence_count: int = 0
    negative_evidence_count: int = 0
    neutral_evidence_count: int = 0
    confidence_level: str = ConfidenceLevel.LOW.value
    stale_evidence_count: int = 0
    warning_flags: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["evidence_items"] = [item.to_dict() for item in self.evidence_items]
        return data


@dataclass(frozen=True)
class HardLogicResult:
    hard_logic_score: float
    hard_logic_level: str
    warning_flags: Tuple[str, ...] = ()
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_industry_evidence_schema(path: str | Path | None) -> Dict[str, Any]:
    if not path:
        return {}
    schema_path = Path(path)
    if not schema_path.exists():
        raise FileNotFoundError(f"industry evidence schema not found: {schema_path}")
    raw = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    industries = raw.get("industries") or {}
    if not isinstance(industries, dict):
        raise ValueError("industry evidence schema must contain an industries mapping")
    for industry, config in industries.items():
        indicators = (config or {}).get("indicators") or []
        if not isinstance(indicators, list) or len(indicators) < 1:
            raise ValueError(f"industry evidence schema for {industry} must define indicators")
        for indicator in indicators:
            for key in (
                "name",
                "description",
                "direction_rule",
                "positive_condition",
                "negative_condition",
                "source_hint",
                "default_weight",
                "freshness_limit_days",
                "required_or_optional",
            ):
                if key not in indicator:
                    raise ValueError(f"industry evidence indicator {industry}/{indicator.get('name')} missing {key}")
    return raw


def load_evidence_csv(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"evidence CSV not found: {csv_path}")
    return pd.read_csv(csv_path)


def normalize_evidence_source(path: str | Path | None, source_mode: str = "real") -> str:
    if not path:
        return "none"
    lowered = Path(path).name.lower()
    if "template" in lowered or "example" in lowered or "demo" in lowered:
        return "manual_template"
    if source_mode == "fixture":
        return "fixture"
    return "user_supplied"


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return pd.to_datetime(value, errors="coerce").date()
    except Exception:
        return None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _normalize_direction(value: Any) -> str:
    raw = _as_text(value).upper()
    mapping = {
        "+": EvidenceDirection.POSITIVE.value,
        "POS": EvidenceDirection.POSITIVE.value,
        "POSITIVE": EvidenceDirection.POSITIVE.value,
        "利好": EvidenceDirection.POSITIVE.value,
        "-": EvidenceDirection.NEGATIVE.value,
        "NEG": EvidenceDirection.NEGATIVE.value,
        "NEGATIVE": EvidenceDirection.NEGATIVE.value,
        "利空": EvidenceDirection.NEGATIVE.value,
        "0": EvidenceDirection.NEUTRAL.value,
        "NEU": EvidenceDirection.NEUTRAL.value,
        "NEUTRAL": EvidenceDirection.NEUTRAL.value,
        "中性": EvidenceDirection.NEUTRAL.value,
    }
    return mapping.get(raw, EvidenceDirection.NEUTRAL.value)


def _normalize_source_type(value: Any, source: Any = "") -> str:
    raw = _as_text(value).lower()
    source_raw = _as_text(source).lower()
    if raw in {"verified_multi_source", "verified", "multi_source", "multi-source"}:
        return EvidenceQuality.VERIFIED_MULTI_SOURCE.value
    if raw in {"provider_derived", "provider", "akshare", "qstock", "tushare", "baostock"}:
        return EvidenceQuality.PROVIDER_DERIVED.value
    if raw in {"user_supplied", "research_note", "manual_research", "user"}:
        return EvidenceQuality.USER_SUPPLIED.value
    if raw in {"manual_template", "template", "example", "demo"} or source_raw in {"manual_template", "template", "example", "demo"}:
        return EvidenceQuality.MANUAL_TEMPLATE.value
    if raw:
        return EvidenceQuality.USER_SUPPLIED.value
    return EvidenceQuality.MANUAL_TEMPLATE.value if source_raw in {"manual_template", "template", "example"} else EvidenceQuality.USER_SUPPLIED.value


def _industry_schema(schema: Mapping[str, Any] | None, industry: str | None) -> Dict[str, Any]:
    if not schema or not industry:
        return {}
    industries = schema.get("industries") or {}
    if industry in industries:
        return dict(industries[industry] or {})
    aliases = (schema.get("aliases") or {})
    canonical = aliases.get(industry)
    if canonical and canonical in industries:
        merged = dict(industries[canonical] or {})
        merged.setdefault("canonical_industry", canonical)
        return merged
    return {}


def _indicator_map(schema: Mapping[str, Any] | None, industry: str | None) -> Dict[str, Dict[str, Any]]:
    industry_config = _industry_schema(schema, industry)
    indicators = industry_config.get("indicators") or []
    return {str(item.get("name")): dict(item) for item in indicators if item.get("name")}


def _source_quality(source_types: Iterable[str]) -> str:
    types = set(source_types)
    if not types:
        return EvidenceQuality.MISSING.value
    if EvidenceQuality.VERIFIED_MULTI_SOURCE.value in types:
        return EvidenceQuality.VERIFIED_MULTI_SOURCE.value
    if EvidenceQuality.PROVIDER_DERIVED.value in types:
        return EvidenceQuality.PROVIDER_DERIVED.value
    if EvidenceQuality.USER_SUPPLIED.value in types:
        return EvidenceQuality.USER_SUPPLIED.value
    return EvidenceQuality.MANUAL_TEMPLATE.value


def _dominant_source_type(source_types: Iterable[str]) -> str:
    ordered = sorted(set(source_types), key=lambda value: QUALITY_RANK.get(value, 0), reverse=True)
    return ordered[0] if ordered else EvidenceQuality.MISSING.value


def _quality_weight(source_type: str) -> float:
    return {
        EvidenceQuality.MANUAL_TEMPLATE.value: 0.65,
        EvidenceQuality.USER_SUPPLIED.value: 0.85,
        EvidenceQuality.PROVIDER_DERIVED.value: 1.0,
        EvidenceQuality.VERIFIED_MULTI_SOURCE.value: 1.15,
        EvidenceQuality.MISSING.value: 0.0,
    }.get(source_type, 0.8)


def _phase_from_score(score: float, positive: int, negative: int) -> str:
    if score >= 88 and positive >= max(2, negative + 2):
        return CyclePhase.OVERHEATING.value
    if score >= 78 and positive >= max(2, negative + 1):
        return CyclePhase.EXPANDING.value
    if score >= 64 and positive > negative:
        return CyclePhase.RECOVERING.value
    if score >= 54 and positive >= negative and positive > 0:
        return CyclePhase.BOTTOMING.value
    if score <= 42 and negative > positive:
        return CyclePhase.DECLINING.value
    return CyclePhase.UNKNOWN.value


def _confidence(
    *,
    quality: str,
    source_types: Iterable[str],
    total_items: int,
    missing_required: List[str],
    stale_count: int,
    warning_flags: List[str],
) -> str:
    if total_items == 0 or quality == EvidenceQuality.MISSING.value:
        return ConfidenceLevel.LOW.value
    if quality == EvidenceQuality.MANUAL_TEMPLATE.value:
        return ConfidenceLevel.MEDIUM.value if total_items >= 3 and not missing_required else ConfidenceLevel.LOW.value
    if missing_required:
        return ConfidenceLevel.LOW.value
    if stale_count >= max(1, total_items):
        return ConfidenceLevel.LOW.value
    if "evidence_conflict" in warning_flags:
        return ConfidenceLevel.MEDIUM.value
    types = set(source_types)
    if (
        quality in {EvidenceQuality.PROVIDER_DERIVED.value, EvidenceQuality.VERIFIED_MULTI_SOURCE.value}
        and total_items >= 4
        and len(types) >= 2
    ):
        return ConfidenceLevel.HIGH.value
    return ConfidenceLevel.MEDIUM.value


def _rows_as_dataframe(evidence_rows: Any) -> pd.DataFrame:
    if evidence_rows is None:
        return pd.DataFrame()
    if isinstance(evidence_rows, pd.DataFrame):
        return evidence_rows.copy()
    return pd.DataFrame(list(evidence_rows))


def _industry_alias_set(schema: Mapping[str, Any] | None, industry: str) -> set[str]:
    names = {str(industry)}
    if not schema:
        return names
    aliases = schema.get("aliases") or {}
    canonical = aliases.get(industry)
    if canonical:
        names.add(str(canonical))
    for alias, target in aliases.items():
        if str(target) in names:
            names.add(str(alias))
    return names


def _evidence_rows_for_industry(
    evidence_rows: Any,
    industry: str,
    as_of_date: date,
    schema: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    df = _rows_as_dataframe(evidence_rows)
    if df.empty:
        return df
    if "industry" not in df.columns:
        return pd.DataFrame()
    local = df.copy()
    local["industry"] = local["industry"].astype(str)
    local = local[local["industry"].isin(_industry_alias_set(schema, industry))]
    date_column = "evidence_date" if "evidence_date" in local.columns else "date"
    if date_column not in local.columns:
        return pd.DataFrame()
    local["_evidence_date"] = pd.to_datetime(local[date_column], errors="coerce").dt.date
    local = local.dropna(subset=["_evidence_date"])
    local = local[local["_evidence_date"] <= as_of_date].sort_values("_evidence_date")
    return local


def _build_item(
    row: pd.Series,
    *,
    as_of_date: date,
    indicator: Optional[Mapping[str, Any]],
    default_freshness_days: int,
    is_stale: bool,
) -> EvidenceItem:
    evidence_date = row.get("_evidence_date") or _coerce_date(row.get("evidence_date") or row.get("date"))
    freshness_days = (as_of_date - evidence_date).days if evidence_date else None
    source_type = _normalize_source_type(row.get("source_type"), row.get("source"))
    base_weight = row.get("weight")
    try:
        weight = float(base_weight)
    except (TypeError, ValueError):
        weight = float((indicator or {}).get("default_weight") or 1.0)
    if is_stale:
        weight *= 0.35
    weight *= _quality_weight(source_type)
    if freshness_days is not None and freshness_days < 0:
        weight = 0.0
    return EvidenceItem(
        evidence_name=_as_text(row.get("evidence_name") or row.get("name")),
        evidence_value=_as_text(row.get("evidence_value") or row.get("value")),
        evidence_direction=_normalize_direction(row.get("evidence_direction") or row.get("direction")),
        evidence_date=evidence_date.isoformat() if evidence_date else "",
        source=_as_text(row.get("source")),
        source_type=source_type,
        freshness_days=freshness_days,
        weight=round(max(0.0, weight), 4),
        note=_as_text(row.get("note")),
    )


def compute_industry_evidence_score(
    industry: str | None,
    as_of_date: Any,
    evidence_rows: Any,
    schema: Mapping[str, Any] | None = None,
) -> IndustryEvidence:
    target = _coerce_date(as_of_date) or date.today()
    industry_name = str(industry or "").strip()
    if not industry_name:
        return IndustryEvidence(
            industry="",
            as_of_date=target.isoformat(),
            cycle_phase=CyclePhase.UNKNOWN.value,
            evidence_score=50.0,
            evidence_quality=EvidenceQuality.MISSING.value,
            evidence_source_type=EvidenceQuality.MISSING.value,
            confidence_level=ConfidenceLevel.LOW.value,
            missing_evidence_fields=["stock_industry_map"],
            warning_flags=["missing_industry"],
            summary="缺少股票行业映射，行业证据按中性处理。",
        )

    indicators = _indicator_map(schema, industry_name)
    required = {
        name
        for name, item in indicators.items()
        if str(item.get("required_or_optional") or "optional").lower() == "required"
    }
    rows = _evidence_rows_for_industry(evidence_rows, industry_name, target, schema)
    if rows.empty:
        missing = sorted(required) if required else ["industry_evidence"]
        return IndustryEvidence(
            industry=industry_name,
            as_of_date=target.isoformat(),
            cycle_phase=CyclePhase.UNKNOWN.value,
            evidence_score=50.0,
            evidence_quality=EvidenceQuality.MISSING.value,
            evidence_source_type=EvidenceQuality.MISSING.value,
            confidence_level=ConfidenceLevel.LOW.value,
            missing_evidence_fields=missing,
            warning_flags=["missing_industry_evidence"],
            summary=f"{industry_name} 缺少截至 {target.isoformat()} 的行业证据，按中性低置信度处理。",
        )

    items: List[EvidenceItem] = []
    stale_count = 0
    source_types: List[str] = []
    seen_names: set[str] = set()
    directions_by_name: Dict[str, set[str]] = {}
    for _, row in rows.iterrows():
        name = _as_text(row.get("evidence_name") or row.get("name"))
        indicator = indicators.get(name)
        freshness_limit = int((indicator or {}).get("freshness_limit_days") or DEFAULT_SCHEMA_FRESHNESS_DAYS)
        evidence_date = row.get("_evidence_date") or _coerce_date(row.get("evidence_date") or row.get("date"))
        freshness_days = (target - evidence_date).days if evidence_date else None
        stale = bool(freshness_days is None or freshness_days > freshness_limit)
        stale_count += int(stale)
        item = _build_item(
            row,
            as_of_date=target,
            indicator=indicator,
            default_freshness_days=freshness_limit,
            is_stale=stale,
        )
        if not item.evidence_name:
            continue
        items.append(item)
        seen_names.add(item.evidence_name)
        source_types.append(item.source_type)
        directions_by_name.setdefault(item.evidence_name, set()).add(item.evidence_direction)

    positive = sum(1 for item in items if item.evidence_direction == EvidenceDirection.POSITIVE.value)
    negative = sum(1 for item in items if item.evidence_direction == EvidenceDirection.NEGATIVE.value)
    neutral = sum(1 for item in items if item.evidence_direction == EvidenceDirection.NEUTRAL.value)
    score_delta = 0.0
    for item in items:
        if item.evidence_direction == EvidenceDirection.POSITIVE.value:
            score_delta += item.weight * 7.5
        elif item.evidence_direction == EvidenceDirection.NEGATIVE.value:
            score_delta -= item.weight * 9.0
    score = round(max(0.0, min(100.0, 50.0 + score_delta)), 2)
    warning_flags: List[str] = []
    if stale_count:
        warning_flags.append("stale_evidence")
    if any(
        EvidenceDirection.POSITIVE.value in values and EvidenceDirection.NEGATIVE.value in values
        for values in directions_by_name.values()
    ) or (positive > 0 and negative > 0):
        warning_flags.append("evidence_conflict")
    missing_required = sorted(required - seen_names)
    if missing_required:
        warning_flags.append("missing_required_evidence")
    quality = _source_quality(source_types)
    confidence = _confidence(
        quality=quality,
        source_types=source_types,
        total_items=len(items),
        missing_required=missing_required,
        stale_count=stale_count,
        warning_flags=warning_flags,
    )
    phase = _phase_from_score(score, positive, negative)
    if negative > positive and phase in {CyclePhase.RECOVERING.value, CyclePhase.EXPANDING.value, CyclePhase.OVERHEATING.value}:
        phase = CyclePhase.UNKNOWN.value
    summary = (
        f"{industry_name} 行业证据分 {score:.1f}，阶段 {phase}，"
        f"正/负/中性证据 {positive}/{negative}/{neutral}，置信度 {confidence}。"
    )
    if missing_required:
        summary += f" 缺少必需证据：{','.join(missing_required)}。"
    return IndustryEvidence(
        industry=industry_name,
        as_of_date=target.isoformat(),
        cycle_phase=phase,
        evidence_score=score,
        evidence_quality=quality,
        evidence_source_type=_dominant_source_type(source_types),
        evidence_items=items,
        positive_evidence_count=positive,
        negative_evidence_count=negative,
        neutral_evidence_count=neutral,
        confidence_level=confidence,
        stale_evidence_count=stale_count,
        missing_evidence_fields=missing_required,
        warning_flags=sorted(set(warning_flags)),
        summary=summary,
    )


def compute_company_evidence_score(
    code: str,
    as_of_date: Any,
    evidence_rows: Any,
    *,
    stock_name: str = "",
    industry: str = "",
) -> CompanyEvidence:
    target = _coerce_date(as_of_date) or date.today()
    normalized_code = str(code).strip().zfill(6) if str(code).strip().isdigit() else str(code).strip()
    df = _rows_as_dataframe(evidence_rows)
    if df.empty or "code" not in df.columns:
        return CompanyEvidence(
            code=normalized_code,
            stock_name=stock_name,
            industry=industry,
            as_of_date=target.isoformat(),
            evidence_score=50.0,
            evidence_quality=EvidenceQuality.MISSING.value,
            evidence_source_type=EvidenceQuality.MISSING.value,
            confidence_level=ConfidenceLevel.LOW.value,
            warning_flags=["missing_company_evidence"],
            summary="缺少公司层证据，按中性低置信度处理。",
        )
    local = df.copy()
    local["code"] = local["code"].astype(str).str.zfill(6)
    local = local[local["code"] == normalized_code]
    date_column = "evidence_date" if "evidence_date" in local.columns else "date"
    if date_column not in local.columns:
        return CompanyEvidence(
            code=normalized_code,
            stock_name=stock_name,
            industry=industry,
            as_of_date=target.isoformat(),
            evidence_score=50.0,
            evidence_quality=EvidenceQuality.MISSING.value,
            evidence_source_type=EvidenceQuality.MISSING.value,
            confidence_level=ConfidenceLevel.LOW.value,
            warning_flags=["missing_company_evidence_date"],
            summary="公司证据缺少日期字段，按中性低置信度处理。",
        )
    local["_evidence_date"] = pd.to_datetime(local[date_column], errors="coerce").dt.date
    local = local.dropna(subset=["_evidence_date"])
    local = local[local["_evidence_date"] <= target].sort_values("_evidence_date")
    if local.empty:
        return CompanyEvidence(
            code=normalized_code,
            stock_name=stock_name,
            industry=industry,
            as_of_date=target.isoformat(),
            evidence_score=50.0,
            evidence_quality=EvidenceQuality.MISSING.value,
            evidence_source_type=EvidenceQuality.MISSING.value,
            confidence_level=ConfidenceLevel.LOW.value,
            warning_flags=["missing_company_evidence"],
            summary="缺少截至评估日的公司层证据，按中性低置信度处理。",
        )
    items: List[EvidenceItem] = []
    source_types: List[str] = []
    stale_count = 0
    directions_by_name: Dict[str, set[str]] = {}
    for _, row in local.iterrows():
        freshness_days = (target - row["_evidence_date"]).days
        stale = freshness_days > DEFAULT_SCHEMA_FRESHNESS_DAYS
        stale_count += int(stale)
        item = _build_item(
            row,
            as_of_date=target,
            indicator={"default_weight": 1.0, "freshness_limit_days": DEFAULT_SCHEMA_FRESHNESS_DAYS},
            default_freshness_days=DEFAULT_SCHEMA_FRESHNESS_DAYS,
            is_stale=stale,
        )
        if not item.evidence_name:
            continue
        items.append(item)
        source_types.append(item.source_type)
        directions_by_name.setdefault(item.evidence_name, set()).add(item.evidence_direction)

    positive = sum(1 for item in items if item.evidence_direction == EvidenceDirection.POSITIVE.value)
    negative = sum(1 for item in items if item.evidence_direction == EvidenceDirection.NEGATIVE.value)
    neutral = sum(1 for item in items if item.evidence_direction == EvidenceDirection.NEUTRAL.value)
    delta = sum(item.weight * 7.0 for item in items if item.evidence_direction == EvidenceDirection.POSITIVE.value)
    delta -= sum(item.weight * 9.0 for item in items if item.evidence_direction == EvidenceDirection.NEGATIVE.value)
    score = round(max(0.0, min(100.0, 50.0 + delta)), 2)
    flags: List[str] = []
    if stale_count:
        flags.append("stale_company_evidence")
    if any(
        EvidenceDirection.POSITIVE.value in values and EvidenceDirection.NEGATIVE.value in values
        for values in directions_by_name.values()
    ) or (positive > 0 and negative > 0):
        flags.append("company_evidence_conflict")
    quality = _source_quality(source_types)
    confidence = _confidence(
        quality=quality,
        source_types=source_types,
        total_items=len(items),
        missing_required=[],
        stale_count=stale_count,
        warning_flags=flags,
    )
    summary = f"公司证据分 {score:.1f}，正/负/中性证据 {positive}/{negative}/{neutral}，置信度 {confidence}。"
    return CompanyEvidence(
        code=normalized_code,
        stock_name=stock_name,
        industry=industry,
        as_of_date=target.isoformat(),
        evidence_score=score,
        evidence_quality=quality,
        evidence_source_type=_dominant_source_type(source_types),
        evidence_items=items,
        positive_evidence_count=positive,
        negative_evidence_count=negative,
        neutral_evidence_count=neutral,
        confidence_level=confidence,
        stale_evidence_count=stale_count,
        warning_flags=sorted(set(flags)),
        summary=summary,
    )


def compute_hard_logic_level(
    industry_evidence: IndustryEvidence,
    company_evidence: Optional[CompanyEvidence] = None,
) -> HardLogicResult:
    company = company_evidence or CompanyEvidence(code="", as_of_date=industry_evidence.as_of_date)
    warning_flags: List[str] = []
    score = industry_evidence.evidence_score * 0.75 + company.evidence_score * 0.25
    has_industry_evidence = industry_evidence.evidence_quality != EvidenceQuality.MISSING.value
    has_company_evidence = company.evidence_quality != EvidenceQuality.MISSING.value
    negative_industry = (
        industry_evidence.negative_evidence_count > industry_evidence.positive_evidence_count
        or industry_evidence.cycle_phase == CyclePhase.DECLINING.value
        or industry_evidence.evidence_score < 45
    )
    negative_company = company.negative_evidence_count > company.positive_evidence_count and company.evidence_quality != EvidenceQuality.MISSING.value
    if negative_industry:
        warning_flags.append("negative_industry_evidence")
    if negative_company:
        warning_flags.append("negative_company_evidence")
    if industry_evidence.stale_evidence_count >= max(1, len(industry_evidence.evidence_items)):
        warning_flags.append("stale_evidence_blocks_strong")
    if industry_evidence.evidence_quality == EvidenceQuality.MANUAL_TEMPLATE.value:
        warning_flags.append("manual_template_caps_hard_logic")
    if not has_industry_evidence and not has_company_evidence:
        return HardLogicResult(
            hard_logic_score=50.0,
            hard_logic_level=HardLogicLevel.NONE.value,
            warning_flags=("missing_evidence_blocks_hard_logic",),
            summary="缺少行业和公司证据，硬逻辑等级为 NONE。",
        )
    if negative_industry or negative_company:
        return HardLogicResult(
            hard_logic_score=round(min(score, 49.0), 2),
            hard_logic_level=HardLogicLevel.WEAK.value,
            warning_flags=tuple(sorted(set(warning_flags))),
            summary="存在负向行业或公司证据，硬逻辑最多为 WEAK。",
        )
    phase_ok = industry_evidence.cycle_phase in {CyclePhase.BOTTOMING.value, CyclePhase.RECOVERING.value, CyclePhase.EXPANDING.value}
    evidence_positive = industry_evidence.positive_evidence_count > industry_evidence.negative_evidence_count
    if phase_ok and evidence_positive and industry_evidence.evidence_score >= 58:
        level = HardLogicLevel.MEDIUM.value
    elif score >= 55 and (has_industry_evidence or has_company_evidence):
        level = HardLogicLevel.WEAK.value
    else:
        level = HardLogicLevel.NONE.value
    can_strong = (
        level == HardLogicLevel.MEDIUM.value
        and industry_evidence.evidence_score >= 68
        and company.evidence_score >= 62
        and (has_industry_evidence or has_company_evidence)
        and industry_evidence.evidence_quality not in {EvidenceQuality.MANUAL_TEMPLATE.value, EvidenceQuality.MISSING.value}
        and industry_evidence.confidence_level in {ConfidenceLevel.MEDIUM.value, ConfidenceLevel.HIGH.value}
        and industry_evidence.stale_evidence_count == 0
        and "evidence_conflict" not in industry_evidence.warning_flags
    )
    if can_strong:
        level = HardLogicLevel.STRONG.value
    summary = f"硬逻辑分 {score:.1f}，等级 {level}；行业证据 {industry_evidence.evidence_quality}，公司证据 {company.evidence_quality}。"
    return HardLogicResult(
        hard_logic_score=round(max(0.0, min(100.0, score)), 2),
        hard_logic_level=level,
        warning_flags=tuple(sorted(set(warning_flags))),
        summary=summary,
    )


def hard_logic_meets_minimum(level: str, minimum: str) -> bool:
    return HARD_LOGIC_RANK.get(str(level or "").upper(), 0) >= HARD_LOGIC_RANK.get(str(minimum or "MEDIUM").upper(), 2)
