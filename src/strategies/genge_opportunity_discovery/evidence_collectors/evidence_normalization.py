"""Shared, fail-closed normalization and numeric-evidence recovery.

This module treats document layout as representation, not semantics.  It may
repair harmless PDF/HTML extraction noise, but it never invents a value or
chooses between materially conflicting candidates.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

SOURCE_DATA_ABSENT = "SOURCE_DATA_ABSENT"
SOURCE_FETCH_FAILED = "SOURCE_FETCH_FAILED"
PARSE_FAILED = "PARSE_FAILED"
STRUCTURE_RECOVERY_FAILED = "STRUCTURE_RECOVERY_FAILED"
AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
VALUE_RECOVERED = "VALUE_RECOVERED"
VALUE_VERIFIED = "VALUE_VERIFIED"

VALUE_STATUSES = {VALUE_RECOVERED, VALUE_VERIFIED}

_FULLWIDTH_TRANSLATION = str.maketrans(
    {
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "，": ",", "．": ".", "：": ":", "（": "(", "）": ")",
        "％": "%", "－": "-", "—": "-", "–": "-", "−": "-",
        "＋": "+", "／": "/", "｜": "|", "；": ";", "　": " ", "\u00a0": " ",
    }
)
_UNIT_CANONICAL = {
    "元": ("CURRENCY", "CNY_YUAN", 1.0),
    "万元": ("CURRENCY", "CNY_YUAN", 10_000.0),
    "亿元": ("CURRENCY", "CNY_YUAN", 100_000_000.0),
    "%": ("PERCENT", "PERCENT", 1.0),
    "个百分点": ("PERCENTAGE_POINT", "PERCENTAGE_POINT", 1.0),
    "bp": ("BASIS_POINT", "BASIS_POINT", 1.0),
    "BP": ("BASIS_POINT", "BASIS_POINT", 1.0),
    "基点": ("BASIS_POINT", "BASIS_POINT", 1.0),
    "股": ("SHARES", "SHARES", 1.0),
    "万股": ("SHARES", "SHARES", 10_000.0),
    "吨": ("MASS", "TONNE", 1.0),
    "万吨": ("MASS", "TONNE", 10_000.0),
    "台": ("COUNT", "UNIT_COUNT", 1.0),
    "片": ("COUNT", "UNIT_COUNT", 1.0),
    "GWh": ("ENERGY", "GWH", 1.0),
    "MW": ("POWER", "MW", 1.0),
    "GW": ("POWER", "GW", 1.0),
    "亿": ("COUNT", "UNIT_COUNT", 100_000_000.0),
    "万": ("COUNT", "UNIT_COUNT", 10_000.0),
}
_NUMBER_BODY = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_UNIT_TOKEN = r"(?:亿元|万元|万股|万吨|个百分点|GWh|MW|GW|元|股|吨|台|片|亿|万|%|bp|BP|基点)"
_NUMBER_WITH_UNIT_RE = re.compile(
    rf"(?:\(\s*[+-]?\s*{_NUMBER_BODY}\s*{_UNIT_TOKEN}?\s*\)\s*{_UNIT_TOKEN}?"
    rf"|[+-]?\s*{_NUMBER_BODY}\s*{_UNIT_TOKEN}?)"
)
_PAREN_NUMBER_RE = re.compile(
    rf"\(\s*(?P<sign>[+-]?)\s*(?P<number>{_NUMBER_BODY})\s*"
    rf"(?P<inner_unit>{_UNIT_TOKEN})?\s*\)\s*(?P<outer_unit>{_UNIT_TOKEN})?"
)
_PLAIN_NUMBER_RE = re.compile(
    rf"(?P<sign>[+-]?)\s*(?P<number>{_NUMBER_BODY})\s*(?P<unit>{_UNIT_TOKEN})?"
)
_UNIT_HEADER_RE = re.compile(
    r"(?:金额单位|单位)\s*:?\s*(?:人民币\s*)?(?P<unit>亿元|万元|万股|万吨|个百分点|GWh|MW|GW|元|股|吨|台|片|亿|万|%|bp|BP|基点)"
)
_NUMBERISH_RE = re.compile(r"[\d０-９].{0,30}(?:元|万|亿|%|％|bp|BP|基点)?")
_STRONG_BOUNDARY_RE = re.compile(
    r"(?:^|\n)\s*(?:第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+、)"
)


@dataclass(frozen=True)
class EvidenceValue:
    status: str
    canonical_label: str = ""
    matched_label: str = ""
    raw_value: str = ""
    number_text: str = ""
    numeric_value: float | None = None
    unit: str = ""
    unit_family: str = ""
    normalized_value: float | None = None
    normalized_unit: str = ""
    unit_source: str = ""
    extraction_method: str = ""
    excerpt: str = ""
    source_url: str = ""
    document_id: str = ""
    report_period: str = ""
    page: str = ""
    table: str = ""
    reason: str = ""
    cross_source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_evidence_text(value: Any) -> str:
    """Normalize presentation noise while preserving semantic boundaries."""
    text = str(value or "").translate(_FULLWIDTH_TRANSLATION)
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u00ad", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r"人\s*民\s*币", "人民币", text)
    text = re.sub(r"亿\s*元", "亿元", text)
    text = re.sub(r"万\s*元", "万元", text)
    text = re.sub(r"个\s*百\s*分\s*点", "个百分点", text)
    text = re.sub(r"基\s*点", "基点", text)
    text = re.sub(r"金\s*额\s*单\s*位", "金额单位", text)
    text = re.sub(r"单\s*位", "单位", text)
    text = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ",", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    text = re.sub(r"(?<=\d)\s*%\b", "%", text)
    return text


def label_pattern(label: str) -> re.Pattern[str]:
    """Match a label even when a PDF extractor inserts whitespace/newlines."""
    normalized = normalize_evidence_text(label).strip()
    return re.compile(r"\s*".join(re.escape(char) for char in normalized))


def _normalize_expected_family(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    aliases = {
        "CURRENCY": "CURRENCY",
        "CNY": "CURRENCY",
        "CNY_YUAN": "CURRENCY",
        "PERCENT": "PERCENT",
        "%": "PERCENT",
        "PERCENTAGE_POINT": "PERCENTAGE_POINT",
        "PP": "PERCENTAGE_POINT",
        "BASIS_POINT": "BASIS_POINT",
        "BP": "BASIS_POINT",
    }
    return aliases.get(text, text)


def parse_numeric_value(
    token: str,
    *,
    default_unit: str | None = None,
    expected_unit_family: str | None = None,
) -> EvidenceValue:
    """Parse one numeric token without inferring an undeclared scale."""
    raw = str(token or "")
    normalized = normalize_evidence_text(raw).strip()
    parenthesized = _PAREN_NUMBER_RE.fullmatch(normalized)
    plain = None if parenthesized else _PLAIN_NUMBER_RE.fullmatch(normalized)
    if not parenthesized and not plain:
        return EvidenceValue(status=PARSE_FAILED, raw_value=raw, reason="NUMERIC_TOKEN_NOT_PARSEABLE")

    if parenthesized:
        sign = parenthesized.group("sign") or ""
        number_text = parenthesized.group("number")
        inside_unit = parenthesized.group("inner_unit") or ""
        outside_unit = parenthesized.group("outer_unit") or ""
        if inside_unit and outside_unit and inside_unit != outside_unit:
            return EvidenceValue(status=PARSE_FAILED, raw_value=raw, reason="CONFLICTING_INLINE_UNITS")
        unit = inside_unit or outside_unit or default_unit or ""
        inline_unit = inside_unit or outside_unit
    else:
        sign = plain.group("sign") or ""
        number_text = plain.group("number")
        unit = plain.group("unit") or default_unit or ""
        inline_unit = plain.group("unit") or ""

    unit_source = "INLINE" if inline_unit else ("DECLARED_CONTEXT" if default_unit else "")
    if unit and unit not in _UNIT_CANONICAL:
        return EvidenceValue(status=PARSE_FAILED, raw_value=raw, reason="UNSUPPORTED_UNIT")

    numeric = float(number_text.replace(",", ""))
    if sign == "-":
        numeric = -numeric
    if parenthesized:
        if sign == "+":
            return EvidenceValue(status=PARSE_FAILED, raw_value=raw, reason="CONFLICTING_SIGN_AND_PARENTHESES")
        numeric = -abs(numeric)

    if unit:
        family, normalized_unit, multiplier = _UNIT_CANONICAL[unit]
        normalized_value = numeric * multiplier
    else:
        family, normalized_unit, normalized_value = "UNITLESS", "UNITLESS", numeric

    expected = _normalize_expected_family(expected_unit_family)
    if expected and family != expected:
        return EvidenceValue(
            status=PARSE_FAILED,
            raw_value=raw,
            number_text=("-" if numeric < 0 else "") + number_text,
            numeric_value=numeric,
            unit=unit,
            unit_family=family,
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            unit_source=unit_source,
            reason=f"UNIT_FAMILY_MISMATCH:{family}!={expected}",
        )

    return EvidenceValue(
        status=VALUE_VERIFIED,
        raw_value=raw,
        number_text=("-" if numeric < 0 else "") + number_text,
        numeric_value=numeric,
        unit=unit,
        unit_family=family,
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        unit_source=unit_source,
        extraction_method="NUMERIC_TOKEN",
        reason="NUMERIC_VALUE_PARSED",
    )


def _resolved_labels(
    labels: Iterable[str],
    aliases: Mapping[str, Sequence[str]] | None,
) -> list[tuple[str, str, re.Pattern[str]]]:
    result: list[tuple[str, str, re.Pattern[str]]] = []
    aliases = aliases or {}
    for canonical in labels:
        variants = [canonical, *aliases.get(canonical, ())]
        seen: set[str] = set()
        for variant in variants:
            normalized = normalize_evidence_text(variant).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append((canonical, normalized, label_pattern(normalized)))
    return result


def _nearby_declared_unit(text: str, label_start: int) -> tuple[str | None, str | None]:
    before = text[max(0, label_start - 1400):label_start]
    matches = list(_UNIT_HEADER_RE.finditer(before))
    if not matches:
        return None, None
    nearest = matches[-1]
    nearest_distance = len(before) - nearest.end()
    if nearest_distance > 1000:
        return None, None
    coherent = [
        item for item in matches
        if len(before) - item.end() <= nearest_distance + 260
    ]
    units = {item.group("unit") for item in coherent}
    if len(units) != 1:
        return None, "CONFLICTING_NEARBY_UNIT_HEADERS"
    return nearest.group("unit"), None


def _candidate_windows(
    normalized: str,
    label_end: int,
    all_label_patterns: Sequence[re.Pattern[str]],
    max_chars: int,
) -> str:
    window = normalized[label_end:label_end + max_chars]
    boundaries: list[int] = []
    for pattern in all_label_patterns:
        match = pattern.search(window)
        if match:
            boundaries.append(match.start())
    boundary = _STRONG_BOUNDARY_RE.search(window)
    if boundary:
        boundaries.append(boundary.start())
    if boundaries:
        window = window[:min(boundaries)]
    return window


def _family_matches(result: EvidenceValue, expected: str | None) -> bool:
    if not expected:
        return True
    return result.unit_family == _normalize_expected_family(expected)


def _materially_same(left: EvidenceValue, right: EvidenceValue) -> bool:
    if left.normalized_unit != right.normalized_unit:
        return False
    if left.normalized_value is None or right.normalized_value is None:
        return False
    scale = max(1.0, abs(left.normalized_value), abs(right.normalized_value))
    return abs(left.normalized_value - right.normalized_value) <= scale * 1e-10


def extract_labeled_numeric_evidence(
    text: str,
    *,
    labels: Iterable[str],
    aliases: Mapping[str, Sequence[str]] | None = None,
    expected_unit_family: str | None = None,
    default_unit: str | None = None,
    allow_nearby_unit_header: bool = True,
    max_chars_after_label: int = 260,
    source_url: str = "",
    document_id: str = "",
    report_period: str = "",
    page: str | int = "",
    table: str = "",
) -> EvidenceValue:
    """Recover one value near a semantic label, or fail closed on ambiguity."""
    raw_text = str(text or "")
    if not raw_text.strip():
        return EvidenceValue(
            status=SOURCE_DATA_ABSENT,
            source_url=source_url,
            document_id=document_id,
            report_period=report_period,
            page=str(page or ""),
            table=table,
            reason="EMPTY_SOURCE_TEXT",
        )

    normalized = normalize_evidence_text(raw_text)
    resolved = _resolved_labels(labels, aliases)
    all_patterns = [item[2] for item in resolved]
    label_hits: list[tuple[int, int, str, str, re.Match[str]]] = []
    for canonical, variant, pattern in resolved:
        for match in pattern.finditer(normalized):
            label_hits.append((match.start(), match.end(), canonical, variant, match))

    if not label_hits:
        return EvidenceValue(
            status=SOURCE_DATA_ABSENT,
            source_url=source_url,
            document_id=document_id,
            report_period=report_period,
            page=str(page or ""),
            table=table,
            reason="TARGET_LABEL_NOT_PRESENT",
        )

    accepted: list[tuple[EvidenceValue, bool, bool, str, str, int, int]] = []
    failure_reasons: list[str] = []
    for start, end, canonical, variant, match in sorted(label_hits, key=lambda row: row[0]):
        declared_unit = default_unit
        if allow_nearby_unit_header and not declared_unit:
            declared_unit, header_error = _nearby_declared_unit(normalized, start)
            if header_error:
                failure_reasons.append(header_error)
                continue

        window = _candidate_windows(normalized, end, all_patterns, max_chars_after_label)
        same_line_end = window.find("\n")
        if same_line_end < 0:
            same_line_end = len(window)

        local_candidates: list[tuple[EvidenceValue, bool, int, int]] = []
        for number_match in _NUMBER_WITH_UNIT_RE.finditer(window):
            token = number_match.group(0).strip()
            if not token:
                continue
            parsed = parse_numeric_value(
                token,
                default_unit=declared_unit,
                expected_unit_family=expected_unit_family,
            )
            if parsed.status != VALUE_VERIFIED or not _family_matches(parsed, expected_unit_family):
                continue
            if (
                parsed.unit_family == "UNITLESS"
                and parsed.numeric_value is not None
                and float(parsed.numeric_value).is_integer()
                and 2000 <= abs(parsed.numeric_value) <= 2100
            ):
                continue
            same_line = number_match.start() < same_line_end
            local_candidates.append((parsed, same_line, number_match.start(), number_match.end()))

        if not local_candidates:
            if _NUMBERISH_RE.search(window):
                failure_reasons.append("NUMBERISH_CONTEXT_NOT_SEMANTICALLY_PARSEABLE")
            else:
                failure_reasons.append("NO_NUMERIC_VALUE_IN_LOCAL_LABEL_CONTEXT")
            continue

        for parsed, same_line, number_start, number_end in local_candidates:
            excerpt_end = min(len(normalized), end + number_end + 100)
            excerpt = normalized[start:excerpt_end].strip()[:900]
            required_recovery = (
                not same_line
                or variant != canonical
                or "\n" in match.group(0)
                or normalized != raw_text
            )
            method = "SAME_LINE_LABEL_VALUE" if not required_recovery else "NORMALIZED_LOCAL_NEIGHBORHOOD"
            accepted.append(
                (
                    EvidenceValue(
                        status=VALUE_RECOVERED if required_recovery else VALUE_VERIFIED,
                        canonical_label=canonical,
                        matched_label=variant,
                        raw_value=parsed.raw_value,
                        number_text=parsed.number_text,
                        numeric_value=parsed.numeric_value,
                        unit=parsed.unit,
                        unit_family=parsed.unit_family,
                        normalized_value=parsed.normalized_value,
                        normalized_unit=parsed.normalized_unit,
                        unit_source=parsed.unit_source,
                        extraction_method=method,
                        excerpt=excerpt,
                        source_url=source_url,
                        document_id=document_id,
                        report_period=report_period,
                        page=str(page or ""),
                        table=table,
                        reason="SEMANTIC_LABEL_VALUE_MATCH",
                    ),
                    same_line,
                    variant == canonical,
                    canonical,
                    variant,
                    start,
                    number_start,
                )
            )

    if not accepted:
        reason = (
            "CONFLICTING_NEARBY_UNIT_HEADERS"
            if "CONFLICTING_NEARBY_UNIT_HEADERS" in failure_reasons
            else "STRUCTURE_RECOVERY_EXHAUSTED"
        )
        status = AMBIGUOUS_MATCH if reason.startswith("CONFLICTING") else STRUCTURE_RECOVERY_FAILED
        return EvidenceValue(
            status=status,
            source_url=source_url,
            document_id=document_id,
            report_period=report_period,
            page=str(page or ""),
            table=table,
            reason=reason,
        )

    best_tier = max((2 if same_line else 0) + (1 if canonical == variant else 0)
                    for _, same_line, _, canonical, variant, _, _ in accepted)
    best = [
        item[0]
        for item in accepted
        if (2 if item[1] else 0) + (1 if item[3] == item[4] else 0) == best_tier
    ]
    baseline = best[0]
    conflicts = [item for item in best[1:] if not _materially_same(baseline, item)]
    if conflicts:
        return EvidenceValue(
            status=AMBIGUOUS_MATCH,
            canonical_label=baseline.canonical_label,
            matched_label=baseline.matched_label,
            source_url=source_url,
            document_id=document_id,
            report_period=report_period,
            page=str(page or ""),
            table=table,
            reason="MULTIPLE_MATERIAL_VALUES_MATCH_TARGET",
        )
    return baseline


def extract_with_fallback_sources(
    sources: Sequence[Mapping[str, Any]],
    *,
    labels: Iterable[str],
    aliases: Mapping[str, Sequence[str]] | None = None,
    expected_unit_family: str | None = None,
    default_unit: str | None = None,
) -> EvidenceValue:
    """Cross-check same-target public sources and recover from failed primaries."""
    values: list[EvidenceValue] = []
    failures: list[str] = []
    for source in sources:
        source_status = str(source.get("status") or "")
        if source_status in {
            SOURCE_FETCH_FAILED,
            PARSE_FAILED,
            STRUCTURE_RECOVERY_FAILED,
            SOURCE_DATA_ABSENT,
        }:
            failures.append(source_status)
            continue
        result = extract_labeled_numeric_evidence(
            str(source.get("text") or ""),
            labels=labels,
            aliases=aliases,
            expected_unit_family=expected_unit_family,
            default_unit=str(source.get("default_unit") or default_unit or "") or None,
            source_url=str(source.get("source_url") or ""),
            document_id=str(source.get("document_id") or ""),
            report_period=str(source.get("report_period") or ""),
            page=source.get("page") or "",
            table=str(source.get("table") or ""),
        )
        if result.status in VALUE_STATUSES:
            values.append(result)
        else:
            failures.append(result.status)

    if not values:
        precedence = [AMBIGUOUS_MATCH, PARSE_FAILED, SOURCE_FETCH_FAILED, STRUCTURE_RECOVERY_FAILED, SOURCE_DATA_ABSENT]
        status = next((item for item in precedence if item in failures), SOURCE_DATA_ABSENT)
        return EvidenceValue(status=status, reason="NO_TRUSTED_FALLBACK_SOURCE_RECOVERED_TARGET")

    baseline = values[0]
    if any(not _materially_same(baseline, item) for item in values[1:]):
        return EvidenceValue(
            status=AMBIGUOUS_MATCH,
            canonical_label=baseline.canonical_label,
            report_period=baseline.report_period,
            reason="CROSS_SOURCE_VALUE_CONFLICT",
            cross_source_count=len(values),
        )

    if len(values) == 1:
        return baseline

    payload = baseline.to_dict()
    payload["status"] = VALUE_VERIFIED
    payload["reason"] = "CROSS_SOURCE_VALUE_VERIFIED"
    payload["cross_source_count"] = len(values)
    payload["extraction_method"] = "CROSS_SOURCE_CONSENSUS"
    return EvidenceValue(**payload)


def failure_evidence(
    status: str,
    *,
    reason: str,
    source_url: str = "",
    document_id: str = "",
    report_period: str = "",
) -> EvidenceValue:
    """Create a typed extraction failure without collapsing it to UNKNOWN."""
    allowed = {
        SOURCE_DATA_ABSENT,
        SOURCE_FETCH_FAILED,
        PARSE_FAILED,
        STRUCTURE_RECOVERY_FAILED,
        AMBIGUOUS_MATCH,
    }
    if status not in allowed:
        raise ValueError(f"invalid evidence failure status: {status}")
    return EvidenceValue(
        status=status,
        reason=reason,
        source_url=source_url,
        document_id=document_id,
        report_period=report_period,
    )
