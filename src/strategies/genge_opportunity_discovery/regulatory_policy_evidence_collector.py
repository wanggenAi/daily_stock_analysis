"""Collect official regulatory/policy evidence for the current research workset.

This is a slow-lane collector. It maps securities to industries only from reviewed
company-cycle evidence, scans official MIIT/NDRC listing pages for dated policy
items, and emits research-only Evidence Events. It never infers a Formal action.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

from .evidence_event_store import append_events

POLICY_SOURCES = (
    ("MIIT", "https://www.miit.gov.cn/zwgk/zcwj/index.html"),
    ("NDRC", "https://www.ndrc.gov.cn/xxgk/zcfb/"),
)
POLICY_TITLE_TOKENS = ("通知", "意见", "办法", "规定", "方案", "政策", "公告", "指导")
POSITIVE_TOKENS = ("支持", "鼓励", "促进", "加快", "提升", "推动", "扩大")
NEGATIVE_TOKENS = ("限制", "禁止", "暂停", "压减", "整治", "处罚", "淘汰")


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, Mapping) else {}


def _code(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())[-6:]
    return digits.zfill(6) if digits else ""


def _workset_codes(overlay: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in overlay.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        code = _code(row.get("code"))
        if code:
            result[code] = str(row.get("name") or "")
    return result


def _industry_map(path: Path, workset: set[str]) -> dict[str, str]:
    latest: dict[str, tuple[str, str]] = {}
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            code = _code(row.get("code"))
            if code not in workset:
                continue
            industry = str(row.get("industry") or "").strip()
            stamp = str(row.get("date") or "")
            if industry and (code not in latest or stamp >= latest[code][0]):
                latest[code] = (stamp, industry)
    return {code: value[1] for code, value in latest.items()}


def _aliases(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: dict[str, list[str]] = {}
    for industry, cfg in (payload.get("industries") or {}).items():
        values = [str(industry), *[str(x) for x in ((cfg or {}).get("aliases") or [])]]
        result[str(industry)] = [x for x in dict.fromkeys(v.strip() for v in values) if len(x) >= 2]
    return result


def _extract_date(text: str) -> str:
    match = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})", text)
    if not match:
        return ""
    y, m, d = match.groups()
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def _direction(title: str) -> str:
    if any(token in title for token in NEGATIVE_TOKENS):
        return "WEAKENING"
    if any(token in title for token in POSITIVE_TOKENS):
        return "STRENGTHENING"
    return "UNKNOWN"


def collect(
    *,
    overlay: Mapping[str, Any],
    company_cycle_evidence: Path,
    industry_alias_map: Path,
    as_of: date | None = None,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    as_of = as_of or datetime.now(timezone.utc).date()
    codes = _workset_codes(overlay)
    industries = _industry_map(company_cycle_evidence, set(codes))
    aliases = _aliases(industry_alias_map)
    observed_at = datetime.now(timezone.utc).isoformat()
    events: list[dict[str, Any]] = []
    fetch_failures: list[str] = []
    seen: set[tuple[str, str]] = set()

    for source_name, base_url in POLICY_SOURCES:
        try:
            response = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0 GenGe-evidence-slow-lane"}, timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as exc:
            fetch_failures.append(f"{source_name}:{type(exc).__name__}")
            continue
        for anchor in soup.find_all("a"):
            title = anchor.get_text(" ", strip=True)
            href = str(anchor.get("href") or "").strip()
            if not title or not href or not any(token in title for token in POLICY_TITLE_TOKENS):
                continue
            row_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else title
            published = _extract_date(row_text) or _extract_date(title)
            if not published or published > as_of.isoformat():
                continue
            try:
                age_days = (as_of - date.fromisoformat(published)).days
            except ValueError:
                continue
            if age_days > 180:
                continue
            url = urljoin(base_url, href)
            for code, industry in industries.items():
                terms = aliases.get(industry, [industry])
                matched = next((term for term in terms if term and term in title), "")
                if not matched or (code, url) in seen:
                    continue
                seen.add((code, url))
                events.append({
                    "code": code,
                    "name": codes.get(code, ""),
                    "observed_at": observed_at,
                    "published_at": f"{published}T00:00:00+00:00",
                    "source": f"official_policy:{source_name}",
                    "source_ref": url,
                    "evidence_type": "REGULATORY_POLICY",
                    "title": title,
                    "summary": f"Official policy title matched reviewed industry={industry}, term={matched}.",
                    "materiality": "MEDIUM",
                    "direction": _direction(title),
                    "thesis_link": "POLICY_CONTEXT_REQUIRES_REUNDERWRITING_IF_MATERIAL",
                    "confidence": "OFFICIAL_SOURCE_TITLE_MATCH",
                })

    if not industries:
        status = "CONNECTED_NO_REVIEWED_WORKSET_INDUSTRY_MAPPING"
    elif events:
        status = "CONNECTED_WITH_POLICY_EVENTS"
    elif len(fetch_failures) == len(POLICY_SOURCES):
        status = "SOURCE_FETCH_FAILED"
    else:
        status = "CONNECTED_NO_MATCHING_RECENT_POLICY_EVENTS"
    summary = {
        "generated_at": observed_at,
        "status": status,
        "workset_count": len(codes),
        "mapped_security_count": len(industries),
        "event_candidate_count": len(events),
        "fetch_failures": fetch_failures,
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }
    return events, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly-overlay", type=Path, default=Path("data/hourly_deep_overlay/latest.json"))
    parser.add_argument("--company-cycle-evidence", type=Path, default=Path("data/user_supplied/company_cycle_evidence.csv"))
    parser.add_argument("--industry-alias-map", type=Path, default=Path("config/industry_alias_map.yaml"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/policy_collector_status.json"))
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args(argv)
    events, status = collect(
        overlay=_load_json(args.hourly_overlay),
        company_cycle_evidence=args.company_cycle_evidence,
        industry_alias_map=args.industry_alias_map,
        timeout=args.timeout,
    )
    result = append_events(args.evidence_root, events) if events else {"accepted": 0, "duplicates": 0}
    status.update(result)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
