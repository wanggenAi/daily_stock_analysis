"""Point-in-time reviewed insurance embedded-value disclosure inputs.

The registry contains issuer disclosures that may be consumed only after their
public ``known_at`` date and while they remain inside the configured freshness
window.  It is deliberately evidence-only: it cannot create Formal BUY
eligibility or an automatic trade signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


_ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
DEFAULT_MAX_AGE_DAYS = 365


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except Exception as exc:
        raise ValueError(f"invalid {field}") from exc


def _positive(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _optional_positive(value: Any, field: str) -> float | None:
    if value in (None, ""):
        return None
    return _positive(value, field)


@dataclass(frozen=True)
class InsuranceEmbeddedValueInput:
    input_id: str
    code: str
    stock_name: str
    known_at: date
    evidence_as_of: date
    report_year: int
    currency: str
    unit: str
    embedded_value: float
    normalized_annual_nbv: float
    embedded_value_scope: str
    nbv_scope: str
    confidence: str
    evidence_refs: tuple[str, ...]
    source_name: str = ""
    source_url: str = ""
    embedded_value_per_share: float | None = None
    max_age_days: int = DEFAULT_MAX_AGE_DAYS

    def freshness_days(self, as_of: date) -> int:
        return (as_of - self.known_at).days

    def to_dict(self, *, as_of: date | None = None) -> dict[str, Any]:
        freshness_days = "" if as_of is None else self.freshness_days(as_of)
        return {
            "input_id": self.input_id,
            "code": self.code,
            "stock_name": self.stock_name,
            "known_at": self.known_at.isoformat(),
            "evidence_as_of": self.evidence_as_of.isoformat(),
            "report_year": self.report_year,
            "currency": self.currency,
            "unit": self.unit,
            "embedded_value": self.embedded_value,
            "normalized_annual_nbv": self.normalized_annual_nbv,
            "embedded_value_scope": self.embedded_value_scope,
            "nbv_scope": self.nbv_scope,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
            "source_name": self.source_name,
            "source_url": self.source_url,
            "embedded_value_per_share": (
                "" if self.embedded_value_per_share is None else self.embedded_value_per_share
            ),
            "freshness_days": freshness_days,
            "max_age_days": self.max_age_days,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


@dataclass(frozen=True)
class InsuranceInputResolution:
    status: str
    input: InsuranceEmbeddedValueInput | None
    as_of: date

    @property
    def execution_eligible(self) -> bool:
        return self.status == "FOUND" and self.input is not None

    @property
    def evidence_status(self) -> str:
        return {
            "FOUND": "VALID",
            "NOT_FOUND": "MISSING",
            "NOT_YET_KNOWN": "NOT_YET_KNOWN",
            "LOW_CONFIDENCE": "LOW_CONFIDENCE",
            "STALE": "STALE",
        }.get(self.status, "INVALID")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_status": self.evidence_status,
            "input": None if self.input is None else self.input.to_dict(as_of=self.as_of),
            "execution_eligible": self.execution_eligible,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


class InsuranceEmbeddedValueInputRepository:
    def __init__(self, inputs: tuple[InsuranceEmbeddedValueInput, ...]):
        self.inputs = tuple(sorted(inputs, key=lambda item: (item.code, item.known_at)))
        seen: set[tuple[str, date]] = set()
        for item in self.inputs:
            key = (item.code, item.known_at)
            if key in seen:
                raise ValueError("duplicate insurance input known_at")
            seen.add(key)

    def resolve(self, code: str, *, as_of: date) -> InsuranceInputResolution:
        normalized = _normalize_code(code)
        matching = [item for item in self.inputs if item.code == normalized]
        if not matching:
            return InsuranceInputResolution("NOT_FOUND", None, as_of)
        known = [item for item in matching if item.known_at <= as_of]
        if not known:
            return InsuranceInputResolution("NOT_YET_KNOWN", None, as_of)
        selected = sorted(known, key=lambda item: item.known_at)[-1]
        if selected.confidence != "HIGH":
            return InsuranceInputResolution("LOW_CONFIDENCE", selected, as_of)
        if selected.freshness_days(as_of) > selected.max_age_days:
            return InsuranceInputResolution("STALE", selected, as_of)
        return InsuranceInputResolution("FOUND", selected, as_of)


def load_insurance_embedded_value_input_repository(
    path: str | Path = "config/insurance_embedded_value_inputs.yaml",
) -> InsuranceEmbeddedValueInputRepository:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_inputs = payload.get("inputs") or []
    if not isinstance(raw_inputs, list):
        raise ValueError("insurance inputs must be a list")
    default_max_age_days = int(payload.get("default_max_age_days") or DEFAULT_MAX_AGE_DAYS)
    if default_max_age_days <= 0:
        raise ValueError("default_max_age_days must be positive")

    parsed: list[InsuranceEmbeddedValueInput] = []
    for raw in raw_inputs:
        if not isinstance(raw, dict):
            raise ValueError("insurance input must be a mapping")
        known_at = _date(raw.get("known_at"), "known_at")
        evidence_as_of = _date(raw.get("evidence_as_of"), "evidence_as_of")
        if evidence_as_of > known_at:
            raise ValueError("evidence_as_of cannot be after known_at")
        confidence = str(raw.get("confidence") or "").strip().upper()
        if confidence not in _ALLOWED_CONFIDENCE:
            raise ValueError("invalid insurance input confidence")
        report_year = int(raw.get("report_year"))
        if report_year != evidence_as_of.year:
            raise ValueError("report_year must match evidence_as_of year")
        currency = str(raw.get("currency") or "").strip().upper()
        unit = str(raw.get("unit") or "").strip().lower()
        if currency != "CNY" or unit != "million":
            raise ValueError("insurance input unit must be CNY million")
        input_id = str(raw.get("input_id") or "").strip()
        code = _normalize_code(raw.get("code"))
        if not input_id or not code:
            raise ValueError("insurance input id and code are required")
        max_age_days = int(raw.get("max_age_days") or default_max_age_days)
        if max_age_days <= 0:
            raise ValueError("max_age_days must be positive")
        parsed.append(
            InsuranceEmbeddedValueInput(
                input_id=input_id,
                code=code,
                stock_name=str(raw.get("stock_name") or "").strip(),
                known_at=known_at,
                evidence_as_of=evidence_as_of,
                report_year=report_year,
                currency=currency,
                unit=unit,
                embedded_value=_positive(raw.get("embedded_value"), "embedded_value"),
                normalized_annual_nbv=_positive(
                    raw.get("normalized_annual_nbv"), "normalized_annual_nbv"
                ),
                embedded_value_scope=str(raw.get("embedded_value_scope") or "").strip(),
                nbv_scope=str(raw.get("nbv_scope") or "").strip(),
                confidence=confidence,
                evidence_refs=tuple(str(item) for item in (raw.get("evidence_refs") or [])),
                source_name=str(raw.get("source_name") or "").strip(),
                source_url=str(raw.get("source_url") or "").strip(),
                embedded_value_per_share=_optional_positive(
                    raw.get("embedded_value_per_share"), "embedded_value_per_share"
                ),
                max_age_days=max_age_days,
            )
        )
    return InsuranceEmbeddedValueInputRepository(tuple(parsed))
