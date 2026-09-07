"""Fail-closed insurer-specific valuation recovery for V3.1.1 production.

This module is intentionally narrow.  It resolves issuer-reviewed, point-in-time
insurance evidence for securities that are already present in the production
surface (including confirmed holdings).  It does not expand the production
universe, fabricate missing evidence, grant Formal BUY eligibility, or place
orders.

The conservative insurer base value is disclosed embedded value per share.  It
excludes any positive franchise multiple for future new business.  Sustainable
growth is the lower of issuer-disclosed Life & Health NBV YoY growth and group
attributable operating-profit YoY growth.  One-off net-profit growth is not used.
Because this typed path has not been promoted as a candidate BUY model, valid
insurer evidence is capped at MEDIUM valuation confidence and candidate BUY is
explicitly disabled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from .insurance_embedded_value_inputs import (
    InsuranceEmbeddedValueInput,
    load_insurance_embedded_value_input_repository,
)
from .selection_framework_v31 import assess_v31, exit_action_from_valuation
from .selection_framework_v311 import (
    ConfidenceAssessment,
    V311Decision,
    ValuationConfidence,
)

DEFAULT_EV_CONFIG = Path("config/insurance_embedded_value_inputs.yaml")
DEFAULT_GROWTH_CONFIG = Path("config/insurance_growth_inputs.yaml")
GROWTH_CAP = 0.20
SELL_ACTIONS = frozenset({"REDUCE_25", "REDUCE_50", "CORE_ONLY"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _iso_date(value: Any) -> date | None:
    raw = _text(value)
    if len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _as_of(data: Mapping[str, Any]) -> date | None:
    for field in ("decision_date", "date", "price_date"):
        parsed = _iso_date(data.get(field))
        if parsed is not None:
            return parsed
    return None


def _current_price(data: Mapping[str, Any]) -> float | None:
    for field in ("v31_current_price", "raw_latest_close", "current_price", "close"):
        value = _finite(data.get(field))
        if value is not None and value > 0:
            return value
    return None


def _has_position(data: Mapping[str, Any]) -> bool:
    if _truthy(data.get("v311_has_position")) or _truthy(data.get("v32_has_position")):
        return True
    value = _finite(data.get("current_position_fraction"))
    return value is not None and value > 0


@dataclass(frozen=True)
class InsurerGrowthInput:
    input_id: str
    code: str
    known_at: date
    evidence_as_of: date
    confidence: str
    max_age_days: int
    nbv_growth_yoy: float
    operating_profit_growth_yoy: float
    source_name: str
    source_url: str
    evidence_refs: tuple[str, ...]
    attributable_equity_million: float | None = None
    interim_dividend_per_share: float | None = None


@dataclass(frozen=True)
class InsurerTypedEvidence:
    status: str
    reason_codes: tuple[str, ...]
    code: str
    as_of: date | None
    current_price: float | None = None
    neutral_value: float | None = None
    realistic_growth: float | None = None
    ev_input: InsuranceEmbeddedValueInput | None = None
    growth_input: InsurerGrowthInput | None = None

    @property
    def ready(self) -> bool:
        return self.status == "READY"


def _load_growth_inputs(path: str | Path = DEFAULT_GROWTH_CONFIG) -> tuple[InsurerGrowthInput, ...]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    default_max_age = int(payload.get("default_max_age_days") or 365)
    rows = payload.get("inputs") or []
    if not isinstance(rows, list):
        raise ValueError("insurance growth inputs must be a list")
    result: list[InsurerGrowthInput] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("insurance growth input must be a mapping")
        code = _code(raw.get("code"))
        known_at = _iso_date(raw.get("known_at"))
        evidence_as_of = _iso_date(raw.get("evidence_as_of"))
        confidence = _text(raw.get("confidence")).upper()
        nbv = _finite(raw.get("nbv_growth_yoy"))
        opat = _finite(raw.get("operating_profit_growth_yoy"))
        max_age = int(raw.get("max_age_days") or default_max_age)
        if not code or known_at is None or evidence_as_of is None:
            raise ValueError("insurance growth code/dates are required")
        if evidence_as_of > known_at:
            raise ValueError("insurance growth evidence_as_of cannot exceed known_at")
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError("invalid insurance growth confidence")
        if nbv is None or opat is None:
            raise ValueError("insurance growth metrics must be finite")
        if max_age <= 0:
            raise ValueError("insurance growth max_age_days must be positive")
        result.append(
            InsurerGrowthInput(
                input_id=_text(raw.get("input_id")),
                code=code,
                known_at=known_at,
                evidence_as_of=evidence_as_of,
                confidence=confidence,
                max_age_days=max_age,
                nbv_growth_yoy=nbv,
                operating_profit_growth_yoy=opat,
                source_name=_text(raw.get("source_name")),
                source_url=_text(raw.get("source_url")),
                evidence_refs=tuple(str(item) for item in (raw.get("evidence_refs") or [])),
                attributable_equity_million=_finite(raw.get("attributable_equity_million")),
                interim_dividend_per_share=_finite(raw.get("interim_dividend_per_share")),
            )
        )
    return tuple(sorted(result, key=lambda item: (item.code, item.known_at)))


def _resolve_growth(code: str, as_of: date, path: str | Path) -> tuple[str, InsurerGrowthInput | None]:
    matching = [item for item in _load_growth_inputs(path) if item.code == code]
    if not matching:
        return "NOT_FOUND", None
    known = [item for item in matching if item.known_at <= as_of]
    if not known:
        return "NOT_YET_KNOWN", None
    selected = known[-1]
    if selected.confidence != "HIGH":
        return "LOW_CONFIDENCE", selected
    if (as_of - selected.known_at).days > selected.max_age_days:
        return "STALE", selected
    return "FOUND", selected


def is_insurer_typed_input(
    data: Mapping[str, Any],
    *,
    ev_config: str | Path = DEFAULT_EV_CONFIG,
) -> bool:
    code = _code(data.get("code") or data.get("stock_code") or data.get("symbol"))
    if not code:
        return False
    try:
        repository = load_insurance_embedded_value_input_repository(ev_config)
    except (OSError, ValueError):
        return False
    return any(item.code == code for item in repository.inputs)


def _status_reason(prefix: str, status: str) -> str:
    return {
        "NOT_FOUND": f"{prefix}_MISSING",
        "NOT_YET_KNOWN": f"{prefix}_NOT_YET_KNOWN",
        "LOW_CONFIDENCE": f"{prefix}_AUTHORITY_INSUFFICIENT",
        "STALE": f"{prefix}_STALE",
    }.get(status, f"{prefix}_INVALID")


def resolve_insurer_typed_evidence(
    data: Mapping[str, Any],
    *,
    ev_config: str | Path = DEFAULT_EV_CONFIG,
    growth_config: str | Path = DEFAULT_GROWTH_CONFIG,
) -> InsurerTypedEvidence:
    code = _code(data.get("code") or data.get("stock_code") or data.get("symbol"))
    as_of = _as_of(data)
    reasons: list[str] = []
    if not code:
        return InsurerTypedEvidence("INVALID", ("INSURER_CODE_MISSING",), code, as_of)
    if as_of is None:
        return InsurerTypedEvidence("INVALID", ("INSURER_DECISION_DATE_MISSING",), code, None)

    try:
        ev_resolution = load_insurance_embedded_value_input_repository(ev_config).resolve(code, as_of=as_of)
    except (OSError, ValueError) as exc:
        return InsurerTypedEvidence(
            "INVALID", (f"INSURER_EV_REGISTRY_INVALID:{type(exc).__name__}",), code, as_of
        )
    if not ev_resolution.execution_eligible or ev_resolution.input is None:
        reasons.append(_status_reason("INSURER_EMBEDDED_VALUE", ev_resolution.status))
        return InsurerTypedEvidence("INVALID", tuple(reasons), code, as_of)
    ev = ev_resolution.input
    neutral = ev.embedded_value_per_share
    if neutral is None or neutral <= 0:
        reasons.append("INSURER_EMBEDDED_VALUE_PER_SHARE_MISSING")

    try:
        growth_status, growth = _resolve_growth(code, as_of, growth_config)
    except (OSError, ValueError) as exc:
        return InsurerTypedEvidence(
            "INVALID", (f"INSURER_GROWTH_REGISTRY_INVALID:{type(exc).__name__}",), code, as_of,
            neutral_value=neutral, ev_input=ev,
        )
    if growth_status != "FOUND" or growth is None:
        reasons.append(_status_reason("INSURER_GROWTH_EVIDENCE", growth_status))

    current = _current_price(data)
    if current is None:
        reasons.append("CURRENT_PRICE_INVALID")
    price_date = _iso_date(data.get("price_date"))
    if price_date is None:
        reasons.append("PRICE_DATE_UNVERIFIED")
    elif price_date > as_of:
        reasons.append("PRICE_DATE_AFTER_DECISION_DATE")

    realistic: float | None = None
    if growth is not None:
        supportable = min(growth.nbv_growth_yoy, growth.operating_profit_growth_yoy)
        realistic = max(0.0, min(float(supportable), GROWTH_CAP))

    if reasons:
        return InsurerTypedEvidence(
            "INVALID", tuple(dict.fromkeys(reasons)), code, as_of,
            current_price=current, neutral_value=neutral, realistic_growth=realistic,
            ev_input=ev, growth_input=growth,
        )
    return InsurerTypedEvidence(
        "READY",
        (
            "INSURER_TYPED_EVIDENCE_VALID",
            "INSURER_DISCLOSED_EV_REFERENCE_BASE",
            "INSURER_GROWTH_CONSERVATIVE_MIN_NBV_OPAT",
            "TYPED_INSURER_FORMAL_BUY_DISABLED",
        ),
        code, as_of, current_price=current, neutral_value=neutral,
        realistic_growth=realistic, ev_input=ev, growth_input=growth,
    )


def assess_insurer_valuation_confidence_v311(data: Mapping[str, Any]) -> ConfidenceAssessment:
    evidence = resolve_insurer_typed_evidence(data)
    if not evidence.ready:
        return ConfidenceAssessment(ValuationConfidence.INVALID, evidence.reason_codes)
    # Deliberately capped at MEDIUM: EV/share is a conservative disclosed base
    # anchor, not a full appraisal value with an analyst-supplied NBV franchise multiple.
    return ConfidenceAssessment(ValuationConfidence.MEDIUM, evidence.reason_codes)


def decide_insurer_v311(data: Mapping[str, Any]) -> V311Decision:
    evidence = resolve_insurer_typed_evidence(data)
    confidence = assess_insurer_valuation_confidence_v311(data)
    v31 = assess_v31(data)

    def result(action: str, target: float | None, reasons: list[str]) -> V311Decision:
        current = evidence.current_price
        neutral = evidence.neutral_value
        ratio = current / neutral if current and neutral and neutral > 0 else None
        return V311Decision(
            action=action,
            target_position_fraction=target,
            valuation_confidence=confidence.level,
            reason_codes=tuple(reasons),
            normalized_earnings=None,
            realistic_growth=evidence.realistic_growth,
            market_implied_growth=None,
            expectation_gap=None,
            neutral_value=neutral,
            current_price=current,
            price_to_neutral=ratio,
        )

    if v31.hard_gate_failures:
        return result("EXIT", 0.0, ["HARD_GATE_FAIL", *v31.hard_gate_failures])
    if confidence.level is ValuationConfidence.INVALID:
        return result("HOLD_REVIEW", None, ["VALUATION_CONFIDENCE_INVALID", *confidence.reason_codes])

    action, reason, target = exit_action_from_valuation(
        current_price=evidence.current_price,
        neutral_value=evidence.neutral_value,
        hard_gate_failures=(),
    )
    has_position = _has_position(data)
    if not has_position:
        return result("WAIT", 0.0, ["TYPED_INSURER_FORMAL_BUY_NOT_PROMOTED", reason])
    if action in SELL_ACTIONS:
        return result(action, target, ["V31_TYPED_INSURER_VALUATION_SELL", action, reason])
    if action == "HOLD_NO_ADD":
        return result("HOLD_NO_ADD", 1.0, ["PRICE_AT_OR_ABOVE_INSURER_EV_BASE", reason])
    if action == "HOLD_REVIEW":
        return result("HOLD_REVIEW", None, ["INSURER_VALUATION_INCOMPLETE", reason])
    return result("HOLD", 1.0, ["INSURER_EVIDENCE_VALID", "NO_ACTION_THRESHOLD", reason])


def insurer_typed_payload_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    evidence = resolve_insurer_typed_evidence(data)
    ev = evidence.ev_input
    growth = evidence.growth_input
    return {
        "typed_valuation_model": "insurance_embedded_value_conservative_base",
        "typed_valuation_status": evidence.status,
        "typed_valuation_missing_or_invalid_inputs": ";".join(evidence.reason_codes)
        if not evidence.ready else "",
        "typed_valuation_reference_kind": "DISCLOSED_EMBEDDED_VALUE",
        "typed_neutral_value_method": "DISCLOSED_EV_PER_SHARE_NO_FRANCHISE_MULTIPLE",
        "typed_realistic_growth_method": "MIN_NBV_YOY_OPAT_YOY_CLIPPED_0_20",
        "typed_formal_buy_eligible": False,
        "typed_formal_action_recomputed": True,
        "insurer_ev_input_id": ev.input_id if ev else "",
        "insurer_ev_known_at": ev.known_at.isoformat() if ev else "",
        "insurer_ev_evidence_as_of": ev.evidence_as_of.isoformat() if ev else "",
        "insurer_ev_source_name": ev.source_name if ev else "",
        "insurer_ev_source_url": ev.source_url if ev else "",
        "insurer_growth_input_id": growth.input_id if growth else "",
        "insurer_growth_known_at": growth.known_at.isoformat() if growth else "",
        "insurer_growth_evidence_as_of": growth.evidence_as_of.isoformat() if growth else "",
        "insurer_growth_source_name": growth.source_name if growth else "",
        "insurer_growth_source_url": growth.source_url if growth else "",
        "insurer_nbv_growth_yoy": growth.nbv_growth_yoy if growth else None,
        "insurer_operating_profit_growth_yoy": growth.operating_profit_growth_yoy if growth else None,
        "insurer_realistic_growth": evidence.realistic_growth,
        "insurer_attributable_equity_million": growth.attributable_equity_million if growth else None,
        "insurer_interim_dividend_per_share": growth.interim_dividend_per_share if growth else None,
        "no_auto_trade": True,
    }
