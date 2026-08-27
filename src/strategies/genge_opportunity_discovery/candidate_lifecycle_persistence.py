"""Persist candidate lifecycle state after a finalized GenGe V3.1.1 snapshot.

This module sits strictly downstream of Canonical Authority. It never filters
broad Discovery and never creates a Formal BUY/ADD/REDUCE/EXIT action.

The durable JSON state is the lifecycle source of truth. ``V31_CANDIDATE_LEDGER.md``
is a generated human-readable projection only. For the first migration, an
existing legacy Markdown ledger may be imported so historically researched names
are not silently forgotten when the state machine becomes authoritative.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .candidate_lifecycle_state import (
    ACTIVE,
    ARCHIVED,
    INVALIDATED,
    LIFECYCLE_CONTRACT_VERSION,
    apply_snapshot,
    empty_state,
    load_state,
    write_state,
)

LEDGER_PROJECTION_VERSION = "GEN_GE_V31_CANDIDATE_LEDGER_PROJECTION_V1"
LEGACY_IMPORT_EVENT = "LEGACY_IMPORT"


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _leading_int(value: str, default: int = 0) -> int:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else default


def _legacy_state_for_section(section: str | None) -> str | None:
    if section == "active":
        return ACTIVE
    if section == "archived":
        return ARCHIVED
    if section == "invalidated":
        return INVALIDATED
    return None


def bootstrap_state_from_legacy_ledger(path: Path) -> dict[str, Any]:
    """Import lifecycle identity from the old hand-maintained Markdown ledger.

    The importer is intentionally conservative. It imports lifecycle membership,
    identity, tier, seen count and a few last-known fields, but does not convert
    prose research notes into evidence or Formal actions.
    """
    state = empty_state()
    if not path.exists():
        state["bootstrap_source"] = "EMPTY_NO_LEGACY_LEDGER"
        return state

    section: str | None = None
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        code = _code(current.get("code"))
        lifecycle_state = _legacy_state_for_section(current.get("section"))
        if code and lifecycle_state:
            seen_count = max(0, int(current.get("seen_count") or 0))
            candidate = {
                "code": code,
                "stock_name": str(current.get("stock_name") or ""),
                "lifecycle_state": lifecycle_state,
                "research_tier": str(current.get("research_tier") or ""),
                "first_seen_snapshot_id": "",
                "first_seen_source_run_id": "",
                "last_seen_snapshot_id": "",
                "last_seen_source_run_id": "",
                "seen_count": seen_count,
                "last_formal_action": str(current.get("last_formal_action") or ""),
                "last_valuation_confidence": str(current.get("valuation_confidence") or ""),
                "last_event": LEGACY_IMPORT_EVENT,
                "last_event_at": "",
                "applied_evidence_ids": [],
                "history": [],
                "legacy_imported": True,
                "legacy_first_seen_text": str(current.get("first_seen") or ""),
                "legacy_last_seen_text": str(current.get("last_seen") or ""),
                "legacy_seen_count_imported": seen_count,
            }
            state["candidates"][code] = candidate
        current = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "## Active candidate ledger":
            flush()
            section = "active"
            continue
        if line.startswith("## Archived"):
            flush()
            section = "archived"
            continue
        if line.startswith("## INVALIDATED") or line.startswith("## Invalidated"):
            flush()
            section = "invalidated"
            continue
        if line.startswith("## "):
            flush()
            section = None
            continue
        if line.startswith("### ") and section is not None:
            flush()
            heading = line[4:].strip()
            parts = heading.split(None, 1)
            code = _code(parts[0] if parts else "")
            if len(code) == 6 and code.isdigit():
                current = {
                    "section": section,
                    "code": code,
                    "stock_name": parts[1].strip() if len(parts) > 1 else "",
                }
            continue
        if current is None or not line.startswith("-"):
            continue

        normalized = line.lstrip("- ").replace("**", "")
        if ":" not in normalized:
            continue
        key, value = normalized.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "first_seen":
            current["first_seen"] = value
        elif key == "last_seen":
            current["last_seen"] = value
        elif key == "seen_count":
            current["seen_count"] = _leading_int(value, 0)
        elif key == "current tier":
            current["research_tier"] = value
        elif key == "valuation confidence":
            current["valuation_confidence"] = value
        elif key == "genge v3.1.1 production action":
            current["last_formal_action"] = value.split()[0].strip().upper() if value else ""

    flush()
    state["bootstrap_source"] = "LEGACY_MARKDOWN"
    state["legacy_ledger_path"] = str(path)
    state["legacy_imported_candidate_count"] = len(state["candidates"])
    return state


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[int, int, str]:
    lifecycle = str(candidate.get("lifecycle_state") or "")
    state_rank = {ACTIVE: 0, ARCHIVED: 1, INVALIDATED: 2}.get(lifecycle, 9)
    tier = str(candidate.get("research_tier") or "").upper()
    if tier.startswith("A1"):
        tier_rank = 0
    elif tier.startswith("A2"):
        tier_rank = 1
    elif "BUY_REVIEW" in tier:
        tier_rank = 2
    elif "WATCH" in tier:
        tier_rank = 3
    elif "WAIT" in tier:
        tier_rank = 4
    else:
        tier_rank = 9
    return state_rank, tier_rank, str(candidate.get("code") or "")


def render_ledger_projection(state: Mapping[str, Any]) -> str:
    candidates = list((state.get("candidates") or {}).values())
    candidates = [row for row in candidates if isinstance(row, Mapping)]
    candidates.sort(key=_candidate_sort_key)

    active = [row for row in candidates if row.get("lifecycle_state") == ACTIVE]
    inactive = [row for row in candidates if row.get("lifecycle_state") in {ARCHIVED, INVALIDATED}]

    lines = [
        "# V31_CANDIDATE_LEDGER",
        "",
        "> **GENERATED FILE — DO NOT EDIT LIFECYCLE FIELDS MANUALLY.**",
        ">",
        "> Machine source of truth: `data/opportunity_snapshots/candidate_lifecycle_state.json`.",
        "> This Markdown file is only a human-readable projection. Broad Discovery remains ledger-independent,",
        "> and this lifecycle memory cannot grant a Formal BUY/ADD/REDUCE/EXIT action.",
        "",
        f"- projection_version: `{LEDGER_PROJECTION_VERSION}`",
        f"- lifecycle_contract: `{state.get('contract_version') or ''}`",
        f"- latest_applied_snapshot_id: `{state.get('latest_applied_snapshot_id') or ''}`",
        f"- latest_research_as_of: `{state.get('latest_research_as_of') or ''}`",
        f"- active_candidates: {len(active)}",
        f"- archived_or_invalidated_candidates: {len(inactive)}",
        f"- lifecycle_event_count: {int(state.get('event_count') or 0)}",
        "- no_auto_trade: `true`",
        "- discovery_is_filtered_by_lifecycle: `false`",
        "",
        "## Active candidate ledger",
        "",
        "| Code | Name | Tier | Seen | Last Formal Action | Valuation Confidence | Last Snapshot | Last Event |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]

    for row in active:
        lines.append(
            "| {code} | {name} | {tier} | {seen} | {action} | {confidence} | {snapshot} | {event} |".format(
                code=row.get("code") or "",
                name=row.get("stock_name") or "",
                tier=row.get("research_tier") or "",
                seen=int(row.get("seen_count") or 0),
                action=row.get("last_formal_action") or "",
                confidence=row.get("last_valuation_confidence") or "",
                snapshot=row.get("last_seen_snapshot_id") or "LEGACY_IMPORT",
                event=row.get("last_event") or "",
            )
        )

    if not active:
        lines.append("| - | - | - | 0 | - | - | - | - |")

    for row in active:
        lines.extend(_render_candidate_detail(row))

    lines.extend([
        "",
        "## Archived / INVALIDATED candidate ledger",
        "",
        "| Code | Name | Lifecycle State | Tier | Seen | Last Snapshot | Last Event |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ])
    for row in inactive:
        lines.append(
            "| {code} | {name} | {state} | {tier} | {seen} | {snapshot} | {event} |".format(
                code=row.get("code") or "",
                name=row.get("stock_name") or "",
                state=row.get("lifecycle_state") or "",
                tier=row.get("research_tier") or "",
                seen=int(row.get("seen_count") or 0),
                snapshot=row.get("last_seen_snapshot_id") or "LEGACY_IMPORT",
                event=row.get("last_event") or "",
            )
        )
    if not inactive:
        lines.append("| - | - | - | - | 0 | - | - |")
    for row in inactive:
        lines.extend(_render_candidate_detail(row))

    lines.extend([
        "",
        "## Contract",
        "",
        "- Re-reading the same canonical snapshot is idempotent and must not increment `seen_count`.",
        "- Absence from a snapshot does not automatically archive or invalidate a candidate.",
        "- Archived/INVALIDATED rediscovery requires explicit evidence-backed reactivation.",
        "- Explicit upgrade/downgrade/archive/invalidate/reactivate events require unique evidence IDs.",
        "- The lifecycle state is downstream memory only; it must never filter broad Discovery.",
        "- Formal actions remain owned by a newly validated Canonical Snapshot, never by this ledger.",
        "",
    ])
    return "\n".join(lines)


def _render_candidate_detail(row: Mapping[str, Any]) -> list[str]:
    history = [item for item in list(row.get("history") or []) if isinstance(item, Mapping)]
    lines = [
        "",
        f"### {row.get('code') or ''} {row.get('stock_name') or ''}",
        "",
        f"- **lifecycle_state:** {row.get('lifecycle_state') or ''}",
        f"- **current tier:** {row.get('research_tier') or ''}",
        f"- **seen_count:** {int(row.get('seen_count') or 0)}",
        f"- **last_seen_snapshot_id:** {row.get('last_seen_snapshot_id') or ''}",
        f"- **last_seen_source_run_id:** {row.get('last_seen_source_run_id') or ''}",
        f"- **last Formal action:** {row.get('last_formal_action') or ''}",
        f"- **valuation confidence:** {row.get('last_valuation_confidence') or ''}",
        f"- **last lifecycle event:** {row.get('last_event') or ''}",
    ]
    if row.get("legacy_imported"):
        lines.append("- **legacy migration:** imported once from the pre-state-machine Markdown ledger")
    lines.extend(["", "#### Delta history"])
    if history:
        for event in history[-10:]:
            evidence = str(event.get("evidence_id") or "")
            suffix = f"; evidence `{evidence}`" if evidence else ""
            lines.append(
                f"- {event.get('observed_at') or ''} — **{event.get('event') or ''}**"
                f"; snapshot `{event.get('snapshot_id') or ''}`{suffix}"
            )
    else:
        lines.append("- No machine lifecycle events recorded after migration yet.")
    return lines


def persist_finalized_snapshot(
    *,
    snapshot_path: Path,
    state_path: Path,
    projection_path: Path,
    legacy_ledger: Path | None = None,
    events_path: Path | None = None,
    summary_path: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be a JSON object")

    bootstrapped = False
    if state_path.exists():
        state = load_state(state_path)
    else:
        state = bootstrap_state_from_legacy_ledger(legacy_ledger) if legacy_ledger else empty_state()
        bootstrapped = True

    state, events = apply_snapshot(state, snapshot)
    state["projection_version"] = LEDGER_PROJECTION_VERSION
    state["last_persistence_bootstrapped"] = bootstrapped
    state["last_persisted_snapshot_id"] = str(snapshot.get("snapshot_id") or "")
    state["last_persisted_source_run_id"] = str(snapshot.get("source_run_id") or "")
    write_state(state_path, state)

    projection_path.parent.mkdir(parents=True, exist_ok=True)
    projection_path.write_text(render_ledger_projection(state), encoding="utf-8")

    if events_path:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary_path:
        summary = {
            "contract_version": LIFECYCLE_CONTRACT_VERSION,
            "projection_version": LEDGER_PROJECTION_VERSION,
            "canonical_snapshot_id": snapshot.get("snapshot_id"),
            "canonical_source_run_id": snapshot.get("source_run_id"),
            "bootstrapped_from_legacy": bootstrapped and state.get("bootstrap_source") == "LEGACY_MARKDOWN",
            "snapshot_event_count": len(events),
            "candidate_count": len(state.get("candidates") or {}),
            "active_count": sum(
                1 for row in (state.get("candidates") or {}).values()
                if isinstance(row, Mapping) and row.get("lifecycle_state") == ACTIVE
            ),
            "inactive_count": sum(
                1 for row in (state.get("candidates") or {}).values()
                if isinstance(row, Mapping) and row.get("lifecycle_state") in {ARCHIVED, INVALIDATED}
            ),
            "latest_applied_snapshot_id": state.get("latest_applied_snapshot_id"),
            "latest_research_as_of": state.get("latest_research_as_of"),
            "no_auto_trade": True,
            "discovery_is_filtered_by_lifecycle": False,
        }
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return state, events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--projection", type=Path, required=True)
    parser.add_argument("--legacy-ledger", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)

    state, events = persist_finalized_snapshot(
        snapshot_path=args.snapshot,
        state_path=args.state,
        projection_path=args.projection,
        legacy_ledger=args.legacy_ledger,
        events_path=args.events,
        summary_path=args.summary,
    )
    print(json.dumps({
        "contract_version": LIFECYCLE_CONTRACT_VERSION,
        "projection_version": LEDGER_PROJECTION_VERSION,
        "latest_applied_snapshot_id": state.get("latest_applied_snapshot_id"),
        "candidate_count": len(state.get("candidates") or {}),
        "new_events": len(events),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
