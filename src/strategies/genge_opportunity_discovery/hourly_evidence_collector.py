"""Research-only hourly announcement collector for the authorized GenGe workset.

This collector uses public announcement metadata to create normalized Evidence
Events. It never recomputes or mutates Formal actions. Source failures are
reported explicitly and do not fail-open into trading decisions.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evidence_event_store import append_events

SOURCE = "eastmoney_announcement"

NEGATIVE_KEYWORDS = (
    "处罚", "立案", "调查", "风险提示", "业绩预亏", "亏损", "下修", "减持", "终止", "诉讼", "仲裁", "违约", "退市",
)
POSITIVE_KEYWORDS = (
    "中标", "签订合同", "订单", "回购", "增持", "业绩预增", "扭亏", "获批", "注册获批", "重大合同",
)
EARNINGS_KEYWORDS = ("年度报告", "半年度报告", "季度报告", "业绩预告", "业绩快报")


def _classify(title: str) -> tuple[str, str, str]:
    text = title.strip()
    if any(k in text for k in EARNINGS_KEYWORDS):
        evidence_type = "EARNINGS_OR_FINANCIAL_REPORT"
    elif any(k in text for k in ("中标", "合同", "订单")):
        evidence_type = "ORDER_OR_CONTRACT"
    elif any(k in text for k in ("处罚", "立案", "调查", "监管")):
        evidence_type = "REGULATORY_OR_POLICY"
    elif any(k in text for k in ("回购", "增持", "减持")):
        evidence_type = "CAPITAL_MARKETS_OR_OWNERSHIP"
    else:
        evidence_type = "COMPANY_ANNOUNCEMENT"
    if any(k in text for k in NEGATIVE_KEYWORDS):
        direction = "WEAKENING"
        materiality = "HIGH" if any(k in text for k in ("立案", "处罚", "退市", "违约", "业绩预亏")) else "MEDIUM"
    elif any(k in text for k in POSITIVE_KEYWORDS):
        direction = "STRENGTHENING"
        materiality = "MEDIUM"
    else:
        direction = "NEUTRAL"
        materiality = "LOW"
    return evidence_type, direction, materiality


def _codes_from_hourly(hourly_path: Path) -> list[str]:
    payload = json.loads(hourly_path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    return sorted({str(row.get("code") or "").zfill(6) for row in rows if row.get("code")})


def fetch_announcements(code: str, *, page_size: int = 30) -> list[Mapping[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "sr": "-1",
            "page_size": str(page_size),
            "page_index": "1",
            "ann_type": "A",
            "client_source": "web",
            "stock_list": code,
        }
    )
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GenGe-hourly-evidence"})
    with urllib.request.urlopen(req, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    data = payload.get("data") or {}
    rows = data.get("list") or []
    return [row for row in rows if isinstance(row, Mapping)]


def collect(codes: Iterable[str], *, lookback_hours: int = 72) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    observed = datetime.now(timezone.utc).isoformat()
    events: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for code in codes:
        try:
            rows = fetch_announcements(code)
        except Exception as exc:
            failures.append({"code": code, "error": f"{type(exc).__name__}:{exc}"})
            continue
        for row in rows:
            title = str(row.get("title") or "").strip()
            notice_date = str(row.get("notice_date") or row.get("display_time") or "").strip()
            if not title:
                continue
            published_at = notice_date
            try:
                parsed = datetime.fromisoformat(notice_date.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed.astimezone(timezone.utc) < cutoff:
                    continue
                published_at = parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
            evidence_type, direction, materiality = _classify(title)
            art_code = str(row.get("art_code") or row.get("notice_id") or "").strip()
            source_ref = (
                "https://data.eastmoney.com/notices/detail/" + code + "/" + art_code + ".html"
                if art_code else ""
            )
            events.append(
                {
                    "code": code,
                    "name": str(row.get("short_name") or "").strip(),
                    "observed_at": observed,
                    "published_at": published_at or observed,
                    "source": SOURCE,
                    "source_ref": source_ref,
                    "evidence_type": evidence_type,
                    "title": title,
                    "summary": "Public company announcement metadata; content requires Deep Review before thesis/value changes.",
                    "materiality": materiality,
                    "direction": direction,
                    "thesis_link": "UNASSESSED_BY_METADATA_COLLECTOR",
                    "value_anchor_impact": "REUNDERWRITE_REQUIRED" if materiality == "HIGH" else "UNASSESSED",
                    "sell_relevance": "REVIEW" if direction == "WEAKENING" else "UNASSESSED",
                    "confidence": "SOURCE_METADATA",
                }
            )
    return events, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly-overlay", type=Path, default=Path("data/hourly_deep_overlay/latest.json"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--status-output", type=Path, default=Path("data/evidence_events/collector_status.json"))
    parser.add_argument("--lookback-hours", type=int, default=72)
    args = parser.parse_args(argv)
    codes = _codes_from_hourly(args.hourly_overlay)
    events, failures = collect(codes, lookback_hours=args.lookback_hours)
    result = append_events(args.evidence_root, events)
    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "workset_count": len(codes),
        "fetched_event_count": len(events),
        "accepted_event_count": result["accepted"],
        "duplicate_event_count": result["duplicates"],
        "source_failure_count": len(failures),
        "source_failures": failures,
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "no_auto_trade": True,
    }
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
