"""Strict multi-year official-report evidence for the V3.1 predictability gate.

This collector is fail-closed on evidence, not on PDF layout. Official annual
report values may be wrapped across lines/columns, use full-width punctuation,
or place years/units on separate table rows. Those representation differences
must not turn available evidence into UNKNOWN. Genuine missing, conflicting or
scope-ambiguous evidence still remains UNKNOWN.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

import requests

from .company_announcements import (
    REQUEST_HEADERS,
    _clean_title,
    _cninfo_publish_date,
    _load_cninfo_org_ids,
)
from .validators import content_hash, extract_text_from_response, source_domain, utc_now

RULE_VERSION = "PREDICTABILITY_MULTI_YEAR_OFFICIAL_V2"
HISTORY_DAYS = 2200
MAX_REPORTS = 5
MIN_COMPLETE_YEARS = 3
_METRIC_WINDOW = 1400
_HEADER_WINDOW = 1600

_RESOURCE_TOKENS = (
    "有色", "金属", "矿", "煤", "石油", "石化", "油气", "钢铁", "能源",
    "基础化工", "化工原料", "黄金", "铜", "铝", "锂", "钴", "镍", "稀土",
)
_RESOURCE_REPORT_PATTERNS = (
    re.compile(r"矿山|矿产资源|采矿|选矿"),
    re.compile(r"铜矿|金矿|钼矿|锂矿|镍矿|钴矿|铁矿"),
    re.compile(r"原油|天然气|煤炭开采"),
)
_FISCAL_YEAR_RE = re.compile(r"(20\d{2})年(?:年度报告|年报)")
_NUMBER_TOKEN = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NUMBER_RE = re.compile(
    rf"(?<![\d.])(?P<sign>-?)(?P<number>{_NUMBER_TOKEN})(?![\d.])"
)
_UNIT_RE = re.compile(r"(亿元|万元|元)")
_UNIT_HEADER_RE = re.compile(
    r"(?:金额单位|单位)\s*[:：]?\s*(?:人民币\s*)?(?P<unit>亿元|万元|元)(?![/每])"
)
_DATE_RE = re.compile(
    r"(?:20\d{2}(?:[-/.]\d{1,2}){1,2}|"
    r"20\d{2}年\d{1,2}月(?:\d{1,2}日)?|"
    r"\d{1,2}月\d{1,2}日|"
    r"\d{1,2}[-/]\d{1,2})"
)
_UNIT_MULTIPLIERS: Mapping[str, float] = {
    "元": 1.0,
    "万元": 10_000.0,
    "亿元": 100_000_000.0,
}
_METRIC_LABELS: Mapping[str, tuple[str, ...]] = {
    "revenue": ("营业收入",),
    "net_profit": ("归属于上市公司股东的净利润", "归属于母公司股东的净利润"),
    "operating_cash_flow": ("经营活动产生的现金流量净额",),
}
_REQUIRED_METRICS = tuple(_METRIC_LABELS)
_SCOPED_METRIC_TOKENS = (
    "产品", "板块", "分部", "地区", "区域", "分行业", "按行业", "按产品",
    "按地区", "按区域", "矿山端", "贸易端", "冶炼端", "单项业务", "单一业务",
)

_FULLWIDTH_TRANSLATION = str.maketrans(
    {
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "，": ",", "．": ".", "：": ":", "（": "(", "）": ")",
        "％": "%", "－": "-", "—": "-", "–": "-", "−": "-",
        "／": "/", "｜": "|", "；": ";", "　": " ", " ": " ",
    }
)
_SPLIT_GROUP_RE = re.compile(
    r"(?P<head>\d{1,3}(?:,\d{3})*,)(?P<partial>\d{1,2})"
    r"[ \t]*\n[ \t]*(?P<tail>\d{1,2})(?P<decimal>\.\d+)?(?!\d)"
)
_DANGLING_GROUP_RE = re.compile(
    r"(?P<head>\d{1,3}(?:,\d{3})*,)[ \t]*\n[ \t]*"
    r"(?P<tail>\d{3})(?P<decimal>\.\d+)?(?!\d)"
)
_SECTION_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:第[一二三四五六七八九十百]+[章节]|[一二三四五六七八九十]+、)"
)


def _repair_split_grouped_numbers(text: str) -> str:
    """Repair only line breaks that split a valid comma-grouped number.

    PDF extractors sometimes emit ``2,261,294,31\n2.85`` for
    ``2,261,294,312.85``. Joining arbitrary adjacent digit lines would be
    unsafe because separate table columns can also be numeric. We therefore
    repair only an already comma-grouped token whose last group is provably
    incomplete, or a dangling comma followed by one complete 3-digit group.
    """
    previous = None
    while previous != text:
        previous = text

        def complete_partial(match: re.Match[str]) -> str:
            partial = match.group("partial")
            tail = match.group("tail")
            if len(partial) + len(tail) != 3:
                return match.group(0)
            return (
                match.group("head")
                + partial
                + tail
                + (match.group("decimal") or "")
            )

        text = _SPLIT_GROUP_RE.sub(complete_partial, text)
        text = _DANGLING_GROUP_RE.sub(
            lambda match: (
                match.group("head")
                + match.group("tail")
                + (match.group("decimal") or "")
            ),
            text,
        )
    return text


def _normalize_pdf_text(value: Any) -> str:
    """Normalize presentation noise without joining unrelated table cells."""
    text = str(value or "").translate(_FULLWIDTH_TRANSLATION)
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u00ad", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _repair_split_grouped_numbers(text)
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r"人\s*民\s*币", "人民币", text)
    text = re.sub(r"亿\s*元", "亿元", text)
    text = re.sub(r"万\s*元", "万元", text)
    text = re.sub(r"金\s*额\s*单\s*位", "金额单位", text)
    text = re.sub(r"单\s*位", "单位", text)
    # A line wrap around decimal/thousands punctuation is layout, not a new cell.
    text = re.sub(r"(?<=\d)\s*,\s*(?=\d)", ",", text)
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    return text


def _label_pattern(label: str) -> re.Pattern[str]:
    # PDF text extraction often inserts spaces/newlines inside Chinese labels.
    return re.compile(r"\s*".join(re.escape(char) for char in label))


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _fiscal_year(title: Any) -> int | None:
    match = _FISCAL_YEAR_RE.search(str(title or ""))
    return int(match.group(1)) if match else None


def _query_cninfo_history(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> list[dict[str, Any]]:
    start = (as_of - timedelta(days=HISTORY_DAYS)).isoformat()
    is_shanghai = code.startswith(("6", "9"))
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "sse" if is_shanghai else "szse",
        "tabName": "fulltext",
        "plate": "sh" if is_shanghai else "sz",
        "stock": f"{code},{org_id}",
        "searchkey": "年度报告",
        "secid": "",
        "category": "category_ndbg_szsh",
        "trade": "",
        "seDate": f"{start}~{as_of.isoformat()}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = session.post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        data=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    by_year: dict[int, dict[str, Any]] = {}
    for item in response.json().get("announcements") or []:
        title = _clean_title(item.get("announcementTitle"))
        if "摘要" in title or "英文" in title or "取消" in title:
            continue
        year = _fiscal_year(title)
        adjunct = str(item.get("adjunctUrl") or "").strip()
        published = _cninfo_publish_date(item.get("announcementTime"))
        if year is None or not adjunct or published is None or published > as_of:
            continue
        candidate = {
            "fiscal_year": year,
            "title": title,
            "publish_date": published.isoformat(),
            "url": f"https://static.cninfo.com.cn/{adjunct}",
        }
        previous = by_year.get(year)
        if previous is None or candidate["publish_date"] > previous["publish_date"]:
            by_year[year] = candidate
    return [by_year[year] for year in sorted(by_year, reverse=True)[:MAX_REPORTS]]


def _nearby_header_unit(text: str, label_start: int) -> tuple[str | None, str]:
    """Use the closest coherent unit header; ignore remote unrelated tables."""
    before = text[max(0, label_start - _HEADER_WINDOW):label_start]
    matches = list(_UNIT_HEADER_RE.finditer(before))
    if not matches:
        return None, "NO_TRUSTED_UNIT_HEADER"

    with_distance = [(len(before) - match.end(), match) for match in matches]
    with_distance = [(distance, match) for distance, match in with_distance if distance <= 1000]
    if not with_distance:
        return None, "NO_NEARBY_UNIT_HEADER"
    with_distance.sort(key=lambda item: item[0])
    nearest_distance = with_distance[0][0]
    coherent = [
        match for distance, match in with_distance
        if distance <= nearest_distance + 220
    ]
    units = {match.group("unit") for match in coherent}
    if len(units) != 1:
        return None, "CONFLICTING_NEARBY_UNIT_HEADERS"
    return coherent[0].group("unit"), "TABLE_HEADER"


def _metric_label_unit(text: str, label_end: int) -> str | None:
    tail = text[label_end:label_end + 40]
    match = re.match(r"\s*\(\s*(亿元|万元|元)\s*\)", tail)
    return match.group(1) if match else None


def _metric_context_is_scoped(text: str, label_start: int, label_end: int) -> bool:
    prefix = text[max(0, label_start - 100):label_start]
    prefix_clause = re.split(r"[。；;\n]", prefix)[-1]
    if any(token in prefix_clause for token in _SCOPED_METRIC_TOKENS):
        return True

    suffix = text[label_end:label_end + 100]
    suffix_clause = re.split(r"[。；;\n]", suffix)[0]
    suffix_before_number = re.split(r"\d", suffix_clause, maxsplit=1)[0]
    return any(token in suffix_before_number for token in _SCOPED_METRIC_TOKENS)


def _raw_number(window: str, match: re.Match[str]) -> float:
    token = (match.group("sign") or "") + match.group("number")
    value = float(token.replace(",", ""))
    if not match.group("sign"):
        left = window[max(0, match.start() - 8):match.start()].rstrip()
        right = window[match.end():match.end() + 8].lstrip()
        if left.endswith("(") and right.startswith(")"):
            value = -value
    return value


def _looks_like_non_metric_number(window: str, match: re.Match[str], fiscal_year: int) -> bool:
    try:
        value = _raw_number(window, match)
    except ValueError:
        return True
    raw = match.group(0)
    left = window[max(0, match.start() - 16):match.start()]
    right = window[match.end():match.end() + 16]
    around = left + raw + right

    if "%" in right[:5]:
        return True
    if right.lstrip().startswith(("年", "月", "日")):
        return True
    token_start = len(left)
    token_end = token_start + len(raw)
    if any(
        item.start() < token_end and item.end() > token_start
        for item in _DATE_RE.finditer(around)
    ):
        return True
    if value.is_integer() and 2000 <= abs(value) <= 2100:
        return True
    if value.is_integer() and int(abs(value)) == int(fiscal_year):
        return True
    if re.search(r"(?:第|P\.?|Page\s*)\s*$", left, flags=re.IGNORECASE):
        return True
    if right.lstrip().startswith(("页", "项", "章")) and abs(value) < 10000:
        return True
    return False


def _next_metric_position(window: str) -> int | None:
    positions: list[int] = []
    for labels in _METRIC_LABELS.values():
        for label in labels:
            match = _label_pattern(label).search(window)
            if match:
                positions.append(match.start())
    return min(positions) if positions else None


def _nearby_header_years(text: str, label_start: int) -> list[int]:
    """Recover fiscal-year columns even when the PDF emits one header per line."""
    before = text[max(0, label_start - _HEADER_WINDOW):label_start]
    block = before[-900:]
    found: list[int] = []
    for match in re.finditer(r"(?<!\d)(20\d{2})\s*年?(?!\s*\d{1,2}\s*月|\d)", block):
        year = int(match.group(1))
        if 2000 <= year <= 2100 and year not in found:
            found.append(year)
    if len(found) < 2:
        return []
    # Table headers normally cover a compact fiscal range. Wider ranges are
    # likely narrative references and are intentionally not used as columns.
    if max(found) - min(found) > 6:
        return []
    return found[-6:]


def _row_fallback_is_local(window: str, match: re.Match[str]) -> bool:
    """Reject values reached only by drifting from prose into another section."""
    prefix = window[:match.start()]
    # In a genuine table row there is no completed prose sentence between the
    # metric label and its first value. This blocks examples such as
    # “经营活动产生的现金流量净额远高于净利润。 六、资产...” from borrowing a
    # later balance-sheet number.
    if re.search(r"[。！？]", prefix):
        return False
    if _SECTION_HEADING_RE.search(prefix):
        return False
    # Table headers/cell wrapping can be verbose, but a long run of prose before
    # the first number is not a local metric row.
    compact = re.sub(r"\s+", "", prefix)
    return len(compact) <= 180


def _local_unit(
    *,
    normalized: str,
    label_match: re.Match[str],
    window: str,
    number_match: re.Match[str],
    label_unit: str | None,
    header_unit: str | None,
    header_reason: str,
) -> tuple[str | None, str | None, str | None]:
    suffix = window[number_match.end():number_match.end() + 24].lstrip()
    inline_match = _UNIT_RE.match(suffix)
    inline_unit = inline_match.group(1) if inline_match else None

    local_headers = list(_UNIT_HEADER_RE.finditer(window[:number_match.start()]))
    local_unit: str | None = None
    if local_headers:
        nearest = local_headers[-1]
        if number_match.start() - nearest.end() <= 500:
            local_unit = nearest.group("unit")

    declared = {unit for unit in (inline_unit, label_unit, local_unit, header_unit) if unit}
    if len(declared) > 1:
        return None, None, "INLINE_HEADER_UNIT_CONFLICT"
    unit = inline_unit or label_unit or local_unit or header_unit
    if not unit:
        return None, None, header_reason
    source = (
        "INLINE" if inline_unit
        else "METRIC_LABEL" if label_unit
        else "LOCAL_HEADER" if local_unit
        else header_reason
    )
    return unit, source, None


def _measurement_payload(
    *,
    normalized: str,
    label_match: re.Match[str],
    number_match: re.Match[str],
    raw_value: float,
    unit: str,
    unit_source: str,
    extraction_mode: str,
) -> dict[str, Any]:
    excerpt_start = label_match.start()
    excerpt_end = min(len(normalized), label_match.end() + number_match.end() + 140)
    return {
        "value_yuan": raw_value * _UNIT_MULTIPLIERS[unit],
        "raw_value": raw_value,
        "unit": unit,
        "unit_source": unit_source,
        "verified": True,
        "reason": "TRUSTED_UNIT_NORMALIZED_TO_YUAN",
        "extraction_mode": extraction_mode,
        "excerpt": normalized[excerpt_start:excerpt_end].strip()[:900],
    }


def _candidate_from_match(
    *,
    normalized: str,
    label_match: re.Match[str],
    window: str,
    number_match: re.Match[str],
    label_unit: str | None,
    header_unit: str | None,
    header_reason: str,
    extraction_mode: str,
    priority: int,
    fiscal_year: int,
) -> tuple[int, dict[str, Any]] | tuple[None, str]:
    if _looks_like_non_metric_number(window, number_match, fiscal_year):
        return None, "NON_METRIC_NUMBER"
    unit, unit_source, error = _local_unit(
        normalized=normalized,
        label_match=label_match,
        window=window,
        number_match=number_match,
        label_unit=label_unit,
        header_unit=header_unit,
        header_reason=header_reason,
    )
    if error or not unit or not unit_source:
        return None, error or "NO_TRUSTED_UNIT_HEADER"
    payload = _measurement_payload(
        normalized=normalized,
        label_match=label_match,
        number_match=number_match,
        raw_value=_raw_number(window, number_match),
        unit=unit,
        unit_source=unit_source,
        extraction_mode=extraction_mode,
    )
    return priority, payload


def _choose_metric_candidate(
    candidates: list[tuple[int, dict[str, Any]]], reasons: list[str]
) -> dict[str, Any]:
    if candidates:
        top = max(priority for priority, _ in candidates)
        selected = [payload for priority, payload in candidates if priority == top]
        baseline = float(selected[0]["value_yuan"])
        materially_different = [
            row for row in selected[1:]
            if abs(float(row["value_yuan"]) - baseline) > max(1.0, abs(baseline) * 1e-8)
        ]
        if not materially_different:
            return selected[0]
        reasons.append("AMBIGUOUS_METRIC_VALUES_FOR_FISCAL_YEAR")

    reason = next(
        (value for value in reasons if value not in {"NON_METRIC_NUMBER"}),
        "METRIC_VALUE_NOT_FOUND",
    )
    return {
        "value_yuan": None,
        "raw_value": None,
        "unit": None,
        "unit_source": None,
        "verified": False,
        "reason": reason,
        "extraction_mode": None,
        "excerpt": "",
    }


def _metric_measurement(text: str, labels: Iterable[str], fiscal_year: int) -> dict[str, Any]:
    """Extract a consolidated metric while tolerating harmless PDF layout noise."""
    normalized = _normalize_pdf_text(text)
    reasons: list[str] = []
    candidates: list[tuple[int, dict[str, Any]]] = []

    for label in labels:
        for label_match in _label_pattern(label).finditer(normalized):
            if _metric_context_is_scoped(normalized, label_match.start(), label_match.end()):
                reasons.append("SCOPED_SUBTOTAL_NOT_COMPANY_METRIC")
                continue

            label_unit = _metric_label_unit(normalized, label_match.end())
            header_unit, header_reason = _nearby_header_unit(normalized, label_match.start())
            window = normalized[label_match.end():label_match.end() + _METRIC_WINDOW]
            next_metric = _next_metric_position(window)
            if next_metric is not None:
                window = window[:next_metric]

            # Highest confidence: requested fiscal year is explicitly bound to
            # its value. A newline is accepted; narrative words between year and
            # number are not, so “2024年实现...” cannot be mistaken for a table.
            year_value_pattern = re.compile(
                rf"(?<!\d){int(fiscal_year)}\s*年?(?!\d)"
                rf"(?:\s|[:|/;,-])+"
                rf"(?P<sign>-?)(?P<number>{_NUMBER_TOKEN})(?![\d.])"
            )
            for match in year_value_pattern.finditer(window):
                candidate = _candidate_from_match(
                    normalized=normalized,
                    label_match=label_match,
                    window=window,
                    number_match=match,
                    label_unit=label_unit,
                    header_unit=header_unit,
                    header_reason=header_reason,
                    extraction_mode="EXPLICIT_FISCAL_YEAR_VALUE",
                    priority=30,
                    fiscal_year=fiscal_year,
                )
                if candidate[0] is None:
                    reasons.append(candidate[1])
                else:
                    candidates.append(candidate)

            # Second confidence tier: year headers are emitted before the metric
            # row while values are emitted after it. This is common in PDF table
            # extraction, including one header/value per line.
            header_years = _nearby_header_years(normalized, label_match.start())
            if fiscal_year in header_years:
                value_matches = [
                    match for match in _NUMBER_RE.finditer(window)
                    if not _looks_like_non_metric_number(window, match, fiscal_year)
                ]
                index = header_years.index(fiscal_year)
                if index < len(value_matches):
                    candidate = _candidate_from_match(
                        normalized=normalized,
                        label_match=label_match,
                        window=window,
                        number_match=value_matches[index],
                        label_unit=label_unit,
                        header_unit=header_unit,
                        header_reason=header_reason,
                        extraction_mode="HEADER_COLUMN_FISCAL_YEAR",
                        priority=20,
                        fiscal_year=fiscal_year,
                    )
                    if candidate[0] is None:
                        reasons.append(candidate[1])
                    else:
                        candidates.append(candidate)

            # Backward-compatible annual-report row fallback. In the annual
            # report for fiscal_year the first consolidated metric value is the
            # current-period value. It is used only when stronger year binding is
            # unavailable, and still requires trusted unit provenance/scope.
            for match in _NUMBER_RE.finditer(window):
                if _looks_like_non_metric_number(window, match, fiscal_year):
                    continue
                if not _row_fallback_is_local(window, match):
                    reasons.append("NARRATIVE_OR_SECTION_BOUNDARY_BEFORE_VALUE")
                    break
                candidate = _candidate_from_match(
                    normalized=normalized,
                    label_match=label_match,
                    window=window,
                    number_match=match,
                    label_unit=label_unit,
                    header_unit=header_unit,
                    header_reason=header_reason,
                    extraction_mode="ANNUAL_REPORT_CURRENT_ROW",
                    priority=10,
                    fiscal_year=fiscal_year,
                )
                if candidate[0] is None:
                    reasons.append(candidate[1])
                else:
                    candidates.append(candidate)
                break

    return _choose_metric_candidate(candidates, reasons)


def extract_report_metrics(text: str, fiscal_year: int) -> dict[str, Any]:
    measurements = {
        name: _metric_measurement(text, labels, int(fiscal_year))
        for name, labels in _METRIC_LABELS.items()
    }
    return {
        "fiscal_year": int(fiscal_year),
        **{name: measurement["value_yuan"] for name, measurement in measurements.items()},
        "metric_provenance": measurements,
        "normalization_unit": "CNY_YUAN",
        "unit_provenance_required": True,
    }


def _metric_is_trusted(row: Mapping[str, Any], metric: str) -> bool:
    if row.get(metric) is None:
        return False
    provenance = row.get("metric_provenance")
    if not isinstance(provenance, Mapping):
        return False
    detail = provenance.get(metric)
    if not isinstance(detail, Mapping):
        return False
    return bool(
        detail.get("verified")
        and detail.get("unit") in _UNIT_MULTIPLIERS
        and detail.get("unit_source") in {"INLINE", "METRIC_LABEL", "LOCAL_HEADER", "TABLE_HEADER"}
        and detail.get("value_yuan") is not None
    )


def _complete_record(row: Mapping[str, Any]) -> bool:
    return row.get("fiscal_year") is not None and all(
        _metric_is_trusted(row, metric) for metric in _REQUIRED_METRICS
    )


def _consecutive_years(records: list[Mapping[str, Any]]) -> bool:
    years = sorted({int(row["fiscal_year"]) for row in records})
    return len(years) >= MIN_COMPLETE_YEARS and all(
        b - a == 1 for a, b in zip(years, years[1:])
    )


def _yoy_floor(values: list[float], floor: float) -> bool:
    for previous, current in zip(values, values[1:]):
        if previous <= 0 or current <= 0:
            return False
        if current / previous - 1.0 < floor:
            return False
    return True


def classify_multi_year_metrics(
    records: Iterable[Mapping[str, Any]], *, cyclical_or_resource: bool
) -> tuple[str, str]:
    complete = [dict(row) for row in records if _complete_record(row)]
    complete.sort(key=lambda row: int(row["fiscal_year"]))
    if len(complete) < MIN_COMPLETE_YEARS or not _consecutive_years(complete):
        return "UNKNOWN", "INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS"
    if cyclical_or_resource:
        return "UNKNOWN", "CYCLICAL_RESOURCE_REQUIRES_EXPLICIT_CYCLE_RESILIENCE_EVIDENCE"

    revenue = [float(row["revenue"]) for row in complete]
    profit = [float(row["net_profit"]) for row in complete]
    cash_flow = [float(row["operating_cash_flow"]) for row in complete]
    if any(value <= 0 for value in revenue + profit + cash_flow):
        return "UNKNOWN", "MULTI_YEAR_POSITIVITY_NOT_PROVEN"
    if not _yoy_floor(revenue, -0.20):
        return "UNKNOWN", "REVENUE_STABILITY_THRESHOLD_NOT_MET"
    if not _yoy_floor(profit, -0.50):
        return "UNKNOWN", "EARNINGS_STABILITY_THRESHOLD_NOT_MET"
    if not _yoy_floor(cash_flow, -0.50):
        return "UNKNOWN", "OPERATING_CASH_FLOW_STABILITY_THRESHOLD_NOT_MET"
    if max(profit) / min(profit) > 5.0 or max(cash_flow) / min(cash_flow) > 5.0:
        return "UNKNOWN", "MULTI_YEAR_VOLATILITY_THRESHOLD_NOT_MET"
    return "PASS", "STRICT_MULTI_YEAR_ACCOUNTING_PREDICTABILITY_PROVEN"


def _is_cyclical_or_resource(industry: Any, reports_text: Iterable[str]) -> bool:
    industry_text = str(industry or "")
    if any(token in industry_text for token in _RESOURCE_TOKENS):
        return True
    sample = "\n".join(str(text or "")[:12000] for text in reports_text)
    return any(pattern.search(sample) for pattern in _RESOURCE_REPORT_PATTERNS)


def _unknown_row(code: str, industry: str, reason: str) -> dict[str, Any]:
    payload = {"code": code, "industry": industry, "reason": reason, "rule": RULE_VERSION}
    return {
        "code": code,
        "industry": industry,
        "evidence_kind": "multi_year_predictability",
        "indicator": "predictability_multi_year_official",
        "predictability_classification": "UNKNOWN",
        "reason_code": reason,
        "rule_version": RULE_VERSION,
        "coverage_years": [],
        "metrics_by_year": [],
        "evidence_status": "OBSERVED_CONTEXT",
        "source_type": "OFFICIAL_REPORT",
        "source_domain": "cninfo.com.cn",
        "publish_date": "",
        "original_url": "",
        "normalized_summary": reason,
        "content_hash": content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        "unit_provenance_required": True,
        "normalization_unit": "CNY_YUAN",
        "authority_crossed": False,
        "formal_decision": False,
        "adopted_for_gate": False,
        "collected_at": utc_now(),
    }


def collect_multi_year_predictability_evidence(
    *,
    priority_rows: Iterable[Mapping[str, Any]],
    as_of: date,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    selected = [dict(row) for row in priority_rows if _code(row.get("code"))]
    if not selected:
        return []

    session = requests.Session()
    try:
        org_ids = _load_cninfo_org_ids(session, timeout)
    except Exception as exc:
        reason = f"CNINFO_ORG_ID_FETCH_FAILED:{type(exc).__name__}"
        return [
            _unknown_row(
                _code(row.get("code")),
                str(row.get("normalized_industry") or row.get("industry") or ""),
                reason,
            )
            for row in selected
        ]

    results: list[dict[str, Any]] = []
    for row in selected:
        code = _code(row.get("code"))
        industry = str(row.get("normalized_industry") or row.get("industry") or "")
        org_id = org_ids.get(code)
        if not org_id:
            results.append(_unknown_row(code, industry, "CNINFO_ORG_ID_NOT_FOUND"))
            continue
        try:
            candidates = _query_cninfo_history(code, org_id, as_of, session, timeout)
        except Exception as exc:
            results.append(_unknown_row(code, industry, f"ANNUAL_REPORT_QUERY_FAILED:{type(exc).__name__}"))
            continue

        metrics: list[dict[str, Any]] = []
        source_rows: list[dict[str, Any]] = []
        report_texts: list[str] = []
        for candidate in candidates:
            try:
                response = session.get(candidate["url"], headers=REQUEST_HEADERS, timeout=timeout)
                response.raise_for_status()
                text, extraction_method = extract_text_from_response(
                    response.content, response.headers.get("Content-Type", "")
                )
            except Exception:
                continue
            if not text.strip():
                continue
            parsed = extract_report_metrics(text, int(candidate["fiscal_year"]))
            metrics.append(parsed)
            report_texts.append(text)
            source_rows.append({**candidate, "extraction_method": extraction_method})

        cyclical = _is_cyclical_or_resource(industry, report_texts)
        classification, reason = classify_multi_year_metrics(metrics, cyclical_or_resource=cyclical)
        coverage_years = sorted(
            int(item["fiscal_year"]) for item in metrics if _complete_record(item)
        )
        latest = max(source_rows, key=lambda item: item["publish_date"], default={})
        digest_payload = {
            "code": code,
            "rule": RULE_VERSION,
            "classification": classification,
            "reason": reason,
            "metrics": metrics,
            "sources": [item.get("url") for item in source_rows],
        }
        results.append({
            "code": code,
            "industry": industry,
            "evidence_kind": "multi_year_predictability",
            "indicator": "predictability_multi_year_official",
            "predictability_classification": classification,
            "reason_code": reason,
            "rule_version": RULE_VERSION,
            "coverage_years": coverage_years,
            "coverage_count": len(coverage_years),
            "metrics_by_year": metrics,
            "cyclical_or_resource": cyclical,
            "source_urls": [item.get("url") for item in source_rows],
            "evidence_status": "VERIFIED" if classification in {"PASS", "FAIL"} else "OBSERVED_CONTEXT",
            "source_type": "OFFICIAL_REPORT",
            "source_domain": source_domain(latest.get("url") or "https://www.cninfo.com.cn/"),
            "publish_date": latest.get("publish_date") or "",
            "original_url": latest.get("url") or "",
            "normalized_summary": (
                f"{classification}:{reason}; years={coverage_years}; "
                "unit_provenance=required; normalization=CNY_YUAN"
            ),
            "content_hash": content_hash(json.dumps(digest_payload, ensure_ascii=False, sort_keys=True)),
            "unit_provenance_required": True,
            "normalization_unit": "CNY_YUAN",
            "authority_crossed": False,
            "formal_decision": False,
            "adopted_for_gate": classification in {"PASS", "FAIL"},
            "collected_at": utc_now(),
        })
    return results
