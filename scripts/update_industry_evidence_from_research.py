#!/usr/bin/env python3
"""Build industry/company evidence CSVs from local research notes.

The script extracts evidence rows only. It does not trust narrative
conclusions in markdown notes and downgrades rows without a concrete source.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


INDUSTRY_COLUMNS = [
    "date",
    "industry",
    "evidence_name",
    "evidence_value",
    "evidence_direction",
    "source",
    "source_type",
    "confidence",
    "note",
]
COMPANY_COLUMNS = [
    "date",
    "code",
    "stock_name",
    "industry",
    "evidence_name",
    "evidence_value",
    "evidence_direction",
    "source",
    "source_type",
    "confidence",
    "note",
]
REJECTED_COLUMNS = [
    "source_file",
    "row_type",
    "reason",
    "date",
    "code",
    "stock_name",
    "industry",
    "evidence_name",
    "evidence_value",
    "evidence_direction",
    "source",
    "source_type",
    "confidence",
    "note",
]
ALLOWED_SOURCE_TYPES = {
    "provider_derived",
    "official_report",
    "company_announcement",
    "exchange_disclosure",
    "research_report_summary",
    "news_summary",
    "user_supplied",
    "verified_multi_source",
    "manual_template",
}
AUTHORITATIVE_SOURCE_TYPES = {
    "provider_derived",
    "official_report",
    "company_announcement",
    "exchange_disclosure",
    "verified_multi_source",
}
HIGH_AUTHORITY_SOURCE_TYPES = {
    "official_report",
    "company_announcement",
    "exchange_disclosure",
    "verified_multi_source",
}
LOW_AUTHORITY_SOURCE_TYPES = {"manual_template", "news_summary"}
KEY_VALUE_RE = re.compile(r"([A-Za-z_]+)\s*[:=]\s*([^,;|]+)")


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_direction(value: Any) -> str:
    raw = _as_text(value).upper()
    if raw in {"+", "POS", "POSITIVE", "利好"}:
        return "POSITIVE"
    if raw in {"-", "NEG", "NEGATIVE", "利空"}:
        return "NEGATIVE"
    return "NEUTRAL"


def _normalize_confidence(value: Any, source_type: str) -> str:
    raw = _as_text(value).upper()
    confidence = raw if raw in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM"
    if source_type == "news_summary":
        return "LOW" if confidence == "HIGH" else confidence
    if source_type not in HIGH_AUTHORITY_SOURCE_TYPES and confidence == "HIGH":
        return "MEDIUM"
    return confidence


def _normalize_source_type(value: Any) -> str:
    raw = _as_text(value).lower()
    if raw in {"provider_derived", "provider", "akshare", "qstock", "tushare", "baostock"}:
        return "provider_derived"
    if raw in {"official_report", "official", "government", "stats", "nbs", "moa", "ndrc"}:
        return "official_report"
    if raw in {"company_announcement", "announcement", "annual_report", "quarterly_report"}:
        return "company_announcement"
    if raw in {"exchange_disclosure", "exchange", "cninfo", "szse", "sse"}:
        return "exchange_disclosure"
    if raw in {"research_report_summary", "research_report", "broker_summary", "industry_report"}:
        return "research_report_summary"
    if raw in {"news_summary", "news", "media"}:
        return "news_summary"
    if raw in {"verified_multi_source", "verified", "multi_source"}:
        return "verified_multi_source"
    if raw in {"manual_template", "template", "example", "demo"}:
        return "manual_template"
    return "user_supplied"


def _missing_required_evidence_fields(row: Dict[str, Any], *, company: bool) -> List[str]:
    fields = {
        "industry": _as_text(row.get("industry")),
        "evidence_name": _as_text(row.get("evidence_name") or row.get("name")),
        "evidence_value": _as_text(row.get("evidence_value") or row.get("value")),
        "evidence_direction": _as_text(row.get("evidence_direction") or row.get("direction")),
    }
    if company:
        fields["code"] = _as_text(row.get("code"))
    return [name for name, value in fields.items() if not value]


def _has_required_evidence_fields(row: Dict[str, Any], *, company: bool) -> bool:
    checks = [
        _as_text(row.get("industry")),
        _as_text(row.get("evidence_name") or row.get("name")),
        _as_text(row.get("evidence_value") or row.get("value")),
        _as_text(row.get("evidence_direction") or row.get("direction")),
    ]
    if company:
        checks.insert(1, _as_text(row.get("code")))
    return all(checks)


def _reject_row(row: Dict[str, Any], source_file: Path, *, company: bool, reason: str) -> Dict[str, str]:
    return {
        "source_file": str(source_file),
        "row_type": "company" if company else "industry",
        "reason": reason,
        "date": _as_text(row.get("date") or row.get("evidence_date")),
        "code": _as_text(row.get("code")).zfill(6) if _as_text(row.get("code")) else "",
        "stock_name": _as_text(row.get("stock_name")),
        "industry": _as_text(row.get("industry")),
        "evidence_name": _as_text(row.get("evidence_name") or row.get("name")),
        "evidence_value": _as_text(row.get("evidence_value") or row.get("value")),
        "evidence_direction": _as_text(row.get("evidence_direction") or row.get("direction")),
        "source": _as_text(row.get("source")),
        "source_type": _as_text(row.get("source_type")),
        "confidence": _as_text(row.get("confidence")),
        "note": _as_text(row.get("note")),
    }


def _finalize_row(row: Dict[str, Any], source_file: Path, *, company: bool) -> Tuple[Dict[str, str] | None, Dict[str, str] | None]:
    missing_required = _missing_required_evidence_fields(row, company=company)
    if missing_required:
        return None, _reject_row(row, source_file, company=company, reason="missing_required_fields")
    if not _as_text(row.get("date") or row.get("evidence_date")):
        return None, _reject_row(row, source_file, company=company, reason="missing_date")
    if not _as_text(row.get("source")):
        return None, _reject_row(row, source_file, company=company, reason="missing_source")
    source_type = _normalize_source_type(row.get("source_type"))
    if source_type not in ALLOWED_SOURCE_TYPES:
        return None, _reject_row(row, source_file, company=company, reason="unsupported_source_type")
    normalized = {
        "date": _as_text(row.get("date") or row.get("evidence_date")),
        "industry": _as_text(row.get("industry")),
        "evidence_name": _as_text(row.get("evidence_name") or row.get("name")),
        "evidence_value": _as_text(row.get("evidence_value") or row.get("value")),
        "evidence_direction": _normalize_direction(row.get("evidence_direction") or row.get("direction")),
        "source": _as_text(row.get("source")),
        "source_type": source_type,
        "confidence": _normalize_confidence(row.get("confidence"), source_type),
        "note": _as_text(row.get("note")),
    }
    if company:
        normalized.update(
            {
                "code": _as_text(row.get("code")).zfill(6),
                "stock_name": _as_text(row.get("stock_name")),
            }
        )
    return normalized, None


def _extract_json_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        payload = {"industry_evidence": raw, "company_evidence": []}
    elif isinstance(raw, dict):
        payload = raw
    else:
        return [], [], [], 0
    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    rejected_rows: List[Dict[str, str]] = []
    skipped = 0
    for item in payload.get("industry_evidence") or []:
        row, rejected = _finalize_row(dict(item or {}), path, company=False)
        if row:
            industry_rows.append(row)
        elif rejected:
            rejected_rows.append(rejected)
        else:
            skipped += 1
    for item in payload.get("company_evidence") or []:
        row, rejected = _finalize_row(dict(item or {}), path, company=True)
        if row:
            company_rows.append(row)
        elif rejected:
            rejected_rows.append(rejected)
        else:
            skipped += 1
    return industry_rows, company_rows, rejected_rows, skipped


def _parse_key_value_line(line: str) -> Dict[str, str]:
    return {match.group(1).strip(): match.group(2).strip() for match in KEY_VALUE_RE.finditer(line)}


def _extract_markdown_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], int]:
    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    rejected_rows: List[Dict[str, str]] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if "evidence_name" not in line and "evidence_value" not in line:
            continue
        raw = _parse_key_value_line(line)
        if not raw:
            skipped += 1
            continue
        company = bool(_as_text(raw.get("code")))
        row, rejected = _finalize_row(raw, path, company=company)
        if row and company:
            company_rows.append(row)
        elif row:
            industry_rows.append(row)
        elif rejected:
            rejected_rows.append(rejected)
        else:
            skipped += 1
    return industry_rows, company_rows, rejected_rows, skipped


def _iter_research_files(research_dir: Path) -> Iterable[Path]:
    for pattern in ("*.json", "*.md"):
        yield from sorted(research_dir.rglob(pattern))


def _write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _write_quality_report(path: Path, stats: Dict[str, int], files: List[str]) -> None:
    lines = [
        "# Evidence Quality Report",
        "",
        f"- files_scanned: {stats.get('files_scanned', 0)}",
        f"- industry_rows: {stats.get('industry_rows', 0)}",
        f"- company_rows: {stats.get('company_rows', 0)}",
        f"- rejected_rows: {stats.get('rejected_rows', 0)}",
        f"- skipped_rows: {stats.get('skipped_rows', 0)}",
        f"- missing_source_rows: {stats.get('missing_source_rows', 0)}",
        f"- missing_date_rows: {stats.get('missing_date_rows', 0)}",
        f"- high_confidence_rows: {stats.get('high_confidence_rows', 0)}",
        "",
        "说明：缺少 source/date 或必需字段的证据不会进入正式 CSV，而是写入 rejected_evidence.csv；脚本只抽取结构化 evidence item，不采纳未标来源的叙述性结论，也不会从叙述文本自动推断 HIGH。",
        "",
        "## Files",
        "",
    ]
    lines.extend(f"- {name}" for name in files)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract cycle evidence CSVs from local research files.")
    parser.add_argument("--research-dir", default="research/industry_cycle/")
    parser.add_argument("--output", default="data/user_supplied/industry_cycle_evidence.csv")
    parser.add_argument("--company-output", default="data/user_supplied/company_cycle_evidence.csv")
    parser.add_argument("--quality-report", default="")
    parser.add_argument("--rejected-output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    research_dir = Path(args.research_dir)
    if not research_dir.exists():
        raise FileNotFoundError(f"research directory not found: {research_dir}")

    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    rejected_rows: List[Dict[str, str]] = []
    skipped = 0
    files: List[str] = []
    for path in _iter_research_files(research_dir):
        files.append(str(path))
        if path.suffix.lower() == ".json":
            industry_part, company_part, rejected_part, skipped_part = _extract_json_rows(path)
        else:
            industry_part, company_part, rejected_part, skipped_part = _extract_markdown_rows(path)
        industry_rows.extend(industry_part)
        company_rows.extend(company_part)
        rejected_rows.extend(rejected_part)
        skipped += skipped_part

    output = Path(args.output)
    company_output = Path(args.company_output)
    quality_report = Path(args.quality_report) if args.quality_report else output.parent / "evidence_quality_report.md"
    rejected_output = Path(args.rejected_output) if args.rejected_output else output.parent / "rejected_evidence.csv"
    _write_csv(output, INDUSTRY_COLUMNS, industry_rows)
    _write_csv(company_output, COMPANY_COLUMNS, company_rows)
    _write_csv(rejected_output, REJECTED_COLUMNS, rejected_rows)
    stats = {
        "files_scanned": len(files),
        "industry_rows": len(industry_rows),
        "company_rows": len(company_rows),
        "rejected_rows": len(rejected_rows),
        "skipped_rows": skipped,
        "missing_source_rows": sum(1 for row in rejected_rows if row.get("reason") == "missing_source"),
        "missing_date_rows": sum(1 for row in rejected_rows if row.get("reason") == "missing_date"),
        "high_confidence_rows": sum(1 for row in industry_rows + company_rows if row.get("confidence") == "HIGH"),
    }
    _write_quality_report(quality_report, stats, files)
    print(f"industry_output={output}")
    print(f"company_output={company_output}")
    print(f"quality_report={quality_report}")
    print(f"rejected_output={rejected_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
