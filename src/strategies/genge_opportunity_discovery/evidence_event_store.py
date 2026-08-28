"""Durable, research-only evidence event store for GenGe V3.1.1.

The store is deliberately downstream of production authority. Evidence can raise
research priority or require re-underwriting, but it can never manufacture or
mutate a Formal BUY/HOLD/REDUCE/EXIT action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "GEN_GE_EVIDENCE_EVENT_STORE_V1"
ALLOWED_DIRECTIONS = {"STRENGTHENING", "WEAKENING", "NEUTRAL", "UNKNOWN"}
ALLOWED_MATERIALITY = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def _iso(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _code(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())[-6:]
    return text.zfill(6) if text else ""


def stable_evidence_id(event: Mapping[str, Any]) -> str:
    supplied = str(event.get("evidence_id") or "").strip()
    if supplied:
        return supplied
    basis = "|".join(
        [
            _code(event.get("code")),
            str(event.get("source") or "").strip(),
            str(event.get("source_ref") or event.get("url") or "").strip(),
            str(event.get("published_at") or event.get("observed_at") or "").strip(),
            str(event.get("title") or "").strip(),
        ]
    )
    return "ev_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def normalize_event(event: Mapping[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
    code = _code(event.get("code"))
    title = str(event.get("title") or "").strip()
    source = str(event.get("source") or "").strip()
    if not code or not title or not source:
        raise ValueError("evidence event requires code, title and source")

    observed = _iso(event.get("observed_at") or observed_at or datetime.now(timezone.utc).isoformat())
    if not observed:
        raise ValueError("evidence observed_at must be ISO-8601")
    published = _iso(event.get("published_at")) or observed
    published_at_adjusted = False
    if datetime.fromisoformat(published) > datetime.fromisoformat(observed):
        # Upstream exchange feeds can occasionally expose a next-calendar-day label
        # before that timestamp is actually observable. Research freshness must never
        # be driven by evidence from the future, so fail safe at the common store boundary.
        published = observed
        published_at_adjusted = True

    direction = str(event.get("direction") or "UNKNOWN").strip().upper()
    materiality = str(event.get("materiality") or "UNKNOWN").strip().upper()
    if direction not in ALLOWED_DIRECTIONS:
        direction = "UNKNOWN"
    if materiality not in ALLOWED_MATERIALITY:
        materiality = "UNKNOWN"

    normalized = {
        "contract_version": CONTRACT_VERSION,
        "evidence_id": stable_evidence_id(event),
        "code": code,
        "name": str(event.get("name") or "").strip(),
        "observed_at": observed,
        "published_at": published,
        "published_at_adjusted": published_at_adjusted,
        "source": source,
        "source_ref": str(event.get("source_ref") or event.get("url") or "").strip(),
        "evidence_type": str(event.get("evidence_type") or "OTHER").strip().upper(),
        "title": title,
        "summary": str(event.get("summary") or "").strip(),
        "materiality": materiality,
        "direction": direction,
        "thesis_link": str(event.get("thesis_link") or "").strip(),
        "value_anchor_impact": str(event.get("value_anchor_impact") or "UNASSESSED").strip().upper(),
        "sell_relevance": str(event.get("sell_relevance") or "UNASSESSED").strip().upper(),
        "confidence": str(event.get("confidence") or "SOURCE_ONLY").strip().upper(),
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "no_auto_trade": True,
    }
    return normalized


def load_events(root: Path, *, code: str | None = None) -> list[dict[str, Any]]:
    paths = [root / f"{_code(code)}.jsonl"] if code else sorted(root.glob("*.jsonl"))
    events: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                events.append(row)
    return events


def append_events(root: Path, events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    existing = {row.get("evidence_id") for row in load_events(root)}
    accepted: list[dict[str, Any]] = []
    duplicates = 0
    for raw in events:
        event = normalize_event(raw)
        if event["evidence_id"] in existing:
            duplicates += 1
            continue
        path = root / f"{event['code']}.jsonl"
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        existing.add(event["evidence_id"])
        accepted.append(event)

    all_events = load_events(root)
    latest_by_code: dict[str, dict[str, Any]] = {}
    for event in all_events:
        code = str(event.get("code") or "")
        prior = latest_by_code.get(code)
        if prior is None or str(event.get("published_at") or "") > str(prior.get("published_at") or ""):
            latest_by_code[code] = event
    index = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(all_events),
        "security_count": len(latest_by_code),
        "latest_by_code": latest_by_code,
        "formal_action_eligible": False,
        "no_auto_trade": True,
    }
    (root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"accepted": len(accepted), "duplicates": duplicates, "event_count": len(all_events)}


def recent_for_code(root: Path, code: str, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = load_events(root, code=code)
    rows.sort(key=lambda r: str(r.get("published_at") or r.get("observed_at") or ""), reverse=True)
    return rows[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="JSON array or JSONL evidence file")
    parser.add_argument("--root", type=Path, default=Path("data/evidence_events"))
    args = parser.parse_args(argv)
    text = args.input.read_text(encoding="utf-8")
    if args.input.suffix.lower() == ".jsonl":
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("events", [payload])
    if not isinstance(payload, list):
        raise ValueError("evidence input must be a JSON array or JSONL")
    result = append_events(args.root, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
