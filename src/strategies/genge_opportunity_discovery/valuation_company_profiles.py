"""Point-in-time company valuation profiles for research-model routing.

Company-cycle evidence answers "how is the business doing now?". A valuation
profile answers the separate structural question "what kind of business is this
and which valuation families are admissible?". Keeping those concepts apart
prevents a temporary cycle signal from silently changing a company's economic
archetype.

Profiles are append-only, versioned research metadata. Resolution is strictly
point-in-time: a profile can influence routing only when ``known_at <= as_of``.
Every profile also has a mandatory ``review_after`` date: stale or low-confidence
profiles remain visible for audit but their routing inputs are suppressed. This
module never creates a Formal BUY or an automatic trade signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import (
    CompanyArchetype,
    DEFAULT_VALUATION_STRATEGY_REGISTRY,
    ValuationStrategyRegistry,
)


PROFILE_SCHEMA_VERSION = 1
PROFILE_CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
PROFILE_ROUTING_CONFIDENCE_CAP = {"MEDIUM": 0.80, "HIGH": 1.00}
ROUTING_MIN_CONFIDENCE = "MEDIUM"


def normalize_profile_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            text = text[len(prefix) :]
            break
    if not text.isdigit():
        raise ValueError(f"invalid valuation profile stock code: {value!r}")
    normalized = text.zfill(6)
    if len(normalized) != 6:
        raise ValueError(f"invalid valuation profile stock code: {value!r}")
    return normalized


def _date_value(value: Any, *, field_name: str) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"valuation profile {field_name} is required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"valuation profile {field_name} must be ISO YYYY-MM-DD: {text!r}"
        ) from exc


def _string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = value.replace("；", ";").replace("，", ",").replace("|", ",")
        parts: list[str] = []
        for segment in raw.split(";"):
            parts.extend(segment.split(","))
        items = [item.strip() for item in parts if item.strip()]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise ValueError(f"valuation profile {field_name} must be a string or list")
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True)
class CompanyValuationProfile:
    profile_id: str
    code: str
    stock_name: str
    known_at: date
    evidence_as_of: date
    review_after: date
    confidence: str
    business_tags: tuple[str, ...]
    archetype_hints: tuple[CompanyArchetype, ...]
    disabled_strategy_ids: tuple[str, ...]
    rationale: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "code": self.code,
            "stock_name": self.stock_name,
            "known_at": self.known_at.isoformat(),
            "evidence_as_of": self.evidence_as_of.isoformat(),
            "review_after": self.review_after.isoformat(),
            "confidence": self.confidence,
            "business_tags": list(self.business_tags),
            "archetype_hints": [item.value for item in self.archetype_hints],
            "disabled_strategy_ids": list(self.disabled_strategy_ids),
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class CompanyValuationProfileResolution:
    code: str
    as_of: date
    status: str
    profile: CompanyValuationProfile | None
    reasons: tuple[str, ...]

    @property
    def routing_eligible(self) -> bool:
        return self.status == "FOUND" and self.profile is not None

    @property
    def routing_business_tags(self) -> tuple[str, ...]:
        if not self.routing_eligible or self.profile is None:
            return ()
        return self.profile.business_tags

    @property
    def routing_archetype_hints(self) -> tuple[str, ...]:
        if not self.routing_eligible or self.profile is None:
            return ()
        return tuple(item.value for item in self.profile.archetype_hints)

    @property
    def routing_disabled_strategy_ids(self) -> tuple[str, ...]:
        if not self.routing_eligible or self.profile is None:
            return ()
        return self.profile.disabled_strategy_ids

    @property
    def routing_confidence_cap(self) -> float:
        if not self.routing_eligible or self.profile is None:
            return 0.0
        return PROFILE_ROUTING_CONFIDENCE_CAP[self.profile.confidence]

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "as_of": self.as_of.isoformat(),
            "status": self.status,
            "routing_eligible": self.routing_eligible,
            "routing_confidence_cap": self.routing_confidence_cap,
            "reasons": list(self.reasons),
            "profile": self.profile.to_dict() if self.profile else None,
            "routing_business_tags": list(self.routing_business_tags),
            "routing_archetype_hints": list(self.routing_archetype_hints),
            "routing_disabled_strategy_ids": list(
                self.routing_disabled_strategy_ids
            ),
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


class CompanyValuationProfileRepository:
    """Immutable point-in-time repository of versioned company profiles."""

    def __init__(self, profiles: Iterable[CompanyValuationProfile]):
        ordered = tuple(
            sorted(
                profiles,
                key=lambda item: (item.code, item.known_at, item.profile_id),
            )
        )
        ids: set[str] = set()
        code_dates: set[tuple[str, date]] = set()
        by_code: dict[str, list[CompanyValuationProfile]] = {}
        for profile in ordered:
            if profile.profile_id in ids:
                raise ValueError(
                    f"duplicate valuation profile_id: {profile.profile_id}"
                )
            ids.add(profile.profile_id)
            key = (profile.code, profile.known_at)
            if key in code_dates:
                raise ValueError(
                    "duplicate valuation profile known_at for code: "
                    f"{profile.code} {profile.known_at.isoformat()}"
                )
            code_dates.add(key)
            by_code.setdefault(profile.code, []).append(profile)
        self._profiles = ordered
        self._by_code = {code: tuple(items) for code, items in by_code.items()}

    @property
    def profiles(self) -> tuple[CompanyValuationProfile, ...]:
        return self._profiles

    def resolve(
        self,
        code: Any,
        *,
        as_of: date,
    ) -> CompanyValuationProfileResolution:
        normalized = normalize_profile_code(code)
        versions = self._by_code.get(normalized, ())
        if not versions:
            return CompanyValuationProfileResolution(
                normalized,
                as_of,
                "NOT_FOUND",
                None,
                ("no_company_valuation_profile",),
            )

        known = [profile for profile in versions if profile.known_at <= as_of]
        if not known:
            return CompanyValuationProfileResolution(
                normalized,
                as_of,
                "NOT_YET_KNOWN",
                None,
                ("all_company_profiles_are_future_knowledge",),
            )

        profile = known[-1]
        if as_of > profile.review_after:
            return CompanyValuationProfileResolution(
                normalized,
                as_of,
                "STALE",
                profile,
                ("company_valuation_profile_review_expired",),
            )
        if PROFILE_CONFIDENCE_RANK[profile.confidence] < PROFILE_CONFIDENCE_RANK[
            ROUTING_MIN_CONFIDENCE
        ]:
            return CompanyValuationProfileResolution(
                normalized,
                as_of,
                "LOW_CONFIDENCE",
                profile,
                ("company_valuation_profile_below_routing_confidence",),
            )
        return CompanyValuationProfileResolution(
            normalized,
            as_of,
            "FOUND",
            profile,
            ("point_in_time_company_valuation_profile",),
        )


def _parse_profile(
    raw: Any,
    *,
    strategy_registry: ValuationStrategyRegistry,
) -> CompanyValuationProfile:
    if not isinstance(raw, dict):
        raise ValueError("each valuation company profile must be a mapping")

    profile_id = str(raw.get("profile_id") or "").strip()
    if not profile_id:
        raise ValueError("valuation profile profile_id is required")
    code = normalize_profile_code(raw.get("code"))
    stock_name = str(raw.get("stock_name") or "").strip()
    known_at = _date_value(raw.get("known_at"), field_name="known_at")
    evidence_as_of = _date_value(
        raw.get("evidence_as_of"), field_name="evidence_as_of"
    )
    review_after = _date_value(raw.get("review_after"), field_name="review_after")
    if evidence_as_of > known_at:
        raise ValueError(
            "valuation profile evidence_as_of cannot be after known_at: "
            f"{profile_id}"
        )
    if review_after < known_at:
        raise ValueError(
            "valuation profile review_after cannot be before known_at: "
            f"{profile_id}"
        )

    confidence = str(raw.get("confidence") or "").strip().upper()
    if confidence not in PROFILE_CONFIDENCE_RANK:
        raise ValueError(
            f"valuation profile confidence must be LOW/MEDIUM/HIGH: {profile_id}"
        )

    business_tags = _string_tuple(raw.get("business_tags"), field_name="business_tags")
    archetype_names = _string_tuple(
        raw.get("archetype_hints"), field_name="archetype_hints"
    )
    archetypes: list[CompanyArchetype] = []
    for item in archetype_names:
        try:
            archetype = CompanyArchetype(item.upper())
        except ValueError as exc:
            raise ValueError(
                f"unknown valuation profile archetype {item!r}: {profile_id}"
            ) from exc
        if archetype not in archetypes:
            archetypes.append(archetype)

    disabled_strategy_ids = _string_tuple(
        raw.get("disabled_strategy_ids"), field_name="disabled_strategy_ids"
    )
    known_strategy_ids = {
        strategy.strategy_id for strategy in strategy_registry.strategies
    }
    unknown_disabled = [
        strategy_id
        for strategy_id in disabled_strategy_ids
        if strategy_id not in known_strategy_ids
    ]
    if unknown_disabled:
        raise ValueError(
            "unknown disabled valuation strategy ids: "
            + ",".join(sorted(unknown_disabled))
        )

    if not business_tags and not archetypes and not disabled_strategy_ids:
        raise ValueError(
            "valuation profile must contain business_tags, archetype_hints, "
            f"or disabled_strategy_ids: {profile_id}"
        )

    rationale = str(raw.get("rationale") or "").strip()
    if not rationale:
        raise ValueError(f"valuation profile rationale is required: {profile_id}")
    evidence_refs = _string_tuple(
        raw.get("evidence_refs"), field_name="evidence_refs"
    )
    if not evidence_refs:
        raise ValueError(
            f"valuation profile evidence_refs must be non-empty: {profile_id}"
        )

    return CompanyValuationProfile(
        profile_id=profile_id,
        code=code,
        stock_name=stock_name,
        known_at=known_at,
        evidence_as_of=evidence_as_of,
        review_after=review_after,
        confidence=confidence,
        business_tags=business_tags,
        archetype_hints=tuple(archetypes),
        disabled_strategy_ids=disabled_strategy_ids,
        rationale=rationale,
        evidence_refs=evidence_refs,
    )


def load_company_valuation_profile_repository(
    path: str | Path,
    *,
    strategy_registry: ValuationStrategyRegistry = DEFAULT_VALUATION_STRATEGY_REGISTRY,
) -> CompanyValuationProfileRepository:
    """Load and strictly validate a versioned YAML profile repository."""

    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(f"valuation company profile file not found: {profile_path}")
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("valuation company profile root must be a mapping")
    if raw.get("version") != PROFILE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported valuation company profile schema version: "
            f"{raw.get('version')!r}"
        )
    records = raw.get("profiles")
    if records is None:
        records = []
    if not isinstance(records, list):
        raise ValueError("valuation company profiles must be a list")
    profiles = [
        _parse_profile(item, strategy_registry=strategy_registry) for item in records
    ]
    return CompanyValuationProfileRepository(profiles)
