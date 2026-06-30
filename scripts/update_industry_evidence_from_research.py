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


def _normalize_confidence(value: Any, missing_source: bool) -> str:
    if missing_source:
        return "LOW"
    raw = _as_text(value).upper()
    return raw if raw in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM"


def _normalize_source_type(value: Any, missing_source: bool) -> str:
    if missing_source:
        return "manual_template"
    raw = _as_text(value).lower()
    if raw in {"provider_derived", "provider", "akshare", "qstock", "tushare", "baostock"}:
        return "provider_derived"
    if raw in {"verified_multi_source", "verified", "multi_source"}:
        return "verified_multi_source"
    if raw in {"manual_template", "template", "example", "demo"}:
        return "manual_template"
    return "user_supplied"


def _has_required_evidence_fields(row: Dict[str, Any], *, company: bool) -> bool:
    required = ["date", "industry", "evidence_name", "evidence_value", "evidence_direction"]
    if company:
        required.insert(1, "code")
    return all(_as_text(row.get(key)) for key in required)


def _finalize_row(row: Dict[str, Any], source_file: Path, *, company: bool) -> Dict[str, str] | None:
    if not _has_required_evidence_fields(row, company=company):
        return None
    missing_source = not _as_text(row.get("source"))
    note = _as_text(row.get("note"))
    if missing_source:
        note = (note + "；" if note else "") + f"missing source downgraded from {source_file.name}"
    normalized = {
        "date": _as_text(row.get("date") or row.get("evidence_date")),
        "industry": _as_text(row.get("industry")),
        "evidence_name": _as_text(row.get("evidence_name") or row.get("name")),
        "evidence_value": _as_text(row.get("evidence_value") or row.get("value")),
        "evidence_direction": _normalize_direction(row.get("evidence_direction") or row.get("direction")),
        "source": _as_text(row.get("source")) or f"missing_source:{source_file.name}",
        "source_type": _normalize_source_type(row.get("source_type"), missing_source),
        "confidence": _normalize_confidence(row.get("confidence"), missing_source),
        "note": note,
    }
    if company:
        normalized.update(
            {
                "code": _as_text(row.get("code")).zfill(6),
                "stock_name": _as_text(row.get("stock_name")),
            }
        )
    return normalized


def _extract_json_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        payload = {"industry_evidence": raw, "company_evidence": []}
    elif isinstance(raw, dict):
        payload = raw
    else:
        return [], [], 0
    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    skipped = 0
    for item in payload.get("industry_evidence") or []:
        row = _finalize_row(dict(item or {}), path, company=False)
        if row:
            industry_rows.append(row)
        else:
            skipped += 1
    for item in payload.get("company_evidence") or []:
        row = _finalize_row(dict(item or {}), path, company=True)
        if row:
            company_rows.append(row)
        else:
            skipped += 1
    return industry_rows, company_rows, skipped


def _parse_key_value_line(line: str) -> Dict[str, str]:
    return {match.group(1).strip(): match.group(2).strip() for match in KEY_VALUE_RE.finditer(line)}


def _extract_markdown_rows(path: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], int]:
    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if "evidence_name" not in line and "evidence_value" not in line:
            continue
        raw = _parse_key_value_line(line)
        if not raw:
            skipped += 1
            continue
        company = bool(_as_text(raw.get("code")))
        row = _finalize_row(raw, path, company=company)
        if row and company:
            company_rows.append(row)
        elif row:
            industry_rows.append(row)
        else:
            skipped += 1
    return industry_rows, company_rows, skipped


def _iter_research_files(research_dir: Path) -> Iterable[Path]:
    for pattern in ("*.json", "*.md"):
        yield from sorted(research_dir.rglob(pattern))


def _write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
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
        f"- skipped_rows: {stats.get('skipped_rows', 0)}",
        f"- missing_source_rows: {stats.get('missing_source_rows', 0)}",
        "",
        "说明：缺少 source 的证据已降级为 manual_template/LOW；脚本只抽取结构化 evidence item，不采纳未标来源的叙述性结论。",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    research_dir = Path(args.research_dir)
    if not research_dir.exists():
        raise FileNotFoundError(f"research directory not found: {research_dir}")

    industry_rows: List[Dict[str, str]] = []
    company_rows: List[Dict[str, str]] = []
    skipped = 0
    files: List[str] = []
    for path in _iter_research_files(research_dir):
        files.append(str(path))
        if path.suffix.lower() == ".json":
            industry_part, company_part, skipped_part = _extract_json_rows(path)
        else:
            industry_part, company_part, skipped_part = _extract_markdown_rows(path)
        industry_rows.extend(industry_part)
        company_rows.extend(company_part)
        skipped += skipped_part

    output = Path(args.output)
    company_output = Path(args.company_output)
    _write_csv(output, INDUSTRY_COLUMNS, industry_rows)
    _write_csv(company_output, COMPANY_COLUMNS, company_rows)
    missing_source_rows = sum(1 for row in industry_rows + company_rows if row.get("source", "").startswith("missing_source:"))
    stats = {
        "files_scanned": len(files),
        "industry_rows": len(industry_rows),
        "company_rows": len(company_rows),
        "skipped_rows": skipped,
        "missing_source_rows": missing_source_rows,
    }
    _write_quality_report(output.parent / "evidence_quality_report.md", stats, files)
    print(f"industry_output={output}")
    print(f"company_output={company_output}")
    print(f"quality_report={output.parent / 'evidence_quality_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
